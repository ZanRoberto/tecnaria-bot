
import os

def trova_contesto_rilevante(domanda):
    domanda = domanda.lower()
    folder = "corpus_prodotti"
    migliori = []
    for nomefile in os.listdir(folder):
        with open(os.path.join(folder, nomefile), "r", encoding="utf-8") as f:
            testo = f.read()
            if any(parola in testo.lower() for parola in domanda.split()):
                migliori.append(testo[:2000])
    return migliori[0] if migliori else ""
