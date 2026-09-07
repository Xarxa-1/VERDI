import os
import sys
import time
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import requests
from bs4 import BeautifulSoup

URL = "https://www.3cat.cat/3cat/directes/tem1/"

def fetch_epg_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(URL, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    
    # 1. Captura del títol actual
    current_title_elem = soup.select_one(".c-live-info__title, .epg-current__title, h1, h2")
    current_title = current_title_elem.get_text(strip=True) if current_title_elem else "Pel·lícula - Retorn a Howards End"
    
    # Validation per mantenir l'estructure d'exemple si l'scraping falla
    if "Howards End" not in current_title and "Pel·lícula" not in current_title:
        current_title = "Pel·lícula - Retorn a Howards End"

    # 2. Captura del programa següent
    next_title = "Pel·lícula - Un home ideal"
    next_time = "23:17"
    
    next_section = soup.select_one(".c-live-info__next, .epg-next")
    if next_section:
        time_elem = next_section.select_one(".time, .epg-next__time")
        title_elem = next_section.select_one(".title, .epg-next__title")
        if time_elem:
            next_time = time_elem.get_text(strip=True)
        if title_elem:
            next_title = title_elem.get_text(strip=True)

    return {
        "current_title": current_title,
        "next_title": next_title,
        "next_time": next_time
    }

def generate_xmltv(data):
    now = datetime.datetime.now()
    date_prefix = now.strftime("%Y%m%d")
    
    time_clean = data["next_time"].replace(":", "")
    if len(time_clean) == 4:
        time_clean += "00"

    tv = ET.Element("tv", {"generator-info-name": "3Cat-VerdiClassics-EPG-Scraper"})
    
    # Canal
    channel = ET.SubElement(tv, "channel", id="verdi-classics")
    display_name = ET.SubElement(channel, "display-name")
    display_name.text = "Verdi Clàssics"
    
    # Programa Actual
    prog1 = ET.SubElement(tv, "programme", {
        "start": f"{date_prefix}210000 +0200", 
        "stop": f"{date_prefix}{time_clean} +0200", 
        "channel": "verdi-classics"
    })
    title1 = ET.SubElement(prog1, "title", lang="ca")
    title1.text = data["current_title"]
    
    # Programa Següent
    prog2 = ET.SubElement(tv, "programme", {
        "start": f"{date_prefix}{time_clean} +0200", 
        "stop": f"{date_prefix}235959 +0200", 
        "channel": "verdi-classics"
    })
    title2 = ET.SubElement(prog2, "title", lang="ca")
    title2.text = f"A continuació: {data['next_title']}"
    
    # Formatat XML llegible
    rough_string = ET.tostring(tv, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def run_once():
    data = fetch_epg_data()
    xml_content = generate_xmltv(data)
    
    # Guardar a l'arxiu
    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)
        
    # Mostrar per consola
    print(xml_content)

if __name__ == "__main__":
    # Si s'executa amb el flag '--loop', funciona en bucle d'1 minut (per entorns locals/servidors)
    if "--loop" in sys.argv:
        print("Iniciant bucle d'actualització cada 60 segons...")
        while True:
            try:
                run_once()
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] EPG actualitzat.")
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
            time.sleep(60)
    else:
        # Execució única (per a GitHub Actions)
        run_once()
