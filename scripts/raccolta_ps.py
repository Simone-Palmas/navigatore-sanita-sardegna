"""
Raccolta dati Pronto Soccorso Sardegna
Scarica lo stato dei pronto soccorso dal Monitor PS della Regione Sardegna
e aggiunge una riga per ogni pronto soccorso al CSV del mese corrente.
Progetto demo non commerciale, a scopo di portfolio.
"""
import csv
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://monitorps.sardegnasalute.it/monitorps/MonitorServlet"

# Le 11 aziende sanitarie con il loro codice usato dal sito
AZIENDE = {
    "200101": "ASL Sassari",
    "200102": "ASL Gallura",
    "200103": "ASL Nuoro",
    "200104": "ASL Ogliastra",
    "200105": "ASL Oristano",
    "200106": "ASL Medio Campidano",
    "200107": "ASL Sulcis",
    "200108": "ASL Cagliari",
    "200904": "ARNAS Brotzu",
    "200905": "AOU Sassari",
    "200906": "AOU Cagliari",
}

# I 5 codici del triage, nell'ordine delle colonne della tabella
CODICI = ["1_rosso", "2_arancione", "3_azzurro", "4_verde", "5_bianco"]

# Righe della tabella del sito -> nome della colonna nel CSV
RIGHE = {
    "Pazienti in visita": "in_visita",
    "Pazienti in arrivo da 118": "in_arrivo_118",
    "Pazienti in attesa di visita": "in_attesa",
    "Tempo massimo di attesa": "attesa_max",
    "Attesa prevista": "attesa_prevista",
}

COLONNE = ["data_ora_raccolta", "ultimo_aggiornamento_sito",
           "codice_azienda", "azienda", "pronto_soccorso"] + [
    f"{chiave}_{codice}" for chiave in RIGHE.values() for codice in CODICI
]

ORA_ITALIA = ZoneInfo("Europe/Rome")


def leggi_azienda(sessione, codice_azienda):
    """Scarica i dati di un'azienda sanitaria e restituisce una riga per pronto soccorso."""
    risposta = sessione.get(
        URL,
        params={
            "codiceAziendaSanitaria": codice_azienda,
            "tipoProntoSoccorso": "GENERALE",
            "xhr": "true",
        },
        timeout=30,
    )
    risposta.raise_for_status()
    dati = json.loads(risposta.text)

    ultimo_aggiornamento = " ".join(dati.get("lastRefresh", "").split())
    pagina = BeautifulSoup(dati["view"], "html.parser")

    righe = []
    for tabella in pagina.select("table.tableTriagePS"):
        titolo = tabella.find_previous("span", class_="titoloparagrafo")
        nome_ps = " ".join(titolo.get_text().split()) if titolo else "SCONOSCIUTO"

        riga = {
            "data_ora_raccolta": datetime.now(ORA_ITALIA).strftime("%Y-%m-%d %H:%M"),
            "ultimo_aggiornamento_sito": ultimo_aggiornamento,
            "codice_azienda": codice_azienda,
            "azienda": AZIENDE[codice_azienda],
            "pronto_soccorso": nome_ps,
        }

        for tr in tabella.find_all("tr"):
            celle = [" ".join(td.get_text().split()) for td in tr.find_all(["td", "th"])]
            if not celle:
                continue
            for testo, chiave in RIGHE.items():
                if celle[0].startswith(testo):
                    for codice, valore in zip(CODICI, celle[1:6]):
                        riga[f"{chiave}_{codice}"] = valore

        righe.append(riga)
    return righe


def main():
    sessione = requests.Session()
    # Intestazioni come quelle di un normale browser
    sessione.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "it-IT,it;q=0.9",
        "Referer": URL,
        "X-Requested-With": "XMLHttpRequest",
    })

    # Prima visita alla pagina principale, come farebbe un browser
    sessione.get(URL, timeout=30)

    tutte_le_righe = []
    for codice in AZIENDE:
        try:
            righe = leggi_azienda(sessione, codice)
            print(f"{AZIENDE[codice]}: {len(righe)} pronto soccorso")
            tutte_le_righe.extend(righe)
        except Exception as errore:
            print(f"ERRORE {AZIENDE[codice]}: {errore}")
        time.sleep(2)  # pausa di cortesia tra una richiesta e l'altra

    if not tutte_le_righe:
        raise SystemExit("Nessun dato raccolto: controllare il sito o lo script.")

    os.makedirs("data", exist_ok=True)
    mese = datetime.now(ORA_ITALIA).strftime("%Y-%m")
    percorso = f"data/ps_{mese}.csv"
    file_nuovo = not os.path.exists(percorso)

    with open(percorso, "a", newline="", encoding="utf-8") as f:
        scrittore = csv.DictWriter(f, fieldnames=COLONNE)
        if file_nuovo:
            scrittore.writeheader()
        scrittore.writerows(tutte_le_righe)

    print(f"Salvate {len(tutte_le_righe)} righe in {percorso}")


if __name__ == "__main__":
    main()
