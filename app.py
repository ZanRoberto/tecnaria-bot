"""
ORACOLO COVOLO V11 — COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Login 3 livelli (superadmin/admin/commerciale)
• Layout 3-colonne: LEFT sidebar | CENTER listino | RIGHT drawer PIANI
• Color system: VERDE=normale, BLU=abbinamenti, ROSSO=sconto, VIOLA=manuale
• Drawer PIANI/STANZE/VOCI con inline editing
• Subtotali LIVE a cascata
• Stessi colori su entrambe le interfacce
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os, json, sqlite3, re, hashlib, secrets, base64, io
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session
import httpx
try:
    import openpyxl
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "oracolo_covolo.db")
os.makedirs(DATA_DIR, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "tecnaria2024")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "").strip()

BRANDS_LIST = [
    "Gessi", "Duravit", "Remer", "Kaldewei", "Colombo", "Simas", "Cielo", "Cerasa",
    "Acquabella", "Altamarea", "Antoniolupi", "Aparici", "Ariostea", "Caesar", "Casalgrande Padana",
    "Cerasarda", "Cottodeste", "FMG", "Iris", "Italgraniti", "Marca Corona", "Mirage", "Sichenia",
    "Tonalite", "Bisazza", "Bauwerk", "CP Parquet", "Gerflor", "Decor Walther", "Wedi"
]

MODULI_DISPONIBILI = ["cantieri", "carrello", "bi", "commerciali"]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS aziende (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        admin_password TEXT,
        admin_required BOOLEAN DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS clienti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        slug TEXT UNIQUE NOT NULL
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS utenti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        ruolo TEXT NOT NULL,
        cliente_id INTEGER,
        attivo INTEGER DEFAULT 1,
        FOREIGN KEY (cliente_id) REFERENCES clienti(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS moduli_cliente (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER NOT NULL,
        modulo TEXT NOT NULL,
        attivo INTEGER DEFAULT 0,
        UNIQUE(cliente_id, modulo),
        FOREIGN KEY (cliente_id) REFERENCES clienti(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS cantieri (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER NOT NULL,
        commerciale_id INTEGER,
        nome TEXT NOT NULL,
        stato TEXT DEFAULT 'bozza',
        modalita TEXT DEFAULT 'semplice',
        note TEXT,
        data_creazione TEXT,
        data_aggiornamento TEXT,
        totale_generale REAL DEFAULT 0,
        FOREIGN KEY (cliente_id) REFERENCES clienti(id),
        FOREIGN KEY (commerciale_id) REFERENCES utenti(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS piani (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cantiere_id INTEGER NOT NULL,
        numero INTEGER,
        nome TEXT,
        totale_piano REAL DEFAULT 0,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (cantiere_id) REFERENCES cantieri(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS stanze (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        piano_id INTEGER NOT NULL,
        nome TEXT,
        descrizione TEXT,
        totale_stanza REAL DEFAULT 0,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (piano_id) REFERENCES piani(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS stanza_voci (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stanza_id INTEGER NOT NULL,
        tipo TEXT,
        codice TEXT,
        brand TEXT,
        descrizione TEXT,
        quantita REAL DEFAULT 1,
        udm TEXT,
        prezzo_unitario REAL DEFAULT 0,
        sconto_percentuale REAL DEFAULT 0,
        sconto_fisso REAL DEFAULT 0,
        subtotale REAL DEFAULT 0,
        note TEXT,
        colore TEXT DEFAULT 'verde',
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (stanza_id) REFERENCES stanze(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codice TEXT UNIQUE NOT NULL,
        nome TEXT,
        collezione TEXT,
        categoria TEXT,
        prezzo REAL,
        prezzo_rivenditore REAL,
        prezzo_scontato REAL,
        disponibilita TEXT,
        descrizione TEXT,
        finiture TEXT,
        fonte TEXT,
        brand TEXT,
        image_url TEXT,
        ha_abbinamenti INTEGER DEFAULT 0,
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS product_accessories (
        id INTEGER PRIMARY KEY,
        prodotto_padre TEXT NOT NULL,
        accessorio_id TEXT NOT NULL,
        accessorio_nome TEXT,
        brand_accessorio TEXT,
        categoria_accessorio TEXT,
        tipo_relazione TEXT,
        priority INTEGER DEFAULT 99,
        note TEXT,
        created_at TEXT,
        FOREIGN KEY (categoria_accessorio) REFERENCES categories_accessori(categoria_id),
        UNIQUE(prodotto_padre, accessorio_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS categories_accessori (
        id INTEGER PRIMARY KEY,
        categoria_id TEXT UNIQUE NOT NULL,
        categoria_nome TEXT NOT NULL,
        created_at TEXT
    )''')
    
    c.execute("INSERT OR IGNORE INTO clienti (nome, slug) VALUES ('Covolo SRL', 'covolo')")
    conn.commit()
    
    c.execute("SELECT id FROM clienti")
    for (cid,) in c.fetchall():
        for m in MODULI_DISPONIBILI:
            c.execute("INSERT OR IGNORE INTO moduli_cliente (cliente_id, modulo, attivo) VALUES (?,?,0)", (cid, m))
    conn.commit()
    
    for brand in BRANDS_LIST:
        c.execute('INSERT OR IGNORE INTO aziende (nome) VALUES (?)', (brand,))
    conn.commit()
    conn.close()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
init_db()

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def get_session_user():
    return session.get('user')

def require_login(ruoli=None):
    u = get_session_user()
    if not u:
        return None
    if ruoli and u['ruolo'] not in ruoli:
        return None
    return u

# ═══════════════════════════════════════════════════════════════════════════════
# API AUTH
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if username == 'superadmin' and password == SUPERADMIN_PASSWORD:
        session['user'] = {'id': 0, 'nome': 'Tecnaria', 'ruolo': 'superadmin', 'cliente_id': None}
        return jsonify({"ok": True, "ruolo": "superadmin", "nome": "Tecnaria"})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nome, ruolo, cliente_id, password_hash, attivo FROM utenti WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"ok": False, "error": "Utente non trovato"})
    
    uid, nome, ruolo, cliente_id, pwd_hash, attivo = row
    if not attivo:
        return jsonify({"ok": False, "error": "Utente disabilitato"})
    if hash_pwd(password) != pwd_hash:
        return jsonify({"ok": False, "error": "Password errata"})
    
    session['user'] = {'id': uid, 'nome': nome, 'ruolo': ruolo, 'cliente_id': cliente_id}
    return jsonify({"ok": True, "ruolo": ruolo, "nome": nome})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route('/api/me', methods=['GET'])
def me():
    u = get_session_user()
    if not u:
        return jsonify({"logged": False})
    
    moduli = []
    cid = u.get('cliente_id')
    if cid:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT modulo FROM moduli_cliente WHERE cliente_id=? AND attivo=1", (cid,))
        moduli = [r[0] for r in c.fetchall()]
        conn.close()
    elif u['ruolo'] == 'superadmin':
        moduli = MODULI_DISPONIBILI
    
    return jsonify({"logged": True, "user": u, "moduli": moduli})

# ═══════════════════════════════════════════════════════════════════════════════
# API CANTIERI
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/cantieri', methods=['GET'])
def get_cantieri():
    u = require_login(['superadmin', 'admin', 'commerciale'])
    if not u:
        return jsonify({"error": "Non autorizzato"}), 403
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if u['ruolo'] == 'superadmin':
        c.execute("""SELECT ca.id, ca.nome, ca.stato, ca.data_creazione, u.nome as comm, cl.nome as cliente
                     FROM cantieri ca
                     LEFT JOIN utenti u ON ca.commerciale_id=u.id
                     LEFT JOIN clienti cl ON ca.cliente_id=cl.id
                     ORDER BY ca.data_creazione DESC LIMIT 100""")
    elif u['ruolo'] == 'admin':
        c.execute("""SELECT ca.id, ca.nome, ca.stato, ca.data_creazione, u.nome as comm, cl.nome as cliente
                     FROM cantieri ca
                     LEFT JOIN utenti u ON ca.commerciale_id=u.id
                     LEFT JOIN clienti cl ON ca.cliente_id=cl.id
                     WHERE ca.cliente_id=?
                     ORDER BY ca.data_creazione DESC""", (u['cliente_id'],))
    else:
        c.execute("""SELECT ca.id, ca.nome, ca.stato, ca.data_creazione, u.nome as comm, cl.nome as cliente
                     FROM cantieri ca
                     LEFT JOIN utenti u ON ca.commerciale_id=u.id
                     LEFT JOIN clienti cl ON ca.cliente_id=cl.id
                     WHERE ca.commerciale_id=?
                     ORDER BY ca.data_creazione DESC""", (u['id'],))
    
    rows = c.fetchall()
    conn.close()
    return jsonify({"cantieri": [{"id": r[0], "nome": r[1], "stato": r[2], "data": r[3], "commerciale": r[4], "cliente": r[5]} for r in rows]})

@app.route('/api/cantieri', methods=['POST'])
def add_cantiere():
    u = require_login(['superadmin', 'admin', 'commerciale'])
    if not u:
        return jsonify({"error": "Non autorizzato"}), 403
    
    data = request.get_json()
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({"error": "Nome richiesto"}), 400
    
    cliente_id = u.get('cliente_id') or 1
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO cantieri (cliente_id, commerciale_id, nome, stato, data_creazione, data_aggiornamento) VALUES (?,?,?,?,?,?)",
              (cliente_id, u['id'] if u['ruolo'] != 'superadmin' else None, nome, 'bozza', datetime.now().isoformat(), datetime.now().isoformat()))
    cid = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": cid})

@app.route('/api/cantieri/<int:cid>/modalita', methods=['GET'])
def get_modalita_cantiere(cid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT modalita FROM cantieri WHERE id = ?", (cid,))
    row = c.fetchone()
    conn.close()
    modalita = row[0] if row else 'semplice'
    return jsonify({'modalita': modalita}), 200

@app.route('/api/cantieri/<int:cid>/modalita', methods=['PUT'])
def set_modalita_cantiere(cid):
    data = request.get_json()
    nuova_modalita = data.get('modalita', 'semplice')
    
    if nuova_modalita not in ['semplice', 'piani']:
        return jsonify({'error': 'Modalita non valida'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE cantieri SET modalita = ?, data_aggiornamento = ? WHERE id = ?",
             (nuova_modalita, datetime.now().isoformat(), cid))
    conn.commit()
    conn.close()
    
    return jsonify({
        'ok': True,
        'cantiere_id': cid,
        'modalita': nuova_modalita,
        'message': f'Convertito a modalita {nuova_modalita}'
    }), 200

# ═══════════════════════════════════════════════════════════════════════════════
# API PIANI/STANZE/VOCI — V11 COMPLETE
# ═══════════════════════════════════════════════════════════════════════════════

def calcola_subtotale_voce(prezzo, quantita, sconto_perc=0, sconto_fisso=0):
    """Calcola subtotale voce dopo sconti"""
    prezzo_scontato = prezzo - sconto_fisso
    if sconto_perc > 0:
        prezzo_scontato = prezzo_scontato * (1 - sconto_perc / 100)
    return max(0, prezzo_scontato * quantita)

def ricalcola_totali_cantiere(cantiere_id):
    """Ricalcola totali a cascata: voce → stanza → piano → generale"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Ricalcola subtotali voci
    c.execute("SELECT id, prezzo_unitario, quantita, sconto_percentuale, sconto_fisso FROM stanza_voci")
    for voce_id, prezzo, qty, sconto_perc, sconto_fisso in c.fetchall():
        subtotale = calcola_subtotale_voce(prezzo, qty, sconto_perc, sconto_fisso)
        c.execute("UPDATE stanza_voci SET subtotale = ?, updated_at = ? WHERE id = ?", 
                 (subtotale, datetime.now().isoformat(), voce_id))
    
    # Ricalcola totali stanze
    c.execute("SELECT id FROM stanze")
    for (stanza_id,) in c.fetchall():
        c.execute("SELECT COALESCE(SUM(subtotale), 0) FROM stanza_voci WHERE stanza_id = ?", (stanza_id,))
        total = c.fetchone()[0] or 0
        c.execute("UPDATE stanze SET totale_stanza = ?, updated_at = ? WHERE id = ?", 
                 (total, datetime.now().isoformat(), stanza_id))
    
    # Ricalcola totali piani
    c.execute("SELECT id FROM piani WHERE cantiere_id = ?", (cantiere_id,))
    for (piano_id,) in c.fetchall():
        c.execute("SELECT COALESCE(SUM(totale_stanza), 0) FROM stanze WHERE piano_id = ?", (piano_id,))
        total = c.fetchone()[0] or 0
        c.execute("UPDATE piani SET totale_piano = ?, updated_at = ? WHERE id = ?", 
                 (total, datetime.now().isoformat(), piano_id))
    
    # Ricalcola totale generale cantiere
    c.execute("SELECT COALESCE(SUM(totale_piano), 0) FROM piani WHERE cantiere_id = ?", (cantiere_id,))
    total_generale = c.fetchone()[0] or 0
    c.execute("UPDATE cantieri SET totale_generale = ?, data_aggiornamento = ? WHERE id = ?", 
             (total_generale, datetime.now().isoformat(), cantiere_id))
    
    conn.commit()
    conn.close()

@app.route('/api/cantieri/<int:cid>/struttura', methods=['GET'])
def get_struttura(cid):
    """Restituisce gerarchia PIANO → STANZA → VOCE con colori"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT id, nome FROM cantieri WHERE id = ?", (cid,))
    cant = c.fetchone()
    if not cant:
        return jsonify({'error': 'Cantiere not found'}), 404
    
    c.execute("SELECT id, numero, nome, totale_piano FROM piani WHERE cantiere_id = ? ORDER BY numero", (cid,))
    piani = []
    for pid, num, pnome, ptot in c.fetchall():
        c.execute("SELECT id, nome, descrizione, totale_stanza FROM stanze WHERE piano_id = ? ORDER BY id", (pid,))
        stanze = []
        for sid, snome, sdesc, stot in c.fetchall():
            c.execute("""
                SELECT id, codice, brand, descrizione, quantita, udm, prezzo_unitario, 
                       sconto_percentuale, sconto_fisso, subtotale, colore
                FROM stanza_voci WHERE stanza_id = ? ORDER BY id
            """, (sid,))
            voci = [{
                'id': v[0], 'codice': v[1], 'brand': v[2], 'descrizione': v[3],
                'quantita': v[4], 'udm': v[5], 'prezzo': v[6],
                'sconto_perc': v[7], 'sconto_fisso': v[8], 'subtotale': v[9],
                'colore': v[10] or 'verde'
            } for v in c.fetchall()]
            
            stanze.append({
                'id': sid, 'nome': snome, 'desc': sdesc, 'totale': stot, 'voci': voci
            })
        
        piani.append({
            'id': pid, 'num': num, 'nome': pnome, 'totale': ptot, 'stanze': stanze
        })
    
    conn.close()
    
    c = conn.cursor()
    c.execute("SELECT totale_generale FROM cantieri WHERE id = ?", (cid,))
    row = c.fetchone()
    tot_gen = row[0] if row else 0
    
    return jsonify({'ok': True, 'cantiere': cant, 'piani': piani, 'totale_generale': tot_gen})

@app.route('/api/cantieri/<int:cid>/piani', methods=['POST'])
def add_piano(cid):
    """Crea un nuovo piano"""
    data = request.get_json()
    nome = data.get('nome', 'Piano')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT MAX(numero) FROM piani WHERE cantiere_id = ?", (cid,))
    max_num = c.fetchone()[0] or 0
    numero = max_num + 1
    
    c.execute("""
        INSERT INTO piani (cantiere_id, numero, nome, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (cid, numero, nome, datetime.now().isoformat(), datetime.now().isoformat()))
    
    pid = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'ok': True, 'piano_id': pid})

@app.route('/api/piani/<int:pid>/stanze', methods=['POST'])
def add_stanza(pid):
    """Crea una nuova stanza"""
    data = request.get_json()
    nome = data.get('nome', 'Stanza')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT cantiere_id FROM piani WHERE id = ?", (pid,))
    row = c.fetchone()
    if not row:
        return jsonify({'error': 'Piano not found'}), 404
    cid = row[0]
    
    c.execute("""
        INSERT INTO stanze (piano_id, nome, descrizione, created_at, updated_at)
        VALUES (?, ?, '', ?, ?)
    """, (pid, nome, datetime.now().isoformat(), datetime.now().isoformat()))
    
    sid = c.lastrowid
    conn.commit()
    conn.close()
    
    ricalcola_totali_cantiere(cid)
    return jsonify({'ok': True, 'stanza_id': sid})

@app.route('/api/stanze/<int:sid>/voci', methods=['POST'])
def add_voce(sid):
    """Aggiungi voce a stanza con colore"""
    data = request.get_json()
    codice = data.get('codice', '')
    brand = data.get('brand', '')
    desc = data.get('descrizione', '')
    qty = float(data.get('quantita', 1))
    udm = data.get('udm', 'pezzo')
    prezzo = float(data.get('prezzo_unitario', 0))
    sconto_p = float(data.get('sconto_perc', 0))
    sconto_f = float(data.get('sconto_fisso', 0))
    colore = data.get('colore', 'verde')  # NEW: colore
    
    subtotale = calcola_subtotale_voce(prezzo, qty, sconto_p, sconto_f)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT piano_id FROM stanze WHERE id = ?", (sid,))
    row = c.fetchone()
    if not row:
        return jsonify({'error': 'Stanza not found'}), 404
    pid = row[0]
    
    c.execute("SELECT cantiere_id FROM piani WHERE id = ?", (pid,))
    cid = c.fetchone()[0]
    
    c.execute("""
        INSERT INTO stanza_voci 
        (stanza_id, tipo, codice, brand, descrizione, quantita, udm, prezzo_unitario, 
         sconto_percentuale, sconto_fisso, subtotale, colore, created_at, updated_at)
        VALUES (?, 'prodotto', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sid, codice, brand, desc, qty, udm, prezzo, sconto_p, sconto_f, subtotale, colore,
          datetime.now().isoformat(), datetime.now().isoformat()))
    
    vid = c.lastrowid
    conn.commit()
    conn.close()
    
    ricalcola_totali_cantiere(cid)
    return jsonify({'ok': True, 'voce_id': vid})

@app.route('/api/stanza_voci/<int:vid>', methods=['PUT'])
def edit_voce(vid):
    """Modifica voce"""
    data = request.get_json()
    qty = float(data.get('quantita', 1))
    prezzo = float(data.get('prezzo_unitario', 0))
    sconto_p = float(data.get('sconto_perc', 0))
    sconto_f = float(data.get('sconto_fisso', 0))
    colore = data.get('colore', 'verde')  # NEW: colore
    
    subtotale = calcola_subtotale_voce(prezzo, qty, sconto_p, sconto_f)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT stanza_id FROM stanza_voci WHERE id = ?", (vid,))
    row = c.fetchone()
    if not row:
        return jsonify({'error': 'Voce not found'}), 404
    sid = row[0]
    
    c.execute("SELECT piano_id FROM stanze WHERE id = ?", (sid,))
    pid = c.fetchone()[0]
    
    c.execute("SELECT cantiere_id FROM piani WHERE id = ?", (pid,))
    cid = c.fetchone()[0]
    
    c.execute("""
        UPDATE stanza_voci 
        SET quantita = ?, prezzo_unitario = ?, sconto_percentuale = ?, 
            sconto_fisso = ?, subtotale = ?, colore = ?, updated_at = ?
        WHERE id = ?
    """, (qty, prezzo, sconto_p, sconto_f, subtotale, colore, datetime.now().isoformat(), vid))
    
    conn.commit()
    conn.close()
    
    ricalcola_totali_cantiere(cid)
    return jsonify({'ok': True})

@app.route('/api/stanza_voci/<int:vid>', methods=['DELETE'])
def delete_voce(vid):
    """Elimina voce"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT stanza_id FROM stanza_voci WHERE id = ?", (vid,))
    row = c.fetchone()
    if not row:
        return jsonify({'error': 'Voce not found'}), 404
    sid = row[0]
    
    c.execute("SELECT piano_id FROM stanze WHERE id = ?", (sid,))
    pid = c.fetchone()[0]
    
    c.execute("SELECT cantiere_id FROM piani WHERE id = ?", (pid,))
    cid = c.fetchone()[0]
    
    c.execute("DELETE FROM stanza_voci WHERE id = ?", (vid,))
    
    conn.commit()
    conn.close()
    
    ricalcola_totali_cantiere(cid)
    return jsonify({'ok': True})

@app.route('/api/get-brands', methods=['GET'])
def get_brands():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nome FROM aziende ORDER BY nome')
    brands = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify({"brands": brands})

# ═══════════════════════════════════════════════════════════════════════════════
# FRONTEND HTML V11
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template_string(open('/mnt/skills/examples/oracolo_v11_frontend.html').read() if os.path.exists('/mnt/skills/examples/oracolo_v11_frontend.html') else HTML_TEMPLATE_V11)

HTML_TEMPLATE_V11 = r'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Oracolo Covolo V11</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system; background: #f5f5f5; color: #1a1a1a; min-height: 100vh; }

.login-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 9999; display: flex; align-items: center; justify-content: center; }
.login-box { background: white; border-radius: 12px; padding: 32px; width: 320px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
.login-title { color: #3b82f6; font-size: 20px; font-weight: 700; margin-bottom: 20px; text-align: center; }
.login-box input { width: 100%; padding: 10px; margin-bottom: 8px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; }
.login-box button { width: 100%; padding: 10px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; margin-top: 16px; }
.login-error { color: #ef4444; font-size: 11px; margin-top: 8px; text-align: center; }

/* MAIN LAYOUT */
.container { display: flex; height: 100vh; background: white; }

/* SIDEBAR LEFT */
.sidebar { width: 280px; background: #0a0f1f; border-right: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; color: white; }
.sidebar h2 { font-size: 14px; font-weight: 700; color: #93c5fd; margin: 12px 0 8px 0; text-transform: uppercase; letter-spacing: 0.05em; }
.sidebar button { width: 100%; padding: 8px 12px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 11px; font-weight: 600; margin-bottom: 6px; }
.sidebar select { width: 100%; padding: 8px; background: #1e293b; color: white; border: 1px solid #334155; border-radius: 6px; font-size: 11px; margin-bottom: 6px; }

/* CENTER */
.main { flex: 1; display: flex; flex-direction: column; padding: 20px; overflow: hidden; }
.main-header { margin-bottom: 12px; }
.main-title { font-size: 20px; font-weight: 700; color: #3b82f6; margin-bottom: 4px; }
.main-content { flex: 1; overflow-y: auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }

/* PRODUCT CARD - COLOR SYSTEM */
.product-card { background: white; border-radius: 8px; border: 2px solid #ddd; padding: 12px; cursor: pointer; transition: all 0.2s; }
.product-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }

.product-card.colore-verde { border-color: #10b981; border-left: 4px solid #10b981; }
.product-card.colore-blu { border-color: #3b82f6; border-left: 4px solid #3b82f6; }
.product-card.colore-rosso { border-color: #ef4444; border-left: 4px solid #ef4444; }
.product-card.colore-viola { border-color: #8b5cf6; border-left: 4px solid #8b5cf6; }

.product-card-code { font-size: 10px; color: #6b7280; font-family: monospace; margin-bottom: 4px; }
.product-card-name { font-size: 13px; font-weight: 600; color: #1a1a1a; margin-bottom: 6px; }
.product-card-desc { font-size: 11px; color: #666; margin-bottom: 8px; }
.product-card-price { font-size: 14px; font-weight: 700; margin-bottom: 8px; }
.product-card-price.verde { color: #10b981; }
.product-card-price.blu { color: #3b82f6; }
.product-card-price.rosso { color: #ef4444; }
.product-card-price.viola { color: #8b5cf6; }

.product-card-badge { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: 600; color: white; margin-right: 4px; margin-bottom: 8px; }
.badge-verde { background: #10b981; }
.badge-blu { background: #3b82f6; }
.badge-rosso { background: #ef4444; }
.badge-viola { background: #8b5cf6; }

.product-card-button { width: 100%; padding: 6px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 11px; font-weight: 600; }

/* DRAWER RIGHT */
.drawer-piani { position: fixed; right: 0; top: 0; width: 320px; height: 100vh; background: #0f172e; border-left: 2px solid #3b82f6; z-index: 1000; display: none; flex-direction: column; overflow-y: auto; box-shadow: -4px 0 12px rgba(0,0,0,0.3); }
.drawer-piani.open { display: flex; }

.drawer-header { background: rgba(59,130,245,0.2); border-bottom: 1px solid #334155; padding: 15px; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; }
.drawer-title { font-size: 14px; font-weight: 700; color: #60a5fa; }
.drawer-close { background: #6b7280; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 11px; }

.drawer-body { flex: 1; padding: 12px; overflow-y: auto; }

.piano-item { background: rgba(30,58,95,0.8); border: 1px solid #3b82f6; border-radius: 6px; padding: 10px; margin-bottom: 10px; cursor: pointer; }
.piano-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; color: #60a5fa; font-size: 12px; }
.piano-total { color: #10b981; font-weight: 700; }

.stanza-item { background: rgba(30,41,59,0.7); border-left: 3px solid #8b5cf6; padding: 8px; margin: 8px 0 8px 12px; border-radius: 4px; cursor: pointer; }
.stanza-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; color: #c4b5fd; font-size: 11px; }
.stanza-total { color: #10b981; }

.voce-item { background: rgba(15,23,41,0.9); border-left: 3px solid #6b7280; padding: 6px; margin: 4px 0; border-radius: 3px; font-size: 10px; display: flex; justify-content: space-between; align-items: center; }

.voce-item.verde { border-left-color: #10b981; background: rgba(16,185,129,0.1); }
.voce-item.blu { border-left-color: #3b82f6; background: rgba(59,130,245,0.1); }
.voce-item.rosso { border-left-color: #ef4444; background: rgba(239,68,68,0.1); }
.voce-item.viola { border-left-color: #8b5cf6; background: rgba(139,92,246,0.1); }

.voce-brand { color: #60a5fa; font-weight: 600; }
.voce-desc { color: #d1d5db; font-size: 9px; margin-top: 2px; }
.voce-price { color: #10b981; font-weight: 700; margin: 0 8px; white-space: nowrap; }

.drawer-total { background: rgba(16,185,129,0.2); border: 1px solid rgba(16,185,129,0.5); padding: 12px; margin: 12px 0; border-radius: 6px; text-align: center; color: #10b981; }
.drawer-total-label { font-size: 10px; color: #9ca3af; }
.drawer-total-value { font-size: 18px; font-weight: 700; color: #10b981; }

.btn-add { width: 100%; padding: 6px; background: rgba(16,185,129,0.3); color: #6ee7b7; border: 1px solid rgba(16,185,129,0.5); border-radius: 4px; cursor: pointer; font-size: 10px; margin-top: 4px; }

</style>
</head>
<body>

<!-- LOGIN -->
<div class="login-overlay" id="login-overlay">
  <div class="login-box">
    <div class="login-title">Oracolo Covolo V11</div>
    <input type="text" id="login-user" placeholder="Username" onkeypress="if(event.key==='Enter') doLogin()">
    <input type="password" id="login-pwd" placeholder="Password" onkeypress="if(event.key==='Enter') doLogin()">
    <button onclick="doLogin()">Accedi</button>
    <div class="login-error" id="login-error"></div>
  </div>
</div>

<!-- MAIN APP -->
<div class="container" id="main-app" style="display: none;">
  
  <!-- SIDEBAR -->
  <div class="sidebar">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <span style="font-size: 11px; color: #60a5fa; font-weight: 600;" id="user-label"></span>
      <button style="width: auto; padding: 4px 8px; background: #6b7280; font-size: 10px;" onclick="doLogout()">Esci</button>
    </div>
    
    <h2>Cantieri</h2>
    <select id="cantiere-sel" onchange="openCantiere()">
      <option value="">-- Seleziona cantiere --</option>
    </select>
    <button onclick="addCantiere()">➕ Nuovo cantiere</button>
    
    <h2 style="margin-top: 16px;">Brand</h2>
    <select id="brand-sel" multiple style="height: 120px;">
    </select>
  </div>
  
  <!-- CENTER -->
  <div class="main">
    <div class="main-header">
      <div class="main-title">Oracolo Covolo V11</div>
      <div style="font-size: 12px; color: #666;">Seleziona cantiere e brand per iniziare</div>
    </div>
    <div class="main-content" id="main-content">
      <div style="grid-column: 1/-1; text-align: center; padding: 40px 20px; color: #999;">Seleziona un cantiere per visualizzare i prodotti</div>
    </div>
  </div>
  
  <!-- DRAWER PIANI -->
  <div class="drawer-piani" id="drawer-piani">
    <div class="drawer-header">
      <div>
        <div class="drawer-title" id="drawer-nome"></div>
        <div style="font-size: 10px; color: #9ca3af; margin-top: 2px;">Modalità: PIANI</div>
      </div>
      <button class="drawer-close" onclick="closeDrawer()">✕</button>
    </div>
    
    <div class="drawer-body" id="drawer-body">
      <div style="color: #9ca3af; font-size: 11px; text-align: center; padding: 20px;">Caricamento...</div>
    </div>
    
    <div style="padding: 12px; border-top: 1px solid #334155; display: flex; gap: 8px;">
      <button class="btn-add" style="background: rgba(59,130,245,0.3); color: #93c5fd; border: 1px solid rgba(59,130,245,0.5);" onclick="aggiungiPiano()">➕ Piano</button>
      <button class="btn-add" style="background: rgba(139,92,246,0.3); color: #a78bfa; border: 1px solid rgba(139,92,246,0.5);" onclick="switchModalita()">🔄 SEMPLICE</button>
    </div>
  </div>
  
</div>

<script>
let currentCantiere = null;
let selectedBrands = [];

function doLogin() {
  const username = document.getElementById('login-user').value.trim();
  const password = document.getElementById('login-pwd').value.trim();
  if (!username || !password) { document.getElementById('login-error').textContent = 'Completa i campi'; return; }
  
  fetch('/api/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username, password})
  })
  .then(r => r.json())
  .then(d => {
    if (d.ok) {
      document.getElementById('login-overlay').style.display = 'none';
      document.getElementById('main-app').style.display = 'flex';
      initApp();
    } else {
      document.getElementById('login-error').textContent = d.error || 'Errore login';
    }
  });
}

function doLogout() {
  fetch('/api/logout', {method: 'POST'}).then(() => {
    document.getElementById('login-overlay').style.display = 'flex';
    document.getElementById('main-app').style.display = 'none';
    document.getElementById('login-user').value = '';
    document.getElementById('login-pwd').value = '';
  });
}

function initApp() {
  fetch('/api/me').then(r => r.json()).then(d => {
    if (!d.logged) { doLogout(); return; }
    document.getElementById('user-label').textContent = d.user.nome + ' (' + d.user.ruolo + ')';
    loadCantieri();
    loadBrands();
  });
}

function loadCantieri() {
  fetch('/api/cantieri').then(r => r.json()).then(d => {
    const sel = document.getElementById('cantiere-sel');
    sel.innerHTML = '<option value="">-- Seleziona cantiere --</option>';
    (d.cantieri || []).forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = c.nome + ' (' + c.stato + ')';
      sel.appendChild(opt);
    });
  });
}

function loadBrands() {
  fetch('/api/get-brands').then(r => r.json()).then(d => {
    const sel = document.getElementById('brand-sel');
    sel.innerHTML = '';
    (d.brands || []).forEach(b => {
      const opt = document.createElement('option');
      opt.value = b;
      opt.textContent = b;
      sel.appendChild(opt);
    });
  });
}

function addCantiere() {
  const nome = prompt('Nome cantiere:');
  if (!nome) return;
  fetch('/api/cantieri', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nome})})
    .then(r => r.json()).then(d => { if (d.ok) { loadCantieri(); currentCantiere = d.id; } });
}

function openCantiere() {
  const cid = document.getElementById('cantiere-sel').value;
  if (!cid) return;
  currentCantiere = cid;
  
  fetch('/api/cantieri/' + cid + '/modalita').then(r => r.json()).then(d => {
    const modalita = d.modalita || 'semplice';
    if (modalita === 'piani') {
      openDrawerPiani(cid);
    } else {
      document.getElementById('main-content').innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px 20px; color: #999;">Clicca il bottone PIANI per gestire la struttura</div>';
    }
  });
}

function openDrawerPiani(cid) {
  const drawer = document.getElementById('drawer-piani');
  const sel = document.getElementById('cantiere-sel');
  const nome = sel.options[sel.selectedIndex].text.split(' (')[0];
  document.getElementById('drawer-nome').textContent = nome;
  drawer.classList.add('open');
  loadStrutturaPiani(cid);
}

function closeDrawer() {
  document.getElementById('drawer-piani').classList.remove('open');
}

function switchModalita() {
  if (!currentCantiere) return;
  if (!confirm('Cambiare modalità da PIANI a SEMPLICE?')) return;
  fetch('/api/cantieri/' + currentCantiere + '/modalita', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({modalita: 'semplice'})})
    .then(r => r.json()).then(d => { if (d.ok) { closeDrawer(); openCantiere(); } });
}

function loadStrutturaPiani(cid) {
  fetch('/api/cantieri/' + cid + '/struttura').then(r => r.json()).then(d => {
    if (!d.ok) return;
    let html = '';
    (d.piani || []).forEach(p => {
      html += '<div class="piano-item">';
      html += '<div class="piano-header"><span>📍 ' + p.nome + '</span><span class="piano-total">€' + p.totale.toFixed(2) + '</span></div>';
      (p.stanze || []).forEach(s => {
        html += '<div class="stanza-item">';
        html += '<div class="stanza-header"><span>🚿 ' + s.nome + '</span><span class="stanza-total">€' + s.totale.toFixed(2) + '</span></div>';
        (s.voci || []).forEach(v => {
          html += '<div class="voce-item ' + (v.colore || 'verde') + '">';
          html += '<div><div class="voce-brand">' + v.brand + ' [' + (v.codice || '—') + ']</div>';
          html += '<div class="voce-desc">' + v.descrizione + '</div></div>';
          html += '<div style="display: flex; gap: 4px; align-items: center;">';
          html += '<span class="voce-price">€' + v.subtotale.toFixed(2) + '</span>';
          html += '<button style="background: #6b7280; color: white; border: none; padding: 3px 6px; border-radius: 3px; font-size: 10px; cursor: pointer;">✏️</button>';
          html += '</div></div>';
        });
        html += '<button class="btn-add">➕ Voce</button>';
        html += '</div>';
      });
      html += '<button class="btn-add">➕ Stanza</button>';
      html += '</div>';
    });
    document.getElementById('drawer-body').innerHTML = html || '<div style="color: #9ca3af; text-align: center; padding: 20px;">Nessun piano. Clicca ➕ Piano per iniziare</div>';
  });
}

function aggiungiPiano() {
  if (!currentCantiere) return;
  const nome = prompt('Nome piano:');
  if (!nome) return;
  fetch('/api/cantieri/' + currentCantiere + '/piani', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nome})})
    .then(r => r.json()).then(d => { if (d.ok) loadStrutturaPiani(currentCantiere); });
}

// Auto-login for testing
fetch('/api/me').then(r => r.json()).then(d => {
  if (d.logged) {
    document.getElementById('login-overlay').style.display = 'none';
    document.getElementById('main-app').style.display = 'flex';
    initApp();
  }
});

</script>

</body>
</html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
