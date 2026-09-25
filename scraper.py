import json
import re
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

# URLs de les pàgines de directes
URLS = [
    "https://www.3cat.cat/3cat/directes/tem1/",
    "https://www.3cat.cat/3cat/directes/tv3/",
    "https://www.3cat.cat/3cat/directes/324/",
    "https://www.3cat.cat/3cat/directes/esport3/",
    "https://www.3cat.cat/3cat/directes/sx3/"
]

def fetch_json(url):
    print(f"--> Sol·licitant URL: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8')
            print(f"    Resposta rebuda ({len(html)} caràcters). Buscant __NEXT_DATA__...")
            
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if match:
            print("    [OK] Bloc __NEXT_DATA__ trobat!")
            return json.loads(match.group(1))
        else:
            print("    [ERROR] No s'ha trobat l'etiqueta __NEXT_DATA__ a l'HTML.")
    except Exception as e:
        print(f"    [ERROR] Error al descarregar {url}: {e}")
    return None

def format_date(iso_str):
    if not iso_str:
        return ""
    try:
        iso_clean = iso_str.split('.')[0] + iso_str[-6:] if '.' in iso_str else iso_str
        dt = datetime.fromisoformat(iso_clean)
        return dt.strftime('%Y%m%d%H%M%S %z')
    except Exception:
        return ""

def main():
    print("=== INICI DE L'SCRAPER EPG 3CAT ===")
    all_programmes = []

    for url in URLS:
        data = fetch_json(url)
        if not data:
            continue
            
        try:
            structure = data.get('props', {}).get('pageProps', {}).get('structure', [])
            count_before = len(all_programmes)
            
            for block in structure:
                if block.get('name') == 'Fila':
                    for child in block.get('children', []):
                        items = child.get('finalProps', {}).get('items', [])
                        for item in items:
                            for key in ['ara_fem', 'despres_fem']:
                                prog = item.get(key)
                                if prog and isinstance(prog, dict):
                                    ch = prog.get('codi_canal')
                                    st = prog.get('start_time')
                                    et = prog.get('end_time')
                                    title = prog.get('titol_programa', '')
                                    if prog.get('titol_capitol'):
                                        title += f" - {prog.get('titol_capitol')}"
                                    
                                    if ch and st and et:
                                        all_programmes.append({
                                            'channel': ch,
                                            'start': format_date(st),
                                            'stop': format_date(et),
                                            'title': title,
                                            'desc': prog.get('sinopsi', ''),
                                            'category': prog.get('tematica', '')
                                        })
            print(f"    S'han trobat {len(all_programmes) - count_before} programes a aquesta URL.")
        except Exception as e:
            print(f"    [ERROR] Error processant l'estructura JSON: {e}")

    print(f"\nTotal de programes recollits: {len(all_programmes)}")

    if not all_programmes:
        print("[AVÍS] No s'ha pogut extreure cap programa. Es cancel·la la generació d'epg.xml.")
        return

    # Generar document XMLTV
    tv = ET.Element('tv', generator_info_name='3Cat EPG Scraper')
    
    # Canals únics
    channels = sorted(list(set(p['channel'] for p in all_programmes)))
    for ch_id in channels:
        ch_elem = ET.SubElement(tv, 'channel', id=ch_id)
        name_elem = ET.SubElement(ch_elem, 'display-name')
        name_elem.text = ch_id.upper()

    # Programes
    for prog in all_programmes:
        p_elem = ET.SubElement(tv, 'programme', {
            'start': prog['start'],
            'stop': prog['stop'],
            'channel': prog['channel']
        })
        t_elem = ET.SubElement(p_elem, 'title', lang='ca')
        t_elem.text = prog['title']
        if prog['desc']:
            d_elem = ET.SubElement(p_elem, 'desc', lang='ca')
            d_elem.text = prog['desc']
        if prog['category']:
            c_elem = ET.SubElement(p_elem, 'category', lang='ca')
            c_elem.text = prog['category']

    # Guardar el fitxer
    output_path = "epg.xml"
    tree = ET.ElementTree(tv)
    ET.indent(tree, space="  ", level=0)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    
    print(f"--- FITXER GENERAT ---")
    print(f"Ubicació: {os.path.abspath(output_path)}")
    print(f"Mida del fitxer: {os.path.getsize(output_path)} bytes")

if __name__ == "__main__":
    main()
