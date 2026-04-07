"""
ORACOLO COVOLO - SISTEMA COMPLETO V2
+ Login 3 livelli: superadmin (Tecnaria) / admin cliente / commerciale
+ Moduli ON/OFF configurabili da superadmin per cliente
+ Pannello destra: Cantieri, Carrello, BI
+ Tutto il precedente invariato
"""
import os, json, sqlite3, re, hashlib, secrets
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session
import httpx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "oracolo_covolo.db")
os.makedirs(DATA_DIR, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "tecnaria2024").strip()

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

MODULI_DISPONIBILI = ["cantieri", "carrello", "bi", "commerciali"]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabelle esistenti
    c.execute('''CREATE TABLE IF NOT EXISTS aziende (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        admin_password TEXT,
        admin_required BOOLEAN DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT, content TEXT, azienda_id INTEGER,
        visibility TEXT DEFAULT 'public', access_code TEXT, upload_date TEXT,
        FOREIGN KEY (azienda_id) REFERENCES aziende(id)
    )''')
    # Tabelle nuove
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
        note TEXT,
        data_creazione TEXT,
        data_aggiornamento TEXT,
        FOREIGN KEY (cliente_id) REFERENCES clienti(id),
        FOREIGN KEY (commerciale_id) REFERENCES utenti(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cantiere_righe (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cantiere_id INTEGER NOT NULL,
        brand TEXT, categoria TEXT, descrizione TEXT, note TEXT,
        importo REAL DEFAULT 0,
        FOREIGN KEY (cantiere_id) REFERENCES cantieri(id)
    )''')
    # Cliente default Covolo
    c.execute("INSERT OR IGNORE INTO clienti (nome, slug) VALUES ('Covolo SRL', 'covolo')")
    conn.commit()
    # Inizializza moduli per clienti esistenti
    c.execute("SELECT id FROM clienti")
    for (cid,) in c.fetchall():
        for m in MODULI_DISPONIBILI:
            c.execute("INSERT OR IGNORE INTO moduli_cliente (cliente_id, modulo, attivo) VALUES (?,?,0)", (cid, m))
    conn.commit()
    # Brand default
    for brand in BRANDS_LIST:
        c.execute('INSERT OR IGNORE INTO aziende (nome) VALUES (?)', (brand,))
    conn.commit()
    conn.close()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
init_db()

# ---------------------------------------------------------------------------
# HELPERS AUTH
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# API AUTH
# ---------------------------------------------------------------------------

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    # Superadmin
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
    # Carica moduli attivi per il cliente
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

# ---------------------------------------------------------------------------
# API SUPERADMIN — gestione clienti e moduli
# ---------------------------------------------------------------------------

@app.route('/api/sa/clienti', methods=['GET'])
def sa_get_clienti():
    if not require_login(['superadmin']):
        return jsonify({"error": "Non autorizzato"}), 403
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nome, slug FROM clienti ORDER BY nome")
    clienti = [{"id": r[0], "nome": r[1], "slug": r[2]} for r in c.fetchall()]
    conn.close()
    return jsonify({"clienti": clienti})

@app.route('/api/sa/clienti', methods=['POST'])
def sa_add_cliente():
    if not require_login(['superadmin']):
        return jsonify({"error": "Non autorizzato"}), 403
    data = request.get_json()
    nome = data.get('nome', '').strip()
    slug = data.get('slug', '').strip().lower().replace(' ', '-')
    if not nome or not slug:
        return jsonify({"error": "Nome e slug richiesti"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO clienti (nome, slug) VALUES (?,?)", (nome, slug))
        cid = c.lastrowid
        for m in MODULI_DISPONIBILI:
            c.execute("INSERT OR IGNORE INTO moduli_cliente (cliente_id, modulo, attivo) VALUES (?,?,0)", (cid, m))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "id": cid})
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

@app.route('/api/sa/moduli/<int:cliente_id>', methods=['GET'])
def sa_get_moduli(cliente_id):
    if not require_login(['superadmin']):
        return jsonify({"error": "Non autorizzato"}), 403
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT modulo, attivo FROM moduli_cliente WHERE cliente_id=?", (cliente_id,))
    moduli = {r[0]: bool(r[1]) for r in c.fetchall()}
    conn.close()
    return jsonify({"moduli": moduli})

@app.route('/api/sa/moduli/<int:cliente_id>', methods=['POST'])
def sa_set_moduli(cliente_id):
    if not require_login(['superadmin']):
        return jsonify({"error": "Non autorizzato"}), 403
    data = request.get_json()
    modulo = data.get('modulo')
    attivo = 1 if data.get('attivo') else 0
    if modulo not in MODULI_DISPONIBILI:
        return jsonify({"error": "Modulo non valido"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO moduli_cliente (cliente_id, modulo, attivo) VALUES (?,?,?)", (cliente_id, modulo, attivo))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/sa/utenti', methods=['GET'])
def sa_get_utenti():
    if not require_login(['superadmin']):
        return jsonify({"error": "Non autorizzato"}), 403
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT u.id, u.nome, u.username, u.ruolo, u.attivo, cl.nome as cliente
                 FROM utenti u LEFT JOIN clienti cl ON u.cliente_id=cl.id ORDER BY u.nome""")
    utenti = [{"id": r[0], "nome": r[1], "username": r[2], "ruolo": r[3], "attivo": r[4], "cliente": r[5]} for r in c.fetchall()]
    conn.close()
    return jsonify({"utenti": utenti})

@app.route('/api/sa/utenti', methods=['POST'])
def sa_add_utente():
    if not require_login(['superadmin']):
        return jsonify({"error": "Non autorizzato"}), 403
    data = request.get_json()
    nome = data.get('nome', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    ruolo = data.get('ruolo', 'commerciale')
    cliente_id = data.get('cliente_id')
    if not nome or not username or not password:
        return jsonify({"error": "Dati incompleti"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO utenti (nome, username, password_hash, ruolo, cliente_id) VALUES (?,?,?,?,?)",
                  (nome, username, hash_pwd(password), ruolo, cliente_id))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

@app.route('/api/sa/utenti/<int:uid>', methods=['DELETE'])
def sa_delete_utente(uid):
    if not require_login(['superadmin']):
        return jsonify({"error": "Non autorizzato"}), 403
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE utenti SET attivo=0 WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# API CANTIERI
# ---------------------------------------------------------------------------

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

@app.route('/api/cantieri/<int:cid>', methods=['PUT'])
def update_cantiere(cid):
    u = require_login(['superadmin', 'admin', 'commerciale'])
    if not u:
        return jsonify({"error": "Non autorizzato"}), 403
    data = request.get_json()
    stato = data.get('stato')
    note = data.get('note')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if stato:
        c.execute("UPDATE cantieri SET stato=?, data_aggiornamento=? WHERE id=?", (stato, datetime.now().isoformat(), cid))
    if note is not None:
        c.execute("UPDATE cantieri SET note=?, data_aggiornamento=? WHERE id=?", (note, datetime.now().isoformat(), cid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/cantieri/<int:cid>/righe', methods=['GET'])
def get_righe(cid):
    u = require_login(['superadmin', 'admin', 'commerciale'])
    if not u:
        return jsonify({"error": "Non autorizzato"}), 403
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, brand, categoria, descrizione, note, importo FROM cantiere_righe WHERE cantiere_id=?", (cid,))
    righe = [{"id": r[0], "brand": r[1], "categoria": r[2], "descrizione": r[3], "note": r[4], "importo": r[5]} for r in c.fetchall()]
    conn.close()
    return jsonify({"righe": righe})

@app.route('/api/cantieri/<int:cid>/righe', methods=['POST'])
def add_riga(cid):
    u = require_login(['superadmin', 'admin', 'commerciale'])
    if not u:
        return jsonify({"error": "Non autorizzato"}), 403
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO cantiere_righe (cantiere_id, brand, categoria, descrizione, note, importo) VALUES (?,?,?,?,?,?)",
              (cid, data.get('brand',''), data.get('categoria',''), data.get('descrizione',''), data.get('note',''), data.get('importo',0)))
    rid = c.lastrowid
    c.execute("UPDATE cantieri SET data_aggiornamento=? WHERE id=?", (datetime.now().isoformat(), cid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": rid})

@app.route('/api/cantieri/righe/<int:rid>', methods=['DELETE'])
def delete_riga(rid):
    u = require_login(['superadmin', 'admin', 'commerciale'])
    if not u:
        return jsonify({"error": "Non autorizzato"}), 403
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM cantiere_righe WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/cantieri/<int:cid>', methods=['DELETE'])
def delete_cantiere(cid):
    u = require_login(['superadmin', 'admin'])
    if not u:
        return jsonify({"error": "Non autorizzato"}), 403
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM cantiere_righe WHERE cantiere_id=?", (cid,))
    c.execute("DELETE FROM cantieri WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# API BI
# ---------------------------------------------------------------------------

@app.route('/api/bi/stats', methods=['GET'])
def bi_stats():
    u = require_login(['superadmin', 'admin'])
    if not u:
        return jsonify({"error": "Non autorizzato"}), 403
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    filter_cid = "" if u['ruolo'] == 'superadmin' else f" AND ca.cliente_id={u['cliente_id']}"
    c.execute("SELECT stato, COUNT(*) FROM cantieri ca WHERE 1=1" + filter_cid + " GROUP BY stato")
    per_stato = {r[0]: r[1] for r in c.fetchall()}
    c.execute("SELECT COALESCE(SUM(cr.importo),0) FROM cantiere_righe cr JOIN cantieri ca ON cr.cantiere_id=ca.id WHERE ca.stato='vinta'" + filter_cid)
    valore_vinto = c.fetchone()[0] or 0
    c.execute("SELECT COALESCE(SUM(cr.importo),0) FROM cantiere_righe cr JOIN cantieri ca ON cr.cantiere_id=ca.id WHERE ca.stato='bozza' OR ca.stato='inviata'" + filter_cid)
    valore_aperto = c.fetchone()[0] or 0
    c.execute("""SELECT u.nome, COUNT(ca.id), COALESCE(SUM(cr.importo),0)
                 FROM cantieri ca
                 LEFT JOIN utenti u ON ca.commerciale_id=u.id
                 LEFT JOIN cantiere_righe cr ON cr.cantiere_id=ca.id
                 WHERE 1=1""" + filter_cid + " GROUP BY ca.commerciale_id")
    per_comm = [{"nome": r[0] or "N/D", "cantieri": r[1], "valore": round(r[2], 2)} for r in c.fetchall()]
    conn.close()
    return jsonify({"per_stato": per_stato, "valore_vinto": round(valore_vinto, 2), "valore_aperto": round(valore_aperto, 2), "per_commerciale": per_comm})

@app.route('/api/bi/cancella', methods=['POST'])
def bi_cancella():
    u = require_login(['superadmin', 'admin'])
    if not u:
        return jsonify({"error": "Non autorizzato"}), 403
    data = request.get_json()
    da = data.get('da', '')
    a = data.get('a', '')
    stati = data.get('stati', [])
    if not da or not a or not stati:
        return jsonify({"error": "Parametri mancanti"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ','.join('?' * len(stati))
    filter_cid = () if u['ruolo'] == 'superadmin' else (u['cliente_id'],)
    extra = "" if u['ruolo'] == 'superadmin' else " AND cliente_id=?"
    c.execute("SELECT id FROM cantieri WHERE data_creazione>=? AND data_creazione<=? AND stato IN (" + placeholders + ")" + extra,
              [da, a + "T23:59:59"] + stati + list(filter_cid))
    ids = [r[0] for r in c.fetchall()]
    for cid in ids:
        c.execute("DELETE FROM cantiere_righe WHERE cantiere_id=?", (cid,))
        c.execute("DELETE FROM cantieri WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "eliminati": len(ids)})

# ---------------------------------------------------------------------------
# API ESISTENTI (invariate)
# ---------------------------------------------------------------------------

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
                     FROM documents d JOIN aziende a ON d.azienda_id = a.id
                     WHERE a.nome = ? ORDER BY d.upload_date DESC''', (brand,))
    else:
        c.execute('SELECT id, filename, upload_date, visibility FROM documents ORDER BY upload_date DESC LIMIT 20')
    docs = c.fetchall()
    conn.close()
    return jsonify({"documents": [{"id": d[0], "filename": d[1], "date": d[2], "visibility": d[3]} for d in docs]})

@app.route('/api/delete-document/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    admin_password = request.args.get('admin_password', '')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''SELECT a.nome, a.admin_required, a.admin_password
                     FROM documents d JOIN aziende a ON d.azienda_id = a.id WHERE d.id = ?''', (doc_id,))
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
    return None

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
            return matches[:5] if matches else []
        return []
    except Exception as e:
        print("[IMAGES ERROR] " + str(e))
        return []

def deepseek_ask(prompt):
    if not DEEPSEEK_API_KEY:
        return "Errore: API Key non configurata"
    for attempt in range(2):
        try:
            resp = httpx.post(
                DEEPSEEK_API_URL,
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "max_tokens": 800},
                headers={"Authorization": "Bearer " + DEEPSEEK_API_KEY},
                timeout=60
            )
            if resp.status_code == 200:
                data = resp.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
            return "Errore API: " + str(resp.status_code)
        except Exception as e:
            print("[DEEPSEEK] Tentativo " + str(attempt + 1) + " fallito: " + str(e))
            if attempt == 1:
                return "DeepSeek non risponde. Riprova tra qualche secondo."
    return "Errore sconosciuto"

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
    prompt += "\n\nRispondi come esperto del settore, considerando i brand specifici. La risposta deve essere completa, coerente e non superare i 1500 caratteri."
    answer = deepseek_ask(prompt)
    return jsonify({"answer": answer, "images": images})

# ---------------------------------------------------------------------------
# FRONTEND
# ---------------------------------------------------------------------------

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
.sidebar { width: 320px; background: rgba(15,23,46,0.9); border-right: 1px solid rgba(59,130,245,0.2); padding: 16px; overflow-y: auto; flex-shrink: 0; }
.main { flex: 1; display: flex; flex-direction: column; padding: 16px; min-width: 0; min-height: 0; overflow: hidden; }
.rightpanel { width: 280px; background: rgba(15,23,46,0.9); border-left: 1px solid rgba(59,130,245,0.2); padding: 12px; overflow-y: auto; flex-shrink: 0; display: none; }
.rightpanel.visible { display: block; }
h2 { color: #3b82f6; margin-bottom: 10px; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
button { padding: 8px 12px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; margin-bottom: 6px; font-size: 11px; }
button:hover { opacity: 0.85; }
.btn-green { background: #10b981; }
.btn-red { background: #ef4444; }
.btn-gray { background: #6b7280; }
.btn-purple { background: #8b5cf6; }
.btn-sm { padding: 4px 8px; font-size: 10px; margin-bottom: 0; }
.dropdown { background: rgba(30,41,59,0.95); border: 1px solid rgba(59,130,245,0.5); border-radius: 6px; padding: 8px; max-height: 220px; overflow-y: auto; display: none; margin-bottom: 8px; }
.dropdown.show { display: block; }
.brand-item { padding: 4px; cursor: pointer; font-size: 11px; }
.brand-item input { margin-right: 4px; }
.badge { display: inline-block; background: #10b981; color: white; padding: 2px 5px; border-radius: 3px; margin: 2px; font-size: 10px; }
.chat-area { flex: 1; background: rgba(15,23,46,0.5); border: 1px solid rgba(59,130,245,0.2); border-radius: 6px; padding: 12px; overflow-y: auto; margin-bottom: 8px; font-size: 12px; min-height: 0; }
.oracolo-msg { position: relative; }
.copy-btn { position: absolute; top: 6px; right: 6px; padding: 3px 8px; font-size: 10px; background: rgba(59,130,245,0.3); color: #93c5fd; border: 1px solid rgba(59,130,245,0.4); border-radius: 4px; cursor: pointer; margin-bottom: 0; }
.copy-btn:hover { background: rgba(59,130,245,0.5); }
.message { background: rgba(59,130,245,0.1); padding: 8px; margin: 4px 0; border-radius: 4px; border-left: 3px solid #3b82f6; }
.message img { max-width: 100%; max-height: 180px; margin-top: 6px; border-radius: 4px; }
.input-area { display: flex; gap: 8px; }
input[type=text], input[type=password], input[type=number], select, textarea { padding: 8px; background: rgba(30,41,59,0.8); border: 1px solid rgba(59,130,245,0.3); color: white; border-radius: 6px; font-size: 11px; }
input[type=text]::placeholder, input[type=password]::placeholder { color: #6b7280; }
.title { color: #3b82f6; font-size: 20px; font-weight: 700; margin-bottom: 12px; }
.btn-3pulsanti { display: flex; gap: 6px; margin-bottom: 10px; }
.btn-3pulsanti button { flex: 1; padding: 7px; font-size: 10px; }
.toggle-btn { width: 100%; padding: 7px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; margin-bottom: 6px; font-size: 11px; }
.toggle-on { background: #10b981; color: white; }
.toggle-off { background: #6b7280; color: white; }
.module-box { background: rgba(30,41,59,0.6); border: 1px solid rgba(59,130,245,0.2); border-radius: 6px; margin-bottom: 8px; overflow: hidden; }
.module-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; cursor: pointer; }
.module-header:hover { background: rgba(59,130,245,0.1); }
.module-title { font-size: 12px; font-weight: 600; color: #93c5fd; }
.module-body { padding: 8px 10px; border-top: 1px solid rgba(59,130,245,0.2); display: none; }
.module-body.open { display: block; }
.cantiere-item { background: rgba(59,130,245,0.1); border-radius: 4px; padding: 6px 8px; margin: 4px 0; font-size: 11px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
.cantiere-item:hover { background: rgba(59,130,245,0.2); }
.stato-badge { padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; }
.stato-bozza { background: #6b7280; color: white; }
.stato-inviata { background: #3b82f6; color: white; }
.stato-vinta { background: #10b981; color: white; }
.stato-persa { background: #ef4444; color: white; }
.riga-item { background: rgba(30,41,59,0.8); border-radius: 4px; padding: 5px 8px; margin: 3px 0; font-size: 10px; display: flex; justify-content: space-between; align-items: center; }
.login-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 9999; display: flex; align-items: center; justify-content: center; }
.login-box { background: rgba(15,23,46,0.98); border: 1px solid rgba(59,130,245,0.4); border-radius: 12px; padding: 32px; width: 320px; }
.login-title { color: #3b82f6; font-size: 20px; font-weight: 700; margin-bottom: 20px; text-align: center; }
.sa-panel { background: rgba(139,92,246,0.15); border: 1px solid rgba(139,92,246,0.4); border-radius: 6px; padding: 8px; margin-bottom: 6px; font-size: 11px; }
.bi-stat { background: rgba(30,41,59,0.8); border-radius: 4px; padding: 6px 8px; margin: 3px 0; font-size: 11px; display: flex; justify-content: space-between; }
.brand-autocomplete { position: relative; width: 100%; }
.brand-dropdown-list { position: absolute; top: 100%; left: 0; right: 0; background: #1e293b; border: 1px solid rgba(59,130,245,0.5); border-top: none; border-radius: 0 0 6px 6px; max-height: 180px; overflow-y: auto; z-index: 3000; display: none; }
.brand-dropdown-list.open { display: block; }
.brand-dropdown-item { padding: 7px 10px; font-size: 11px; cursor: pointer; color: #e0e0e0; }
.brand-dropdown-item:hover { background: rgba(59,130,245,0.3); color: white; }
/* DRAWER CANTIERE */
.cantiere-drawer { display: none; position: fixed; top: 0; right: 0; width: 520px; height: 100vh; background: #0f172e; border-left: 2px solid rgba(59,130,245,0.4); z-index: 1000; flex-direction: column; box-shadow: -4px 0 24px rgba(0,0,0,0.5); }
.cantiere-drawer.open { display: flex; }
.drawer-header { background: rgba(59,130,245,0.15); border-bottom: 1px solid rgba(59,130,245,0.3); padding: 14px 18px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.drawer-title { font-size: 15px; font-weight: 700; color: #60a5fa; }
.drawer-body { flex: 1; overflow-y: auto; padding: 0; }
.drawer-section { border-bottom: 1px solid rgba(59,130,245,0.15); padding: 14px 18px; }
.drawer-section-title { font-size: 11px; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 10px; }
.riga-card { background: rgba(30,41,59,0.9); border: 1px solid rgba(59,130,245,0.2); border-radius: 6px; padding: 8px 12px; margin: 5px 0; display: flex; align-items: center; justify-content: space-between; }
.riga-card-info { flex: 1; }
.riga-card-brand { font-size: 12px; font-weight: 600; color: #60a5fa; }
.riga-card-cat { font-size: 11px; color: #9ca3af; }
.riga-card-importo { font-size: 13px; font-weight: 700; color: #10b981; margin: 0 12px; white-space: nowrap; }
.totale-bar { background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.3); border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.form-row { display: flex; gap: 8px; margin-bottom: 8px; }
.form-row > * { flex: 1; }
.drawer-footer { border-top: 1px solid rgba(59,130,245,0.3); padding: 12px 18px; display: flex; gap: 8px; flex-shrink: 0; background: rgba(15,23,46,0.95); }
</style>
</head>
<body>

<!-- LOGIN OVERLAY -->
<div class="login-overlay" id="login-overlay">
  <div class="login-box">
    <div class="login-title">Oracolo Covolo</div>
    <div style="margin-bottom: 12px;">
      <input type="text" id="login-user" placeholder="Username" style="width: 100%; margin-bottom: 8px;" onkeypress="if(event.key==='Enter') doLogin()">
      <input type="password" id="login-pwd" placeholder="Password" style="width: 100%;" onkeypress="if(event.key==='Enter') doLogin()">
    </div>
    <button onclick="doLogin()" style="width: 100%; padding: 10px; font-size: 13px;">Accedi</button>
    <div id="login-error" style="color: #ef4444; font-size: 11px; margin-top: 8px; text-align: center;"></div>
    <div style="font-size: 10px; color: #4b5563; margin-top: 16px; text-align: center;">Oracolo Covolo — Tecnaria</div>
  </div>
</div>

<div class="container" id="main-app" style="display: none;">
  <!-- SIDEBAR SX -->
  <div class="sidebar">
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
      <span id="user-label" style="font-size: 11px; color: #60a5fa; font-weight: 600;"></span>
      <button onclick="doLogout()" class="btn-sm btn-gray">Esci</button>
    </div>
    <h2>Seleziona brand</h2>
    <button onclick="toggleDropdown()" style="width: 100%;">Seleziona Brand</button>
    <div id="dropdown" class="dropdown">
      <input type="text" id="search" placeholder="Ricerca brand..." onkeyup="filterBrands()" style="width: 100%; margin-bottom: 6px;">
      <div id="brands-list"></div>
    </div>
    <div style="margin: 8px 0;" id="selected"></div>
    <h2>Gruppi salvati</h2>
    <div style="display: flex; gap: 6px; margin-bottom: 8px;">
      <input type="text" id="group-name" placeholder="Nome gruppo..." style="flex: 1;">
      <button onclick="saveGroup()" class="btn-green btn-sm" style="margin-bottom:0;">Salva</button>
    </div>
    <div id="saved-groups" style="max-height: 120px; overflow-y: auto; font-size: 11px;"></div>
    <h2 style="margin-top: 10px;">Protezione cassetto</h2>
    <div style="display: flex; gap: 6px; margin-bottom: 8px;">
      <input type="password" id="admin-pwd" placeholder="Password admin..." style="flex: 1;">
      <button onclick="setAdminPassword()" class="btn-green btn-sm" style="margin-bottom:0;">Proteggi</button>
    </div>
    <h2>Nuovo cassetto</h2>
    <div style="display: flex; gap: 6px; margin-bottom: 8px;">
      <input type="text" id="new-cassetto" placeholder="Nome cassetto..." style="flex: 1;">
      <button onclick="addCassetto()" class="btn-green btn-sm" style="margin-bottom:0;">+</button>
    </div>
    <h2>Accesso privato</h2>
    <input type="password" id="access-code" placeholder="Codice accesso..." style="width: 100%; margin-bottom: 6px;">
    <button onclick="toggleAccess()" style="width: 100%;">Attiva</button>
    <div style="font-size: 10px; color: #9ca3af; margin-top: 4px;" id="access-status">Accesso: PUBBLICO</div>
    <h2 style="margin-top: 10px;">Web search</h2>
    <button id="web-toggle" class="toggle-btn toggle-on" onclick="toggleWeb()">ON</button>
    <h2>Upload documenti</h2>
    <div class="brand-autocomplete" style="margin-bottom:6px;">
      <input type="text" id="upload-brand-input" placeholder="Cerca brand..." autocomplete="off"
        oninput="filterAutocomplete('upload-brand-input','upload-brand-list','upload-brand-val')"
        onfocus="filterAutocomplete('upload-brand-input','upload-brand-list','upload-brand-val')"
        onblur="setTimeout(()=>closeAutocomplete('upload-brand-list'),200)"
        style="width:100%;">
      <input type="hidden" id="upload-brand-val">
      <div class="brand-dropdown-list" id="upload-brand-list"></div>
    </div>
    <label style="display:block; width:100%; background:#8b5cf6; color:white; padding:8px; border-radius:6px; cursor:pointer; font-weight:600; font-size:11px; text-align:center; margin-bottom:6px;">
      Upload Doc <input type="file" id="file-doc" style="display:none" onchange="doUpload(this, 'doc')">
    </label>
    <label style="display:block; width:100%; background:#8b5cf6; color:white; padding:8px; border-radius:6px; cursor:pointer; font-weight:600; font-size:11px; text-align:center; margin-bottom:6px;">
      Upload Excel <input type="file" id="file-excel" accept=".xlsx,.xls,.csv" style="display:none" onchange="doUpload(this, 'excel')">
    </label>
    <div id="upload-status" style="font-size:10px; color:#9ca3af; margin-top:2px;"></div>
    <button onclick="showDocuments()" style="width:100%; background:#ef4444; margin-top:6px;">Gestisci Documenti</button>
  </div>

  <!-- CENTRO -->
  <div class="main">
    <div class="title">Oracolo Covolo</div>
    <div class="btn-3pulsanti" id="btn-3pulsanti">
      <button class="btn-green" onclick="generateOfferta()">OFFERTA</button>
      <button class="btn-green" onclick="generateAnalisi()">ANALISI</button>
      <button class="btn-green" onclick="generateProposta()">PROPOSTA</button>
    </div>
    <div class="chat-area" id="chat"></div>
    <div class="input-area">
      <input type="text" id="question" placeholder="Domanda..." onkeypress="if(event.key==='Enter') ask()" style="flex: 1;">
      <button onclick="ask()" style="width: 100px;">Invia</button>
    </div>
  </div>

  <!-- PANNELLO DX -->
  <div class="rightpanel" id="rightpanel">
    <div style="font-size: 13px; font-weight: 700; color: #93c5fd; margin-bottom: 10px;">Moduli</div>

    <!-- SUPERADMIN PANEL -->
    <div id="sa-panel" style="display:none;">
      <div class="module-box">
        <div class="module-header" onclick="toggleModule('sa-config')">
          <span class="module-title">Config Superadmin</span>
          <span style="font-size:10px; color:#8b5cf6;">SA</span>
        </div>
        <div class="module-body" id="sa-config">
          <div style="margin-bottom: 8px;">
            <select id="sa-cliente-sel" style="width:100%; margin-bottom:6px;" onchange="loadSAModuli()">
              <option value="">-- Seleziona cliente --</option>
            </select>
            <div id="sa-moduli-list" style="font-size:11px;"></div>
          </div>
          <div style="border-top: 1px solid rgba(59,130,245,0.2); padding-top: 8px; margin-top: 4px;">
            <div style="font-size: 11px; font-weight: 600; color: #9ca3af; margin-bottom: 6px;">Nuovo utente</div>
            <input type="text" id="sa-u-nome" placeholder="Nome..." style="width:100%; margin-bottom:4px;">
            <input type="text" id="sa-u-username" placeholder="Username..." style="width:100%; margin-bottom:4px;">
            <input type="password" id="sa-u-pwd" placeholder="Password..." style="width:100%; margin-bottom:4px;">
            <select id="sa-u-ruolo" style="width:100%; margin-bottom:4px;">
              <option value="commerciale">Commerciale</option>
              <option value="admin">Admin cliente</option>
            </select>
            <select id="sa-u-cliente" style="width:100%; margin-bottom:6px;">
              <option value="">-- Cliente --</option>
            </select>
            <button onclick="saAddUtente()" class="btn-green" style="width:100%;">Crea utente</button>
          </div>
        </div>
      </div>
    </div>

    <!-- CANTIERI -->
    <div class="module-box" id="mod-cantieri" style="display:none;">
      <div class="module-header" onclick="toggleModule('cantieri-body')">
        <span class="module-title">Cantieri</span>
        <span id="cantieri-count" style="font-size:10px; color:#9ca3af;">0</span>
      </div>
      <div class="module-body" id="cantieri-body">
        <div style="display: flex; gap: 4px; margin-bottom: 8px;">
          <input type="text" id="new-cantiere" placeholder="Nome cantiere / cliente..." style="flex:1;">
          <button onclick="addCantiere()" class="btn-green btn-sm" style="margin-bottom:0;">+</button>
        </div>
        <div id="cantieri-list"></div>
      </div>
    </div>

    <!-- BI -->
    <div class="module-box" id="mod-bi" style="display:none;">
      <div class="module-header" onclick="toggleModule('bi-body'); loadBI();">
        <span class="module-title">BI / Statistiche</span>
        <span style="font-size:10px; color:#9ca3af;">admin</span>
      </div>
      <div class="module-body" id="bi-body">
        <div id="bi-stats"></div>
        <div style="border-top:1px solid rgba(59,130,245,0.2); padding-top:8px; margin-top:8px;">
          <div style="font-size:11px; font-weight:600; color:#9ca3af; margin-bottom:6px;">Pulizia archivio</div>
          <input type="date" id="bi-da" style="width:100%; margin-bottom:4px;">
          <input type="date" id="bi-a" style="width:100%; margin-bottom:4px;">
          <div style="font-size:10px; color:#9ca3af; margin-bottom:4px;">Stati da eliminare:</div>
          <label style="font-size:10px; display:block;"><input type="checkbox" value="vinta" id="del-vinta"> Vinte</label>
          <label style="font-size:10px; display:block;"><input type="checkbox" value="persa" id="del-persa"> Perse</label>
          <label style="font-size:10px; display:block; margin-bottom:6px;"><input type="checkbox" value="bozza" id="del-bozza"> Bozze</label>
          <button onclick="biCancella()" class="btn-red" style="width:100%; font-size:10px;">Cancella selezionati</button>
        </div>
      </div>
    </div>

    <!-- COMMERCIALI -->
    <div class="module-box" id="mod-commerciali" style="display:none;">
      <div class="module-header" onclick="toggleModule('comm-body')">
        <span class="module-title">Commerciali</span>
        <span style="font-size:10px; color:#9ca3af;">admin</span>
      </div>
      <div class="module-body" id="comm-body">
        <div id="comm-list" style="font-size:11px;"></div>
      </div>
    </div>

  </div>
</div>

<!-- DRAWER DETTAGLIO CANTIERE -->
<div class="cantiere-drawer" id="cantiere-drawer">
  <div class="drawer-header">
    <div>
      <div class="drawer-title" id="drawer-nome"></div>
      <div style="font-size:11px; color:#9ca3af; margin-top:2px;">Gestione offerta</div>
    </div>
    <div style="display:flex; gap:8px; align-items:center;">
      <select id="cantiere-stato" style="font-size:11px; padding:5px 8px;" onchange="updateCantiere()">
        <option value="bozza">Bozza</option>
        <option value="inviata">Inviata</option>
        <option value="vinta">Vinta</option>
        <option value="persa">Persa</option>
      </select>
      <button onclick="closeCantiere()" class="btn-gray btn-sm" style="margin-bottom:0;">✕ Chiudi</button>
    </div>
  </div>

  <div class="drawer-body">
    <!-- RIGHE ESISTENTI -->
    <div class="drawer-section">
      <div class="drawer-section-title">Elementi nel carrello</div>
      <div id="righe-list"></div>
      <div class="totale-bar" id="totale-bar" style="display:none;">
        <span style="font-size:12px; color:#9ca3af;">Totale offerta</span>
        <span style="font-size:15px; font-weight:700; color:#10b981;" id="totale-valore">€0</span>
      </div>
    </div>

    <!-- AGGIUNGI RIGA -->
    <div class="drawer-section">
      <div class="drawer-section-title">Aggiungi elemento</div>
      <div class="form-row">
        <div class="brand-autocomplete" style="flex:1;">
          <input type="text" id="riga-brand-input" placeholder="Cerca brand..." autocomplete="off"
            oninput="filterAutocomplete('riga-brand-input','riga-brand-list','riga-brand-val')"
            onfocus="filterAutocomplete('riga-brand-input','riga-brand-list','riga-brand-val')"
            onblur="setTimeout(()=>closeAutocomplete('riga-brand-list'),200)"
            style="width:100%;">
          <input type="hidden" id="riga-brand-val">
          <div class="brand-dropdown-list" id="riga-brand-list"></div>
        </div>
        <input type="text" id="riga-categoria" placeholder="Categoria (es. sanitari)" style="flex:1;">
      </div>
      <input type="text" id="riga-descrizione" placeholder="Descrizione prodotto..." style="width:100%; margin-bottom:8px;">
      <div class="form-row">
        <input type="number" id="riga-importo" placeholder="Importo €" style="flex:1;">
        <button onclick="addRiga()" class="btn-green" style="flex:1; margin-bottom:0;">+ Aggiungi</button>
      </div>
    </div>
  </div>

  <div class="drawer-footer">
    <button onclick="generaOffertaCantiere()" class="btn-green" style="flex:2; font-size:12px; margin-bottom:0; padding:10px;">Genera Offerta AI</button>
    <button onclick="deleteCantiere()" class="btn-red" style="flex:1; font-size:11px; margin-bottom:0;">Elimina cantiere</button>
  </div>
</div>

<script>
let BRANDS = [];
let selected = [];
let webEnabled = true;
let accessCode = null;
let accessLevel = "public";
let groups = JSON.parse(localStorage.getItem('oracolo_groups')) || {};
let currentUser = null;
let moduliAttivi = [];
let cantiereAttivo = null;

// ---------------------------------------------------------------------------
// AUTOCOMPLETE BRAND
// ---------------------------------------------------------------------------
function filterAutocomplete(inputId, listId, valId) {
  const input = document.getElementById(inputId);
  const list = document.getElementById(listId);
  const val = input.value.toLowerCase();
  const filtered = val.length === 0 ? BRANDS : BRANDS.filter(b => b.toLowerCase().includes(val));
  list.innerHTML = filtered.map(b =>
    '<div class="brand-dropdown-item" onmousedown="selectBrand(\'' + inputId + '\',\'' + listId + '\',\'' + valId + '\',\'' + b.replace(/'/g, "\\'") + '\')">' + b + '</div>'
  ).join('');
  list.classList.add('open');
}

function selectBrand(inputId, listId, valId, brand) {
  document.getElementById(inputId).value = brand;
  document.getElementById(valId).value = brand;
  closeAutocomplete(listId);
}

function closeAutocomplete(listId) {
  const list = document.getElementById(listId);
  if (list) list.classList.remove('open');
}

// ---------------------------------------------------------------------------
// LOGIN
// ---------------------------------------------------------------------------
function doLogin() {
  const username = document.getElementById('login-user').value.trim();
  const password = document.getElementById('login-pwd').value.trim();
  if (!username || !password) { document.getElementById('login-error').textContent = 'Inserisci username e password'; return; }
  fetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username, password}) })
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
  fetch('/api/logout', { method:'POST' }).then(() => {
    document.getElementById('login-overlay').style.display = 'flex';
    document.getElementById('main-app').style.display = 'none';
    document.getElementById('login-user').value = '';
    document.getElementById('login-pwd').value = '';
    document.getElementById('login-error').textContent = '';
    currentUser = null;
    moduliAttivi = [];
  });
}

function initApp() {
  fetch('/api/me').then(r => r.json()).then(d => {
    if (!d.logged) { doLogout(); return; }
    currentUser = d.user;
    moduliAttivi = d.moduli || [];
    document.getElementById('user-label').textContent = currentUser.nome + ' (' + currentUser.ruolo + ')';
    setupRightPanel();
    loadBrands();
  });
}

// ---------------------------------------------------------------------------
// SETUP PANNELLO DX
// ---------------------------------------------------------------------------
function setupRightPanel() {
  const rp = document.getElementById('rightpanel');
  const hasMods = moduliAttivi.length > 0 || currentUser.ruolo === 'superadmin';
  if (hasMods) rp.classList.add('visible');

  if (currentUser.ruolo === 'superadmin') {
    document.getElementById('sa-panel').style.display = 'block';
    loadSAClienti();
    document.getElementById('mod-cantieri').style.display = 'block';
    document.getElementById('mod-bi').style.display = 'block';
    document.getElementById('mod-commerciali').style.display = 'block';
  } else {
    if (moduliAttivi.includes('cantieri')) document.getElementById('mod-cantieri').style.display = 'block';
    if (moduliAttivi.includes('bi') && (currentUser.ruolo === 'admin')) document.getElementById('mod-bi').style.display = 'block';
    if (moduliAttivi.includes('commerciali') && (currentUser.ruolo === 'admin')) document.getElementById('mod-commerciali').style.display = 'block';
  }
  loadCantieri();
}

function toggleModule(id) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle('open');
}

// ---------------------------------------------------------------------------
// SUPERADMIN
// ---------------------------------------------------------------------------
function loadSAClienti() {
  fetch('/api/sa/clienti').then(r => r.json()).then(d => {
    const sel1 = document.getElementById('sa-cliente-sel');
    const sel2 = document.getElementById('sa-u-cliente');
    (d.clienti || []).forEach(cl => {
      const o1 = document.createElement('option'); o1.value = cl.id; o1.textContent = cl.nome; sel1.appendChild(o1);
      const o2 = document.createElement('option'); o2.value = cl.id; o2.textContent = cl.nome; sel2.appendChild(o2);
    });
  });
}

function loadSAModuli() {
  const cid = document.getElementById('sa-cliente-sel').value;
  if (!cid) return;
  fetch('/api/sa/moduli/' + cid).then(r => r.json()).then(d => {
    const moduli = d.moduli || {};
    const names = {'cantieri':'Cantieri','carrello':'Carrello','bi':'BI / Statistiche','commerciali':'Commerciali'};
    let html = '';
    Object.keys(names).forEach(k => {
      const on = moduli[k];
      html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0;">';
      html += '<span>' + names[k] + '</span>';
      html += '<button onclick="toggleModulo(' + cid + ',\'' + k + '\',' + (on?'false':'true') + ')" class="btn-sm ' + (on?'btn-green':'btn-gray') + '" style="margin-bottom:0;">' + (on?'ON':'OFF') + '</button>';
      html += '</div>';
    });
    document.getElementById('sa-moduli-list').innerHTML = html;
  });
}

function toggleModulo(cid, modulo, attivo) {
  fetch('/api/sa/moduli/' + cid, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({modulo, attivo}) })
    .then(r => r.json()).then(d => { if (d.ok) loadSAModuli(); });
}

function saAddUtente() {
  const nome = document.getElementById('sa-u-nome').value.trim();
  const username = document.getElementById('sa-u-username').value.trim();
  const password = document.getElementById('sa-u-pwd').value.trim();
  const ruolo = document.getElementById('sa-u-ruolo').value;
  const cliente_id = document.getElementById('sa-u-cliente').value || null;
  if (!nome || !username || !password) { alert('Dati incompleti'); return; }
  fetch('/api/sa/utenti', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nome, username, password, ruolo, cliente_id}) })
    .then(r => r.json()).then(d => {
      if (d.ok) { alert('Utente creato!'); document.getElementById('sa-u-nome').value=''; document.getElementById('sa-u-username').value=''; document.getElementById('sa-u-pwd').value=''; }
      else alert('Errore: ' + d.error);
    });
}

// ---------------------------------------------------------------------------
// CANTIERI
// ---------------------------------------------------------------------------
function loadCantieri() {
  if (!document.getElementById('mod-cantieri') || document.getElementById('mod-cantieri').style.display === 'none') return;
  fetch('/api/cantieri').then(r => r.json()).then(d => {
    const list = d.cantieri || [];
    document.getElementById('cantieri-count').textContent = list.length;
    document.getElementById('cantieri-list').innerHTML = list.map(ca =>
      '<div class="cantiere-item" onclick="openCantiere(' + ca.id + ',\'' + ca.nome.replace(/'/g,'') + '\',\'' + ca.stato + '\')">' +
      '<span>' + ca.nome + '</span>' +
      '<span class="stato-badge stato-' + ca.stato + '">' + ca.stato + '</span>' +
      '</div>'
    ).join('');
  });
}

function addCantiere() {
  const nome = document.getElementById('new-cantiere').value.trim();
  if (!nome) { alert('Nome richiesto'); return; }
  fetch('/api/cantieri', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nome}) })
    .then(r => r.json()).then(d => {
      if (d.ok) { document.getElementById('new-cantiere').value = ''; loadCantieri(); openCantiere(d.id, nome, 'bozza'); }
      else alert('Errore: ' + d.error);
    });
}

function openCantiere(id, nome, stato) {
  cantiereAttivo = id;
  document.getElementById('drawer-nome').textContent = nome;
  document.getElementById('cantiere-stato').value = stato;
  document.getElementById('cantiere-drawer').classList.add('open');
  loadRighe();
}

function closeCantiere() {
  cantiereAttivo = null;
  document.getElementById('cantiere-drawer').classList.remove('open');
}

function updateCantiere() {
  if (!cantiereAttivo) return;
  const stato = document.getElementById('cantiere-stato').value;
  fetch('/api/cantieri/' + cantiereAttivo, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({stato}) })
    .then(r => r.json()).then(() => loadCantieri());
}

function deleteCantiere() {
  if (!cantiereAttivo) return;
  if (!confirm('Eliminare questo cantiere e tutte le sue righe?')) return;
  fetch('/api/cantieri/' + cantiereAttivo, { method:'DELETE' })
    .then(r => r.json()).then(() => { closeCantiere(); loadCantieri(); });
}

function loadRighe() {
  if (!cantiereAttivo) return;
  fetch('/api/cantieri/' + cantiereAttivo + '/righe').then(r => r.json()).then(d => {
    const righe = d.righe || [];
    let totale = 0;
    righe.forEach(r => { totale += (r.importo || 0); });
    document.getElementById('righe-list').innerHTML = righe.length === 0
      ? '<div style="color:#6b7280; font-size:11px; text-align:center; padding:12px 0;">Nessun elemento aggiunto</div>'
      : righe.map(r =>
          '<div class="riga-card">' +
          '<div class="riga-card-info">' +
          '<div class="riga-card-brand">' + (r.brand||'—') + '</div>' +
          '<div class="riga-card-cat">' + (r.categoria||'') + (r.descrizione ? ' — ' + r.descrizione : '') + '</div>' +
          '</div>' +
          '<div class="riga-card-importo">' + (r.importo ? '€' + r.importo.toFixed(0) : '—') + '</div>' +
          '<button onclick="deleteRiga(' + r.id + ')" class="btn-red btn-sm" style="margin-bottom:0; padding:3px 7px;">✕</button>' +
          '</div>'
        ).join('');
    const totBar = document.getElementById('totale-bar');
    if (righe.length > 0) {
      totBar.style.display = 'flex';
      document.getElementById('totale-valore').textContent = '€' + totale.toFixed(0);
    } else {
      totBar.style.display = 'none';
    }
  });
}

function addRiga() {
  if (!cantiereAttivo) return;
  const brand = document.getElementById('riga-brand-val').value;
  const categoria = document.getElementById('riga-categoria').value.trim();
  const descrizione = document.getElementById('riga-descrizione').value.trim();
  const importo = parseFloat(document.getElementById('riga-importo').value) || 0;
  if (!brand && !categoria) { alert('Inserisci almeno brand o categoria'); return; }
  fetch('/api/cantieri/' + cantiereAttivo + '/righe', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({brand, categoria, descrizione, importo}) })
    .then(r => r.json()).then(d => {
      if (d.ok) {
        document.getElementById('riga-brand-input').value = '';
        document.getElementById('riga-brand-val').value = '';
        document.getElementById('riga-categoria').value = '';
        document.getElementById('riga-descrizione').value = '';
        document.getElementById('riga-importo').value = '';
        loadRighe();
      }
    });
}

function deleteRiga(rid) {
  fetch('/api/cantieri/righe/' + rid, { method:'DELETE' }).then(() => loadRighe());
}

function generaOffertaCantiere() {
  if (!cantiereAttivo) return;
  fetch('/api/cantieri/' + cantiereAttivo + '/righe').then(r => r.json()).then(d => {
    const righe = d.righe || [];
    if (righe.length === 0) { alert('Aggiungi prima delle righe al cantiere'); return; }
    const nome = document.getElementById('cantiere-nome-label').textContent;
    const riepilogo = righe.map(r => '- ' + (r.brand||'') + ' | ' + (r.categoria||'') + ' | ' + (r.descrizione||'') + (r.importo ? ' | €' + r.importo : '')).join('\n');
    const brands = [...new Set(righe.map(r => r.brand).filter(Boolean))];
    if (brands.length === 0) { alert('Aggiungi brand alle righe'); return; }
    selected = brands;
    document.getElementById('selected').innerHTML = selected.map(b => '<span class="badge">' + b + ' x</span>').join('');
    document.getElementById('question').value = 'Genera una proposta commerciale completa per il cantiere "' + nome + '" con i seguenti elementi:\n' + riepilogo;
    ask();
  });
}

// ---------------------------------------------------------------------------
// BI
// ---------------------------------------------------------------------------
function loadBI() {
  fetch('/api/bi/stats').then(r => r.json()).then(d => {
    const ps = d.per_stato || {};
    let html = '<div style="font-size:11px;font-weight:600;color:#9ca3af;margin-bottom:4px;">Per stato</div>';
    ['bozza','inviata','vinta','persa'].forEach(s => {
      if (ps[s]) html += '<div class="bi-stat"><span>' + s + '</span><span>' + ps[s] + '</span></div>';
    });
    html += '<div class="bi-stat" style="margin-top:4px;"><span>Valore vinto</span><span style="color:#10b981;">€' + (d.valore_vinto||0).toFixed(0) + '</span></div>';
    html += '<div class="bi-stat"><span>Valore aperto</span><span style="color:#3b82f6;">€' + (d.valore_aperto||0).toFixed(0) + '</span></div>';
    if (d.per_commerciale && d.per_commerciale.length > 0) {
      html += '<div style="font-size:11px;font-weight:600;color:#9ca3af;margin-top:8px;margin-bottom:4px;">Per commerciale</div>';
      d.per_commerciale.forEach(pc => {
        html += '<div class="bi-stat"><span>' + pc.nome + '</span><span>' + pc.cantieri + ' | €' + pc.valore.toFixed(0) + '</span></div>';
      });
    }
    document.getElementById('bi-stats').innerHTML = html;
  });
}

function biCancella() {
  const da = document.getElementById('bi-da').value;
  const a = document.getElementById('bi-a').value;
  if (!da || !a) { alert('Seleziona un range di date'); return; }
  const stati = [];
  if (document.getElementById('del-vinta').checked) stati.push('vinta');
  if (document.getElementById('del-persa').checked) stati.push('persa');
  if (document.getElementById('del-bozza').checked) stati.push('bozza');
  if (stati.length === 0) { alert('Seleziona almeno uno stato'); return; }
  if (!confirm('Cancellare i cantieri selezionati? Operazione irreversibile.')) return;
  fetch('/api/bi/cancella', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({da, a, stati}) })
    .then(r => r.json()).then(d => {
      if (d.ok) { alert('Eliminati ' + d.eliminati + ' cantieri'); loadBI(); loadCantieri(); }
    });
}

// ---------------------------------------------------------------------------
// BRANDS / DROPDOWN
// ---------------------------------------------------------------------------
function loadBrands() {
  fetch('/api/get-brands').then(r => r.json()).then(d => {
    BRANDS = d.brands || [];
    loadGroups();
  }).catch(e => console.error("Errore brand:", e));
}

function toggleDropdown() {
  const dd = document.getElementById('dropdown');
  if (!dd) return;
  if (dd.classList.contains('show')) { dd.classList.remove('show'); }
  else { dd.classList.add('show'); filterBrands(); }
}

function filterBrands() {
  const search = document.getElementById('search');
  const brandsList = document.getElementById('brands-list');
  if (!search || !brandsList) return;
  const sv = search.value.toLowerCase();
  const filtered = BRANDS.filter(b => b.toLowerCase().includes(sv));
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
  if (code) { accessCode = code; accessLevel = "private"; document.getElementById('access-status').textContent = 'Accesso: PRIVATO (' + code + ')'; }
  else { accessCode = null; accessLevel = "public"; document.getElementById('access-status').textContent = 'Accesso: PUBBLICO'; }
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
    '<div style="padding:4px;background:rgba(59,130,245,0.2);border-radius:4px;margin:3px 0;font-size:11px"><strong>' + name + '</strong> <button onclick="loadGroup(\'' + name + '\')" style="padding:1px 5px;font-size:9px">carica</button> <button onclick="deleteGroup(\'' + name + '\')" style="padding:1px 5px;font-size:9px;background:#ef4444">x</button></div>'
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
  fetch('/api/set-admin-password', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({brand, admin_password: pwd}) })
    .then(r => r.json()).then(d => {
      if (d.ok) alert('OK: ' + d.message);
      else alert('Errore: ' + d.error);
      document.getElementById('admin-pwd').value = '';
    });
}

function addCassetto() {
  const nome = document.getElementById('new-cassetto').value.trim();
  if (!nome) { alert('Nome richiesto'); return; }
  fetch('/api/add-azienda', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({nome}) })
    .then(r => r.json()).then(d => {
      if (d.ok) {
        alert('Cassetto aggiunto!');
        document.getElementById('new-cassetto').value = '';
        fetch('/api/get-brands').then(r => r.json()).then(data => { BRANDS = data.brands || []; });
      } else alert('Errore: ' + d.error);
    });
}

function doUpload(input, tipo) {
  const brand = document.getElementById('upload-brand-val').value;
  if (!brand) { document.getElementById('upload-status').textContent = 'Seleziona prima un brand!'; document.getElementById('upload-status').style.color = '#ef4444'; input.value=''; return; }
  const file = input.files[0];
  if (!file) return;
  document.getElementById('upload-status').textContent = 'Caricamento...';
  document.getElementById('upload-status').style.color = '#9ca3af';
  const reader = new FileReader();
  reader.onload = function(e) {
    const filename = tipo === 'excel' ? file.name + ' [EXCEL]' : file.name;
    fetch('/api/upload-document', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({filename, content: e.target.result, brand, visibility: accessLevel, access_code: accessCode}) })
      .then(r => r.json()).then(d => {
        if (d.ok) { document.getElementById('upload-status').textContent = 'Caricato: ' + file.name; document.getElementById('upload-status').style.color = '#10b981'; }
        else { document.getElementById('upload-status').textContent = 'Errore: ' + d.error; document.getElementById('upload-status').style.color = '#ef4444'; }
        input.value = '';
      });
  };
  reader.readAsDataURL(file);
}

function showDocuments() {
  const brand = prompt('Per quale brand?');
  if (!brand) return;
  fetch('/api/list-documents?brand=' + encodeURIComponent(brand)).then(r => r.json()).then(d => {
    if (!d.documents || d.documents.length === 0) { alert('Nessun documento per ' + brand); return; }
    const list = d.documents.map(doc => doc.id + ' | ' + doc.filename + ' | ' + (doc.date||'')).join('\n');
    const idStr = prompt('Documenti:\n' + list + '\n\nID da eliminare:');
    if (!idStr) return;
    const docId = parseInt(idStr);
    if (isNaN(docId)) { alert('ID non valido'); return; }
    if (!confirm('Eliminare documento ID ' + docId + '?')) return;
    fetch('/api/delete-document/' + docId, { method:'DELETE' }).then(r => r.json()).then(d => {
      if (d.ok) alert('Eliminato!');
      else alert('Errore: ' + d.error);
    });
  });
}

function generateOfferta() {
  if (!selected.length) { alert('Seleziona brand'); return; }
  document.getElementById('question').value = 'Genera una proposta commerciale da presentare al cliente finale, illustrando i vantaggi e le caratteristiche dei brand selezionati: ' + selected.join(', ') + '. Il documento deve essere professionale, orientato al cliente e convincente.';
  ask();
}
function generateAnalisi() {
  if (!selected.length) { alert('Seleziona brand'); return; }
  document.getElementById('question').value = 'Crea una scheda analitica da condividere con il cliente sui brand selezionati: ' + selected.join(', ') + '. Evidenzia punti di forza, materiali, design e perché sono la scelta giusta per un progetto di qualità.';
  ask();
}
function generateProposta() {
  if (!selected.length) { alert('Seleziona brand'); return; }
  document.getElementById('question').value = 'Prepara una proposta strategica da presentare al cliente per un progetto che utilizzi i brand: ' + selected.join(', ') + '. Includi posizionamento, benefici concreti e suggerimenti di abbinamento.';
  ask();
}

function copyRisposta(msgId) {
  const el = document.getElementById(msgId);
  if (!el) return;
  const testo = el.innerText.replace('Copia\n', '').replace('Oracolo:\n', '').trim();
  navigator.clipboard.writeText(testo).then(() => {
    const btn = el.querySelector('.copy-btn');
    if (btn) { btn.textContent = 'Copiato!'; setTimeout(() => { btn.textContent = 'Copia'; }, 2000); }
  }).catch(() => {
    const range = document.createRange();
    range.selectNode(el);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    document.execCommand('copy');
    window.getSelection().removeAllRanges();
  });
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
    body: JSON.stringify({question: q, brands: selected, web: webEnabled, access_code: accessCode}) })
    .then(r => r.json())
    .then(d => {
      const loading = document.getElementById(loadingId);
      if (loading) loading.remove();
      const formatted = parseMarkdown(d.answer || 'Nessuna risposta');
      const msgId = 'msg_' + Date.now();
      let html = '<div class="message oracolo-msg" id="' + msgId + '">';
      html += '<button class="copy-btn" onclick="copyRisposta(\'' + msgId + '\')">Copia</button>';
      html += '<strong style="color:#60a5fa">Oracolo:</strong><div style="margin-top:6px;line-height:1.6">' + formatted + '</div>';
      if (d.images && d.images.length > 0) {
        html += '<div style="margin-top:8px;display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:6px">';
        d.images.forEach(img => { html += '<img src="' + img + '" style="max-width:100%;height:auto;border-radius:4px;cursor:pointer" onclick="window.open(\'' + img + '\',\'_blank\')">'; });
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

// Controlla se già loggato
fetch('/api/me').then(r => r.json()).then(d => {
  if (d.logged) {
    document.getElementById('login-overlay').style.display = 'none';
    document.getElementById('main-app').style.display = 'flex';
    initApp();
  }
});
</script>
</body>
</html>''')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
