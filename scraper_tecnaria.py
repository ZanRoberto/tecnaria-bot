
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def cerca_online_tecnaria(domanda, max_url=1):
    query = f"site:tecnaria.com {domanda}"
    url = f"https://www.google.com/search?q={quote_plus(query)}"

    try:
        response = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(response.text, "html.parser")
        risultati = []

        for a in soup.select("a"):
            href = a.get("href")
            if href and "/url?q=" in href and "tecnaria.com" in href:
                link = href.split("/url?q=")[1].split("&")[0]
                risultati.append(link)
            if len(risultati) >= max_url:
                break

        if risultati:
            return estrai_testo_da_url(risultati[0])
        return ""

    except Exception:
        return ""

def estrai_testo_da_url(url):
    try:
        response = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        testo = " ".join(chunk.strip() for chunk in soup.stripped_strings)
        return re.sub(r"\s+", " ", testo)[:3000]
    except Exception:
        return ""
