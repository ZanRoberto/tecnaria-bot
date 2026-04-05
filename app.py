"""
ORACOLO COVOLO - VERSIONE CON GUARDRAIL BRAND
================================================
Ricerca SOLO sui brand selezionati - Doc interni + Web
"""

import os, json, sqlite3, base64, re
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
import httpx
from urllib.parse import quote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "oracolo_covolo.db")

os.makedirs(DATA_DIR, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

# 74 BRAND COVOLO - LISTA UFFICIALE
BRANDS_LIST = [
    "Acquabella", "Altamarea", "Anem", "Antoniolupi", "Aparici", "Apavisa",
    "Ariostea", "Artesia", "Austroflamm", "BGP", "Brera", "Bisazza",
    "Blue Design", "Baufloor", "Bauwerk", "Caros", "Caesar", "Casalgrande Padana",
    "Cerasarda", "Cerasa", "Cielo", "Colombo", "Cottodeste", "CP Parquet",
    "CSA", "Decor Walther", "Demm", "DoorAmeda", "Duscholux", "Duravit",
    "Edimax Astor", "FAP Ceramiche", "FMG", "Floorim", "Gerflor", "Gessi",
    "Gigacer", "Glamm Fire", "GOman", "Gridiron", "Gruppo Bardelli", "Gruppo Geromin",
    "Ier Hürne", "Inklostro Bianco", "Iniziativa Legno", "Iris", "Italgraniti",
    "Kaldewei", "Linki", "Madegan", "Marca Corona", "Mirage", "Milldue",
    "Murexin", "Noorth", "Omegius", "Piastrelle d'Arredo", "Profiletec", "Remer",
    "Sichenia", "Simas", "Schlüter Systems", "SDR", "Sterneldesign", "Stüv",
    "Sunshower", "Sunshower Wellness", "Tonalite", "Tresse", "Trimline Fires",
    "Tubes", "Valdama", "Vismara Vetro", "Wedi"
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Tabelle
    c.execute('''CREATE TABLE IF NOT EXISTS aziende (id INTEGER PRIMARY KEY, nome TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, filename TEXT UNIQUE, content TEXT, azienda_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS presets (id INTEGER PRIMARY KEY, nome TEXT UNIQUE, azienda_ids TEXT)''')
    
    # Carica brand se vuoto
    c.execute('SELECT COUNT(*) FROM aziende')
    if c.fetchone()[0] == 0:
        for brand in BRANDS_LIST:
            try:
                c.execute('INSERT INTO aziende (nome) VALUES (?)', (brand,))
            except:
                pass
    
    conn.commit()
    conn.close()

init_db()
app = Flask(__name__)

def search_documents(question, selected_brands):
    """Cerca SOLO nei documenti dei brand selezionati"""
    try:
        if not selected_brands or selected_brands == ['']: 
            return None, None
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Prendi ID dei brand selezionati
        placeholders = ','.join('?' * len(selected_brands))
        c.execute(f'SELECT id FROM aziende WHERE nome IN ({placeholders})', selected_brands)
        brand_ids = [str(row[0]) for row in c.fetchall()]
        
        if not brand_ids:
            conn.close()
            return None, None
        
        # Cerca documenti SOLO per questi brand
        placeholders = ','.join('?' * len(brand_ids))
        c.execute(f'SELECT filename, content, azienda_id FROM documents WHERE azienda_id IN ({placeholders})', [int(x) for x in brand_ids])
        docs = c.fetchall()
        conn.close()
        
        if not docs:
            return None, None
        
        # Trova miglior match
        keywords = re.findall(r'\b\w{3,}\b', question.lower())
        best_match = None
        best_brand = None
        best_score = 0
        
        for filename, content, azienda_id in docs:
            score = sum(1 for kw in keywords if kw in content.lower())
            if score > best_score:
                best_score = score
                best_match = (filename, content)
                best_brand = azienda_id
        
        return best_match, best_brand if best_score > 0 else (None, None)
    except:
        return None, None

def search_web(question, selected_brands):
    """Ricerca web FILTRATA per brand selezionati"""
    try:
        if not selected_brands:
            return None, []
        
        # Crea query specifica per brand
        brands_query = " OR ".join([f'"{b}"' for b in selected_brands])
        query = f"({brands_query}) AND ({question})"
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://www.bing.com/search?q={quote(query)}"
        response = httpx.get(url, headers=headers, timeout=10)
        
        text = ""
        if response.status_code == 200:
            snippets = re.findall(r'<p[^>]*>(.*?)</p>', response.text)
            for s in snippets[:8]:
                clean = re.sub(r'<[^>]+>', '', s).strip()
                if len(clean) > 40 and len(text) < 800:
                    text += clean + " "
        
        return text[:500] if text else None, []
    except:
        return None, []

def deepseek_ask(prompt, selected_brands):
    """DeepSeek - con context sui brand selezionati"""
    try:
        brands_context = ", ".join(selected_brands) if selected_brands else "Covolo"
        full_prompt = f"""Sei consulente esperto arredo bagno per: {brands_context}

{prompt}

Rispondi SOLO per questi brand. Se la domanda riguarda altri brand, rispondi: 'Posso aiutarti solo con {brands_context}'"""
        
        resp = httpx.post(DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": full_prompt}], "temperature": 0.5, "max_tokens": 800},
            timeout=15)
        
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except:
        pass
    return None

@app.route('/')
def index():
    brands_json = json.dumps(BRANDS_LIST)
    return render_template_string('''<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Oracolo Covolo</title><style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system; background: linear-gradient(135deg, #0f172e 0%, #1a1f3a 100%); color: #e0e0e0; min-height: 100vh; }
.container { display: flex; height: 100vh; }
.sidebar { width: 340px; background: rgba(15,23,46,0.8); border-right: 1px solid rgba(59,130,245,0.2); padding: 20px; overflow-y: auto; }
.main { flex: 1; display: flex; flex-direction: column; }
.header { background: rgba(59,130,245,0.1); border-bottom: 1px solid rgba(59,130,245,0.2); padding: 20px; text-align: center; }
.header h1 { color: #3b82f6; font-size: 28px; }
.header p { color: #9ca3af; font-size: 12px; }
.actions-bar { background: rgba(59,130,245,0.05); border-bottom: 1px solid rgba(59,130,245,0.2); padding: 10px 20px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
.action-btn { background: #10b981; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; }
.action-btn:hover { background: #059669; }
.chat-area { flex: 1; display: flex; flex-direction: column; padding: 20px; overflow-y: auto; }
.messages { flex: 1; overflow-y: auto; margin-bottom: 20px; }
.message { margin-bottom: 15px; padding: 12px 15px; border-radius: 8px; max-width: 88%; word-wrap: break-word; }
.bot-message { background: rgba(59,130,245,0.2); border-left: 3px solid #3b82f6; }
.user-message { background: rgba(168,85,247,0.2); border-left: 3px solid #a855f7; margin-left: auto; }
.input-area { display: flex; gap: 10px; }
input[type="text"] { flex: 1; background: rgba(30,41,59,0.8); border: 1px solid rgba(59,130,245,0.3); color: #e0e0e0; padding: 10px 15px; border-radius: 6px; }
button { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
button:hover { background: #2563eb; }
.sidebar h3 { color: #3b82f6; margin-top: 20px; margin-bottom: 12px; font-size: 13px; text-transform: uppercase; }
.sidebar h3:first-child { margin-top: 0; }
.brand-selector-btn { width: 100%; background: #3b82f6; color: white; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; font-weight: 600; margin-bottom: 10px; }
.brand-selector-btn:hover { background: #2563eb; }
.brand-dropdown { background: rgba(30,41,59,0.95); border: 1px solid rgba(59,130,245,0.5); border-radius: 6px; padding: 10px; max-height: 300px; overflow-y: auto; margin-bottom: 10px; display: none; }
.brand-dropdown.show { display: block; }
.brand-dropdown input { width: 100%; margin-bottom: 10px; padding: 8px; font-size: 12px; background: rgba(15,23,46,0.8); border: 1px solid rgba(59,130,245,0.3); color: #e0e0e0; border-radius: 4px; }
.brand-item { padding: 8px; cursor: pointer; border-radius: 4px; font-size: 12px; margin-bottom: 4px; background: rgba(59,130,245,0.1); display: flex; align-items: center; }
.brand-item:hover { background: rgba(59,130,245,0.3); }
.brand-item input[type="checkbox"] { margin-right: 8px; cursor: pointer; }
.selected-brands { background: rgba(59,130,245,0.1); padding: 8px; border-radius: 4px; margin-bottom: 10px; min-height: 30px; display: flex; flex-wrap: wrap; gap: 6px; }
.brand-badge { background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; display: flex; gap: 4px; align-items: center; }
.brand-badge button { background: transparent; color: white; border: none; cursor: pointer; padding: 0; font-size: 12px; }
</style></head><body>
<div class="container">
<div class="sidebar">
<h3>🏢 Seleziona Brand (Guardrail)</h3>
<button class="brand-selector-btn" onclick="toggleDropdown()">🔽 Seleziona Brand</button>

<div id="brand-dropdown" class="brand-dropdown">
<input type="text" id="brand-search" placeholder="Ricerca..." onkeyup="filterBrands()">
<div id="brands-list"></div>
</div>

<div class="selected-brands" id="selected-display">
<span style="font-size: 11px; color: #9ca3af;">Nessun brand</span>
</div>

<h3>🌐 Web Search</h3>
<button style="width: 100%; background: #10b981; padding: 10px; border-radius: 6px; border: none; color: white; cursor: pointer; font-weight: 600;" id="web-btn" onclick="toggleWeb()">🟢 ON</button>

<h3>📁 Documenti</h3>
<div style="border: 2px dashed rgba(59,130,245,0.3); padding: 10px; border-radius: 6px; text-align: center; cursor: pointer; font-size: 12px; color: #9ca3af;" onclick="document.getElementById('file-input').click()">📤 Carica file
<input type="file" id="file-input" hidden multiple></div>
</div>

<div class="main">
<div class="header">
<h1>🔮 Oracolo Covolo</h1>
<p>Documenti + Web Intelligente (Guardrail Brand)</p>
</div>
<div class="actions-bar">
<button class="action-btn" disabled>📄 OFFERTA</button>
<button class="action-btn" disabled>📊 ANALISI</button>
<button class="action-btn" disabled>🎯 PROPOSTA</button>
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
const BRANDS = ''' + brands_json + ''';
let selectedBrands = [];
let webEnabled = true;

console.log("✅ App caricata - " + BRANDS.length + " brand");

function toggleDropdown() {
    const dd = document.getElementById('brand-dropdown');
    dd.classList.toggle('show');
    if (dd.classList.contains('show')) {
        filterBrands();
        setTimeout(() => document.getElementById('brand-search').focus(), 100);
    }
}

function filterBrands() {
    const search = document.getElementById('brand-search').value.toLowerCase();
    const filtered = BRANDS.filter(b => b.toLowerCase().includes(search));
    const html = filtered.map(b => 
        '<div class="brand-item"><input type="checkbox" value="' + b + '" onchange="updateBrandSelection()" ' + (selectedBrands.includes(b) ? 'checked' : '') + '>' + b + '</div>'
    ).join('');
    document.getElementById('brands-list').innerHTML = html;
}

function updateBrandSelection() {
    selectedBrands = [];
    document.querySelectorAll('.brand-item input[type="checkbox"]:checked').forEach(cb => {
        selectedBrands.push(cb.value);
    });
    updateDisplay();
}

function updateDisplay() {
    const container = document.getElementById('selected-display');
    if (selectedBrands.length === 0) {
        container.innerHTML = '<span style="font-size: 11px; color: #9ca3af;">Nessun brand</span>';
    } else {
        container.innerHTML = selectedBrands.sort().map(b =>
            '<div class="brand-badge">' + b + '<button onclick="removeBrand(\\'' + b + '\\')" style="background: transparent; color: white; border: none; cursor: pointer; padding: 0;">✕</button></div>'
        ).join('');
    }
}

function removeBrand(brand) {
    selectedBrands = selectedBrands.filter(b => b !== brand);
    updateDisplay();
    filterBrands();
}

function toggleWeb() {
    webEnabled = !webEnabled;
    document.getElementById('web-btn').textContent = webEnabled ? '🟢 ON' : '🔴 OFF';
}

async function sendQuestion() {
    const q = document.getElementById('question').value.trim();
    if (!q) return;
    if (selectedBrands.length === 0) { alert('Seleziona almeno 1 brand!'); return; }
    
    const msg = document.getElementById('messages');
    msg.innerHTML += '<div class="message user-message">' + q + '</div>';
    document.getElementById('question').value = '';
    msg.scrollTop = msg.scrollHeight;
    
    try {
        const res = await fetch('/api/ask', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                question: q,
                brands: selectedBrands,
                web: webEnabled
            })
        });
        const data = await res.json();
        const escaped = data.answer.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        msg.innerHTML += '<div class="message bot-message">' + escaped + '</div>';
        msg.scrollTop = msg.scrollHeight;
    } catch (e) {
        msg.innerHTML += '<div class="message bot-message">❌ Errore: ' + e + '</div>';
    }
}

console.log("✅ JavaScript caricato");
</script>
</body></html>''')

@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.get_json()
    q = data.get('question', '').strip()
    selected_brands = data.get('brands', [])
    use_web = data.get('web', True)
    
    if not selected_brands:
        return jsonify({"answer": "❌ Seleziona almeno 1 brand!"})
    
    # Ricerca nei documenti (GUARDRAIL: solo brand selezionati)
    doc_match, doc_brand = search_documents(q, selected_brands)
    doc_text = f"[DOC: {doc_match[0]}] {doc_match[1]}" if doc_match else None
    
    # Ricerca web (GUARDRAIL: solo brand selezionati)
    web_text = None
    if use_web:
        web_text, _ = search_web(q, selected_brands)
    
    # Genera risposta
    brands_str = ", ".join(selected_brands)
    context = ""
    if doc_text:
        context += f"\nDOCUMENTO INTERNO:\n{doc_text}"
    if web_text:
        context += f"\nWEB:\n{web_text}"
    
    prompt = f"""Domanda: {q}
Brand selezionati (GUARDRAIL): {brands_str}
{context}

Rispondi SOLO per i brand selezionati. Se la domanda non riguarda questi brand, rispondi: 'Posso aiutarti solo con {brands_str}'"""
    
    answer = deepseek_ask(prompt, selected_brands)
    if not answer:
        answer = f"Consiglio su {q} per {brands_str}"
    
    return jsonify({
        "answer": answer,
        "source": f"🎯 Filtro: {brands_str}" + (" + Web" if use_web and web_text else "")
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
