import pandas as pd
from seleniumbase import Driver
from bs4 import BeautifulSoup
import time
import os
import subprocess
import vlrdevapi as vlr

# ==========================================
# 📋 CONFIGURATION & UTILS
# ==========================================

def load_watchlist():
    if not os.path.exists("targets.txt"):
        print("❌ targets.txt not found!")
        return []
    with open("targets.txt", "r") as file:
        lines = [line.strip() for line in file if line.strip()]
        return list(dict.fromkeys(lines)) 

def load_page_safely(driver, url, wait_element=None):
    try:
        driver.uc_open(url)
        time.sleep(2) # Stabilization delay
        try:
            driver.uc_gui_click_captcha() 
        except:
            pass 
        if wait_element:
            time.sleep(3) 
        if "Just a moment" in driver.title or "Cloudflare" in driver.title:
            print("      [!] Cloudflare challenge detected. Waiting 10s...")
            time.sleep(10)
        return True
    except Exception as e:
        print(f"      [!] Connection error: {e}")
        return False

def push_to_cloud():
    print("\n☁️ PUSHING DATA TO THE CLOUD...")
    try:
        subprocess.run('git add daily_stats.csv', shell=True, check=True)
        subprocess.run('git commit -m "🤖 Daily stats update" || echo "No changes to commit"', shell=True, check=True)
        subprocess.run('git push origin main', shell=True, check=True)
        print("✅ LIVE WEBSITE SUCCESSFULLY UPDATED!")
    except Exception as e:
        print(f"❌ Failed to push to GitHub: {e}")

# ==========================================
# 🔫 VALORANT MINING ENGINE
# ==========================================

def get_valorant_stats(team_id, team_name):
    print(f"   ▶ Syncing Valorant Team: {team_name}...")
    team_data = []
    try:
        roster = vlr.teams.roster(team_id=team_id)
        for player in roster:
            p_name = getattr(player, 'handle', getattr(player, 'ign', 'Unknown'))
            p_id = getattr(player, 'player_id', getattr(player, 'id', None))
            if not p_id: continue
                
            print(f"      - Processing {p_name}...")
            recent_matches = vlr.players.matches(player_id=p_id, limit=10)
            l10_kills = []
            base_kpr = 0.75
            
            profile = vlr.players.profile(player_id=p_id)
            if hasattr(profile, 'stats') and hasattr(profile.stats, 'kpr'):
                base_kpr = float(profile.stats.kpr)
            
            for match in recent_matches:
                try:
                    series_data = vlr.series.per_map_statistics(series_id=match.id)
                    if not series_data or len(series_data.maps) < 2: continue
                    m1_k, m2_k = 0, 0
                    for p_stat in series_data.maps[0].players:
                        if p_stat.player_id == p_id: m1_k = p_stat.kills; break
                    for p_stat in series_data.maps[1].players:
                        if p_stat.player_id == p_id: m2_k = p_stat.kills; break
                    if (m1_k + m2_k) > 0: l10_kills.append(str(m1_k + m2_k))
                except: continue
            
            if l10_kills:
                team_data.append({
                    "Player": p_name, "Game": "Valorant", "Team": team_name, 
                    "BaseKPR": base_kpr, "L10": ", ".join(l10_kills), "ExpectedMaps": "TBD"
                })
                print(f"      ✅ Saved: {p_name}")
    except Exception as e:
        print(f"      [!] Valorant API Error: {e}")
    return team_data

# ==========================================
# 💣 CS2 MINING ENGINE
# ==========================================

def get_player_stats(driver, player_url, player_name):
    print(f"   ▶ Syncing CS2 Player: {player_name}...")
    url_parts = player_url.split('/')
    try: p_id, p_slug = url_parts[-2], url_parts[-1]
    except: return 0.75, "" 

    base_kpr, l10_kills = 0.75, []
    if load_page_safely(driver, f"https://www.hltv.org/stats/players/{p_id}/{p_slug}"):
        soup = BeautifulSoup(driver.page_source, 'lxml')
        for row in soup.find_all('div', class_='stats-row'):
            if "Kills / round" in row.text:
                try: base_kpr = float(row.find_all('span')[-1].text.strip())
                except: pass
                break

    if load_page_safely(driver, f"https://www.hltv.org/stats/players/matches/{p_id}/{p_slug}", wait_element="table"):
        try:
            soup = BeautifulSoup(driver.page_source, 'lxml')
            table = soup.find('table', class_=lambda c: c and 'stats-table' in c)
            if table:
                rows = table.find('tbody').find_all('tr')
                all_maps = []
                for row in rows:
                    tds = row.find_all('td')
                    if len(tds) < 5: continue
                    kd = ""
                    for td in tds:
                        if "-" in td.text and any(c.isdigit() for c in td.text): kd = td.text; break
                    if not kd: continue
                    m_link = tds[4].find('a', href=True) or tds[2].find('a', href=True)
                    s_id = m_link['href'].split('/')[-2] if m_link else "0"
                    all_maps.append({'k': int(kd.split('-')[0]), 'series': s_id})

                grps, curr, tmp = [], None, []
                for m in all_maps:
                    if m['series'] != curr:
                        if tmp: grps.append(tmp)
                        tmp, curr = [m['k']], m['series']
                    else: tmp.append(m['k'])
                if tmp: grps.append(tmp)
                for g in grps[:10]: l10_kills.append(str(sum(g[::-1][:2]))) 
        except: pass
    return base_kpr, ", ".join(l10_kills)

# ==========================================
# 🚀 EXECUTION ENGINE
# ==========================================

def build_daily_vault():
    targets = load_watchlist()
    if not targets: return
    cs2_t = [t.split(": ")[1] for t in targets if t.startswith("CS2:")]
    val_t = [t.split(": ")[1] for t in targets if t.startswith("VAL:")]
    all_data = []

    # --- VALORANT MINING ---
    if val_t:
        print("\n🔫 STARTING VALORANT SYNC...")
        for t in val_t:
            pts = t.split("|")
            if len(pts) == 2: all_data.extend(get_valorant_stats(pts[0].strip(), pts[1].strip()))

    # --- CS2 MINING ---
    if cs2_t:
        print("\n💣 STARTING CS2 SYNC...")
        for team in cs2_t:
            print(f"\n🕵️‍♂️ Targeting {team}...")
            driver = Driver(uc=True, headless=True) 
            time.sleep(3) 
            try:
                if load_page_safely(driver, f"https://www.hltv.org/search?query={team}"):
                    if "/team/" not in driver.current_url:
                        soup = BeautifulSoup(driver.page_source, 'lxml')
                        link = soup.find('a', href=lambda h: h and "/team/" in h)
                        if link: load_page_safely(driver, "https://www.hltv.org" + link['href'])
                    
                    tags = BeautifulSoup(driver.page_source, 'lxml').select('div.bodyshot-team.g-grid a.col-custom')
                    seen = set()
                    for tag in tags:
                        url = "https://www.hltv.org" + tag['href']
                        if url in seen: continue
                        seen.add(url)
                        name = tag.get('title', '').split("'")[-2] if "'" in tag.get('title', '') else tag['href'].split('/')[-1]
                        k, l10 = get_player_stats(driver, url, name)
                        if l10:
                            all_data.append({"Player": name, "Game": "CS2", "Team": team, "BaseKPR": k, "L10": l10, "ExpectedMaps": "TBD"})
                            print(f"      ✅ Saved: {name}")
            finally:
                driver.quit()
                time.sleep(2)

    # --- FINAL SAVE & UPLOAD ---
    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv("daily_stats.csv", index=False)
        print(f"\n✅ Saved {len(df)} players to Local Vault!")
        push_to_cloud()
    else:
        # Safeguard: Create an empty file with headers if no data found
        df = pd.DataFrame(columns=["Player", "Game", "Team", "BaseKPR", "L10", "ExpectedMaps"])
        df.to_csv("daily_stats.csv", index=False)
        print("\n⚠️ No data found. Created empty template to prevent App crash.")

if __name__ == "__main__":
    build_daily_vault()