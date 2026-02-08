import requests
from bs4 import BeautifulSoup
import json
import re
import time
import random
import os
import html

# --- KONFIGURACJA ---
START_ID = 1      
END_ID = 10000       # Zwiększ ten zakres (np. do 5000)
OUTPUT_FILE = 'margonem_maps_final.json'

BASE_URL_VIEW = 'https://www.margoworld.pl/world/view/'
BASE_URL_FRAME = 'https://www.margoworld.pl/world-frame/'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def load_existing_db():
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_db(data):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def extract_map_id(href):
    if not href: return None
    match = re.search(r'/world/view/(\d+)', href)
    return int(match.group(1)) if match else None

def parse_npc_data(soup_frame):
    """Analizuje NPC i grupuje ich."""
    npc_counts = {}
    npc_divs = soup_frame.find_all('div', class_='npc')

    for npc in npc_divs:
        raw_tip = npc.get('data-tip', '')
        decoded_tip = html.unescape(raw_tip)

        # Regex: wyciąga nazwę z <b>Nazwa</b> i level
        match = re.search(r'<b>(.*?)</b>(.*)', decoded_tip)
        
        name = "Nieznany"
        level = 0

        if match:
            name = match.group(1).strip()
            level_str = match.group(2).replace('lvl', '').strip()
            level = int(level_str) if level_str.isdigit() else 0
        else:
            name = BeautifulSoup(decoded_tip, "html.parser").get_text(strip=True)

        # Obrazek
        style = npc.get('style', '')
        img_match = re.search(r'url\(["\']?(.*?)["\']?\)', style)
        image_url = img_match.group(1) if img_match else ""

        # Klucz unikalności (żeby grupować te same moby)
        unique_key = (name, level, image_url)

        if unique_key in npc_counts:
            npc_counts[unique_key] += 1
        else:
            npc_counts[unique_key] = 1

    # Formatowanie listy
    npc_list = []
    for (n, l, i), count in npc_counts.items():
        npc_list.append({
            "name": n,
            "level": l,
            "count": count,
            "image": i
        })
    return npc_list

def scrape_maps():
    maps_db = load_existing_db()
    print(f"Rozpoczynam pobieranie (Filtrowanie błędów) do pliku: {OUTPUT_FILE}")

    for map_id in range(START_ID, END_ID + 1):
        str_map_id = str(map_id)

        try:
            # 1. Pobierz widok główny (nazwa)
            resp_view = requests.get(f"{BASE_URL_VIEW}{map_id}", headers=HEADERS)
            if resp_view.status_code != 200:
                print(f"[!] ID {map_id}: Błąd HTTP {resp_view.status_code}")
                continue

            soup_view = BeautifulSoup(resp_view.text, 'html.parser')
            title_tag = soup_view.find('h2')
            
            if not title_tag:
                continue 

            map_name = title_tag.get_text(strip=True)

            # --- FILTR ANTY-ŚMIECIOWY ---
            # Jeśli nazwa to "Błąd" albo jest pusta -> POMIJAMY
            if map_name == "Błąd" or not map_name:
                print(f"[-] ID {map_id}: Mapa nie istnieje (Błąd). Pomijam.")
                continue
            # -----------------------------

            # 2. Pobierz ramkę (przejścia i NPC)
            resp_frame = requests.get(f"{BASE_URL_FRAME}{map_id}", headers=HEADERS)
            connections = {}
            npcs = []
            
            if resp_frame.status_code == 200:
                soup_frame = BeautifulSoup(resp_frame.text, 'html.parser')
                
                # Przejścia
                links = soup_frame.find_all('a', href=re.compile(r'/world/view/'))
                for link in links:
                    target_id = extract_map_id(link['href'])
                    if target_id and target_id != map_id:
                        str_target = str(target_id)
                        if str_target not in connections:
                            img = link.find('img')
                            t_name = img.get('data-tip') or img.get('title') or "Nieznana" if img else "Nieznana"
                            connections[str_target] = t_name
                
                # NPC
                npcs = parse_npc_data(soup_frame)

            # --- DODATKOWY FILTR ---
            # Jeśli mapa nie ma wyjść ORAZ nie ma NPC, a nazwa jest podejrzana, też można pominąć
            # Ale na razie zostawiamy tylko filtr po nazwie "Błąd" zgodnie z prośbą.

            # Zapis do pamięci
            maps_db[str_map_id] = {
                "name": map_name,
                "exits": connections,
                "npcs": npcs
            }

            # Zapis do pliku
            save_db(maps_db)
            
            # Statystyki w konsoli
            total_npcs = sum(n['count'] for n in npcs)
            print(f"[+] ID {map_id}: {map_name} | Wyjść: {len(connections)} | NPC: {total_npcs}")
            
            time.sleep(random.uniform(0.2, 0.5))

        except Exception as e:
            print(f"[ERROR] ID {map_id}: {e}")

    print(f"\nZakończono! Czysta baza zapisana w: {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_maps()