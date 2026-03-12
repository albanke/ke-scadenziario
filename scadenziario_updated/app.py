import os
import json
import re
import base64
import secrets
import psycopg2
import psycopg2.extras
import bcrypt
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename

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
                    folder           TEXT DEFAULT 'Generale',
                    expiry_date      TEXT NOT NULL,
                    note             TEXT,
                    file_path        TEXT,
                    reminder_sent_30 INTEGER DEFAULT 0,
                    reminder_sent_7  INTEGER DEFAULT 0,
                    created_at       TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
                )
            """)
            # Aggiungi colonna folder se non esiste (per DB esistenti)
            try:
                cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS folder TEXT DEFAULT 'Generale'")
            except Exception:
                pass
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
        ensure_db()
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    ensure_db()
    return render_template("index.html")

@app.route("/login")
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/api/login", methods=["POST"])
def api_login():
    ip = request.remote_addr or "unknown"
    ok, remaining = check_rate_limit(ip)
    if not ok:
        return jsonify({"error": f"Troppi tentativi. Riprova tra {remaining} minuti."}), 429
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
        clear_attempts(ip)
        session.permanent = True
        session["logged_in"] = True
        session["username"] = username
        return jsonify({"ok": True})
    record_failed(ip)
    return jsonify({"error": "Credenziali non valide"}), 401

# ── Documents API ─────────────────────────────────────────────────────────────

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
        folder = data.get("folder", "Generale") or "Generale"
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO documents (name, category, folder, expiry_date, note) VALUES (%s,%s,%s,%s,%s) RETURNING *",
                    (data["name"], data.get("category", "Altro"), folder, data["expiry_date"], data.get("note", "")),
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
        folder = data.get("folder", "Generale") or "Generale"
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET name=%s, category=%s, folder=%s, expiry_date=%s, note=%s WHERE id=%s RETURNING *",
                    (data["name"], data.get("category"), folder, data["expiry_date"], data.get("note", ""), doc_id),
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

# ── Folders API ───────────────────────────────────────────────────────────────

@app.route("/api/folders", methods=["GET"])
@login_required
def get_folders():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT folder FROM documents WHERE folder IS NOT NULL ORDER BY folder")
                rows = cur.fetchall()
        folders = [r["folder"] for r in rows if r["folder"]]
        if "Generale" not in folders:
            folders = ["Generale"] + folders
        return jsonify(folders)
    except Exception as e:
        return jsonify(["Generale"])

# ── Upload ────────────────────────────────────────────────────────────────────

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

    safe_name = secure_filename(file.filename)
    unique_name = f"{int(time.time())}_{secrets.token_hex(4)}_{safe_name}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(file_path)

    result = {"ok": True, "file_path": unique_name, "original_name": file.filename}

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

# ── Notifications ─────────────────────────────────────────────────────────────

@app.route("/api/check-notifications", methods=["GET"])
@login_required
def check_notifications():
    ensure_db()
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, category, folder, expiry_date, note
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
                    "folder": d.get("folder", "Generale"),
                    "expiry_date": d["expiry_date"][:10],
                    "days_left": days_left,
                })
            except Exception:
                pass
        return jsonify({"ok": True, "documents": results})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File troppo grande (max 10MB)"}), 413

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Non trovato"}), 404
    return redirect(url_for("index"))

@app.errorhandler(500)
def server_error(e):
    print(f"[ERROR] 500: {e}")
    return jsonify({"error": "Errore interno del server"}), 500

if __name__ == "__main__":
    ensure_db()
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))
