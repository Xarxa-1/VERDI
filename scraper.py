import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

# URL de la pàgina de directes de 3Cat
URL = "https://www.3cat.cat/3cat/directes/tem1/"

def fetch_html(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        return response.read().decode('utf-8')

def parse_next_data(html_content):
    # Cercar el blocs JSON integrat a __NEXT_DATA__
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html_content, re.DOTALL)
    if not match:
        raise ValueError("No s'ha trobat el bloc __NEXT_DATA__ a la pàgina.")
    return json.loads(match.group(1))

def format_date_xmltv(iso_str):
    """Converteix dates ISO (ex: 2026-09-25T22:05:25+02:00) al format XMLTV (20260925220525 +0200)"""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime('%Y%m%d%H%M%S %z')
    except Exception:
        return ""

def generate_xmltv(data):
    tv = ET.Element('tv', generator_info_name='3Cat EPG Scraper')

    # Cercar els canals i programes dins de la llista de components
    try:
        structure = data['props']['pageProps']['structure']
    except KeyError:
        print("Estructura de dades JSON no vàlida")
        return

    channels_added = set()

    for item in structure:
        if item.get('name') == 'Fila':
            for child in item.get('children', []):
                if child.get('name') == 'Slider':
                    items = child.get('finalProps', {}).get('items', [])
                    for entry in items:
                        # Extraure programació "ara_fem" i "despres_fem"
                        for key in ['ara_fem', 'despres_fem']:
                            prog = entry.get(key)
                            if not prog or not isinstance(prog, dict):
                                continue

                            channel_id = prog.get('codi_canal', '3cat_default')
                            channel_name = channel_id.upper()

                            # Afegir canal si encara no s'ha afegit
                            if channel_id not in channels_added:
                                chan_elem = ET.SubElement(tv, 'channel', id=channel_id)
                                name_elem = ET.SubElement(chan_elem, 'display-name')
                                name_elem.text = channel_name
                                channels_added.add(channel_id)

                            # Crear entrada de programa
                            start = format_date_xmltv(prog.get('start_time'))
                            stop = format_date_xmltv(prog.get('end_time'))

                            programme = ET.SubElement(tv, 'programme', {
                                'start': start,
                                'stop': stop,
                                'channel': channel_id
                            })

                            # Títol
                            title_text = prog.get('titol_programa', '')
                            if prog.get('titol_capitol'):
                                title_text += f" - {prog.get('titol_capitol')}"
                            
                            title_elem = ET.SubElement(programme, 'title', lang='ca')
                            title_elem.text = title_text

                            # Descripció / Sinopsi
                            if prog.get('sinopsi'):
                                desc_elem = ET.SubElement(programme, 'desc', lang='ca')
                                desc_elem.text = prog.get('sinopsi')

                            # Categoria / Temàtica
                            if prog.get('tematica'):
                                cat_elem = ET.SubElement(programme, 'category', lang='ca')
                                cat_elem.text = f"Temàtica {prog.get('tematica')}"

    # Escriure l'XML generat
    tree = ET.ElementTree(tv)
    ET.indent(tree, space="  ", level=0)
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)
    print("Fitxer epg.xml generat correctament.")

if __name__ == "__main__":
    html = fetch_html(URL)
    next_data = parse_next_data(html)
    generate_xmltv(next_data)
