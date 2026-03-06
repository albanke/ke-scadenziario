<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KE Group — Impostazioni</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg:         #141C14;
  --surface-1:  #1A231A;
  --surface-2:  #202B20;
  --surface-3:  #293329;
  --border:     rgba(255,255,255,0.13);
  --border-hi:  rgba(255,255,255,0.24);
  --green:      #4ECB74;
  --green-dim:  #1E4D2E;
  --green-glow: rgba(78,203,116,0.18);
  --amber:      #F5A623;
  --red:        #F05A52;
  --red-dim:    #4A1A18;
  --text-1:     #EEF5EE;
  --text-2:     #A8BEA8;
  --text-3:     #6A826A;
}

*, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
body {
  background: var(--bg);
  color: var(--text-1);
  font-family: 'DM Sans', sans-serif;
  font-size: 14px;
  min-height: 100vh;
  line-height: 1.5;
}
body::before {
  content:'';
  position:fixed; inset:0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
  pointer-events:none; z-index:0;
}

.layout { display:flex; min-height:100vh; position:relative; z-index:1; }

/* ── Sidebar ── */
.sidebar {
  width:72px; flex-shrink:0;
  background:var(--surface-1);
  border-right:1px solid var(--border);
  display:flex; flex-direction:column; align-items:center;
  padding:24px 0; position:sticky; top:0; height:100vh;
  gap:8px; z-index:100;
  transition:width 0.3s cubic-bezier(0.4,0,0.2,1);
  overflow:hidden;
}
.sidebar:hover { width:220px; }

.sidebar-logo {
  width:38px; height:38px;
  background:var(--green); border-radius:10px;
  display:flex; align-items:center; justify-content:center;
  flex-shrink:0; margin-bottom:16px;
  box-shadow:0 0 20px var(--green-glow);
}
.sidebar-logo svg { width:22px; height:22px; }

.nav-link {
  width:100%; display:flex; align-items:center; gap:14px;
  padding:10px 17px; text-decoration:none; color:var(--text-3);
  transition:all 0.2s; white-space:nowrap; position:relative;
}
.nav-link:hover { color:var(--text-1); background:var(--surface-3); }
.nav-link.active { color:var(--green); background:rgba(61,186,102,0.08); }
.nav-link.active::before {
  content:''; position:absolute; left:0; top:0; bottom:0;
  width:3px; background:var(--green); border-radius:0 2px 2px 0;
}
.nav-icon { width:18px; height:18px; flex-shrink:0; }
.nav-label { font-size:13px; font-weight:500; opacity:0; transition:opacity 0.2s; }
.sidebar:hover .nav-label { opacity:1; }
.sidebar-spacer { flex:1; }
.status-pill {
  margin:0 10px; padding:8px 14px;
  background:var(--surface-3); border:1px solid var(--border);
  border-radius:8px; display:flex; align-items:center; gap:8px;
  white-space:nowrap; overflow:hidden; min-width:0;
  width:calc(100% - 20px);
}
.status-dot { width:6px; height:6px; border-radius:50%; background:var(--text-3); flex-shrink:0; }
.status-dot.on { background:var(--green); box-shadow:0 0 8px var(--green); }
.status-text { font-size:11px; color:var(--text-2); overflow:hidden; text-overflow:ellipsis; opacity:0; transition:opacity 0.2s; white-space:nowrap; }
.sidebar:hover .status-text { opacity:1; }

/* ── Main ── */
.main { flex:1; min-width:0; display:flex; flex-direction:column; }

.topbar {
  display:flex; align-items:center; justify-content:space-between;
  padding:20px 40px; border-bottom:1px solid var(--border);
  background:var(--surface-1); position:sticky; top:0; z-index:50;
  backdrop-filter:blur(10px);
}
.topbar-title {
  font-family:'DM Serif Display',serif; font-size:22px;
  color:var(--text-1); line-height:1.2;
}
.topbar-title em { font-style:italic; color:var(--green); }
.topbar-sub { font-size:12px; color:var(--text-3); margin-top:2px; font-family:'DM Mono',monospace; }

/* ── Content ── */
.content { padding:40px; max-width:760px; }

/* Section cards */
.section-card {
  background:var(--surface-2);
  border:1px solid var(--border);
  border-radius:20px;
  padding:28px;
  margin-bottom:20px;
  transition:border-color 0.2s;
}
.section-card:hover { border-color:var(--border-hi); }

.section-head {
  display:flex; align-items:flex-start; justify-content:space-between;
  margin-bottom:22px; padding-bottom:18px;
  border-bottom:1px solid var(--border); gap:12px; flex-wrap:wrap;
}
.section-title {
  font-family:'DM Serif Display',serif; font-size:18px;
  color:var(--text-1); display:flex; align-items:center; gap:10px;
}
.section-title .ico { font-size:20px; }
.section-desc { font-size:13px; color:var(--text-3); margin-top:4px; line-height:1.6; }

/* Status row */
.status-row {
  display:flex; align-items:center; gap:14px;
  padding:14px 16px; background:var(--surface-3);
  border:1px solid var(--border); border-radius:12px; margin-bottom:16px;
}
.status-icon { font-size:20px; flex-shrink:0; }
.status-title { font-weight:500; color:var(--text-1); font-size:14px; }
.status-sub   { font-size:12px; color:var(--text-3); }

/* Action row */
.action-row {
  display:flex; gap:10px; flex-wrap:wrap;
}

/* Badges */
.badge {
  display:inline-flex; align-items:center; gap:6px;
  padding:4px 12px; border-radius:99px;
  font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.06em;
}
.badge::before { content:''; width:5px; height:5px; border-radius:50%; }
.badge-ok { background:rgba(61,186,102,0.1); color:var(--green); border:1px solid rgba(61,186,102,0.3); }
.badge-ok::before { background:var(--green); box-shadow:0 0 6px var(--green); }
.badge-err { background:rgba(232,69,60,0.1); color:var(--red); border:1px solid rgba(232,69,60,0.3); }
.badge-err::before { background:var(--red); }
.badge-warn { background:rgba(245,166,35,0.1); color:var(--amber); border:1px solid rgba(245,166,35,0.3); }
.badge-warn::before { background:var(--amber); }

/* Buttons */
.btn {
  display:inline-flex; align-items:center; gap:7px;
  padding:9px 18px; font-family:'DM Sans',sans-serif;
  font-size:13px; font-weight:500; cursor:pointer;
  border:none; border-radius:8px; transition:all 0.2s;
  text-decoration:none;
}
.btn-primary { background:var(--green); color:#0C1A0C; font-weight:600; }
.btn-primary:hover { background:#4dd174; box-shadow:0 6px 16px var(--green-glow); }
.btn-ghost { background:transparent; border:1px solid var(--border-hi); color:var(--text-2); }
.btn-ghost:hover { background:var(--surface-3); color:var(--text-1); }
.btn-danger { background:transparent; border:1px solid var(--red); color:var(--red); }
.btn-danger:hover { background:var(--red); color:#fff; }
.btn-sm { padding:7px 14px; font-size:12px; }

/* Form */
.field { margin-bottom:18px; }
.field label {
  display:block; font-size:11px; font-weight:600;
  text-transform:uppercase; letter-spacing:0.1em;
  color:var(--text-3); margin-bottom:8px;
}
.field input {
  width:100%; max-width:420px;
  background:var(--surface-3); border:1px solid var(--border);
  color:var(--text-1); padding:10px 13px; border-radius:8px;
  transition:border-color 0.2s; font-family:'DM Sans',sans-serif;
  font-size:14px;
}
.field input:focus {
  outline:none; border-color:var(--green);
  box-shadow:0 0 0 2px rgba(78,203,116,0.1);
}

/* Info box */
.info-box {
  background:rgba(78,203,116,0.05);
  border:1px solid rgba(78,203,116,0.2);
  border-radius:12px;
  padding:14px;
  font-size:12px;
  line-height:1.6;
  color:var(--text-2);
  margin-top:16px;
}
.info-box code {
  background:var(--surface-3);
  padding:2px 6px;
  border-radius:4px;
  font-family:'DM Mono',monospace;
  font-size:11px;
  color:var(--text-1);
}
.info-box strong {
  color:var(--text-1);
}

/* Steps */
.steps {
  display:flex; flex-direction:column; gap:12px;
}
.step-item {
  display:flex; gap:14px; align-items:flex-start;
}
.step-num {
  width:32px; height:32px;
  background:rgba(78,203,116,0.1);
  border:1px solid rgba(78,203,116,0.3);
  border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-weight:600; color:var(--green); flex-shrink:0; font-size:14px;
}
.step-text {
  flex:1; padding-top:4px;
  font-size:13px; color:var(--text-2); line-height:1.5;
}
.step-text strong { color:var(--text-1); }

/* Toast */
.toast-stack {
  position:fixed; bottom:20px; right:20px;
  display:flex; flex-direction:column; gap:10px;
  z-index:9999;
}
.toast {
  display:flex; align-items:center; gap:10px;
  background:var(--green); color:#0C1A0C;
  padding:12px 16px; border-radius:8px;
  font-weight:500; font-size:13px;
  animation:slideIn 0.3s cubic-bezier(0.4,0,0.2,1);
  box-shadow:0 8px 24px rgba(78,203,116,0.3);
}
.toast.err {
  background:var(--red); color:#fff;
  box-shadow:0 8px 24px rgba(240,90,82,0.3);
}
@keyframes slideIn {
  from { opacity:0; transform:translateX(100px); }
  to { opacity:1; transform:translateX(0); }
}

/* Sidebar responsive */
.sidebar-item {
  width:100%; display:flex; align-items:center; gap:12px;
  padding:10px 16px; text-decoration:none; color:var(--text-3);
  transition:all 0.2s;
}
.sidebar-item:hover { color:var(--text-1); background:var(--surface-3); }
.sidebar-item.active { color:var(--green); }
</style>
</head>
<body>

<div class="layout">
  <aside class="sidebar">
    <div class="sidebar-logo">
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
      </svg>
    </div>

    <a href="/" class="nav-link">
      <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
      </svg>
      <span class="nav-label">Dashboard</span>
    </a>

    <a href="/settings" class="nav-link active">
      <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="1"></circle>
        <path d="M12 1v6m0 6v6"></path>
        <path d="M4.22 4.22l4.24 4.24m2.12 2.12l4.24 4.24M1 12h6m6 0h6"></path>
        <path d="M4.22 19.78l4.24-4.24m2.12-2.12l4.24-4.24"/>
      </svg>
      <span class="nav-label">Impostazioni</span>
    </a>

    <div class="sidebar-spacer"></div>

    <div class="status-pill">
      <div class="status-dot on"></div>
      <span class="status-text">SMTP Attivo</span>
    </div>

    <a href="/logout" class="nav-link" style="margin-top:8px;">
      <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
        <polyline points="16 17 21 12 16 7"></polyline>
        <line x1="21" y1="12" x2="9" y2="12"></line>
      </svg>
      <span class="nav-label">Esci</span>
    </a>
  </aside>

  <div class="main">
    <header class="topbar">
      <div>
        <div class="topbar-title">Impost<em>azioni</em></div>
        <div class="topbar-sub">Configura notifiche SMTP e Gemini AI</div>
      </div>
    </header>

    <div class="content">

      <!-- Email SMTP -->
      <div class="section-card">
        <div class="section-head">
          <div>
            <div class="section-title"><span class="ico">📧</span> Email SMTP — Notifiche Automatiche</div>
            <div class="section-desc">Ricevi email ai 30 e 7 giorni prima delle scadenze usando il tuo provider SMTP (Outlook, Aruba, ecc.)</div>
          </div>
          <span id="smtpBadge"><span class="badge badge-ok">Configurato</span></span>
        </div>

        <div class="status-row">
          <span class="status-icon">✅</span>
          <div>
            <div class="status-title">Sistema SMTP Attivo</div>
            <div class="status-sub">Email configurate tramite variabili d'ambiente su Render</div>
          </div>
        </div>

        <div class="field">
          <label>Email dove ricevere i reminder</label>
          <input type="email" id="reminderEmail" placeholder="es. tuaaaa@outlook.com">
        </div>

        <div class="action-row">
          <button class="btn btn-primary btn-sm" onclick="saveEmail()">
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path d="M5 13l4 4L19 7"/></svg>
            Salva email
          </button>
          <button class="btn btn-ghost btn-sm" onclick="testEmail()">
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
            Invia email di prova
          </button>
        </div>

        <div class="info-box">
          <strong>Configurazione SMTP:</strong> Le credenziali sono già impostate su Render con questi parametri:<br><br>
          <code>SMTP_SERVER=smtp-mail.outlook.com</code><br>
          <code>SMTP_PORT=587</code><br>
          <code>SMTP_USER=[tua email]</code><br>
          <code>SMTP_PASSWORD=[tua password]</code><br><br>
          Inserisci qui l'email dove vuoi ricevere i reminder e clicca "Salva".
        </div>
      </div>

      <!-- Gemini API -->
      <div class="section-card">
        <div class="section-head">
          <div>
            <div class="section-title"><span class="ico">🤖</span> KE AI Core — Gemini API</div>
            <div class="section-desc">Il motore AI che analizza i documenti e estrae automaticamente nome, categoria e data di scadenza.</div>
          </div>
          <span id="apiKeyBadge"></span>
        </div>
        <div class="info-box">
          <strong>Configurazione:</strong> imposta la chiave come variabile d'ambiente su Render.<br><br>
          <strong>Render Environment Variables:</strong> <code>GEMINI_API_KEY=AIzaSy-tuachiave</code><br><br>
          Ottieni la tua chiave su <strong>aistudio.google.com</strong> → API Keys.
        </div>
      </div>

      <!-- Protocollo -->
      <div class="section-card">
        <div class="section-head">
          <div>
            <div class="section-title"><span class="ico">🔄</span> Protocollo di Monitoraggio</div>
            <div class="section-desc">Come funziona il sistema di notifiche automatiche.</div>
          </div>
        </div>
        <div class="steps">
          <div class="step-item">
            <div class="step-num">1</div>
            <div class="step-text">Ogni giorno alle <strong>08:00</strong> il server esegue una scansione completa dell'archivio.</div>
          </div>
          <div class="step-item">
            <div class="step-num">2</div>
            <div class="step-text">Se un documento scade tra esattamente <strong>30 giorni</strong>, viene inviata una email di promemoria anticipata.</div>
          </div>
          <div class="step-item">
            <div class="step-num">3</div>
            <div class="step-text">Un secondo promemoria critico viene inviato quando mancano <strong>7 giorni</strong> alla scadenza.</div>
          </div>
          <div class="step-item">
            <div class="step-num">4</div>
            <div class="step-text">Le email vengono inviate tramite SMTP dal tuo provider (Outlook, Aruba, ecc.). Verifica la configurazione con "Email di prova".</div>
          </div>
        </div>
      </div>

    </div>
  </div>
</div>

<div class="toast-stack" id="toastStack"></div>

<script>
function toast(msg, err=false) {
  const stack = document.getElementById('toastStack');
  const el = document.createElement('div');
  el.className = 'toast' + (err ? ' err' : '');
  el.innerHTML = `<span>${err ? '❌' : '✅'}</span><span>${msg}</span>`;
  stack.appendChild(el);
  setTimeout(() => { el.style.opacity='0'; el.style.transition='opacity 0.4s'; setTimeout(()=>el.remove(),400); }, 3500);
}

async function loadSettings() {
  try {
    const s = await fetch('/api/settings').then(r=>r.json());

    if (s.user_email) document.getElementById('reminderEmail').value = s.user_email;

    document.getElementById('apiKeyBadge').innerHTML = s.gemini_key_set
      ? '<span class="badge badge-ok">Configurato</span>'
      : '<span class="badge badge-warn">Non impostata</span>';

  } catch(e) {
    toast('Errore caricamento impostazioni', true);
  }
}

async function saveEmail() {
  const email = document.getElementById('reminderEmail').value.trim();
  if (!email) { toast('Inserisci un indirizzo email valido', true); return; }
  try {
    const res = await fetch('/api/settings/email', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email})
    });
    if (res.ok) {
      toast('Email salvata con successo!');
    } else {
      toast('Errore nel salvataggio', true);
    }
  } catch(e) {
    toast('Errore di connessione', true);
  }
}

async function testEmail() {
  const email = document.getElementById('reminderEmail').value.trim();
  if (!email) {
    toast('Inserisci prima l\'email dove ricevere i reminder', true);
    return;
  }

  try {
    const res = await fetch('/api/test-email', { method:'POST' });
    const data = await res.json();
    if (data.ok) {
      toast('Email di prova inviata! Controlla la tua inbox (o spam)');
    } else {
      toast('Errore: ' + (data.error || 'Invio fallito'), true);
    }
  } catch(e) {
    toast('Errore di connessione', true);
  }
}

loadSettings();
</script>
</body>
</html>
