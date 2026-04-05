"""
ORACOLO COVOLO - VERSIONE RISOLTA
"""
import os, sqlite3, base64, re, json
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file
import httpx
from urllib.parse import quote
from io import BytesIO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "oracolo_covolo.db")

os.makedirs(DATA_DIR, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS aziende (id INTEGER PRIMARY KEY, nome TEXT UNIQUE)')
    c.execute('CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, filename TEXT UNIQUE, content TEXT, azienda_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS product_images (id INTEGER PRIMARY KEY, product_name TEXT, azienda_id INTEGER, image_base64 TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS presets (id INTEGER PRIMARY KEY, nome TEXT UNIQUE, azienda_ids TEXT)')
    conn.commit()
    conn.close()

init_db()
app = Flask(__name__)

BRANDS = [
    "Artesia", "Ariostea", "Madegan", "Tonalite", "Gruppo Bardelli",
    "Schlüter Systems", "Murexin", "BGP", "Gridiron", "Cerasarda",
    "Gigacer", "FAP Ceramiche", "Caesar", "Cottodeste", "Piastrelle d'Arredo",
    "Mirage", "Bauwerk", "Gerflor", "Casalgrande Padana", "Aparici",
    "Iniziativa Legno", "FMG", "Profiletec", "Baufloor", "Marca Corona",
    "Italgraniti", "Sichenia", "Apavisa", "Bisazza", "Iris", "CP Parquet",
    "Ier Hürne", "Floorim", "Edimax Astor", "Inklostro Bianco",
    "GOman", "Tubes", "Sunshower", "Noorth", "Kaldewei", "Valdama",
    "Blue Design", "DoorAmeda", "Antoniolupi", "Tresse", "Colombo",
    "Gruppo Geromin", "Altamarea", "Vismara Vetro", "Demm", "Linki",
    "SDR", "Omegius", "Remer", "Cerasa", "CSA", "Simas", "Cielo",
    "Acquabella", "Duscholux", "Milldue", "Caros", "Anem",
    "Gessi", "Brera", "Wedi", "Decor Walther", "Duravit",
    "Austroflamm", "Stüv", "Glamm Fire", "Trimline Fires",
    "Sterneldesign", "Sunshower Wellness"
]

def search_web(q):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://www.bing.com/search?q={quote(q)}"
        resp = httpx.get(url, headers=headers, timeout=10)
        text = ""
        if resp.status_code == 200:
            snippets = re.findall(r'<p[^>]*>(.*?)</p>', resp.text)
            for s in snippets[:5]:
                clean = re.sub(r'<[^>]+>', '', s).strip()
                if len(clean) > 40: text += clean + " "
        return text[:500] if text else None
    except:
        return None

def deepseek_ask(prompt):
    try:
        resp = httpx.post(DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.5, "max_tokens": 800},
            timeout=15)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except:
        pass
    return None

@app.route('/')
def index():
    return render_template_string("""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Oracolo Covolo</title><style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system; background: linear-gradient(135deg, #0f172e 0%, #1a1f3a 100%); color: #e0e0e0; min-height: 100vh; }
.container { display: flex; height: 100vh; }
.sidebar { width: 340px; background: rgba(15,23,46,0.8); border-right: 1px solid rgba(59,130,245,0.2); padding: 20px; overflow-y: auto; }
.main { flex: 1; display: flex; flex-direction: column; }
.header { background: rgba(59,130,245,0.1); border-bottom: 1px solid rgba(59,130,245,0.2); padding: 20px; text-align: center; }
.header h1 { color: #3b82f6; font-size: 28px; }
.actions-bar { background: rgba(59,130,245,0.05); border-bottom: 1px solid rgba(59,130,245,0.2); padding: 10px 20px; display: flex; gap: 10px; justify-content: center; }
.action-btn { background: #10b981; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; }
.action-btn:hover { background: #059669; }
.action-btn.disabled { background: #6b7280; cursor: not-allowed; }
.chat-area { flex: 1; display: flex; flex-direction: column; padding: 20px; overflow-y: auto; }
.messages { flex: 1; overflow-y: auto; margin-bottom: 20px; }
.message { margin-bottom: 15px; padding: 12px 15px; border-radius: 8px; max-width: 88%; word-wrap: break-word; }
.bot-message { background: rgba(59,130,245,0.2); border-left: 3px solid #3b82f6; }
.user-message { background: rgba(168,85,247,0.2); border-left: 3px solid #a855f7; margin-left: auto; }
.input-area { display: flex; gap: 10px; }
input { flex: 1; background: rgba(30,41,59,0.8); border: 1px solid rgba(59,130,245,0.3); color: #e0e0e0; padding: 10px 15px; border-radius: 6px; }
button { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
.sidebar h3 { color: #3b82f6; margin-top: 20px; margin-bottom: 12px; font-size: 13px; text-transform: uppercase; }
.sidebar h3:first-child { margin-top: 0; }
.brand-btn { width: 100%; background: #3b82f6; color: white; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; font-weight: 600; margin-bottom: 10px; }
.brand-btn:hover { background: #2563eb; }
.brand-list { background: rgba(30,41,59,0.95); border: 1px solid rgba(59,130,245,0.5); border-radius: 6px; padding: 10px; max-height: 250px; overflow-y: auto; margin-bottom: 10px; }
.brand-list input { width: 100%; margin-bottom: 10px; padding: 8px; font-size: 12px; }
.brand-item { padding: 8px; cursor: pointer; border-radius: 4px; font-size: 12px; margin-bottom: 4px; background: rgba(59,130,245,0.1); }
.brand-item:hover { background: rgba(59,130,245,0.3); }
.brand-item.selected { background: #10b981; color: white; }
.selected-brands { background: rgba(59,130,245,0.1); padding: 8px; border-radius: 4px; margin-bottom: 10px; min-height: 30px; display: flex; flex-wrap: wrap; gap: 6px; }
.brand-badge { background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; display: flex; gap: 4px; }
.brand-badge button { background: transparent; color: white; border: none; cursor: pointer; padding: 0; font-size: 12px; }
</style></head><body>
<div class="container">
<div class="sidebar">
<h3>🏢 Seleziona Brand</h3>
<button class="brand-btn" id="toggle-btn" onclick="toggleDropdown()">🔽 Aggiungi Brand</button>
<div id="brand-dropdown" style="display: none;">
<input type="text" id="search-input" placeholder="Ricerca brand..." onkeyup="filterBrands()">
<div id="brands-container"></div>
</div>
<div class="selected-brands" id="selected-container"><span style="font-size: 11px; color: #9ca3af;">Nessun brand</span></div>

<h3>🌐 Web Search</h3>
<button style="width: 100%; background: #10b981; padding: 10px; border-radius: 6px; border: none; color: white; cursor: pointer; font-weight: 600;" id="web-btn" onclick="toggleWeb()">🟢 ON</button>

<h3>📁 Documenti</h3>
<div style="border: 2px dashed rgba(59,130,245,0.3); padding: 10px; border-radius: 6px; text-align: center; cursor: pointer; font-size: 12px;" onclick="document.getElementById('file-input').click()">📤 Carica
<input type="file" id="file-input" hidden multiple></div>
</div>

<div class="main">
<div class="header"><h1>🔮 Oracolo Covolo</h1><p>Consulente Arredo Bagno</p></div>
<div class="actions-bar">
<button class="action-btn" id="btn-offerta" onclick="alert('OFFERTA in prep')" disabled>📄 OFFERTA</button>
<button class="action-btn" id="btn-analisi" onclick="alert('ANALISI in prep')" disabled>📊 ANALISI</button>
<button class="action-btn" id="btn-proposta" onclick="alert('PROPOSTA in prep')" disabled>🎯 PROPOSTA</button>
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
let selectedBrands = [];
let allBrands = """ + json.dumps(BRANDS) + """;
let webEnabled = true;

function toggleDropdown() {
    const dropdown = document.getElementById('brand-dropdown');
    dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
    if (dropdown.style.display === 'block') {
        renderBrands();
        document.getElementById('search-input').focus();
    }
}

function filterBrands() {
    renderBrands();
}

function renderBrands() {
    const search = document.getElementById('search-input').value.toLowerCase();
    const filtered = allBrands.filter(b => b.toLowerCase().includes(search));
    const html = filtered.map(b => 
        '<div class="brand-item ' + (selectedBrands.includes(b) ? 'selected' : '') + '" onclick="toggleBrand(\'' + b + '\')">' + b + '</div>'
    ).join('');
    document.getElementById('brands-container').innerHTML = html;
}

function toggleBrand(brand) {
    if (selectedBrands.includes(brand)) {
        selectedBrands = selectedBrands.filter(b => b !== brand);
    } else {
        selectedBrands.push(brand);
    }
    updateDisplay();
}

function removeBrand(brand) {
    selectedBrands = selectedBrands.filter(b => b !== brand);
    updateDisplay();
}

function updateDisplay() {
    const container = document.getElementById('selected-container');
    if (selectedBrands.length === 0) {
        container.innerHTML = '<span style="font-size: 11px; color: #9ca3af;">Nessun brand</span>';
    } else {
        container.innerHTML = selectedBrands.map(b =>
            '<div class="brand-badge">' + b + '<button onclick="removeBrand(\'' + b + '\')">✕</button></div>'
        ).join('');
    }
    renderBrands();
}

function toggleWeb() {
    webEnabled = !webEnabled;
    document.getElementById('web-btn').textContent = webEnabled ? '🟢 ON' : '🔴 OFF';
}

async function sendQuestion() {
    const q = document.getElementById('question').value.trim();
    if (!q) return;
    const msg = document.getElementById('messages');
    msg.innerHTML += '<div class="message user-message">' + q + '</div>';
    document.getElementById('question').value = '';
    msg.scrollTop = msg.scrollHeight;
    
    try {
        const res = await fetch('/api/ask', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({question: q, brands: selectedBrands, web: webEnabled})
        });
        const data = await res.json();
        const escaped = data.answer.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        msg.innerHTML += '<div class="message bot-message">' + escaped + '</div>';
        msg.scrollTop = msg.scrollHeight;
    } catch (e) {
        msg.innerHTML += '<div class="message bot-message">❌ Errore: ' + e + '</div>';
    }
}

// Init
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Brand caricati:', allBrands.length);
});
</script>
</body></html>""")

@app.route('/api/aziende', methods=['GET'])
def get_aziende():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, nome FROM aziende ORDER BY nome')
    aziende = [{"id": str(r[0]), "nome": r[1]} for r in c.fetchall()]
    conn.close()
    return jsonify({"aziende": aziende})

@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.get_json()
    q = data.get('question', '').strip()
    brands = data.get('brands', [])
    use_web = data.get('web', True)
    
    brands_str = ", ".join(brands) if brands else "Covolo"
    web_content = search_web(q) if use_web else None
    
    if web_content or brands:
        prompt = f"""Sei consulente arredo bagno per {brands_str}.
DOMANDA: {q}
{'WEB: ' + web_content if web_content else ''}
Rispondi professionalmente."""
        answer = deepseek_ask(prompt) or f"Consiglio su {q}"
    else:
        answer = "Abilita Web Search o seleziona un brand"
    
    return jsonify({"answer": answer})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
