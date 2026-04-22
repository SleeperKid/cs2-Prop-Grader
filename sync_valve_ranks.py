import requests
from bs4 import BeautifulSoup
import json
import datetime
import os
import sub
import subprocess
import asyncio
from playwright.async_api import async_playwright


def generate_standard_tag(full_name):
    """
    Standardizes CS2 Team Names into 2-5 letter abbreviations (Tags).
    Prioritizes Hard-Coded Top 100 Mappings, then falls back to Heuristic Logic.
    """
    # --- 1. HARD-CODED TOP 100 ORACLE ---
    HARD_MAP = {
        # Tier 1 & Elite
        "Team Vitality": "VIT", "Natus Vincere": "NAVI", "Team Falcons": "FAL",
        "FUT Esports": "FUT", "Team Spirit": "SPIRIT", "Astralis": "ASTR",
        "The MongolZ": "MNGZ", "FURIA": "FUR", "MOUZ": "MOUZ", "PARIVISION": "PARI",
        "Aurora": "AUR", "G2 Esports": "G2", "9z Team": "9Z", "3DMAX": "3DMAX",
        "paiN Gaming": "PAIN", "B8": "B8", "BetBoom Team": "BB", "Legacy": "LEG",
        "Monte": "MONTE", "HEROIC": "HEROIC", "BIG": "BIG", "GamerLegion": "GL",
        "Alliance": "ALL", "MIBR": "MIBR", "FOKUS": "FOKUS", "FaZe Clan": "FAZE",
        "Virtus.pro": "VP", "Cloud9": "CLD9", "100 Thieves": "100T",
        
        # Tier 2 & High Frequency
        "M80": "M80", "SINNERS": "SIN", "EYEBALLERS": "EYE", "NRG": "NRG",
        "Nemesis": "NEM", "Ninjas in Pyjamas": "NIP", "K27": "K27", 
        "Gaimin Gladiators": "GG", "Nemiga": "NEMIG", "TYLOO": "TYLOO",
        "Fnatic": "FNC", "RED Canids": "RED", "Imperial": "IMP", "Sashi": "SAS",
        "Endpoint": "ENDP", "Metizport": "METZ", "KOI": "KOI", "ENCE": "ENCE",
        "SAW": "SAW", "9INE": "9INE", "ECSTATIC": "ECST", "Passion UA": "PANI",
        "FlyQuest": "FLYQ", "Sangal": "SANG", "AMKAL": "AMK", "Rare Atom": "RARE",
        "Zero Tenacity": "00T", "BLEED": "BLD", "JANO": "JANO", "Rhyno": "RHY",
        "Permitta": "PER", "BC.Game": "BCG", "Illuminar": "ILL", "Revenant": "REV",
        "Enterprise": "ENT", "UNiTY": "UNI", "Dynamo Eclot": "ECL", "Oddik": "ODK",
        "Fluxo": "FLX", "Team Solid": "SOL", "Sharks": "SHA", "Case": "CASE",
        "Dust2 Brasil": "D2B", "Bestia": "BST", "Wildcard": "WLD", "Nouns": "NOUN",
        "Party Astronauts": "PA", "Boss": "BOSS", "Limitless": "LMT", "LFO": "LFO", 
        "Team Liquid": "TL"
    }

    name_clean = full_name.strip()
    if name_clean in HARD_MAP: return HARD_MAP[name_clean]
    upper_name = name_clean.upper().replace("TEAM", "").replace("ESPORTS", "").replace("GAMING", "").strip()
    if upper_name and upper_name[0].isdigit(): return upper_name.replace(" ", "")[:4]
    words = upper_name.split()
    if len(words) >= 2: return "".join([w[0] for w in words])[:4]
    return upper_name[:4]

# --- 🚀 CLOUD BRIDGE ---
def push_to_github():
    try:
        print("🚀 [GIT] Syncing to Cloud...")
        # Pull first to avoid 'rejected' errors
        subprocess.run(["git", "pull", "--rebase"], check=True)
        subprocess.run(["git", "add", "cs2_manifest.json"], check=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(["git", "commit", "-m", f"🛰️ AUTO-SYNC: {timestamp}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ [GIT] Push successful.")
    except Exception as e:
        print(f"⚠️ [GIT] Push failed or no changes: {e}")

# --- 📡 THE ORACLE ---
async def run_sync():
    today = datetime.date.today().strftime('%Y-%m-%d')
    url = f"https://bo3.gg/teams/valve-rankings/world?ranking_date={today}"
    
    print(f"📡 [SYNC] Opening Sovereign Engine for {today}...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 1000}
        )
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="load", timeout=60000)
            await page.wait_for_selector('a[href*="/teams/"]', timeout=30000)

            print("🖱️ Commencing Deep-Scroll (Top 250)...")
            for i in range(1, 35):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(0.7)

            raw_teams = await page.evaluate("""
                () => {
                    const noise = ['TEAMS', 'PLAYERS', 'MATCHES', 'COMPARE', 'WORLDWIDE', 'EUROPE', 'AMERICAS', 'ASIA', 'OCEANIA', 'EARNINGS', 'ENG'];
                    const container = document.querySelector('.ranking-list') || document.body;
                    const links = Array.from(container.querySelectorAll('a[href*="/teams/"]'));
                    return links.map(link => {
                        const text = link.innerText || "";
                        const textLines = text.split('\\n');
                        return textLines[0] ? textLines[0].trim() : "";
                    }).filter(name => name.length > 2 && !noise.includes(name.toUpperCase()));
                }
            """)
            
            manifest_data = {}
            seen_teams = set()
            rank_counter = 1
            for name in raw_teams:
                if name not in seen_teams:
                    tag = generate_standard_tag(name)
                    manifest_data[tag] = {"full": name, "rank": rank_counter}
                    seen_teams.add(name)
                    rank_counter += 1
                if rank_counter > 250: break 
            
            # Final Write
            with open("cs2_manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=4)
            
            print(f"✅ SUCCESS: {len(manifest_data)} teams written.")
            
            # Push to GitHub so your Streamlit app sees it!
            push_to_github()

        except Exception as e:
            print(f"❌ ERROR: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_sync())