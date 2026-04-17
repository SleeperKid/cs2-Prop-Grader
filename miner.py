import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
import pandas as pd
import numpy as np
import re
import os
from seleniumbase import SB
from bs4 import BeautifulSoup

# ==========================================
# 🛡️ THE UPLOADER ENGINE
# ==========================================
def upload_to_vault(df, worksheet_name):
    """Pushes local scraped data directly to Google Sheets"""
    if df.empty:
        print(f"⚠️ [CLOUD] No data found to upload for {worksheet_name}.")
        return

    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        # Ensure service_account.json is in your project folder
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
        client = gspread.authorize(creds)
        
        # Open 'PropVault' and the specific worksheet tab
        spreadsheet = client.open("PropVault") 
        worksheet = spreadsheet.worksheet(worksheet_name)
        
        worksheet.clear()
        set_with_dataframe(worksheet, df)
        print(f"🚀 [CLOUD SUCCESS] {len(df)} players synced to {worksheet_name}!")
    except Exception as e:
        print(f"❌ [CLOUD ERROR] Failed to upload to {worksheet_name}: {e}")

# ==========================================
# 🎮 VALORANT ENGINE (V36 RE-LOCKED)
# ==========================================
def get_val_stats(sb, p_id, p_tag, p_url):
    try:
        sb.uc_open_with_reconnect(f"{p_url}/?timespan=all", reconnect_time=4)
        sb.sleep(5)
        soup = BeautifulSoup(sb.get_page_source(), 'lxml')
        all_html = soup.get_text() + " " + str(soup.find_all(True))
        
        # Team & Agents
        base_team = "Free Agent"
        team_anchor = soup.find('a', href=re.compile(r'/team/'))
        if team_anchor:
            raw_team = team_anchor.get_text(separator=" ").strip()
            base_team = re.split(r'joined|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec', raw_team)[0].strip()

        known_agents = ["Neon", "Jett", "Raze", "Sova", "Skye", "Fade", "Breach", "Omen", "Viper", "Cypher", "Killjoy", "Tejo"]
        agent_found = [a for a in known_agents if re.search(a, all_html, re.IGNORECASE)]
        top_agents = ", ".join(agent_found[:3])

        # KPR Extraction
        kpr = 0.80
        table = soup.find('table', class_='wf-table')
        if table:
            headers = [th.text.strip().upper() for th in table.find('thead').find_all('th')]
            if "KPR" in headers:
                kpr_idx = headers.index("KPR")
                for row in table.find('tbody').find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) > kpr_idx:
                        try:
                            val = float(cols[kpr_idx].text.strip())
                            if val > 0.6: kpr = val; break
                        except: continue

        # Match History (Map 1+2 Fix)
        sb.uc_open_with_reconnect(f"https://www.vlr.gg/player/matches/{p_id}/{p_tag}", reconnect_time=4)
        sb.sleep(4)
        match_links = [f"https://www.vlr.gg{a['href']}" for a in 
                       BeautifulSoup(sb.get_page_source(), 'lxml').select('a.wf-card.m-item')][:12]
        
        l10_list = []
        for m_link in match_links:
            if len(l10_list) >= 10: break
            sb.uc_open_with_reconnect(m_link, reconnect_time=4)
            m_soup = BeautifulSoup(sb.get_page_source(), 'lxml')
            
            map_containers = []
            for container in m_soup.find_all('div', class_='vm-stats-game'):
                txt = container.get_text().upper()
                if any(x in txt for x in ["OVERALL", "SERIES", "SUMMARY"]): continue
                if container.find('div', class_='map'): map_containers.append(container)

            def extract_k(cont):
                for r in cont.find_all('tr'):
                    if p_id in str(r) or p_tag.lower() in r.text.lower():
                        cell = r.find('td', class_='mod-vlr-kills')
                        return int(re.split(r'[\n-]', cell.text.strip())[0].strip()) if cell else 0
                return 0

            if len(map_containers) >= 2:
                l10_list.append(extract_k(map_containers[0]) + extract_k(map_containers[1]))

        expected = kpr * 26
        avg_actual = np.mean(l10_list) if l10_list else 0
        edge = round(((avg_actual - expected) / expected * 100), 1) if expected > 0 else 0

        return {"Player": p_tag, "Game": "Valorant", "Team": base_team, "Agents": top_agents, 
                "KPR": kpr, "L10": ", ".join(map(str, l10_list)), "Edge %": edge}
    except Exception as e:
        print(f"      [!] VAL Error: {e}")
        return None

# ==========================================
# 🎮 CS2 ENGINE (V35 VERIFIED)
# ==========================================
def get_cs2_stats(sb, p_id, p_tag, p_url):
    try:
        sb.uc_open_with_reconnect(p_url, reconnect_time=4)
        sb.sleep(4)
        soup = BeautifulSoup(sb.get_page_source(), 'lxml')
        
        # --- NEW: TEAM EXTRACTION ---
        base_team = "Free Agent"
        team_link = soup.find('a', href=re.compile(r'/team/'))
        if team_link and "player" not in team_link.get('href'):
            base_team = team_link.get_text().strip()
        
        kpr = 0.82
        stat_label = soup.find(string=re.compile("Kills per round"))
        if stat_label:
            val_elem = stat_label.find_parent().find_next(['b', 'span', 'div'])
            if val_elem: 
                m = re.search(r"\d+\.\d+", val_elem.text)
                if m: kpr = float(m.group())

        # Match History logic remains the same...
        matches_url = f"https://www.hltv.org/stats/players/matches/{p_id}/{p_tag.lower()}"
        sb.uc_open_with_reconnect(matches_url, reconnect_time=4)
        sb.sleep(6)
        m_soup = BeautifulSoup(sb.get_page_source(), 'lxml')
        rows = m_soup.select('.stats-table tbody tr')
        match_groups = {}
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 5: continue
            date, opp_raw = cols[0].text.strip(), cols[2].text.strip()
            opp_clean = re.sub(r'\s*\(\d+\)', '', opp_raw.replace("vs ", "")).strip()
            kills = int(cols[4].text.strip().split('-')[0].strip())
            match_key = f"{date}_{opp_clean}"
            if match_key not in match_groups: match_groups[match_key] = []
            match_groups[match_key].append(kills)

        l10_list = []
        for m_key in match_groups:
            k_list = match_groups[m_key]
            if len(k_list) >= 2: l10_list.append(k_list[-1] + k_list[-2])
            if len(l10_list) >= 10: break

        return {"Player": p_tag, "Game": "CS2", "Team": base_team, "KPR": kpr, 
                "L10": ", ".join(map(str, l10_list)), "Edge %": 0}
    except Exception as e:
        print(f"      [!] CS2 Error: {e}"); return None

# ==========================================
# 🚀 MASTER EXECUTION (V38 COMPLETE)
# ==========================================
def run_master_miner():
    print("🚀 Launching V38 Master Miner: Cloud-Linked Mode")
    with SB(uc=True, headless=False, incognito=True) as sb:
        try:
            with open("targets.txt", "r") as f:
                raw_targets = [line.strip() for line in f if line.strip()]
            targets = sorted(raw_targets, key=lambda x: x.split(":")[0], reverse=True)
        except Exception as e:
            print(f"❌ Target Error: {e}"); return

        val_results, cs_results = [], []
        last_prefix = None

        for entry in targets:
            prefix, data = entry.split(": ")
            if last_prefix and prefix != last_prefix:
                print(f"🛑 Domain Cooldown ({last_prefix} -> {prefix})..."); sb.sleep(10)

            p_id, p_tag, p_url = data.split("|")
            print(f"📡 Mining {p_tag}...")
            
            res = get_val_stats(sb, p_id, p_tag, p_url) if prefix == "VAL" else get_cs2_stats(sb, p_id, p_tag, p_url)
            if res:
                val_results.append(res) if prefix == "VAL" else cs_results.append(res)
            last_prefix = prefix

        # Final Sync
        print("\n☁️  Initiating Cloud Vault Synchronization...")
        if val_results:
            df_v = pd.DataFrame(val_results)
            df_v.to_csv("val_daily_stats.csv", index=False)
            upload_to_vault(df_v, "VAL_DATA")
        if cs_results:
            df_c = pd.DataFrame(cs_results)
            df_c.to_csv("cs_daily_stats.csv", index=False)
            upload_to_vault(df_c, "CS2_DATA")
        
        print("\n🏆 Session Complete. Data is Live!")

if __name__ == "__main__":
    run_master_miner()