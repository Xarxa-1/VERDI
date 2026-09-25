import urllib.request
import json
import xml.etree.ElementTree as ET
from datetime import datetime

# Canals de 3Cat a extreure
CHANNELS = {
    'TV3': 'TV3',
    '324': '324',
    'ESP3': 'Esport3',
    'SX3': 'SX3'
}

def get_epg():
    tv = ET.Element('tv', generator_info_name='3Cat EPG Generator')
    
    # Afegir canals
    for ch_id, ch_name in CHANNELS.items():
        chan_elem = ET.SubElement(tv, 'channel', id=ch_id)
        name_elem = ET.SubElement(chan_elem, 'display-name')
        name_elem.text = ch_name

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # URL de l'API directa de la graella de 3Cat
    url = "https://a3cat.cat/api/epg/programacio"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            for item in data.get('emissions', []):
                ch_code = item.get('codi_canal')
                if ch_code in CHANNELS:
                    prog = ET.SubElement(tv, 'programme', {
                        'start': format_date(item.get('hora_inici')),
                        'stop': format_date(item.get('hora_fi')),
                        'channel': ch_code
                    })
                    
                    title = ET.SubElement(prog, 'title', lang='ca')
                    title.text = item.get('titol', 'Sense títol')
                    
                    if item.get('sinopsi'):
                        desc = ET.SubElement(prog, 'desc', lang='ca')
                        desc.text = item.get('sinopsi')

    except Exception as e:
        print(f"Error descarregant l'API: {e}")
        # En cas que l'API falli, utilitza la via secundària d'emergència
        fallback_3cat(tv)

    tree = ET.ElementTree(tv)
    ET.indent(tree, space="  ", level=0)
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)
    print("Fitxer epg.xml actualitzat amb èxit!")

def fallback_3cat(tv):
    print("Executant mètode d'emergència via scraping web...")
    url = "https://www.3cat.cat/3cat/directes/tv3/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            html = resp.read().decode('utf-8')
            import re
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
            if match:
                json_data = json.loads(match.group(1))
                structure = json_data.get('props', {}).get('pageProps', {}).get('structure', [])
                for block in structure:
                    if block.get('name') == 'Fila':
                        for child in block.get('children', []):
                            items = child.get('finalProps', {}).get('items', [])
                            for entry in items:
                                for k in ['ara_fem', 'despres_fem']:
                                    p = entry.get(k)
                                    if p and isinstance(p, dict):
                                        prog = ET.SubElement(tv, 'programme', {
                                            'start': format_date(p.get('start_time')),
                                            'stop': format_date(p.get('end_time')),
                                            'channel': p.get('codi_canal', 'TV3')
                                        })
                                        t = ET.SubElement(prog, 'title', lang='ca')
                                        t.text = p.get('titol_programa', '')
    except Exception as ex:
        print(f"Error al fallback: {ex}")

def format_date(date_str):
    if not date_str:
        return ""
    try:
        clean_str = date_str.split('.')[0].replace('Z', '+00:00')
        dt = datetime.fromisoformat(clean_str)
        return dt.strftime('%Y%m%d%H%M%S +0200')
    except Exception:
        return ""

if __name__ == "__main__":
    get_epg()
