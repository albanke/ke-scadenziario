import os
import json
import re
import base64
import hashlib
import secrets
import psycopg2
import psycopg2.extras
import bcrypt
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
import atexit

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET", "ke-group-secret-changeme-in-production")
app.permanent_session_lifetime = timedelta(hours=8)

# ── Rate limiting ──────────────────────────────────────────────────────────────
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

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

LOGIN_USERNAME = os.environ.get("LOGIN_USERNAME", "admin")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD", "kegroup2024")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Database PostgreSQL ───────────────────────────────────────────────────────
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
                    reminder_sent_30 INTEGER DEFAULT 0,
                    reminder_sent_7  INTEGER DEFAULT 0,
                    created_at       TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

_db_initialized = False

def ensure_db():
    global _db_initialized
    if not _db_initialized:
        try:
            init_db()
            _db_initialized = True
        except Exception as e:
            print(f"[DB] Errore init_db: {e}")

# ── Auth helpers ──────────────────────────────────────────────────────────────
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

# ── Settings helpers ──────────────────────────────────────────────────────────
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

# ── Gemini AI ─────────────────────────────────────────────────────────────────
def analyze_document_with_gemini(file_path, filename):
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return {"error": "GEMINI_API_KEY non configurata"}

        genai.configure(api_key=api_key)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mime_map = {
            "pdf": "application/pdf",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")

        with open(file_path, "rb") as f:
            file_data = f.read()

        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        prompt = """Analizza questo documento e rispondi SOLO con un JSON valido (senza markdown, senza backtick), con questa struttura:
{"name":"nome del documento","expiry_date":"YYYY-MM-DD oppure null","category":"una tra: Identità, Veicoli, Assicurazioni, Immobili, Lavoro, Sanitario, Finanziario, Altro","note":"breve nota max 100 caratteri"}"""
        response = model.generate_content([
            {"mime_type": mime_type, "data": file_data},
            prompt
        ])

        text = response.text.strip()
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text).strip()
        return json.loads(text)

    except Exception as e:
        print(f"[Gemini] Errore: {e}")
        return {"error": str(e)}

# ── Email ─────────────────────────────────────────────────────────────────────
def send_email_smtp(recipient_email, subject, body_html):
    try:
        api_key = os.environ.get("SENDGRID_API_KEY", "").strip()
        from_email = os.environ.get("SENDGRID_FROM_EMAIL", "").strip()
        if not api_key or not from_email:
            return False
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        message = Mail(
            from_email=Email(from_email),
            to_emails=To(recipient_email),
            subject=subject,
            html_content=Content("text/html", body_html)
        )
        response = sg.send(message)
        return response.status_code in (200, 202)
    except Exception as e:
        print(f"[Email] Errore: {e}")
        return False

def send_reminder_email(doc, days_left):
    user_email = get_setting("user_email", "")
    if not user_email:
        return False
    doc_name = doc["name"]
    category = doc.get("category", "Senza categoria")
    expiry = doc["expiry_date"]
    note = doc.get("note", "")
    subject = f"⚠️ Scadenza in {days_left} giorni: {doc_name}"
    body_html = f"""<html><body style="font-family:Arial,sans-serif;color:#333">
<h2 style="color:#4ECB74">KE Scadenziario — Reminder</h2>
<p><b>Documento:</b> {doc_name}</p>
<p><b>Categoria:</b> {category}</p>
<p><b>Scadenza:</b> {expiry}</p>
<p><b>Giorni rimanenti:</b> <span style="color:#d32f2f;font-weight:bold">{days_left}</span></p>
{f'<p><b>Note:</b> {note}</p>' if note else ''}
<hr><p style="font-size:12px;color:#666">Reminder automatico da KE Scadenziario.</p>
</body></html>"""
    return send_email_smtp(user_email, subject, body_html)

def check_expirations():
    print("[Scheduler] Verifica scadenze...")
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM documents
                    WHERE DATE(expiry_date) = CURRENT_DATE + INTERVAL '30 days'
                    AND reminder_sent_30 = 0
                """)
                for doc in cur.fetchall():
                    d = dict(doc)
                    if send_reminder_email(d, 30):
                        cur.execute("UPDATE documents SET reminder_sent_30=1 WHERE id=%s", (d["id"],))
                cur.execute("""
                    SELECT * FROM documents
                    WHERE DATE(expiry_date) = CURRENT_DATE + INTERVAL '7 days'
                    AND reminder_sent_7 = 0
                """)
                for doc in cur.fetchall():
                    d = dict(doc)
                    if send_reminder_email(d, 7):
                        cur.execute("UPDATE documents SET reminder_sent_7=1 WHERE id=%s", (d["id"],))
                conn.commit()
    except Exception as e:
        print(f"[Scheduler] Errore: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(check_expirations, "cron", hour=8, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.before_request
def before_request():
    ensure_db()

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
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
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "")
    if username != LOGIN_USERNAME:
        bcrypt.checkpw(b"dummy", b"$2b$12$invalidhashfortimingprotectio.AAAAAAAAAAAAAAAAAAAAAA")
        record_failed(ip)
        return jsonify({"ok": False, "error": "Credenziali non valide"}), 401
    stored_hash = os.environ.get("LOGIN_PASSWORD_HASH", "")
    ok = False
    if stored_hash:
        try:
            ok = bcrypt.checkpw(password.encode(), stored_hash.encode())
        except Exception:
            ok = False
    else:
        ok = (password == LOGIN_PASSWORD)
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

# ── Documenti ─────────────────────────────────────────────────────────────────

@app.route("/api/documents", methods=["GET"])
@login_required
def get_documents():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM documents ORDER BY expiry_date ASC")
                docs = cur.fetchall()
        return jsonify([dict(d) for d in docs])
    except Exception as e:
        print(f"[API] get_documents error: {e}")
        return jsonify([])

@app.route("/api/documents", methods=["POST"])
@login_required
def add_document():
    try:
        data = request.get_json()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO documents (name, category, expiry_date, note) VALUES (%s,%s,%s,%s) RETURNING *",
                    (data["name"], data.get("category", "Altro"), data["expiry_date"], data.get("note", "")),
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
                    "UPDATE documents SET name=%s, category=%s, expiry_date=%s, note=%s WHERE id=%s RETURNING *",
                    (data["name"], data.get("category"), data["expiry_date"], data.get("note", ""), doc_id),
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
                cur.execute("SELECT file_path FROM documents WHERE id=%s", (doc_id,))
                row = cur.fetchone()
                if row and row["file_path"]:
                    fp = os.path.join(UPLOAD_FOLDER, os.path.basename(row["file_path"]))
                    if os.path.exists(fp):
                        try: os.remove(fp)
                        except: pass
                cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
                conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Upload + Gemini ───────────────────────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
@login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Nessun file inviato"}), 400
    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "File non valido"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": f"Tipo non supportato. Usa: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower()
    safe_name = secure_filename(file.filename)
    unique_name = f"{int(time.time())}_{secrets.token_hex(4)}_{safe_name}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(file_path)

    result = {"ok": True, "file_path": unique_name, "original_name": file.filename}

    # Analisi Gemini se richiesta
    analyze = request.form.get("analyze", "false").lower() == "true"
    if analyze:
        gemini_result = analyze_document_with_gemini(file_path, file.filename)
        if "error" not in gemini_result:
            result["gemini"] = gemini_result
        else:
            result["gemini_error"] = gemini_result["error"]

    # Associa a documento esistente
    doc_id = request.form.get("doc_id")
    if doc_id:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT file_path FROM documents WHERE id=%s", (doc_id,))
                    old = cur.fetchone()
                    if old and old["file_path"]:
                        old_fp = os.path.join(UPLOAD_FOLDER, os.path.basename(old["file_path"]))
                        if os.path.exists(old_fp):
                            try: os.remove(old_fp)
                            except: pass
                    cur.execute("UPDATE documents SET file_path=%s WHERE id=%s", (unique_name, doc_id))
                    conn.commit()
        except Exception as e:
            print(f"[Upload] Errore associazione doc {doc_id}: {e}")

    return jsonify(result), 200

@app.route("/uploads/<path:filename>")
@login_required
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ── Settings ──────────────────────────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
@login_required
def get_settings():
    return jsonify({
        "user_email": get_setting("user_email", ""),
        "gemini_configured": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
    })

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

@app.route("/api/test-email", methods=["POST"])
@login_required
def test_email():
    try:
        user_email = get_setting("user_email", "")
        if not user_email:
            return jsonify({"ok": False, "error": "Nessuna email configurata"}), 400
        if not os.environ.get("SENDGRID_API_KEY", "").strip():
            return jsonify({"ok": False, "error": "SENDGRID_API_KEY non configurata"}), 400
        test_doc = {
            "id": 0, "name": "Documento di prova KE Group",
            "expiry_date": (datetime.now().date() + timedelta(days=30)).isoformat(),
            "category": "Test", "note": "Email di test"
        }
        ok = send_reminder_email(test_doc, 30)
        return jsonify({"ok": ok}) if ok else jsonify({"ok": False, "error": "Errore invio"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(413)
@app.route("/api/check-notifications", methods=["GET"])
@login_required
def check_notifications():
    """Ritorna documenti in scadenza a 30 e 7 giorni — usato da Electron per notifiche native."""
    ensure_db()
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, category, expiry_date, note
                    FROM documents
                    WHERE DATE(expiry_date) <= CURRENT_DATE + INTERVAL '30 days'
                    AND DATE(expiry_date) >= CURRENT_DATE
                    ORDER BY expiry_date ASC
                """)
                docs = [dict(r) for r in cur.fetchall()]

        results = []
        today = datetime.now().date()
        for d in docs:
            try:
                exp = datetime.strptime(d["expiry_date"][:10], "%Y-%m-%d").date()
                days_left = (exp - today).days
                results.append({
                    "id": d["id"],
                    "name": d["name"],
                    "category": d.get("category", ""),
                    "expiry_date": d["expiry_date"][:10],
                    "days_left": days_left,
                })
            except Exception:
                pass
        return jsonify({"ok": True, "documents": results})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def too_large(e):
    return jsonify({"error": "File troppo grande (max 10MB)"}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Non trovato"}), 404

@app.errorhandler(500)
def server_error(e):
    print(f"[ERROR] 500: {e}")
    return jsonify({"error": "Errore interno del server"}), 500

if __name__ == "__main__":
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))
