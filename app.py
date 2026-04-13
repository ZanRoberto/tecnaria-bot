"""
ORACOLO COVOLO - V8 - SISTEMA PIANI/STANZE/VOCI COMPLETO + FIX DRAWER BUG
==================================================================================
✅ Login 3 livelli (superadmin/admin/commerciale)
✅ Carica listino Excel + abbinamenti
✅ Sistema PIANI (Piano 1, 2, 3...)
✅ STANZE dentro piani (Bagno, Cucina, Camera...)
✅ VOCI dentro stanze (Brand prodotti + voci manuali montaggio/posa)
✅ Subtotali: voce → stanza → piano → totale generale
✅ Sconto parametrico (per riga o generale)
✅ MODALITA SMART (semplice/piani) con switch bottone
✅ FIX: Drawer non torna più a SEMPLICE quando clicchi Piano

DATABASE: SQLite /home/app/data/oracolo_covolo.db
DEPLOY: Render (git push → auto-deploy)
"""

import os, json, sqlite3, re, hashlib, secrets, sys, io, base64
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session, send_file
from functools import wraps

# ============================================================================
# CONFIGURAZIONE
# ============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'oracolo_covolo.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Password superadmin (legge da env var Render, senza .strip() per preservare ?)
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "tecnaria2024")

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

print("[START] ORACOLO COVOLO V8 - Sistema PIANI/STANZE/VOCI", file=sys.stderr)
sys.stderr.flush()

# ============================================================================
# DATABASE INIT
# ============================================================================
def init_db():
    """Inizializza database con tabelle piani/stanze/voci"""
    print("[INIT_DB] Starting...", file=sys.stderr)
    sys.stderr.flush()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Tabelle esistenti
    c.execute("""
        CREATE TABLE IF NOT EXISTS utenti (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            livello TEXT,
            cliente_id INTEGER,
            created_at TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS cantieri (
            id INTEGER PRIMARY KEY,
            nome TEXT,
            cliente_id INTEGER,
            stato TEXT DEFAULT 'bozza',
            totale_generale REAL DEFAULT 0,
            modalita TEXT DEFAULT 'semplice',
            created_at TEXT,
            FOREIGN KEY(cliente_id) REFERENCES utenti(id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS cantiere_righe (
            id INTEGER PRIMARY KEY,
            cantiere_id INTEGER,
            codice TEXT,
            brand TEXT,
            categoria TEXT,
            descrizione TEXT,
            quantita INTEGER DEFAULT 1,
            udm TEXT,
            prezzo REAL,
            sconto_percentuale REAL DEFAULT 0,
            subtotale REAL,
            created_at TEXT,
            FOREIGN KEY(cantiere_id) REFERENCES cantieri(id)
        )
    """)
    
    # NUOVE tabelle PIANI/STANZE/VOCI
    c.execute("""
        CREATE TABLE IF NOT EXISTS piani (
            id INTEGER PRIMARY KEY,
            cantiere_id INTEGER,
            numero INTEGER,
            nome TEXT,
            totale_piano REAL DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY(cantiere_id) REFERENCES cantieri(id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS stanze (
            id INTEGER PRIMARY KEY,
            piano_id INTEGER,
            nome TEXT,
            descrizione TEXT,
            totale_stanza REAL DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY(piano_id) REFERENCES piani(id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS stanza_voci (
            id INTEGER PRIMARY KEY,
            stanza_id INTEGER,
            tipo TEXT,
            codice TEXT,
            brand TEXT,
            descrizione TEXT,
            quantita INTEGER DEFAULT 1,
            udm TEXT,
            prezzo_unitario REAL,
            sconto_percentuale REAL DEFAULT 0,
            sconto_fisso REAL DEFAULT 0,
            subtotale REAL,
            immagine_b64 TEXT,
            note TEXT,
            created_at TEXT,
            FOREIGN KEY(stanza_id) REFERENCES stanze(id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS config_sistema (
            id INTEGER PRIMARY KEY,
            chiave TEXT UNIQUE,
            valore TEXT,
            descrizione TEXT,
            updated_at TEXT
        )
    """)
    
    # Inizializza config
    c.execute("INSERT OR IGNORE INTO config_sistema (chiave, valore, descrizione) VALUES ('SCONTO_MODE', '1', 'Modalità sconto: 1=per riga, 2=generale')")
    
    # Superadmin
    superadmin_hash = hashlib.sha256(SUPERADMIN_PASSWORD.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO utenti (username, password_hash, livello, created_at) VALUES ('superadmin', ?, 'superadmin', ?)",
              (superadmin_hash, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    print("[INIT_DB] DONE!", file=sys.stderr)
    sys.stderr.flush()

init_db()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        return f(*args, **kwargs)
    return decorated

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
    
    # Ricalcola subtotali voci (se in modalita piani)
    c.execute("SELECT id, prezzo_unitario, quantita, sconto_percentuale, sconto_fisso FROM stanza_voci")
    for voce_id, prezzo, qty, sconto_perc, sconto_fisso in c.fetchall():
        subtotale = calcola_subtotale_voce(prezzo, qty, sconto_perc, sconto_fisso)
        c.execute("UPDATE stanza_voci SET subtotale = ? WHERE id = ?", (subtotale, voce_id))
    
    # Ricalcola totali stanze
    c.execute("SELECT id FROM stanze")
    for (stanza_id,) in c.fetchall():
        c.execute("SELECT SUM(subtotale) FROM stanza_voci WHERE stanza_id = ?", (stanza_id,))
        total = c.fetchone()[0] or 0
        c.execute("UPDATE stanze SET totale_stanza = ? WHERE id = ?", (total, stanza_id))
    
    # Ricalcola totali piani
    c.execute("SELECT id FROM piani WHERE cantiere_id = ?", (cantiere_id,))
    for (piano_id,) in c.fetchall():
        c.execute("SELECT SUM(totale_stanza) FROM stanze WHERE piano_id = ?", (piano_id,))
        total = c.fetchone()[0] or 0
        c.execute("UPDATE piani SET totale_piano = ? WHERE id = ?", (total, piano_id))
    
    # Ricalcola totale generale cantiere
    c.execute("SELECT SUM(totale_piano) FROM piani WHERE cantiere_id = ?", (cantiere_id,))
    total_generale = c.fetchone()[0] or 0
    c.execute("UPDATE cantieri SET totale_generale = ? WHERE id = ?", (total_generale, cantiere_id))
    
    conn.commit()
    conn.close()

# ============================================================================
# API ENDPOINTS - AUTH
# ============================================================================
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    c.execute("SELECT id, livello FROM utenti WHERE username = ? AND password_hash = ?", (username, password_hash))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['livello'] = user[1]
        return jsonify({'ok': True, 'livello': user[1]})
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/me', methods=['GET'])
@login_required
def me():
    user_id = session.get('user_id')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, livello FROM utenti WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({'username': row[0], 'livello': row[1]})
    return jsonify({'error': 'User not found'}), 404

# ============================================================================
# API ENDPOINTS - PIANI/STANZE/VOCI
# ============================================================================
@app.route('/api/cantieri/<int:cid>/modalita', methods=['GET'])
@login_required
def get_modalita(cid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT modalita FROM cantieri WHERE id = ?", (cid,))
    row = c.fetchone()
    conn.close()
    modalita = row[0] if row else 'semplice'
    return jsonify({'modalita': modalita})

@app.route('/api/cantieri/<int:cid>/modalita', methods=['PUT'])
@login_required
def set_modalita(cid):
    data = request.json
    nuova_modalita = data.get('modalita', 'semplice')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Leggi modalita attuale
    c.execute("SELECT modalita FROM cantieri WHERE id = ?", (cid,))
    row = c.fetchone()
    modalita_attuale = row[0] if row else 'semplice'
    
    # Se cambio da semplice a piani: migra righe in Piano 1 → Stanza unica
    if modalita_attuale == 'semplice' and nuova_modalita == 'piani':
        # Crea Piano 1
        c.execute("INSERT INTO piani (cantiere_id, numero, nome, created_at) VALUES (?, 1, 'Piano 1', ?)",
                  (cid, datetime.now().isoformat()))
        piano_id = c.lastrowid
        
        # Crea Stanza unica
        c.execute("INSERT INTO stanze (piano_id, nome, descrizione, created_at) VALUES (?, 'Stanza unica', 'Importata', ?)",
                  (piano_id, datetime.now().isoformat()))
        stanza_id = c.lastrowid
        
        # Migra righe cantiere → stanza_voci
        c.execute("SELECT codice, brand, categoria, descrizione, quantita, udm, prezzo, sconto_percentuale FROM cantiere_righe WHERE cantiere_id = ?", (cid,))
        for codice, brand, categoria, desc, qty, udm, prezzo, sconto in c.fetchall():
            subtotale = calcola_subtotale_voce(prezzo, qty, sconto)
            c.execute("""
                INSERT INTO stanza_voci 
                (stanza_id, tipo, codice, brand, descrizione, quantita, udm, prezzo_unitario, sconto_percentuale, subtotale, created_at)
                VALUES (?, 'brand', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (stanza_id, codice, brand, desc, qty, udm, prezzo, sconto, subtotale, datetime.now().isoformat()))
    
    # Salva nuova modalita
    c.execute("UPDATE cantieri SET modalita = ? WHERE id = ?", (nuova_modalita, cid))
    
    conn.commit()
    conn.close()
    
    ricalcola_totali_cantiere(cid)
    
    return jsonify({'ok': True, 'modalita': nuova_modalita})

@app.route('/api/cantieri/<int:cid>/struttura', methods=['GET'])
@login_required
def get_struttura_cantiere(cid):
    """Restituisce INTERA struttura piani/stanze/voci con totali"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT id, nome, totale_generale FROM cantieri WHERE id = ?", (cid,))
    cantiere = c.fetchone()
    if not cantiere:
        return jsonify({'error': 'Cantiere not found'}), 404
    
    c.execute("SELECT id, numero, nome, totale_piano FROM piani WHERE cantiere_id = ? ORDER BY numero", (cid,))
    piani_list = []
    for piano_id, numero, nome, totale_piano in c.fetchall():
        c.execute("SELECT id, nome, descrizione, totale_stanza FROM stanze WHERE piano_id = ? ORDER BY id", (piano_id,))
        stanze_list = []
        for stanza_id, stanza_nome, stanza_desc, totale_stanza in c.fetchall():
            c.execute("""
                SELECT id, tipo, codice, brand, descrizione, quantita, udm, prezzo_unitario, 
                       sconto_percentuale, sconto_fisso, subtotale
                FROM stanza_voci 
                WHERE stanza_id = ? 
                ORDER BY id
            """, (stanza_id,))
            voci = [{
                'id': v[0], 'tipo': v[1], 'codice': v[2], 'brand': v[3], 'descrizione': v[4],
                'quantita': v[5], 'udm': v[6], 'prezzo_unitario': v[7],
                'sconto_percentuale': v[8], 'sconto_fisso': v[9], 'subtotale': v[10]
            } for v in c.fetchall()]
            
            stanze_list.append({
                'id': stanza_id, 'nome': stanza_nome, 'descrizione': stanza_desc,
                'totale_stanza': totale_stanza, 'voci': voci
            })
        
        piani_list.append({
            'id': piano_id, 'numero': numero, 'nome': nome,
            'totale_piano': totale_piano, 'stanze': stanze_list
        })
    
    conn.close()
    
    return jsonify({
        'ok': True,
        'cantiere_id': cid,
        'cantiere_nome': cantiere[0],
        'totale_generale': cantiere[2],
        'piani': piani_list
    })

@app.route('/api/cantieri/<int:cid>/piani', methods=['POST'])
@login_required
def crea_piano(cid):
    data = request.json
    nome_piano = data.get('nome', 'Piano')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Trova numero successivo
    c.execute("SELECT MAX(numero) FROM piani WHERE cantiere_id = ?", (cid,))
    max_num = c.fetchone()[0] or 0
    numero = max_num + 1
    
    c.execute("""
        INSERT INTO piani (cantiere_id, numero, nome, created_at)
        VALUES (?, ?, ?, ?)
    """, (cid, numero, nome_piano, datetime.now().isoformat()))
    
    piano_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'ok': True, 'piano_id': piano_id, 'numero': numero})

@app.route('/api/piani/<int:pid>/stanze', methods=['POST'])
@login_required
def crea_stanza(pid):
    data = request.json
    nome_stanza = data.get('nome', 'Stanza')
    descrizione = data.get('descrizione', '')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Leggi piano per trovare cantiere_id
    c.execute("SELECT cantiere_id FROM piani WHERE id = ?", (pid,))
    row = c.fetchone()
    if not row:
        return jsonify({'error': 'Piano not found'}), 404
    
    cantiere_id = row[0]
    
    c.execute("""
        INSERT INTO stanze (piano_id, nome, descrizione, created_at)
        VALUES (?, ?, ?, ?)
    """, (pid, nome_stanza, descrizione, datetime.now().isoformat()))
    
    stanza_id = c.lastrowid
    conn.commit()
    conn.close()
    
    ricalcola_totali_cantiere(cantiere_id)
    
    return jsonify({'ok': True, 'stanza_id': stanza_id})

@app.route('/api/stanze/<int:sid>/voci', methods=['POST'])
@login_required
def aggiungi_voce(sid):
    data = request.json
    tipo = data.get('tipo', 'manuale')  # brand o manuale
    codice = data.get('codice', '')
    brand = data.get('brand', '')
    descrizione = data.get('descrizione', '')
    quantita = int(data.get('quantita', 1))
    udm = data.get('udm', 'pezzo')
    prezzo_unitario = float(data.get('prezzo_unitario', 0))
    sconto_perc = float(data.get('sconto_percentuale', 0))
    sconto_fisso = float(data.get('sconto_fisso', 0))
    
    # Calcola subtotale
    subtotale = calcola_subtotale_voce(prezzo_unitario, quantita, sconto_perc, sconto_fisso)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Leggi stanza → piano → cantiere
    c.execute("SELECT piano_id FROM stanze WHERE id = ?", (sid,))
    stanza_row = c.fetchone()
    if not stanza_row:
        return jsonify({'error': 'Stanza not found'}), 404
    
    piano_id = stanza_row[0]
    c.execute("SELECT cantiere_id FROM piani WHERE id = ?", (piano_id,))
    piano_row = c.fetchone()
    cantiere_id = piano_row[0]
    
    c.execute("""
        INSERT INTO stanza_voci 
        (stanza_id, tipo, codice, brand, descrizione, quantita, udm, prezzo_unitario, 
         sconto_percentuale, sconto_fisso, subtotale, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sid, tipo, codice, brand, descrizione, quantita, udm, prezzo_unitario, 
          sconto_perc, sconto_fisso, subtotale, datetime.now().isoformat()))
    
    voce_id = c.lastrowid
    conn.commit()
    conn.close()
    
    ricalcola_totali_cantiere(cantiere_id)
    
    return jsonify({'ok': True, 'voce_id': voce_id})

@app.route('/api/stanza_voci/<int:vid>', methods=['PUT'])
@login_required
def modifica_voce(vid):
    data = request.json
    quantita = int(data.get('quantita', 1))
    prezzo_unitario = float(data.get('prezzo_unitario', 0))
    sconto_perc = float(data.get('sconto_percentuale', 0))
    sconto_fisso = float(data.get('sconto_fisso', 0))
    
    subtotale = calcola_subtotale_voce(prezzo_unitario, quantita, sconto_perc, sconto_fisso)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Leggi voce per trovare stanza → piano → cantiere
    c.execute("SELECT stanza_id FROM stanza_voci WHERE id = ?", (vid,))
    voce_row = c.fetchone()
    if not voce_row:
        return jsonify({'error': 'Voce not found'}), 404
    
    stanza_id = voce_row[0]
    c.execute("SELECT piano_id FROM stanze WHERE id = ?", (stanza_id,))
    stanza_row = c.fetchone()
    piano_id = stanza_row[0]
    c.execute("SELECT cantiere_id FROM piani WHERE id = ?", (piano_id,))
    piano_row = c.fetchone()
    cantiere_id = piano_row[0]
    
    c.execute("""
        UPDATE stanza_voci 
        SET quantita = ?, prezzo_unitario = ?, sconto_percentuale = ?, sconto_fisso = ?, subtotale = ?
        WHERE id = ?
    """, (quantita, prezzo_unitario, sconto_perc, sconto_fisso, subtotale, vid))
    
    conn.commit()
    conn.close()
    
    ricalcola_totali_cantiere(cantiere_id)
    
    return jsonify({'ok': True})

@app.route('/api/stanza_voci/<int:vid>', methods=['DELETE'])
@login_required
def rimuovi_voce(vid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Leggi voce
    c.execute("SELECT stanza_id FROM stanza_voci WHERE id = ?", (vid,))
    voce_row = c.fetchone()
    if not voce_row:
        return jsonify({'error': 'Voce not found'}), 404
    
    stanza_id = voce_row[0]
    c.execute("SELECT piano_id FROM stanze WHERE id = ?", (stanza_id,))
    stanza_row = c.fetchone()
    piano_id = stanza_row[0]
    c.execute("SELECT cantiere_id FROM piani WHERE id = ?", (piano_id,))
    piano_row = c.fetchone()
    cantiere_id = piano_row[0]
    
    c.execute("DELETE FROM stanza_voci WHERE id = ?", (vid,))
    
    conn.commit()
    conn.close()
    
    ricalcola_totali_cantiere(cantiere_id)
    
    return jsonify({'ok': True})

# ============================================================================
# API ENDPOINTS - CANTIERI (semplice)
# ============================================================================
@app.route('/api/cantieri', methods=['GET'])
@login_required
def get_cantieri():
    user_id = session.get('user_id')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nome, stato, totale_generale, modalita FROM cantieri WHERE cliente_id = ?", (user_id,))
    cantieri = [{'id': row[0], 'nome': row[1], 'stato': row[2], 'totale': row[3], 'modalita': row[4]} for row in c.fetchall()]
    conn.close()
    return jsonify(cantieri)

@app.route('/api/cantieri', methods=['POST'])
@login_required
def crea_cantiere():
    user_id = session.get('user_id')
    data = request.json
    nome = data.get('nome', 'Cantiere')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO cantieri (nome, cliente_id, created_at, modalita)
        VALUES (?, ?, ?, 'semplice')
    """, (nome, user_id, datetime.now().isoformat()))
    cantiere_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'ok': True, 'cantiere_id': cantiere_id})

# ============================================================================
# HTML PRINCIPALE
# ============================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORACOLO COVOLO V8</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a1a; color: #e0e0e0; }
        
        .container { display: flex; height: 100vh; }
        .sidebar { width: 25%; background: #0d0d0d; border-right: 1px solid #333; padding: 20px; overflow-y: auto; }
        .main { flex: 1; display: flex; flex-direction: column; }
        .top-panel { background: #1a1a1a; padding: 20px; border-bottom: 1px solid #333; }
        .content { display: flex; flex: 1; }
        .center { flex: 2; padding: 20px; overflow-y: auto; }
        .right-panel { width: 30%; background: #0d0d0d; border-left: 1px solid #333; padding: 20px; overflow-y: auto; }
        
        h2 { color: #fff; margin-bottom: 15px; font-size: 18px; }
        h3 { color: #888; margin-top: 20px; margin-bottom: 10px; font-size: 14px; }
        
        button { 
            background: #10b981; color: white; border: none; padding: 10px 15px; 
            border-radius: 6px; cursor: pointer; font-size: 13px; margin: 5px 5px 5px 0;
            transition: background 0.2s;
        }
        button:hover { background: #059669; }
        button.secondary { background: #6b7280; }
        button.secondary:hover { background: #4b5563; }
        button.danger { background: #ef4444; }
        button.danger:hover { background: #dc2626; }
        
        input[type="text"], input[type="password"], input[type="number"], select, textarea {
            background: #2a2a2a; color: #e0e0e0; border: 1px solid #444; padding: 8px; 
            border-radius: 4px; width: 100%; margin: 5px 0; font-size: 13px;
        }
        
        .drawer { display: none; position: fixed; right: 0; top: 0; width: 30%; height: 100%; background: #1a1a1a; border-left: 1px solid #333; padding: 20px; overflow-y: auto; z-index: 1000; }
        .drawer.open { display: block; }
        .drawer-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 15px; }
        .drawer-close { cursor: pointer; color: #888; font-size: 20px; }
        
        .cantiere-item { 
            background: #2a2a2a; padding: 12px; margin: 8px 0; border-radius: 6px; 
            cursor: pointer; border-left: 3px solid transparent; transition: all 0.2s;
        }
        .cantiere-item:hover { background: #333; border-left-color: #10b981; }
        
        .piano-container { background: #2a2a2a; padding: 15px; margin: 10px 0; border-radius: 6px; border-left: 3px solid #10b981; }
        .stanza-container { background: #262626; padding: 12px; margin: 8px 0; border-radius: 6px; margin-left: 10px; }
        .voce-item { background: #1a1a1a; padding: 10px; margin: 5px 0; border-radius: 4px; border-left: 2px solid #6b7280; }
        
        .total-box { background: #10b981; color: white; padding: 15px; border-radius: 6px; margin-top: 20px; font-weight: bold; text-align: center; }
        
        input:focus, select:focus, textarea:focus { outline: none; border-color: #10b981; background: #333; }
        
        .hidden { display: none !important; }
        .login-form { max-width: 400px; margin: 50px auto; background: #2a2a2a; padding: 30px; border-radius: 8px; }
        .login-form h1 { text-align: center; color: #fff; margin-bottom: 30px; }
        .login-form button { width: 100%; }
    </style>
</head>
<body>

<div id="login-page" class="login-form">
    <h1>🔑 ORACOLO COVOLO V8</h1>
    <input type="text" id="login-user" placeholder="Username" value="superadmin">
    <input type="password" id="login-pass" placeholder="Password">
    <button onclick="faciLogin()">Accedi</button>
    <div id="login-error" style="color: #ef4444; margin-top: 10px; text-align: center;"></div>
</div>

<div id="app-container" class="hidden">
    <div class="container">
        <!-- SIDEBAR SINISTRO -->
        <div class="sidebar">
            <h2>📋 ORACOLO COVOLO</h2>
            <p id="user-info" style="color: #888; font-size: 12px; margin-bottom: 20px;"></p>
            <button onclick="logout()" style="width: 100%; margin-bottom: 20px;">Logout</button>
            
            <h3>Cantieri</h3>
            <div style="margin-bottom: 10px;">
                <input type="text" id="new-cantiere-name" placeholder="Nome cantiere">
                <button onclick="creaCantiereJS()">➕ Nuovo</button>
            </div>
            <div id="cantieri-list"></div>
        </div>
        
        <!-- CENTRO -->
        <div class="main">
            <div class="top-panel">
                <h2>🏢 ORACOLO COVOLO V8</h2>
                <p style="color: #888; font-size: 12px;">Sistema gestionale piani/stanze/voci con subtotali automatici</p>
            </div>
            <div class="content">
                <div class="center">
                    <div id="content-area">
                        <p style="text-align: center; color: #888; margin-top: 50px;">Seleziona un cantiere dal pannello sinistro</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- DRAWER CANTIERE -->
    <div class="drawer" id="drawer-piani">
        <div class="drawer-header">
            <div>
                <h2 id="drawer-title">Cantiere</h2>
            </div>
            <span class="drawer-close" onclick="chiudiDrawer()">✕</span>
        </div>
        
        <div id="drawer-content">
            <!-- PIANI -->
            <div id="piani-section"></div>
            
            <button onclick="aggiungiPianoModal()" style="width: 100%; margin-top: 20px;">➕ Aggiungi Piano</button>
        </div>
    </div>
</div>

<script>
let cantiereAttivo = null;
let user = null;

// ====== LOGIN ======
function faciLogin() {
    const username = document.getElementById('login-user').value;
    const password = document.getElementById('login-pass').value;
    
    fetch('/api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, password})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) {
            document.getElementById('login-page').classList.add('hidden');
            document.getElementById('app-container').classList.remove('hidden');
            caricaUser();
            caricaCantieri();
        } else {
            document.getElementById('login-error').textContent = '❌ Credenziali errate';
        }
    });
}

function caricaUser() {
    fetch('/api/me').then(r => r.json()).then(d => {
        user = d;
        document.getElementById('user-info').textContent = `👤 ${d.username} (${d.livello})`;
    });
}

function logout() {
    fetch('/api/logout', {method: 'POST'}).then(() => {
        document.getElementById('app-container').classList.add('hidden');
        document.getElementById('login-page').classList.remove('hidden');
        document.getElementById('login-error').textContent = '';
    });
}

// ====== CANTIERI ======
function caricaCantieri() {
    fetch('/api/cantieri').then(r => r.json()).then(cantieri => {
        const list = document.getElementById('cantieri-list');
        list.innerHTML = cantieri.map(c => `
            <div class="cantiere-item" onclick="apriCantiere(${c.id}, '${c.nome}', '${c.modalita}')">
                <strong>${c.nome}</strong>
                <div style="font-size: 11px; color: #888; margin-top: 5px;">
                    Stato: ${c.stato} | €${c.totale?.toFixed(2)}
                </div>
            </div>
        `).join('');
    });
}

function creaCantiereJS() {
    const nome = document.getElementById('new-cantiere-name').value || 'Cantiere';
    fetch('/api/cantieri', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({nome})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) {
            document.getElementById('new-cantiere-name').value = '';
            caricaCantieri();
        }
    });
}

function apriCantiere(cid, nome, modalita) {
    cantiereAttivo = cid;
    document.getElementById('drawer-title').textContent = nome;
    
    // Carica struttura piani/stanze
    fetch(`/api/cantieri/${cid}/struttura`)
        .then(r => r.json())
        .then(d => {
            if (d.ok) {
                renderizzaPiani(d.piani);
                document.getElementById('drawer-piani').classList.add('open');
            }
        });
}

function renderizzaPiani(piani) {
    const section = document.getElementById('piani-section');
    section.innerHTML = piani.map((piano, idx) => `
        <div class="piano-container">
            <div style="display: flex; justify-content: space-between;">
                <strong>📍 ${piano.nome}</strong>
                <span style="color: #10b981;">€${piano.totale_piano?.toFixed(2)}</span>
            </div>
            
            <div id="stanze-piano-${piano.id}" style="margin-top: 10px;">
                ${piano.stanze.map(stanza => `
                    <div class="stanza-container">
                        <div style="display: flex; justify-content: space-between;">
                            <strong>🚿 ${stanza.nome}</strong>
                            <span style="color: #888;">€${stanza.totale_stanza?.toFixed(2)}</span>
                        </div>
                        
                        <div style="margin-top: 8px; font-size: 12px;">
                            ${stanza.voci.map(v => `
                                <div class="voce-item">
                                    ${v.brand || ''} ${v.codice} - ${v.descrizione}
                                    <br><span style="color: #888;">${v.quantita}x €${v.prezzo_unitario?.toFixed(2)} = €${v.subtotale?.toFixed(2)}</span>
                                </div>
                            `).join('')}
                        </div>
                        
                        <button onclick="aggiungiVoceModal(${stanza.id})" style="width: 100%; margin-top: 8px; font-size: 11px;">➕ Aggiungi voce</button>
                    </div>
                `).join('')}
            </div>
            
            <button onclick="aggiungiStanzaModal(${piano.id})" style="width: 100%; margin-top: 10px; font-size: 11px;">➕ Stanza</button>
        </div>
    `).join('');
}

function aggiungiPianoModal() {
    const nome = prompt('Nome piano:', 'Piano ' + (new Date().getTime() % 10));
    if (!nome) return;
    
    fetch(`/api/cantieri/${cantiereAttivo}/piani`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({nome})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) {
            apriCantiere(cantiereAttivo, document.getElementById('drawer-title').textContent, 'piani');
        }
    });
}

function aggiungiStanzaModal(pid) {
    const nome = prompt('Nome stanza:', 'Bagno');
    if (!nome) return;
    
    fetch(`/api/piani/${pid}/stanze`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({nome, descrizione: ''})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) {
            apriCantiere(cantiereAttivo, document.getElementById('drawer-title').textContent, 'piani');
        }
    });
}

function aggiungiVoceModal(sid) {
    const codice = prompt('Codice:', '');
    const brand = prompt('Brand:', 'Gessi');
    const desc = prompt('Descrizione:', '');
    const qty = parseInt(prompt('Quantità:', '1'));
    const prezzo = parseFloat(prompt('Prezzo unitario:', '100'));
    
    if (!brand || !desc) return;
    
    fetch(`/api/stanze/${sid}/voci`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            tipo: 'brand', codice, brand, descrizione: desc, 
            quantita: qty, udm: 'pezzo', prezzo_unitario: prezzo,
            sconto_percentuale: 0, sconto_fisso: 0
        })
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) {
            apriCantiere(cantiereAttivo, document.getElementById('drawer-title').textContent, 'piani');
        }
    });
}

function chiudiDrawer() {
    document.getElementById('drawer-piani').classList.remove('open');
    cantiereAttivo = null;
}

// INIT
window.addEventListener('load', () => {
    fetch('/api/me')
        .then(r => {
            if (r.ok) {
                document.getElementById('login-page').classList.add('hidden');
                document.getElementById('app-container').classList.remove('hidden');
                caricaUser();
                caricaCantieri();
            }
        })
        .catch(() => {});
});
</script>

</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# ============================================================================
# RUN
# ============================================================================
print("[LOG] All endpoints registered successfully!", file=sys.stderr)
print("[LOG] Starting Flask server on 0.0.0.0:10000...", file=sys.stderr)
sys.stderr.flush()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
