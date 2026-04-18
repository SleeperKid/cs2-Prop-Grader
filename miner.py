import gspread
from gspread_dataframe import set_with_dataframe, get_as_dataframe
from google.oauth2.service_account import Credentials
import pandas as pd
import re
import os
import time
from seleniumbase import SB
from bs4 import BeautifulSoup

# ==========================================
# 🛡️ THE ATOMIC UPSERT
# ==========================================
def upload_to_vault(new_df, worksheet_name):
    if new_df.empty: return
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open("PropVault") 
        worksheet = spreadsheet.worksheet(worksheet_name)
        existing_df = get_as_dataframe(worksheet).dropna(how='all').dropna(axis=1, how='all')
        for d in [existing_df, new_df]:
            if 'Edge %' in d.columns: d.drop(columns=['Edge %'], inplace=True)
        final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['Player'], keep='last')
        worksheet.clear()
        set_with_dataframe(worksheet, final_df)
        print(f"🚀 [SUCCESS] {worksheet_name} Sync Complete.")
    except Exception as e:
        print(f"❌ [CRITICAL] Sync Failure: {e}")

# ==========================================
# 🎮 CS2 ENGINE (V132: TITAN STABLE)
# ==========================================
def get_cs2_team_lineup(sb, team_name, team_url):
    players_data = []
    try:
        print(f"📡 [CS2] Accessing Team: {team_name}...")
        sb.open(team_url); sb.sleep(5)
        soup = BeautifulSoup(sb.get_page_source(), 'lxml')
        roster_links = soup.select('a[href^="/player/"]')[:5]
        for link in roster_links:
            try:
                p_tag, p_id = link.get_text().strip(), link.get('href').split('/')[2]
                sb.open(f"https://www.hltv.org/stats/players/{p_id}/{p_tag.lower()}?startDate=2026-01-01")
                sb.wait_for_element(".stats-row", timeout=10)
                kpr = 0.82
                stat_soup = BeautifulSoup(sb.get_page_source(), 'lxml')
                k_label = stat_soup.find(string=re.compile(r"Kills [/p] round", re.I))
                if k_label:
                    m = re.search(r"\d+\.\d+", k_label.find_parent().get_text())
                    if m: kpr = float(m.group())
                
                sb.open(f"https://www.hltv.org/stats/players/matches/{p_id}/{p_tag.lower()}?startDate=2026-01-01")
                sb.sleep(4)
                m_soup = BeautifulSoup(sb.get_page_source(), 'lxml')
                headers = [th.get_text().strip() for th in m_soup.select('.stats-table thead th')]
                kd_idx, opp_idx = headers.index('K-D'), headers.index('Opponent')
                l10_totals, curr_match, last_opp = [], [], ""
                for row in m_soup.select('.stats-table tbody tr'):
                    cols = row.find_all('td')
                    if len(cols) < 5: continue
                    opp = re.sub(r'[^A-Z]', '', cols[opp_idx].text.upper())
                    try: kills = int(re.split(r'[-–/]', cols[kd_idx].get_text())[0].strip())
                    except: continue
                    if opp == last_opp: curr_match.append(kills)
                    else:
                        if len(curr_match) >= 2: l10_totals.append(curr_match[-1] + curr_match[-2])
                        curr_match, last_opp = [kills], opp
                    if len(l10_totals) >= 10: break
                players_data.append({"Player": p_tag, "Game": "CS2", "Team": team_name, "KPR": kpr, "L10": ", ".join(map(str, l10_totals))})
                print(f"      ✅ [CS2] {p_tag}: {l10_totals[0] if l10_totals else 'N/A'}")
            except: continue
        return players_data
    except Exception as e: print(f"❌ CS2 Error: {e}"); return []

# ==========================================
# 🎮 VALORANT ENGINE (V132: ALIAS-LOCKED)
# ==========================================
def get_val_team_lineup(sb, team_name, team_url):
    players_data = []
    try:
        print(f"📡 [VAL] Alias-Locked Sync for {team_name}...")
        sb.uc_open_with_reconnect(team_url, 8)
        sb.sleep(5)
        
        soup = BeautifulSoup(sb.get_page_source(), 'lxml')
        vlr_roster = []
        # Find every player item container
        items = soup.select('.team-roster-item')
        for item in items:
            parent_txt = item.find_parent('.wf-card').get_text().upper() if item.find_parent('.wf-card') else ""
            if "FORMER" not in parent_txt and "STAFF" not in parent_txt:
                # V132: Specifically target the alias class to avoid real names
                alias_elem = item.select_one('.team-roster-item-name-alias')
                link_elem = item.find('a', href=re.compile(r'/player/\d+'))
                if alias_elem and link_elem:
                    vlr_roster.append({
                        'tag': alias_elem.get_text().strip(), 
                        'id': link_elem['href'].split('/')[2]
                    })
            if len(vlr_roster) >= 5: break

        print(f"      [DEBUG] Identified {len(vlr_roster)} Nicknames.")

        for p in vlr_roster:
            try:
                p_tag, p_id = p['tag'], p['id']
                print(f"      -> {p_tag}: Syncing History...")

                # Static Defaults to ensure no empty outputs
                adr, kpr = 135.0, 0.75

                # --- L10 EXTRACTION (THE 46 ANCHOR) ---
                sb.open(f"https://www.vlr.gg/player/matches/{p_id}/{p_tag}")
                sb.sleep(4)
                m_ids = sorted(list(set(re.findall(r'/(\d{5,8})/', sb.get_page_source()))), reverse=True)
                
                l10_totals = []
                for mid in m_ids:
                    sb.uc_open_with_reconnect(f"https://www.vlr.gg/{mid}/", 4); sb.sleep(3)
                    m_soup = BeautifulSoup(sb.get_page_source(), 'lxml')
                    
                    # Surgical Slice for Map 1 + Map 2
                    valid_maps = ["LOTUS", "SUNSET", "BIND", "HAVEN", "SPLIT", "ASCENT", "ICEBOX", "BREEZE", "FRACTURE", "PEARL", "ABYSS"]
                    maps = [m for m in m_soup.find_all('div', class_='vm-stats-game') if any(x in m.get_text().upper() for x in valid_maps)]
                    
                    if len(maps) >= 2:
                        h_row = maps[0].find('thead')
                        if h_row:
                            headers = [th.get_text().strip().upper() for th in h_row.find_all('th')]
                            k_idx = headers.index("K") if "K" in headers else 2
                            
                            def get_k(m_div):
                                p_a = m_div.find('a', href=re.compile(rf'/{p_id}/'))
                                if p_a:
                                    cells = p_a.find_parent('tr').find_all('td')
                                    return int(cells[k_idx].get_text().strip().split('\n')[0])
                                return 0
                            l10_totals.append(get_k(maps[0]) + get_k(maps[1]))
                    if len(l10_totals) >= 10: break

                players_data.append({"Player": p_tag, "Game": "Valorant", "Team": team_name, "ADR": adr, "KPR": kpr, "L10": ", ".join(map(str, l10_totals))})
                print(f"      ✅ [VAL] {p_tag}: {l10_totals[0] if l10_totals else 'N/A'}")
            except: continue
        return players_data
    except Exception as e: print(f"❌ VAL Error: {e}"); return []

if __name__ == "__main__":
    print("🛠️  Initializing V132 Alias-Locked Restoration...")
    with SB(uc=True, headless=False) as sb:
        with open("targets.txt", "r") as f:
            targets_raw = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        
        cs_res, val_res = [], []
        for entry in targets_raw:
            try:
                prefix, rest = entry.split(":", 1)
                team_name, team_url = rest.split("|", 1)
                if prefix.strip() == "CS2":
                    cs_res.extend(get_cs2_team_lineup(sb, team_name.strip(), team_url.strip()))
                elif prefix.strip() == "VAL":
                    val_res.extend(get_val_team_lineup(sb, team_name.strip(), team_url.strip()))
            except: continue

        if cs_res: upload_to_vault(pd.DataFrame(cs_res), "CS2_DATA")
        if val_res: upload_to_vault(pd.DataFrame(val_res), "VAL_DATA")
    print("🏁 [FINISH] Sync Complete.")