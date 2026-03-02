# KE Group — Registro Scadenze

Sistema di gestione scadenze documenti con analisi AI, notifiche email automatiche e dashboard interattiva.

---

## Avvio locale (Windows)

```bash
cd scadenziario_updated
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

set GEMINI_API_KEY=AIzaSy-tuachiave
set LOGIN_USERNAME=admin
set LOGIN_PASSWORD=latuapassword
set FLASK_SECRET=unastringsegretarandom

py app.py
```

Apri: **http://localhost:5000**

---

## Credenziali predefinite

- **Username:** `admin`  
- **Password:** `kegroup2024`

⚠️ **Cambia sempre prima di pubblicare online** impostando `LOGIN_USERNAME` e `LOGIN_PASSWORD`.

---

## Deploy su Render

### 1. Pubblica su GitHub
```bash
git init
git add .
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/tuoutente/ke-scadenziario.git
git push -u origin main
```

### 2. Crea il servizio su Render
1. Vai su [render.com](https://render.com)
2. **New → Web Service** → collega il repository GitHub
3. Render usa automaticamente il `render.yaml`

### 3. Variabili d'ambiente su Render
Pannello servizio → **Environment**:

| Variabile | Valore |
|-----------|--------|
| `GEMINI_API_KEY` | Chiave da [aistudio.google.com](https://aistudio.google.com) |
| `LOGIN_USERNAME` | Il tuo username |
| `LOGIN_PASSWORD` | Una password sicura |
| `FLASK_SECRET` | Stringa casuale (32+ caratteri) |

---

## Configurazione Gmail

1. [Google Cloud Console](https://console.cloud.google.com) → nuovo progetto
2. Abilita **Gmail API**
3. **Credentials → OAuth 2.0 Client ID** (tipo: Web application)
4. Aggiungi redirect URI:
   - Locale: `http://localhost:5000/auth/google/callback`
   - Render: `https://tuoservizio.onrender.com/auth/google/callback`
5. Scarica il JSON → rinominalo `client_secrets.json` → mettilo accanto a `app.py`
6. Nell'app: Impostazioni → Accedi con Google

---

## Struttura

```
├── app.py              # Backend Flask
├── requirements.txt    # Dipendenze
├── Procfile            # Avvio Render
├── render.yaml         # Config Render
├── .gitignore
├── README.md
└── templates/
    ├── login.html
    ├── index.html
    └── settings.html
```
