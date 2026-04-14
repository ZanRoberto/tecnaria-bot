#!/usr/bin/env python3
"""
ORACOLO COVOLO — Versione 8 PULITA
Architetto: Roberto / Tecnaria
Login: superadmin / ZANNA1959?
"""

import os
import json
import sqlite3
import hashlib
import secrets
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session

# ====== CONFIG ======
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "oracolo_covolo.db")
os.makedirs(DATA_DIR, exist_ok=True)

SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "ZANNA1959?")

BRANDS_LIST = [
    "Gessi", "Duravit", "Bisazza", "FMG", "Aparici", "Ariostea",
    "Caesar", "Cerasa", "Cielo", "Colombo", "Cottodeste", "Duscholux",
    "FAP Ceramiche", "Floorim", "Gigacer", "Iris", "Italgraniti", "Kaldewei",
    "Marca Corona", "Mirage", "Sichenia", "Simas", "Tonalite", "Altamarea",
    "Antoniolupi", "Bauwerk", "CP Parquet", "Gerflor", "Iniziativa Legno",
    "Madegan", "Acquabella", "Remer", "Decor Walther", "Tubes"
]

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

def init_db():
    """Inizializza database con tabelle essenziali"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # TABELLA PRINCIPALE: CANTIERI
    c.execute('''CREATE TABLE IF NOT EXISTS cantieri (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        stato TEXT DEFAULT 'bozza',
        modalita TEXT DEFAULT 'semplice',
        data_creazione TEXT,
        data_aggiornamento TEXT
    )''')
    
    # PIANI per modalita PIANI
    c.execute('''CREATE TABLE IF NOT EXISTS piani (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cantiere_id INTEGER NOT NULL,
        numero INTEGER,
        nome TEXT,
        totale_piano REAL DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY (cantiere_id) REFERENCES cantieri(id)
    )''')
    
    # STANZE
    c.execute('''CREATE TABLE IF NOT EXISTS stanze (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        piano_id INTEGER NOT NULL,
        nome TEXT,
        totale_stanza REAL DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY (piano_id) REFERENCES piani(id)
    )''')
    
    # VOCI STANZA
    c.execute('''CREATE TABLE IF NOT EXISTS stanza_voci (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stanza_id INTEGER NOT NULL,
        codice TEXT,
        brand TEXT,
        descrizione TEXT,
        quantita REAL DEFAULT 1,
        prezzo_unitario REAL DEFAULT 0,
        subtotale REAL DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY (stanza_id) REFERENCES stanze(id)
    )''')
    
    # RIGHE SEMPLICE
    c.execute('''CREATE TABLE IF NOT EXISTS cantiere_righe (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cantiere_id INTEGER NOT NULL,
        brand TEXT,
        categoria TEXT,
        descrizione TEXT,
        importo REAL DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY (cantiere_id) REFERENCES cantieri(id)
    )''')
    
    # PRODOTTI LISTINO
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codice TEXT UNIQUE NOT NULL,
        nome TEXT,
        categoria TEXT,
        prezzo REAL,
        prezzo_rivenditore REAL,
        descrizione TEXT,
        colore TEXT,
        disponibile INTEGER DEFAULT 1,
        immagine TEXT,
        brand TEXT,
        created_at TEXT
    )''')
    
    # BRAND
    c.execute('''CREATE TABLE IF NOT EXISTS aziende (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    )''')
    
    # DOCUMENTI
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        content TEXT,
        brand TEXT,
        upload_date TEXT
    )''')
    
    conn.commit()
    conn.close()
    
    # Carica brand
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for brand in BRANDS_LIST:
        c.execute('INSERT OR IGNORE INTO aziende (nome) VALUES (?)', (brand,))
    conn.commit()
    conn.close()

init_db()

# ====== AUTH ======
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if username == 'superadmin' and password == SUPERADMIN_PASSWORD:
        session['user'] = {
            'id': 0,
            'nome': 'Tecnaria',
            'ruolo': 'superadmin'
        }
        return jsonify({"ok": True, "ruolo": "superadmin", "nome": "Tecnaria"})
    
    return jsonify({"ok": False, "error": "Credenziali errate"})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route('/api/me', methods=['GET'])
def me():
    user = session.get('user')
    if not user:
        return jsonify({"logged": False})
    return jsonify({
        "logged": True,
        "user": user,
        "moduli": ["cantieri", "carrello", "bi"]
    })

# ====== CANTIERI ======
@app.route('/api/cantieri', methods=['GET'])
def get_cantieri():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nome, stato, data_creazione FROM cantieri ORDER BY data_creazione DESC LIMIT 100")
    rows = c.fetchall()
    conn.close()
    
    return jsonify({
        "cantieri": [
            {
                "id": r[0],
                "nome": r[1],
                "stato": r[2],
                "data": r[3]
            }
            for r in rows
        ]
    })

@app.route('/api/cantieri', methods=['POST'])
def add_cantiere():
    data = request.get_json()
    nome = data.get('nome', '').strip()
    
    if not nome:
        return jsonify({"error": "Nome richiesto"}), 400
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("INSERT INTO cantieri (nome, data_creazione, data_aggiornamento) VALUES (?,?,?)",
              (nome, now, now))
    cid = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True, "id": cid})

@app.route('/api/cantieri/<int:cid>/modalita', methods=['GET'])
def get_modalita(cid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT modalita FROM cantieri WHERE id = ?", (cid,))
    row = c.fetchone()
    conn.close()
    
    modalita = row[0] if row else 'semplice'
    return jsonify({"modalita": modalita})

@app.route('/api/cantieri/<int:cid>/modalita', methods=['PUT'])
def set_modalita(cid):
    data = request.get_json()
    modalita = data.get('modalita', 'semplice')
    
    if modalita not in ['semplice', 'piani']:
        return jsonify({"error": "Modalita non valida"}), 400
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE cantieri SET modalita = ?, data_aggiornamento = ? WHERE id = ?",
              (modalita, datetime.now().isoformat(), cid))
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True, "modalita": modalita})

@app.route('/api/cantieri/<int:cid>/struttura', methods=['GET'])
def get_struttura(cid):
    """Legge PIANI > STANZE > VOCI"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT id, numero, nome, totale_piano FROM piani WHERE cantiere_id = ? ORDER BY numero", (cid,))
    piani_rows = c.fetchall()
    
    piani = []
    for pid, num, nome, tot_piano in piani_rows:
        c.execute("SELECT id, nome, totale_stanza FROM stanze WHERE piano_id = ? ORDER BY nome", (pid,))
        stanze_rows = c.fetchall()
        
        stanze = []
        for sid, snome, tot_stanza in stanze_rows:
            c.execute("""SELECT id, codice, brand, descrizione, quantita, prezzo_unitario, subtotale
                         FROM stanza_voci WHERE stanza_id = ? ORDER BY created_at""", (sid,))
            voci_rows = c.fetchall()
            
            voci = [
                {
                    'id': v[0],
                    'codice': v[1],
                    'brand': v[2],
                    'descrizione': v[3],
                    'quantita': v[4],
                    'prezzo_unitario': v[5] or 0,
                    'subtotale': v[6] or 0
                }
                for v in voci_rows
            ]
            
            stanze.append({
                'id': sid,
                'nome': snome,
                'totale_stanza': tot_stanza or 0,
                'voci': voci
            })
        
        piani.append({
            'id': pid,
            'numero': num,
            'nome': nome,
            'totale_piano': tot_piano or 0,
            'stanze': stanze
        })
    
    conn.close()
    return jsonify({"ok": True, "piani": piani})

@app.route('/api/cantieri/<int:cid>/piani', methods=['POST'])
def create_piano(cid):
    data = request.get_json()
    nome = data.get('nome', 'Piano 1')
    numero = data.get('numero', 1)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("INSERT INTO piani (cantiere_id, numero, nome, created_at) VALUES (?,?,?,?)",
              (cid, numero, nome, now))
    pid = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True, "piano_id": pid})

@app.route('/api/piani/<int:pid>/stanze', methods=['POST'])
def add_stanza(pid):
    data = request.get_json()
    nome = data.get('nome', 'Stanza')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("INSERT INTO stanze (piano_id, nome, created_at) VALUES (?,?,?)",
              (pid, nome, now))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True, "stanza_id": sid})

@app.route('/api/stanze/<int:sid>/voci', methods=['POST'])
def add_voce(sid):
    data = request.get_json()
    
    qty = float(data.get('quantita', 1))
    prezzo = float(data.get('prezzo_unitario', 0))
    subtotale = prezzo * qty
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("""INSERT INTO stanza_voci 
                (stanza_id, codice, brand, descrizione, quantita, prezzo_unitario, subtotale, created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
              (sid, data.get('codice', ''), data.get('brand', ''), data.get('descrizione', ''),
               qty, prezzo, subtotale, now))
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True})

@app.route('/api/stanza_voci/<int:vid>', methods=['DELETE'])
def delete_voce(vid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM stanza_voci WHERE id = ?", (vid,))
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True})

# ====== BRAND ======
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
    except sqlite3.IntegrityError:
        pass
    conn.close()
    
    return jsonify({"ok": True, "nome": nome})

# ====== LISTINO ======
@app.route('/api/listino/<brand>', methods=['GET'])
def get_listino(brand):
    """Ritorna prodotti dal DB per un brand"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""SELECT codice, nome, categoria, prezzo, descrizione, colore, disponibile, immagine
                 FROM products WHERE LOWER(brand) = LOWER(?) ORDER BY nome LIMIT 100""", (brand,))
    rows = c.fetchall()
    conn.close()
    
    prodotti = [
        {
            'codice': r[0],
            'nome': r[1],
            'categoria': r[2],
            'prezzo': r[3] or 0,
            'descrizione': r[4] or '',
            'colore': r[5] or '',
            'disponibile': bool(r[6]),
            'immagine': r[7] or '',
            'brand': brand
        }
        for r in rows
    ]
    
    return jsonify({"ok": True, "prodotti": prodotti, "fonte": "db"})

@app.route('/api/cantieri/<int:cid>/righe', methods=['GET'])
def get_righe(cid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, brand, categoria, descrizione, importo FROM cantiere_righe WHERE cantiere_id = ?", (cid,))
    righe = [{"id": r[0], "brand": r[1], "categoria": r[2], "descrizione": r[3], "importo": r[4]} for r in c.fetchall()]
    conn.close()
    return jsonify({"righe": righe})

@app.route('/api/cantieri/<int:cid>/righe', methods=['POST'])
def add_riga(cid):
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("INSERT INTO cantiere_righe (cantiere_id, brand, categoria, descrizione, importo, created_at) VALUES (?,?,?,?,?,?)",
              (cid, data.get('brand', ''), data.get('categoria', ''), data.get('descrizione', ''), data.get('importo', 0), now))
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": rid})

@app.route('/api/cantieri/righe/<int:rid>', methods=['DELETE'])
def delete_riga(rid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM cantiere_righe WHERE id = ?", (rid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ====== FRONTEND ======
@app.route('/')
def index():
    return render_template_string('''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Oracolo Covolo V8</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system; background: #0f172e; color: #e0e0e0; min-height: 100vh; }
.container { display: flex; height: 100vh; }
.sidebar { width: 300px; background: rgba(15,23,46,0.95); border-right: 1px solid rgba(59,130,245,0.2); padding: 16px; overflow-y: auto; }
.main { flex: 1; display: flex; flex-direction: column; padding: 20px; }
h2 { color: #3b82f6; margin: 16px 0 8px 0; font-size: 12px; text-transform: uppercase; }
button { padding: 10px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; margin: 6px 0; }
button:hover { opacity: 0.85; }
input { padding: 8px 12px; background: rgba(30,41,59,0.8); border: 1px solid rgba(59,130,245,0.3); color: white; border-radius: 4px; width: 100%; margin: 6px 0; }
.cantiere-card { background: rgba(59,130,245,0.1); padding: 12px; border-radius: 6px; margin: 6px 0; cursor: pointer; border-left: 3px solid #3b82f6; }
.chat { flex: 1; background: rgba(30,41,59,0.5); border: 1px solid rgba(59,130,245,0.2); border-radius: 6px; padding: 16px; overflow-y: auto; margin: 12px 0; font-size: 13px; }
.message { background: rgba(59,130,245,0.1); padding: 10px; margin: 8px 0; border-radius: 4px; border-left: 3px solid #3b82f6; }
.login-box { position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%); background: #0f172e; border: 2px solid #3b82f6; border-radius: 12px; padding: 32px; width: 320px; }
.login-title { color: #3b82f6; font-size: 20px; font-weight: 700; margin-bottom: 20px; text-align: center; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; margin-top: 12px; }
.prod-card { background: rgba(30,41,59,0.9); border: 1px solid rgba(59,130,245,0.2); border-radius: 6px; padding: 12px; }
.prod-name { font-weight: 600; color: #e0e0e0; margin-bottom: 6px; }
.prod-price { font-size: 14px; color: #10b981; font-weight: bold; }
</style>
</head>
<body id="app" style="display:none;">
<div class="container">
  <div class="sidebar">
    <div id="user-label" style="color:#60a5fa;font-weight:600;margin-bottom:12px;"></div>
    <button onclick="doLogout()" style="background:#ef4444;width:100%;">Esci</button>
    
    <h2>Seleziona Brand</h2>
    <select id="brand-select" style="width:100%;" onchange="onBrandChange()"></select>
    
    <h2>Cantieri</h2>
    <div style="margin-bottom:8px;">
      <input type="text" id="new-cant" placeholder="Nome cantiere..." style="width:100%;margin-bottom:4px;">
      <button onclick="addCantiere()" style="width:100%;">+ Crea</button>
    </div>
    <div id="cantieri-list"></div>
  </div>
  
  <div class="main">
    <h1 style="color:#3b82f6;margin-bottom:12px;">Oracolo Covolo V8</h1>
    <div class="chat" id="chat"></div>
    <div style="display:flex;gap:8px;">
      <input type="text" id="question" placeholder="Domanda..." style="flex:1;">
      <button onclick="ask()" style="width:100px;">Invia</button>
    </div>
  </div>
</div>

<div id="login" class="login-box">
  <div class="login-title">Oracolo Covolo</div>
  <input type="text" id="user" placeholder="Username" value="superadmin">
  <input type="password" id="pwd" placeholder="Password" value="ZANNA1959?">
  <button onclick="doLogin()" style="width:100%;margin-top:12px;">Accedi</button>
  <div id="err" style="color:#ef4444;font-size:11px;margin-top:8px;"></div>
</div>

<script>
let BRANDS = [], currentCantiere = null, currentBrand = '';

function doLogin() {
  const user = document.getElementById('user').value;
  const pwd = document.getElementById('pwd').value;
  fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:user, password:pwd})})
    .then(r => r.json())
    .then(d => {
      if (d.ok) {
        document.getElementById('login').style.display = 'none';
        document.getElementById('app').style.display = 'flex';
        document.getElementById('user-label').textContent = d.nome;
        loadBrands();
        loadCantieri();
      } else {
        document.getElementById('err').textContent = d.error || 'Errore login';
      }
    });
}

function doLogout() {
  fetch('/api/logout', {method:'POST'}).then(() => {
    document.getElementById('app').style.display = 'none';
    document.getElementById('login').style.display = 'block';
    document.getElementById('user').value = 'superadmin';
    document.getElementById('pwd').value = 'ZANNA1959?';
  });
}

function loadBrands() {
  fetch('/api/get-brands').then(r => r.json()).then(d => {
    BRANDS = d.brands || [];
    const sel = document.getElementById('brand-select');
    sel.innerHTML = '<option value="">-- Seleziona brand --</option>' + BRANDS.map(b => '<option value="' + b + '">' + b + '</option>').join('');
  });
}

function onBrandChange() {
  currentBrand = document.getElementById('brand-select').value;
  if (currentBrand) {
    fetch('/api/listino/' + encodeURIComponent(currentBrand)).then(r => r.json()).then(d => {
      if (d.ok) {
        const chat = document.getElementById('chat');
        chat.innerHTML = '<div class="message"><strong>Listino ' + currentBrand + ':</strong> ' + d.prodotti.length + ' prodotti</div>';
        const html = '<div class="grid">' + d.prodotti.slice(0, 12).map(p =>
          '<div class="prod-card" onclick="addToCart(\'' + currentBrand + '\',\'' + p.codice.replace(/'/g,"") + '\')">' +
          '<div class="prod-name">' + (p.nome || p.codice) + '</div>' +
          '<div style="font-size:9px;color:#9ca3af;">' + (p.categoria||'') + '</div>' +
          '<div class="prod-price">€' + parseFloat(p.prezzo||0).toFixed(0) + '</div>' +
          '</div>'
        ).join('') + '</div>';
        chat.innerHTML += html;
      }
    });
  }
}

function loadCantieri() {
  fetch('/api/cantieri').then(r => r.json()).then(d => {
    const list = document.getElementById('cantieri-list');
    list.innerHTML = (d.cantieri || []).map(c =>
      '<div class="cantiere-card" onclick="openCantiere(' + c.id + ',\'' + c.nome.replace(/'/g,"") + '\')">' +
      c.nome + ' <span style="font-size:9px;color:#6b7280;">(' + c.stato + ')</span></div>'
    ).join('');
  });
}

function addCantiere() {
  const nome = document.getElementById('new-cant').value.trim();
  if (!nome) return;
  fetch('/api/cantieri', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({nome})})
    .then(r => r.json()).then(d => { if (d.ok) { document.getElementById('new-cant').value = ''; loadCantieri(); } });
}

function openCantiere(id, nome) {
  currentCantiere = id;
  fetch('/api/cantieri/' + id + '/modalita').then(r => r.json()).then(d => {
    const chat = document.getElementById('chat');
    chat.innerHTML = '<div class="message"><strong>📍 ' + nome + '</strong><br>Modalita: ' + d.modalita + '</div>';
    document.getElementById('question').placeholder = 'Aggiungi riga al cantiere...';
  });
}

function addToCart(brand, codice) {
  if (!currentCantiere) { alert('Apri un cantiere'); return; }
  fetch('/api/cantieri/' + currentCantiere + '/righe', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({brand, categoria:'', descrizione:codice, importo:0})
  }).then(r => r.json()).then(d => {
    if (d.ok) {
      const chat = document.getElementById('chat');
      chat.innerHTML += '<div class="message">✓ ' + codice + ' aggiunto</div>';
    }
  });
}

function ask() {
  const q = document.getElementById('question').value;
  if (!q || !currentCantiere) return;
  const chat = document.getElementById('chat');
  chat.innerHTML += '<div class="message"><strong>Tu:</strong> ' + q + '</div>';
  document.getElementById('question').value = '';
}

fetch('/api/me').then(r => r.json()).then(d => {
  if (d.logged) {
    document.getElementById('login').style.display = 'none';
    document.getElementById('app').style.display = 'flex';
    document.getElementById('user-label').textContent = d.user.nome;
    loadBrands();
    loadCantieri();
  }
});
</script>
</body>
</html>''')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
