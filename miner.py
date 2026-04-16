import pandas as pd
from seleniumbase import SB
from bs4 import BeautifulSoup
import time
import os
import subprocess
import random
import json
import re

# ==========================================
# 📋 CONFIG & CLOUD SYNC
# ==========================================

CACHE_FILE = "team_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f: return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f: json.dump(cache, f, indent=4)

def load_watchlist():
    if not os.path.exists("targets.txt"):
        print("❌ targets.txt not found!")
        return []
    with open("targets.txt", "r") as file:
        return list(dict.fromkeys([line.strip() for line in file if line.strip()]))

def push_to_cloud():
    """Syncs the latest CSV and Cache to GitHub."""
    print("   ☁️ Syncing to GitHub...")
    try:
        # Standardizing remote to your SleeperKid repo
        subprocess.run('git add daily_stats.csv team_cache.json', shell=True, check=True)
        subprocess.run('git commit -m "🤖 Surgical Vault Update" || echo "No changes"', shell=True, check=True)
        subprocess.run('git push origin main', shell=True, check=True)
        print("      ✅ Sync Complete.")
    except Exception as e: 
        print(f"      [!] Git Error: {e}")

# ==========================================
# 🎯 RECOVERY-FIRST SCRAPING ENGINE
# ==========================================

def get_player_stats(sb, player_url, player_name):
    """Refined version of your working engine."""
    print(f"   ▶ Syncing {player_name}...")
    
    url_parts = player_url.split('/')
    try:
        p_id, p_slug = url_parts[-2], url_parts[-1]
    except: return 0.75, "" 

    base_kpr, l10_totals = 0.75, []

    try:
        # --- NAVIGATE TO STATS ---
        sb.uc_open_with_reconnect(f"https://www.hltv.org/stats/players/{p_id}/{p_slug}", reconnect_time=5)
        if "Verify you are human" in sb.get_page_source():
            sb.uc_gui_click_captcha() 

        soup = BeautifulSoup(sb.get_page_source(), 'lxml')
        for row in soup.find_all('div', class_='stats-row'):
            if "Kills / round" in row.text:
                base_kpr = float(row.find_all('span')[-1].text.strip())
                break

        # --- NAVIGATE TO MATCHES ---
        sb.uc_open_with_reconnect(f"https://www.hltv.org/stats/players/matches/{p_id}/{p_slug}", reconnect_time=4)
        soup = BeautifulSoup(sb.get_page_source(), 'lxml')
        table = soup.find('table', class_=lambda c: c and 'stats-table' in c)
        
        if table:
            rows = table.find('tbody').find_all('tr')
            all_maps = []
            
            for row in rows:
                tds = row.find_all('td')
                if len(tds) < 5: continue
                
                # Dynamic K-D Search (Your working logic)
                kd_text = ""
                for td in tds[4:]:
                    val = td.text.strip()
                    if re.match(r'^\d+\s*-\s*\d+$', val):
                        kd_text = val
                        break
                
                if not kd_text: continue
                # Match grouping using the series link
                match_link = tds[4].find('a', href=True) or tds[2].find('a', href=True)
                series_id = match_link['href'].split('/')[-2] if match_link else "unknown"
                
                try:
                    kills = int(kd_text.split('-')[0].strip())
                    all_maps.append({'k': kills, 'series': series_id})
                except: continue

            # --- SERIES GROUPING (Your working logic) ---
            match_groups = []
            if all_maps:
                curr_series, temp_grp = None, []
                for m in all_maps:
                    if m['series'] != curr_series:
                        if temp_grp: match_groups.append(temp_grp)
                        temp_grp, curr_series = [m['k']], m['series']
                    else: temp_grp.append(m['k'])
                if temp_grp: match_groups.append(temp_grp)

            # --- MAP 1+2 LOGIC (Your working logic) ---
            for grp in match_groups[:10]:
                chrono = grp[::-1] # Newest-to-Oldest becomes Oldest-to-Newest
                if len(chrono) >= 2:
                    # Chrono[0] = Map 1, Chrono[1] = Map 2
                    l10_totals.append(str(chrono[0] + chrono[1]))
                # Optional: Handle BO1s if desired, currently skips them if < 2 maps
                    
    except Exception as e:
        print(f"      [!] Skipping {player_name}: {e}")

    # Return exactly 2 values to fix the ValueError
    return base_kpr, ", ".join(l10_totals)

# ==========================================
# 🚀 MAIN EXECUTION
# ==========================================

def build_daily_vault():
    teams = load_watchlist()
    if not teams: return
    
    cache = load_cache()
    all_data = []

    with SB(uc=True, incognito=True, headless=False) as sb:
        for team in teams:
            team_clean = team.replace("CS2: ", "").strip()
            print(f"\n🕵️‍♂️ Targeting {team_clean}...")

            if team_clean in cache:
                team_url = cache[team_clean]
            else:
                sb.uc_open_with_reconnect(f"https://www.hltv.org/search?query={team_clean}", reconnect_time=4)
                soup = BeautifulSoup(sb.get_page_source(), 'lxml')
                links = soup.find_all('a', href=lambda h: h and "/team/" in h)
                
                if not links: continue
                
                # Filter out academy/female teams
                target_path = links[0]['href']
                for l in links:
                    if "academy" not in l.text.lower() and "female" not in l.text.lower():
                        target_path = l['href']
                        break
                
                team_url = "https://www.hltv.org" + target_path
                cache[team_clean] = team_url
                save_cache(cache)

            sb.uc_open_with_reconnect(team_url, reconnect_time=3)
            p_tags = BeautifulSoup(sb.get_page_source(), 'lxml').select('div.bodyshot-team.g-grid a.col-custom')
            
            for tag in p_tags:
                p_url = "https://www.hltv.org" + tag['href']
                # Surgical nickname extraction
                p_name = tag.get('title', '').split("'")[-2] if "'" in tag.get('title', '') else tag['href'].split('/')[-1]
                
                # Fix: Catching exactly 2 values
                k, l10 = get_player_stats(sb, p_url, p_name)
                
                if l10:
                    all_data.append({
                        "Player": p_name, "Team": team_clean, 
                        "BaseKPR": k, "L10": l10, "Game": "CS2"
                    })
                    print(f"      ✅ Success: {p_name}")

            # Push to GitHub after every team for safety
            if all_data:
                pd.DataFrame(all_data).to_csv("daily_stats.csv", index=False)
                push_to_cloud()

    print("\n✅ Vault Updated & Synced!")

if __name__ == "__main__":
    build_daily_vault()