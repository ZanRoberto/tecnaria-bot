"""
ORACOLO COVOLO - WEB FALLBACK AUTOMATICO
=========================================
Se non trova documenti, cerca automaticamente su web
"""

import os
import json
import sqlite3
import base64
import re
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
import httpx
from urllib.parse import quote

from macrorule_engine import MacroruleEngine
from narrator_system import NarratorSystem

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "oracolo_covolo.db")
MACRORULE_FILE = os.path.join(BASE_DIR, "macroregole_covolo_universe.json")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

macrorule_engine = MacroruleEngine(MACRORULE_FILE)
narrator = NarratorSystem()

def init_covolo_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS aziende
                 (id INTEGER PRIMARY KEY,
                  nome TEXT UNIQUE,
                  suffisso TEXT,
                  sito TEXT,
                  categoria TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id INTEGER PRIMARY KEY,
                  filename TEXT UNIQUE,
                  content TEXT,
                  azienda_id INTEGER,
                  upload_date TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS queries
                 (id INTEGER PRIMARY KEY,
                  question TEXT,
                  answer TEXT,
                  azienda_ids TEXT,
                  timestamp TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS presets
                 (id INTEGER PRIMARY KEY,
                  nome TEXT UNIQUE,
                  azienda_ids TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    aziende = [
        (1, "Gessi", "rubinetteria", "https://www.gessi.com", "Rubinetteria"),
        (2, "Ideal Standard", "sanitari", "https://www.idealstandard.com", "Sanitari"),
        (3, "Duravit", "ceramica", "https://www.duravit.com", "Ceramica"),
        (4, "Villeroy&Boch", "piastrelle", "https://www.villeroy-boch.com", "Piastrelle"),
        (5, "Grohe", "rubinetteria", "https://www.grohe.com", "Rubinetteria"),
        (6, "Hansgrohe", "rubinetteria", "https://www.hansgrohe.com", "Rubinetteria"),
    ]
    
    for aid, nome, suffisso, sito, categoria in aziende:
        try:
            c.execute('INSERT INTO aziende (id, nome, suffisso, sito, categoria) VALUES (?, ?, ?, ?, ?)',
                      (aid, nome, suffisso, sito, categoria))
        except:
            pass
    
    conn.commit()
    conn.close()

init_covolo_db()
app = Flask(__name__)

def search_web_bing(query):
    """Cerca su Bing e restituisce risultati."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        url = f"https://www.bing.com/search?q={quote(query)}"
        response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        
        if response.status_code == 200:
            # Estrai snippet dai risultati
            snippets = re.findall(r'<p[^>]*>(.*?)</p>', response.text)
            cleaned = []
            for s in snippets[:5]:
                text = re.sub(r'<[^>]+>', '', s)
                if len(text) > 50:
                    cleaned.append(text)
            
            return " ".join(cleaned[:3])
        return ""
    except:
        return ""

def search_product_images(product_name, azienda_nome=""):
    """Cerca immagini del prodotto."""
    try:
        query = f"{product_name} {azienda_nome}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        url = f"https://www.bing.com/images/search?q={quote(query)}"
        response = httpx.get(url, headers=headers, timeout=5, follow_redirects=True)
        
        images = []
        if response.status_code == 200:
            img_urls = re.findall(r'murl":"([^"]+\.jpg)"', response.text)
            
            for img_url in img_urls[:3]:
                try:
                    img_response = httpx.get(img_url, timeout=3, headers=headers)
                    if img_response.status_code == 200:
                        img_base64 = base64.b64encode(img_response.content).decode('utf-8')
                        images.append(img_base64)
                except:
                    pass
        
        return images
    except:
        return []

def extract_product_names(answer_text):
    """Estrae nomi prodotti dalla risposta."""
    products = []
    
    gessi_pattern = r'Rubinetto\s+Gessi\s+([^\n,\.]+)'
    products.extend(re.findall(gessi_pattern, answer_text, re.IGNORECASE))
    
    model_pattern = r'[Mm]odello\s+([A-Z0-9\-]+)'
    products.extend(re.findall(model_pattern, answer_text))
    
    azienda_pattern = r'(Gessi|Grohe|Hansgrohe|Ideal Standard|Duravit|Villeroy)\s+([A-Za-z0-9\s\-]+?)(?:[,\.\n]|$)'
    matches = re.findall(azienda_pattern, answer_text, re.IGNORECASE)
    products.extend([f"{m[0]} {m[1]}" for m in matches])
    
    return list(set(products))[:3]

@app.route('/')
def index():
    html = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oracolo Covolo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f172e 0%, #1a1f3a 100%);
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
        }
        .container { display: flex; width: 100%; height: 100vh; }
        .sidebar {
            width: 320px;
            background: rgba(15, 23, 46, 0.8);
            border-right: 1px solid rgba(59, 130, 245, 0.2);
            padding: 20px;
            overflow-y: auto;
        }
        .main {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: rgba(59, 130, 245, 0.1);
            border-bottom: 1px solid rgba(59, 130, 245, 0.2);
            padding: 20px;
            text-align: center;
        }
        .header h1 { color: #3b82f6; font-size: 28px; }
        .header p { color: #9ca3af; font-size: 13px; }
        .chat-area {
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 20px;
            overflow-y: auto;
        }
        .messages { flex: 1; overflow-y: auto; margin-bottom: 20px; }
        .message {
            margin-bottom: 15px;
            padding: 12px 15px;
            border-radius: 8px;
            max-width: 85%;
            word-wrap: break-word;
            line-height: 1.4;
        }
        .bot-message {
            background: rgba(59, 130, 245, 0.2);
            border-left: 3px solid #3b82f6;
        }
        .user-message {
            background: rgba(168, 85, 247, 0.2);
            border-left: 3px solid #a855f7;
            margin-left: auto;
        }
        .image-gallery {
            margin-top: 10px;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 8px;
        }
        .image-item {
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid rgba(59, 130, 245, 0.3);
            cursor: pointer;
        }
        .image-item img {
            width: 100%;
            height: 100px;
            object-fit: cover;
        }
        .loading-spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(59, 130, 245, 0.3);
            border-top: 2px solid #3b82f6;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .input-area {
            display: flex;
            gap: 10px;
        }
        input {
            flex: 1;
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(59, 130, 245, 0.3);
            color: #e0e0e0;
            padding: 10px 15px;
            border-radius: 6px;
            font-size: 14px;
        }
        button {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
        }
        button:hover { background: #2563eb; }
        .sidebar h3 {
            color: #3b82f6;
            margin-top: 25px;
            margin-bottom: 12px;
            font-size: 14px;
            text-transform: uppercase;
        }
        .sidebar h3:first-child { margin-top: 0; }
        
        .azienda-checkbox {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px;
            margin-bottom: 6px;
            background: rgba(59, 130, 245, 0.1);
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
        }
        .azienda-checkbox input {
            width: 16px;
            height: 16px;
            cursor: pointer;
        }
        
        .preset-controls {
            display: flex;
            gap: 6px;
            margin-bottom: 12px;
        }
        .preset-controls input {
            flex: 1;
            font-size: 12px;
            padding: 6px;
        }
        .preset-controls button {
            padding: 6px 12px;
            font-size: 12px;
        }
        
        .preset-item {
            background: rgba(59, 130, 245, 0.15);
            padding: 8px;
            border-radius: 4px;
            margin-bottom: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
        }
        .preset-item button {
            padding: 2px 8px;
            font-size: 11px;
            background: #10b981;
        }
        .preset-item button.delete {
            background: #ef4444;
        }
        
        .web-toggle {
            background: #6b7280;
            padding: 10px;
            margin-bottom: 15px;
            border-radius: 6px;
            text-align: center;
            cursor: pointer;
            font-size: 13px;
        }
        .web-toggle.on {
            background: #10b981;
        }
        
        .file-item {
            background: rgba(59, 130, 245, 0.1);
            padding: 8px;
            margin-bottom: 8px;
            border-radius: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 999;
            justify-content: center;
            align-items: center;
        }
        .modal.active {
            display: flex;
        }
        .modal-content {
            position: relative;
            max-width: 90%;
            max-height: 90%;
        }
        .modal-content img {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }
        .modal-close {
            position: absolute;
            top: 10px; right: 10px;
            background: #ef4444;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h3>🏢 Aziende</h3>
            <div id="aziende-list"></div>
            
            <h3>💾 Preset</h3>
            <div class="preset-controls">
                <input type="text" id="preset-name" placeholder="Nome..." style="flex: 1;">
                <button onclick="savePreset()" style="flex: 0 0 auto; padding: 6px 10px; font-size: 12px;">Salva</button>
            </div>
            <div id="presets-list"></div>
            
            <h3>🌐 Web Search</h3>
            <div class="web-toggle" id="web-toggle" onclick="toggleWeb()">
                🔴 OFF
            </div>
            
            <h3>📁 Documenti</h3>
            <div style="border: 2px dashed rgba(59, 130, 245, 0.3); padding: 12px; border-radius: 8px; text-align: center; cursor: pointer; margin-bottom: 15px; font-size: 13px;" onclick="document.getElementById('file-input').click()">
                📤 Carica
                <input type="file" id="file-input" hidden multiple onchange="uploadFile(this)">
            </div>
            <div id="files-list"></div>
        </div>
        
        <div class="main">
            <div class="header">
                <h1>🔮 Oracolo Covolo</h1>
                <p>Consulente + Auto Web Search</p>
            </div>
            
            <div class="chat-area">
                <div class="messages" id="messages"></div>
                <div class="input-area">
                    <input type="text" id="question" placeholder="Fai una domanda..." onkeypress="if(event.key==='Enter') sendQuestion()">
                    <button onclick="sendQuestion()">Invia</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal" id="image-modal">
        <div class="modal-content">
            <img id="modal-img" src="">
            <button class="modal-close" onclick="closeModal()">✕</button>
        </div>
    </div>
    
    <script>
        let webEnabled = true;
        let selectedAziende = [];
        
        async function loadAziende() {
            const response = await fetch('/api/aziende');
            const data = await response.json();
            const container = document.getElementById('aziende-list');
            
            container.innerHTML = data.aziende.map(az => `
                <div class="azienda-checkbox">
                    <input type="checkbox" id="az-${az.id}" value="${az.id}" onchange="updateSelectedAziende()">
                    <label for="az-${az.id}">${az.nome}</label>
                </div>
            `).join('');
        }
        
        function updateSelectedAziende() {
            selectedAziende = Array.from(document.querySelectorAll('input[type="checkbox"]:checked')).map(el => el.value);
            loadFiles();
            document.getElementById('messages').innerHTML = '';
        }
        
        async function loadPresets() {
            const response = await fetch('/api/presets');
            const data = await response.json();
            const container = document.getElementById('presets-list');
            
            container.innerHTML = data.presets.map(preset => `
                <div class="preset-item">
                    <span>${preset.nome}</span>
                    <div style="display: flex; gap: 4px;">
                        <button onclick="loadPreset('${preset.nome}')" style="background: #10b981;">Carica</button>
                        <button class="delete" onclick="deletePreset('${preset.nome}')">🗑</button>
                    </div>
                </div>
            `).join('');
        }
        
        async function savePreset() {
            const name = document.getElementById('preset-name').value.trim();
            if (!name || selectedAziende.length === 0) return;
            
            await fetch('/api/presets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nome: name, azienda_ids: selectedAziende })
            });
            
            document.getElementById('preset-name').value = '';
            loadPresets();
        }
        
        async function loadPreset(presetName) {
            const response = await fetch(`/api/presets/${presetName}`);
            const data = await response.json();
            
            document.querySelectorAll('input[type="checkbox"]').forEach(el => {
                el.checked = data.azienda_ids.includes(el.value);
            });
            
            updateSelectedAziende();
        }
        
        async function deletePreset(presetName) {
            if (confirm('Elimina?')) {
                await fetch(`/api/presets/${presetName}`, { method: 'DELETE' });
                loadPresets();
            }
        }
        
        function toggleWeb() {
            webEnabled = !webEnabled;
            const btn = document.getElementById('web-toggle');
            btn.textContent = webEnabled ? '🟢 ON' : '🔴 OFF';
            btn.classList.toggle('on');
        }
        
        async function sendQuestion() {
            const input = document.getElementById('question');
            const question = input.value.trim();
            if (!question) return;
            
            const messagesDiv = document.getElementById('messages');
            messagesDiv.innerHTML += `<div class="message user-message">${question}</div>`;
            
            const loadingMsg = document.createElement('div');
            loadingMsg.className = 'message bot-message';
            loadingMsg.innerHTML = `<div class="loading-spinner"></div> Ricerca in corso...`;
            messagesDiv.appendChild(loadingMsg);
            
            input.value = '';
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
            try {
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: question,
                        azienda_ids: selectedAziende,
                        use_web: webEnabled
                    })
                });
                const data = await response.json();
                
                messagesDiv.removeChild(loadingMsg);
                
                let msgHtml = `<div class="message bot-message">${data.answer}`;
                if (data.images && data.images.length > 0) {
                    msgHtml += '<div class="image-gallery">';
                    data.images.forEach(img => {
                        msgHtml += `<div class="image-item" onclick="openModal('data:image/jpeg;base64,${img}')"><img src="data:image/jpeg;base64,${img}"></div>`;
                    });
                    msgHtml += '</div>';
                }
                msgHtml += '</div>';
                
                messagesDiv.innerHTML += msgHtml;
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            } catch (e) {
                messagesDiv.removeChild(loadingMsg);
                messagesDiv.innerHTML += `<div class="message bot-message">Errore: ${e}</div>`;
            }
        }
        
        async function uploadFile(input) {
            const files = Array.from(input.files);
            const formData = new FormData();
            files.forEach(f => formData.append('files', f));
            
            if (selectedAziende.length > 0) {
                formData.append('azienda_ids', selectedAziende.join(','));
            }
            
            try {
                await fetch('/api/upload', { method: 'POST', body: formData });
                loadFiles();
            } catch (e) {
                console.error('Errore:', e);
            }
        }
        
        async function loadFiles() {
            if (selectedAziende.length === 0) {
                document.getElementById('files-list').innerHTML = '';
                return;
            }
            
            const response = await fetch(`/api/documents?azienda_ids=${selectedAziende.join(',')}`);
            const data = await response.json();
            const filesList = document.getElementById('files-list');
            filesList.innerHTML = data.documents.map(doc => `
                <div class="file-item">
                    <span>📄 ${doc.filename}</span>
                    <button style="background: #ef4444; padding: 2px 8px; font-size: 11px;" onclick="deleteFile('${doc.filename}')">✕</button>
                </div>
            `).join('');
        }
        
        async function deleteFile(filename) {
            await fetch(`/api/documents/${filename}`, { method: 'DELETE' });
            loadFiles();
        }
        
        function openModal(src) {
            document.getElementById('modal-img').src = src;
            document.getElementById('image-modal').classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('image-modal').classList.remove('active');
        }
        
        loadAziende();
        loadPresets();
    </script>
</body>
</html>
    """
    return render_template_string(html)

@app.route('/api/aziende', methods=['GET'])
def get_aziende():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, nome FROM aziende ORDER BY nome')
    aziende = [{"id": str(row[0]), "nome": row[1]} for row in c.fetchall()]
    conn.close()
    return jsonify({"aziende": aziende})

@app.route('/api/presets', methods=['GET'])
def get_presets():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT nome, azienda_ids FROM presets ORDER BY nome')
    presets = [{"nome": row[0], "azienda_ids": row[1].split(',')} for row in c.fetchall()]
    conn.close()
    return jsonify({"presets": presets})

@app.route('/api/presets', methods=['POST'])
def save_preset():
    data = request.get_json()
    nome = data.get('nome')
    azienda_ids = ','.join(data.get('azienda_ids', []))
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO presets (nome, azienda_ids) VALUES (?, ?)', (nome, azienda_ids))
        conn.commit()
    except:
        pass
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/presets/<nome>', methods=['GET'])
def get_preset(nome):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT azienda_ids FROM presets WHERE nome = ?', (nome,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return jsonify({"azienda_ids": result[0].split(',')})
    return jsonify({"azienda_ids": []})

@app.route('/api/presets/<nome>', methods=['DELETE'])
def delete_preset(nome):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM presets WHERE nome = ?', (nome,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/documents', methods=['GET'])
def get_documents():
    azienda_ids = request.args.get('azienda_ids', '').split(',')
    if not azienda_ids or azienda_ids == ['']:
        return jsonify({"documents": []})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    placeholders = ','.join('?' * len(azienda_ids))
    c.execute(f'SELECT DISTINCT filename FROM documents WHERE azienda_id IN ({placeholders})', azienda_ids)
    docs = [{"filename": row[0]} for row in c.fetchall()]
    conn.close()
    return jsonify({"documents": docs})

@app.route('/api/upload', methods=['POST'])
def upload():
    if 'files' not in request.files:
        return jsonify({"status": "error"}), 400
    
    files = request.files.getlist('files')
    azienda_ids = request.form.get('azienda_ids', '').split(',')
    if not azienda_ids or azienda_ids == ['']:
        azienda_ids = ['1']
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    for file in files:
        if file.filename == '':
            continue
        
        try:
            doc_path = os.path.join(UPLOADS_DIR, file.filename)
            file.save(doc_path)
            
            with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            for aid in azienda_ids:
                try:
                    c.execute('INSERT OR REPLACE INTO documents (filename, content, azienda_id) VALUES (?, ?, ?)',
                              (file.filename, content, aid))
                except:
                    pass
        except Exception as e:
            print(f"Errore: {e}")
    
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/documents/<filename>', methods=['DELETE'])
def delete_document(filename):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM documents WHERE filename = ?', (filename,))
    conn.commit()
    conn.close()
    
    file_path = os.path.join(UPLOADS_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    return jsonify({"status": "success"})

@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = (data.get('question') or "").strip()
    azienda_ids = data.get('azienda_ids', [])
    use_web = data.get('use_web', True)  # Default TRUE
    
    if not question:
        return jsonify({"answer": "Domanda vuota", "images": []})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Cerca documenti
    docs = []
    if azienda_ids:
        placeholders = ','.join('?' * len(azienda_ids))
        c.execute(f'SELECT filename, content FROM documents WHERE azienda_id IN ({placeholders})', azienda_ids)
        docs = c.fetchall()
    
    c.execute('SELECT nome FROM aziende WHERE id IN ({})'.format(','.join('?' * len(azienda_ids)) if azienda_ids else '""'))
    aziende_names = [row[0] for row in c.fetchall()] if azienda_ids else []
    conn.close()
    
    # Se ha documenti, usa quelli
    if docs:
        doc_context = "\n".join([f"📄 {doc[0]}:\n{doc[1][:300]}" for doc in docs[:2]])
        
        prompt = f"""Tu sei consulente ESPERTO arredo bagno per Covolo.

DOCUMENTI AZIENDA:
{doc_context}

DOMANDA: {question}

Rispondi basandoti sui documenti. Se suggerisci prodotti, includi NOME e MODELLO."""
    
    # ALTRIMENTI usa web automaticamente
    else:
        web_content = search_web_bing(question)
        if not web_content:
            web_content = "No web content found"
        
        prompt = f"""Tu sei consulente ESPERTO arredo bagno per Covolo.

RICERCA WEB:
{web_content}

DOMANDA: {question}

Rispondi da esperto, basandoti sulla ricerca web. Se suggerisci prodotti, includi NOME AZIENDA e MODELLO."""
    
    try:
        response = httpx.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 1500,
            },
            timeout=30
        )
        
        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            
            # Ricerca automatica immagini prodotti
            products = extract_product_names(answer)
            images = []
            
            for product in products:
                product_images = search_product_images(product, " ".join(aziende_names))
                images.extend(product_images)
            
            return jsonify({"answer": answer, "images": images[:5]})
        else:
            return jsonify({"answer": "Errore risposta API", "images": []})
    
    except Exception as e:
        return jsonify({"answer": f"Errore: {str(e)}", "images": []})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
