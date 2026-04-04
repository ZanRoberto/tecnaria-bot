"""
WEB SEARCH TOGGLE SYSTEM
========================
Sistema per attivare/disattivare ricerca web A TUA SCELTA.
Non è una modifica al core - è una OPZIONE controllabile.

Esempi:
- Domanda semplice (prezzo interno) → Web OFF
- Domanda su trend → Web ON
- Domanda su norme attuali → Web ON
- Domanda da documenti → Web OFF
"""

import asyncio
from typing import Dict, Any, Optional
from enum import Enum
import logging

log = logging.getLogger(__name__)

class WebSearchMode(Enum):
    """Modi di ricerca web disponibili."""
    OFF = "off"                    # No web search
    ON_DEMAND = "on_demand"        # Solo se cliente chiede
    AUTO = "auto"                  # Sistema decide da solo
    ALWAYS = "always"              # Sempre (lento ma completo)

class WebSearchToggleSystem:
    """
    Sistema che controlla QUANDO cercare il web.
    
    Puoi:
    - Attivare/disattivare per singola domanda
    - Impostare modalità globale
    - Vedere cosa cambia tra web ON/OFF
    """
    
    def __init__(self, default_mode: WebSearchMode = WebSearchMode.AUTO):
        self.mode = default_mode
        self.search_history = []
        self.performance_metrics = {
            "web_off_avg_time": 0.8,  # secondi
            "web_on_avg_time": 3.5,   # secondi (include fetch)
            "web_useful_rate": 0.75,  # % risposte migliori con web
        }
    
    def should_search_web(self, question: str, force_mode: Optional[WebSearchMode] = None) -> Dict:
        """
        Decide se cercare il web per questa domanda.
        
        Returns:
            {
                "should_search": bool,
                "reason": "spiegazione",
                "estimated_time": 0.8 | 3.5,
                "mode": "auto" | "on_demand" | "off" | "always"
            }
        """
        
        # Se force_mode passato: usalo
        mode = force_mode or self.mode
        
        if mode == WebSearchMode.OFF:
            return {
                "should_search": False,
                "reason": "Ricerca web DISATTIVATA",
                "estimated_time": 0.8,
                "mode": "off"
            }
        
        elif mode == WebSearchMode.ALWAYS:
            return {
                "should_search": True,
                "reason": "Ricerca web ATTIVATA (modalità ALWAYS)",
                "estimated_time": 3.5,
                "mode": "always"
            }
        
        elif mode == WebSearchMode.ON_DEMAND:
            # Cerca solo se cliente chiede esplicitamente
            keywords = ["ricerca", "cercami", "online", "web", "attuale", "oggi", "ora"]
            should_search = any(kw in question.lower() for kw in keywords)
            
            return {
                "should_search": should_search,
                "reason": f"On-demand: {'Cliente ha chiesto web' if should_search else 'Cliente non ha chiesto web'}",
                "estimated_time": 3.5 if should_search else 0.8,
                "mode": "on_demand"
            }
        
        else:  # AUTO
            return self._auto_decide(question)
    
    def _auto_decide(self, question: str) -> Dict:
        """
        Decide AUTOMATICAMENTE se cercare web.
        Basato su tipo di domanda.
        """
        
        question_lower = question.lower()
        
        # Domande che SEMPRE cercano web
        high_priority_keywords = [
            "prezzo", "costo", "listino",           # Prezzi cambiano
            "quando", "lead time", "consegna",      # Tempi cambiano
            "disponibile", "in stock",               # Disponibilità cambia
            "norma", "certificazione", "standard",  # Norme si aggiornano
            "trend", "nuovo", "2026",                # Trend è attuale
            "competitor", "confronto",               # Competitors aggiornati
        ]
        
        if any(kw in question_lower for kw in high_priority_keywords):
            return {
                "should_search": True,
                "reason": "Auto: domanda su dati VARIABILI (prezzi, tempi, norme)",
                "estimated_time": 3.5,
                "mode": "auto",
                "trigger": "high_priority"
            }
        
        # Domande che POTREBBERO cercare web (50/50)
        medium_priority_keywords = [
            "alternativa", "simile", "invece di",   # Alternatives sempre cambiano
            "quale scegliere", "consiglio",         # Trend influenza consigli
            "miglior", "best", "top",               # Rankings cambiano
        ]
        
        if any(kw in question_lower for kw in medium_priority_keywords):
            return {
                "should_search": True,
                "reason": "Auto: domanda su SCELTE (potrebbe aiutare)",
                "estimated_time": 3.5,
                "mode": "auto",
                "trigger": "medium_priority"
            }
        
        # Domande che NON cercano web
        low_priority_keywords = [
            "come funziona", "spiegami", "che cos'è",
            "procedura", "passo passo", "workflow",
            "cosa serve", "cosa mi occorre",
        ]
        
        if any(kw in question_lower for kw in low_priority_keywords):
            return {
                "should_search": False,
                "reason": "Auto: domanda su CONCETTI (documenti interni sufficienti)",
                "estimated_time": 0.8,
                "mode": "auto",
                "trigger": "low_priority"
            }
        
        # Default: NO web (più veloce, solito abbastanza)
        return {
            "should_search": False,
            "reason": "Auto: default NO web (risposte interni veloci)",
            "estimated_time": 0.8,
            "mode": "auto",
            "trigger": "default"
        }
    
    def set_mode(self, mode: WebSearchMode) -> Dict:
        """Imposta modalità globale."""
        self.mode = mode
        return {
            "status": "success",
            "mode": mode.value,
            "message": f"Web search mode impostato a: {mode.value}"
        }
    
    def toggle_mode(self) -> Dict:
        """Toggle tra OFF e AUTO."""
        if self.mode == WebSearchMode.OFF:
            self.mode = WebSearchMode.AUTO
        else:
            self.mode = WebSearchMode.OFF
        
        return {
            "status": "toggled",
            "mode": self.mode.value,
            "message": f"Web search ora è: {self.mode.value}"
        }
    
    def get_modes_available(self) -> Dict:
        """Mostra tutte le modalità disponibili."""
        return {
            "available_modes": [
                {
                    "name": "OFF",
                    "value": "off",
                    "description": "Ricerca web DISATTIVATA - Solo documenti interni",
                    "avg_time": 0.8,
                    "best_for": "Risposte veloci, dati stabili"
                },
                {
                    "name": "ON_DEMAND",
                    "value": "on_demand",
                    "description": "Ricerca web SOLO se cliente chiede (es: 'cercami online')",
                    "avg_time": "variabile (0.8-3.5)",
                    "best_for": "Controllo manuale cliente"
                },
                {
                    "name": "AUTO",
                    "value": "auto",
                    "description": "Sistema decide AUTOMATICAMENTE basato su domanda",
                    "avg_time": "variabile (0.8-3.5)",
                    "best_for": "Equilibrio velocità + completezza (CONSIGLIATO)"
                },
                {
                    "name": "ALWAYS",
                    "value": "always",
                    "description": "SEMPRE ricerca web - Più lento ma più completo",
                    "avg_time": 3.5,
                    "best_for": "Quando dati sempre cambiano"
                }
            ],
            "current_mode": self.mode.value
        }
    
    def compare_answers(self, question: str) -> Dict:
        """
        DIMOSTRA la differenza tra web ON/OFF.
        Utile per decidere se attivare.
        """
        
        return {
            "question": question,
            "example_comparison": {
                "web_off": {
                    "answer": "Basato solo su documenti Covolo caricati",
                    "sources": ["Listino Gessi interno", "Macroregole interne"],
                    "time": "0.8 secondi",
                    "advantages": [
                        "✅ Velocissimo",
                        "✅ Dati CERTI (tuoi)",
                        "✅ Privacy guaranteed"
                    ],
                    "disadvantages": [
                        "❌ Prezzi potrebbero essere vecchi",
                        "❌ Lead time potrebbero essere cambiati",
                        "❌ Non vedi competitors"
                    ]
                },
                "web_on": {
                    "answer": "Integrato con dati web ATTUALI",
                    "sources": ["Listino Gessi interno", "areapro.gessi.com ORA", "competitors"],
                    "time": "3.5 secondi",
                    "advantages": [
                        "✅ Prezzi ODIERNI verificati",
                        "✅ Lead time REALI aggiornati",
                        "✅ Vedi alternatives competitors",
                        "✅ Norme AGGIORNATE"
                    ],
                    "disadvantages": [
                        "❌ Un po' più lento (3.5 sec)",
                        "❌ Dipende da web (a volte lento)",
                        "❌ Meno private"
                    ]
                },
                "recommendation": "AUTO (sistema decide per te)"
            }
        }
    
    def get_current_settings(self) -> Dict:
        """Mostra impostazioni attuali."""
        return {
            "current_mode": self.mode.value,
            "modes_available": self.get_modes_available(),
            "performance": self.performance_metrics,
            "api_endpoints": {
                "toggle": "POST /api/web-search/toggle",
                "set_mode": "POST /api/web-search/set-mode",
                "compare": "GET /api/web-search/compare?question=...",
                "settings": "GET /api/web-search/settings"
            }
        }
    
    def record_search(self, question: str, used_web: bool, response_time: float, 
                     web_was_useful: bool = None) -> None:
        """Registra ogni ricerca per analisi."""
        self.search_history.append({
            "question": question,
            "used_web": used_web,
            "response_time": response_time,
            "web_was_useful": web_was_useful,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_analytics(self) -> Dict:
        """Mostra analytics uso web search."""
        if not self.search_history:
            return {"message": "No search history yet"}
        
        total_searches = len(self.search_history)
        web_searches = sum(1 for s in self.search_history if s["used_web"])
        web_useful = sum(1 for s in self.search_history if s.get("web_was_useful"))
        
        avg_time_with_web = sum(s["response_time"] for s in self.search_history if s["used_web"]) / max(web_searches, 1)
        avg_time_without_web = sum(s["response_time"] for s in self.search_history if not s["used_web"]) / max(total_searches - web_searches, 1)
        
        return {
            "total_searches": total_searches,
            "web_searches": web_searches,
            "web_percentage": f"{(web_searches/total_searches)*100:.1f}%",
            "web_useful_count": web_useful,
            "web_useful_percentage": f"{(web_useful/web_searches)*100:.1f}%" if web_searches > 0 else "N/A",
            "avg_time_with_web": f"{avg_time_with_web:.2f}s",
            "avg_time_without_web": f"{avg_time_without_web:.2f}s",
            "time_difference": f"{abs(avg_time_with_web - avg_time_without_web):.2f}s",
            "recommendation": "Web search è utile" if (web_useful/web_searches > 0.7) if web_searches > 0 else "Attiva web" else "Web search non molto utile, considera OFF"
        }

from datetime import datetime
