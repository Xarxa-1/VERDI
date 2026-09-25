#!/usr/bin/env python3
"""
Scraper EPG per a 3Cat (Verdi Clàssics) -> epg.xml en format XMLTV
"""

import os
import sys
import time
import json
import datetime
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET
from xml.dom import minidom

import requests
from bs4 import BeautifulSoup

URL = "https://www.3cat.cat/3cat/directes/tem1/"
CHANNEL_ID = "verdi-classics"
CHANNEL_NAME = "Verdi Clàssics"
TIMEZONE = ZoneInfo("Europe/Madrid")
OUTPUT_FILE = "epg.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ca,es;q=0.9,en;q=0.8",
}

DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")


def log(*args):
    print(*args, file=sys.stderr)


# ---------------------------------------------------------------------------
# 1. Obtenció de l'HTML
# ---------------------------------------------------------------------------
def fetch_html():
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


# ---------------------------------------------------------------------------
# 2. Extracció de dades
# ---------------------------------------------------------------------------
def extract_from_next_data(html):
    """3cat és Next.js: moltes dades viuen dins <script id='__NEXT_DATA__'>."""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None
    try:
        data = json.loads(script.string)
    except Exception as e:
        log("No s'ha pogut parsejar __NEXT_DATA__:", e)
        return None

    result = {"current_title": None, "next_title": None, "next_time": None}

    # Claus candidates, en ordre de prioritat (les més específiques primer)
    CURRENT_KEYS = ("currentTitle", "current_title", "liveTitle", "title")
    NEXT_TITLE_KEYS = ("nextTitle", "next_title", "nextProgramTitle")
    NEXT_TIME_KEYS = ("nextTime", "next_time", "nextStartTime", "startTime")

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if result["current_title"] is None and k in CURRENT_KEYS:
                    if isinstance(v, str) and 2 < len(v) < 200:
                        result["current_title"] = v
                if result["next_title"] is None and k in NEXT_TITLE_KEYS:
                    if isinstance(v, str) and len(v) > 2:
                        result["next_title"] = v
                if result["next_time"] is None and k in NEXT_TIME_KEYS:
                    if isinstance(v, str):
                        result["next_time"] = v
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return result


def extract_from_html(html):
    """Fallback: selectors CSS sobre l'HTML renderitzat."""
    soup = BeautifulSoup(html, "html.parser")
    result = {"current_title": None, "next_title": None, "next_time": None}

    # Títol actual: provem diversos selectors genèrics
    for sel in (
        ".c-live-info__title",
        ".epg-current__title",
        "[data-testid='live-title']",
        "[class*='live'] [class*='title']",
        "[class*='Live'] h1",
        "[class*='directe'] h1",
        "main h1",
        "h1",
    ):
        el = soup.select_one(sel)
        if el:
            txt = el.get_text(strip=True)
            if txt and 2 < len(txt) < 200:
                result["current_title"] = txt
                break

    # Bloc "a continuació"
    next_section = soup.select_one(
        ".c-live-info__next, .epg-next, "
        "[class*='next'], [class*='Next'], [class*='seguent']"
    )
    if next_section:
        te = next_section.select_one("[class*='time'], [class*='hora'], time")
        ti = next_section.select_one("[class*='title'], h2, h3, h4")
        if te:
            result["next_time"] = te.get_text(strip=True)
        if ti:
            result["next_title"] = ti.get_text(strip=True)

    return result


def fetch_epg_data():
    html = fetch_html()

    if DEBUG:
        log("--- HTML (primeres 800 lletres) ---")
        log(html[:800])

    data_json = extract_from_next_data(html) or {}
    data_html = extract_from_html(html)

    current_title = data_json.get("current_title") or data_html.get("current_title")
    next_title = data_json.get("next_title") or data_html.get("next_title")
    next_time = data_json.get("next_time") or data_html.get("next_time")

    if DEBUG:
        log("Extret JSON:", data_json)
        log("Extret HTML:", data_html)

    # Fallbacks raonables (no inventem noms de pel·lícules)
    if not current_title:
        current_title = "Programació Verdi Clàssics"
    if not next_title:
        next_title = "Programa següent"
    if not next_time:
        now = datetime.datetime.now(TIMEZONE)
        next_time = (now + datetime.timedelta(hours=1)).strftime("%H:%M")

    return {
        "current_title": current_title,
        "next_title": next_title,
        "next_time": next_time,
    }


# ---------------------------------------------------------------------------
# 3. Generació XMLTV
# ---------------------------------------------------------------------------
def parse_hhmm(s):
    """Accepta '23:17', '23h17', '2317'. Retorna (h, m) o None."""
    if not s:
        return None
    s = s.strip().replace("h", ":").replace(".", ":")
    try:
        if ":" in s:
            h, m = s.split(":")[:2]
            h, m = int(h), int(m)
        elif len(s) == 4 and s.isdigit():
            h, m = int(s[:2]), int(s[2:])
        else:
            return None
        if 0 <= h < 24 and 0 <= m < 60:
            return h, m
    except Exception:
        pass
    return None


def fmt_xmltv(dt):
    """Format XMLTV: YYYYMMDDHHMMSS +HHMM (calcula offset real)."""
    offset = dt.utcoffset() or datetime.timedelta(0)
    total_min = int(offset.total_seconds() // 60)
    sign = "+" if total_min >= 0 else "-"
    total_min = abs(total_min)
    oh, om = divmod(total_min, 60)
    return dt.strftime("%Y%m%d%H%M%S") + f" {sign}{oh:02d}{om:02d}"


def generate_xmltv(data):
    now = datetime.datetime.now(TIMEZONE)
    today = now.date()

    # Hora d'inici del programa següent
    hm = parse_hhmm(data["next_time"])
    if hm:
        h, m = hm
        next_start = datetime.datetime.combine(
            today, datetime.time(h, m), tzinfo=TIMEZONE
        )
        # Si l'hora ja ha passat avui, és que és demà
        if next_start <= now:
            next_start += datetime.timedelta(days=1)
    else:
        next_start = now + datetime.timedelta(hours=1)

    # Programa actual: comença com a màxim fa 2h (o a mitjanit) i acaba
    # quan comença el següent.
    midnight = datetime.datetime.combine(today, datetime.time(0, 0), tzinfo=TIMEZONE)
    current_start = max(now - datetime.timedelta(hours=2), midnight)
    if current_start >= next_start:
        current_start = next_start - datetime.timedelta(minutes=30)

    # Programa següent: 2h de durada per defecte
    next_end = next_start + datetime.timedelta(hours=2)

    tv = ET.Element(
        "tv",
        {
            "generator-info-name": "3Cat-VerdiClassics-EPG-Scraper",
            "source-info-name": "3cat.cat",
        },
    )

    channel = ET.SubElement(tv, "channel", id=CHANNEL_ID)
    ET.SubElement(channel, "display-name", lang="ca").text = CHANNEL_NAME
    ET.SubElement(channel, "display-name").text = CHANNEL_ID

    prog1 = ET.SubElement(
        tv,
        "programme",
        {
            "start": fmt_xmltv(current_start),
            "stop": fmt_xmltv(next_start),
            "channel": CHANNEL_ID,
        },
    )
    ET.SubElement(prog1, "title", lang="ca").text = data["current_title"]

    prog2 = ET.SubElement(
        tv,
        "programme",
        {
            "start": fmt_xmltv(next_start),
            "stop": fmt_xmltv(next_end),
            "channel": CHANNEL_ID,
        },
    )
    ET.SubElement(prog2, "title", lang="ca").text = data["next_title"]

    rough = ET.tostring(tv, encoding="utf-8")
    reparsed = minidom.parseString(rough)
    return reparsed.toprettyxml(indent="  ")


# ---------------------------------------------------------------------------
# 4. Execució
# ---------------------------------------------------------------------------
def run_once():
    data = fetch_epg_data()
    xml_content = generate_xmltv(data)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(xml_content)

    print(xml_content)
    log(
        f"[{datetime.datetime.now(TIMEZONE).strftime('%H:%M:%S')}] "
        f"EPG actualitzat: {data['current_title']!r} -> "
        f"{data['next_title']!r} ({data['next_time']})"
    )


if __name__ == "__main__":
    if "--loop" in sys.argv:
        interval = 60
        for i, a in enumerate(sys.argv):
            if a == "--interval" and i + 1 < len(sys.argv):
                try:
                    interval = int(sys.argv[i + 1])
                except ValueError:
                    pass
        log(f"Iniciant bucle cada {interval}s...")
        while True:
            try:
                run_once()
            except Exception as e:
                log(f"Error: {e}")
            time.sleep(interval)
    else:
        run_once()
