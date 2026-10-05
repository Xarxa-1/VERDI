#!/usr/bin/env python3
import json
import urllib.request
import sys
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# URL de l'API de 3Cat per al canal TEM1
API_URL = "https://api-media.3cat.cat/pvideo/media.jsp?media=video&versio=vast&idint=tem1&desplacament=0&profile=pc_3cat"
OUTPUT_FILE = "epg.xml"
CHANNEL_ID = "tem1"
CHANNEL_NAME = "TEM1"

def fetch_api():
    """Descarrega les dades de l'API."""
    req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

def format_xmltv_time(dt_str):
    """Converteix la data ISO a format XMLTV (YYYYMMDDHHMMSS +HHMM)."""
    # Exemple d'entrada: "2026-10-05T20:14:50+02:00"
    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%Y%m%d%H%M%S %z")

def add_programme(root, prog):
    """Afegeix un programa a l'XML."""
    start = prog.get("data_emissio", {}).get("utc")
    stop = prog.get("data_caducitat", {}).get("utc")
    
    if not start or not stop:
        return

    # Crear element programme
    programme = SubElement(root, "programme", attrib={
        "start": format_xmltv_time(start),
        "stop": format_xmltv_time(stop),
        "channel": CHANNEL_ID
    })

    # Títol
    title = SubElement(programme, "title", lang="ca")
    title.text = prog.get("titol", "Sense títol")

    # Descripció
    desc = SubElement(programme, "desc", lang="ca")
    desc.text = prog.get("descripcio", "")

    # Categoria
    if prog.get("programa"):
        cat = SubElement(programme, "category", lang="ca")
        cat.text = prog["programa"]

def main():
    try:
        data = fetch_api()
    except Exception as e:
        print(f"Error descarregant l'API: {e}", file=sys.stderr)
        sys.exit(1)

    # Arrel de l'XML
    tv = Element("tv", attrib={"generator-info-name": "3cat-epg-scraper"})

    # Canal
    channel = SubElement(tv, "channel", id=CHANNEL_ID)
    display_name = SubElement(channel, "display-name", lang="ca")
    display_name.text = CHANNEL_NAME

    # Extreure programes
    info = data.get("informacio", {})
    
    # Programa actual (arafem)
    if info.get("arafem"):
        add_programme(tv, info["arafem"])
        
    # Programa següent (despresfem)
    if info.get("despresfem"):
        add_programme(tv, info["despresfem"])

    # Guardar arxiu formatat
    rough_string = tostring(tv, encoding="unicode")
    parsed = minidom.parseString(rough_string)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(parsed.toprettyxml(indent="  ", encoding="UTF-8").decode("UTF-8"))
    
    print(f"EPG generat correctament a {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
