import os
import json
import re
import base64
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from werkzeug.utils import secure_filename
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# ── IMPORTANTE: disabilita il requisito HTTPS per OAuth su localhost ──────────
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "ke-group-secret-changeme-in-production")

# ── Config ────────────────────────────────────────────────────────────────────
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}
DB_PATH = "scadenziario.db"
REMINDER_DAYS = 30
GOOGLE_CLIENT_SECRETS = "client_secrets.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# ── Credenziali di accesso (da variabili d'ambiente in produzione) ─────────────
# Imposta su Render: LOGIN_USERNAME e LOGIN_PASSWORD
# Di default: admin / kegroup2024
LOGIN_USERNAME = os.environ.get("LOGIN_USERNAME", "admin")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD", "kegroup2024")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT NOT NULL,
                category         TEXT,
                expiry_date      TEXT NOT NULL,
                note             TEXT,
                file_path        TEXT,
                reminder_sent_30 INTEGER DEFAULT 0,
                reminder_sent_7  INTEGER DEFAULT 0,
                created_at       TEXT DEFAULT (datetime('now'))
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        db.commit()

init_db()

# ── Auth helpers ──────────────────────────────────────────────────────────────
def login_required(f):
    """Decoratore: protegge le route, reindirizza al login se non autenticato."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            # Per le API restituisce 401, per le pagine reindirizza
            if request.path.startswith("/api/"):
                return jsonify({"error": "Non autenticato"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

# ── Settings helpers ──────────────────────────────────────────────────────────
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_setting(key, default=None):
    with get_db() as db:
        row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

def set_setting(key, value):
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        db.commit()

def get_google_creds():
    """Carica le credenziali Google e rinnova automaticamente il token se scaduto."""
    token_json = get_setting("google_token")
    if not token_json:
        return None
    try:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    except Exception as e:
        print(f"[Auth] Errore caricamento credenziali: {e}")
        return None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            set_setting("google_token", creds.to_json())
            print("[Auth] Token Gmail rinnovato automaticamente.")
            return creds
        except Exception as e:
            print(f"[Auth] Impossibile rinnovare il token: {e}")
            set_setting("google_token", None)
            return None

    return None

# ── Gemini AI ─────────────────────────────────────────────────────────────────
def _extract_json_object(text: str) -> dict:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = re.sub(r"^json\s*", "", t, flags=re.I).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        raise ValueError("Risposta AI non contiene JSON valido")
    return json.loads(m.group(0))

def extract_expiry_with_gemini(file_path: str, filename: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY non impostata.")

    genai.configure(api_key=api_key)
    ext = filename.rsplit(".", 1)[-1].lower()
    mime_map = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "webp": "image/webp"}
    mime_type = mime_map.get(ext, "application/octet-stream")
    up = genai.upload_file(path=file_path, mime_type=mime_type)

    prompt = (
        "Analizza questo documento e rispondi SOLO con un oggetto JSON valido.\n"
        "Estrai: nome, data scadenza (YYYY-MM-DD), categoria (Contratto/Assicurazione/"
        "Licenza/Certificazione/Altro), nota breve (max 60 caratteri).\n"
        "Formato: {\"name\":\"...\",\"expiry_date\":\"YYYY-MM-DD\",\"category\":\"...\",\"note\":\"...\"}\n"
        "Se non trovi la data di scadenza usa null."
    )

    model_candidates = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
    last_err, resp = None, None
    for mid in model_candidates:
        for name in [mid, f"models/{mid}"]:
            try:
                resp = genai.GenerativeModel(name).generate_content([up, prompt])
                break
            except Exception as e:
                last_err = e
        if resp:
            break

    if resp is None:
        raise RuntimeError(f"Nessun modello Gemini disponibile. Errore: {last_err}")

    data = _extract_json_object(getattr(resp, "text", "") or "")
    data.setdefault("name", filename)
    data.setdefault("expiry_date", None)
    data.setdefault("category", "Altro")
    data.setdefault("note", "")
    return data

# ── Email reminder ────────────────────────────────────────────────────────────
def send_reminder_email(doc, days_left):
    creds = get_google_creds()
    if not creds:
        print(f"[Email] Gmail non connesso — salto reminder per '{doc['name']}'")
        return False
    user_email = get_setting("user_email", "")
    if not user_email:
        print("[Email] Nessuna email destinatario configurata.")
        return False
    try:
        service = build("gmail", "v1", credentials=creds)
        if days_left <= 0:
            subject = f"SCADUTO: {doc['name']}"
            body = (f"Il documento \"{doc['name']}\" e' scaduto il {doc['expiry_date']}.\n\n"
                    f"Rinnova al piu' presto!\nCategoria: {doc.get('category') or 'N/D'}\n"
                    f"Note: {doc.get('note') or '-'}")
        else:
            subject = f"Scadenza tra {days_left} giorni: {doc['name']}"
            body = (f"Promemoria: \"{doc['name']}\" scadra' il {doc['expiry_date']} (tra {days_left} giorni).\n\n"
                    f"Categoria: {doc.get('category') or 'N/D'}\nNote: {doc.get('note') or '-'}\n\n"
                    f"Accedi allo Scadenziario KE Group per gestire il rinnovo.")
        msg = MIMEText(body, "plain", "utf-8")
        msg["to"] = user_email
        msg["from"] = user_email
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        print(f"[Email] Inviato reminder per '{doc['name']}' a {user_email}")
        return True
    except Exception as e:
        print(f"[Email] Errore invio: {e}")
        return False

# ── Scheduler ─────────────────────────────────────────────────────────────────
def check_expirations():
    print(f"[Scheduler] Controllo scadenze -- {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    today = datetime.now().date()
    with get_db() as db:
        docs = db.execute("SELECT * FROM documents").fetchall()
        for doc in docs:
            try:
                exp = datetime.strptime(doc["expiry_date"], "%Y-%m-%d").date()
                days_left = (exp - today).days
                if days_left == REMINDER_DAYS and not doc["reminder_sent_30"]:
                    if send_reminder_email(dict(doc), days_left):
                        db.execute("UPDATE documents SET reminder_sent_30=1 WHERE id=?", (doc["id"],))
                if days_left == 7 and not doc["reminder_sent_7"]:
                    if send_reminder_email(dict(doc), days_left):
                        db.execute("UPDATE documents SET reminder_sent_7=1 WHERE id=?", (doc["id"],))
            except Exception as e:
                print(f"[Scheduler] Errore doc {doc['id']}: {e}")
        db.commit()

scheduler = BackgroundScheduler()
scheduler.add_job(check_expirations, "cron", hour=8, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── Login / Logout ────────────────────────────────────────────────────────────
@app.route("/login")
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "")

    if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
        session["logged_in"] = True
        session.permanent = True
        print(f"[Login] Accesso effettuato: {username}")
        return jsonify({"ok": True})
    else:
        print(f"[Login] Tentativo fallito per: {username}")
        return jsonify({"ok": False, "error": "Nome utente o password non corretti"}), 401

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# ── Pagine (protette) ─────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/settings")
@login_required
def settings_page():
    return render_template("settings.html")

# ── API documenti (protette) ──────────────────────────────────────────────────
@app.route("/api/documents", methods=["GET"])
@login_required
def get_documents():
    with get_db() as db:
        docs = db.execute("SELECT * FROM documents ORDER BY expiry_date ASC").fetchall()
    return jsonify([dict(d) for d in docs])

@app.route("/api/documents", methods=["POST"])
@login_required
def add_document():
    data = request.get_json()
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO documents (name, category, expiry_date, note) VALUES (?,?,?,?)",
            (data["name"], data.get("category", "Altro"), data["expiry_date"], data.get("note", "")),
        )
        db.commit()
        doc = db.execute("SELECT * FROM documents WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(doc)), 201

@app.route("/api/documents/<int:doc_id>", methods=["PUT"])
@login_required
def update_document(doc_id):
    data = request.get_json()
    with get_db() as db:
        db.execute(
            "UPDATE documents SET name=?, category=?, expiry_date=?, note=? WHERE id=?",
            (data["name"], data.get("category"), data["expiry_date"], data.get("note", ""), doc_id),
        )
        db.commit()
        doc = db.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    return jsonify(dict(doc))

@app.route("/api/documents/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_document(doc_id):
    with get_db() as db:
        db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        db.commit()
    return jsonify({"ok": True})

# ── Upload + AI (protetto) ────────────────────────────────────────────────────
@app.route("/api/upload", methods=["POST"])
@login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Nessun file"}), 400
    f = request.files["file"]
    if not f or not allowed_file(f.filename):
        return jsonify({"error": "Formato non supportato (usa PDF, JPG, PNG, WEBP)"}), 400
    filename = secure_filename(f.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    f.save(path)
    try:
        result = extract_expiry_with_gemini(path, filename)
        result["file_path"] = path
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Gmail OAuth ───────────────────────────────────────────────────────────────
@app.route("/auth/google")
@login_required
def google_auth():
    if not os.path.exists(GOOGLE_CLIENT_SECRETS):
        return (
            "<h2>File mancante: client_secrets.json</h2>"
            "<p>Scaricalo da Google Cloud Console → Credentials → OAuth 2.0 → Download JSON</p>"
            "<p>Rinominalo <code>client_secrets.json</code> e mettilo accanto a <code>app.py</code>.</p>"
        ), 400
    flow = Flow.from_client_secrets_file(GOOGLE_CLIENT_SECRETS, scopes=SCOPES)
    flow.redirect_uri = url_for("google_callback", _external=True)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    session["oauth_state"] = state
    return redirect(auth_url)

@app.route("/auth/google/callback")
def google_callback():
    # Questo callback non richiede login (Google lo chiama direttamente)
    try:
        flow = Flow.from_client_secrets_file(
            GOOGLE_CLIENT_SECRETS, scopes=SCOPES, state=session.get("oauth_state")
        )
        flow.redirect_uri = url_for("google_callback", _external=True)
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        set_setting("google_token", creds.to_json())
        service = build("oauth2", "v2", credentials=creds)
        info = service.userinfo().get().execute()
        set_setting("user_email", info.get("email", ""))
        print(f"[Auth] Gmail connesso: {info.get('email')}")
        return redirect(url_for("settings_page") + "?gmail=ok")
    except Exception as e:
        print(f"[Auth] Errore callback OAuth: {e}")
        return redirect(url_for("settings_page") + "?gmail=error")

# ── Settings API (protette) ───────────────────────────────────────────────────
@app.route("/api/settings", methods=["GET"])
@login_required
def get_settings():
    return jsonify({
        "gmail_connected": get_google_creds() is not None,
        "user_email": get_setting("user_email", ""),
        "gemini_key_set": bool(os.environ.get("GEMINI_API_KEY")),
    })

@app.route("/api/settings/email", methods=["POST"])
@login_required
def update_email():
    data = request.get_json()
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "Email non valida"}), 400
    set_setting("user_email", email)
    return jsonify({"ok": True})

@app.route("/api/gmail/disconnect", methods=["POST"])
@login_required
def gmail_disconnect():
    set_setting("google_token", None)
    return jsonify({"ok": True})

@app.route("/api/test-email", methods=["POST"])
@login_required
def test_email():
    user_email = get_setting("user_email", "")
    if not user_email:
        return jsonify({"ok": False, "error": "Nessuna email configurata"}), 400
    if not get_google_creds():
        return jsonify({"ok": False, "error": "Gmail non connesso"}), 400
    fake_doc = {
        "name": "Documento di prova KE Group",
        "expiry_date": (datetime.now().date() + timedelta(days=30)).isoformat(),
        "category": "Test",
        "note": "Email di test"
    }
    ok = send_reminder_email(fake_doc, 30)
    return jsonify({"ok": ok}) if ok else jsonify({"ok": False, "error": "Invio fallito — controlla i log"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
