import gspread
from gspread_dataframe import set_with_dataframe, get_as_dataframe
from google.oauth2.service_account import Credentials
import pandas as pd
import re
import os
import time
import random
from seleniumbase import SB
from bs4 import BeautifulSoup

# ==========================================
# 🛡️ THE ATOMIC UPSERT (Purity Doctrine)
# ==========================================
def upload_to_vault(new_df, worksheet_name):
    if new_df.empty: return
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open("PropVault") 
        worksheet = spreadsheet.worksheet(worksheet_name)
        
        # Load existing data; drop calculated fields to maintain Raw Data Layer [Manifest 1.0]
        try:
            existing_df = get_as_dataframe(worksheet).dropna(how='all').dropna(axis=1, how='all')
            for d in [existing_df, new_df]:
                if 'Edge %' in d.columns: d.drop(columns=['Edge %'], inplace=True)
        except:
            existing_df = pd.DataFrame()

        # Atomic Upsert: Overwrite old stats for the same player [Manifest 1.0]
        final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['Player'], keep='last')
        
        worksheet.clear()
        set_with_dataframe(worksheet, final_df)
        print(f"🚀 [VAULT UPDATE] {worksheet_name} Sync Complete.")
    except Exception as e:
        print(f"❌ [CRITICAL] Vault Sync Failure: {e}")

# ==========================================
# 🎮 CORE ENGINE (V172: DEEP TABLE)
# ==========================================
def get_cs2_team_lineup(sb, team_name, team_url):
    players_data = []
    try:
        print(f"📡 [CS2] V172 Deep Table Sync: {team_name}...")
        sb.uc_open_with_reconnect(team_url, 12)
        
        # Discovery Phase
        soup = BeautifulSoup(sb.get_page_source(), 'lxml')
        seen_ids, roster_links = set(), []
        for a in soup.select('a[href*="/player/"]'):
            href = a.get('href')
            p_id = href.split('/')[2]
            if 'coach' not in href.lower() and p_id.isdigit() and p_id not in seen_ids:
                roster_links.append(a); seen_ids.add(p_id)
            if len(roster_links) >= 5: break

        for link in roster_links:
            p_tag, p_id = link.get_text().strip(), link.get('href').split('/')[2]
            try:
                # 1. KPR Extraction
                sb.open(f"https://www.hltv.org/stats/players/{p_id}/{p_tag.lower()}?startDate=2026-01-01")
                sb.execute_script("window.scrollTo(0, 400);") # Trigger lazy-load
                sb.sleep(2)
                
                kpr = 0.72 
                m = re.search(r"(?:Kills / round|KPR).*?>(\d\.\d+)<", sb.get_page_source(), re.S | re.I)
                if m: kpr = float(m.group(1))

                # 2. MATCH HISTORY: V172 Multi-Selector Fallback
                sb.open(f"https://www.hltv.org/stats/players/matches/{p_id}/{p_tag.lower()}")
                sb.execute_script("window.scrollTo(0, 600);")
                
                # Check for table presence via multiple tags used in 2026 UI
                table_selector = ".stats-table, table.matches-table, table"
                try:
                    sb.wait_for_element(table_selector, timeout=15)
                except:
                    print(f"      ⚠️  {p_tag} table blocked. Signaling Restart.")
                    return "RESTART_REQUIRED"

                m_soup = BeautifulSoup(sb.get_page_source(), 'lxml')
                # Find the largest table on the page if .stats-table is missing
                m_table = m_soup.select_one('.stats-table') or m_soup.find('table')
                
                l10 = []
                if m_table:
                    rows = m_table.select('tbody tr')
                    raw_maps = []
                    for r in rows:
                        c = r.find_all('td')
                        if len(c) < 5: continue
                        opp = re.sub(r'[^A-Z]', '', c[1].get_text().split('(')[0].upper())
                        date = c[0].get_text()
                        raw_maps.append({'id': f"{opp}_{date}", 'k': int(re.split(r'[-/]', c[4].get_text())[0])})
                    
                    if raw_maps:
                        keys = []
                        for m in raw_maps:
                            if m['id'] not in keys: keys.append(m['id'])
                        for k in keys:
                            s_k = [x['k'] for x in raw_maps if x['id'] == k]
                            l10.append(sum(s_k[:2]))
                            if len(l10) >= 10: break
                
                players_data.append({"Player": p_tag, "Game": "CS2", "Team": team_name, "KPR": kpr, "L10": ", ".join(map(str, l10))})
                print(f"      ✅ {p_tag}: {kpr} KPR Sync Complete.")
                sb.sleep(1.5)
            except Exception as e:
                print(f"      ⚠️ {p_tag} failed: {str(e)[:30]}...")
                continue
        return players_data
    except Exception as e:
        print(f"🛑 Fatal: {e}"); return []

# ==========================================
# 🛡️ VAL ENGINE (V171: ROBUST SELECTOR)
# ==========================================
def get_val_team_lineup(sb, team_name, team_url):
    players_data = []
    try:
        print(f"📡 [VAL] V171 Robust Sync: {team_name}...")
        sb.uc_open_with_reconnect(team_url, 10)
        soup = BeautifulSoup(sb.get_page_source(), 'lxml')
        player_links = [f"https://www.vlr.gg{a.get('href')}" for a in soup.select('a[href^="/player/"]')][:5]
            
        for l in player_links:
            sb.open(f"{l}/?game=all&tab=matches")
            sb.sleep(3)
            p_soup = BeautifulSoup(sb.get_page_source(), 'lxml')
            
            # V171: Flexible Header Discovery (Kills NoneType error)
            header = p_soup.select_one('.player-header-name, .wf-title, h1')
            p_tag = header.get_text().strip() if header else "Unknown"
            
            kills = [k.get_text().strip() for k in p_soup.select('.m-item-stat.mod-vlr-k')][:10]
            players_data.append({"Player": p_tag, "Game": "Valorant", "Team": team_name, "L10": ", ".join(kills)})
            print(f"      ✅ [VAL] {p_tag} Sync Complete.")
        return players_data
    except Exception as e:
        print(f"⚠️ VAL Failed: {e}"); return []
# ==========================================
# 🏁 MAIN EXECUTION (Heartbeat Restart Logic)
# ==========================================
if __name__ == "__main__":
    print("🛠️  Initializing V141.2 Sleeper Standard Miner...")
    with open("targets.txt", "r") as f:
        targets_raw = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    
    idx = 0
    while idx < len(targets_raw):
        with SB(uc=True, headless=False) as sb:
            try:
                for i in range(idx, len(targets_raw)):
                    prefix, rest = targets_raw[i].split(":", 1)
                    team_name, team_url = rest.split("|", 1)
                    res = get_cs2_team_lineup(sb, team_name.strip(), team_url.strip()) if prefix.strip() == "CS2" else get_val_team_lineup(sb, team_name.strip(), team_url.strip())
                    
                    if res == "RESTART_REQUIRED":
                        print("♻️  Cloudflare Heartbeat Triggered. Relaunching...")
                        break
                    
                    if res: upload_to_vault(pd.DataFrame(res), f"{prefix.strip()}_DATA")
                    idx += 1
            except Exception as e:
                print(f"🧨 Fatality: {e}. Cooling down..."); time.sleep(10)
    print("🏁 [FINISH] Sync Complete. Iron Guard Intel is Live.")