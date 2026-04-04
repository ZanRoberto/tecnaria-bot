"""
NARRATOR SYSTEM
===============
Trasforma risposte fredde in narrativa calda e persuasiva.
Stile consulente esperto arredo bagno.
"""

class NarratorSystem:
    """Sistema di narrativa intelligente per Oracolo Covolo."""
    
    def __init__(self):
        self.templates = {
            "incompatibilita_critica": """Comprendo perfettamente quello che stai cercando. Ma devo essere sincero con te: 
se installassimo {product} sulla tua configurazione attuale, potremmo avere 
problemi significativi nel tempo. 

Ecco cosa accadrebbe:
{technical_issue}

Per questo ti propongo due strade bellissime:

**Opzione 1 - Smart** ({option1_name}):
{option1_detail}
Investimento: {option1_cost}
Timeline: {option1_time}

**Opzione 2 - Luxury** ({option2_name}):
{option2_detail}
Investimento: {option2_cost}
Timeline: {option2_time}

Quale sente più TUA?""",
            
            "requirement": """Ottima domanda! Per {product}, abbiamo alcuni requirement tecnici 
che garantiscono il successo dell'installazione:

{requirement_list}

Questo non è rigido - è la nostra esperienza che ti protegge. 
Vuoi che ti spieghiamo il perché di ciascuno?""",
            
            "best_practice": """Bellissima scelta! Per {product}, abbiamo identificato le best practice 
che separano una buona installazione da un capolavoro:

{practices_list}

Queste combinazioni hanno un tasso di soddisfazione del 98% 
nella nostra esperienza. Cosa ne pensi?""",
            
            "timeline": """Perfetto, facciamo chiarezza sulla timeline realistica per {project}:

{timeline_breakdown}

**Timeline TOTALE: {total_days} giorni lavorativi**

Abbiamo calcolato:
- Margini di sicurezza (buffer): +20%
- Possibili ritardi fornitori: +3-5 giorni
- Assestamento finale: +2 giorni

Sei d'accordo con questa planning, o hai vincoli specifici?""",
            
            "decisione_difficile": """Stai prendendo una decisione importante, e lo sentiamo.

Ecco il nocciolo della questione:

{dilemma_core}

**Dati dalla nostra esperienza:**
{data_driven_insight}

Non c'è una risposta "giusta" in assoluto. 
Dipende da cosa conta DAVVERO per te:

1. Massima efficienza? → {choice1}
2. Massima flexibilità? → {choice2}
3. Equilibrio? → {choice3}

Quale valore vince per te?""",
            
            "workflow": """Perfetto! Segui questo flusso (è il nostro standard):

**STEP 1: Analisi & Design** (giorni 1-2)
{step1_detail}

**STEP 2: Preparazione Spazi** (giorni 3-4)
{step2_detail}

**STEP 3: Installazione Strutturale** (giorni 5-7)
{step3_detail}

**STEP 4: Finiture & Collaudo** (giorni 8-10)
{step4_detail}

**STEP 5: Consegna & Assistenza** (giorno 11+)
{step5_detail}

Sei pronto? Partiamo!""",
            
            "margine_info": """Questa è informazione commerciale sensibile, 
ma voglio che tu sappia come lavoriamo:

**Nostro modello di margine:**
- Prodotti Gessi rubinetteria: 30-35% (margine minimo)
- Servizi di posa: 50-60% (value-based)
- Progettazione: min 25%, target 35%

Non è grezzo. È il risultato di:
- Anni di esperienza
- Qualità garantita
- Assistenza post-vendita
- Continuità aziendale

Questo trasparenza ti rassicura?""",
            
            "certificazione": """Questo è CRITICO per la tua sicurezza e tranquillità:

{certification_requirement}

**Perché?**
{certification_why}

**Come verifichiamo:**
{certification_verify}

Vogliamo che tu dorma tranquillo. Ok?"""
        }
    
    def narrate(self, response_type, context):
        if response_type not in self.templates:
            return context.get('base_message', 'Domanda interessante!')
        
        template = self.templates[response_type]
        
        try:
            narrative = template.format(**context)
            return narrative.strip()
        except KeyError as e:
            return f"Domanda interessante!"
    
    def incompatibilita_critica(self, product, technical_issue, option1_name, 
                               option1_detail, option1_cost, option1_time,
                               option2_name, option2_detail, option2_cost, option2_time):
        return self.narrate('incompatibilita_critica', {
            'product': product,
            'technical_issue': technical_issue,
            'option1_name': option1_name,
            'option1_detail': option1_detail,
            'option1_cost': option1_cost,
            'option1_time': option1_time,
            'option2_name': option2_name,
            'option2_detail': option2_detail,
            'option2_cost': option2_cost,
            'option2_time': option2_time,
        })
    
    def requirement(self, product, requirement_list):
        return self.narrate('requirement', {
            'product': product,
            'requirement_list': requirement_list,
        })
    
    def best_practice(self, product, practices_list):
        return self.narrate('best_practice', {
            'product': product,
            'practices_list': practices_list,
        })
    
    def warmify(self, cold_response):
        warm_intro = "Perfetto, te lo spiego: "
        warm_outro = " Cosa ne pensi?"
        return f"{warm_intro}\n\n{cold_response}\n\n{warm_outro}"
