"""
ORACOLO COVOLO - SMART MERGE CON DEEPSEEK SYNTHESIS
=====================================================
Combina intelligentemente doc interno + web usando AI
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
    c.execute('''CREATE TABLE IF NOT EXISTS aziende (id INTEGER PRIMARY KEY, nome TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, filename TEXT UNIQUE, content TEXT, azienda_id INTEGER, upload_date TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS selection_cart (id INTEGER PRIMARY KEY, response TEXT, images TEXT, product_name TEXT, source TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_covolo_db()
app = Flask(__name__)

def search_documents(question, azienda_ids=None):
    """Cerca nei documenti interni"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        if azienda_ids:
            placeholders = ','.join('?' * len(azienda_ids))
            c.execute(f'SELECT filename, content FROM documents WHERE azienda_id IN ({placeholders})', azienda_ids)
        else:
            c.execute('SELECT filename, content FROM documents')
        
        docs = c.fetchall()
        conn.close()
        
        keywords = re.findall(r'\b\w{3,}\b', question.lower())
        best_match = None
        best_score = 0
        
        for doc_file, doc_content in docs:
            score = sum(1 for kw in keywords if kw in doc_content.lower())
            if score > best_score:
                best_score = score
                best_match = (doc_file, doc_content)
        
        return best_match if best_score > 0 else None
    except:
        return None

def search_web(question):
    """Ricerca web + immagini"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        url = f"https://www.bing.com/search?q={quote(question)}"
        response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        
        answer = ""
        if response.status_code == 200:
            snippets = re.findall(r'<p[^>]*>(.*?)</p>', response.text)
            for s in snippets[:5]:
                text = re.sub(r'<[^>]+>', '', s).strip()
                if len(text) > 50 and len(answer) < 500:
                    answer += text + " "
        
        images = []
        try:
            img_url = f"https://www.bing.com/images/search?q={quote(question)}"
            img_response = httpx.get(img_url, headers=headers, timeout=5, follow_redirects=True)
            if img_response.status_code == 200:
                img_urls = re.findall(r'murl":"([^"]+\.jpg)"', img_response.text)
                for img_u in img_urls[:3]:
                    try:
                        img_data = httpx.get(img_u, timeout=3, headers=headers)
                        if img_data.status_code == 200 and len(images) < 3:
                            images.append(base64.b64encode(img_data.content).decode('utf-8')[:100])
                    except:
                        pass
        except:
            pass
        
        return answer.strip() if answer else None, images
    except:
        return None, []

def synthesis_with_ai(question, doc_text, doc_file, web_text):
    """Usa DeepSeek per sintetizzare meglio il merge"""
    try:
        prompt = f"""Sei un esperto consulente arredo bagno.

DOMANDA CLIENTE: {question}

INFORMAZIONE INTERNA (documento: {doc_file}):
{doc_text[:300]}

INFORMAZIONE WEB:
{web_text[:300]}

COMPITO: Sintetizza le MIGLIORI informazioni da entrambe le fonti.
- Priorità ai nostri documenti (sono specifici per Covolo)
- Integra con web se aggiunge valore
- Sii conciso e consulenziale
- NON ripetere identiche informazioni

Formato: 2-3 paragrafi solidi."""

        response = httpx.post(
            DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": DEEPSEEK_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.5, "max_tokens": 800},
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
    except:
        pass
    
    # Fallback se DeepSeek fallisce
    return f"📚 {doc_text[:200]}\n\n🌐 {web_text[:200]}"

@app.route('/')
def index():
    return render_template_string("""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oracolo Covolo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system; background: linear-gradient(135deg, #0f172e 0%, #1a1f3a 100%); color: #e0e0e0; min-height: 100vh; display: flex; }
        .container { display: flex; width: 100%; height: 100vh; }
        .sidebar { width: 340px; background: rgba(15, 23, 46, 0.8); border-right: 1px solid rgba(59, 130, 245, 0.2); padding: 20px; overflow-y: auto; }
        .main { flex: 1; display: flex; flex-direction: column; }
        .header { background: rgba(59, 130, 245, 0.1); border-bottom: 1px solid rgba(59, 130, 245, 0.2); padding: 20px; text-align: center; }
        .header h1 { color: #3b82f6; font-size: 28px; }
        .chat-area { flex: 1; display: flex; flex-direction: column; padding: 20px; overflow-y: auto; }
        .messages { flex: 1; overflow-y: auto; margin-bottom: 20px; }
        .message { margin-bottom: 15px; padding: 12px 15px; border-radius: 8px; max-width: 88%; word-wrap: break-word; }
        .bot-message { background: rgba(59, 130, 245, 0.2); border-left: 3px solid #3b82f6; }
        .user-message { background: rgba(168, 85, 247, 0.2); border-left: 3px solid #a855f7; margin-left: auto; }
        .image-gallery { margin-top: 10px; display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; }
        .image-item { border-radius: 8px; overflow: hidden; border: 2px solid rgba(16, 185, 129, 0.5); }
        .image-item img { width: 100%; height: 80px; object-fit: cover; }
        .add-to-cart { background: #10b981; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; margin-top: 8px; }
        .input-area { display: flex; gap: 10px; }
        input { flex: 1; background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(59, 130, 245, 0.3); color: #e0e0e0; padding: 10px 15px; border-radius: 6px; }
        button { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
        .sidebar h3 { color: #3b82f6; margin-top: 20px; margin-bottom: 12px; font-size: 13px; text-transform: uppercase; }
        .sidebar h3:first-child { margin-top: 0; }
        .cart-item { background: rgba(59, 130, 245, 0.1); padding: 8px; margin-bottom: 6px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; }
        .source-badge { display: inline-block; background: #10b981; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin-top: 8px; }
        .file-input-area { border: 2px dashed rgba(59, 130, 245, 0.3); padding: 10px; border-radius: 6px; text-align: center; cursor: pointer; margin-bottom: 12px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h3>🏢 Aziende</h3>
            <div style="display: flex; gap: 6px; margin-bottom: 10px;">
                <input type="text" id="new-azienda-nome" placeholder="Nome..." style="flex: 1; font-size: 12px; padding: 6px;">
                <button onclick="addAzienda()" style="padding: 6px 12px; font-size: 12px;">➕</button>
            </div>
            <div id="aziende-list"></div>
            
            <h3>📁 Documenti</h3>
            <div class="file-input-area" onclick="document.getElementById('file-input').click()">
                📤 Carica
                <input type="file" id="file-input" hidden multiple onchange="uploadFile(this)">
            </div>
            <div id="files-list"></div>
            
            <h3>🛒 Carrello Proposta</h3>
            <div id="cart-list"></div>
            <button onclick="generateOfferta()" style="width: 100%; margin-top: 10px; background: #10b981;">📄 GENERA OFFERTA</button>
        </div>
        
        <div class="main">
            <div class="header">
                <h1>🔮 Oracolo Covolo</h1>
                <p>Docs Interni + Web Intelligente</p>
            </div>
            
            <div class="chat-area">
                <div class="messages" id="messages"></div>
                <div class="input-area">
                    <input type="text" id="question" placeholder="Domanda..." onkeypress="if(event.key==='Enter') sendQuestion()">
                    <button onclick="sendQuestion()">Invia</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let selectedAziende = [];
        let currentResponse = null;
        let currentImages = [];
        let currentSource = null;
        
        async function sendQuestion() {
            const input = document.getElementById('question');
            const question = input.value.trim();
            if (!question) return;
            
            const messagesDiv = document.getElementById('messages');
            messagesDiv.innerHTML += '<div class="message user-message">' + question + '</div>';
            
            const loadingMsg = document.createElement('div');
            loadingMsg.className = 'message bot-message';
            loadingMsg.innerHTML = '⏳ Ricercando...';
            messagesDiv.appendChild(loadingMsg);
            input.value = '';
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
            try {
                const response = await fetch('/api/ask-smart', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({question: question, azienda_ids: selectedAziende})
                });
                const data = await response.json();
                
                messagesDiv.removeChild(loadingMsg);
                
                currentResponse = data.answer;
                currentImages = data.images || [];
                currentSource = data.source || 'SCONOSCIUTO';
                
                let msgHtml = '<div class="message bot-message">' + data.answer + 
                    '<div class="source-badge">' + currentSource + '</div>';
                
                if (data.images && data.images.length > 0) {
                    msgHtml += '<div class="image-gallery">';
                    data.images.forEach(img => {
                        msgHtml += '<div class="image-item"><img src="data:image/jpeg;base64,' + img.substring(0, 50) + '..."></div>';
                    });
                    msgHtml += '</div>';
                }
                
                msgHtml += '<button class="add-to-cart" onclick="addToCart()">✅ AGGIUNGI A PROPOSTA</button></div>';
                
                messagesDiv.innerHTML += msgHtml;
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            } catch (e) {
                messagesDiv.removeChild(loadingMsg);
                messagesDiv.innerHTML += '<div class="message bot-message">❌ Errore: ' + e + '</div>';
            }
        }
        
        function addToCart() {
            if (!currentResponse) {alert('Nessuna risposta'); return;}
            const productName = prompt('Nome prodotto:');
            if (!productName) return;
            
            fetch('/api/add-to-cart', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({response: currentResponse, images: currentImages, product_name: productName, source: currentSource})
            }).then(() => {
                alert('✅ In carrello!');
                loadCart();
                currentResponse = null;
            });
        }
        
        async function loadCart() {
            const response = await fetch('/api/cart');
            const data = await response.json();
            const cartList = document.getElementById('cart-list');
            cartList.innerHTML = data.cart.map(item => 
                '<div class="cart-item"><span>' + item.product_name + '<br><small>' + item.source + '</small></span><button onclick="removeFromCart(' + item.id + ')" style="padding: 2px 6px; background: #ef4444; font-size: 11px;">✕</button></div>'
            ).join('');
        }
        
        async function removeFromCart(id) {
            await fetch('/api/cart/' + id, {method: 'DELETE'});
            loadCart();
        }
        
        async function generateOfferta() {
            const response = await fetch('/api/generate-offerta-from-cart', {method: 'POST'});
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'Proposta_Covolo_' + new Date().toISOString().split('T')[0] + '.html';
            a.click();
        }
        
        async function uploadFile(input) {
            const files = Array.from(input.files);
            const formData = new FormData();
            files.forEach(f => formData.append('files', f));
            if (selectedAziende.length > 0) formData.append('azienda_ids', selectedAziende.join(','));
            await fetch('/api/upload', {method: 'POST', body: formData});
            loadFiles();
            alert('✅ Documenti caricati!');
        }
        
        async function loadFiles() {
            if (selectedAziende.length === 0) {document.getElementById('files-list').innerHTML = ''; return;}
            const response = await fetch('/api/documents?azienda_ids=' + selectedAziende.join(','));
            const data = await response.json();
            document.getElementById('files-list').innerHTML = data.documents.map(doc => 
                '<div class="cart-item"><span>📄 ' + doc.filename + '</span><button onclick="deleteFile(\'' + doc.filename + '\')" style="padding: 2px 6px; background: #ef4444; font-size: 11px;">✕</button></div>'
            ).join('');
        }
        
        async function deleteFile(filename) {
            await fetch('/api/documents/' + filename, {method: 'DELETE'});
            loadFiles();
        }
        
        async function addAzienda() {
            const nome = document.getElementById('new-azienda-nome').value.trim();
            if (!nome) {alert('Nome azienda'); return;}
            await fetch('/api/aziende', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nome: nome})});
            document.getElementById('new-azienda-nome').value = '';
            loadAziende();
        }
        
        async function loadAziende() {
            const response = await fetch('/api/aziende');
            const data = await response.json();
            document.getElementById('aziende-list').innerHTML = data.aziende.map(az => 
                '<div style="background: rgba(59, 130, 245, 0.1); padding: 8px; margin-bottom: 6px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; font-size: 12px;"><input type="checkbox" id="az-' + az.id + '" value="' + az.id + '" onchange="updateSelectedAziende()" style="margin-right: 6px;"><label for="az-' + az.id + '">' + az.nome + '</label><button style="padding: 2px 6px; background: #ef4444; font-size: 11px;" onclick="deleteAzienda(' + az.id + ')">✕</button></div>'
            ).join('');
        }
        
        function updateSelectedAziende() {
            selectedAziende = Array.from(document.querySelectorAll('input[type=checkbox]:checked')).map(el => el.value);
            loadFiles();
        }
        
        async function deleteAzienda(id) {
            if (confirm('Elimina azienda?')) {await fetch('/api/aziende/' + id, {method: 'DELETE'}); loadAziende();}
        }
        
        loadAziende();
        loadCart();
    </script>
</body>
</html>""")

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
        return jsonify({"status": "error"}), 400

@app.route('/api/aziende/<azienda_id>', methods=['DELETE'])
def delete_azienda(azienda_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM aziende WHERE id = ?', (azienda_id,))
    c.execute('DELETE FROM documents WHERE azienda_id = ?', (azienda_id,))
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

@app.route('/api/ask-smart', methods=['POST'])
def ask_smart():
    data = request.get_json()
    question = data.get('question', '').strip()
    azienda_ids = data.get('azienda_ids', [])
    
    # Cerca nei documenti
    doc_result = search_documents(question, azienda_ids if azienda_ids else None)
    
    # Cerca su web
    web_result = search_web(question)
    web_text, web_images = web_result
    
    # Logica MERGE intelligente
    if doc_result and web_text:
        # ENTRAMBI trovati - Sintetizza con AI
        doc_file, doc_text = doc_result
        answer = synthesis_with_ai(question, doc_text, doc_file, web_text)
        source = "📚 DOCUMENTO + 🌐 WEB (SINTETIZZATO)"
        images = web_images
    elif doc_result:
        # SOLO documento interno
        doc_file, doc_text = doc_result
        answer = f"📚 **Secondo nostri documenti** ({doc_file}):\n\n{doc_text[:600]}"
        source = "📚 DOCUMENTO INTERNO"
        images = []
    elif web_text:
        # SOLO web
        answer = f"🌐 **Ricerca web:**\n\n{web_text}"
        source = "🌐 WEB SEARCH"
        images = web_images
    else:
        # Niente trovato
        answer = "❌ Nessuna informazione trovata né nei documenti né su web. Prova a caricare documentazione o riformula la domanda."
        source = "NESSUNO"
        images = []
    
    return jsonify({"answer": answer, "images": images, "source": source})

@app.route('/api/add-to-cart', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO selection_cart (response, images, product_name, source) VALUES (?, ?, ?, ?)',
              (data.get('response', ''), json.dumps(data.get('images', [])), data.get('product_name', ''), data.get('source', '')))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/cart', methods=['GET'])
def get_cart():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, product_name, response, source FROM selection_cart')
    cart = [{"id": row[0], "product_name": row[1], "response": row[2], "source": row[3]} for row in c.fetchall()]
    conn.close()
    return jsonify({"cart": cart})

@app.route('/api/cart/<cart_id>', methods=['DELETE'])
def remove_from_cart(cart_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM selection_cart WHERE id = ?', (cart_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/generate-offerta-from-cart', methods=['POST'])
def generate_offerta():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT product_name, response, source FROM selection_cart')
    items = c.fetchall()
    conn.close()
    
    if not items:
        html = "<html><body><h1>Carrello vuoto</h1></body></html>"
    else:
        items_html = "\n".join([f"<li><h3>{item[0]}</h3><p>{item[1][:500]}</p><small>Fonte: {item[2]}</small></li>" for item in items])
        html = f"""<html><head><meta charset='UTF-8'><style>body{{font-family: Arial; margin: 40px; background: #f5f5f5;}} h1{{color: #0066cc;}} li{{background: white; padding: 15px; margin: 10px 0; border-left: 4px solid #0066cc; border-radius: 4px;}}</style></head><body>
        <h1>PROPOSTA COMMERCIALE COVOLO</h1>
        <p><strong>Data:</strong> {datetime.now().strftime('%d/%m/%Y')}</p>
        <h2>Prodotti e Soluzioni Selezionate</h2>
        <ul style="list-style: none; padding: 0;">{items_html}</ul>
        <h2>💰 PROSSIMO PASSO</h2>
        <p><strong>Aggiungi i PREZZI da Excel</strong> - Compila la colonna prezzi utilizzando le tariffe attuali dal file Excel Covolo.</p>
        <p style="color: #666; font-size: 12px; margin-top: 30px;">Proposta generata da ORACOLO COVOLO</p>
        </body></html>"""
    
    return send_file(BytesIO(html.encode('utf-8')), mimetype='text/html', as_attachment=True, download_name=f'Proposta_Covolo_{datetime.now().strftime("%d%m%Y")}.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
