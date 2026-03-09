import os
import json
import re
import csv
import io
import base64
import hashlib
import secrets
import psycopg2
import psycopg2.extras
import bcrypt
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, Response
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "ke-group-secret-changeme-in-production")
app.permanent_session_lifetime = timedelta(hours=8)

_login_attempts = {}
MAX_ATTEMPTS = 5
BLOCK_SECONDS = 15 * 60

def check_rate_limit(ip):
    now = time.time()
    entry = _login_attempts.get(ip, {'count': 0, 'blocked_until': 0})
    if entry['blocked_until'] > now:
        remaining = int((entry['blocked_until'] - now) / 60) + 1
        return False, remaining
    return True, 0

def record_failed(ip):
    now = time.time()
    entry = _login_attempts.get(ip, {'count': 0, 'blocked_until': 0})
    entry['count'] += 1
    if entry['count'] >= MAX_ATTEMPTS:
        entry['blocked_until'] = now + BLOCK_SECONDS
        entry['count'] = 0
    _login_attempts[ip] = entry

def clear_attempts(ip):
    _login_attempts.pop(ip, None)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}

LOGIN_USERNAME = os.environ.get("LOGIN_USERNAME", "admin")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD", "kegroup2024")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id               SERIAL PRIMARY KEY,
                    name             TEXT NOT NULL,
                    category         TEXT,
                    expiry_date      TEXT NOT NULL,
                    note             TEXT,
                    file_path        TEXT,
                    archived         INTEGER DEFAULT 0,
                    priority         TEXT DEFAULT 'normale',
                    reminder_sent_30 INTEGER DEFAULT 0,
                    reminder_sent_7  INTEGER DEFAULT 0,
                    notif_sent_30    INTEGER DEFAULT 0,
                    notif_sent_7     INTEGER DEFAULT 0,
                    notif_sent_0     INTEGER DEFAULT 0,
                    created_at       TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS quick_notes (
                    id         SERIAL PRIMARY KEY,
                    content    TEXT NOT NULL,
                    color      TEXT DEFAULT 'green',
                    pinned     INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
                )
            """)
            for col, definition in [
                ('archived', 'INTEGER DEFAULT 0'),
                ('priority', "TEXT DEFAULT 'normale'"),
                ('notif_sent_30', 'INTEGER DEFAULT 0'),
                ('notif_sent_7', 'INTEGER DEFAULT 0'),
                ('notif_sent_0', 'INTEGER DEFAULT 0'),
            ]:
                try:
                    cur.execute(f"ALTER TABLE documents ADD COLUMN IF NOT EXISTS {col} {definition}")
                except Exception:
                    pass
            conn.commit()

_db_initialized = False

def ensure_db():
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Non autenticato"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_setting(key, default=None):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM settings WHERE key=%s", (key,))
                row = cur.fetchone()
                return row["value"] if row else default
    except Exception as e:
        print(f"[DB] Errore lettura setting {key}: {e}")
        return default

def set_setting(key, value):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO settings (key, value) VALUES (%s, %s) "
                    "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
                    (key, value)
                )
                conn.commit()
    except Exception as e:
        print(f"[DB] Errore scrittura setting {key}: {e}")

def check_expirations():
    print("[Scheduler] Verifica scadenze...")
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE documents SET notif_sent_30 = 0
                    WHERE DATE(expiry_date) > CURRENT_DATE + INTERVAL '30 days' AND notif_sent_30 = 1
                """)
                cur.execute("""
                    UPDATE documents SET notif_sent_7 = 0
                    WHERE DATE(expiry_date) > CURRENT_DATE + INTERVAL '7 days' AND notif_sent_7 = 1
                """)
                conn.commit()
    except Exception as e:
        print(f"[Scheduler] Errore: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(check_expirations, "cron", hour=8, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.before_request
def before_request():
    ensure_db()

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

@app.route("/login")
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()
    allowed, remaining = check_rate_limit(ip)
    if not allowed:
        return jsonify({"ok": False, "error": f"Troppi tentativi. Riprova tra {remaining} minuti."}), 429
    data = request.get_json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "")
    stored_hash = os.environ.get("LOGIN_PASSWORD_HASH", "")
    stored_plain = LOGIN_PASSWORD
    if username != LOGIN_USERNAME:
        bcrypt.checkpw(b"dummy", b"$2b$12$invalidhashfortimingprotectio.AAAAAAAAAAAAAAAAAAAAAA")
        record_failed(ip)
        return jsonify({"ok": False, "error": "Credenziali non valide"}), 401
    ok = False
    if stored_hash:
        try:
            ok = bcrypt.checkpw(password.encode(), stored_hash.encode())
        except Exception:
            ok = False
    else:
        ok = (password == stored_plain)
    if not ok:
        record_failed(ip)
        return jsonify({"ok": False, "error": "Credenziali non valide"}), 401
    clear_attempts(ip)
    session["logged_in"] = True
    session.permanent = True
    return jsonify({"ok": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/settings")
@login_required
def settings_page():
    return render_template("settings.html")

@app.route("/api/documents", methods=["GET"])
@login_required
def get_documents():
    try:
        archived = request.args.get("archived", "0")
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM documents WHERE archived=%s ORDER BY expiry_date ASC", (int(archived),))
                docs = cur.fetchall()
        return jsonify([dict(d) for d in docs])
    except Exception as e:
        return jsonify([])

@app.route("/api/documents", methods=["POST"])
@login_required
def add_document():
    try:
        data = request.get_json()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO documents (name, category, expiry_date, note, priority) VALUES (%s,%s,%s,%s,%s) RETURNING *",
                    (data["name"], data.get("category", "Altro"), data["expiry_date"], data.get("note", ""), data.get("priority", "normale")),
                )
                doc = cur.fetchone()
                conn.commit()
        return jsonify(dict(doc)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents/<int:doc_id>", methods=["PUT"])
@login_required
def update_document(doc_id):
    try:
        data = request.get_json()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET name=%s, category=%s, expiry_date=%s, note=%s, priority=%s, "
                    "notif_sent_30=0, notif_sent_7=0, notif_sent_0=0 WHERE id=%s RETURNING *",
                    (data["name"], data.get("category"), data["expiry_date"], data.get("note", ""), data.get("priority", "normale"), doc_id),
                )
                doc = cur.fetchone()
                conn.commit()
        return jsonify(dict(doc))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_document(doc_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
                conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents/<int:doc_id>/archive", methods=["POST"])
@login_required
def archive_document(doc_id):
    try:
        data = request.get_json()
        archived = 1 if data.get("archived", True) else 0
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE documents SET archived=%s WHERE id=%s RETURNING *", (archived, doc_id))
                doc = cur.fetchone()
                conn.commit()
        return jsonify(dict(doc))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/notifications/pending", methods=["GET"])
@login_required
def get_pending_notifications():
    try:
        notifications = []
        crit_count = 0
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as n FROM documents
                    WHERE archived = 0 AND DATE(expiry_date) <= CURRENT_DATE + INTERVAL '7 days'
                """)
                row = cur.fetchone()
                crit_count = row["n"] if row else 0

                for days_int, col in [(30, "notif_sent_30"), (7, "notif_sent_7"), (0, "notif_sent_0")]:
                    if days_int == 0:
                        cur.execute(f"SELECT * FROM documents WHERE archived=0 AND DATE(expiry_date)=CURRENT_DATE AND {col}=0")
                    else:
                        cur.execute(f"SELECT * FROM documents WHERE archived=0 AND DATE(expiry_date)=CURRENT_DATE + INTERVAL '{days_int} days' AND {col}=0")
                    for doc in cur.fetchall():
                        d = dict(doc)
                        notifications.append({"id": d["id"], "name": d["name"], "category": d["category"], "days": days_int, "expiry_date": d["expiry_date"], "type": f"{days_int}d"})

        return jsonify({"notifications": notifications, "crit_count": crit_count})
    except Exception as e:
        return jsonify({"notifications": [], "crit_count": 0})

@app.route("/api/notifications/mark-sent", methods=["POST"])
@login_required
def mark_notifications_sent():
    try:
        data = request.get_json()
        items = data.get("ids", [])
        if not items:
            return jsonify({"ok": True})
        with get_db() as conn:
            with conn.cursor() as cur:
                for item in items:
                    if isinstance(item, dict):
                        doc_id = item.get("id")
                        notif_type = item.get("type", "30d")
                    else:
                        doc_id = item
                        notif_type = "30d"
                    col = {"30d": "notif_sent_30", "7d": "notif_sent_7", "0d": "notif_sent_0"}.get(notif_type, "notif_sent_30")
                    cur.execute(f"UPDATE documents SET {col}=1 WHERE id=%s", (doc_id,))
                conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/notifications/count", methods=["GET"])
@login_required
def get_notification_count():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as n FROM documents WHERE archived=0 AND DATE(expiry_date) <= CURRENT_DATE + INTERVAL '7 days'")
                row = cur.fetchone()
                count = row["n"] if row else 0
        return jsonify({"count": count})
    except Exception:
        return jsonify({"count": 0})

@app.route("/api/export/csv", methods=["GET"])
@login_required
def export_csv():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM documents WHERE archived=0 ORDER BY expiry_date ASC")
                docs = [dict(d) for d in cur.fetchall()]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Nome", "Categoria", "Data Scadenza", "Giorni Rimanenti", "Stato", "Priorita", "Note", "Creato il"])
        today = datetime.now().date()
        for d in docs:
            try:
                exp = datetime.strptime(d["expiry_date"], "%Y-%m-%d").date()
                days = (exp - today).days
                stato = "Scaduto" if days < 0 else "Critico" if days <= 7 else "In scadenza" if days <= 30 else "Valido"
            except Exception:
                days, stato = "", ""
            writer.writerow([d.get("id",""), d.get("name",""), d.get("category",""), d.get("expiry_date",""), days, stato, d.get("priority","normale"), d.get("note",""), d.get("created_at","")])
        output.seek(0)
        filename = f"ke-scadenziario-{datetime.now().strftime('%Y%m%d')}.csv"
        return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/notes", methods=["GET"])
@login_required
def get_notes():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM quick_notes ORDER BY pinned DESC, id DESC")
                notes = [dict(n) for n in cur.fetchall()]
        return jsonify(notes)
    except Exception:
        return jsonify([])

@app.route("/api/notes", methods=["POST"])
@login_required
def add_note():
    try:
        data = request.get_json()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO quick_notes (content, color, pinned) VALUES (%s,%s,%s) RETURNING *",
                    (data.get("content",""), data.get("color","green"), data.get("pinned",0)))
                note = cur.fetchone()
                conn.commit()
        return jsonify(dict(note)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/notes/<int:note_id>", methods=["DELETE"])
@login_required
def delete_note(note_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM quick_notes WHERE id=%s", (note_id,))
                conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/notes/<int:note_id>/pin", methods=["POST"])
@login_required
def pin_note(note_id):
    try:
        data = request.get_json()
        pinned = 1 if data.get("pinned", True) else 0
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE quick_notes SET pinned=%s WHERE id=%s RETURNING *", (pinned, note_id))
                note = cur.fetchone()
                conn.commit()
        return jsonify(dict(note))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/settings", methods=["GET"])
@login_required
def get_settings():
    return jsonify({
        "user_email": get_setting("user_email", ""),
        "notifications_enabled": get_setting("notifications_enabled", "1"),
        "notify_30d": get_setting("notify_30d", "1"),
        "notify_7d": get_setting("notify_7d", "1"),
        "notify_0d": get_setting("notify_0d", "1"),
    })

@app.route("/api/settings/notifications", methods=["POST"])
@login_required
def update_notification_settings():
    try:
        data = request.get_json()
        for key in ["notifications_enabled", "notify_30d", "notify_7d", "notify_0d"]:
            if key in data:
                set_setting(key, str(data[key]))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/settings/email", methods=["POST"])
@login_required
def update_email():
    try:
        data = request.get_json()
        email = data.get("email", "").strip()
        if not email:
            return jsonify({"error": "Email non valida"}), 400
        set_setting("user_email", email)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload", methods=["POST"])
@login_required
def upload_file():
    return jsonify({"error": "Upload disabilitato - usa il form manuale"}), 400

@app.route("/api/stats", methods=["GET"])
@login_required
def get_stats():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM documents WHERE archived=0")
                docs = [dict(d) for d in cur.fetchall()]
        today = datetime.now().date()
        stats = {"total": len(docs), "ok": 0, "warn": 0, "crit": 0, "expired": 0, "by_category": {}, "expiring_soon": []}
        for d in docs:
            try:
                exp = datetime.strptime(d["expiry_date"], "%Y-%m-%d").date()
                days = (exp - today).days
            except Exception:
                continue
            cat = d.get("category", "Altro") or "Altro"
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
            if days < 0:
                stats["crit"] += 1
                stats["expired"] += 1
            elif days <= 7:
                stats["crit"] += 1
                stats["expiring_soon"].append({"id": d["id"], "name": d["name"], "days": days})
            elif days <= 30:
                stats["warn"] += 1
                stats["expiring_soon"].append({"id": d["id"], "name": d["name"], "days": days})
            else:
                stats["ok"] += 1
        stats["expiring_soon"].sort(key=lambda x: x["days"])
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Non trovato"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Errore interno del server"}), 500

if __name__ == "__main__":
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))
