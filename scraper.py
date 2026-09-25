import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

# Llista de canals / URLs de 3Cat a analitzar
URLS = [
    "https://www.3cat.cat/3cat/directes/tem1/",
    "https://www.3cat.cat/3cat/directes/tv3/",
    "https://www.3cat.cat/3cat/directes/324/",
    "https://www.3cat.cat/3cat/directes/esport3/",
    "https://www.3cat.cat/3cat/directes/sx3/"
]

def fetch_json_data(url):
    """Descarrega el contingut d'una pàgina i n'extreu el bloc __NEXT_DATA__"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
        
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except Exception as e:
        print(f"Error descarregant/parsing {url}: {e}")
    return None

def format_xmltv_date(iso_str):
    """Converteix format ISO8601 (2026-09-25T22:05:25+02:00) a format XMLTV (20260925220525 +0200)"""
    if not iso_str:
        return ""
    try:
        # Neteja de mil·lissegons si n'hi ha
        iso_str = iso_str.split('.')[0] + iso_str[-6:] if '.' in iso_str else iso_str
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime('%Y%m%d%H%M%S %z')
    except Exception as e:
        print(f"Error formatant data {iso_str}: {e}")
        return ""

def process_programmes(data, programmes_dict):
    """Extreu la informació de programació del JSON __NEXT_DATA__"""
    try:
        structure = data.get('props', {}).get('pageProps', {}).get('structure', [])
    except Exception:
        return

    for block in structure:
        if block.get('name') == 'Fila':
            for child in block.get('children', []):
                # Extraure si és de tipus Slider (canals TDT)
                if child.get('name') == 'Slider':
                    items = child.get('finalProps', {}).get('items', [])
                    for item in items:
                        for slot in ['ara_fem', 'despres_fem']:
                            prog = item.get(slot)
                            if prog and isinstance(prog, dict):
                                add_programme_to_dict(prog, programmes_dict)

def add_programme_to_dict(prog, programmes_dict):
    channel_id = prog.get('codi_canal', '').strip()
    start_raw = prog.get('start_time')
    stop_raw = prog.get('end_time')

    if not channel_id or not start_raw or not stop_raw:
        return

    title = prog.get('titol_programa', '')
    if prog.get('titol_capitol'):
        title += f" - {prog.get('titol_capitol')}"

    prog_key = f"{channel_id}_{start_raw}"
    programmes_dict[prog_key] = {
        'channel': channel_id,
        'start': format_xmltv_date(start_raw),
        'stop': format_xmltv_date(stop_raw),
        'title': title,
        'desc': prog.get('sinopsi', ''),
        'category': prog.get('tematica', '')
    }

def main():
    programmes_dict = {}

    print("Iniciant extracció de dades EPG 3Cat...")
    for url in URLS:
        print(f"Processant: {url}")
        json_data = fetch_json_data(url)
        if json_data:
            process_programmes(json_data, programmes_dict)

    if not programmes_dict:
        print("ALERTA: No s'ha pogut extreure cap programa. Revisa la connexió o l'estructura.")
        return

    # Generar l'XML final
    tv = ET.Element('tv', generator_info_name='3Cat EPG Generator')

    # 1. Identificar i crear la llista de canals únics
    channels = sorted(list(set(p['channel'] for p in programmes_dict.values())))
    for ch_id in channels:
        channel_elem = ET.SubElement(tv, 'channel', id=ch_id)
        display_name = ET.SubElement(channel_elem, 'display-name')
        display_name.text = ch_id.upper()

    # 2. Afegir tots els programes
    for prog in programmes_dict.values():
        programme_elem = ET.SubElement(tv, 'programme', {
            'start': prog['start'],
            'stop': prog['stop'],
            'channel': prog['channel']
        })
        
        title_elem = ET.SubElement(programme_elem, 'title', lang='ca')
        title_elem.text = prog['title']

        if prog['desc']:
            desc_elem = ET.SubElement(programme_elem, 'desc', lang='ca')
            desc_elem.text = prog['desc']

        if prog['category']:
            cat_elem = ET.SubElement(programme_elem, 'category', lang='ca')
            cat_elem.text = f"Temàtica {prog['category']}"

    # Desar a disc
    tree = ET.ElementTree(tv)
    ET.indent(tree, space="  ", level=0)
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)
    print(f"PROCÉS COMPLETAT: Se s'han guardat {len(programmes_dict)} programes a epg.xml.")

if __name__ == "__main__":
    main()
