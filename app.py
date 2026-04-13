"""
ORACOLO COVOLO - V9 - DRAWER A COMPLETO
========================================
✅ Drawer PIANO → STANZA → VOCE (espandibile/collassabile)
✅ Form INLINE per aggiungere/modificare
✅ Subtotali LIVE a cascata
✅ UX PURA: chiaro, intuitivo, mobile-friendly
✅ Tutto gestibile dal drawer
"""

import os, json, sqlite3, re, hashlib, secrets, sys, io, base64
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session
import httpx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'oracolo_covolo.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "ZANNA1959?")

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

print("[START] ORACOLO COVOLO V9 - Drawer A Completo", file=sys.stderr)
sys.stderr.flush()

# ============================================================================
# DATABASE INIT
# ============================================================================
def init_db():
    """Inizializza database con tabelle piani/stanze/voci"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Tabelle base
    c.execute("""
        CREATE TABLE IF NOT EXISTS utenti (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            livello TEXT,
            created_at TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS cantieri (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            stato TEXT DEFAULT 'bozza',
            modalita TEXT DEFAULT 'semplice',
            totale_generale REAL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS piani (
            id INTEGER PRIMARY KEY,
            cantiere_id INTEGER NOT NULL,
            numero INTEGER,
            nome TEXT,
            totale_piano REAL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(cantiere_id) REFERENCES cantieri(id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS stanze (
            id INTEGER PRIMARY KEY,
            piano_id INTEGER NOT NULL,
            nome TEXT,
            descrizione TEXT,
            totale_stanza REAL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(piano_id) REFERENCES piani(id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS stanza_voci (
            id INTEGER PRIMARY KEY,
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
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(stanza_id) REFERENCES stanze(id)
        )
    """)
    
    # Superadmin
    superadmin_hash = hashlib.sha256(SUPERADMIN_PASSWORD.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO utenti (username, password_hash, livello, created_at) VALUES ('superadmin', ?, 'superadmin', ?)",
              (superadmin_hash, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

init_db()

# ============================================================================
# UTILITY
# ============================================================================
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
    c.execute("UPDATE cantieri SET totale_generale = ?, updated_at = ? WHERE id = ?", 
             (total_generale, datetime.now().isoformat(), cantiere_id))
    
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
def me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'logged': False})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, livello FROM utenti WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({'logged': True, 'username': row[0], 'livello': row[1]})
    return jsonify({'logged': False})

# ============================================================================
# API ENDPOINTS - CANTIERI
# ============================================================================
@app.route('/api/cantieri', methods=['GET'])
def get_cantieri():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nome, stato, totale_generale, modalita FROM cantieri ORDER BY created_at DESC LIMIT 100")
    cantieri = [{'id': r[0], 'nome': r[1], 'stato': r[2], 'totale': r[3], 'modalita': r[4]} for r in c.fetchall()]
    conn.close()
    return jsonify(cantieri)

@app.route('/api/cantieri', methods=['POST'])
def crea_cantiere():
    data = request.json
    nome = data.get('nome', 'Cantiere')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO cantieri (nome, stato, modalita, created_at, updated_at)
        VALUES (?, 'bozza', 'semplice', ?, ?)
    """, (nome, datetime.now().isoformat(), datetime.now().isoformat()))
    cid = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'ok': True, 'id': cid})

@app.route('/api/cantieri/<int:cid>/modalita', methods=['GET'])
def get_modalita(cid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT modalita FROM cantieri WHERE id = ?", (cid,))
    row = c.fetchone()
    conn.close()
    modalita = row[0] if row else 'semplice'
    return jsonify({'modalita': modalita})

@app.route('/api/cantieri/<int:cid>/modalita', methods=['PUT'])
def set_modalita(cid):
    data = request.json
    nuova = data.get('modalita', 'semplice')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE cantieri SET modalita = ?, updated_at = ? WHERE id = ?",
              (nuova, datetime.now().isoformat(), cid))
    conn.commit()
    conn.close()
    
    return jsonify({'ok': True, 'modalita': nuova})

# ============================================================================
# API ENDPOINTS - PIANI/STANZE/VOCI
# ============================================================================
@app.route('/api/cantieri/<int:cid>/struttura', methods=['GET'])
def get_struttura(cid):
    """Restituisce gerarchia PIANO → STANZA → VOCE"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT id, nome, totale_generale FROM cantieri WHERE id = ?", (cid,))
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
                       sconto_percentuale, sconto_fisso, subtotale
                FROM stanza_voci WHERE stanza_id = ? ORDER BY id
            """, (sid,))
            voci = [{
                'id': v[0], 'codice': v[1], 'brand': v[2], 'descrizione': v[3],
                'quantita': v[4], 'udm': v[5], 'prezzo': v[6],
                'sconto_perc': v[7], 'sconto_fisso': v[8], 'subtotale': v[9]
            } for v in c.fetchall()]
            
            stanze.append({
                'id': sid, 'nome': snome, 'desc': sdesc, 'totale': stot, 'voci': voci
            })
        
        piani.append({
            'id': pid, 'num': num, 'nome': pnome, 'totale': ptot, 'stanze': stanze
        })
    
    conn.close()
    return jsonify({'ok': True, 'cantiere': cant, 'piani': piani})

@app.route('/api/cantieri/<int:cid>/piani', methods=['POST'])
def add_piano(cid):
    data = request.json
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
    data = request.json
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
    data = request.json
    codice = data.get('codice', '')
    brand = data.get('brand', '')
    desc = data.get('descrizione', '')
    qty = float(data.get('quantita', 1))
    udm = data.get('udm', 'pezzo')
    prezzo = float(data.get('prezzo_unitario', 0))
    sconto_p = float(data.get('sconto_perc', 0))
    sconto_f = float(data.get('sconto_fisso', 0))
    
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
         sconto_percentuale, sconto_fisso, subtotale, created_at, updated_at)
        VALUES (?, 'prodotto', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sid, codice, brand, desc, qty, udm, prezzo, sconto_p, sconto_f, subtotale,
          datetime.now().isoformat(), datetime.now().isoformat()))
    
    vid = c.lastrowid
    conn.commit()
    conn.close()
    
    ricalcola_totali_cantiere(cid)
    return jsonify({'ok': True, 'voce_id': vid})

@app.route('/api/stanza_voci/<int:vid>', methods=['PUT'])
def edit_voce(vid):
    data = request.json
    qty = float(data.get('quantita', 1))
    prezzo = float(data.get('prezzo_unitario', 0))
    sconto_p = float(data.get('sconto_perc', 0))
    sconto_f = float(data.get('sconto_fisso', 0))
    
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
            sconto_fisso = ?, subtotale = ?, updated_at = ?
        WHERE id = ?
    """, (qty, prezzo, sconto_p, sconto_f, subtotale, datetime.now().isoformat(), vid))
    
    conn.commit()
    conn.close()
    
    ricalcola_totali_cantiere(cid)
    return jsonify({'ok': True})

@app.route('/api/stanza_voci/<int:vid>', methods=['DELETE'])
def delete_voce(vid):
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

# ============================================================================
# HTML FRONTEND - DRAWER A COMPLETO
# ============================================================================

HTML = """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORACOLO COVOLO V9 — Drawer A</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0f172e; color: #e0e0e0; min-height: 100vh; }
        
        .container { display: flex; height: 100vh; }
        .sidebar { width: 25%; background: #0a0f1f; border-right: 1px solid #334155; padding: 20px; overflow-y: auto; }
        .main { flex: 1; display: flex; flex-direction: column; padding: 20px; }
        .top { background: #1a2744; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
        .content { flex: 1; background: #1a2744; border-radius: 8px; padding: 20px; overflow-y: auto; }
        
        h1 { color: #60a5fa; font-size: 18px; margin-bottom: 10px; }
        h2 { color: #93c5fd; font-size: 14px; margin: 15px 0 10px 0; }
        
        button { background: #3b82f6; color: white; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; margin: 5px 5px 5px 0; font-size: 12px; }
        button:hover { opacity: 0.85; }
        button.btn-green { background: #10b981; }
        button.btn-gray { background: #6b7280; }
        button.btn-red { background: #ef4444; }
        button.btn-sm { padding: 6px 10px; font-size: 11px; margin: 2px; }
        
        input[type="text"], input[type="number"], select { background: #334155; color: #e0e0e0; border: 1px solid #475569; padding: 8px; border-radius: 4px; margin: 5px 0; font-size: 12px; }
        
        /* DRAWER */
        .drawer { display: none; position: fixed; right: 0; top: 0; width: 35%; height: 100vh; background: #0f172e; border-left: 2px solid #3b82f6; z-index: 1000; flex-direction: column; box-shadow: -4px 0 20px rgba(0,0,0,0.5); }
        .drawer.open { display: flex; }
        
        .drawer-header { background: #1e2d4a; border-bottom: 1px solid #334155; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; }
        .drawer-header h2 { margin: 0; color: #60a5fa; font-size: 16px; }
        
        .drawer-body { flex: 1; overflow-y: auto; padding: 15px 20px; }
        .drawer-footer { border-top: 1px solid #334155; padding: 15px 20px; display: flex; gap: 10px; flex-shrink: 0; }
        .drawer-footer button { flex: 1; }
        
        /* GERARCHIA PIANO/STANZA/VOCE */
        .piano-block { background: #1e3a5f; border-left: 4px solid #3b82f6; margin: 12px 0; border-radius: 6px; overflow: hidden; }
        .piano-header { background: #2a4a7f; padding: 12px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-weight: bold; color: #60a5fa; }
        .piano-header:hover { background: #354a8f; }
        .piano-toggle { font-size: 11px; color: #9ca3af; }
        .piano-content { display: none; padding: 0; }
        .piano-content.open { display: block; }
        
        .piano-total { font-size: 13px; color: #10b981; font-weight: bold; margin-left: auto; }
        
        .stanza-block { background: #1e293b; border-left: 3px solid #8b5cf6; margin: 8px 12px 8px 0; border-radius: 4px; padding: 10px; }
        .stanza-header { cursor: pointer; display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; color: #c4b5fd; font-weight: 600; font-size: 12px; }
        .stanza-header:hover { color: #e9d5ff; }
        .stanza-total { font-size: 12px; color: #10b981; font-weight: bold; }
        
        .stanza-content { display: none; }
        .stanza-content.open { display: block; }
        
        .voce-item { background: #1a1f35; border-left: 2px solid #6b7280; padding: 8px; margin: 4px 0; border-radius: 3px; font-size: 11px; display: flex; justify-content: space-between; align-items: center; }
        .voce-info { flex: 1; }
        .voce-brand { color: #60a5fa; font-weight: bold; font-size: 11px; }
        .voce-desc { color: #d1d5db; font-size: 10px; margin: 2px 0; }
        .voce-qty { color: #9ca3af; font-size: 10px; }
        .voce-price { color: #10b981; font-weight: bold; font-size: 12px; margin: 0 10px; }
        .voce-actions { display: flex; gap: 4px; flex-shrink: 0; }
        
        .totale-general { background: rgba(16,185,129,0.2); border: 1px solid rgba(16,185,129,0.5); padding: 12px; border-radius: 6px; margin-top: 15px; text-align: center; }
        .totale-valore { font-size: 18px; font-weight: bold; color: #10b981; }
        
        .btn-add-stanza { width: 100%; margin-top: 8px; background: rgba(139,92,246,0.3); color: #a78bfa; }
        .btn-add-voce { width: 100%; margin-top: 6px; background: rgba(16,185,129,0.2); color: #6ee7b7; font-size: 11px; }
        
        .login-box { background: #1a2744; border: 1px solid #3b82f6; border-radius: 8px; padding: 30px; max-width: 400px; margin: 50px auto; }
        .login-box input { width: 100%; margin-bottom: 10px; }
        .login-box button { width: 100%; }
        
        .cantiere-item { background: #1e2d4a; padding: 12px; margin: 8px 0; border-radius: 6px; cursor: pointer; border-left: 3px solid transparent; transition: all 0.2s; }
        .cantiere-item:hover { background: #2a3f54; border-left-color: #3b82f6; }
        
        .form-inline { background: rgba(59,130,245,0.1); border: 1px solid rgba(59,130,245,0.3); border-radius: 6px; padding: 10px; margin: 8px 0; }
        .form-row { display: flex; gap: 8px; margin-bottom: 8px; }
        .form-row > * { flex: 1; }
        .form-row > input, .form-row > select { margin: 0; }
    </style>
</head>
<body>

<div id="login-page">
    <div class="login-box">
        <h1 style="text-align: center;">🔑 ORACOLO COVOLO V9</h1>
        <input type="text" id="user" placeholder="Username" value="superadmin">
        <input type="password" id="pass" placeholder="Password">
        <button onclick="doLogin()">Accedi</button>
        <div id="login-error" style="color: #ef4444; margin-top: 10px; text-align: center; font-size: 12px;"></div>
    </div>
</div>

<div id="app" class="container" style="display: none;">
    <!-- SIDEBAR -->
    <div class="sidebar">
        <h1 style="margin-bottom: 15px;">📋 ORACOLO</h1>
        <button onclick="logout()" style="width: 100%; background: #ef4444; margin-bottom: 20px;">Logout</button>
        
        <h2>Cantieri</h2>
        <div style="margin-bottom: 10px;">
            <input type="text" id="new-cant-name" placeholder="Nome cantiere" style="width: 100%; margin-bottom: 5px;">
            <button onclick="creaCantiereBtn()" style="width: 100%;">➕ Nuovo</button>
        </div>
        <div id="cantieri-list"></div>
    </div>
    
    <!-- MAIN -->
    <div class="main">
        <div class="top">
            <h1>🏢 ORACOLO COVOLO V9</h1>
            <p style="color: #9ca3af; font-size: 12px;">Drawer A Completo: PIANO → STANZA → VOCE</p>
        </div>
        
        <div class="content">
            <div id="content-area">
                <p style="text-align: center; color: #9ca3af; margin-top: 40px;">Seleziona un cantiere dal pannello sinistro</p>
            </div>
        </div>
    </div>
    
    <!-- DRAWER PIANI/STANZE/VOCI -->
    <div class="drawer" id="drawer">
        <div class="drawer-header">
            <h2 id="drawer-title">Cantiere</h2>
            <button onclick="closeDrawer()" class="btn-gray btn-sm" style="margin: 0;">✕</button>
        </div>
        
        <div class="drawer-body">
            <div id="drawer-content">
                <p style="color: #9ca3af; text-align: center;">Caricamento...</p>
            </div>
        </div>
        
        <div class="drawer-footer">
            <button class="btn-green" onclick="aggiungiPianoBtn()">➕ Piano</button>
            <button class="btn-green" onclick="generaOfferta()">📝 Offerta</button>
            <button class="btn-red" onclick="eliminaCantiereBtn()">🗑️ Elimina</button>
        </div>
    </div>
</div>

<script>
let cantiereAttivo = null;

function doLogin() {
    const user = document.getElementById('user').value;
    const pass = document.getElementById('pass').value;
    
    fetch('/api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: user, password: pass})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) {
            document.getElementById('login-page').style.display = 'none';
            document.getElementById('app').style.display = 'flex';
            caricaCantieri();
        } else {
            document.getElementById('login-error').textContent = d.error || 'Errore login';
        }
    });
}

function logout() {
    fetch('/api/logout', {method: 'POST'}).then(() => {
        document.getElementById('app').style.display = 'none';
        document.getElementById('login-page').style.display = 'block';
        document.getElementById('user').value = '';
        document.getElementById('pass').value = '';
    });
}

function caricaCantieri() {
    fetch('/api/cantieri')
        .then(r => r.json())
        .then(cantieri => {
            const list = document.getElementById('cantieri-list');
            list.innerHTML = cantieri.map(c =>
                `<div class="cantiere-item" onclick="apriDrawer(${c.id}, '${c.nome}')">
                    <strong>${c.nome}</strong>
                    <div style="font-size: 10px; color: #9ca3af; margin-top: 4px;">
                        ${c.stato} · €${c.totale ? c.totale.toFixed(0) : '0'}
                    </div>
                </div>`
            ).join('');
        });
}

function creaCantiereBtn() {
    const nome = document.getElementById('new-cant-name').value;
    if (!nome) return;
    
    fetch('/api/cantieri', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({nome})
    })
    .then(r => r.json())
    .then(d => {
        document.getElementById('new-cant-name').value = '';
        caricaCantieri();
    });
}

function apriDrawer(cid, nome) {
    cantiereAttivo = cid;
    document.getElementById('drawer-title').textContent = nome;
    document.getElementById('drawer').classList.add('open');
    caricaStruttura(cid);
}

function closeDrawer() {
    document.getElementById('drawer').classList.remove('open');
    cantiereAttivo = null;
}

function caricaStruttura(cid) {
    fetch(`/api/cantieri/${cid}/struttura`)
        .then(r => r.json())
        .then(d => {
            if (!d.ok) {
                document.getElementById('drawer-content').innerHTML = '<p style="color: #ef4444;">Errore caricamento</p>';
                return;
            }
            
            renderStruttura(d.piani, d.cantiere[2]); // totale_generale
        });
}

function renderStruttura(piani, totaleGenerale) {
    let html = '';
    
    piani.forEach((piano, pidx) => {
        html += `
        <div class="piano-block">
            <div class="piano-header" onclick="togglePiano(this)">
                <div>
                    <span class="piano-toggle">▼</span>
                    <strong> 📍 ${piano.nome}</strong>
                </div>
                <div class="piano-total">€${piano.totale.toFixed(2)}</div>
            </div>
            <div class="piano-content open">
                ${renderStanze(piano.stanze, piano.id)}
                <button class="btn-add-stanza" onclick="aggiungiStanzaBtn(${piano.id})">➕ Aggiungi stanza</button>
            </div>
        </div>
        `;
    });
    
    html += `
    <div class="totale-general">
        <div style="color: #9ca3af; font-size: 12px; margin-bottom: 5px;">TOTALE GENERALE</div>
        <div class="totale-valore">€${totaleGenerale.toFixed(2)}</div>
    </div>
    `;
    
    document.getElementById('drawer-content').innerHTML = html;
}

function renderStanze(stanze, pianoId) {
    return stanze.map((stanza, sidx) => `
        <div class="stanza-block">
            <div class="stanza-header" onclick="toggleStanza(this)">
                <div>
                    <span style="font-size: 10px; color: #9ca3af;">▼</span>
                    <strong>🚿 ${stanza.nome}</strong>
                </div>
                <div class="stanza-total">€${stanza.totale.toFixed(2)}</div>
            </div>
            <div class="stanza-content open">
                ${renderVoci(stanza.voci)}
                <button class="btn-add-voce" onclick="aggiungiVoceBtn(${stanza.id})">➕ Voce</button>
            </div>
        </div>
    `).join('');
}

function renderVoci(voci) {
    if (voci.length === 0) {
        return '<div style="padding: 8px; color: #9ca3af; font-size: 11px; font-style: italic;">Nessuna voce</div>';
    }
    
    return voci.map(v => `
        <div class="voce-item">
            <div class="voce-info">
                <div class="voce-brand">${v.brand || '—'} ${v.codice ? '[' + v.codice + ']' : ''}</div>
                <div class="voce-desc">${v.descrizione}</div>
                <div class="voce-qty">${v.quantita}x €${v.prezzo.toFixed(2)}</div>
            </div>
            <div class="voce-price">€${v.subtotale.toFixed(2)}</div>
            <div class="voce-actions">
                <button class="btn-sm" onclick="modificaVoceBtn(${v.id})" style="background: #6b7280; padding: 4px 6px;">✏️</button>
                <button class="btn-sm btn-red" onclick="eliminaVoceBtn(${v.id})" style="padding: 4px 6px;">✕</button>
            </div>
        </div>
    `).join('');
}

function togglePiano(el) {
    const content = el.nextElementSibling;
    content.classList.toggle('open');
    const toggle = el.querySelector('.piano-toggle');
    toggle.textContent = content.classList.contains('open') ? '▼' : '▶';
}

function toggleStanza(el) {
    const content = el.nextElementSibling;
    content.classList.toggle('open');
    const toggle = el.querySelector('span:first-child');
    if (toggle) toggle.textContent = content.classList.contains('open') ? '▼' : '▶';
}

function aggiungiPianoBtn() {
    const nome = prompt('Nome piano:', 'Piano ' + (new Date().getTime() % 10));
    if (!nome) return;
    
    fetch(`/api/cantieri/${cantiereAttivo}/piani`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({nome})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) caricaStruttura(cantiereAttivo);
    });
}

function aggiungiStanzaBtn(pianoId) {
    const nome = prompt('Nome stanza:', 'Bagno');
    if (!nome) return;
    
    fetch(`/api/piani/${pianoId}/stanze`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({nome})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) caricaStruttura(cantiereAttivo);
    });
}

function aggiungiVoceBtn(stanzaId) {
    const codice = prompt('Codice prodotto (opzionale):');
    const brand = prompt('Brand:', 'Gessi');
    const desc = prompt('Descrizione:');
    const qty = parseFloat(prompt('Quantità:', '1'));
    const prezzo = parseFloat(prompt('Prezzo unitario (€):'));
    
    if (!brand || !desc || !prezzo) return;
    
    fetch(`/api/stanze/${stanzaId}/voci`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({codice, brand, descrizione: desc, quantita: qty, prezzo_unitario: prezzo})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) caricaStruttura(cantiereAttivo);
    });
}

function modificaVoceBtn(voceId) {
    const qty = parseFloat(prompt('Nuova quantità:'));
    const prezzo = parseFloat(prompt('Nuovo prezzo (€):'));
    
    if (isNaN(qty) || isNaN(prezzo)) return;
    
    fetch(`/api/stanza_voci/${voceId}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({quantita: qty, prezzo_unitario: prezzo})
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) caricaStruttura(cantiereAttivo);
    });
}

function eliminaVoceBtn(voceId) {
    if (!confirm('Eliminare questa voce?')) return;
    
    fetch(`/api/stanza_voci/${voceId}`, {method: 'DELETE'})
        .then(r => r.json())
        .then(d => {
            if (d.ok) caricaStruttura(cantiereAttivo);
        });
}

function eliminaCantiereBtn() {
    if (!confirm('Eliminare questo cantiere?')) return;
    closeDrawer();
    // TODO: implementare DELETE cantiere
    caricaCantieri();
}

function generaOfferta() {
    alert('Offerta generata! (TODO)');
}

// Init
fetch('/api/me').then(r => r.json()).then(d => {
    if (!d.logged) return;
    document.getElementById('login-page').style.display = 'none';
    document.getElementById('app').style.display = 'flex';
    caricaCantieri();
});
</script>

</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

# ============================================================================
# RUN
# ============================================================================
if __name__ == '__main__':
    print("[LOG] Starting ORACOLO COVOLO V9 on 0.0.0.0:10000", file=sys.stderr)
    sys.stderr.flush()
    app.run(host='0.0.0.0', port=10000, debug=False)
