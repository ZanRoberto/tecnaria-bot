"""
ORACOLO COVOLO - VERSIONE COMPLETA E FUNZIONANTE
==================================================
Doc Interni + Web Search + Smart Merge + 3 Agenti + Carrello
"""

import os, json, sqlite3, base64, re
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file
import httpx
from urllib.parse import quote
from io import BytesIO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "oracolo_covolo.db")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS aziende (id INTEGER PRIMARY KEY, nome TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, filename TEXT UNIQUE, content TEXT, azienda_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cart (id INTEGER PRIMARY KEY, product_name TEXT, response TEXT, source TEXT, images TEXT)''')
    conn.commit()
    
    # SEED 74 BRAND COVOLO se DB è vuoto
    c.execute('SELECT COUNT(*) FROM aziende')
    if c.fetchone()[0] == 0:
        brands = ["Artesia","Ariostea","Madegan","Tonalite","Gruppo Bardelli","Schlüter Systems","Murexin","BGP","Gridiron","Cerasarda","Gigacer","FAP Ceramiche","Caesar","Cottodeste","Piastrelle d'Arredo","Mirage","Bauwerk","Gerflor","Casalgrande Padana","Aparici","Iniziativa Legno","FMG","Profiletec","Baufloor","Marca Corona","Italgraniti","Sichenia","Apavisa","Bisazza","Iris","CP Parquet","Ier Hürne","Floorim","Edimax Astor","Inklostro Bianco","GOman","Tubes","Sunshower","Noorth","Kaldewei","Valdama","Blue Design","DoorAmeda","Antoniolupi","Tresse","Colombo","Gruppo Geromin","Altamarea","Vismara Vetro","Demm","Linki","SDR","Omegius","Remer","Cerasa","CSA","Simas","Cielo","Acquabella","Duscholux","Milldue","Caros","Anem","Gessi","Brera","Wedi","Decor Walther","Duravit","Austroflamm","Stüv","Glamm Fire","Trimline Fires","Sterneldesign","Sunshower Wellness"]
        for brand in brands:
            try:
                c.execute('INSERT INTO aziende (nome) VALUES (?)', (brand,))
            except:
                pass
        conn.commit()
    
    conn.close()

init_db()
app = Flask(__name__)

# ============================================================================
# FUNZIONI DI RICERCA
# ============================================================================

def search_documents(question, azienda_ids):
    """Cerca nei documenti interni"""
    try:
        if not azienda_ids or azienda_ids == ['']:
            return None
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        placeholders = ','.join('?' * len(azienda_ids))
        c.execute(f'SELECT filename, content FROM documents WHERE azienda_id IN ({placeholders})', azienda_ids)
        docs = c.fetchall()
        conn.close()
        
        if not docs:
            return None
        
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
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://www.bing.com/search?q={quote(question)}"
        response = httpx.get(url, headers=headers, timeout=10)
        
        text = ""
        if response.status_code == 200:
            snippets = re.findall(r'<p[^>]*>(.*?)</p>', response.text)
            for s in snippets[:8]:
                s_clean = re.sub(r'<[^>]+>', '', s).strip()
                if len(s_clean) > 40 and len(text) < 800:
                    text += s_clean + " "
        
        images = []
        try:
            img_url = f"https://www.bing.com/images/search?q={quote(question)}"
            img_resp = httpx.get(img_url, headers=headers, timeout=5)
            if img_resp.status_code == 200:
                img_urls = re.findall(r'murl":"([^"]+\.jpg)"', img_resp.text)
                for iu in img_urls[:3]:
                    try:
                        img_data = httpx.get(iu, timeout=3, headers=headers)
                        if img_data.status_code == 200:
                            images.append(base64.b64encode(img_data.content).decode()[:150])
                    except:
                        pass
        except:
            pass
        
        return text.strip() if text else None, images
    except:
        return None, []

def deepseek_merge(question, doc_text, doc_file, web_text):
    """Usa DeepSeek per sintetizzare doc + web"""
    try:
        prompt = f"""Sei consulente senior arredo bagno.
DOMANDA: {question}
DOC ({doc_file}): {doc_text[:300]}
WEB: {web_text[:300]}
Sintetizza meglio, priorità doc se specifico. 2-3 paragrafi."""
        
        resp = httpx.post(DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.5, "max_tokens": 800},
            timeout=15)
        
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except:
        pass
    
    return f"📚 {doc_text[:250]}\n\n🌐 {web_text[:250]}"

# ============================================================================
# LOGICA PRINCIPALE
# ============================================================================

def smart_answer(question, azienda_ids):
    """Logica intelligente: doc → web → merge → sceglie migliore"""
    
    doc_result = search_documents(question, azienda_ids)
    web_text, web_images = search_web(question)
    
    if doc_result and web_text:
        # ENTRAMBI - Sintetizza
        doc_file, doc_text = doc_result
        answer = deepseek_merge(question, doc_text, doc_file, web_text)
        source = "📚 DOC + 🌐 WEB (SINTETIZZATO)"
        images = web_images
    elif doc_result:
        # SOLO DOC
        doc_file, doc_text = doc_result
        answer = f"📚 **Secondo nostri documenti** ({doc_file}):\n\n{doc_text[:500]}"
        source = "📚 DOCUMENTO"
        images = []
    elif web_text:
        # SOLO WEB
        answer = f"🌐 **Ricerca web:**\n\n{web_text}"
        source = "🌐 WEB"
        images = web_images
    else:
        # NIENTE
        answer = "❌ Nessuna informazione trovata"
        source = "❌ NESSUNO"
        images = []
    
    return answer, images, source

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    html = """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Oracolo Covolo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system; background: linear-gradient(135deg, #0f172e 0%, #1a1f3a 100%); color: #e0e0e0; min-height: 100vh; display: flex; }
        .container { display: flex; width: 100%; height: 100vh; }
        .sidebar { width: 340px; background: rgba(15, 23, 46, 0.8); border-right: 1px solid rgba(59, 130, 245, 0.2); padding: 20px; overflow-y: auto; }
        .main { flex: 1; display: flex; flex-direction: column; }
        .header { background: rgba(59, 130, 245, 0.1); border-bottom: 1px solid rgba(59, 130, 245, 0.2); padding: 20px; text-align: center; }
        .header h1 { color: #3b82f6; font-size: 28px; }
        .agents-bar { background: rgba(59, 130, 245, 0.05); border-bottom: 1px solid rgba(59, 130, 245, 0.2); padding: 10px 20px; display: flex; gap: 10px; }
        .agent-btn { background: #10b981; color: white; border: none; padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; }
        .agent-btn:hover { background: #059669; }
        .agent-btn.disabled { background: #6b7280; cursor: not-allowed; }
        .chat-area { flex: 1; display: flex; flex-direction: column; padding: 20px; overflow-y: auto; }
        .messages { flex: 1; overflow-y: auto; margin-bottom: 20px; }
        .message { margin-bottom: 15px; padding: 12px 15px; border-radius: 8px; max-width: 88%; word-wrap: break-word; }
        .bot-message { background: rgba(59, 130, 245, 0.2); border-left: 3px solid #3b82f6; }
        .user-message { background: rgba(168, 85, 247, 0.2); border-left: 3px solid #a855f7; margin-left: auto; }
        .image-gallery { margin-top: 10px; display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; }
        .image-item { border-radius: 8px; overflow: hidden; border: 2px solid rgba(16, 185, 129, 0.5); }
        .image-item img { width: 100%; height: 80px; object-fit: cover; }
        .btn-cart { background: #10b981; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; margin-top: 8px; }
        .input-area { display: flex; gap: 10px; }
        input { flex: 1; background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(59, 130, 245, 0.3); color: #e0e0e0; padding: 10px 15px; border-radius: 6px; }
        button { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
        .sidebar h3 { color: #3b82f6; margin-top: 20px; margin-bottom: 12px; font-size: 13px; text-transform: uppercase; }
        .sidebar h3:first-child { margin-top: 0; }
        .item { background: rgba(59, 130, 245, 0.1); padding: 8px; margin-bottom: 6px; border-radius: 4px; display: flex; justify-content: space-between; font-size: 12px; }
        .badge { display: inline-block; background: #10b981; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px; margin-top: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h3>🏢 Aziende</h3>
            <div style="display: flex; gap: 6px; margin-bottom: 10px;">
                <input type="text" id="new-azienda" placeholder="Nome..." style="flex: 1; font-size: 12px; padding: 6px;">
                <button onclick="addAzienda()" style="padding: 6px 12px; font-size: 12px;">➕</button>
            </div>
            <div id="aziende-list"></div>
            
            <h3>📁 Documenti</h3>
            <div style="border: 2px dashed rgba(59, 130, 245, 0.3); padding: 10px; border-radius: 6px; text-align: center; cursor: pointer; margin-bottom: 12px; font-size: 12px;" onclick="document.getElementById('file-input').click()">
                📤 Carica
                <input type="file" id="file-input" hidden multiple onchange="uploadFile(this)">
            </div>
            <div id="files-list"></div>
            
            <h3>🛒 Carrello</h3>
            <div id="cart-list"></div>
            <button onclick="generateOfferta()" style="width: 100%; margin-top: 10px; background: #10b981;">📄 OFFERTA</button>
        </div>
        
        <div class="main">
            <div class="header">
                <h1>🔮 Oracolo Covolo</h1>
                <p>Documenti + Web Intelligente</p>
            </div>
            
            <div class="agents-bar">
                <button class="agent-btn" id="btn-offerta" onclick="generateOfferta()" disabled>📄 OFFERTA</button>
                <button class="agent-btn" id="btn-analisi" onclick="alert('Analisi prossimamente')" disabled>📊 ANALISI</button>
                <button class="agent-btn" id="btn-proposta" onclick="alert('Proposta prossimamente')" disabled>🎯 PROPOSTA</button>
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
        
        function updateAgentButtons() {
            const hasAziende = selectedAziende.length > 0;
            document.getElementById('btn-offerta').disabled = !hasAziende;
            document.getElementById('btn-analisi').disabled = !hasAziende;
            document.getElementById('btn-proposta').disabled = !hasAziende;
        }
        
        async function sendQuestion() {
            const input = document.getElementById('question');
            const q = input.value.trim();
            if (!q) return;
            
            const msg = document.getElementById('messages');
            msg.innerHTML += '<div class="message user-message">' + q + '</div>';
            
            const load = document.createElement('div');
            load.className = 'message bot-message';
            load.innerHTML = '⏳ Ricercando documenti + web...';
            msg.appendChild(load);
            input.value = '';
            msg.scrollTop = msg.scrollHeight;
            
            try {
                const res = await fetch('/api/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({q: q, aids: selectedAziende})
                });
                const data = await res.json();
                
                msg.removeChild(load);
                currentResponse = data.answer;
                currentImages = data.images || [];
                currentSource = data.source || 'SCONOSCIUTO';
                
                let html = '<div class="message bot-message">' + data.answer + '<div class="badge">' + currentSource + '</div>';
                
                if (data.images && data.images.length > 0) {
                    html += '<div class="image-gallery">';
                    data.images.forEach(img => {
                        html += '<div class="image-item"><img src="data:image/jpeg;base64,' + img.substring(0, 50) + '..."></div>';
                    });
                    html += '</div>';
                }
                
                html += '<button class="btn-cart" onclick="addCart()">✅ AGGIUNGI A PROPOSTA</button></div>';
                msg.innerHTML += html;
                msg.scrollTop = msg.scrollHeight;
            } catch (e) {
                msg.removeChild(load);
                msg.innerHTML += '<div class="message bot-message">❌ Errore: ' + e + '</div>';
            }
        }
        
        function addCart() {
            if (!currentResponse) return;
            const name = prompt('Nome prodotto:');
            if (!name) return;
            
            fetch('/api/add-cart', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name, resp: currentResponse, img: JSON.stringify(currentImages), src: currentSource})
            }).then(() => {
                loadCart();
                currentResponse = null;
            });
        }
        
        async function loadCart() {
            const res = await fetch('/api/cart');
            const data = await res.json();
            document.getElementById('cart-list').innerHTML = data.items.map(i => 
                '<div class="item"><span>' + i.name + '</span><button onclick="removeCart(' + i.id + ')" style="padding: 2px 6px; background: #ef4444; font-size: 11px;">✕</button></div>'
            ).join('');
        }
        
        async function removeCart(id) {
            await fetch('/api/cart/' + id, {method: 'DELETE'});
            loadCart();
        }
        
        async function generateOfferta() {
            const res = await fetch('/api/offerta', {method: 'POST'});
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'Proposta_' + new Date().toISOString().split('T')[0] + '.html';
            a.click();
        }
        
        async function uploadFile(input) {
            const files = Array.from(input.files);
            const fd = new FormData();
            files.forEach(f => fd.append('files', f));
            if (selectedAziende.length > 0) fd.append('aids', selectedAziende.join(','));
            await fetch('/api/upload', {method: 'POST', body: fd});
            loadFiles();
        }
        
        async function loadFiles() {
            if (!selectedAziende.length) {document.getElementById('files-list').innerHTML = ''; return;}
            const res = await fetch('/api/files?aids=' + selectedAziende.join(','));
            const data = await res.json();
            document.getElementById('files-list').innerHTML = data.files.map(f => 
                '<div class="item"><span>📄 ' + f + '</span><button onclick="deleteFile(\'' + f + '\')" style="padding: 2px 6px; background: #ef4444; font-size: 11px;">✕</button></div>'
            ).join('');
        }
        
        async function deleteFile(f) {
            await fetch('/api/files/' + f, {method: 'DELETE'});
            loadFiles();
        }
        
        async function addAzienda() {
            const name = document.getElementById('new-azienda').value.trim();
            if (!name) return;
            await fetch('/api/aziende', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nome: name})});
            document.getElementById('new-azienda').value = '';
            loadAziende();
        }
        
        async function loadAziende() {
            const res = await fetch('/api/aziende');
            const data = await res.json();
            document.getElementById('aziende-list').innerHTML = data.items.map(a => 
                '<div class="item"><input type="checkbox" value="' + a.id + '" onchange="updateAziende()" style="margin-right: 6px;"><label>' + a.nome + '</label><button style="padding: 2px 6px; background: #ef4444; font-size: 11px;" onclick="delAzienda(' + a.id + ')">✕</button></div>'
            ).join('');
        }
        
        function updateAziende() {
            selectedAziende = Array.from(document.querySelectorAll('input[type=checkbox]:checked')).map(e => e.value);
            loadFiles();
            updateAgentButtons();
        }
        
        async function delAzienda(id) {
            if (!confirm('Elimina?')) return;
            await fetch('/api/aziende/' + id, {method: 'DELETE'});
            loadAziende();
            updateAziende();
        }
        
        loadAziende();
        loadCart();
    </script>
</body>
</html>"""
    return render_template_string(html)

@app.route('/api/aziende', methods=['GET'])
def get_aziende():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, nome FROM aziende')
    items = [{"id": str(r[0]), "nome": r[1]} for r in c.fetchall()]
    conn.close()
    return jsonify({"items": items})

@app.route('/api/aziende', methods=['POST'])
def add_azienda():
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO aziende (nome) VALUES (?)', (data['nome'],))
        conn.commit()
    except:
        pass
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/aziende/<aid>', methods=['DELETE'])
def del_azienda(aid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM aziende WHERE id=?', (aid,))
    c.execute('DELETE FROM documents WHERE azienda_id=?', (aid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/files', methods=['GET'])
def get_files():
    aids = request.args.get('aids', '').split(',')
    if not aids or aids == ['']:
        return jsonify({"files": []})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ','.join('?' * len(aids))
    c.execute(f'SELECT DISTINCT filename FROM documents WHERE azienda_id IN ({placeholders})', aids)
    files = [r[0] for r in c.fetchall()]
    conn.close()
    return jsonify({"files": files})

@app.route('/api/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files')
    aids = request.form.get('aids', '').split(',') if request.form.get('aids') else ['1']
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for f in files:
        if not f.filename:
            continue
        try:
            path = os.path.join(UPLOADS_DIR, f.filename)
            f.save(path)
            with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                content = fp.read()
            for aid in aids:
                c.execute('INSERT OR REPLACE INTO documents (filename, content, azienda_id) VALUES (?, ?, ?)',
                          (f.filename, content, aid))
        except:
            pass
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/files/<fname>', methods=['DELETE'])
def del_file(fname):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM documents WHERE filename=?', (fname,))
    conn.commit()
    conn.close()
    path = os.path.join(UPLOADS_DIR, fname)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"ok": True})

@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.get_json()
    q = data.get('q', '').strip()
    aids = data.get('aids', [])
    
    answer, images, source = smart_answer(q, aids)
    
    return jsonify({"answer": answer, "images": images, "source": source})

@app.route('/api/add-cart', methods=['POST'])
def add_cart():
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO cart (product_name, response, source, images) VALUES (?, ?, ?, ?)',
              (data['name'], data['resp'], data['src'], data['img']))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/cart', methods=['GET'])
def get_cart():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, product_name FROM cart')
    items = [{"id": r[0], "name": r[1]} for r in c.fetchall()]
    conn.close()
    return jsonify({"items": items})

@app.route('/api/cart/<cid>', methods=['DELETE'])
def del_cart(cid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM cart WHERE id=?', (cid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/offerta', methods=['POST'])
def offerta():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT product_name, response, source FROM cart')
    items = c.fetchall()
    conn.close()
    
    html = f"""<html><head><meta charset='UTF-8'><style>body{{font-family: Arial; margin: 40px; background: #f5f5f5;}} h1{{color: #0066cc;}} li{{background: white; padding: 15px; margin: 10px 0; border-left: 4px solid #0066cc; border-radius: 4px;}}</style></head><body>
    <h1>PROPOSTA COMMERCIALE COVOLO - {datetime.now().strftime('%d/%m/%Y')}</h1>
    <ul style="list-style: none; padding: 0;">{''.join([f'<li><h3>{i[0]}</h3><p>{i[1][:400]}</p><small>Fonte: {i[2]}</small></li>' for i in items])}</ul>
    <h2>💰 Aggiungi prezzi da Excel</h2>
    </body></html>"""
    
    return send_file(BytesIO(html.encode('utf-8')), mimetype='text/html', as_attachment=True, download_name=f'Proposta_{datetime.now().strftime("%d%m%Y")}.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
