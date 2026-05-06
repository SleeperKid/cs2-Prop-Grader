import streamlit as st
import json
import os
import re
import numpy as np
import pandas as pd
import gspread
import requests
from itertools import combinations
from groq import Groq
from tavily import TavilyClient

# --- 1. CORE SETUP & MONOLITH V41.2 STYLING ---
st.set_page_config(page_title="Iron Guard V42.2", layout="wide", page_icon="📡")

# Initialize Session State
if 'last_intel' not in st.session_state: st.session_state['last_intel'] = None
if 'auto_duel' not in st.session_state: st.session_state['auto_duel'] = 5.0
if 'p_rank' not in st.session_state: st.session_state['p_rank'] = 60
if 'o_rank' not in st.session_state: st.session_state['o_rank'] = 110
if 'sweep_results' not in st.session_state: st.session_state['sweep_results'] = {}

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=JetBrains+Mono:wght@500;800&display=swap');
    .stApp { background-color: #010204; color: #e0e0e0; }
    .sovereign-card {
        background: linear-gradient(135deg, #0d1117 0%, #1c2333 50%, #0d1117 100%);
        border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 30px; 
        margin-bottom: 25px; box-shadow: 0 40px 100px rgba(0, 0, 0, 1);
        position: relative; overflow: hidden;
    }
    .nuke-play-badge {
        background: linear-gradient(90deg, #FFD700, #FF8C00); color: black;
        padding: 6px 15px; border-radius: 8px; font-family: 'Inter';
        font-size: 14px; font-weight: 900; display: inline-block; margin-bottom: 15px;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.4);
    }
    .grade-display { 
        font-family: 'Inter', sans-serif; font-weight: 900; letter-spacing: -30px; 
        line-height: 1; margin: 0; color: rgba(255, 255, 255, 0.03); 
        position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
        z-index: 0; pointer-events: none;
    }
    .card-content { position: relative; z-index: 1; text-align: left; }
    .player-name { font-family: 'Inter', sans-serif; font-weight: 900; text-transform: uppercase; color: white; margin-bottom: 5px; }
    .match-header { font-family: 'JetBrains Mono'; color: #FFD700; margin-bottom: 20px; font-weight: 800; font-size: 14px; text-transform: uppercase; }
    .decision-line { font-family: 'JetBrains Mono', monospace; font-weight: 800; text-transform: uppercase; margin-top: 15px; }
    .stat-val { color: white; font-weight: 900; margin-bottom: 15px; }
    .stat-lbl { font-size: 10px; color: rgba(255,255,255,0.4); text-transform: uppercase; margin-bottom: 5px; letter-spacing: 1px; }
    .metric-grid { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; margin-top: 10px; margin-bottom: 15px;}
    .metric-card {
        flex: 1 1 18%; background-color: #12161f; border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px; padding: 15px 10px; text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }
    .metric-card-lbl { font-size: 9px; color: rgba(255,255,255,0.5); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
    .metric-card-val { font-size: 18px; font-weight: 900; color: white; font-family: 'JetBrains Mono', monospace; }
    .ai-badge { 
        background: rgba(255, 69, 0, 0.1); color: #ff4500; font-size: 9px; font-weight: bold;
        border: 1px solid #ff4500; padding: 2px 5px; border-radius: 4px; margin-left: 6px; vertical-align: middle;
    }
    .vol-nerf-badge {
        background: rgba(255, 68, 68, 0.1); color: #ff4444; font-size: 10px; font-weight: bold;
        border: 1px solid #ff4444; padding: 2px 6px; border-radius: 4px; margin-left: 6px; vertical-align: middle; font-family: 'JetBrains Mono';
    }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { font-family: 'JetBrains Mono'; font-weight: 800; font-size: 16px; padding: 10px 20px; }
</style>
""", unsafe_allow_html=True)

try:
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    tavily_client = TavilyClient(api_key=st.secrets["TAVILY_API_KEY"])
except: st.error("📡 API ERROR: Check Secrets."); st.stop()

# --- HELPER FUNCTIONS ---
def load_live_ranks(game):
    filename = "val_manifest.json" if game == "VALORANT" else "cs2_manifest.json"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def load_codex():
    if os.path.exists("player_codex.json"):
        with open("player_codex.json", "r") as f: return json.load(f)
    return {"CS2_PLAYERS": {}, "VAL_PLAYERS": {}}

def safe_float(v, d=0.0):
    try: return float(str(v).replace('%', '').strip()) if v else d
    except: return d

def get_fuzzy_rank(team_str, manifest, default_rank):
    if not team_str or str(team_str).strip() == "": return default_rank
    ts = str(team_str).strip().lower().replace(" ", "")
    for tag, info in manifest.items():
        t_tag = tag.lower()
        t_full = info.get('full', '').lower().replace(" ", "")
        if ts == t_tag or ts == t_full or ts in t_full or t_full in ts:
            return safe_float(info.get("rank", default_rank))
    return default_rank

CS2_LIVE = load_live_ranks("CS2")
VAL_LIVE = load_live_ranks("VALORANT")
MANIFEST = { "VALORANT": VAL_LIVE, "CS2": CS2_LIVE }

# --- GLOBAL GAME ENGINES ---
CS2_ARCHETYPES = {"Anubis": 1.12, "Ancient": 1.12, "Dust 2": 1.15, "Inferno": 0.90, "Mirage": 1.05, "Nuke": 0.90, "Overpass": 1.00, "Vertigo": 1.08}
CS2_GRAVITY = {"Entry": 1.10, "Star": 1.08, "Primary AWP": 1.10, "Rifler": 1.00, "IGL": 0.88, "Anchor": 0.88}

VAL_GRAVITY = {"Duelist": 1.12, "Hybrid": 1.08, "Initiator": 1.00, "Controller": 0.88, "Sentinel": 0.80}

AGENT_ROLES = {
    "Jett": "Duelist", "Raze": "Duelist", "Neon": "Duelist", "Phoenix": "Duelist", "Reyna": "Duelist", "Yoru": "Duelist", "Iso": "Duelist",
    "Sova": "Initiator", "Fade": "Initiator", "Skye": "Initiator", "Breach": "Initiator", "Kayo": "Initiator", "Gekko": "Initiator", "Tejo": "Initiator",
    "Omen": "Controller", "Viper": "Controller", "Astra": "Controller", "Brimstone": "Controller", "Harbor": "Controller", "Clove": "Controller",
    "Killjoy": "Sentinel", "Cypher": "Sentinel", "Sage": "Sentinel", "Chamber": "Sentinel", "Deadlock": "Sentinel", "Vyse": "Sentinel"
}
VAL_AGENTS = list(AGENT_ROLES.keys())

def get_match_id(t1, t2):
    arr = sorted([str(t1).strip().upper(), str(t2).strip().upper()])
    return f"{arr[0]} vs {arr[1]}"

def lock_match_in_sheet(match_key):
    with st.spinner(f"Locking {match_key} in PropVault..."):
        try:
            google_creds = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(google_creds) 
            sh = gc.open_by_key("1xsxwRlnwF2MNkHwmSSRsOlKCV8H7W9iXemXyaTcIhlg")
            
            updates_val, updates_cs2 = [], []
            val_sheet, cs2_sheet = sh.worksheet("Valorant Master"), sh.worksheet("CS2 Master")
            
            val_data = val_sheet.get_all_values()
            val_headers = [h.strip().upper() for h in val_data[0]]
            cs2_data = cs2_sheet.get_all_values()
            cs2_headers = [h.strip().upper() for h in cs2_data[0]]
            
            v_col = val_headers.index("LOCKED") + 1 if "LOCKED" in val_headers else None
            c_col = cs2_headers.index("LOCKED") + 1 if "LOCKED" in cs2_headers else None

            for item in st.session_state['sweep_results'][match_key]:
                for card in item['data']:
                    if card.get('row_num'):
                        if item['type'] == "VALORANT" and v_col: 
                            updates_val.append(gspread.Cell(row=card['row_num'], col=v_col, value=True))
                        elif item['type'] == "CS2" and c_col: 
                            updates_cs2.append(gspread.Cell(row=card['row_num'], col=c_col, value=True))
            
            if updates_val: val_sheet.update_cells(updates_val)
            if updates_cs2: cs2_sheet.update_cells(updates_cs2)
            
            for item in st.session_state['sweep_results'][match_key]:
                for card in item['data']: card['Locked'] = True
            st.success(f"PropVault Updated for {match_key}")
        except Exception as e: 
            st.error(f"Failed to lock: {e}")

# --- 2. THE SOVEREIGN ENGINE ---
def apply_kill_economy_dampener(sweep_cards, r_total, theater="CS2"):
    team_groups = {}
    for card in sweep_cards:
        if card.get('prop_type', '').upper() == 'KILLS':
            team = card.get('full_team', 'Unknown')
            if team not in team_groups: team_groups[team] = []
            team_groups[team].append(card)

    # 🛡️ THE FIX: Differentiate ceilings based on the game meta
    if theater == "VALORANT":
        base_ceiling = 125.0
        base_rounds = 40.0
        ot_threshold = 48.0
    else:
        base_ceiling = 140.0
        base_rounds = 44.0
        ot_threshold = 50.0

    ceiling = 999.0 if r_total >= ot_threshold else (base_ceiling * (r_total / base_rounds))
    
    for team, players in team_groups.items():
        team_total = sum(p.get('proj', 0) for p in players)
        if team_total > ceiling:
            multiplier = ceiling / team_total
            for p in players:
                old_p = p['proj']
                p['proj'] = round(p['proj'] * multiplier, 1)
                p['vol_tax'] = round(old_p - p['proj'], 1)
                p['delta'] = round(p['proj'] - p['line'], 1)
        else:
            for p in players: p['vol_tax'] = 0.0

    team_overs = {}
    for card in sweep_cards:
        if card.get('prop_type', '').upper() == 'KILLS' and card.get('delta', 0) > 0:
            team = card.get('full_team', 'Unknown')
            if team not in team_overs: team_overs[team] = []
            team_overs[team].append(card)

    for team, players in team_overs.items():
        if len(players) > 1:
            players.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            for i, p in enumerate(players):
                tax = 0.5 + (i * 1.0) 
                p['proj'] = round(p['proj'] - tax, 1)
                p['vol_tax'] = round(p.get('vol_tax', 0) + tax, 1)
                p['delta'] = round(p['proj'] - p['line'], 1)

                if i > 0:
                    p['confidence'] = max(50.0, p['confidence'] - 10.0)
                    p['dampened'] = True

    for p in sweep_cards:
        abs_d = abs(p['delta'])
        is_consistent = abs(p.get('impact_stat', 0)) <= 8.0 if theater == "CS2" else p.get('impact_stat', 0) >= 74.0
        
        # 🛡️ THE FIX: Enforce the exact same Trap Line logic so the Dampener doesn't resurrect them
        if abs_d >= 10.0: 
            p['grade'], p['color'] = "C", "#FFFFFF" 
            p['rec'], p['rec_color'] = "🛑 TRAP LINE (DO NOT BET)", "#FF4444"
            p['confidence'] = min(p.get('confidence', 50), 45.0)
        elif 7.5 < abs_d < 10.0:
            p['grade'], p['color'] = "C", "#A0A0A0"
            p['rec'], p['rec_color'] = "🛑 NO BET (EDGE TOO HIGH)", "#FF8C00"
            p['confidence'] = min(p.get('confidence', 50), 55.0)
        elif 3.5 <= abs_d <= 7.5:
            if is_consistent:
                p['grade'], p['color'] = ("S+", "#FFD700") if abs_d >= 5.0 else ("S", "#FFC125")
                p['rec'], p['rec_color'] = "🟢 GREEN LIGHT (LOCK)", "#00FF7F"
            else:
                p['grade'], p['color'] = ("A+", "#00FF7F") if abs_d >= 5.0 else ("A", "#00ccff")
                p['rec'], p['rec_color'] = "🟡 NEUTRAL (SPRINKLE)", "#00ccff"
        elif 2.0 <= abs_d < 3.5:
            p['grade'], p['color'] = "A", "#00ccff"
            p['rec'], p['rec_color'] = "🟡 NEUTRAL (SPRINKLE)", "#00ccff"
        else: 
            p['grade'], p['color'] = "C", "#A0A0A0"
            p['rec'], p['rec_color'] = "🛑 NO BET (COIN FLIP)", "#A0A0A0"
            p['confidence'] = min(p.get('confidence', 50), 52.0)

        if p.get('dampened'):
            if p['grade'] in ['A+', 'A']: p['color'] = "#00CCFF"
            elif p['grade'] == 'C' and p['rec_color'] != "#FF4444": p['color'] = "#FFFFFF"
            
        p['pick'] = "OVER" if p['delta'] > 0 else "UNDER"
        p['is_nuke'] = (6.0 <= abs_d <= 8.5 and p.get('prob', 50) >= 85 and is_consistent)

    return sweep_cards

def apply_sovereign_math(data, p_name, u_line, full_p, full_o, targets, m_vals, heat, opp_dpr, r_total, impact_stat, theater, prop_type, hs_pcts, rank_respect_val=0.0, hr_override=None):
    raw_stat = safe_float(data.get('base_stat'), 150.0 if theater == "VALORANT" else 0.70)
    if theater == "CS2" and raw_stat > 3.0: raw_stat = (raw_stat / 100) if raw_stat < 150 else 0.72
    
    rank_gap = safe_float(data.get('o_rank', st.session_state['o_rank'])) - safe_float(data.get('p_rank', st.session_state['p_rank']))
    
    if rank_gap > 0 and rank_respect_val > 0:
        penalty = (rank_gap / 100) * rank_respect_val * 0.15
        raw_stat = raw_stat * (1 - penalty)

    hist_kills = [safe_float(k) for k in data.get('last_10_kills', []) if safe_float(k) > 0]

    if hr_override is not None and hr_override > 0: hr_val = hr_override
    elif prop_type == "Headshots": hr_val = 50.0
    else:
        if hist_kills:
            w = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
            w_h, t_w = 0.0, 0.0
            for i, k in enumerate(hist_kills):
                wt = w[i] if i < len(w) else 0.1
                t_w += wt
                if k > u_line: w_h += wt
            hr_val = (w_h / t_w) * 100
        else: hr_val = 50.0

    # 🧠 1. INDIVIDUAL EFFICIENCY MULTIPLIER
    match_mult = 1.08 if rank_gap >= 50 else 1.04 if rank_gap >= 15 else 0.92 if rank_gap <= -50 else 0.96 if rank_gap <= -15 else 1.0
    
    # 🧠 2. THE HOLY GRAIL VOLUME/PACE MODIFIER
    abs_gap = abs(rank_gap)
    if theater == "CS2":
        pace_mod = max(0.85, 1.08 - (abs_gap / 250.0)) # Softer penalty for CS2
    else:
        pace_mod = 1.15 if abs_gap <= 15 else 0.75 if abs_gap >= 45 else 1.0

    # 🧠 3. ROLE GRAVITY & IMPACT TAMING
    if theater == "CS2":
        role = data.get('role', 'Rifler')
        volume_mod = CS2_GRAVITY.get(role, 1.0) 
        hs_mod = 0.65 if role == "Primary AWP" else 1.0 
        impact_mult = 1.0 + (impact_stat * 0.005) 
    else:
        volume_mod = 1.0
        hs_mod = 1.0
        impact_mult = 1.0 + ((impact_stat - 72.0) * 0.015)
        
    # 🧠 THE MULTIPLIER SQUEEZE
    combined_mult = volume_mod * impact_mult * pace_mod * match_mult
    if combined_mult > 1.25:
        combined_mult = 1.25 + (combined_mult - 1.25) * 0.3
    elif combined_mult < 0.85:
        combined_mult = 0.85 - (0.85 - combined_mult) * 0.3
    
    # 🧠 4. DUAL-ENGINE ARCHITECTURE SETUP
    if theater == "VALORANT":
        pess_k_glob = raw_stat / 180.0
        opt_k_glob = raw_stat / 150.0
        pess_r_total = 34.0 if r_total == 40.0 else (r_total * 0.85)
        opt_r_total = 40.0 if r_total == 40.0 else r_total
    else:
        pess_k_glob = raw_stat / 1.10
        opt_k_glob = raw_stat * 1.08
        pess_r_total = 38.0 if r_total >= 42.0 else (r_total * 0.88)
        opt_r_total = 48.0 if r_total >= 42.0 else (r_total * 1.15) 

    pess_map_proj = []
    opt_map_proj = []
    
    for i in range(2):
        raw_m = m_vals[i]
        if theater == "CS2" and raw_m > 3.0: raw_m = raw_m / 100
        
        if raw_m > 0:
            pess_m_kpr = (raw_m / 180.0) if theater == "VALORANT" else (raw_m / 1.10)
            # FIX: Explicitly apply the optimistic pop-off buff to CS2 Map stats
            opt_m_kpr = (raw_m / 150.0) if theater == "VALORANT" else (raw_m * 1.08) 
        else:
            pess_m_kpr, opt_m_kpr = pess_k_glob, opt_k_glob
        
        if theater == "VALORANT":
            c_agent = str(targets[i]).strip().title()
            if c_agent in ["Kay/O", "Kayo", "Kay-O"]: c_agent = "Kayo"
            spec_mult = VAL_GRAVITY.get(AGENT_ROLES.get(c_agent, "Initiator"), 1.0)
            targets[i] = c_agent 
        else: 
            t_map = str(targets[i]).strip().title()
            spec_mult = CS2_ARCHETYPES.get(t_map, 1.0)
            targets[i] = t_map if t_map and t_map != 'Nan' else 'TBD'
            
        r_mult = spec_mult * (opp_dpr / 0.65)
        if r_mult > 1.15: r_mult = 1.15 + (r_mult - 1.15) * 0.4
        elif r_mult < 0.85: r_mult = 0.85 - (0.85 - r_mult) * 0.4
        
        pess_kills = pess_m_kpr * r_mult * (1 - (heat / 100) * 0.25) * (pess_r_total / 2)
        opt_kills = opt_m_kpr * r_mult * (1 - (heat / 100) * 0.25) * (opt_r_total / 2)
        
        if prop_type == "Headshots" and hs_pcts[i] > 0: 
            pess_kills *= (hs_pcts[i] / 100) * hs_mod 
            opt_kills *= (hs_pcts[i] / 100) * hs_mod 
            
        pess_map_proj.append(pess_kills)
        opt_map_proj.append(opt_kills)

    # 🧠 5. THE DUAL REALITIES
    pess_proj = sum(pess_map_proj) * combined_mult * 0.96 
    opt_proj = sum(opt_map_proj) * combined_mult 
    
    # 🧠 6. THE 25% LOGARITHMIC GOVERNOR (Isolated safely)
    if hist_kills:
        hist_avg = sum(hist_kills) / len(hist_kills)
        if theater == "CS2":
            # FIX: Stops the "Slump Choke" by blending history with the line
            baseline_kills = (hist_avg + u_line) / 2.0 
        else:
            # Keeps Valorant functioning exactly as it did yesterday
            baseline_kills = hist_avg
    else:
        baseline_kills = u_line
        
    cap = 0.25
    
    p_delta_pct = (pess_proj - baseline_kills) / baseline_kills
    if p_delta_pct > cap: pess_proj = baseline_kills * (1 + cap)
    elif p_delta_pct < -cap: pess_proj = baseline_kills * (1 - cap)

    o_delta_pct = (opt_proj - baseline_kills) / baseline_kills
    if o_delta_pct > cap: opt_proj = baseline_kills * (1 + cap)
    elif o_delta_pct < -cap: opt_proj = baseline_kills * (1 - cap)

    # 🧠 7. ASYMMETRIC DECISION ENGINE
    pess_edge = pess_proj - u_line
    opt_edge = u_line - opt_proj

    if pess_edge > 0 and opt_edge < 0:
        pick, final_proj, delta, survived_edge = "OVER", pess_proj, pess_edge, pess_edge
    elif opt_edge > 0 and pess_edge < 0:
        pick, final_proj, delta, survived_edge = "UNDER", opt_proj, -opt_edge, opt_edge
    else:
        if pess_edge > opt_edge:
            pick, final_proj, delta, survived_edge = "OVER", pess_proj, pess_edge, pess_edge
        else:
            pick, final_proj, delta, survived_edge = "UNDER", opt_proj, -opt_edge, opt_edge

    win_prob = (np.random.normal(final_proj, 5.5, 10000) > u_line).mean() * 100
    if delta < 0: win_prob = 100 - win_prob
    
    is_consistent = abs(impact_stat) <= 8.0 if theater == "CS2" else impact_stat >= 74.0
    raw_conf = ((min(100.0, abs(win_prob - 50.0) * 2.0)) * 0.7) + (hr_val * 0.3)

    # 🧠 8. THE NEW PROFITABILITY GRADES
    if survived_edge >= 7.5: 
        if survived_edge >= 10.0:
            grade, color, rec, rec_color = "C", "#FFFFFF", "🛑 TRAP LINE (DO NOT BET)", "#FF4444"
            conf = min(raw_conf, 45.0) 
        else:
            grade, color, rec, rec_color = "C", "#A0A0A0", "🛑 NO BET (EDGE TOO HIGH)", "#FF8C00"
            conf = min(raw_conf, 55.0) 
    elif 3.0 <= survived_edge < 7.5:
        if is_consistent:
            grade, color = ("S+", "#FFD700") if survived_edge >= 4.0 else ("S", "#FFC125")
            rec, rec_color = "🟢 GREEN LIGHT (LOCK)", "#00FF7F"
        else:
            grade, color = ("A+", "#00FF7F") if survived_edge >= 4.0 else ("A", "#00ccff")
            rec, rec_color = "🟢 SOLID PLAY (STANDARD)", "#00ccff"
        conf = raw_conf 
    elif 2.5 <= survived_edge < 3.0:
        grade, color, rec, rec_color = "A", "#00ccff", "🟡 NEUTRAL (SPRINKLE)", "#00ccff"
        conf = raw_conf 
    else: 
        grade, color, rec, rec_color = "C", "#A0A0A0", "🛑 NO BET (COIN FLIP)", "#A0A0A0"
        conf = min(raw_conf, 52.0) 

    return {
        "player": p_name.upper(), "full_team": full_p, "full_opp": full_o,
        "grade": grade, "color": color, "rec": rec, "rec_color": rec_color, "prob": win_prob, "stat_baseline": m_vals[0] if m_vals[0] > 0 else raw_stat, 
        "proj": final_proj, "delta": delta, "is_nuke": (6.0 <= survived_edge <= 8.5 and win_prob >= 85 and is_consistent), 
        "hr": f"{hr_val:.0f}%", "hr_raw": hr_val, "gap": rank_gap, "trace": f"M1: {targets[0]} | M2: {targets[1]}",
        "confidence": round(min(99.9, max(1.0, conf)), 1), "source": data.get("source", "UNKNOWN"), "line": u_line, 
        "prop_type": prop_type, "open_duel": safe_float(data.get('opening_win_pct', 50.0)), "impact_stat": impact_stat,
        "t_rank": data.get('p_rank', 'UNK'), "o_rank": data.get('o_rank', 'UNK'), 
        "dampened": data.get("dampened", False) or (survived_edge >= 10.0),
        "pick": pick, "rounds": r_total
    }

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_player_stats(t_p, p_team_full, domain, stat_target, theater):
    codex_data = load_codex()
    theater_key = "VAL_PLAYERS" if theater == "VALORANT" else "CS2_PLAYERS"
    local_player = codex_data.get(theater_key, {}).get(t_p.lower())
    
    if local_player:
        return {
           "base_stat": local_player.get('adr' if theater == "VALORANT" else 'kpr', 0.0),
           "opening_win_pct": local_player.get('opening_duel_win_pct', local_player.get('opening', 50.0)),
           "impact_stat": local_player.get('kast' if theater == "VALORANT" else 'avg_swing', 72.0 if theater == "VALORANT" else 0.0),
           "last_10_kills": local_player.get('l10_maps_1_and_2_kills', []),
           "role": local_player.get('role', 'Rifler'),
           "source": "CODEX"
        }
    return {"base_stat": 0.0, "source": "MISSING"}

def generate_analytical_writeup(intel, theater_sel):
    grade = intel.get('grade', 'C')
    if grade not in ["S+", "S", "A+", "A"]: return "⚠️ Reserved for premium graded props."
    
    sys_prompt = (
        "You are the lead quantitative AI analyst for the 'Sleepy Kingdom' betting syndicate. "
        "Your job is to write a sharp, 3-sentence mathematical conviction piece for a player prop bet. "
        "CRITICAL RULES: "
        "1. Do NOT hallucinate or invent head-to-head history. "
        "2. Do NOT invent team playstyles, narratives, or match background. "
        "3. ONLY use the mathematical data points provided in the prompt. "
        "4. NEVER confuse 'Kills' or 'Headshots' with 'Total Rounds'. This is strictly a player performance prop. "
        "5. Keep it punchy, cold, and analytical. No bullet points."
    )
    
    user_prompt = f"""
    Draft a 3-sentence write-up for this {grade}-grade {theater_sel} player prop:
    - PLAYER: {intel['player']}
    - MATCHUP: {intel.get('full_team', 'UNK')} vs {intel['full_opp']}
    - PROP TARGET: {intel.get('prop_type', 'Kills')}
    - SPORTSBOOK LINE: {intel['line']}
    - ENGINE PROJECTION: {intel['proj']:.1f}
    - MATHEMATICAL DELTA: {intel.get('delta', 0):+.1f}
    - LAST 10 HIT RATE: {intel.get('hr', 'UNK')}
    - BASELINE EFFICIENCY: {intel.get('stat_baseline', 0):.2f}
    - MODEL WIN PROBABILITY: {intel.get('prob', 50):.1f}%
    - ESTIMATED ROUNDS: {intel.get('rounds', 44)}

    Format strictly as one short paragraph starting with '**The Sleeper Read:**'.
    """
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": sys_prompt}, 
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=250
        )
        return response.choices[0].message.content
    except Exception as e: 
        return f"⚠️ AI Failed: {e}"

def render_grade_card(i, theater_sel, is_dual=False, key_prefix="main"):
    ai_badge = "<span class='ai-badge'>[AI FALLBACK]</span>" if i.get('source') == 'AI_FALLBACK' else "<span class='ai-badge' style='background: rgba(0,255,127,0.1); color: #00FF7F; border-color: #00FF7F;'>[CODEX AUTO]</span>" if i.get('source') == 'CODEX AUTO' else "<span class='ai-badge' style='background: rgba(0,255,127,0.1); color: #00FF7F; border-color: #00FF7F;'>[SHEET SYNC]</span>" if i.get('source') == 'SHEET' else ""
    v_nerf = "<span class='vol-nerf-badge'>⚠️ VOL NERF</span>" if i.get('dampened') else ""
    l_badge = "<span class='vol-nerf-badge' style='color:#FFD700; border-color:#FFD700; background: rgba(255,215,0,0.1);'>🔒 LOCKED</span>" if i.get('Locked') else ""
    d_val = i['delta']
    d_c = "#FFD700" if abs(d_val) >= 10.0 else "#00FF7F" if d_val > 0 else "#FF4500"
    hr_c = "#00FF7F" if i.get('hr_raw', 50) >= 70 else "#FF4500" if i.get('hr_raw', 50) <= 40 else "white"
    
    third_stat_lbl = "Avg Swing" if theater_sel == "CS2" else "KAST %"
    third_stat_val = f"{i.get('impact_stat', 0):+.2f}%" if theater_sel == "CS2" else f"{i.get('impact_stat', 72.0):.1f}%"
    t_color = "#FF4655" if theater_sel == "VALORANT" else "#FFA500"
    
    pad_val = "25px" if is_dual else "40px"
    bg_size = "180px" if is_dual else "300px"
    name_size = "22px" if is_dual else "32px"
    val_size = "20px" if is_dual else "28px"
    dec_size = "18px" if is_dual else "28px"

    card_html = f"""
    <div class="sovereign-card" style="border-top: 15px solid {i.get('color', '#A0A0A0')}; padding: {pad_val};">
    <div class="grade-display" style="font-size: {bg_size};">{i.get('grade', 'C')}</div>
    <div class="card-content">
    {f'<div class="nuke-play-badge">🚀 NUKE PLAY: +10 DELTA LOCK</div>' if i.get('is_nuke', False) else ''}
    <div class="player-name" style="font-size: {name_size};">{i.get('player', 'UNK')} {ai_badge} {v_nerf} {l_badge}</div>
    <div class="match-header"><span style="background-color: {t_color}; color: black; padding: 3px 8px; border-radius: 4px; font-size: 12px; margin-right: 8px; font-weight: 900;">{theater_sel}</span>{i.get('full_team', 'UNK')} vs {i.get('full_opp', 'UNK')} <span style="margin-left: 10px; color: #888; font-size: 10px;">[Rounds: {i.get('rounds', 'UNK')}]</span></div>
    <div style="display: flex; gap: 30px; justify-content: center; align-items: center;">
        <div><div class="stat-lbl">Win Prob</div><div class="stat-val" style="font-size: {val_size};">{i.get('prob', i.get('win_prob', 0.0)):.1f}%</div></div>
        <div><div class="stat-lbl">{i.get('prop_type', 'Prop').upper()} PROJ | LINE</div><div class="stat-val" style="line-height: 1.1;"><span style="color: {i.get('color', '#FFF')}; font-size: {val_size};">{i.get('proj', 0):.1f}</span><br><span style="color: rgba(255,255,255,0.6); font-size: 14px;">Line: {i.get('line', 0)}</span></div></div>
        <div><div class="stat-lbl">{third_stat_lbl}</div><div class="stat-val" style="font-size: {val_size};">{third_stat_val}</div></div>
    </div>
    <div class="decision-line" style="color: {i.get('color', '#FFF')}; font-size: {dec_size};">{i.get('pick', 'N/A')} {abs(i.get('proj', 0) - d_val):.1f} {i.get('prop_type', 'Prop').upper()} {"▲" if d_val > 0 else "▼"}</div>
    
    <div style="margin-top: 15px; border: 1px dashed {i.get('rec_color', '#A0A0A0')}; background-color: {i.get('rec_color', '#A0A0A0')}10; color: {i.get('rec_color', '#A0A0A0')}; padding: 8px; text-align: center; font-family: 'JetBrains Mono'; font-weight: 900; letter-spacing: 1px; border-radius: 4px; font-size: 14px;">
        {i.get('rec', '🛑 NO BET (COIN FLIP)')}
    </div>
    
    <div style="margin-top: 15px; font-family: 'JetBrains Mono'; color: rgba(255,255,255,0.4); font-size: 12px;">{i.get('trace', '🔒 PROP ALREADY LOCKED IN VAULT')}</div>
    </div></div>
    <div class="metric-grid">
        <div class="metric-card"><div class="metric-card-lbl">DELTA (TAX)</div><div class="metric-card-val" style="color: {d_c};">{d_val:+.1f} <span style="font-size: 10px; color: #ff4444;">({i.get('vol_tax', 0.0):-.1f})</span></div></div>
        <div class="metric-card"><div class="metric-card-lbl">CONFIDENCE</div><div class="metric-card-val">{i.get('confidence', 0.0):.1f}%</div></div>
        <div class="metric-card"><div class="metric-card-lbl">MOMENTUM HR</div><div class="metric-card-val" style="color: {hr_c};">{i.get('hr', '0%')}</div></div>
        <div class="metric-card"><div class="metric-card-lbl">GLOBAL {"ADR" if theater_sel == "VALORANT" else "KPR"}</div><div class="metric-card-val">{i.get('stat_baseline', 0.0):.2f}</div></div>
        <div class="metric-card"><div class="metric-card-lbl">RANK GAP</div><div class="metric-card-val">{int(i.get('gap', 0)):+d}</div></div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
    
    if i['grade'] in ["S+", "S", "A+", "A"]:
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            col_btn1, col_btn2 = st.columns(2)
            
            btn_key_ai = f"btn_ai_{key_prefix}_{i['player']}_{i['prop_type']}_{i.get('row_num', 'm')}"
            btn_key_disc = f"btn_disc_{key_prefix}_{i['player']}_{i['prop_type']}_{i.get('row_num', 'm')}"
            
            with col_btn1:
                if st.button(f"🧠 AI WRITEUP", key=btn_key_ai, use_container_width=True):
                    with st.spinner("Consulting the Sleepy Kingdom..."):
                        ai_post = generate_analytical_writeup(i, theater_sel)
                        conf = i.get('confidence', 0)
                        u_size = "2.0U 💣 (NUKE)" if conf >= 85 else "1.5U" if conf >= 75 else "1.0U" if conf >= 60 else "0.5U"
                        st.markdown(f'<div style="background-color: #0f1419; padding: 20px; border-radius: 10px; border-left: 5px solid {i["color"]}; margin-top: 15px;"><h4 style="color: white; margin-top: 0; font-size: 15px;">🌙 SLEEPY KINGDOM CONVICTION</h4>{ai_post}<hr><b>Proj:</b> ~{i["proj"]:.1f} | <b>Grade:</b> {i["grade"]} | <b>Units:</b> {u_size}</div>', unsafe_allow_html=True)
            
            with col_btn2:
                if st.button(f"🚀 FIRE TO DISCORD", key=btn_key_disc, type="primary", use_container_width=True):
                    # Webhook logic goes here!
                    st.success(f"Sniper shot fired to Discord for {i['player']}!")

def run_precision_research(prompt, targets, m_vals, heat, opp_dpr, r_total, impact_stat, sync_duel, sync_ranks, opp_name, theater, prop_type, hs_pcts):
    parts = prompt.split()
    if len(parts) < 2:
        st.error("⚠️ Invalid format. Use: [PLAYER] [LINE] (e.g., 'donk 38.5')")
        return

    p_name = parts[0].upper()
    try: u_line = float(parts[1])
    except: st.error("⚠️ Line must be a valid number."); return

    with st.spinner(f"📡 Establishing Uplink for {p_name}..."):
        manifest_data = MANIFEST.get(theater, {})
        codex_data = load_codex()
        theater_key = "VAL_PLAYERS" if theater == "VALORANT" else "CS2_PLAYERS"
        
        p_team_name = codex_data.get(theater_key, {}).get(p_name.lower(), {}).get("team", "UNK")
        
        if sync_ranks:
            for tag, info in manifest_data.items():
                if p_team_name.lower() in info['full'].lower() or info['full'].lower() in p_team_name.lower():
                    st.session_state['p_rank'] = info['rank']
                    break
            
            if opp_name in manifest_data:
                st.session_state['o_rank'] = manifest_data[opp_name].get("rank", 110)
            else:
                for tag, info in manifest_data.items():
                    if opp_name.lower() in info['full'].lower() or tag.upper() == opp_name.upper():
                        st.session_state['o_rank'] = info['rank']
                        break
        
        full_p = manifest_data.get(p_team_name, {}).get("full", p_team_name)
        full_o = manifest_data.get(opp_name, {}).get("full", opp_name)
        domain = "vlr.gg" if theater == "VALORANT" else "hltv.org"
        stat_target = "KAST ADR" if theater == "VALORANT" else "KPR impact"
        
        raw_data = fetch_player_stats(p_name, full_p, domain, stat_target, theater)
        raw_data['p_rank'] = st.session_state['p_rank']
        raw_data['o_rank'] = st.session_state['o_rank']

        if sync_duel and 'opening_win_pct' in raw_data:
            st.session_state['auto_duel'] = raw_data['opening_win_pct'] / 10.0
            
        if theater == "VALORANT" and raw_data.get('impact_stat') != 72.0:
            impact_stat = raw_data['impact_stat']
            
        if theater == "CS2" and prop_type == "Headshots":
            raw_data['last_10_kills'] = codex_data.get(theater_key, {}).get(p_name.lower(), {}).get('l10_maps_1_and_2_headshots', [])

        intel = apply_sovereign_math(
            raw_data, p_name, u_line, full_p, full_o, targets, m_vals, 
            heat, opp_dpr, r_total, impact_stat, theater, prop_type, hs_pcts
        )
        st.session_state['last_intel'] = intel
        st.rerun()

# --- ALPHA SLIP GENERATOR ENGINES ---
def get_alpha_slips(results_dict, mode="Mixed"):
    elite_pool = []
    
    for match_id, teams in results_dict.items():
        for item in teams:
            theater = item['type']
            if mode != "Mixed" and theater != mode: continue
            
            for p in item['data']:
                if p.get('Locked'): continue 
                if p.get('grade') in ["S+", "S", "A+", "A"]:
                    p['match_id'] = match_id
                    p['theater'] = theater
                    elite_pool.append(p)

    # 🛡️ Must return a list AND a string
    if len(elite_pool) < 2: 
        return [], f"⚠️ Found only {len(elite_pool)} eligible, unlocked S/A-tier player(s). Need at least 2 to form a slip."

    valid_slips = []
    for p1, p2 in combinations(elite_pool, 2):
        # 🛡️ THE INDEPENDENCE RULE: Must be different matches
        if p1['match_id'] == p2['match_id']: continue 
        
        prob1 = p1.get('prob', p1.get('win_prob', 50)) / 100
        prob2 = p2.get('prob', p2.get('win_prob', 50)) / 100
        combined_prob = prob1 * prob2
        
        base_prob = combined_prob * 100
        alpha_score = min(99.9, max(0.0, ((base_prob - 33.3) * 3.5) + 75.0))
        
        valid_slips.append({
            "leg1": p1, "leg2": p2,
            "true_prob": base_prob,
            "alpha_score": alpha_score
        })
        
    # 🛡️ Must return a list AND a string
    if not valid_slips:
        return [], f"⚠️ Found {len(elite_pool)} elite players, but they are all in the SAME match! The Independence Rule prevents same-game parlays."
        
    valid_slips.sort(key=lambda x: x['alpha_score'], reverse=True)
    
    # 🛡️ Must return the slips AND None
    return valid_slips[:3], None

def generate_slip_writeup(slip):
    try:
        l1, l2 = slip['leg1'], slip['leg2']
        prompt = f"""
        You are a sharp esports betting analyst for a syndicate. I am pairing these two props into a 2-leg parlay slip.
        
        LEG 1 ({l1['theater']}): {l1['player']} ({l1['full_team']})
        Prop: {l1['pick']} {l1['line']} {l1['prop_type']}
        Model Projection: {l1['proj']:.1f} (Edge: {l1['delta']:.1f})
        Matchup: Team Rank #{l1.get('t_rank', 'UNK')} vs Opponent Rank #{l1.get('o_rank', 'UNK')}
        
        LEG 2 ({l2['theater']}): {l2['player']} ({l2['full_team']})
        Prop: {l2['pick']} {l2['line']} {l2['prop_type']}
        Model Projection: {l2['proj']:.1f} (Edge: {l2['delta']:.1f})
        Matchup: Team Rank #{l2.get('t_rank', 'UNK')} vs Opponent Rank #{l2.get('o_rank', 'UNK')}
        
        Write a punchy, highly analytical, 3-sentence justification for why this specific 2-man slip has massive positive expected value (+EV). 
        Focus strictly on the math, rank disparities, and the projection edge. 
        Use an authoritative, professional tone. Do not use hashtags or emojis.
        """
        
        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.4,
            max_tokens=150
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"AI Generation Failed: {e}"

def push_to_discord(slip, writeup, webhook_url):
    l1, l2 = slip['leg1'], slip['leg2']
    
    embed = {
        "title": f"🚨 SOVEREIGN ALPHA SLIP 🚨",
        "description": f"**Alpha Score: {slip['alpha_score']:.1f}/100** | *True Prob: {slip['true_prob']:.1f}%*\n\n{writeup}",
        "color": 65280, 
        "fields": [
            {
                "name": f"Leg 1: {l1['player']} ({l1['theater']})",
                "value": f"**{l1['pick']} {l1['line']} {l1['prop_type']}**\nProj: {l1['proj']:.1f} | Grade: {l1['grade']}",
                "inline": False
            },
            {
                "name": f"Leg 2: {l2['player']} ({l2['theater']})",
                "value": f"**{l2['pick']} {l2['line']} {l2['prop_type']}**\nProj: {l2['proj']:.1f} | Grade: {l2['grade']}",
                "inline": False
            }
        ],
        "footer": {"text": "Iron Guard Syndicate Engine"}
    }
    
    payload = {"embeds": [embed]}
    try:
        resp = requests.post(webhook_url, json=payload)
        return resp.status_code in [200, 204]
    except Exception as e:
        st.error(f"Webhook Exception: {e}")
        return False

# --- 3. UI LAYER ---
execute_sweep = False

with st.sidebar:
    st.header("📡 COMMAND CENTER")
    cmd_mode = st.radio("Command Mode", ["Single Target (Manual)", "Syndicate Sweep (API)"])
    st.divider()

    if cmd_mode == "Single Target (Manual)":
        theater_sel = st.radio("Theater", ["VALORANT", "CS2"])
        prop_type = "Kills" if theater_sel == "VALORANT" else st.radio("Prop Type", ["Kills", "Headshots"])
        
        with st.expander("👤 PLAYER TACTICAL", expanded=True):
            label = "Agent" if theater_sel == "VALORANT" else "Map"
            stat_lbl = "ADR" if theater_sel == "VALORANT" else "KPR"
            target_list = VAL_AGENTS if theater_sel == "VALORANT" else list(CS2_ARCHETYPES.keys())
            
            t1 = st.selectbox(f"{label} 1", target_list, key="t1_select")
            t1_v = safe_float(st.text_input(f"{t1} {stat_lbl} (Override)", "", key="t1_stat_input"))
            t1_hs = safe_float(st.text_input(f"{t1} HS%", "50.0", key="t1_hs_input")) if (theater_sel == "CS2" and prop_type == "Headshots") else 0.0
            
            t2 = st.selectbox(f"{label} 2", target_list, key="t2_select")
            t2_v = safe_float(st.text_input(f"{t2} {stat_lbl} (Override)", "", key="t2_stat_input"))
            t2_hs = safe_float(st.text_input(f"{t2} HS%", "50.0", key="t2_hs_input")) if (theater_sel == "CS2" and prop_type == "Headshots") else 0.0
            
            st.write("---")
            sync_ranks = st.checkbox("🛰️ Auto-Sync Ranks", value=True)
            st.session_state['p_rank'] = st.number_input("Team Rank", 1, 300, value=st.session_state['p_rank'], disabled=sync_ranks)
            
            if theater_sel == "CS2":
                sync_duel = st.checkbox("🛰️ Auto-Sync Open Duel", value=True)
                st.session_state['auto_duel'] = st.slider("Open Duel (1-10)", 1.0, 10.0, value=st.session_state['auto_duel'], step=0.1, disabled=sync_duel, help="Player's opening duel win percentage scaled to a 1-10 rating.")
            
            r_total_manual = safe_float(st.text_input("Total Rounds Expected", "40.0" if theater_sel == "VALORANT" else "44.0"))
            
            if theater_sel == "CS2": impact_stat_val = st.number_input("HLTV Round Swing (+/- %)", min_value=-20.0, max_value=20.0, value=0.0, step=1.0)
            else: impact_stat_val = st.number_input("VLR KAST %", min_value=0.0, max_value=100.0, value=72.0, step=1.0)
                
            heat_manual = st.slider("Teammate Heat (Kill Steal %)", 0, 100, 0, help="Higher values reduce the player's projected volume due to teammates taking kills.")
            
        with st.expander("🛡️ OPPONENT TACTICAL", expanded=True):
            opp_name_manual = st.text_input("Opponent (Abbr)", "PCF").upper().strip()
            raw_dpr_manual = safe_float(st.text_input("Opponent DPR", "0.65"))
            st.session_state['o_rank'] = st.number_input("Opponent Rank", 1, 300, value=st.session_state['o_rank'], disabled=sync_ranks)

    else:
        st.subheader("📊 PropVault API Sync")
        st.caption("Hardcoded direct connection via gspread.")
        
        r_total_v = safe_float(st.text_input("Total Rounds Est. (Global Default)", "40.0", help="Defaults to 40.0 for Valorant baseline. Used to model stomps/blowouts if the 'Total Rounds' column in your sheet is blank."))
        raw_dpr_api = safe_float(st.text_input("Global Opp DPR (Fallback)", "0.65", help="Used only if the Google Sheet row is blank."))
        
        heat_val = st.slider("Global Pacing Dampener / Heat (%)", 0, 100, 0, help="Use this to globally model slow matches or steal rates. Can be overridden in your Sheet.")
        rank_respect = st.slider("🎓 Rank Respect", 0.0, 1.0, 0.3, help="Higher = more doubt on stats gained against weak teams.")
        
        execute_sweep = st.button("🔥 EXECUTE SYNDICATE SWEEP", use_container_width=True, type="primary")

# --- 4. EXECUTION LOOP ---
if cmd_mode == "Single Target (Manual)":
    if st.session_state['last_intel']:
        render_grade_card(st.session_state['last_intel'], theater_sel, is_dual=False, key_prefix="manual")
        st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    
    if prompt := st.chat_input("Grade Player (Abbr) Line"):
        hs_pct_array = [t1_hs, t2_hs] if (theater_sel == "CS2" and prop_type == "Headshots") else [0.0, 0.0]
        run_precision_research(prompt, [t1, t2], [t1_v, t2_v], heat_manual, raw_dpr_manual, r_total_manual, impact_stat_val, sync_duel, sync_ranks, opp_name_manual, theater_sel, prop_type, hs_pct_array)

elif cmd_mode == "Syndicate Sweep (API)" and execute_sweep:
    st.session_state['sweep_results'] = {}
    codex_data = load_codex()
    val_codex = codex_data.get("VAL_PLAYERS", {})
    cs2_codex = codex_data.get("CS2_PLAYERS", {})
    
    with st.spinner("Connecting to PropVault API..."):
        try:
            google_creds = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(google_creds) 
            sh = gc.open_by_key("1xsxwRlnwF2MNkHwmSSRsOlKCV8H7W9iXemXyaTcIhlg")
        except Exception as e:
            st.error(f"Google API Error: {e}")
            st.stop()

    # --- VALORANT MASTER SYNC ---
    with st.spinner("Processing & Writing Valorant Master..."):
        try:
            val_sheet = sh.worksheet("Valorant Master")
            val_all_data = val_sheet.get_all_values()
            if val_all_data:
                val_headers = [h.strip().upper() for h in val_all_data[0]]
                val_rows = val_all_data[1:]
                
                def get_v_col(*names):
                    for name in names:
                        try: return val_headers.index(name.upper()) + 1
                        except ValueError: continue
                    return None
                
                V_COLS = {
                    "PLAYER": get_v_col("PLAYER"), "TEAM": get_v_col("TEAM"), "OPP": get_v_col("OPPONENT"),
                    "T_RANK": get_v_col("T-WORLD RANK", "T WORLD RANK", "TEAM RANK"), "O_RANK": get_v_col("O-WORLD RANK", "O WORLD RANK", "OPP RANK"),
                    "LOCKED": get_v_col("LOCKED"), "ACTUAL_K": get_v_col("ACTUAL KILLS"),
                    "K_LINE": get_v_col("KILL LINE"), "K_PROJ": get_v_col("KILL PROJ"),
                    "K_PICK": get_v_col("KILL PICK"), "K_GRADE": get_v_col("KILL GRADE"),
                    "GLOBAL_STAT": get_v_col("GLOBAL ADR"), "OPP_DPR": get_v_col("OPPONENT DPR", "OPP DPR"),
                    "HEAT": get_v_col("PLAYER HEAT", "HEAT"), "L10_HR": get_v_col("L10 KILL HR", "L10 HR"),
                    "M1_AGENT": get_v_col("M1 AGENT"), "M2_AGENT": get_v_col("M2 AGENT"),
                    "M1_ADR": get_v_col("M1 ADR"), "M2_ADR": get_v_col("M2 ADR"),
                    "ROUNDS": get_v_col("TOTAL ROUNDS", "ROUNDS", "EST ROUNDS"),
                    "READY": get_v_col("READY")
                }
                
                v_updates = []
                val_slate_cards = []
                
                for idx, row in enumerate(val_rows):
                    row_num = idx + 2
                    def r_get(key, default=None):
                        idx_map = V_COLS.get(key)
                        if idx_map and len(row) >= idx_map:
                            val = row[idx_map-1]
                            return val if val != "" else default
                        return default
                    
                    p_name = r_get("PLAYER")
                    if not p_name: continue

                    # 🛡️ THE WORKFLOW ENFORCER
                    is_ready = str(r_get("READY", "TRUE")).upper() == "TRUE"
                    if not is_ready: continue

                    actual_k_str = str(r_get("ACTUAL_K", "")).strip().upper()
                    if actual_k_str == "DNP" or safe_float(actual_k_str) > 0: continue
                    
                    k_line_str = str(r_get("K_LINE", "")).strip().upper()
                    if k_line_str == "DNP" or safe_float(k_line_str) <= 0: continue
                    
                    is_locked = str(r_get("LOCKED", "FALSE")).upper() == "TRUE"
                    p_lower = p_name.lower().strip()
                    t_abbr, o_abbr = str(r_get("TEAM", "")).upper(), str(r_get("OPP", "")).upper()
                    
                    base_adr = safe_float(r_get("GLOBAL_STAT"))
                    if base_adr <= 0: base_adr = safe_float(val_codex.get(p_lower, {}).get("adr", 0))

                    kast_val = safe_float(r_get("KAST %"))
                    if kast_val <= 0: kast_val = safe_float(val_codex.get(p_lower, {}).get("kast", 72.0))
                    
                    sheet_t_rank = safe_float(r_get("T_RANK", 0))
                    sheet_o_rank = safe_float(r_get("O_RANK", 0))
                    t_rank = sheet_t_rank if sheet_t_rank > 0 else get_fuzzy_rank(t_abbr, VAL_LIVE, 60)
                    o_rank = sheet_o_rank if sheet_o_rank > 0 else get_fuzzy_rank(o_abbr, VAL_LIVE, 110)
                    
                    sheet_rounds = safe_float(r_get("ROUNDS", 0))
                    active_rounds = sheet_rounds if sheet_rounds > 0 else r_total_v

                    p_data = {
                        "base_stat": base_adr, "source": "SHEET" if r_get("GLOBAL_STAT") else "CODEX AUTO",
                        "p_rank": t_rank, "o_rank": o_rank, "last_10_kills": val_codex.get(p_lower, {}).get('l10_maps_1_and_2_kills', [])
                    }
                    
                    if is_locked:
                        k_proj, k_line = safe_float(r_get("K_PROJ", 0)), safe_float(k_line_str)
                        k_delta = k_proj - k_line
                        over_prob = (np.random.normal(k_proj, 5.5, 5000) > k_line).mean() * 100
                        win_prob = over_prob if k_delta > 0 else (100 - over_prob)
                        conf = min(99.9, max(1.0, (min(100.0, abs(win_prob - 50.0) * 2.0) * 0.7) + 15.0))
                        
                        raw_hr = str(r_get("L10_HR", "")).replace('%', '').strip()
                        sheet_hr = float(raw_hr) if raw_hr.replace('.', '', 1).isdigit() else 0.0

                        res = {
                            "player": p_name.upper(), "full_team": t_abbr, "full_opp": o_abbr,
                            "line": k_line, "Locked": True, "pick": str(r_get("K_PICK", "N/A")),
                            "grade": str(r_get("K_GRADE", "C")), "proj": k_proj, "delta": k_delta,
                            "win_prob": round(win_prob, 1), "confidence": round(conf, 1), "prop_type": "Kills", "row_num": row_num,
                            "stat_baseline": base_adr,
                            "gap": o_rank - t_rank,
                            "hr": f"{sheet_hr:.0f}%",
                            "hr_raw": sheet_hr,
                            "impact_stat": kast_val,
                            "t_rank": t_rank,
                            "o_rank": o_rank,
                            "rounds": active_rounds,
                            "trace": f"M1: {str(r_get('M1_AGENT', 'Unk')).upper()} | M2: {str(r_get('M2_AGENT', 'Unk')).upper()}"
                        }
                    else:
                        raw_hr = str(r_get("L10_HR", "")).replace('%', '').strip()
                        sheet_hr = float(raw_hr) if raw_hr.replace('.', '', 1).isdigit() else 0.0
                        res = apply_sovereign_math(
                            p_data, p_name, safe_float(k_line_str), t_abbr, o_abbr,
                            [str(r_get('M1_AGENT', 'Unk')), str(r_get('M2_AGENT', 'Unk'))],
                            [safe_float(r_get('M1_ADR', 0)), safe_float(r_get('M2_ADR', 0))],
                            safe_float(r_get("HEAT")) or heat_val, safe_float(r_get("OPP_DPR")) or (raw_dpr_api/100 if raw_dpr_api > 2 else raw_dpr_api),
                            active_rounds, kast_val, "VALORANT", "Kills", [0.0, 0.0], rank_respect_val=rank_respect, hr_override=sheet_hr if sheet_hr > 0 else None
                        )
                        res['Locked'], res['row_num'] = False, row_num
                    
                    val_slate_cards.append(res)
                
                apply_kill_economy_dampener(val_slate_cards, r_total_v, "VALORANT")
                
                for res in val_slate_cards:
                    match_id = get_match_id(res['full_team'], res['full_opp'])
                    
                    if not res.get('Locked'):
                        if V_COLS["K_PROJ"]: v_updates.append(gspread.Cell(row=res['row_num'], col=V_COLS["K_PROJ"], value=round(res['proj'], 1)))
                        if V_COLS["K_PICK"]: v_updates.append(gspread.Cell(row=res['row_num'], col=V_COLS["K_PICK"], value=res['pick']))
                        if V_COLS["K_GRADE"]: v_updates.append(gspread.Cell(row=res['row_num'], col=V_COLS["K_GRADE"], value=res['grade']))
                        
                    if match_id not in st.session_state['sweep_results']: st.session_state['sweep_results'][match_id] = []
                    st.session_state['sweep_results'][match_id].append({"type": "VALORANT", "data": [res]})
                
                if v_updates: val_sheet.update_cells(v_updates)
        except Exception as e: st.error(f"Valorant Sync Error: {e}")

   # --- CS2 MASTER W/ BATCH WRITE ---
    with st.spinner("Processing & Writing CS2 Master..."):
        try:
            cs2_sheet = sh.worksheet("CS2 Master")
            df_cs2 = pd.DataFrame(cs2_sheet.get_all_records()).fillna(0)
            
            # 🛡️ BULLETPROOF COLUMN INDEXING (Case-Insensitive)
            df_cols_upper = [str(c).strip().upper() for c in df_cs2.columns]
            
            def get_col_idx(*names):
                for n in names:
                    if n.upper() in df_cols_upper: return df_cols_upper.index(n.upper()) + 1
                return None

            c_kill_proj = get_col_idx("PROJ KILLS", "KILL PROJ")
            c_hs_proj = get_col_idx("PROJ HS", "HS PROJ")
            c_kill_pick = get_col_idx("KILL PICK")
            c_kill_grade = get_col_idx("KILL GRADE")
            c_hs_pick = get_col_idx("HS PICK")
            c_hs_grade = get_col_idx("HS GRADE")

            cs2_updates = []
            cs2_slate_cards = []
            cs2_match_map = {}

            for idx, r in df_cs2.iterrows():
                row_num = idx + 2
                
                # Convert the entire row to uppercase keys to ignore typos/casing in Sheets
                r_upper = {str(k).strip().upper(): v for k, v in r.items()}
                
                def r_get(*keys, default=None):
                    for k in keys:
                        val = r_upper.get(k.upper())
                        if val is not None and str(val).strip() != "": return val
                    return default

                p_raw = r_get('PLAYER')
                if not p_raw: continue
                
                # 🛡️ THE WORKFLOW ENFORCER (Fixed Pandas Empty/Blank bug + Case Sensitivity)
                raw_ready = str(r_get('READY', default='TRUE')).strip().upper()
                if raw_ready == 'FALSE': continue
                
                p_lower = str(p_raw).lower()
                t_abbr = str(r_get('TEAM', default='')).upper()
                o_abbr = str(r_get('OPPONENT', 'OPP', default='')).upper()
                match_id = get_match_id(t_abbr, o_abbr)
                
                base_kpr = safe_float(cs2_codex.get(p_lower, {}).get('kpr', 0.0))
                open_duel = safe_float(cs2_codex.get(p_lower, {}).get('opening', 50.0))
                if 0 < open_duel <= 10.0: open_duel *= 10
                    
                r_swing = safe_float(r_get('AVG SWING', 'SWING', default=0)) 
                
                sheet_t_rank = safe_float(r_get('TEAM RANK', 'T RANK', default=0))
                sheet_o_rank = safe_float(r_get('OPP RANK', 'OPPONENT RANK', 'O RANK', default=0))
                
                t_rank = sheet_t_rank if sheet_t_rank > 0 else get_fuzzy_rank(t_abbr, CS2_LIVE, 60)
                o_rank = sheet_o_rank if sheet_o_rank > 0 else get_fuzzy_rank(o_abbr, CS2_LIVE, 110)
                
                role = str(r_get('ROLE', default=cs2_codex.get(p_lower, {}).get('role', 'Rifler')))
                
                p_data = {
                    "base_stat": base_kpr, "opening_win_pct": open_duel,
                    "source": "SHEET" if safe_float(r_get('GLOBAL KPR', 'KPR', default=0)) > 0 else "CODEX AUTO", 
                    "p_rank": t_rank, "o_rank": o_rank, "last_10_kills": cs2_codex.get(p_lower, {}).get('l10_maps_1_and_2_kills', []),
                    "role": role 
                }

                active_opp_dpr = (raw_dpr_api / 100) if raw_dpr_api > 2.0 else raw_dpr_api
                sheet_heat = safe_float(r_get('PLAYER HEAT', 'HEAT', default=0))
                player_heat = sheet_heat if sheet_heat > 0 else heat_val
                
                sheet_rounds = safe_float(r_get('TOTAL ROUNDS', 'ROUNDS', default=0))
                active_rounds = sheet_rounds if sheet_rounds > 0 else r_total_v

                is_locked = str(r_get('LOCKED', default='FALSE')).upper() == 'TRUE'

                m1_val = str(r_get('M1 MAP', default='TBD')).strip().title()
                m2_val = str(r_get('M2 MAP', default='TBD')).strip().title()
                if m1_val.lower() in ['nan', '0', '0.0', '']: m1_val = 'TBD'
                if m2_val.lower() in ['nan', '0', '0.0', '']: m2_val = 'TBD'
                
                # --- KILL PROP PROCESSING ---
                k_line_raw = str(r_get('KILL LINE', default='')).strip().upper()
                if k_line_raw != "DNP" and safe_float(k_line_raw) > 0:
                    if is_locked:
                        k_res = {
                            "player": str(p_raw).upper(), "full_team": t_abbr, "full_opp": o_abbr,
                            "line": safe_float(k_line_raw), "Locked": True, "pick": str(r_get('KILL PICK', default='N/A')),
                            "grade": str(r_get('KILL GRADE', default='C')), "proj": safe_float(r_get('PROJ KILLS', 'KILL PROJ', default=0)),
                            "prop_type": "Kills", "row_num": row_num,
                            "stat_baseline": base_kpr,
                            "gap": o_rank - t_rank,
                            "impact_stat": r_swing,
                            "hr": "🔒", "hr_raw": 50, "trace": "🔒 PROP ALREADY LOCKED IN VAULT",
                            "t_rank": t_rank, "o_rank": o_rank, "rounds": active_rounds
                        }
                        k_res["delta"] = k_res["proj"] - k_res["line"]
                        
                        over_prob = (np.random.normal(k_res["proj"], 5.5, 5000) > k_res["line"]).mean() * 100
                        k_res["win_prob"] = over_prob if k_res["delta"] > 0 else (100 - over_prob)
                        k_res["confidence"] = min(99.9, max(1.0, (min(100.0, abs(k_res["win_prob"] - 50.0) * 2.0) * 0.7) + 15.0))
                    else:
                        k_res = apply_sovereign_math(
                            p_data, str(p_raw), safe_float(k_line_raw), t_abbr, o_abbr,
                            [m1_val, m2_val], [0.0, 0.0], player_heat, active_opp_dpr, active_rounds, r_swing, 
                            "CS2", "Kills", [0.0, 0.0], rank_respect_val=rank_respect
                        )
                        k_res['Locked'] = False
                        k_res['row_num'] = row_num
                        
                    cs2_slate_cards.append(k_res)

                # --- HS PROP PROCESSING ---
                hs_line_raw = str(r_get('HS LINE', default='')).strip().upper()
                if hs_line_raw != "DNP" and safe_float(hs_line_raw) > 0:
                    if is_locked:
                        h_res = {
                            "player": str(p_raw).upper(), "full_team": t_abbr, "full_opp": o_abbr,
                            "line": safe_float(hs_line_raw), "Locked": True, "pick": str(r_get('HS PICK', default='N/A')),
                            "grade": str(r_get('HS GRADE', default='C')), "proj": safe_float(r_get('PROJ HS', 'HS PROJ', default=0)),
                            "prop_type": "Headshots", "row_num": row_num,
                            "stat_baseline": base_kpr,
                            "gap": o_rank - t_rank,
                            "impact_stat": r_swing,
                            "hr": "🔒", "hr_raw": 50, "trace": "🔒 PROP ALREADY LOCKED IN VAULT",
                            "t_rank": t_rank, "o_rank": o_rank, "rounds": active_rounds
                        }
                        h_res["delta"] = h_res["proj"] - h_res["line"]
                        
                        over_prob = (np.random.normal(h_res["proj"], 5.5, 5000) > h_res["line"]).mean() * 100
                        h_res["win_prob"] = over_prob if h_res["delta"] > 0 else (100 - over_prob)
                        h_res["confidence"] = min(99.9, max(1.0, (min(100.0, abs(h_res["win_prob"] - 50.0) * 2.0) * 0.7) + 15.0))
                    else:
                        hs_pct_val = safe_float(cs2_codex.get(p_lower, {}).get('hs_percentage', 50.0))
                        p_data_hs = p_data.copy()
                        p_data_hs['last_10_kills'] = cs2_codex.get(p_lower, {}).get('l10_maps_1_and_2_headshots', [])

                        h_res = apply_sovereign_math(
                            p_data_hs, str(p_raw), safe_float(hs_line_raw), t_abbr, o_abbr,
                            [m1_val, m2_val], [0.0, 0.0], player_heat, active_opp_dpr, active_rounds, r_swing, 
                            "CS2", "Headshots", [hs_pct_val, hs_pct_val], rank_respect_val=rank_respect
                        )
                        h_res['Locked'] = False
                        h_res['row_num'] = row_num

                    cs2_slate_cards.append(h_res)

            apply_kill_economy_dampener(cs2_slate_cards, r_total_v, "CS2")
            
            for res in cs2_slate_cards:
                match_id = get_match_id(res['full_team'], res['full_opp'])
                
                if match_id not in cs2_match_map: cs2_match_map[match_id] = {}
                p_name = res['player']
                if p_name not in cs2_match_map[match_id]: cs2_match_map[match_id][p_name] = []
                cs2_match_map[match_id][p_name].append(res)
                
                if not res.get('Locked'):
                    if res['prop_type'] == "Kills":
                        if c_kill_proj: cs2_updates.append(gspread.Cell(row=res['row_num'], col=c_kill_proj, value=round(res['proj'], 1)))
                        if c_kill_pick: cs2_updates.append(gspread.Cell(row=res['row_num'], col=c_kill_pick, value=res['pick']))
                        if c_kill_grade: cs2_updates.append(gspread.Cell(row=res['row_num'], col=c_kill_grade, value=res['grade']))
                    elif res['prop_type'] == "Headshots":
                        if c_hs_proj: cs2_updates.append(gspread.Cell(row=res['row_num'], col=c_hs_proj, value=round(res['proj'], 1)))
                        if c_hs_pick: cs2_updates.append(gspread.Cell(row=res['row_num'], col=c_hs_pick, value=res['pick']))
                        if c_hs_grade: cs2_updates.append(gspread.Cell(row=res['row_num'], col=c_hs_grade, value=res['grade']))
            
            for m_id, players in cs2_match_map.items():
                if m_id not in st.session_state['sweep_results']: st.session_state['sweep_results'][m_id] = []
                for p_name, p_cards in players.items():
                    st.session_state['sweep_results'][m_id].append({"type": "CS2", "data": p_cards})
                    
            if cs2_updates:
                cs2_sheet.update_cells(cs2_updates)
        except Exception as e: st.error(f"CS2 Sync Error: {e}")

# --- ALPHA SLIP GENERATOR ENGINES ---
def get_alpha_slips(results_dict, mode="Mixed"):
    elite_pool = []
    
    for match_id, teams in results_dict.items():
        for item in teams:
            theater = item['type']
            if mode != "Mixed" and theater != mode: continue
            
            for p in item['data']:
                if p.get('Locked'): continue 
                if p.get('grade') in ["S+", "S", "A+", "A"]:
                    p['match_id'] = match_id
                    p['theater'] = theater
                    elite_pool.append(p)

    if len(elite_pool) < 2: 
        return [], f"⚠️ Found only {len(elite_pool)} eligible, unlocked S/A-tier player(s). Need at least 2 to form a slip."

    valid_slips = []
    for p1, p2 in combinations(elite_pool, 2):
        if p1['match_id'] == p2['match_id']: continue 
        
        prob1 = p1.get('prob', p1.get('win_prob', 50)) / 100
        prob2 = p2.get('prob', p2.get('win_prob', 50)) / 100
        combined_prob = prob1 * prob2
        
        base_prob = combined_prob * 100
        alpha_score = min(99.9, max(0.0, ((base_prob - 33.3) * 3.5) + 75.0))
        
        valid_slips.append({
            "leg1": p1, "leg2": p2,
            "true_prob": base_prob,
            "alpha_score": alpha_score
        })
        
    if not valid_slips:
        return [], f"⚠️ Found {len(elite_pool)} elite players, but they are all in the SAME match! The Independence Rule prevents same-game parlays."
        
    valid_slips.sort(key=lambda x: x['alpha_score'], reverse=True)
    return valid_slips[:3], None

def generate_slip_writeup(slip):
    try:
        l1, l2 = slip['leg1'], slip['leg2']
        prompt = f"""
        You are a sharp esports betting analyst for a syndicate. I am pairing these two props into a 2-leg parlay slip.
        
        LEG 1 ({l1['theater']}): {l1['player']} ({l1['full_team']})
        Prop: {l1['pick']} {l1['line']} {l1['prop_type']}
        Model Projection: {l1['proj']:.1f} (Edge: {l1['delta']:.1f})
        Matchup: Team Rank #{l1.get('t_rank', 'UNK')} vs Opponent Rank #{l1.get('o_rank', 'UNK')}
        
        LEG 2 ({l2['theater']}): {l2['player']} ({l2['full_team']})
        Prop: {l2['pick']} {l2['line']} {l2['prop_type']}
        Model Projection: {l2['proj']:.1f} (Edge: {l2['delta']:.1f})
        Matchup: Team Rank #{l2.get('t_rank', 'UNK')} vs Opponent Rank #{l2.get('o_rank', 'UNK')}
        
        Write a punchy, highly analytical, 3-sentence justification for why this specific 2-man slip has massive positive expected value (+EV). 
        Focus strictly on the math, rank disparities, and the projection edge. 
        Use an authoritative, professional tone. Do not use hashtags or emojis.
        """
        
        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.4,
            max_tokens=150
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"AI Generation Failed: {e}"

def push_to_discord(slip, writeup, webhook_url):
    l1, l2 = slip['leg1'], slip['leg2']
    
    embed = {
        "title": f"🚨 SOVEREIGN ALPHA SLIP 🚨",
        "description": f"**Alpha Score: {slip['alpha_score']:.1f}/100** | *True Prob: {slip['true_prob']:.1f}%*\n\n{writeup}",
        "color": 65280, 
        "fields": [
            {
                "name": f"Leg 1: {l1['player']} ({l1['theater']})",
                "value": f"**{l1['pick']} {l1['line']} {l1['prop_type']}**\nProj: {l1['proj']:.1f} | Grade: {l1['grade']}",
                "inline": False
            },
            {
                "name": f"Leg 2: {l2['player']} ({l2['theater']})",
                "value": f"**{l2['pick']} {l2['line']} {l2['prop_type']}**\nProj: {l2['proj']:.1f} | Grade: {l2['grade']}",
                "inline": False
            }
        ],
        "footer": {"text": "Iron Guard Syndicate Engine"}
    }
    
    payload = {"embeds": [embed]}
    try:
        resp = requests.post(webhook_url, json=payload)
        return resp.status_code in [200, 204]
    except Exception as e:
        st.error(f"Webhook Exception: {e}")
        return False


# --- 5. RENDER PHASE (THE 3-TAB ARCHITECTURE) ---
if st.session_state.get('sweep_results'):
    all_slate_cards = []
    for match_key, match_items in st.session_state['sweep_results'].items():
        for item in match_items:
            for c in item['data']:
                c['_theater'] = item['type']
                all_slate_cards.append(c)
    
    match_keys = list(st.session_state['sweep_results'].keys())
    
    # 🎯 1. BUCKET THE DATA 
    hit_list = [c for c in all_slate_cards if c.get('grade') in ["S+", "S", "A+", "A"]]
    hit_list = sorted(hit_list, key=lambda x: x.get('confidence', 0), reverse=True)
    
    graveyard = [c for c in all_slate_cards if c.get('grade') == "C"]
    
    # 🎯 2. BUILD THE TABS 
    tab_titles = ["🎯 THE HIT LIST", "⚡ ALPHA SLIPS", "🪦 THE GRAVEYARD"]
    for mk in match_keys:
        theater = st.session_state['sweep_results'][mk][0]['type']
        prefix = "🔴 VAL |" if theater == "VALORANT" else "🟠 CS2 |"
        tab_titles.append(f"{prefix} {mk}")
        
    tabs = st.tabs(tab_titles)
    
    # --- TAB 0: THE HIT LIST ---
    with tabs[0]:
        st.markdown("<h3 style='color: #00FF7F; margin-top: 0px;'>🎯 S-TIER & A-TIER HIT LIST</h3>", unsafe_allow_html=True)
        st.caption("Review the top mathematical edges and manually fire to Discord. Sorted by highest confidence.")
        
        if not hit_list:
            st.warning("⚠️ No S or A-tier plays found on this slate. The math says skip today.")
        else:
            for i in range(0, len(hit_list), 2):
                col1, col2 = st.columns(2)
                with col1:
                    render_grade_card(hit_list[i], hit_list[i]['_theater'], is_dual=True, key_prefix=f"hit_{i}")
                with col2:
                    if i + 1 < len(hit_list):
                        render_grade_card(hit_list[i+1], hit_list[i+1]['_theater'], is_dual=True, key_prefix=f"hit_{i+1}")

    # --- TAB 1: ⚡ ALPHA SLIPS ---
    with tabs[1]:
        st.markdown("<h3 style='color: #FFD700; margin-top: 0px;'>⚡ ALPHA SLIP GENERATOR</h3>", unsafe_allow_html=True)
        st.caption("Auto-generates the Top 3 highest +EV independent parlay pairs.")
        
        if 'active_slips' not in st.session_state: st.session_state['active_slips'] = []
        if 'slip_writeups' not in st.session_state: st.session_state['slip_writeups'] = {}
        if 'slip_error' not in st.session_state: st.session_state['slip_error'] = None
        
        col_mode, col_btn = st.columns([1, 2])
        with col_mode:
            slip_mode = st.radio("Select Slip Engine Mode:", ["Mixed", "VALORANT", "CS2"], horizontal=True)
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🎲 GENERATE TOP 3 SLIPS", type="primary", use_container_width=True):
                slips, msg = get_alpha_slips(st.session_state['sweep_results'], slip_mode)
                st.session_state['active_slips'] = slips
                st.session_state['slip_error'] = msg
                st.session_state['slip_writeups'] = {} 
                st.rerun()

        if st.session_state.get('slip_error'):
            st.warning(st.session_state['slip_error'])

        if not st.session_state.get('active_slips') and st.button("Clear Generator State", key="clear_gen"):
            st.session_state['slip_error'] = None
            st.rerun()
            
        if st.session_state.get('active_slips'):
            for idx, slip in enumerate(st.session_state['active_slips']):
                l1, l2 = slip['leg1'], slip['leg2']
                
                st.markdown(f"""
                <div style='background: #0d1117; border: 1px solid #FFD700; border-radius: 10px; padding: 15px; margin-bottom: 15px;'>
                    <div style='display: flex; justify-content: space-between;'>
                        <h3 style='margin: 0; color: white;'>SLIP #{idx+1}</h3>
                        <h3 style='margin: 0; color: #00FF7F;'>ALPHA SCORE: {slip['alpha_score']:.1f}/100</h3>
                    </div>
                    <hr style='border: 1px solid #333;'>
                    <div style='display: flex; gap: 20px;'>
                        <div style='flex: 1;'>
                            <p style='color: #888; font-size: 11px; margin: 0;'>LEG 1 ({l1['theater']})</p>
                            <h4 style='color: white; margin: 0;'>{l1['player']}</h4>
                            <p style='color: {l1.get('rec_color', '#FFF')}; font-weight: bold; margin: 5px 0;'>{l1['pick']} {l1['line']} {l1['prop_type']}</p>
                            <p style='color: #bbb; font-size: 12px;'>Proj: {l1['proj']:.1f} | Grade: {l1['grade']}</p>
                        </div>
                        <div style='flex: 1;'>
                            <p style='color: #888; font-size: 11px; margin: 0;'>LEG 2 ({l2['theater']})</p>
                            <h4 style='color: white; margin: 0;'>{l2['player']}</h4>
                            <p style='color: {l2.get('rec_color', '#FFF')}; font-weight: bold; margin: 5px 0;'>{l2['pick']} {l2['line']} {l2['prop_type']}</p>
                            <p style='color: #bbb; font-size: 12px;'>Proj: {l2['proj']:.1f} | Grade: {l2['grade']}</p>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                a_col1, a_col2 = st.columns(2)
                slip_key = f"slip_{idx}"
                
                with a_col1:
                    if st.button(f"🧠 Draft AI Analysis for Slip #{idx+1}", key=f"ai_{idx}", use_container_width=True):
                        with st.spinner("Groq is writing..."):
                            analysis = generate_slip_writeup(slip)
                            st.session_state['slip_writeups'][slip_key] = analysis
                            st.rerun()
                            
                with a_col2:
                    if slip_key in st.session_state['slip_writeups']:
                        if st.button(f"🎯 Snipe to Discord", key=f"disc_{idx}", type="primary", use_container_width=True):
                            webhook = st.secrets.get("DISCORD_WEBHOOK_URL", "")
                            if not webhook:
                                st.error("Add DISCORD_WEBHOOK_URL = 'your_url' to your secrets.toml!")
                            else:
                                success = push_to_discord(slip, st.session_state['slip_writeups'][slip_key], webhook)
                                if success: st.success("✅ Alpha Slip pushed to Discord!")
                                else: st.error("❌ Discord push failed. Check your Webhook URL.")
                
                if slip_key in st.session_state['slip_writeups']:
                    st.info(st.session_state['slip_writeups'][slip_key])

    # --- TAB 2: THE GRAVEYARD ---
    with tabs[2]:
        st.markdown("<h3 style='color: #A0A0A0; margin-top: 0px;'>🪦 THE GRAVEYARD</h3>", unsafe_allow_html=True)
        st.caption("These are Trap Lines, anomalies, or strict coin-flips. DO NOT BET.")
        
        if not graveyard:
            st.info("No trap lines found.")
        else:
            for i in range(0, len(graveyard), 2):
                col1, col2 = st.columns(2)
                with col1:
                    render_grade_card(graveyard[i], graveyard[i]['_theater'], is_dual=True, key_prefix=f"grave_{i}")
                with col2:
                    if i + 1 < len(graveyard):
                        render_grade_card(graveyard[i+1], graveyard[i+1]['_theater'], is_dual=True, key_prefix=f"grave_{i+1}")

    # --- TAB 3+: INDIVIDUAL MATCH TABS ---
    for i, match_key in enumerate(match_keys):
        with tabs[i+3]:
            colA, colB = st.columns([3, 1])
            with colB:
                st.button(f"🔒 LOCK MATCH IN PROPVAULT", key=f"lock_btn_{match_key}", on_click=lock_match_in_sheet, args=(match_key,), use_container_width=True, type="primary")

            team_kill_totals = {}
            for item in st.session_state['sweep_results'][match_key]:
                for card in item["data"]:
                    if card.get('prop_type', 'Kills') == 'Kills':
                        team_name = card.get('full_team', 'Unknown')
                        team_kill_totals[team_name] = team_kill_totals.get(team_name, 0) + card.get('proj', 0)
            
            for team_name, t_kills in team_kill_totals.items():
                if t_kills > 140:
                    st.warning(f"⚠️ **ECONOMY WARNING ({team_name}):** Listed players project for {t_kills:.1f} combined kills. Consider lowering expected rounds or increasing the Pacing Dampener.")

            sorted_items = sorted(
                st.session_state['sweep_results'][match_key], 
                key=lambda x: max([d.get('confidence', 0) for d in x['data']]), 
                reverse=True
            )
            
            for item in sorted_items:
                item['data'].sort(key=lambda d: d.get('confidence', 0), reverse=True)
            
            st.write("") 
            
            for item in sorted_items:
                theater_type = item["type"]
                cards = item["data"]

                is_locked = cards[0].get('Locked', False)

                if is_locked:
                    locked_grade = cards[0].get('grade', 'C')
                    delta_val = cards[0].get('delta', 0)
                    
                    if locked_grade == "S+": lock_color = "#FFD700"
                    elif locked_grade == "S": lock_color = "#FFC125"
                    elif locked_grade == "A+": lock_color = "#00FF7F"
                    elif locked_grade == "A": lock_color = "#00ccff"
                    else: lock_color = "#A0A0A0"
                        
                    d_color = "#00FF7F" if delta_val > 0 else "#FF4500"

                    st.markdown(f"""
                    <div style='border: 1px solid #333; border-left: 5px solid {lock_color}; padding: 12px 20px; border-radius: 6px; background-color: #0a0c10; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;'>
                        
                    <div style='flex: 2;'>
                        <h4 style='margin:0; color:#fff; font-family: "Inter", sans-serif; font-weight: 900; font-size: 18px;'>🔒 {cards[0].get('player', 'Player')}</h4>
                        <p style='margin:0; color:#888; font-size: 12px; font-family: "JetBrains Mono", monospace;'>{cards[0].get('full_team', 'Unk')} vs {cards[0].get('full_opp', 'Unk')} | {cards[0].get('prop_type', 'Prop').upper()}</p>
                    </div>

                    <div style='flex: 1; text-align: center;'>
                        <p style='margin:0; color:#888; font-size: 10px; text-transform: uppercase;'>Line / Proj</p>
                        <h5 style='margin:0; color:#eee; font-family: "JetBrains Mono", monospace; font-size: 16px;'>{cards[0].get('line', 0)} / <span style='color:{lock_color};'>{cards[0].get('proj', 0):.1f}</span></h5>
                    </div>

                    <div style='flex: 1; text-align: center;'>
                        <p style='margin:0; color:#888; font-size: 10px; text-transform: uppercase;'>Delta</p>
                        <h5 style='margin:0; color:{d_color}; font-family: "JetBrains Mono", monospace; font-size: 16px;'>{delta_val:+.1f}</h5>
                    </div>

                    <div style='flex: 1; text-align: right;'>
                        <p style='margin:0; color:#888; font-size: 10px; text-transform: uppercase;'>Pick (Grade)</p>
                        <h4 style='margin:0; color:{lock_color}; font-family: "Inter", sans-serif; font-weight: 900; font-size: 18px;'>{cards[0].get('pick', 'N/A')} <span style='font-size: 14px; opacity: 0.8;'>({locked_grade})</span></h4>
                    </div>
                    
                    <div style='flex: 1; text-align: right; border-left: 1px solid #333; padding-left: 10px;'>
                        <p style='margin:0; color:#888; font-size: 10px; text-transform: uppercase;'>Win Prob</p>
                        <h5 style='margin:0; color:#00ccff; font-family: "JetBrains Mono", monospace; font-size: 14px;'>{cards[0].get('prob', cards[0].get('win_prob', 0)):.1f}%</h5>
                        <p style='margin:4px 0 0 0; color:#888; font-size: 10px; text-transform: uppercase;'>Model Conf</p>
                        <h5 style='margin:0; color:#00FF7F; font-family: "JetBrains Mono", monospace; font-size: 14px;'>{cards[0].get('confidence', 0):.1f}%</h5>
                    </div>
                        
                    </div>
                    """, unsafe_allow_html=True)
                    continue 
                
                if len(cards) == 2:
                    col1, col2 = st.columns(2)
                    with col1: render_grade_card(cards[0], theater_type, is_dual=True, key_prefix=f"match1_{match_key}_{cards[0]['player']}")
                    with col2: render_grade_card(cards[1], theater_type, is_dual=True, key_prefix=f"match2_{match_key}_{cards[1]['player']}")
                else:
                    render_grade_card(cards[0], theater_type, is_dual=False, key_prefix=f"match_{match_key}_{cards[0]['player']}")
                st.write("---")