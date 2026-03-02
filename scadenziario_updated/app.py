import os
import json
import re
import sqlite3
import smtplib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import google.generativeai as genai
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "ke-group-secret-2024-xyz")

# ── Config ────────────────────────────────────────────────────────────────────
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}
DB_PATH = "scadenziario.db"
REMINDER_DAYS = 30

# ── Configurazione Email SMTP (Gmail, Outlook, etc) ──────────────────────────
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")  # smtp.gmail.com per Gmail
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))  # 587 per TLS, 465 per SSL
SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "")  # tua-email@gmail.com
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")  # password app (NON la password di Gmail)

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
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                category    TEXT,
                expiry_date TEXT NOT NULL,
                note        TEXT,
                file_path   TEXT,
                reminder_sent_30 INTEGER DEFAULT 0,
                reminder_sent_7  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
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

# ── Helpers ───────────────────────────────────────────────────────────────────
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

def check_smtp_config():
    """Verifica se SMTP è configurato correttamente."""
    return bool(SMTP_EMAIL and SMTP_PASSWORD)

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
        raise ValueError("GEMINI_API_KEY non impostata. Imposta la variabile d'ambiente e riavvia il server.")

    genai.configure(api_key=api_key)

    ext = filename.rsplit(".", 1)[-1].lower()
    mime_map = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "webp": "image/webp"}
    mime_type = mime_map.get(ext, "application/octet-stream")

    up = genai.upload_file(path=file_path, mime_type=mime_type)

    prompt = (
        "Analizza questo documento e rispondi SOLO con un oggetto JSON valido, senza testo aggiuntivo.\n"
        "Estrai:\n"
        "1. Il nome del documento (es. 'Contratto di affitto', 'Polizza assicurativa auto')\n"
        "2. La data di scadenza nel formato YYYY-MM-DD\n"
        "3. La categoria tra: Contratto, Assicurazione, Licenza, Certificazione, Altro\n"
        "4. Una breve nota (max 60 caratteri)\n\n"
        "Formato risposta:\n"
        "{\"name\": \"...\", \"expiry_date\": \"YYYY-MM-DD\", \"category\": \"...\", \"note\": \"...\"}\n\n"
        "Se non trovi una data di scadenza chiara, usa null per expiry_date."
    )

    model_candidates = [
        "gemini-2.5-flash", "gemini-flash-latest",
        "gemini-2.5-flash-lite", "gemini-2.0-flash",
    ]

    last_err = None
    resp = None
    for mid in model_candidates:
        for name in [mid, f"models/{mid}"]:
            try:
                model = genai.GenerativeModel(name)
                resp = model.generate_content([up, prompt])
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
        print(f"[Email] Gmail non connesso — impossibile inviare reminder per '{doc['name']}'")
        return False

    user_email = get_setting("user_email", "")
    if not user_email:
        print("[Email] Nessuna email destinatario configurata.")
        return False

    try:
        service = build("gmail", "v1", credentials=creds)

        if days_left <= 0:
            subject = f"SCADUTO: {doc['name']}"
            body = (
                f"Il documento \"{doc['name']}\" e' scaduto il {doc['expiry_date']}.\n\n"
                f"Rinnova al piu' presto!\n\n"
                f"Categoria: {doc.get('category') or 'N/D'}\n"
                f"Note: {doc.get('note') or '-'}"
            )
        else:
            subject = f"Scadenza tra {days_left} giorni: {doc['name']}"
            body = (
                f"Promemoria: il documento \"{doc['name']}\" scadra' il {doc['expiry_date']} "
                f"(tra {days_left} giorni).\n\n"
                f"Categoria: {doc.get('category') or 'N/D'}\n"
                f"Note: {doc.get('note') or '-'}\n\n"
                f"Accedi allo Scadenziario KE Group per gestire il rinnovo."
            )

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_EMAIL
        msg["To"] = user_email

        # Invia via SMTP
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Usa TLS per sicurezza
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"[Email] Inviato reminder per '{doc['name']}' a {user_email}")
        return True

    except Exception as e:
        print(f"[Email] Errore invio email: {e}")
        return False

# ── Scheduler giornaliero ─────────────────────────────────────────────────────
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
                print(f"[Scheduler] Errore per doc {doc['id']}: {e}")
        db.commit()

scheduler = BackgroundScheduler()
scheduler.add_job(check_expirations, "cron", hour=8, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ── Routes: pagine ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/settings")
def settings_page():
    return render_template("settings.html")

# ── Routes: API documenti ─────────────────────────────────────────────────────
@app.route("/api/documents", methods=["GET"])
def get_documents():
    with get_db() as db:
        docs = db.execute("SELECT * FROM documents ORDER BY expiry_date ASC").fetchall()
    return jsonify([dict(d) for d in docs])

@app.route("/api/documents", methods=["POST"])
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
def delete_document(doc_id):
    with get_db() as db:
        db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        db.commit()
    return jsonify({"ok": True})

# ── Routes: upload + AI ───────────────────────────────────────────────────────
@app.route("/api/upload", methods=["POST"])
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

# ── Routes: settings ──────────────────────────────────────────────────────────
@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify({
        "smtp_configured": check_smtp_config(),
        "user_email": get_setting("user_email", ""),
        "gemini_key_set": bool(os.environ.get("GEMINI_API_KEY")),
    })

@app.route("/api/settings/email", methods=["POST"])
def update_email():
    data = request.get_json()
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "Email non valida"}), 400
    set_setting("user_email", email)
    return jsonify({"ok": True})

@app.route("/api/test-email", methods=["POST"])
def test_email():
    user_email = get_setting("user_email", "")
    if not user_email:
        return jsonify({"ok": False, "error": "Nessuna email configurata nelle impostazioni"}), 400

    if not check_smtp_config():
        return jsonify({"ok": False, "error": "SMTP non configurato — imposta le variabili d'ambiente"}), 400

    fake_doc = {
        "name": "Documento di prova KE Group",
        "expiry_date": (datetime.now().date() + timedelta(days=30)).isoformat(),
        "category": "Test",
        "note": "Email di test dal sistema scadenziario"
    }
    ok = send_reminder_email(fake_doc, 30)
    if ok:
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "Invio fallito — controlla i log del server"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
