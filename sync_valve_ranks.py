import requests
from bs4 import BeautifulSoup
import json
import datetime
import os

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
        "The MongolZ": "TH", "FURIA": "FUR", "MOUZ": "MOUZ", "PARIVISION": "PARI",
        "Aurora": "AUR", "G2 Esports": "G2", "9z Team": "9Z", "3DMAX": "3DMAX",
        "paiN Gaming": "PAIN", "B8": "B8", "BetBoom Team": "BB", "Legacy": "LEG",
        "Monte": "MONTE", "HEROIC": "HEROIC", "BIG": "BIG", "GamerLegion": "GL",
        "Alliance": "ALL", "MIBR": "MIBR", "FOKUS": "FOKUS", "FaZe Clan": "FAZE",
        "Virtus.pro": "VP", "Cloud9": "CLD9",
        
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
        "Party Astronauts": "PA", "Boss": "BOSS", "Limitless": "LMT", "LFO": "LFO"
    }

    # Clean the input name of common noise before checking or slicing
    name_clean = full_name.strip()
    
    # Check the Hard Map first
    if name_clean in HARD_MAP:
        return HARD_MAP[name_clean]

    # --- 2. HEURISTIC SLICER (For Ranks #101 - #250) ---
    # Remove "Team", "Esports", "Gaming", and "Academy" for processing
    process_name = name_clean.upper()
    noise = ["TEAM", "ESPORTS", "GAMING", "CLUB", "PRO", "ORGANIZATION"]
    for word in noise:
        process_name = process_name.replace(word, "")
    
    process_name = process_name.strip()
    words = process_name.split()

    # Case A: Academy Teams (e.g., "MOUZ NXT" or "NAVI Junior")
    if "ACADEMY" in process_name or "JUNIOR" in process_name or "NXT" in process_name or "YOUTH" in process_name:
        # Take the parent team initials + the first letter of the academy tag
        if len(words) >= 2:
            return f"{words[0][:3]}{words[-1][0]}"

    # Case B: Multi-word names (e.g., "Into The Breach")
    if len(words) >= 3:
        return "".join([w[0] for w in words])[:4]
    
    # Case C: Two-word names (e.g., "Lynn Vision")
    if len(words) == 2:
        return f"{words[0][0]}{words[1][:3]}"

    # Case D: Single word (e.g., "Metizport")
    return process_name[:4]

def get_rankings():
    # 1. Target today's date for the BO3 Oracle
    today = datetime.date.today().strftime('%Y-%m-%d')
    url = f"https://bo3.gg/teams/valve-rankings/world?ranking_date={today}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 2. Scrape Team Name and Rank (Assumes standard BO3 table structure)
        # Note: In 2026, we use specific class selectors for the 'Valve Standing' view.
        teams = {}
        rows = soup.select('div.ranking-team-row')[:50] # Top 50 focus
        
        for row in rows:
            rank = int(row.select_one('.rank-number').text.strip())
            full_name = row.select_one('.team-name').text.strip()
            
            # Generate a consistent key (Abbr)
            # Use a map for common teams, otherwise use first 4 letters uppercase
            abbr_map = {"Natus Vincere": "NAVI", "Team Vitality": "VIT", "FaZe Clan": "FAZE", "Team Spirit": "SPIRIT"}
            abbr = abbr_map.get(full_name, full_name[:4].upper().replace(" ", ""))
            
            teams[abbr] = {"full": full_name, "rank": rank}

        # 3. Save to Manifest Format
        with open("cs2_manifest.json", "w") as f:
            json.dump(teams, f, indent=4)
        print(f"✅ Sync Complete: {len(teams)} teams mapped for {today}.")
        
    except Exception as e:
        print(f"❌ Sync Failed: {e}")

if __name__ == "__main__":
    get_rankings()
