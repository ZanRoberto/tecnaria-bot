"""
ORACOLO COVOLO - FIXED VERSION
===============================
"""

import os, json, sqlite3, base64, re
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file
import httpx
from urllib.parse import quote
from io import BytesIO

from macrorule_engine import MacroruleEngine
from narrator_system import NarratorSystem

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
IMAGES_DIR = os.path.join(DATA_DIR, "product_images")
DB_PATH = os.path.join(DATA_DIR, "oracolo_covolo.db")
MACRORULE_FILE = os.path.join(BASE_DIR, "macroregole_covolo_universe.json")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

macrorule_engine = MacroruleEngine(MACRORULE_FILE)
narrator = NarratorSystem()

def init_covolo_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS aziende
                 (id INTEGER PRIMARY KEY, nome TEXT UNIQUE, sito TEXT, categoria TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id INTEGER PRIMARY KEY, filename TEXT UNIQUE, content TEXT, azienda_id INTEGER, upload_date TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS product_images
                 (id INTEGER PRIMARY KEY, product_name TEXT, azienda_id INTEGER, image_base64 TEXT, filename TEXT, upload_date TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS presets
                 (id INTEGER PRIMARY KEY, nome TEXT UNIQUE, azienda_ids TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

init_covolo_db()
app = Flask(__name__)

def search_catalog_images(product_name, azienda_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT image_base64 FROM product_images WHERE azienda_id = ? AND LOWER(product_name) LIKE ?',
                  (azienda_id, f'%{product_name.lower()}%'))
        results = c.fetchall()
        conn.close()
        return [row[0] for row in results]
    except:
        return []

def search_web_bing(query):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        url = f"https://www.bing.com/search?q={quote(query)}"
        response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        if response.status_code == 200:
            snippets = re.findall(r'<p[^>]*>(.*?)</p>', response.text)
            cleaned = [re.sub(r'<[^>]+>', '', s) for s in snippets if len(s) > 50]
            return " ".join(cleaned[:3])
        return ""
    except:
        return ""

def extract_product_names(answer_text):
    products = []
    products.extend([f"Gessi{m}" for m in re.findall(r'Gessi\s*(\d+[A-Z]*)', answer_text, re.IGNORECASE)])
    products.extend(re.findall(r'[Mm]odello\s+([A-Z0-9\-]+)', answer_text))
    products.extend(list(set(products))[:5])
    return list(set(products))[:5]

@app.route('/')
def index():
    return render_template_string(open('templates/index.html').read() if os.path.exists('templates/index.html') else get_html())

def get_html():
    return """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oracolo Covolo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI'; background: linear-gradient(135deg, #0f172e 0%, #1a1f3a 100%); color: #e0e0e0; min-height: 100vh; display: flex; }
        .container { display: flex; width: 100%; height: 100vh; }
        .sidebar { width: 340px; background: rgba(15, 23, 46, 0.8); border-right: 1px solid rgba(59, 130, 245, 0.2); padding: 20px; overflow-y: auto; }
        .main { flex: 1; display: flex; flex-direction: column; }
        .header { background: rgba(59, 130, 245, 0.1); border-bottom: 1px solid rgba(59, 130, 245, 0.2); padding: 20px; text-align: center; }
        .header h1 { color: #3b82f6; font-size: 28px; }
        .header p { color: #9ca3af; font-size: 13px; }
        .agents-bar { background: rgba(59, 130, 245, 0.05); border-bottom: 1px solid rgba(59, 130, 245, 0.2); padding: 10px 20px; display: flex; gap: 10px; flex-wrap: wrap; }
        .agent-btn { background: #10b981; color: white; border: none; padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; }
        .agent-btn:hover { background: #059669; }
        .agent-btn.disabled { background: #6b7280; cursor: not-allowed; }
        .chat-area { flex: 1; display: flex; flex-direction: column; padding: 20px; overflow-y: auto; }
        .messages { flex: 1; overflow-y: auto; margin-bottom: 20px; }
        .message { margin-bottom: 15px; padding: 12px 15px; border-radius: 8px; max-width: 85%; word-wrap: break-word; }
        .bot-message { background: rgba(59, 130, 245, 0.2); border-left: 3px solid #3b82f6; }
        .user-message { background: rgba(168, 85, 247, 0.2); border-left: 3px solid #a855f7; margin-left: auto; }
        .input-area { display: flex; gap: 10px; }
        input { flex: 1; background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(59, 130, 245, 0.3); color: #e0e0e0; padding: 10px 15px; border-radius: 6px; font-size: 14px; }
        button { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 500; }
        button:hover { background: #2563eb; }
        .sidebar h3 { color: #3b82f6; margin-top: 20px; margin-bottom: 12px; font-size: 13px; text-transform: uppercase; }
        .sidebar h3:first-child { margin-top: 0; }
        .input-group { display: flex; gap: 6px; margin-bottom: 10px; }
        .input-group input { flex: 1; font-size: 12px; padding: 6px; }
        .input-group button { padding: 6px 12px; font-size: 12px; flex: 0 0 auto; }
        .web-toggle { background: #ef4444; padding: 12px; margin-bottom: 15px; border-radius: 6px; text-align: center; cursor: pointer; font-size: 14px; font-weight: 600; }
        .web-toggle.on { background: #10b981; }
        .file-item { background: rgba(59, 130, 245, 0.1); padding: 8px; margin-bottom: 6px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; }
        .file-item button { padding: 2px 6px; font-size: 11px; background: #ef4444; }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h3>🏢 Aziende</h3>
            <div class="input-group">
                <input type="text" id="new-azienda-nome" placeholder="Nome...">
                <button onclick="addAzienda()">➕</button>
            </div>
            <div id="aziende-list"></div>
            
            <h3>🌐 Web Search</h3>
            <div class="web-toggle" id="web-toggle" onclick="toggleWeb()">🔴 OFF</div>
            
            <h3>🖼️ Immagini</h3>
            <div class="input-group">
                <input type="text" id="product-name" placeholder="Nome...">
                <button onclick="document.getElementById('product-image-input').click()">📤</button>
                <input type="file" id="product-image-input" hidden accept=".png,.jpg,.jpeg,.gif" onchange="uploadProductImage(this)">
            </div>
            <div id="product-images-list"></div>
            
            <h3>📁 Documenti</h3>
            <div style="border: 2px dashed rgba(59, 130, 245, 0.3); padding: 10px; border-radius: 6px; text-align: center; cursor: pointer; margin-bottom: 12px; font-size: 12px;" onclick="document.getElementById('file-input').click()">
                📤 Carica
                <input type="file" id="file-input" hidden multiple onchange="uploadFile(this)">
            </div>
            <div id="files-list"></div>
        </div>
        
        <div class="main">
            <div class="header">
                <h1>🔮 Oracolo Covolo</h1>
                <p>Consulente Intelligente Arredo Bagno</p>
            </div>
            
            <div class="agents-bar">
                <button class="agent-btn" id="btn-offerta" onclick="generateOfferta()" disabled>📄 OFFERTA</button>
                <button class="agent-btn" id="btn-analisi" onclick="generateAnalisi()" disabled>📊 ANALISI</button>
                <button class="agent-btn" id="btn-proposta" onclick="generateProposta()" disabled>🎯 PROPOSTA</button>
            </div>
            
            <div class="chat-area">
                <div class="messages" id="messages"></div>
                <div class="input-area">
                    <input type="text" id="question" placeholder="Fai una domanda..." onkeypress="if(event.key===String.fromCharCode(13)) sendQuestion()">
                    <button onclick="sendQuestion()">Invia</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let selectedAziende = [];
        let webEnabled = false;
        
        function updateAgentButtons() {
            document.getElementById('btn-offerta').disabled = selectedAziende.length === 0;
            document.getElementById('btn-analisi').disabled = selectedAziende.length === 0;
            document.getElementById('btn-proposta').disabled = selectedAziende.length === 0;
        }
        
        async function generateOfferta() {
            const msg = document.getElementById('messages');
            msg.innerHTML += '<div class="message bot-message">⏳ Generando OFFERTA...</div>';
            try {
                const response = await fetch('/api/generate-offerta', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({azienda_ids: selectedAziende})
                });
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'Offerta_Covolo.html';
                document.body.appendChild(a);
                a.click();
                msg.innerHTML += '<div class="message bot-message">✅ OFFERTA SCARICATA!</div>';
            } catch (e) {
                msg.innerHTML += '<div class="message bot-message">Errore: ' + e + '</div>';
            }
        }
        
        async function generateAnalisi() {
            const msg = document.getElementById('messages');
            msg.innerHTML += '<div class="message bot-message">⏳ Generando ANALISI...</div>';
            try {
                const response = await fetch('/api/generate-analisi', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({azienda_ids: selectedAziende})});
                const data = await response.json();
                msg.innerHTML += '<div class="message bot-message"><strong>ANALISI:</strong><br>' + data.analisi + '</div>';
            } catch (e) {
                msg.innerHTML += '<div class="message bot-message">Errore: ' + e + '</div>';
            }
        }
        
        async function generateProposta() {
            const msg = document.getElementById('messages');
            msg.innerHTML += '<div class="message bot-message">⏳ Generando PROPOSTA...</div>';
            try {
                const response = await fetch('/api/generate-proposta', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({azienda_ids: selectedAziende})});
                const data = await response.json();
                msg.innerHTML += '<div class="message bot-message"><strong>PROPOSTA:</strong><br>' + data.proposta + '</div>';
            } catch (e) {
                msg.innerHTML += '<div class="message bot-message">Errore: ' + e + '</div>';
            }
        }
        
        async function loadAziende() {
            const response = await fetch('/api/aziende');
            const data = await response.json();
            const container = document.getElementById('aziende-list');
            container.innerHTML = data.aziende.map(az => '<div style="background: rgba(59, 130, 245, 0.1); padding: 8px; margin-bottom: 6px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; font-size: 12px;"><div style="flex: 1;"><input type="checkbox" id="az-' + az.id + '" value="' + az.id + '" onchange="updateSelectedAziende()" style="margin-right: 6px;"><label for="az-' + az.id + '">' + az.nome + '</label></div><button style="padding: 2px 6px; background: #ef4444; font-size: 11px;" onclick="deleteAzienda(' + az.id + ')">✕</button></div>').join('');
            updateAgentButtons();
        }
        
        async function addAzienda() {
            const nome = document.getElementById('new-azienda-nome').value.trim();
            if (!nome) {alert('Nome azienda richiesto'); return;}
            await fetch('/api/aziende', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nome: nome})});
            document.getElementById('new-azienda-nome').value = '';
            loadAziende();
        }
        
        async function deleteAzienda(aziendaId) {
            if (confirm('Elimina?')) {
                await fetch('/api/aziende/' + aziendaId, {method: 'DELETE'});
                loadAziende();
                updateSelectedAziende();
            }
        }
        
        function toggleWeb() {
            webEnabled = !webEnabled;
            const btn = document.getElementById('web-toggle');
            btn.textContent = webEnabled ? '🟢 ON' : '🔴 OFF';
            btn.classList.toggle('on');
        }
        
        function updateSelectedAziende() {
            selectedAziende = Array.from(document.querySelectorAll('input[type=checkbox]:checked')).map(el => el.value);
            loadFiles();
            loadProductImages();
            updateAgentButtons();
        }
        
        async function uploadProductImage(input) {
            const file = input.files[0];
            const productName = document.getElementById('product-name').value.trim();
            if (!file || !productName || selectedAziende.length === 0) {alert('Completa campi'); return;}
            const formData = new FormData();
            formData.append('image', file);
            formData.append('product_name', productName);
            formData.append('azienda_ids', selectedAziende.join(','));
            await fetch('/api/upload-product-image', {method: 'POST', body: formData});
            document.getElementById('product-name').value = '';
            loadProductImages();
        }
        
        async function loadProductImages() {
            if (selectedAziende.length === 0) {document.getElementById('product-images-list').innerHTML = ''; return;}
            const response = await fetch('/api/product-images?azienda_ids=' + selectedAziende.join(','));
            const data = await response.json();
            const imagesList = document.getElementById('product-images-list');
            imagesList.innerHTML = data.images.map(img => '<div class="file-item"><span>🖼️ ' + img.product_name + '</span><button onclick="deleteProductImage(' + img.id + ')">✕</button></div>').join('');
        }
        
        async function deleteProductImage(imageId) {
            if (confirm('Elimina?')) {await fetch('/api/product-images/' + imageId, {method: 'DELETE'}); loadProductImages();}
        }
        
        async function uploadFile(input) {
            const files = Array.from(input.files);
            const formData = new FormData();
            files.forEach(f => formData.append('files', f));
            if (selectedAziende.length > 0) formData.append('azienda_ids', selectedAziende.join(','));
            await fetch('/api/upload', {method: 'POST', body: formData});
            loadFiles();
        }
        
        async function loadFiles() {
            if (selectedAziende.length === 0) {document.getElementById('files-list').innerHTML = ''; return;}
            const response = await fetch('/api/documents?azienda_ids=' + selectedAziende.join(','));
            const data = await response.json();
            const filesList = document.getElementById('files-list');
            filesList.innerHTML = data.documents.map(doc => '<div class="file-item"><span>📄 ' + doc.filename + '</span><button onclick="deleteFile(' + doc.filename + ')">✕</button></div>').join('');
        }
        
        async function deleteFile(filename) {
            await fetch('/api/documents/' + filename, {method: 'DELETE'});
            loadFiles();
        }
        
        async function sendQuestion() {
            const input = document.getElementById('question');
            const question = input.value.trim();
            if (!question) return;
            if (selectedAziende.length === 0) {alert('Seleziona azienda'); return;}
            const messagesDiv = document.getElementById('messages');
            messagesDiv.innerHTML += '<div class="message user-message">' + question + '</div>';
            input.value = '';
            try {
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({question: question, azienda_ids: selectedAziende, use_web: webEnabled})
                });
                const data = await response.json();
                messagesDiv.innerHTML += '<div class="message bot-message">' + data.answer + '</div>';
            } catch (e) {
                messagesDiv.innerHTML += '<div class="message bot-message">Errore: ' + e + '</div>';
            }
        }
        
        loadAziende();
    </script>
</body>
</html>"""

@app.route('/api/aziende', methods=['GET'])
def get_aziende():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, nome FROM aziende ORDER BY nome')
    aziende = [{"id": str(row[0]), "nome": row[1]} for row in c.fetchall()]
    conn.close()
    return jsonify({"aziende": aziende})

@app.route('/api/aziende', methods=['POST'])
def add_azienda():
    data = request.get_json()
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({"status": "error"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO aziende (nome) VALUES (?)', (nome,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except:
        conn.close()
        return jsonify({"status": "error"}), 400

@app.route('/api/aziende/<azienda_id>', methods=['DELETE'])
def delete_azienda(azienda_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM aziende WHERE id = ?', (azienda_id,))
    c.execute('DELETE FROM documents WHERE azienda_id = ?', (azienda_id,))
    c.execute('DELETE FROM product_images WHERE azienda_id = ?', (azienda_id,))
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

@app.route('/api/product-images', methods=['GET'])
def get_product_images():
    azienda_ids = request.args.get('azienda_ids', '').split(',')
    if not azienda_ids or azienda_ids == ['']:
        return jsonify({"images": []})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ','.join('?' * len(azienda_ids))
    c.execute(f'SELECT id, product_name FROM product_images WHERE azienda_id IN ({placeholders})', azienda_ids)
    images = [{"id": str(row[0]), "product_name": row[1]} for row in c.fetchall()]
    conn.close()
    return jsonify({"images": images})

@app.route('/api/upload-product-image', methods=['POST'])
def upload_product_image():
    if 'image' not in request.files:
        return jsonify({"status": "error"}), 400
    file = request.files['image']
    product_name = request.form.get('product_name', 'Unknown')
    azienda_ids = request.form.get('azienda_ids', '1').split(',')
    try:
        img_data = base64.b64encode(file.read()).decode('utf-8')
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for aid in azienda_ids:
            c.execute('INSERT INTO product_images (product_name, azienda_id, image_base64, filename) VALUES (?, ?, ?, ?)',
                      (product_name, aid, img_data, file.filename))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except:
        return jsonify({"status": "error"})

@app.route('/api/product-images/<image_id>', methods=['DELETE'])
def delete_product_image(image_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM product_images WHERE id = ?', (image_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

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

@app.route('/api/generate-offerta', methods=['POST'])
def generate_offerta():
    data = request.get_json()
    azienda_ids = data.get('azienda_ids', [])
    html = f"<html><body><h1>Offerta Covolo {datetime.now().strftime('%d/%m/%Y')}</h1><p>Aziende: {azienda_ids}</p></body></html>"
    return send_file(BytesIO(html.encode('utf-8')), mimetype='text/html', as_attachment=True, download_name='Offerta.html')

@app.route('/api/generate-analisi', methods=['POST'])
def generate_analisi():
    data = request.get_json()
    return jsonify({"analisi": "ANALISI COMPARATIVA - Aziende: " + str(data.get('azienda_ids', []))})

@app.route('/api/generate-proposta', methods=['POST'])
def generate_proposta():
    data = request.get_json()
    return jsonify({"proposta": "PROPOSTA COMPLETA - Aziende: " + str(data.get('azienda_ids', []))})

@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = (data.get('question') or "").strip()
    azienda_ids = data.get('azienda_ids', [])
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    docs = []
    if azienda_ids:
        placeholders = ','.join('?' * len(azienda_ids))
        c.execute(f'SELECT filename, content FROM documents WHERE azienda_id IN ({placeholders})', azienda_ids)
        docs = c.fetchall()
    
    conn.close()
    
    if docs:
        doc_context = "\n".join([f"- {doc[0]}" for doc in docs[:2]])
        answer = f"📄 Risposta basata su: {doc_context}\n\nDomanda: {question}\n\nRisposta consulenziale..."
    else:
        answer = f"⚠️ Nessun documento trovato per la domanda: {question}"
    
    return jsonify({"answer": answer, "images": []})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)

# AGGIUNTO: Funzione per raccogliere TUTTO quello selezionato
def get_selection_context(azienda_ids):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ','.join('?' * len(azienda_ids))
    
    c.execute(f'SELECT nome FROM aziende WHERE id IN ({placeholders})', azienda_ids)
    aziende = [row[0] for row in c.fetchall()]
    
    c.execute(f'SELECT filename, content FROM documents WHERE azienda_id IN ({placeholders})', azienda_ids)
    docs = [(row[0], row[1][:400]) for row in c.fetchall()]
    
    c.execute(f'SELECT COUNT(*), GROUP_CONCAT(product_name) FROM product_images WHERE azienda_id IN ({placeholders})', azienda_ids)
    result = c.fetchone()
    img_count = result[0] if result else 0
    img_names = (result[1] or '').split(',') if result and result[1] else []
    
    conn.close()
    return {'aziende': aziende, 'docs': docs, 'images_count': img_count, 'images_names': img_names}
