"""
ORACOLO COVOLO - SISTEMA COMPLETO
Cassetti aziendali + Gruppi + Web Search + Upload + 3 Pulsanti + Immagini
+ Protezione cassetto con password admin + Delete documenti protetto
"""
import os, json, sqlite3, base64, re, hashlib
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
    "Murexin", "Noorth", "Omegius", "Piastrelle d Arredo", "Profiletec", "Remer",
    "Sichenia", "Simas", "Schluter Systems", "SDR", "Sterneldesign", "Stuv",
    "Sunshower", "Sunshower Wellness", "Tonalite", "Tresse", "Trimline Fires",
    "Tubes", "Valdama", "Vismara Vetro", "Wedi"
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS aziende (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        admin_password TEXT,
        admin_required BOOLEAN DEFAULT 0
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

@app.route('/api/set-admin-password', methods=['POST'])
def set_admin_password():
    data = request.get_json()
    brand = data.get('brand', '')
    admin_password = data.get('admin_password', '').strip()
    if not brand or not admin_password:
        return jsonify({"error": "Brand e password richiesti"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        pwd_hash = hashlib.sha256(admin_password.encode()).hexdigest()
        c.execute('UPDATE aziende SET admin_password=?, admin_required=1 WHERE nome=?', (pwd_hash, brand))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "message": "Password admin impostata per " + brand})
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

@app.route('/api/verify-admin', methods=['POST'])
def verify_admin():
    data = request.get_json()
    brand = data.get('brand', '')
    admin_password = data.get('admin_password', '')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('SELECT admin_password, admin_required FROM aziende WHERE nome=?', (brand,))
        result = c.fetchone()
        conn.close()
        if not result:
            return jsonify({"ok": False, "error": "Brand non trovato"})
        pwd_hash, admin_required = result
        if not admin_required:
            return jsonify({"ok": True, "message": "Cassetto non protetto"})
        provided_hash = hashlib.sha256(admin_password.encode()).hexdigest()
        if provided_hash == pwd_hash:
            return jsonify({"ok": True, "message": "Password corretta"})
        else:
            return jsonify({"ok": False, "error": "Password errata"})
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
    admin_password = data.get('admin_password', '')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('SELECT id, admin_required, admin_password FROM aziende WHERE nome = ?', (brand,))
        result = c.fetchone()
        if not result:
            conn.close()
            return jsonify({"error": "Brand non trovato"}), 400
        azienda_id, admin_required, pwd_hash = result
        if admin_required:
            if not admin_password:
                conn.close()
                return jsonify({"error": "Password admin richiesta"}), 403
            provided_hash = hashlib.sha256(admin_password.encode()).hexdigest()
            if provided_hash != pwd_hash:
                conn.close()
                return jsonify({"error": "Password admin errata"}), 403
        c.execute('INSERT INTO documents (filename, content, azienda_id, visibility, access_code, upload_date) VALUES (?, ?, ?, ?, ?, ?)',
                  (filename, content, azienda_id, visibility, access_code, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

@app.route('/api/list-documents', methods=['GET'])
def list_documents():
    brand = request.args.get('brand', '')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if brand:
        c.execute('''SELECT d.id, d.filename, d.upload_date, d.visibility
                     FROM documents d
                     JOIN aziende a ON d.azienda_id = a.id
                     WHERE a.nome = ?
                     ORDER BY d.upload_date DESC''', (brand,))
    else:
        c.execute('SELECT id, filename, upload_date, visibility FROM documents ORDER BY upload_date DESC LIMIT 20')
    docs = c.fetchall()
    conn.close()
    result = [{"id": d[0], "filename": d[1], "date": d[2], "visibility": d[3]} for d in docs]
    return jsonify({"documents": result})

@app.route('/api/delete-document/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    admin_password = request.args.get('admin_password', '')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''SELECT a.nome, a.admin_required, a.admin_password
                     FROM documents d
                     JOIN aziende a ON d.azienda_id = a.id
                     WHERE d.id = ?''', (doc_id,))
        result = c.fetchone()
        if not result:
            conn.close()
            return jsonify({"error": "Documento non trovato"}), 404
        brand, admin_required, pwd_hash = result
        if admin_required:
            if not admin_password:
                conn.close()
                return jsonify({"error": "Password admin richiesta"}), 403
            provided_hash = hashlib.sha256(admin_password.encode()).hexdigest()
            if provided_hash != pwd_hash:
                conn.close()
                return jsonify({"error": "Password admin errata"}), 403
        c.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "message": "Documento eliminato"})
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
    if access_code:
        query = ("SELECT filename, content FROM documents "
                 "WHERE (azienda_id IN (SELECT id FROM aziende WHERE nome IN (" + placeholders + ")) AND visibility='public') "
                 "OR (visibility='private' AND access_code=?) LIMIT 10")
        c.execute(query, brands + [access_code])
    else:
        query = ("SELECT filename, content FROM documents "
                 "WHERE azienda_id IN (SELECT id FROM aziende WHERE nome IN (" + placeholders + ")) "
                 "AND visibility='public' LIMIT 10")
        c.execute(query, brands)
    docs = c.fetchall()
    conn.close()
    return docs

def search_web(question, brands):
    return None  # disabilitato - causa timeout su Render

def search_images(query, brands):
    try:
        search_query = query + " " + " ".join(brands) + " product image"
        url = "https://www.google.com/search"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        params = {'q': search_query, 'tbm': 'isch'}
        resp = httpx.get(url, params=params, headers=headers, timeout=5, follow_redirects=True)
        if resp.status_code == 200:
            pattern = r'"imgurl":"([^"]+)"'
            matches = re.findall(pattern, resp.text)
            images = matches[:5] if matches else []
            print("[IMAGES] Trovate " + str(len(images)) + " immagini")
            return images
        return []
    except Exception as e:
        print("[IMAGES ERROR] " + str(e))
        return []

def deepseek_ask(prompt):
    if not DEEPSEEK_API_KEY:
        return "Errore: API Key non configurata"
    try:
        resp = httpx.post(
            DEEPSEEK_API_URL,
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000
            },
            headers={"Authorization": "Bearer " + DEEPSEEK_API_KEY},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
        return "Errore API: " + str(resp.status_code)
    except Exception as e:
        return "Errore: " + str(e)

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
        doc_context = "\n".join(["[DOC: " + d[0] + "] " + d[1][:200] for d in docs])
    web_context = ""
    images = []
    if use_web:
        web_result = search_web(question, brands)
        if web_result:
            web_context = "[WEB] " + web_result
        images = search_images(question, brands)
    prompt = "Sei un esperto di arredo bagno per i brand: " + ", ".join(brands) + "\n\nDomanda: " + question
    if doc_context:
        prompt += "\n\nDocumenti disponibili: " + doc_context
    if web_context:
        prompt += "\n\n" + web_context
    prompt += "\n\nRispondi come esperto del settore, considerando i brand specifici."
    answer = deepseek_ask(prompt)
    return jsonify({"answer": answer, "images": images})

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
.message img { max-width: 100%; max-height: 200px; margin-top: 8px; border-radius: 4px; }
.input-area { display: flex; gap: 10px; }
input[type=text], input[type=password] { flex: 1; padding: 10px; background: rgba(30,41,59,0.8); border: 1px solid rgba(59,130,245,0.3); color: white; border-radius: 6px; font-size: 12px; }
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
    <h2>PROTEZIONE CASSETTO</h2>
    <div style="display: flex; gap: 6px; margin-bottom: 10px;">
      <input type="password" id="admin-pwd" placeholder="Password admin..." style="flex: 1;">
      <button onclick="setAdminPassword()" class="btn-green">Proteggi</button>
    </div>
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
    <select id="upload-brand" style="width:100%; margin-bottom:8px; padding:8px; background:rgba(30,41,59,0.8); border:1px solid rgba(139,92,246,0.5); color:white; border-radius:6px; font-size:12px;">
      <option value="">-- Seleziona Brand --</option>
    </select>
    <label style="display:block; width:100%; background:#8b5cf6; color:white; padding:10px; border-radius:6px; cursor:pointer; font-weight:600; font-size:12px; text-align:center; margin-bottom:8px;">
      Upload Doc
      <input type="file" id="file-doc" style="display:none" onchange="doUpload(this, 'doc')">
    </label>
    <label style="display:block; width:100%; background:#8b5cf6; color:white; padding:10px; border-radius:6px; cursor:pointer; font-weight:600; font-size:12px; text-align:center; margin-bottom:8px;">
      Upload Excel
      <input type="file" id="file-excel" accept=".xlsx,.xls,.csv" style="display:none" onchange="doUpload(this, 'excel')">
    </label>
    <div id="upload-status" style="font-size:11px; color:#9ca3af; margin-top:4px;"></div>
    <button onclick="showDocuments()" style="width:100%; background:#ef4444; margin-top:8px;">Gestisci Documenti</button>
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
    const sel = document.getElementById('upload-brand');
    if (sel) {
      BRANDS.forEach(b => {
        const opt = document.createElement('option');
        opt.value = b; opt.textContent = b;
        sel.appendChild(opt);
      });
    }
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

function setAdminPassword() {
  if (selected.length === 0) { alert('Seleziona prima un brand'); return; }
  const brand = selected[0];
  const pwd = document.getElementById('admin-pwd').value.trim();
  if (!pwd) { alert('Inserisci una password'); return; }
  fetch('/api/set-admin-password', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({brand: brand, admin_password: pwd})
  })
  .then(r => r.json())
  .then(d => {
    if (d.ok) alert('OK: ' + d.message);
    else alert('Errore: ' + d.error);
    document.getElementById('admin-pwd').value = '';
  });
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
        fetch('/api/get-brands').then(r => r.json()).then(data => {
          BRANDS = data.brands || [];
          const sel = document.getElementById('upload-brand');
          if (sel) {
            sel.innerHTML = '<option value="">-- Seleziona Brand --</option>';
            BRANDS.forEach(b => {
              const opt = document.createElement('option');
              opt.value = b; opt.textContent = b;
              sel.appendChild(opt);
            });
          }
        });
      } else { alert('Errore: ' + d.error); }
    });
}

function doUpload(input, tipo) {
  const brand = document.getElementById('upload-brand').value;
  if (!brand) {
    document.getElementById('upload-status').textContent = 'Seleziona prima un brand!';
    document.getElementById('upload-status').style.color = '#ef4444';
    input.value = '';
    return;
  }
  const file = input.files[0];
  if (!file) return;
  document.getElementById('upload-status').textContent = 'Caricamento in corso...';
  document.getElementById('upload-status').style.color = '#9ca3af';
  const reader = new FileReader();
  reader.onload = function(e) {
    const filename = tipo === 'excel' ? file.name + ' [EXCEL]' : file.name;
    fetch('/api/upload-document', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ filename: filename, content: e.target.result, brand: brand, visibility: accessLevel, access_code: accessCode }) })
      .then(r => r.json())
      .then(d => {
        if (d.ok) {
          document.getElementById('upload-status').textContent = 'Caricato: ' + file.name;
          document.getElementById('upload-status').style.color = '#10b981';
        } else {
          document.getElementById('upload-status').textContent = 'Errore: ' + d.error;
          document.getElementById('upload-status').style.color = '#ef4444';
        }
        input.value = '';
      });
  };
  reader.readAsDataURL(file);
}

function showDocuments() {
  const brand = prompt('Per quale brand vuoi gestire i documenti?');
  if (!brand) return;
  fetch('/api/list-documents?brand=' + encodeURIComponent(brand))
    .then(r => r.json())
    .then(d => {
      if (!d.documents || d.documents.length === 0) {
        alert('Nessun documento caricato per ' + brand);
        return;
      }
      const list = d.documents.map(doc => doc.id + ' | ' + doc.filename + ' | ' + (doc.date || '')).join('\n');
      const idStr = prompt('Documenti:\n' + list + '\n\nInserisci ID da eliminare (o annulla):');
      if (!idStr) return;
      const docId = parseInt(idStr);
      if (isNaN(docId)) { alert('ID non valido'); return; }
      deleteDocument(docId);
    });
}

function deleteDocument(docId) {
  if (!confirm('Sei sicuro di voler cancellare il documento ID ' + docId + '?')) return;
  fetch('/api/delete-document/' + docId, { method: 'DELETE' })
    .then(r => r.json())
    .then(d => {
      if (d.ok) alert('Documento eliminato!');
      else alert('Errore: ' + d.error);
    });
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
    .replace(/^[-\u2013\u2014] (.+)/gm, '<li style="margin-left:16px;margin-bottom:3px">$1</li>')
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
      let html = '<div class="message oracolo-msg"><strong style="color:#60a5fa">Oracolo:</strong><div style="margin-top:6px;line-height:1.6">' + formatted + '</div>';
      if (d.images && d.images.length > 0) {
        html += '<div style="margin-top:10px;display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px">';
        d.images.forEach(img => {
          html += '<img src="' + img + '" style="max-width:100%;height:auto;border-radius:4px;cursor:pointer" onclick="window.open(\'' + img + '\',\'_blank\')" title="Clicca per ingrandire">';
        });
        html += '</div>';
      }
      html += '</div>';
      chat.innerHTML += html;
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
