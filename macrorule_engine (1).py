"""
MACRORULE ENGINE - Sistema Intelligente da Subito
==================================================
Trasforma macroregole in CAPSULE LEARNED intelligenti.
Oracolo non parte CIECO - sa GIÀ cosa funziona e cosa no!
"""

import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

log = logging.getLogger(__name__)

class MacroruleEngine:
    """
    Motore che trasforma MACROREGOLE Covolo in CAPSULE intelligenti.
    
    Al boot: 
    - Legge macroregole_covolo_universe.json
    - Genera LEARNED CAPSULE da subito
    - Sistema PARTE SAPIENTE, non cieco
    - Cliente chiede cosa impossibile → Sistema suggerisce alternativa
    """

    def __init__(self, macroregole_file: str):
        self.macroregole_file = macroregole_file
        self.macroregole = []
        self.generated_capsules = []
        self.load_macroregole()

    def load_macroregole(self):
        """Carica universo macroregole da JSON."""
        try:
            with open(self.macroregole_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.macroregole = data.get("macroregole", [])
            log.info(f"✅ Caricate {len(self.macroregole)} macroregole Covolo")
            
            # Subito genera capsule
            self.generate_capsules_from_macroregole()
            
        except Exception as e:
            log.error(f"❌ Errore caricamento macroregole: {e}")
            self.macroregole = []

    def generate_capsules_from_macroregole(self):
        """
        Trasforma OGNI macrorègola in LEARNED CAPSULE.
        Sistema PARTE INTELLIGENTE!
        """
        self.generated_capsules = []
        
        for macro in self.macroregole:
            capsule = self._macro_to_capsule(macro)
            self.generated_capsules.append(capsule)
        
        log.info(f"🧠 Generat {len(self.generated_capsules)} CAPSULE intelligenti da macroregole")

    def _macro_to_capsule(self, macro: Dict) -> Dict:
        """Converte una macrorègola in CAPSULE LEARNED."""
        
        categoria = macro.get("categoria", "unknown")
        confidence = macro.get("confidence", 0.9)
        
        # Priority basata su confidence
        priority = 1 if confidence >= 0.95 else 2 if confidence >= 0.85 else 3
        
        # Azione basata su categoria
        azione = self._get_action_from_categoria(categoria, macro)
        
        # Trigger da macrorègola
        trigger = macro.get("trigger", [])
        if isinstance(trigger, dict):
            trigger = [{"param": k, "op": "==", "value": v} 
                      for k, v in trigger.items()]
        
        capsule = {
            "id": f"LEARNED_FROM_{macro.get('id', 'unknown')}",
            "asset": "COVOLO_ARREDO_BAGNO",
            "livello": "LEARNED",
            "tipo": categoria.upper(),
            
            "descrizione": macro.get("regola", ""),
            "trigger": trigger,
            "azione": azione,
            
            "priority": priority,
            "enabled": 1,
            
            # Fiducia dalla macrorègola
            "samples": 0,
            "wr": confidence,
            "pnl_avg": 0.0,
            
            "created_ts": time.time(),
            "scade_ts": None,  # Non scade
            
            "hits": 0,
            "hits_saved": 0.0,
            "note": f"Generata da MACRORÈGOLA '{macro.get('id')}' - Fiducia iniziale {confidence:.0%}"
        }
        
        return capsule

    def _get_action_from_categoria(self, categoria: str, macro: Dict) -> Dict:
        """Genera AZIONE intelligente basata su categoria macrorègola."""
        
        if "incompatibilita" in categoria.lower():
            return {
                "type": "blocca_incompatibile",
                "params": {
                    "reason": macro.get("id", ""),
                    "message": macro.get("se_non_presente", {}).get("message", ""),
                    "alternatives": macro.get("se_non_presente", {}).get("alternative_1", {})
                }
            }
        
        elif categoria == "requirement":
            return {
                "type": "verifica_requirement",
                "params": {
                    "requires": macro.get("requirements", []),
                    "cost": macro.get("cost", 0),
                    "message": f"Questo prodotto richiede: {', '.join(macro.get('requirements', []))}"
                }
            }
        
        elif categoria == "best_practice":
            return {
                "type": "suggerisci_combo",
                "params": {
                    "recommendations": macro.get("recommendations", []),
                    "cost_delta": macro.get("cost_delta", 0),
                    "why": macro.get("why", "")
                }
            }
        
        elif categoria == "timeline":
            return {
                "type": "info_timeline",
                "params": {
                    "lead_time_min": macro.get("lead_time_min"),
                    "lead_time_max": macro.get("lead_time_max"),
                    "buffer_days": macro.get("buffer_days", 0),
                    "total_realistic": macro.get("total_realistic") or 
                                     (macro.get("lead_time_max", 0) + macro.get("buffer_days", 0))
                }
            }
        
        elif categoria == "certificazione":
            return {
                "type": "verifica_norma",
                "params": {
                    "requirement": macro.get("requirement", ""),
                    "legal_standard": macro.get("legal", ""),
                    "safety": macro.get("safety", "")
                }
            }
        
        elif categoria == "commerciale":
            return {
                "type": "info_margine",
                "params": {
                    "min_margin": macro.get("min_margin_percent", 0),
                    "typical_margin": macro.get("typical_margin_percent", 0)
                }
            }
        
        elif categoria == "workflow":
            return {
                "type": "guida_workflow",
                "params": {
                    "steps": macro.get("workflow") or macro.get("decision_tree"),
                    "message": macro.get("regola", "")
                }
            }
        
        else:
            return {"type": "info", "params": {"message": macro.get("regola", "")}}

    def check_incompatibility(self, product_request: Dict) -> Optional[Dict]:
        """
        Cliente chiede un prodotto/combo.
        Sistema verifica se è INCOMPATIBILE secondo macroregole.
        Se sì → ritorna alternativa intelligente.
        """
        
        # Cerca tutte le macroregole di incompatibilità
        incompatibility_macros = [
            m for m in self.macroregole 
            if "incompatibilita" in m.get("categoria", "").lower()
        ]
        
        for macro in incompatibility_macros:
            if self._matches_trigger(product_request, macro.get("trigger", {})):
                
                # Verifico se il requirement è soddisfatto
                requirements = macro.get("requirements", [])
                for req in requirements:
                    if req not in product_request.get("has", []):
                        # INCOMPATIBILITÀ TROVATA!
                        return {
                            "status": "INCOMPATIBLE",
                            "blocked_by": macro.get("id"),
                            "message": macro.get("se_non_presente", {}).get("message", ""),
                            "warning": macro.get("se_non_presente", {}).get("warning", ""),
                            "alternatives": [
                                macro.get("se_non_presente", {}).get("alternative_1"),
                                macro.get("se_non_presente", {}).get("alternative_2")
                            ]
                        }
        
        return None  # Compatibile!

    def check_requirements(self, product_request: Dict) -> List[Dict]:
        """
        Cliente chiede un prodotto.
        Sistema verifica COSA RICHIEDE per funzionare bene.
        Ritorna lista di requirements + best practices.
        """
        
        requirements_list = []
        
        # Cerca macroregole di requirement
        requirement_macros = [
            m for m in self.macroregole 
            if m.get("categoria") == "requirement"
        ]
        
        for macro in requirement_macros:
            if self._matches_trigger(product_request, macro.get("trigger", {})):
                requirements_list.append({
                    "type": "requirement",
                    "rule_id": macro.get("id"),
                    "requirement": macro.get("requirements", []),
                    "cost": macro.get("cost", 0),
                    "why": macro.get("why", ""),
                    "notes": macro.get("notes", "")
                })
        
        # Cerca best practices
        best_practice_macros = [
            m for m in self.macroregole 
            if m.get("categoria") == "best_practice"
        ]
        
        for macro in best_practice_macros:
            if self._matches_trigger(product_request, macro.get("trigger", {})):
                requirements_list.append({
                    "type": "best_practice",
                    "rule_id": macro.get("id"),
                    "recommendation": macro.get("recommendations", []),
                    "cost_delta": macro.get("cost_delta", 0),
                    "why": macro.get("why", ""),
                    "customer_satisfaction": macro.get("customer_satisfaction", "")
                })
        
        return requirements_list

    def get_timeline(self, product_request: Dict) -> Optional[Dict]:
        """
        Cliente chiede timeline progetto.
        Sistema ritorna timeline REALISTICO basato su macroregole.
        """
        
        timeline_macros = [
            m for m in self.macroregole 
            if m.get("categoria") == "timeline"
        ]
        
        for macro in timeline_macros:
            if self._matches_trigger(product_request, macro.get("trigger", {})):
                
                lead_min = macro.get("lead_time_min")
                lead_max = macro.get("lead_time_max")
                buffer = macro.get("buffer_days", 0)
                
                if lead_min and lead_max:
                    return {
                        "product": product_request.get("product", ""),
                        "lead_time_min": lead_min,
                        "lead_time_max": lead_max,
                        "buffer_days": buffer,
                        "realistic_total": lead_max + buffer,
                        "confidence": macro.get("confidence", 0.9),
                        "notes": macro.get("notes", "")
                    }
        
        return None

    def get_workflow_guidance(self, scenario: str) -> Optional[Dict]:
        """
        Cliente non sa da dove cominciare.
        Sistema ritorna WORKFLOW intelligente passo-passo.
        """
        
        workflow_macros = [
            m for m in self.macroregole 
            if m.get("categoria") == "workflow"
        ]
        
        for macro in workflow_macros:
            if scenario.lower() in macro.get("regola", "").lower():
                return {
                    "workflow": macro.get("workflow") or macro.get("decision_tree"),
                    "description": macro.get("regola", ""),
                    "confidence": macro.get("confidence", 0.9)
                }
        
        return None

    def _matches_trigger(self, product: Dict, trigger: Dict) -> bool:
        """Verifica se prodotto/richiesta matchizza il trigger."""
        
        if not trigger:
            return False
        
        for key, value in trigger.items():
            if key not in product:
                return False
            if product[key] != value and not isinstance(product[key], list) or value not in product.get(key, []):
                return False
        
        return True

    def get_all_capsules(self) -> List[Dict]:
        """Ritorna tutte le capsule generate."""
        return self.generated_capsules

    def suggest_alternative(self, blocked_product: Dict) -> List[Dict]:
        """
        Cliente vuole un prodotto che è BLOCCATO.
        Sistema suggerisce ALTERNATIVE intelligenti.
        """
        
        alternatives = []
        
        # Cerca macrorègola che blocca
        for macro in self.macroregole:
            if self._matches_trigger(blocked_product, macro.get("trigger", {})):
                if "incompatibilita" in macro.get("categoria", "").lower():
                    
                    # Estrai alternative
                    alt1 = macro.get("se_non_presente", {}).get("alternative_1")
                    alt2 = macro.get("se_non_presente", {}).get("alternative_2")
                    
                    if alt1:
                        alternatives.append(alt1)
                    if alt2:
                        alternatives.append(alt2)
        
        return alternatives

    def debug_info(self) -> Dict:
        """Info debug per dashboard."""
        return {
            "macroregole_caricate": len(self.macroregole),
            "capsule_generate": len(self.generated_capsules),
            "categorie": list(set(m.get("categoria") for m in self.macroregole)),
            "incompatibilita_rules": len([m for m in self.macroregole if "incompatibilita" in m.get("categoria", "")]),
            "requirement_rules": len([m for m in self.macroregole if m.get("categoria") == "requirement"]),
            "best_practice_rules": len([m for m in self.macroregole if m.get("categoria") == "best_practice"]),
            "timeline_rules": len([m for m in self.macroregole if m.get("categoria") == "timeline"]),
            "workflow_rules": len([m for m in self.macroregole if m.get("categoria") == "workflow"]),
        }
