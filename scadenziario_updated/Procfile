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
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
import atexit

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "ke-group-secret-changeme-in-production")
app.permanent_session_lifetime = timedelta(hours=8)

# ── Rate limiting ──────────────────────────────────────────────────────────────
_login_attempts = {}  # ip -> {'count': int, 'blocked_until': float}
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

# ── Database PostgreSQL ───────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_db():
    """Restituisce una connessione PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    """Crea le tabelle se non esistono."""
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
        init_db()
        _db_initialized = True

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

# ── SendGrid Email Configuration ──────────────────────────────────────────────
def send_email_smtp(recipient_email: str, subject: str, body_html: str) -> bool:
    """Invia email via SendGrid API (compatibile con Render.com)."""
    try:
        api_key = os.environ.get("SENDGRID_API_KEY", "").strip()
        from_email = os.environ.get("SENDGRID_FROM_EMAIL", "").strip()

        if not api_key:
            print("[Email] SENDGRID_API_KEY non configurata")
            return False
        if not from_email:
            print("[Email] SENDGRID_FROM_EMAIL non configurata")
            return False

        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        message = Mail(
            from_email=Email(from_email),
            to_emails=To(recipient_email),
            subject=subject,
            html_content=Content("text/html", body_html)
        )
        response = sg.send(message)

        if response.status_code in (200, 202):
            print(f"[Email] Email inviata a {recipient_email} (status {response.status_code})")
            return True
        else:
            print(f"[Email] Errore SendGrid status {response.status_code}: {response.body}")
            return False
    except Exception as e:
        print(f"[Email] Errore invio SendGrid: {e}")
        return False

# ── Email reminder ────────────────────────────────────────────────────────────
def send_reminder_email(doc, days_left):
    """Invia email di reminder per una scadenza."""
    user_email = get_setting("user_email", "")
    if not user_email:
        print(f"[Reminder] Email non configurata per doc {doc['id']}")
        return False
    
    doc_name = doc["name"]
    category = doc.get("category", "Senza categoria")
    expiry = doc["expiry_date"]
    note = doc.get("note", "")
    
    subject = f"⚠️ Scadenza in {days_left} giorni: {doc_name}"
    
    body_html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Reminder Scadenza Documento</h2>
            <p><strong>Documento:</strong> {doc_name}</p>
            <p><strong>Categoria:</strong> {category}</p>
            <p><strong>Data scadenza:</strong> {expiry}</p>
            <p><strong>Giorni rimanenti:</strong> <span style="color: #d32f2f; font-weight: bold;">{days_left}</span></p>
            {f'<p><strong>Note:</strong> {note}</p>' if note else ''}
            <hr>
            <p style="font-size: 12px; color: #666;">
                Questo è un reminder automatico. Accedi a <strong>KE Scadenziario</strong> per gestire i tuoi documenti.
            </p>
        </body>
    </html>
    """
    
    return send_email_smtp(user_email, subject, body_html)

def check_expirations():
    """Controlla i documenti in scadenza e invia reminder."""
    print("[Scheduler] Verifica scadenze...")
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Controlla documenti a 30 giorni
                cur.execute("""
                    SELECT * FROM documents 
                    WHERE DATE(expiry_date) = CURRENT_DATE + INTERVAL '30 days'
                    AND reminder_sent_30 = 0
                """)
                for doc in cur.fetchall():
                    doc_dict = dict(doc)
                    if send_reminder_email(doc_dict, 30):
                        cur.execute(
                            "UPDATE documents SET reminder_sent_30=1 WHERE id=%s",
                            (doc_dict["id"],)
                        )
                
                # Controlla documenti a 7 giorni
                cur.execute("""
                    SELECT * FROM documents 
                    WHERE DATE(expiry_date) = CURRENT_DATE + INTERVAL '7 days'
                    AND reminder_sent_7 = 0
                """)
                for doc in cur.fetchall():
                    doc_dict = dict(doc)
                    if send_reminder_email(doc_dict, 7):
                        cur.execute(
                            "UPDATE documents SET reminder_sent_7=1 WHERE id=%s",
                            (doc_dict["id"],)
                        )
                
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
    print(f"[Login] Accesso: {username} da {ip}")
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
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM documents ORDER BY expiry_date ASC")
                docs = cur.fetchall()
        return jsonify([dict(d) for d in docs])
    except Exception as e:
        print(f"[API] Errore get_documents: {e}")
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
        print(f"[API] Errore add_document: {e}")
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
        print(f"[API] Errore update_document: {e}")
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
        print(f"[API] Errore delete_document: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload", methods=["POST"])
@login_required
def upload_file():
    return jsonify({"error": "Upload disabilitato - usa il form manuale"}), 400

@app.route("/api/settings", methods=["GET"])
@login_required
def get_settings():
    return jsonify({
        "user_email": get_setting("user_email", ""),
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
        print(f"[API] Errore update_email: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/test-email", methods=["POST"])
@login_required
def test_email():
    try:
        user_email = get_setting("user_email", "")
        if not user_email:
            return jsonify({"ok": False, "error": "Nessuna email configurata"}), 400
        
        api_key = os.environ.get("SENDGRID_API_KEY", "").strip()
        if not api_key:
            return jsonify({"ok": False, "error": "SENDGRID_API_KEY non configurata nelle variabili d'ambiente"}), 400
        
        test_doc = {
            "id": 0,
            "name": "Documento di prova KE Group",
            "expiry_date": (datetime.now().date() + timedelta(days=30)).isoformat(),
            "category": "Test",
            "note": "Email di test"
        }
        
        ok = send_reminder_email(test_doc, 30)
        if ok:
            return jsonify({"ok": True}), 200
        else:
            return jsonify({"ok": False, "error": "Errore nell'invio dell'email"}), 500
    except Exception as e:
        print(f"[API] Errore test_email: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Non trovato"}), 404

@app.errorhandler(500)
def server_error(e):
    print(f"[ERROR] 500: {e}")
    return jsonify({"error": "Errore interno del server"}), 500

if __name__ == "__main__":
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))
