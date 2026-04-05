"""
ORACOLO COVOLO - SISTEMA COMPLETO
Cassetti aziendali + Gruppi + Web Search + Upload + 3 Pulsanti + Immagini
"""
import os, json, sqlite3, base64, re
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
import httpx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "oracolo_covolo.db")
os.makedirs(DATA_DIR, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

BRANDS_LIST = [
    "Acquabella", "Altamarea", "Anem", "Antoniolupi", "Aparici", "Apavisa",
    "Ariostea", "Artesia", "Austroflamm", "BGP", "Brera", "Bisazza",
    "Blue Design", "Baufloor", "Bauwerk", "Caros", "Caesar", "Casalgrande Padana",
    "Cerasarda", "Cerasa", "Cielo", "Colombo", "Cottodeste", "CP Parquet",
    "CSA", "Decor Walther", "Demm", "DoorAmeda", "Duscholux", "Duravit",
    "Edimax Astor", "FAP Ceramiche", "FMG", "Floorim", "Gerflor", "Gessi",
    "Gigacer", "Glamm Fire", "GOman", "Gridiron", "Gruppo Bardelli", "Gruppo Geromin",
    "Ier Hurne", "Inklostro Bianco", "Iniziativa Legno", "Iris", "Italgraniti",
    "Kaldewei", "Linki", "Madegan", "Marca Corona", "Mirage", "Milldue",
    "Murexin", "Noorth", "Omegius", "Piastrelle Arredo", "Profiletec", "Remer",
    "Sichenia", "Simas", "Schluter Systems", "SDR", "Sterneldesign", "Stuv",
    "Sunshower", "Sunshower Wellness", "Tonalite", "Tresse", "Trimline Fires",
    "Tubes", "Valdama", "Vismara Vetro", "Wedi"
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS aziende (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        content TEXT,
        azienda_id INTEGER,
        visibility TEXT DEFAULT 'public',
        access_code TEXT,
        upload_date TEXT,
        FOREIGN KEY (azienda_id) REFERENCES aziende(id)
    )''')
    for brand in BRANDS_LIST:
        c.execute('INSERT OR IGNORE INTO aziende (nome) VALUES (?)', (brand,))
    conn.commit()
    conn.close()

app = Flask(__name__)
init_db()

@app.route('/api/get-brands', methods=['GET'])
def get_brands():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nome FROM aziende ORDER BY nome')
    brands = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify({"brands": brands})

@app.route('/api/add-azienda', methods=['POST'])
def add_azienda():
    data = request.get_json()
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({"error": "Nome richiesto"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO aziende (nome) VALUES (?)', (nome,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "nome": nome})
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

@app.route('/api/upload-document', methods=['POST'])
def upload_document():
    data = request.get_json()
    filename = data.get('filename', '')
    content = data.get('content', '')
    brand = data.get('brand', '')
    visibility = data.get('visibility', 'public')
    access_code = data.get('access_code', '')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('SELECT id FROM aziende WHERE nome = ?', (brand,))
        result = c.fetchone()
        if not result:
            conn.close()
            return jsonify({"error": "Brand non trovato"}), 400
        azienda_id = result[0]
        c.execute('INSERT INTO documents (filename, content, azienda_id, visibility, access_code, upload_date) VALUES (?, ?, ?, ?, ?, ?)',
                  (filename, content, azienda_id, visibility, access_code, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

@app.route('/api/search-documents', methods=['POST'])
def search_documents():
    data = request.get_json()
    brands = data.get('brands', [])
    question = data.get('question', '')
    access_code = data.get('access_code')
    docs = _search_docs_internal(brands, question, access_code)
    if docs:
        return jsonify({"found": True, "docs": docs})
    return jsonify({"found": False})

def _search_docs_internal(brands, question, access_code):
    if not brands:
        return []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ','.join('?' * len(brands))
    query = f'SELECT filename, content FROM documents WHERE azienda_id IN (SELECT id FROM aziende WHERE nome IN ({placeholders}))'
    if access_code:
        query += ' OR (visibility="private" AND access_code=?)'
        c.execute(query, brands + [access_code])
    else:
        query += ' AND visibility="public"'
        c.execute(query, brands)
    docs = c.fetchall()
    conn.close()
    return docs

def search_web(question, brands):
    return None  # disabilitato - causa timeout su Render
    try:
        brands_str = " OR ".join(brands)
        query = f"{question} {brands_str}"
        url = "https://www.google.com/search"
        headers = {'User-Agent': 'Mozilla/5.0'}
        params = {'q': query}
        resp = httpx.get(url, params=params, headers=headers, timeout=5, follow_redirects=True)
        if "No results found" in resp.text or len(resp.text) < 100:
            return None
        return resp.text[:500]
    except:
        return None

def deepseek_ask(prompt):
    if not DEEPSEEK_API_KEY:
        return "API Key non configurata"
    try:
        resp = httpx.post(
            DEEPSEEK_API_URL,
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500
            },
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
        return f"Errore API: {resp.status_code}"
    except Exception as e:
        return f"Errore: {str(e)}"

@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = data.get('question', '')
    brands = data.get('brands', [])
    use_web = data.get('web', True)
    access_code = data.get('access_code')
    if not question or not brands:
        return jsonify({"error": "Domanda e brand richiesti"}), 400
    doc_context = ""
    docs = _search_docs_internal(brands, question, access_code)
    if docs:
        doc_context = "\n".join([f"[DOC: {d[0]}] {d[1][:200]}" for d in docs])
    web_context = ""
    if use_web:
        web_result = search_web(question, brands)
        if web_result:
            web_context = f"[WEB] {web_result}"
    prompt = f"""Sei un esperto di arredo bagno per i brand: {', '.join(brands)}

Domanda: {question}

{f'Documenti disponibili: {doc_context}' if doc_context else ''}
{f'{web_context}' if web_context else ''}

Rispondi come esperto del settore, considerando i brand specifici."""
    answer = deepseek_ask(prompt)
    return jsonify({"answer": answer})

@app.route('/')
def index():
    return render_template_string(r'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Oracolo Covolo</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system; background: linear-gradient(135deg, #0f172e 0%, #1a1f3a 100%); color: #e0e0e0; min-height: 100vh; }
.container { display: flex; height: 100vh; }
.sidebar { width: 360px; background: rgba(15,23,46,0.9); border-right: 1px solid rgba(59,130,245,0.2); padding: 20px; overflow-y: auto; }
.main { flex: 1; display: flex; flex-direction: column; padding: 20px; }
h2 { color: #3b82f6; margin-bottom: 12px; font-size: 13px; font-weight: 700; }
button { padding: 10px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; margin-bottom: 8px; font-size: 12px; }
button:hover { background: #2563eb; }
.btn-green { background: #10b981; }
.btn-green:hover { background: #059669; }
.btn-red { background: #ef4444; }
.btn-red:hover { background: #dc2626; }
.dropdown { background: rgba(30,41,59,0.95); border: 1px solid rgba(59,130,245,0.5); border-radius: 6px; padding: 10px; max-height: 250px; overflow-y: auto; display: none; margin-bottom: 10px; }
.dropdown.show { display: block; }
.brand-item { padding: 5px; cursor: pointer; font-size: 12px; }
.brand-item input { margin-right: 5px; }
.badge { display: inline-block; background: #10b981; color: white; padding: 3px 6px; border-radius: 3px; margin: 2px; font-size: 11px; }
.chat-area { flex: 1; background: rgba(15,23,46,0.5); border: 1px solid rgba(59,130,245,0.2); border-radius: 6px; padding: 15px; overflow-y: auto; margin-bottom: 10px; font-size: 13px; }
.message { background: rgba(59,130,245,0.1); padding: 10px; margin: 5px 0; border-radius: 4px; border-left: 3px solid #3b82f6; }
.input-area { display: flex; gap: 10px; }
input { flex: 1; padding: 10px; background: rgba(30,41,59,0.8); border: 1px solid rgba(59,130,245,0.3); color: white; border-radius: 6px; font-size: 12px; }
.title { color: #3b82f6; font-size: 24px; font-weight: 700; margin-bottom: 20px; }
.btn-3pulsanti { display: flex; gap: 6px; margin-bottom: 15px; }
.btn-3pulsanti button { flex: 1; padding: 8px; font-size: 11px; }
.toggle-btn { width: 100%; padding: 8px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; margin-bottom: 8px; }
.toggle-on { background: #10b981; color: white; }
.toggle-off { background: #6b7280; color: white; }
</style>
</head>
<body>
<div class="container">
  <div class="sidebar">
    <h2>SELEZIONA BRAND</h2>
    <button onclick="toggleDropdown()" style="width: 100%;">Seleziona Brand</button>
    <div id="dropdown" class="dropdown">
      <input type="text" id="search" placeholder="Ricerca brand..." onkeyup="filterBrands()" style="width: 100%; margin-bottom: 8px;">
      <div id="brands-list"></div>
    </div>
    <div style="margin: 10px 0;" id="selected"></div>
    <h2>GRUPPI SALVATI</h2>
    <div style="display: flex; gap: 6px; margin-bottom: 10px;">
      <input type="text" id="group-name" placeholder="Nome gruppo..." style="flex: 1;">
      <button onclick="saveGroup()" class="btn-green">Salva</button>
    </div>
    <div id="saved-groups" style="max-height: 150px; overflow-y: auto; font-size: 12px;"></div>
    <h2>NUOVO CASSETTO</h2>
    <div style="display: flex; gap: 6px; margin-bottom: 10px;">
      <input type="text" id="new-cassetto" placeholder="Nome cassetto..." style="flex: 1;">
      <button onclick="addCassetto()" class="btn-green">+</button>
    </div>
    <h2>ACCESSO PRIVATO</h2>
    <input type="password" id="access-code" placeholder="Codice accesso..." style="width: 100%; margin-bottom: 8px;">
    <button onclick="toggleAccess()" style="width: 100%;">Attiva</button>
    <div style="font-size: 11px; color: #9ca3af; margin-top: 5px;" id="access-status">Accesso: PUBBLICO</div>
    <h2>WEB SEARCH</h2>
    <button id="web-toggle" class="toggle-btn toggle-on" onclick="toggleWeb()">ON</button>
    <h2>UPLOAD DOCUMENTI</h2>
    <button onclick="uploadFile()" style="width: 100%; background: #8b5cf6;">Upload Doc</button>
    <button onclick="uploadExcel()" style="width: 100%; background: #8b5cf6;">Upload Excel</button>
  </div>
  <div class="main">
    <div class="title">Oracolo Covolo</div>
    <div class="btn-3pulsanti">
      <button class="btn-green" onclick="generateOfferta()">OFFERTA</button>
      <button class="btn-green" onclick="generateAnalisi()">ANALISI</button>
      <button class="btn-green" onclick="generateProposta()">PROPOSTA</button>
    </div>
    <div class="chat-area" id="chat"></div>
    <div class="input-area">
      <input type="text" id="question" placeholder="Domanda..." onkeypress="if(event.key==='Enter') ask()">
      <button onclick="ask()" style="width: 120px;">Invia</button>
    </div>
  </div>
</div>
<script>
let BRANDS = [];
let selected = [];
let webEnabled = true;
let accessCode = null;
let accessLevel = "public";
let groups = JSON.parse(localStorage.getItem('oracolo_groups')) || {};

fetch('/api/get-brands')
  .then(r => r.json())
  .then(d => {
    BRANDS = d.brands || [];
    console.log("Brand caricati: " + BRANDS.length);
    loadGroups();
  })
  .catch(e => { console.error("Errore caricamento brand:", e); });

function toggleDropdown() {
  const dd = document.getElementById('dropdown');
  if (!dd) return;
  if (dd.classList.contains('show')) {
    dd.classList.remove('show');
  } else {
    dd.classList.add('show');
    filterBrands();
  }
}

function filterBrands() {
  const search = document.getElementById('search');
  const brandsList = document.getElementById('brands-list');
  if (!search || !brandsList) return;
  const searchValue = search.value.toLowerCase();
  const filtered = BRANDS.filter(b => b.toLowerCase().includes(searchValue));
  brandsList.innerHTML = filtered.map(b =>
    '<div class="brand-item"><input type="checkbox" value="' + b + '" onchange="updateSelected()">' + b + '</div>'
  ).join('');
}

function updateSelected() {
  selected = [];
  document.querySelectorAll('.brand-item input:checked').forEach(cb => { selected.push(cb.value); });
  document.getElementById('selected').innerHTML = selected.map(b => '<span class="badge">' + b + ' x</span>').join('');
}

function toggleWeb() {
  webEnabled = !webEnabled;
  const btn = document.getElementById('web-toggle');
  btn.textContent = webEnabled ? 'ON' : 'OFF';
  btn.className = webEnabled ? 'toggle-btn toggle-on' : 'toggle-btn toggle-off';
}

function toggleAccess() {
  const code = document.getElementById('access-code').value;
  if (code) {
    accessCode = code; accessLevel = "private";
    document.getElementById('access-status').textContent = 'Accesso: PRIVATO (' + code + ')';
  } else {
    accessCode = null; accessLevel = "public";
    document.getElementById('access-status').textContent = 'Accesso: PUBBLICO';
  }
}

function saveGroup() {
  const name = document.getElementById('group-name').value;
  if (!name || selected.length === 0) { alert('Nome gruppo e brand richiesti'); return; }
  groups[name] = selected;
  localStorage.setItem('oracolo_groups', JSON.stringify(groups));
  document.getElementById('group-name').value = '';
  loadGroups();
}

function loadGroups() {
  document.getElementById('saved-groups').innerHTML = Object.keys(groups).map(name =>
    '<div style="padding:6px;background:rgba(59,130,245,0.2);border-radius:4px;margin:4px 0"><strong>' + name + '</strong> <button onclick="loadGroup(\'' + name + '\')" style="padding:2px 6px;font-size:10px">carica</button> <button onclick="deleteGroup(\'' + name + '\')" style="padding:2px 6px;font-size:10px;background:#ef4444">x</button></div>'
  ).join('');
}

function loadGroup(name) {
  selected = groups[name] || [];
  updateSelected();
  document.getElementById('dropdown').classList.remove('show');
}

function deleteGroup(name) {
  delete groups[name];
  localStorage.setItem('oracolo_groups', JSON.stringify(groups));
  loadGroups();
}

function addCassetto() {
  const nome = document.getElementById('new-cassetto').value.trim();
  if (!nome) { alert('Nome richiesto'); return; }
  fetch('/api/add-azienda', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({nome}) })
    .then(r => r.json())
    .then(d => {
      if (d.ok) {
        alert('Cassetto aggiunto!');
        document.getElementById('new-cassetto').value = '';
        fetch('/api/get-brands').then(r => r.json()).then(data => { BRANDS = data.brands || []; });
      } else { alert('Errore: ' + d.error); }
    });
}

function uploadFile() {
  const brand = prompt('Brand:');
  if (!brand) return;
  const input = document.createElement('input');
  input.type = 'file';
  input.onchange = function() {
    const file = input.files[0];
    const reader = new FileReader();
    reader.onload = function(e) {
      fetch('/api/upload-document', { method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ filename: file.name, content: e.target.result, brand, visibility: accessLevel, access_code: accessCode }) })
        .then(r => r.json()).then(d => { if (d.ok) alert('Documento caricato!'); else alert('Errore: ' + d.error); });
    };
    reader.readAsDataURL(file);
  };
  input.click();
}

function uploadExcel() {
  const brand = prompt('Brand per EXCEL:');
  if (!brand) return;
  const input = document.createElement('input');
  input.type = 'file'; input.accept = '.xlsx,.xls,.csv';
  input.onchange = function() {
    const file = input.files[0];
    const reader = new FileReader();
    reader.onload = function(e) {
      fetch('/api/upload-document', { method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ filename: file.name + ' [EXCEL]', content: e.target.result, brand, visibility: accessLevel, access_code: accessCode }) })
        .then(r => r.json()).then(d => { if (d.ok) alert('Excel caricato!'); else alert('Errore: ' + d.error); });
    };
    reader.readAsDataURL(file);
  };
  input.click();
}

function generateOfferta() {
  if (!selected.length) { alert('Seleziona brand'); return; }
  document.getElementById('question').value = 'Genera una proposta commerciale per: ' + selected.join(', ');
  ask();
}
function generateAnalisi() {
  if (!selected.length) { alert('Seleziona brand'); return; }
  document.getElementById('question').value = 'Analizza il posizionamento di mercato di: ' + selected.join(', ');
  ask();
}
function generateProposta() {
  if (!selected.length) { alert('Seleziona brand'); return; }
  document.getElementById('question').value = 'Proposta strategica per: ' + selected.join(', ');
  ask();
}

function parseMarkdown(text) {
  return text
    .replace(/### (.+)/g, '<h3 style="color:#60a5fa;margin:10px 0 4px 0;font-size:13px">$1</h3>')
    .replace(/## (.+)/g, '<h2 style="color:#3b82f6;margin:12px 0 6px 0;font-size:14px">$1</h2>')
    .replace(/# (.+)/g, '<h1 style="color:#3b82f6;margin:12px 0 6px 0;font-size:15px">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^[-–—] (.+)/gm, '<li style="margin-left:16px;margin-bottom:3px">$1</li>')
    .replace(/(<li.*<\/li>)/gs, '<ul style="margin:6px 0">$1</ul>')
    .replace(/\n{2,}/g, '</p><p style="margin:6px 0">')
    .replace(/\n/g, '<br>');
}

function ask() {
  if (!selected.length) { alert('Seleziona brand'); return; }
  const q = document.getElementById('question').value;
  if (!q) return;
  document.getElementById('question').value = '';
  const chat = document.getElementById('chat');
  chat.innerHTML += '<div class="message"><strong>Tu:</strong> ' + q + '</div>';
  // Loading indicator
  const loadingId = 'loading_' + Date.now();
  chat.innerHTML += '<div class="message" id="' + loadingId + '" style="opacity:0.6;font-style:italic">Oracolo sta elaborando...</div>';
  chat.scrollTop = chat.scrollHeight;
  fetch('/api/ask', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ question: q, brands: selected, web: webEnabled, access_code: accessCode }) })
    .then(r => r.json())
    .then(d => {
      const loading = document.getElementById(loadingId);
      if (loading) loading.remove();
      const formatted = parseMarkdown(d.answer || 'Nessuna risposta');
      chat.innerHTML += '<div class="message oracolo-msg"><strong style="color:#60a5fa">Oracolo:</strong><div style="margin-top:6px;line-height:1.6">' + formatted + '</div></div>';
      chat.scrollTop = chat.scrollHeight;
    })
    .catch(e => {
      const loading = document.getElementById(loadingId);
      if (loading) loading.remove();
      chat.innerHTML += '<div class="message" style="color:#ef4444"><strong>Errore:</strong> ' + e + '</div>';
    });
}
</script>
</body>
</html>''')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
