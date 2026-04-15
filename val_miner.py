import pandas as pd
from seleniumbase import Driver
from bs4 import BeautifulSoup
import time
import os
import random
import re

# ==========================================
# 📋 CONFIG & CONNECTION
# ==========================================

def load_val_watchlist():
    # Use a separate file for Valorant targets to avoid confusion
    if not os.path.exists("val_targets.txt"):
        print("❌ val_targets.txt not found!")
        return []
    with open("val_targets.txt", "r") as f:
        return [line.strip() for line in f if line.strip()]

def load_page_safely(driver, url):
    try:
        driver.uc_open_with_reconnect(url, reconnect_time=3.0)
        driver.uc_click("body")
        time.sleep(random.uniform(4, 6)) # Valorant sites require slower pacing
        return True
    except: return False

# ==========================================
# 🎯 VALORANT EXTRACTION ENGINE
# ==========================================

def get_val_player_stats(driver, player_url, player_name):
    print(f"   ▶ Mining Valorant Profile: {player_name}...")
    
    # Defaults
    base_kpr, l10_kills = 0.70, []
    top_agents = "Unknown"
    
    # --- PART A: Agent & Base Stats ---
    # We target the 'stats' tab on VLR
    if load_page_safely(driver, player_url + "/?timespan=90d"):
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        # 1. Pull KPR (Kills Per Round)
        # VLR typically lists KPR in the main stats table
        stats_cells = soup.find_all('td')
        for i, cell in enumerate(stats_cells):
            if "KPR" in cell.text:
                try: base_kpr = float(stats_cells[i+1].text.strip())
                except: pass
                break

        # 2. Pull Top Agents
        agent_imgs = soup.select('img[src*="/agents/"]')
        agents = [img['title'] for img in agent_imgs[:3] if img.get('title')]
        top_agents = ", ".join(agents) if agents else "Duelist/Flex"

    # --- PART B: Match History (L10 Grouping) ---
    # We target the 'matches' tab
    matches_url = player_url.replace("/player/", "/player/matches/")
    if load_page_safely(driver, matches_url):
        try:
            soup = BeautifulSoup(driver.page_source, 'lxml')
            match_rows = soup.select('tr')
            
            all_maps = []
            for row in match_rows[:40]: # Scan enough to find 10 matches
                tds = row.find_all('td')
                if len(tds) >= 4:
                    # Grouping by Opponent and Date
                    opp = tds[1].text.strip()
                    date = tds[3].text.strip()
                    # Kills are often found in a 'stats' link or specific cell
                    kill_text = row.find('span', class_='stats-kill') # VLR specific class
                    if kill_text:
                        k = int(kill_text.text.strip())
                        all_maps.append({'k': k, 'key': f"{opp}_{date}"})

            # Match Grouping Engine (Same logic as CS2)
            match_groups = []
            if all_maps:
                curr_key, curr_grp = all_maps[0]['key'], [all_maps[0]['k']]
                for i in range(1, len(all_maps)):
                    if all_maps[i]['key'] == curr_key: curr_grp.append(all_maps[i]['k'])
                    else:
                        match_groups.append(curr_grp)
                        curr_key, curr_grp = all_maps[i]['key'], [all_maps[i]['k']]
                match_groups.append(curr_grp)

            for grp in match_groups[:10]:
                l10_kills.append(str(sum(grp[:2]))) # VLR lists Map 1 first
        except: pass

    return {"BaseKPR": base_kpr, "L10": ", ".join(l10_kills), "Agents": top_agents}

# ==========================================
# 🚀 EXECUTION
# ==========================================

def build_val_vault():
    teams = load_val_watchlist()
    driver = Driver(uc_cdp=True, incognito=True, headless=False)
    
    try:
        all_data = []
        for team in teams:
            print(f"\n🕵️‍♂️ Searching VLR for: {team}...")
            # We search for the team on VLR
            if not load_page_safely(driver, f"https://www.vlr.gg/search/?q={team}"): continue
            
            soup = BeautifulSoup(driver.page_source, 'lxml')
            team_link = soup.find('a', href=lambda h: h and "/team/" in h)
            if not team_link: continue
            
            # Go to team page
            if not load_page_safely(driver, f"https://www.vlr.gg{team_link['href']}"): continue
            
            # Grab Player Links
            p_soup = BeautifulSoup(driver.page_source, 'lxml')
            p_links = p_soup.select('a[href*="/player/"]')
            
            # Filter unique players (VLR lists them multiple times)
            unique_p = []
            seen = set()
            for link in p_links:
                p_id = link['href'].split('/')[2]
                if p_id not in seen and len(unique_p) < 5:
                    seen.add(p_id)
                    unique_p.append(f"https://www.vlr.gg{link['href']}")

            for p_url in unique_p:
                p_name = p_url.split('/')[-1]
                stats = get_val_player_stats(driver, p_url, p_name)
                
                all_data.append({
                    "Player": p_name, "Team": team, "Game": "Valorant",
                    "BaseKPR": stats["BaseKPR"], "L10": stats["L10"],
                    "Agents": stats["Agents"], "Rank": "Tier 1", "ExpectedMaps": "TBD"
                })
                print(f"      ✅ Val Entry Created: {p_name}")

        # Save to a common CSV so app.py can see both
        existing_df = pd.read_csv("daily_stats.csv") if os.path.exists("daily_stats.csv") else pd.DataFrame()
        new_df = pd.DataFrame(all_data)
        combined = pd.concat([existing_df, new_df], ignore_index=True).drop_duplicates(subset=['Player'], keep='last')
        combined.to_csv("daily_stats.csv", index=False)
        
    finally: driver.quit()

if __name__ == "__main__":
    build_val_vault()