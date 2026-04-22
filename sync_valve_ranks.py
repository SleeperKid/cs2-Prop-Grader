import requests
from bs4 import BeautifulSoup
import json
import datetime
import os

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