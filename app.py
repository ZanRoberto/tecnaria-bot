"""
ORACOLO COVOLO - APP PULITA
Versione semplificata e funzionante
"""
import os, json, sqlite3, re, hashlib, secrets, base64, io
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session
import httpx

try:
    import openpyxl
    OPENPYXL_OK = True
except:
    OPENPYXL_OK = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "oracolo_covolo.db")
os.makedirs(DATA_DIR, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "tecnaria2024").strip()

BRANDS_LIST = [
    "Gessi", "Duravit", "Kaldewei", "Antoniolupi", "Aparici", "Ariostea",
    "Caesar", "Casalgrande Padana", "FAP Ceramiche", "FMG", "Iris", "Marca Corona",
    "Mirage", "Sichenia", "Tonalite", "Acquabella", "Cerasa", "Colombo",
    "Remer", "Altamarea", "Anem", "Bauwerk", "CP Parquet", "Gerflor"
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
        filename TEXT, content TEXT, azienda_id INTEGER,
        upload_date TEXT, FOREIGN KEY (azienda_id) REFERENCES aziende(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS cantieri (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        stato TEXT DEFAULT 'bozza',
        data_creazione TEXT,
        UNIQUE(nome)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS cantiere_righe (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cantiere_id INTEGER NOT NULL,
        brand TEXT, descrizione TEXT, importo REAL DEFAULT 0,
        FOREIGN KEY (cantiere_id) REFERENCES cantieri(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS accessori (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prodotto_codice TEXT NOT NULL,
        accessorio_id TEXT NOT NULL,
        accessorio_nome TEXT,
        brand TEXT,
        tipo TEXT DEFAULT 'ufficiale',
        UNIQUE(prodotto_codice, accessorio_id)
    )''')
    
    for brand in BRANDS_LIST:
        c.execute('INSERT OR IGNORE INTO aziende (nome) VALUES (?)', (brand,))
    
    conn.commit()
    conn.close()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
init_db()

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def get_user():
    return session.get('user')

# ============================================================================
# LOGIN
# ============================================================================

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if username == 'superadmin' and password == SUPERADMIN_PASSWORD:
        session['user'] = {'nome': 'Tecnaria', 'ruolo': 'superadmin'}
        return jsonify({"ok": True})
    
    return jsonify({"ok": False, "error": "Credenziali errate"})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route('/api/me', methods=['GET'])
def me():
    u = get_user()
    return jsonify({"logged": u is not None, "user": u})

# ============================================================================
# BRANDS
# ============================================================================

@app.route('/api/get-brands', methods=['GET'])
def get_brands():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nome FROM aziende ORDER BY nome')
    brands = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify({"brands": brands})

# ============================================================================
# LISTINO - PARSING PULITO
# ============================================================================

@app.route('/api/listino/<brand>', methods=['GET'])
def get_listino(brand):
    """Carica il listino Excel dal brand"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Cerca il file Excel del brand
    c.execute("""SELECT content, filename FROM documents 
                 WHERE azienda_id = (SELECT id FROM aziende WHERE nome = ?)
                 AND (filename LIKE '%.xlsx' OR filename LIKE '%.xls')
                 ORDER BY upload_date DESC LIMIT 1""", (brand,))
    
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"ok": False, "prodotti": []})
    
    content_b64, filename = row
    
    try:
        # Decodifica base64
        if ',' in content_b64:
            content_b64 = content_b64.split(',', 1)[1]
        
        raw = base64.b64decode(content_b64)
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        ws = wb.active
        
        prodotti = []
        header = None
        col_idx = {}
        
        for i, row_data in enumerate(ws.iter_rows(values_only=True)):
            # Leggi header
            if header is None:
                row_str = [str(c).lower().strip() if c else '' for c in row_data]
                
                # Identifica colonne
                for j, cell in enumerate(row_str):
                    if 'codice' in cell or 'code' in cell or 'sku' in cell:
                        col_idx['codice'] = j
                    elif 'nome' in cell or 'name' in cell or 'descrizione' in cell:
                        col_idx['nome'] = j
                    elif 'collezione' in cell or 'collection' in cell or 'linea' in cell:
                        col_idx['collezione'] = j
                    elif 'prezzo' in cell and '€' in cell or 'listino' in cell:
                        col_idx['prezzo'] = j
                
                if 'codice' in col_idx:
                    header = row_data
                    continue
            
            # Leggi righe
            if not any(row_data):
                continue
            
            codice = row_data[col_idx['codice']] if 'codice' in col_idx else ''
            if not codice or str(codice).lower() == 'codice':
                continue
            
            nome = row_data[col_idx['nome']] if 'nome' in col_idx else ''
            collezione = row_data[col_idx['collezione']] if 'collezione' in col_idx else ''
            prezzo_raw = row_data[col_idx['prezzo']] if 'prezzo' in col_idx else ''
            
            # Parse prezzo
            prezzo = None
            if prezzo_raw:
                try:
                    prezzo = float(re.sub(r'[^\d.,]', '', str(prezzo_raw)).replace(',', '.'))
                except:
                    pass
            
            prodotti.append({
                'codice': str(codice).strip(),
                'nome': str(nome).strip() if nome else '',
                'collezione': str(collezione).strip() if collezione else '',
                'prezzo': prezzo,
            })
        
        return jsonify({"ok": True, "prodotti": prodotti, "fonte": filename})
    
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "prodotti": []})

# ============================================================================
# ACCESSORI
# ============================================================================

@app.route('/api/accessori/<prodotto_codice>', methods=['GET'])
def get_accessori(prodotto_codice):
    """Carica accessori per un prodotto"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""SELECT accessorio_id, accessorio_nome, brand, tipo 
                 FROM accessori WHERE prodotto_codice = ?
                 ORDER BY tipo DESC""", (prodotto_codice,))
    
    rows = c.fetchall()
    conn.close()
    
    ufficiali = []
    alternative = []
    
    for row in rows:
        acc = {
            'id': row[0],
            'nome': row[1],
            'brand': row[2],
        }
        if row[3] == 'ufficiale':
            ufficiali.append(acc)
        else:
            alternative.append(acc)
    
    return jsonify({
        "ufficiali": ufficiali,
        "alternative": alternative
    })

# ============================================================================
# DOCUMENTS
# ============================================================================

@app.route('/api/upload-document', methods=['POST'])
def upload_document():
    data = request.get_json()
    filename = data.get('filename', '')
    content = data.get('content', '')
    brand = data.get('brand', '')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('SELECT id FROM aziende WHERE nome = ?', (brand,))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return jsonify({"error": "Brand non trovato"}), 400
    
    azienda_id = result[0]
    
    c.execute('INSERT INTO documents (filename, content, azienda_id, upload_date) VALUES (?, ?, ?, ?)',
              (filename, content, azienda_id, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True})

@app.route('/api/list-documents', methods=['GET'])
def list_documents():
    brand = request.args.get('brand', '').strip()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if brand:
        c.execute('''SELECT d.id, d.filename, d.upload_date, a.nome
                     FROM documents d JOIN aziende a ON d.azienda_id = a.id
                     WHERE a.nome = ? ORDER BY d.upload_date DESC''', (brand,))
    else:
        c.execute('''SELECT d.id, d.filename, d.upload_date, a.nome
                     FROM documents d JOIN aziende a ON d.azienda_id = a.id
                     ORDER BY a.nome, d.upload_date DESC LIMIT 100''')
    
    docs = c.fetchall()
    conn.close()
    
    return jsonify({"documents": [{"id": d[0], "filename": d[1], "date": d[2], "brand": d[3]} for d in docs]})

@app.route('/api/delete-document/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ============================================================================
# CANTIERI
# ============================================================================

@app.route('/api/cantieri', methods=['GET'])
def get_cantieri():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, nome, stato FROM cantieri ORDER BY data_creazione DESC')
    cantieri = [{"id": r[0], "nome": r[1], "stato": r[2]} for r in c.fetchall()]
    conn.close()
    return jsonify({"cantieri": cantieri})

@app.route('/api/cantieri', methods=['POST'])
def add_cantiere():
    data = request.get_json()
    nome = data.get('nome', '').strip()
    
    if not nome:
        return jsonify({"error": "Nome richiesto"}), 400
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute('INSERT INTO cantieri (nome, data_creazione) VALUES (?, ?)',
                  (nome, datetime.now().isoformat()))
        cid = c.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "id": cid})
    except:
        conn.close()
        return jsonify({"error": "Cantiere già esiste"}), 400

@app.route('/api/cantieri/<int:cid>/righe', methods=['GET'])
def get_righe(cid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, brand, descrizione, importo FROM cantiere_righe WHERE cantiere_id = ?', (cid,))
    righe = [{"id": r[0], "brand": r[1], "descrizione": r[2], "importo": r[3]} for r in c.fetchall()]
    conn.close()
    return jsonify({"righe": righe})

@app.route('/api/cantieri/<int:cid>/righe', methods=['POST'])
def add_riga(cid):
    data = request.get_json()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO cantiere_righe (cantiere_id, brand, descrizione, importo) VALUES (?, ?, ?, ?)',
              (cid, data.get('brand', ''), data.get('descrizione', ''), data.get('importo', 0)))
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True})

@app.route('/api/cantieri/righe/<int:rid>', methods=['DELETE'])
def delete_riga(rid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM cantiere_righe WHERE id = ?', (rid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ============================================================================
# FRONTEND
# ============================================================================

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
.container { display: flex; height: 100vh; overflow: hidden; }
.sidebar { width: 300px; background: rgba(15,23,46,0.95); border-right: 1px solid rgba(59,130,245,0.2); padding: 16px; overflow-y: auto; }
.main { flex: 1; display: flex; flex-direction: column; padding: 16px; }
h2 { color: #3b82f6; margin-bottom: 10px; font-size: 12px; font-weight: 700; text-transform: uppercase; }
button { padding: 8px 12px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; margin-bottom: 6px; font-size: 11px; }
button:hover { opacity: 0.85; }
.btn-green { background: #10b981; }
.btn-red { background: #ef4444; }
button:disabled { background: #6b7280; cursor: not-allowed; }
input { padding: 8px; background: rgba(30,41,59,0.8); border: 1px solid rgba(59,130,245,0.3); color: white; border-radius: 6px; font-size: 11px; width: 100%; margin-bottom: 6px; }
input::placeholder { color: #6b7280; }
.prodotti-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 12px; }
.prodotto-card { background: rgba(30,41,59,0.9); border: 1px solid rgba(59,130,245,0.2); border-radius: 8px; padding: 12px; }
.codice { color: #3b82f6; font-size: 14px; font-weight: 700; margin-bottom: 4px; }
.nome { font-size: 12px; font-weight: 600; color: #e0e0e0; margin-bottom: 3px; }
.collezione { font-size: 10px; color: #9ca3af; margin-bottom: 6px; }
.prezzo { color: #10b981; font-weight: 700; font-size: 12px; }
.cantiere-item { background: rgba(59,130,245,0.1); border-radius: 4px; padding: 6px 8px; margin: 4px 0; font-size: 11px; cursor: pointer; }
.cantiere-item:hover { background: rgba(59,130,245,0.2); }
.login-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 9999; display: flex; align-items: center; justify-content: center; }
.login-box { background: rgba(15,23,46,0.98); border: 1px solid rgba(59,130,245,0.4); border-radius: 12px; padding: 32px; width: 320px; }
.login-title { color: #3b82f6; font-size: 20px; font-weight: 700; margin-bottom: 20px; text-align: center; }
.drawer { display: none; position: fixed; top: 0; right: 0; width: 480px; height: 100vh; background: #0f172e; border-left: 2px solid rgba(59,130,245,0.4); z-index: 1000; flex-direction: column; overflow-y: auto; padding: 16px; }
.drawer.open { display: flex; }
.drawer-header { font-size: 14px; font-weight: 700; color: #60a5fa; margin-bottom: 12px; }
.drawer-row { background: rgba(30,41,59,0.8); border-radius: 4px; padding: 8px; margin: 6px 0; display: flex; justify-content: space-between; align-items: center; font-size: 11px; }
.drawer-row button { margin: 0; padding: 4px 8px; font-size: 10px; }
.totale { background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.3); border-radius: 6px; padding: 8px; margin: 10px 0; display: flex; justify-content: space-between; font-weight: 700; }
</style>
</head>
<body>

<!-- LOGIN -->
<div class="login-overlay" id="login-overlay">
  <div class="login-box">
    <div class="login-title">Oracolo Covolo</div>
    <input type="text" id="login-user" placeholder="Username">
    <input type="password" id="login-pwd" placeholder="Password" onkeypress="if(event.key==='Enter') doLogin()">
    <button onclick="doLogin()" style="width: 100%; padding: 10px;">Accedi</button>
    <div id="login-error" style="color: #ef4444; font-size: 11px; margin-top: 8px; text-align: center;"></div>
  </div>
</div>

<!-- APP -->
<div class="container" id="main-app" style="display: none;">
  <!-- SIDEBAR -->
  <div class="sidebar">
    <button onclick="doLogout()" class="btn-red" style="width: 100%; margin-bottom: 12px;">Esci</button>
    
    <h2>Selezione Brand</h2>
    <input type="text" id="brand-search" placeholder="Cerca brand..." oninput="filterBrands()">
    <div id="brands-list" style="max-height: 150px; overflow-y: auto;"></div>
    
    <h2 style="margin-top: 16px;">Brand selezionati</h2>
    <div id="selected-brands" style="margin-bottom: 12px;"></div>
    
    <h2>Cantieri</h2>
    <input type="text" id="new-cantiere" placeholder="Nome cantiere...">
    <button onclick="addCantiere()" class="btn-green" style="width: 100%;">+ Nuovo</button>
    <div id="cantieri-list" style="max-height: 200px; overflow-y: auto;"></div>
  </div>

  <!-- MAIN -->
  <div class="main">
    <h2>Prodotti</h2>
    <div class="prodotti-grid" id="prodotti-grid"></div>
  </div>

  <!-- DRAWER CANTIERE -->
  <div class="drawer" id="drawer">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <span class="drawer-header" id="drawer-title"></span>
      <button onclick="closeDrawer()" class="btn-red" style="margin: 0; padding: 4px 8px;">✕</button>
    </div>
    
    <h2>Righe cantiere</h2>
    <div id="drawer-righe"></div>
    <div class="totale" id="totale" style="display: none;"><span>Totale</span><span id="totale-val">€0</span></div>
    
    <h2 style="margin-top: 12px;">Aggiungi prodotto</h2>
    <input type="text" id="desc-input" placeholder="Descrizione...">
    <input type="number" id="prezzo-input" placeholder="Prezzo €">
    <button onclick="addRigaManuale()" class="btn-green" style="width: 100%;">Aggiungi</button>
  </div>
</div>

<script>
let BRANDS = [];
let selected = [];
let cantiereAttivo = null;

function doLogin() {
  const user = document.getElementById('login-user').value.trim();
  const pwd = document.getElementById('login-pwd').value.trim();
  
  if (!user || !pwd) { alert('Inserisci username e password'); return; }
  
  fetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username: user, password: pwd}) })
    .then(r => r.json())
    .then(d => {
      if (d.ok) {
        document.getElementById('login-overlay').style.display = 'none';
        document.getElementById('main-app').style.display = 'flex';
        loadBrands();
        loadCantieri();
      } else {
        document.getElementById('login-error').textContent = d.error || 'Errore login';
      }
    });
}

function doLogout() {
  fetch('/api/logout', {method:'POST'}).then(() => location.reload());
}

function loadBrands() {
  fetch('/api/get-brands').then(r => r.json()).then(d => {
    BRANDS = d.brands || [];
    filterBrands();
  });
}

function filterBrands() {
  const sv = document.getElementById('brand-search').value.toLowerCase();
  const list = document.getElementById('brands-list');
  const filtered = sv ? BRANDS.filter(b => b.toLowerCase().includes(sv)) : BRANDS;
  
  list.innerHTML = filtered.map(b =>
    '<div class="cantiere-item" onclick="selectBrand(\'' + b + '\')">' + b + '</div>'
  ).join('');
}

function selectBrand(brand) {
  if (!selected.includes(brand)) selected.push(brand);
  
  document.getElementById('brand-search').value = '';
  filterBrands();
  updateSelectedBrands();
  
  // Mostra loading
  document.getElementById('prodotti-grid').innerHTML = '<div style="color: #6b7280; grid-column: 1/-1; text-align: center; padding: 20px;">⏳ Caricamento prodotti...</div>';
  
  // Carica listino
  fetch('/api/listino/' + encodeURIComponent(brand))
    .then(r => r.json())
    .then(d => {
      if (d.ok && d.prodotti && d.prodotti.length > 0) {
        showProdotti(d.prodotti, brand);
      } else {
        document.getElementById('prodotti-grid').innerHTML = '<div style="color: #ef4444; grid-column: 1/-1; text-align: center; padding: 20px;">❌ Nessun prodotto trovato per ' + brand + '</div>';
      }
    })
    .catch(e => {
      document.getElementById('prodotti-grid').innerHTML = '<div style="color: #ef4444; grid-column: 1/-1; text-align: center; padding: 20px;">❌ Errore: ' + e + '</div>';
    });
}

function updateSelectedBrands() {
  document.getElementById('selected-brands').innerHTML = selected.map(b =>
    '<div style="background: #3b82f6; color: white; padding: 4px 8px; border-radius: 4px; margin: 2px; display: inline-block; font-size: 11px;">' + b + ' <span onclick="selected.splice(selected.indexOf(\'' + b + '\'),1);updateSelectedBrands();" style="cursor: pointer; margin-left: 4px;">✕</span></div>'
  ).join('');
}

function showProdotti(prodotti, brand) {
  const grid = document.getElementById('prodotti-grid');
  
  grid.innerHTML = prodotti.map(p =>
    '<div class="prodotto-card">' +
    '<div class="codice">' + p.codice + '</div>' +
    '<div class="nome">' + (p.nome || '—') + '</div>' +
    '<div class="collezione">' + (p.collezione || '—') + '</div>' +
    '<div class="prezzo">€' + (p.prezzo || '—') + '</div>' +
    '<button onclick="aggiungiProdotto(\'' + p.codice.replace(/'/g,"\\'") + '\',\'' + (p.nome || '').replace(/'/g,"\\'") + '\',' + (p.prezzo || 0) + ',\'' + brand + '\')" class="btn-green" style="width: 100%; margin-top: 8px;">+ Carrello</button>' +
    '</div>'
  ).join('');
}

function aggiungiProdotto(codice, nome, prezzo, brand) {
  if (!cantiereAttivo) { alert('Crea prima un cantiere'); return; }
  
  const desc = '[' + codice + '] ' + nome;
  
  fetch('/api/cantieri/' + cantiereAttivo + '/righe', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({brand, descrizione: desc, importo: prezzo})
  })
  .then(r => r.json())
  .then(() => loadCantiere());
}

function loadCantieri() {
  fetch('/api/cantieri').then(r => r.json()).then(d => {
    const list = document.getElementById('cantieri-list');
    list.innerHTML = (d.cantieri || []).map(ca =>
      '<div class="cantiere-item" onclick="openCantiere(' + ca.id + ',\'' + ca.nome.replace(/'/g,"\\'") + '\')">' + ca.nome + '</div>'
    ).join('');
  });
}

function addCantiere() {
  const nome = document.getElementById('new-cantiere').value.trim();
  if (!nome) { alert('Nome richiesto'); return; }
  
  fetch('/api/cantieri', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nome}) })
    .then(r => r.json())
    .then(d => {
      if (d.ok) {
        document.getElementById('new-cantiere').value = '';
        loadCantieri();
        openCantiere(d.id, nome);
      }
    });
}

function openCantiere(id, nome) {
  cantiereAttivo = id;
  document.getElementById('drawer-title').textContent = nome;
  document.getElementById('drawer').classList.add('open');
  loadCantiere();
}

function closeDrawer() {
  cantiereAttivo = null;
  document.getElementById('drawer').classList.remove('open');
}

function loadCantiere() {
  if (!cantiereAttivo) return;
  
  fetch('/api/cantieri/' + cantiereAttivo + '/righe')
    .then(r => r.json())
    .then(d => {
      const righe = d.righe || [];
      let totale = 0;
      righe.forEach(r => totale += (r.importo || 0));
      
      document.getElementById('drawer-righe').innerHTML = righe.length === 0
        ? '<div style="color: #6b7280; font-size: 11px; padding: 12px 0;">Nessuna riga</div>'
        : righe.map(r =>
            '<div class="drawer-row">' +
            '<div><strong>' + (r.brand||'—') + '</strong><br>' + r.descrizione + '</div>' +
            '<div style="text-align: right;"><strong>€' + (r.importo||0).toFixed(0) + '</strong><br><button onclick="deleteRiga(' + r.id + ')" class="btn-red" style="padding: 2px 6px; font-size: 9px;">✕</button></div>' +
            '</div>'
          ).join('');
      
      if (righe.length > 0) {
        document.getElementById('totale').style.display = 'flex';
        document.getElementById('totale-val').textContent = '€' + totale.toFixed(0);
      } else {
        document.getElementById('totale').style.display = 'none';
      }
    });
}

function deleteRiga(rid) {
  fetch('/api/cantieri/righe/' + rid, {method:'DELETE'}).then(() => loadCantiere());
}

function addRigaManuale() {
  if (!cantiereAttivo) return;
  
  const desc = document.getElementById('desc-input').value.trim();
  const prezzo = parseFloat(document.getElementById('prezzo-input').value) || 0;
  
  if (!desc) { alert('Descrizione richiesta'); return; }
  
  fetch('/api/cantieri/' + cantiereAttivo + '/righe', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({brand: selected[0] || '', descrizione: desc, importo: prezzo})
  })
  .then(() => {
    document.getElementById('desc-input').value = '';
    document.getElementById('prezzo-input').value = '';
    loadCantiere();
  });
}

// Check login
fetch('/api/me').then(r => r.json()).then(d => {
  if (d.logged) {
    document.getElementById('login-overlay').style.display = 'none';
    document.getElementById('main-app').style.display = 'flex';
    loadBrands();
    loadCantieri();
  }
});
</script>

</body>
</html>''')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
