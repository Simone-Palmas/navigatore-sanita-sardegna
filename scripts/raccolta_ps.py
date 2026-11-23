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


def mostra_risposta(etichetta, risposta):
    """Stampa le informazioni utili a capire come ha risposto il sito."""
    print(f"--- {etichetta}: codice {risposta.status_code}")
    if risposta.status_code != 200:
        motivo = risposta.headers.get("WWW-Authenticate", "nessuno")
        testo = " ".join(risposta.text.split())[:400]
        print(f"    Intestazione WWW-Authenticate: {motivo}")
        print(f"    Testo della risposta: {testo}")


def leggi_azienda(sessione, codice_azienda):
    """Scarica i dati di un'azienda sanitaria e restituisce una riga per pronto soccorso."""
    # 1) "Clic" sul menu dell'azienda, come nel browser
    menu = sessione.post(
        URL,
        data={"page": "carLavoroAsl", "user_id": "public",
              "codiceAziendaSanitaria": codice_azienda},
        timeout=30,
    )
    mostra_risposta(f"Menu {AZIENDE[codice_azienda]}", menu)

    # 2) Richiesta dei dati aggiornati
    risposta = sessione.get(
        URL,
        params={
            "codiceAziendaSanitaria": codice_azienda,
            "tipoProntoSoccorso": "GENERALE",
            "xhr": "true",
        },
        headers={"X-Requested-With": "XMLHttpRequest",
                 "Accept": "application/json, text/javascript, */*; q=0.01"},
        timeout=30,
    )
    mostra_risposta(f"Dati {AZIENDE[codice_azienda]}", risposta)
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0;
