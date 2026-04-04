"""
ORACOLO COVOLO - FLASK CON MULTI-AZIENDE E PRESET
==================================================
"""

import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
import httpx

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
            font-size: 14px;
        }
        button:hover { background: #2563eb; }
        .sidebar h3 {
            color: #3b82f6;
            margin-top: 25px;
            margin-bottom: 12px;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
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
            flex: 0 0 auto;
        }
        .azienda-checkbox label {
            flex: 1;
            cursor: pointer;
            margin: 0;
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
            flex: 0 0 auto;
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
            transition: background 0.3s;
        }
        .web-toggle.on {
            background: #10b981;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h3>🏢 Aziende (Multi-Select)</h3>
            <div id="aziende-list"></div>
            
            <h3>💾 Preset</h3>
            <div class="preset-controls">
                <input type="text" id="preset-name" placeholder="Nome preset..." style="flex: 1;">
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
                <input type="file" id="file-input" hidden onchange="uploadFile(this)">
            </div>
            <div id="files-list"></div>
        </div>
        
        <div class="main">
            <div class="header">
                <h1>🔮 Oracolo Covolo</h1>
                <p>Consulente Intelligente Arredo Bagno</p>
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
    
    <script>
        let webEnabled = false;
        let selectedAziende = [];
        
        async function loadAziende() {
            const response = await fetch('/api/aziende');
            const data = await response.json();
            const container = document.getElementById('aziende-list');
            
            container.innerHTML = data.aziende.map(az => `
                <div class="azienda-checkbox">
                    <input type="checkbox" id="az-${az.id}" value="${az.id}" onchange="updateSelectedAziende()">
                    <label for="az-${az.id}">${az.nome} (${az.categoria})</label>
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
            if (!name) {
                alert('Inserisci nome preset');
                return;
            }
            if (selectedAziende.length === 0) {
                alert('Seleziona almeno un azienda');
                return;
            }
            
            const response = await fetch('/api/presets', {
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
            if (confirm('Elimina questo preset?')) {
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
            if (selectedAziende.length === 0) {
                alert('Seleziona almeno un azienda!');
                return;
            }
            
            const input = document.getElementById('question');
            const question = input.value.trim();
            if (!question) return;
            
            const messagesDiv = document.getElementById('messages');
            messagesDiv.innerHTML += `<div class="message user-message">${question}</div>`;
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
                messagesDiv.innerHTML += `<div class="message bot-message">${data.answer}</div>`;
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            } catch (e) {
                messagesDiv.innerHTML += `<div class="message bot-message">Errore: ${e}</div>`;
            }
        }
        
        async function uploadFile(input) {
            if (selectedAziende.length === 0) {
                alert('Seleziona azienda prima!');
                return;
            }
            
            const file = input.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('azienda_ids', selectedAziende.join(','));
            
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
                <div style="background: rgba(59, 130, 245, 0.1); padding: 8px; margin-bottom: 8px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; font-size: 12px;">
                    <span>📄 ${doc.filename}</span>
                    <button style="background: #ef4444; padding: 2px 8px; font-size: 11px;" onclick="deleteFile('${doc.filename}')">✕</button>
                </div>
            `).join('');
        }
        
        async function deleteFile(filename) {
            try {
                await fetch(`/api/documents/${filename}`, { method: 'DELETE' });
                loadFiles();
            } catch (e) {
                console.error('Errore:', e);
            }
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
    c.execute('SELECT id, nome, categoria FROM aziende ORDER BY nome')
    aziende = [{"id": str(row[0]), "nome": row[1], "categoria": row[2]} for row in c.fetchall()]
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    placeholders = ','.join('?' * len(azienda_ids))
    c.execute(f'SELECT DISTINCT filename FROM documents WHERE azienda_id IN ({placeholders})', azienda_ids)
    docs = [{"filename": row[0]} for row in c.fetchall()]
    conn.close()
    return jsonify({"documents": docs})

@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"status": "error"}), 400
    
    file = request.files['file']
    azienda_ids = request.form.get('azienda_ids', '').split(',')
    
    file_path = os.path.join(UPLOADS_DIR, file.filename)
    file.save(file_path)
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    for aid in azienda_ids:
        try:
            c.execute('INSERT OR REPLACE INTO documents (filename, content, azienda_id) VALUES (?, ?, ?)',
                      (file.filename, content, aid))
        except:
            pass
    
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
    use_web = data.get('use_web', False)
    
    if not question or not azienda_ids:
        return jsonify({"answer": "Errore: dati mancanti"})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    placeholders = ','.join('?' * len(azienda_ids))
    c.execute(f'SELECT filename, content FROM documents WHERE azienda_id IN ({placeholders})', azienda_ids)
    docs = c.fetchall()
    conn.close()
    
    if not docs:
        return jsonify({"answer": "Nessun documento trovato per le aziende selezionate."})
    
    doc_context = "\n".join([f"📄 {doc[0]}:\n{doc[1][:300]}" for doc in docs[:3]])
    
    prompt = f"""Tu sei consulente ESPERTO arredo bagno per Covolo.

DOCUMENTI DISPONIBILI:
{doc_context}

DOMANDA CLIENT: {question}

Rispondi come narrativa calda, professionale e esperta. Se il documento non contiene info, usa la tua esperienza."""

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
            return jsonify({"answer": answer})
        else:
            return jsonify({"answer": "Errore nel generare risposta"})
    
    except Exception as e:
        return jsonify({"answer": f"Errore: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
