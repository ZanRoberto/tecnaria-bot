"""
NARRATOR SYSTEM - Risposte Narrative Intelligenti
===================================================
Non risposte fredde/tecniche.
Narrativa calda, conversazionale, professionale.
Come un consulente che RACCONTA la soluzione.

Transforma:
  ❌ "INCOMPATIBILE. Doccia incasso richiede cartongesso."
  ✅ "Capisco il tuo desiderio, ma qui devo essere sincero con te...
      La doccia incasso che immagini è una fantastica scelta,
      MA richiede una parete in cartongesso.
      Se installo su piastrella diretta, in 2 anni avremo
      muffa e umidità. Non mi sento di proporlo.
      
      PERÒ ho due soluzioni che AMANO i clienti:
      1. Doccia esterna Gessi (stessa eleganza, meno complessità)
      2. Facciamo cartongesso e poi incasso (full luxury)
      
      Quale sente più TUA?"
"""

import json
import logging
from typing import Dict, List, Any, Optional

log = logging.getLogger(__name__)

class NarratorSystem:
    """
    Converte risposte intelligenti in NARRATIVA PERSUASIVA.
    
    Il bot non parla come una macchina.
    Parla come un consulente che COMPRENDE il cliente.
    """

    def __init__(self):
        self.templates = self._load_narrative_templates()

    def _load_narrative_templates(self) -> Dict:
        """Carica template narrativi per ogni tipo di risposta."""
        return {
            "incompatibilita_critica": self._template_incompatibilita,
            "requirement": self._template_requirement,
            "best_practice": self._template_best_practice,
            "timeline": self._template_timeline,
            "decisione_difficile": self._template_decisione,
            "workflow": self._template_workflow,
            "margine_info": self._template_margine,
            "certificazione": self._template_certificazione,
        }

    # =========================================================================
    # TEMPLATE NARRATIVI
    # =========================================================================

    def _template_incompatibilita(self, context: Dict) -> str:
        """Racconta un'incompatibilità in modo UMANO e SINCERO."""
        
        product = context.get("product", "questo prodotto")
        requirement = context.get("requirement", "cartongesso")
        problem = context.get("problem", "non funzionerà bene")
        alternative_1 = context.get("alternative_1", {})
        alternative_2 = context.get("alternative_2", {})
        
        narrative = f"""
Comprendo perfettamente quello che stai cercando. {product.capitalize()} è una scelta elegante e pratica.

Ma qui devo essere sincero con te: **se installassimo {product} sulla tua parete attuale, dopo 1-2 anni potremmo avere problemi significativi.** Umidità, muffa, danni strutturali. Non è quella l'installazione che prometto ai miei clienti.

**La ragione è tecnica ma importante:** {product} richiede {requirement} per funzionare correttamente. Senza, non posso garantire durabilità e qualità.

**ORA, non è una blocco assoluto. Ho per te due strade bellissime:**

**🔷 Opzione 1: Soluzione Smart & Veloce**
{alternative_1.get('name', 'Alternativa 1')}
• Perfetto se vuoi risultato SUBITO
• Eleganza = 95% di quello che vuoi
• Tempi: {alternative_1.get('installation_days', '3-4')} giorni
• Costo: {alternative_1.get('price_delta', 'competitivo')} rispetto a quello che risparmi
• Clienti che l'hanno scelta: "Wow, non pensavo potesse essere così bello"

**🔶 Opzione 2: Soluzione Luxury Completa**
{alternative_2.get('name', 'Alternativa 2')}
• Questo è il VERO lusso, immagina cosa racconterai agli amici
• Parete cartongesso + {product}
• Eleganza: 100% + effetto WOW
• Tempi: {alternative_2.get('installation_days', '7-10')} giorni
• Investimento: più caro, ma è un valore aggiunto che rimane 20 anni
• Clienti che scelgono questa: "Ho preso la decisione migliore"

**Cosa sento più TUA?** Io sono qui per guidarti verso quella che ti farà FELICE nei prossimi 20 anni.
"""
        return narrative.strip()

    def _template_requirement(self, context: Dict) -> str:
        """Racconta un requirement come CONSIGLIO amichevole."""
        
        product = context.get("product", "questo prodotto")
        requires = context.get("requires", [])
        why = context.get("why", "funzionerà meglio")
        cost = context.get("cost", 0)
        
        narrative = f"""
Perfetto, {product} è una grande scelta!

Solo un consiglio da amico che ha visto 100+ bagni: **per farlo funzionare AL MEGLIO, ti suggerisco {', '.join(requires)}.**

**Perché?** {why}

So che sembra un dettaglio, ma è la differenza tra un bagno "ok" e un bagno che **racconterai agli amici con orgoglio**.

Il costo aggiunto è circa **€{cost}**, ma consideriamo:
• Durerà 20 anni (non 5)
• Zero problemi futuri
• Ogni volta che entri in bagno: "Ho scelto bene"

**Io ti consiglio di includerlo. Fiducia?**
"""
        return narrative.strip()

    def _template_best_practice(self, context: Dict) -> str:
        """Racconta una best practice come SCOPERTA ENTUSIASMANTE."""
        
        product = context.get("product", "questo prodotto")
        recommendation = context.get("recommendation", "un abbinamento")
        why = context.get("why", "creano armonia")
        cost_delta = context.get("cost_delta", 0)
        
        cost_text = f"**e risparmi €{abs(cost_delta)}**" if cost_delta < 0 else f"(investimento +€{cost_delta})"
        
        narrative = f"""
Oh, qui devo raccontarti una cosa che **i veri professionisti sanno**: 

{product.capitalize()} + {recommendation} = **MAGIA PURA**

Non è un caso. È geometria, colore, funzionalità che **si parlano**.

**La differenza?**
• Senza: "Bel bagno"
• Con: "WOW, CHI È L'ARCHITETTO?!" (è il tuo stesso stile)

Ho visto clienti scegliere {product} da solo, poi dopo 1 mese chiedere: "Posso aggiungere {recommendation}?"

**Suggerimento:** Iniziamo insieme. Ti costerà appena €{cost_delta} {cost_text}, ma il risultato sarà **completamente diverso**.

Che ne dici? Facciamo la scelta che i veri professionisti farebbero?
"""
        return narrative.strip()

    def _template_timeline(self, context: Dict) -> str:
        """Racconta una timeline come PIANIFICAZIONE CONSAPEVOLE."""
        
        product = context.get("product", "il bagno")
        steps = context.get("steps", [])
        total = context.get("total_days", 10)
        realistic = context.get("realistic_total", total)
        
        steps_narrative = "\n".join([
            f"**Giorno {i+1}-{step.get('days', 1)}: {step.get('activity', 'attività')}**\n{step.get('notes', '')}"
            for i, step in enumerate(steps[:4])
        ])
        
        narrative = f"""
Bene, parliamo della timeline. Voglio darti i NUMERI VERI, non promesse azzardate.

{product.capitalize()} non è una cosa che si fa in 5 giorni. È un progetto che richiede CONSAPEVOLEZZA.

**Ecco il piano realistico:**

{steps_narrative}

**TOTALE: {realistic} giorni**

(Sì, un po' più del "20 giorni" che leggi online. Ma è sincero.)

**Cosa significa per te?**
• Inizio lavori: [data]
• Fine lavori: [data - realistico]
• ZERO sorprese, ZERO attese infinite

I fornitori dicono "6 giorni", poi diventa "12". Non qui. **Io ti do il numero realistico SUBITO.**

Questo significa che puoi **pianificare la tua vita**, invitare gli amici al bagno finito, organizzare senza ansia.

**Tranquillo, siamo professionisti. Sappiamo i tempi VERI.**
"""
        return narrative.strip()

    def _template_decisione(self, context: Dict) -> str:
        """Racconta una decisione difficile come GUIDA CONSAPEVOLE."""
        
        scenario_1 = context.get("scenario_1", {})
        scenario_2 = context.get("scenario_2", {})
        scenario_3 = context.get("scenario_3", {})
        
        narrative = f"""
Ascolta, ogni cliente che arriva qui ha una domanda implicita: **"Cosa mi consiglieresti TU?"**

Eccoti i tre scenari possibili. Leggi e fammi sapere quale **senti più tua**:

**Scenario 1: La Soluzione Smart**
{scenario_1.get('name', 'Smart')} - €{scenario_1.get('price', 'da definire')}
✓ Funziona perfettamente
✓ Tempi rapidi: {scenario_1.get('days', '7')} giorni
✓ Margine di budge: lo hai
→ *Scelgono così i clienti che dicono: "Voglio bello, ma non voglio impazzire"*

**Scenario 2: Lo Standard (Il Più Scelto)**
{scenario_2.get('name', 'Standard')} - €{scenario_2.get('price', 'da definire')}
✓ Qualità vera, non compromessi
✓ Durabilità: 20 anni garantiti
✓ Storia da raccontare: "Guarda come è fatto il MIOOOOO bagno"
→ *Scelgono così i clienti che dicono: "Voglio il meglio per casa mia"*

**Scenario 3: La Scelta Luxury**
{scenario_3.get('name', 'Luxury')} - €{scenario_3.get('price', 'da definire')}
✓ Questo è ART
✓ Non è un bagno, è una DICHIARAZIONE
✓ Gli amici rimangono senza fiato
→ *Scelgono così i clienti che dicono: "La casa è il nostro castello"*

**Ora ascolta me:**
Non dico "qual è la migliore". Dico: **"Qual è la TUA?"**

Perché il bagno che scegli adesso, lo vivrai OGNI GIORNO per 20 anni.

**Dimmi dove senti il tuo cuore. E andiamo da lì.**
"""
        return narrative.strip()

    def _template_workflow(self, context: Dict) -> str:
        """Racconta un workflow come ROADMAP DI FIDUCIA."""
        
        steps = context.get("steps", [])
        
        steps_narrative = "\n".join([
            f"**{i+1}. {step.get('question', 'Passo')}**\nPerché: {step.get('why', '')}"
            for i, step in enumerate(steps)
        ])
        
        narrative = f"""
Ok, so che tutto questo è un po' confuso. Facciamo un po' di ordine.

**Io non invento nulla. Ho una procedura COLLAUDATA che mi porto dietro da 10 anni.**

Ogni cliente che passa di qui, seguiamo QUESTI STEP. Perché? Perché evita errori e malintesi.

{steps_narrative}

**Cosa succede?**
Con queste informazioni, **IO creo per te un preventivo che è VERO.**
Non "dipende", non "variabile". VERO.

Così tra 2 settimane, quando i lavori iniziano, **zero sorprese**.

**Fiducia? Iniziamo?**
"""
        return narrative.strip()

    def _template_certificazione(self, context: Dict) -> str:
        """Racconta una certificazione come PROTEZIONE LEGALE."""
        
        requirement = context.get("requirement", "certificazione")
        standard = context.get("standard", "DIN 51130")
        risk = context.get("risk", "infortunio")
        
        narrative = f"""
Qui devo parlarti di una cosa seria che molti ignorano: **la RESPONSABILITÀ legale.**

Nel tuo bagno, se metti una piastrella liscia in doccia e qualcuno (un bambino, tua mamma, un ospite) scivola, **la responsabilità è MIA** se non ti ho avvertito.

**La norma dice:** {standard}
**Il rischio:** {risk}

Io non voglio bagni legalmente insicuri. **Voglio bagni dove i miei clienti vivono TRANQUILLI.**

Quindi: {requirement} NON è una "scelta di stile".

È una **protezione che ti salva da problemi seri**.

**Ti chiedo solo di fidarti di me su questo.** Scelgamoli insieme.
"""
        return narrative.strip()

    def _template_margine(self, context: Dict) -> str:
        """Racconta i margini come VALORE CONSEGNATO."""
        
        product = context.get("product", "questo prodotto")
        min_margin = context.get("min_margin", 25)
        typical_margin = context.get("typical_margin", 40)
        
        narrative = f"""
Sentiamo di parlare anche di soldi, perché è importante.

{product.capitalize()} ha un valore di mercato. Il mio lavoro (consulenza, coordinamento, garanzia) ha un valore.

**Marchio strutturato:**
• Costo a me: X
• Margine minimo: {min_margin}%
• Margine tipico: {typical_margin}%
• Prezzo a te: Y

Non è "raddoppio il prezzo". È **"aggiungo il valore della consulenza"**.

Che significa? Significa che quando tra 2 anni qualcosa non funziona, **io sono responsabile e sistemo**.

Non è "mors tua vita mea".

**È partnership.**

Ok?
"""
        return narrative.strip()

    # =========================================================================
    # API PRINCIPALE
    # =========================================================================

    def narrate_answer(self, answer_type: str, context: Dict) -> str:
        """
        Trasforma una risposta intelligente in NARRATIVA AFFABILE.
        
        Args:
            answer_type: tipo di risposta (incompatibilita_critica, requirement, ecc)
            context: dati della risposta (prodotto, cost, alternative, ecc)
        
        Returns:
            Narrativa calda e professionale
        """
        
        if answer_type not in self.templates:
            return self._template_generic(context)
        
        try:
            narrative_fn = self.templates[answer_type]
            return narrative_fn(context)
        except Exception as e:
            log.error(f"Errore narrativa {answer_type}: {e}")
            return self._template_generic(context)

    def _template_generic(self, context: Dict) -> str:
        """Template generico fallback."""
        return f"""
Ascolta, quello che stai chiedendo è interessante.

{context.get('base_message', 'Vediamo insieme come risolverlo.')

**Ecco quello che penso:**

{context.get('analysis', 'Analizziamo la situazione.')}

**Le tue opzioni:**

{context.get('alternatives', '1. Opzione A\n2. Opzione B')}

**Cosa sento più TUA?** Raccontami e andiamo da lì.
"""

    def add_emotion_layer(self, text: str, tone: str = "professional_warm") -> str:
        """Aggiunge strato emotivo alla narrativa."""
        
        if tone == "professional_warm":
            prefixes = [
                "Ascolta,",
                "Comprendo perfettamente,",
                "Sentiamo,",
                "Ok, qui devo essere sincero:",
                "Bene, parliamo chiaro:",
            ]
        else:
            prefixes = [""]
        
        import random
        prefix = random.choice(prefixes)
        
        return f"{prefix} {text}" if prefix else text

    def debug_narrative(self, answer_type: str) -> Dict:
        """Debug: mostra quali template disponibili."""
        return {
            "available_templates": list(self.templates.keys()),
            "requested_type": answer_type,
            "found": answer_type in self.templates
        }
