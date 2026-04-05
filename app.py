"""
ORACOLO COVOLO - SISTEMA CASSETTI CON ACCESSO PUBBLICO/PRIVATO
================================================================
Cassetti aziendali con documenti pubblici e riservati
"""

import os, json, sqlite3, base64, re, hashlib
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file
import httpx
from urllib.parse import quote
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "oracolo_covolo.db")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

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
    
    c.execute('''CREATE TABLE IF NOT EXISTS aziende (id INTEGER PRIMARY KEY, nome TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS documents 
                 (id INTEGER PRIMARY KEY, filename TEXT UNIQUE, content TEXT, azienda_id INTEGER, 
                  visibility TEXT DEFAULT 'public', access_code TEXT, upload_date TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, access_codes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS proposte 
                 (id INTEGER PRIMARY KEY, nome TEXT, brands TEXT, data TIMESTAMP, contenuto TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS access_log 
                 (id INTEGER PRIMARY KEY, username TEXT, action TEXT, brand TEXT, document TEXT, timestamp TIMESTAMP)''')
    
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

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def search_documents(question, selected_brands, access_code=None):
    """Cerca documenti in base a visibilità e accesso"""
    try:
        if not selected_brands: 
            return None, None
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        placeholders = ','.join('?' * len(selected_brands))
        c.execute(f'SELECT id FROM aziende WHERE nome IN ({placeholders})', selected_brands)
        brand_ids = [str(row[0]) for row in c.fetchall()]
        
        if not brand_ids:
            conn.close()
            return None, None
        
        # Costruisci query in base ad accesso
        if access_code:
            # Con PSW: accedi a TUTTO (public + private con accesso_code)
            query = f'''SELECT filename, content, azienda_id FROM documents 
                       WHERE azienda_id IN ({','.join('?' * len(brand_ids))})
                       AND (visibility='public' OR access_code=?)
                       ORDER BY upload_date DESC LIMIT 10'''
            c.execute(query, [int(x) for x in brand_ids] + [access_code])
        else:
            # Senza PSW: accedi SOLO a public
            query = f'''SELECT filename, content, azienda_id FROM documents 
                       WHERE azienda_id IN ({','.join('?' * len(brand_ids))})
                       AND visibility='public'
                       ORDER BY upload_date DESC LIMIT 10'''
            c.execute(query, [int(x) for x in brand_ids])
        
        docs = c.fetchall()
        conn.close()
        
        if not docs:
            return None, None
        
        keywords = re.findall(r'\b\w{3,}\b', question.lower())
        best_match = None
        best_score = 0
        
        for filename, content, azienda_id in docs:
            score = sum(1 for kw in keywords if kw in content.lower())
            if score > best_score:
                best_score = score
                best_match = (filename, content)
        
        return best_match if best_score > 0 else (None, None), None
    except Exception as e:
        print(f"[ERROR] search_documents: {e}")
        return None, None

def search_web(question, selected_brands):
    """Ricerca web filtrata per brand"""
    try:
        if not selected_brands:
            return None
        
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
        
        return text[:500] if text else None
    except:
        return None

def deepseek_ask(prompt, selected_brands, access_level="public"):
    """DeepSeek con context"""
    try:
        brands_context = ", ".join(selected_brands) if selected_brands else "Covolo"
        access_text = "PREMIUM (dati completi)" if access_level == "private" else "STANDARD (dati pubblici)"
        
        full_prompt = f"""Sei consulente esperto arredo bagno per: {brands_context}
Livello accesso: {access_text}

{prompt}

Rispondi come esperto professionale. La risposta deve essere diversa dalla domanda."""
        
        print(f"[DEEPSEEK] Calling - Access: {access_level}")
        
        resp = httpx.post(DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": full_prompt}], 
                  "temperature": 0.7, "max_tokens": 1000},
            timeout=20)
        
        if resp.status_code == 200:
            result = resp.json()["choices"][0]["message"]["content"]
            print(f"[DEEPSEEK] OK - {access_level}")
            return result
    except Exception as e:
        print(f"[DEEPSEEK] Error: {e}")
    
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
.action-btn.disabled { background: #6b7280; cursor: not-allowed; }
.chat-area { flex: 1; display: flex; flex-direction: column; padding: 20px; overflow-y: auto; }
.messages { flex: 1; overflow-y: auto; margin-bottom: 20px; }
.message { margin-bottom: 15px; padding: 12px 15px; border-radius: 8px; max-width: 88%; word-wrap: break-word; }
.bot-message { background: rgba(59,130,245,0.2); border-left: 3px solid #3b82f6; }
.user-message { background: rgba(168,85,247,0.2); border-left: 3px solid #a855f7; margin-left: auto; }
.input-area { display: flex; gap: 10px; }
input[type="text"], input[type="password"] { flex: 1; background: rgba(30,41,59,0.8); border: 1px solid rgba(59,130,245,0.3); color: #e0e0e0; padding: 10px 15px; border-radius: 6px; }
button { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
button:hover { background: #2563eb; }
.sidebar h3 { color: #3b82f6; margin-top: 20px; margin-bottom: 12px; font-size: 13px; }
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
.access-section { background: rgba(59,130,245,0.1); padding: 10px; border-radius: 6px; margin-bottom: 10px; }
.access-badge { background: #f59e0b; color: #000; padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; }
.access-badge.private { background: #ef4444; color: white; }
.group-item { background: rgba(139,92,246,0.2); border: 1px solid rgba(139,92,246,0.4); padding: 6px 8px; border-radius: 4px; margin-bottom: 6px; font-size: 11px; display: flex; justify-content: space-between; align-items: center; }
.group-item-name { cursor: pointer; flex: 1; }
.group-item-name:hover { color: #a78bfa; }
.group-item-btns { display: flex; gap: 4px; }
.group-item-btns button { padding: 2px 6px; font-size: 10px; background: #8b5cf6; border: none; color: white; border-radius: 3px; cursor: pointer; }
.group-item-btns button:hover { background: #a78bfa; }
.group-input { width: 100%; padding: 6px; font-size: 11px; background: rgba(15,23,46,0.8); border: 1px solid rgba(139,92,246,0.3); color: #e0e0e0; border-radius: 4px; margin-bottom: 6px; }

</style></head><body>
<div class="container">
<div class="sidebar">
<h3>🏢 Cassetti Aziendali</h3>
<button class="brand-selector-btn" onclick="toggleDropdown()">🔽 Seleziona Brand</button>

<div id="brand-dropdown" class="brand-dropdown">
<input type="text" id="brand-search" placeholder="Ricerca..." onkeyup="filterBrands()">
<div id="brands-list"></div>
</div>

<div class="selected-brands" id="selected-display">
<span style="font-size: 11px; color: #9ca3af;">Nessun brand</span>
</div>

<div style="display: flex; gap: 6px; margin-bottom: 10px;">
<input type="text" id="group-name" class="group-input" placeholder="Nome gruppo..." style="margin-bottom: 0;">
<button onclick="saveGroup()" style="padding: 6px 10px; font-size: 11px; background: #8b5cf6;">💾</button>
</div>

<h3>📊 Gruppi Salvati</h3>
<div id="groups-list" style="max-height: 150px; overflow-y: auto;"></div>

<div class="access-section">
<h3 style="margin-top: 0; font-size: 11px;">🔐 Accesso Privato</h3>
<input type="password" id="access-code" placeholder="Codice accesso..." style="width: 100%; padding: 6px; font-size: 11px; margin-bottom: 6px;">
<button onclick="activatePrivateAccess()" style="width: 100%; padding: 6px; font-size: 11px;">Attiva</button>
<div id="access-status" style="font-size: 11px; color: #9ca3af; margin-top: 6px;">Accesso: PUBBLICO</div>
</div>

<h3>🌐 Web Search</h3>
<button style="width: 100%; background: #10b981; padding: 10px; border-radius: 6px; border: none; color: white; cursor: pointer; font-weight: 600;" id="web-btn" onclick="toggleWeb()">🟢 ON</button>

<h3>📁 Gestione Cassetti</h3>
<button style="width: 100%; background: #8b5cf6; padding: 10px; border-radius: 6px; border: none; color: white; cursor: pointer; font-weight: 600; margin-bottom: 6px;" onclick="showUpload()">📤 Upload Doc</button>
<button style="width: 100%; background: #6366f1; padding: 10px; border-radius: 6px; border: none; color: white; cursor: pointer; font-weight: 600;" onclick="showDocuments()">📋 Documenti</button>
</div>

<div class="main">
<div class="header">
<h1>🔮 Oracolo Covolo</h1>
<p>Documenti Pubblici + Accesso Privato (Guardrail Brand)</p>
</div>
<div class="actions-bar">
<button class="action-btn" onclick="generateOfferta()">📄 OFFERTA</button>
<button class="action-btn" onclick="generateAnalisi()">📊 ANALISI</button>
<button class="action-btn" onclick="generateProposta()">🎯 PROPOSTA</button>
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
let accessCode = null;
let accessLevel = "public";
let groups = JSON.parse(localStorage.getItem('oracolo_groups')) || {};

console.log("✅ App caricata - " + BRANDS.length + " brand");

// GRUPPI FUNCTIONS
function saveGroup() {
    if (selectedBrands.length === 0) { alert('Seleziona almeno 1 brand!'); return; }
    const name = document.getElementById('group-name').value.trim();
    if (!name) { alert('Inserisci nome gruppo'); return; }
    
    groups[name] = selectedBrands;
    localStorage.setItem('oracolo_groups', JSON.stringify(groups));
    document.getElementById('group-name').value = '';
    loadGroups();
    alert('✅ Gruppo "' + name + '" salvato!');
}

function loadGroup(groupName) {
    selectedBrands = [...groups[groupName]];
    updateDisplay();
    filterBrands();
    document.getElementById('brand-dropdown').classList.remove('show');
}

function deleteGroup(groupName) {
    if (confirm('Elimina gruppo "' + groupName + '"?')) {
        delete groups[groupName];
        localStorage.setItem('oracolo_groups', JSON.stringify(groups));
        loadGroups();
    }
}

function updateGroupAdd(groupName) {
    const currentGroup = groups[groupName];
    const newBrands = selectedBrands.filter(b => !currentGroup.includes(b));
    
    if (newBrands.length === 0) { alert('Nessun brand nuovo da aggiungere'); return; }
    
    groups[groupName] = [...new Set([...currentGroup, ...selectedBrands])];
    localStorage.setItem('oracolo_groups', JSON.stringify(groups));
    loadGroups();
    alert('✅ Gruppo aggiornato! Aggiunti: ' + newBrands.join(', '));
}

function loadGroups() {
    const container = document.getElementById('groups-list');
    if (Object.keys(groups).length === 0) {
        container.innerHTML = '<div style="font-size: 11px; color: #9ca3af; padding: 6px;">Nessun gruppo</div>';
        return;
    }
    
    const html = Object.keys(groups).sort().map(gName => `
        <div class="group-item">
            <div class="group-item-name" onclick="loadGroup('${gName}')">${gName} (${groups[gName].length})</div>
            <div class="group-item-btns">
                <button onclick="updateGroupAdd('${gName}')" title="Aggiungi brand attuali">➕</button>
                <button onclick="deleteGroup('${gName}')" title="Elimina">✕</button>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = html;
}

// FINE GRUPPI

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

function activatePrivateAccess() {
    const code = document.getElementById('access-code').value.trim();
    if (!code) { alert('Inserisci codice accesso'); return; }
    accessCode = code;
    accessLevel = "private";
    document.getElementById('access-status').innerHTML = '<span class="access-badge private">🔒 PRIVATO (dati completi)</span>';
    document.getElementById('access-code').value = '';
}

function toggleWeb() {
    webEnabled = !webEnabled;
    document.getElementById('web-btn').textContent = webEnabled ? '🟢 ON' : '🔴 OFF';
}

function showUpload() {
    alert('Upload cassetti: seleziona brand e upload file\n(In sviluppo - contatta admin)');
}

function showDocuments() {
    alert('Visualizza documenti cassetti\n(In sviluppo - contatta admin)');
}

function generateOfferta() {
    if (selectedBrands.length === 0) { alert('Seleziona brand'); return; }
    alert('🔄 Generazione OFFERTA PDF...\n(Basata su risposta consulente + foto + dati ' + accessLevel.toUpperCase() + ')');
}

function generateAnalisi() {
    if (selectedBrands.length === 0) { alert('Seleziona brand'); return; }
    alert('📊 Analisi comparativa ' + selectedBrands.join(', ') + '\n(Dati ' + accessLevel.toUpperCase() + ')');
}

function generateProposta() {
    if (selectedBrands.length === 0) { alert('Seleziona brand'); return; }
    const nome = prompt('Nome proposta:');
    if (nome) alert('💾 Proposta "' + nome + '" salvata!\n(Accesso ' + accessLevel.toUpperCase() + ')');
}

async function sendQuestion() {
    const q = document.getElementById('question').value.trim();
    if (!q) return;
    if (selectedBrands.length === 0) { alert('Seleziona almeno 1 brand!'); return; }
    
    const msg = document.getElementById('messages');
    msg.innerHTML += '<div class="message user-message">' + q + '</div>';
    document.getElementById('question').value = '';
    msg.scrollTop = msg.scrollHeight;
    
    const accessBadge = accessLevel === 'private' ? 
        '<span class="access-badge private">🔒 PRIVATO</span>' : 
        '<span class="access-badge">📖 PUBBLICO</span>';
    
    try {
        const res = await fetch('/api/ask', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                question: q,
                brands: selectedBrands,
                web: webEnabled,
                access_code: accessCode,
                access_level: accessLevel
            })
        });
        const data = await res.json();
        const escaped = data.answer.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        msg.innerHTML += '<div class="message bot-message">' + accessBadge + ' ' + escaped + '</div>';
        msg.scrollTop = msg.scrollHeight;
    } catch (e) {
        msg.innerHTML += '<div class="message bot-message">❌ Errore: ' + e + '</div>';
    }
}

console.log("✅ JavaScript caricato");
loadGroups();
</script>
</body></html>''')

@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.get_json()
    q = data.get('question', '').strip()
    selected_brands = data.get('brands', [])
    use_web = data.get('web', True)
    access_code = data.get('access_code')
    access_level = data.get('access_level', 'public')
    
    if not selected_brands:
        return jsonify({"answer": "❌ Seleziona almeno 1 brand!"})
    
    print(f"\n[REQUEST] Q: {q} | Brands: {selected_brands} | Access: {access_level}")
    
    # Ricerca documenti (con filtro visibilità)
    doc_match, _ = search_documents(q, selected_brands, access_code if access_level == 'private' else None)
    doc_text = f"[DOC: {doc_match[0][:50]}...] {doc_match[1][:300]}" if doc_match else None
    print(f"[SEARCH] Docs (access={access_level}): {doc_text is not None}")
    
    # Ricerca web
    web_text = None
    if use_web:
        web_text = search_web(q, selected_brands)
        print(f"[SEARCH] Web: {web_text is not None}")
    
    # Genera risposta
    brands_str = ", ".join(selected_brands)
    context = ""
    if doc_text:
        context += f"\nDOCUMENTO (access={access_level}):\n{doc_text}"
    if web_text:
        context += f"\nWEB:\n{web_text}"
    
    prompt = f"""Domanda: {q}
Brand (GUARDRAIL): {brands_str}
Livello accesso: {access_level.upper()}
{context}

Rispondi come esperto. Risposta DIVERSA da domanda."""
    
    answer = deepseek_ask(prompt, selected_brands, access_level)
    
    if not answer:
        answer = f"[{access_level.upper()}] Consiglio su {q} per {brands_str}"
    
    return jsonify({
        "answer": answer,
        "access_level": access_level,
        "source": f"🎯 {brands_str} | {access_level.upper()}"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
