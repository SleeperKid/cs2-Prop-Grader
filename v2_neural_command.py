import streamlit as st
import json
import os
import re
import numpy as np
from groq import Groq
from tavily import TavilyClient

# --- 1. CORE SETUP & MONOLITH V29.1 STYLING ---
st.set_page_config(page_title="Iron Guard V29.1", layout="wide", page_icon="📡")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=JetBrains+Mono:wght@500;800&display=swap');
    .stApp { background-color: #010204; color: #e0e0e0; }
    
    .sovereign-card {
        background: linear-gradient(135deg, #0d1117 0%, #1c2333 50%, #0d1117 100%);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 50px; padding: 70px; margin-bottom: 30px;
        box-shadow: 0 60px 150px rgba(0, 0, 0, 1);
        position: relative; overflow: hidden;
    }
    
    .nuclear-alert {
        background: rgba(255, 69, 0, 0.2);
        color: #FF4500;
        border: 1px solid #FF4500;
        padding: 5px 15px;
        border-radius: 10px;
        font-family: 'JetBrains Mono';
        font-size: 14px;
        font-weight: 800;
        display: inline-block;
        margin-bottom: 15px;
    }

    .grade-display { 
        font-family: 'Inter', sans-serif; font-weight: 900; 
        letter-spacing: -60px; line-height: 1; margin: 0;
        font-size: 850px; 
        color: rgba(255, 255, 255, 0.03); 
        position: absolute; top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        z-index: 0; pointer-events: none;
    }
    
    .card-content { position: relative; z-index: 1; text-align: left; }
    .player-name { font-family: 'Inter', sans-serif; font-weight: 900; font-size: 40px; text-transform: uppercase; color: white; margin-bottom: 5px; }
    .match-header { font-family: 'JetBrains Mono'; color: #FFD700; margin-bottom: 30px; font-weight: 800; font-size: 24px; text-transform: uppercase; }
    .decision-line { font-family: 'JetBrains Mono', monospace; font-weight: 800; font-size: 42px; text-transform: uppercase; margin-top: 25px; }
    .stat-val { color: white; font-size: 42px; font-weight: 800; margin-bottom: 25px; }
    .stat-lbl { font-size: 12px; color: rgba(255,255,255,0.4); text-transform: uppercase; margin-bottom: 8px; letter-spacing: 2px; }
</style>
""", unsafe_allow_html=True)

try:
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    tavily_client = TavilyClient(api_key=st.secrets["TAVILY_API_KEY"])
except Exception: st.error("API Error: Check Secrets."); st.stop()

# --- 🧠 THEATER DATA ---
CS2_ARCHETYPES = {"Ancient": 1.12, "Anubis": 1.12, "Dust 2": 1.15, "Mirage": 1.05, "Nuke": 0.90, "Inferno": 0.90, "Overpass": 1.00, "Vertigo": 1.05}
VAL_ROLES = {"Neon": "Duelist", "Phoenix": "Duelist", "Jett": "Duelist", "Waylay": "Duelist", "Reyna": "Duelist", "Raze": "Duelist", "Yoru": "Duelist", "Iso": "Duelist", "Clove": "Hybrid", "Gekko": "Initiator", "Sova": "Initiator", "Fade": "Initiator", "Skye": "Initiator", "Tejo": "Initiator", "Breach": "Initiator", "KAY/O": "Initiator", "Omen": "Controller", "Viper": "Controller", "Astra": "Controller", "Brimstone": "Controller", "Miks": "Controller", "Harbor": "Controller", "Cypher": "Sentinel", "Killjoy": "Sentinel", "Vyse": "Sentinel", "Veto": "Sentinel", "Sage": "Sentinel", "Deadlock": "Sentinel", "Chamber": "Sentinel"}
VAL_GRAVITY = {"Duelist": 1.12, "Hybrid": 1.08, "Initiator": 1.00, "Controller": 0.88, "Sentinel": 0.82}

# --- 🛠️ VAULT ENGINE ---
def get_vault_path(theater):
    return "CS2_Tactical.json" if theater == "CS2" else "Val_Tactical.json"

def load_from_vault(player, opponent, theater):
    path = get_vault_path(theater)
    if not os.path.exists(path): return None
    with open(path, "r") as f:
        try:
            vault = json.load(f)
            if not isinstance(vault, list): return None
            for entry in vault:
                if isinstance(entry, dict) and entry.get('player') == player.upper() and entry.get('opponent') == opponent.upper():
                    return entry.get('raw_data')
        except: return None
    return None

def save_to_vault(player, opponent, theater, raw_data):
    path = get_vault_path(theater)
    vault = []
    if os.path.exists(path):
        with open(path, "r") as f:
            try:
                loaded = json.load(f)
                vault = loaded if isinstance(loaded, list) else []
            except: vault = []
    updated = False
    for entry in vault:
        if isinstance(entry, dict) and entry.get('player') == player.upper() and entry.get('opponent') == opponent.upper():
            entry['raw_data'] = raw_data
            updated = True
            break
    if not updated:
        vault.append({"player": player.upper(), "opponent": opponent.upper(), "raw_data": raw_data})
    with open(path, "w") as f:
        json.dump(vault, f, indent=2)

def safe_float(val, default=0.0):
    try: return float(str(val).replace('%', '').strip()) if val else default
    except: return default

# --- 2. SOVEREIGN ENGINE (V29.1: 10% THROTTLE) ---
def apply_sovereign_math(data, locked_player, locked_line, locked_team, opp_team, targets, m_kprs, m_hs, heat, pacing, opp_dpr, r_total, swing_pct, metric="KILLS", theater="CS2"):
    k_glob = safe_float(data.get('base_kpr'), 0.70)
    hs_glob = safe_float(data.get('hs_pct'), 50.0)
    ok_win = safe_float(data.get('opening_win_pct'), 50.0)
    p_rank, o_rank = int(safe_float(data.get('team_rank', 60))), int(safe_float(data.get('opp_rank', 110)))
    rank_gap = o_rank - p_rank

    swing_mult = 1.0 + (swing_pct / 100)
    match_mult = 0.95 if rank_gap > 70 else 1.05 if rank_gap < -70 else 1.0
    ode_mult = (opp_dpr / 0.67 if opp_dpr > 0 else 1.0)
    pacing_mult = {"Fast": 1.05, "Slow": 0.95, "Auto": 1.0}.get(pacing, 1.0)
    
    per_map_proj = []
    per_map_hs = []
    
    for i in range(2):
        t_name = targets[i]
        m_val = m_kprs[i] if m_kprs[i] > 0 else (safe_float(data.get(f'map{i+1}_kpr')) or k_glob)
        
        specific_mult = 1.0
        if theater == "VALORANT":
            role = VAL_ROLES.get(t_name, "Initiator")
            specific_mult = VAL_GRAVITY.get(role, 1.0)
        else:
            specific_mult = CS2_ARCHETYPES.get(t_name, 1.0)
            
        weighted_kpr = m_val * specific_mult * swing_mult * match_mult * ode_mult * pacing_mult * (1 - (heat / 100) * 0.12)
        per_map_proj.append(weighted_kpr * (r_total / 2))
        per_map_hs.append(m_hs[i] if m_hs[i] > 0 else (safe_float(data.get(f'map{i+1}_hs_pct')) or hs_glob))

    total_kills = sum(per_map_proj) * (1.05 if ok_win > 55 else 1.0)
    
    if metric == "HEADSHOTS":
        avg_hs = np.mean(per_map_hs)
        hs_multiplier = (avg_hs / 100) * (1.8 if theater == "VALORANT" else 1.0)
        final_proj = total_kills * hs_multiplier
    else:
        final_proj = total_kills
        
    # --- SANITY PROTOCOL: 10% DAMPENING FIELD ---
    is_nuclear = False
    ceiling_limit = locked_line * 1.5
    if final_proj > ceiling_limit:
        is_nuclear = True
        excess = final_proj - ceiling_limit
        # Throttle the extreme portion by 10% (0.90 multiplier)
        final_proj = ceiling_limit + (excess * 0.90)
        
    delta = final_proj - locked_line
    return {
        "player": locked_player.upper(), "match": f"{locked_team.upper()} vs {opp_team.upper()}", 
        "grade": ("S" if delta > 6.0 else "A+" if delta > 3.0 else "B" if delta < -3.0 else "C"), 
        "color": ("#FFD700" if delta > 6.0 else "#00FF7F" if delta > 3.0 else "#FF4500" if delta < -3.0 else "#A0A0A0"), 
        "arrow": ("▲" if delta > 3.0 else "▼" if delta < -3.0 else "—"), 
        "d_text": ("OVER" if delta > 0 else "UNDER"), "prob": (np.random.normal(final_proj, 5.5, 10000) > locked_line).mean() * 100,
        "kpr": f"{k_glob:.2f}", "proj": final_proj, "delta": delta, "is_nuclear": is_nuclear,
        "trace": f"{targets[0].upper()} {m_kprs[0]:.2f} | {targets[1].upper()} {m_kprs[1]:.2f}", 
        "metric": metric, "line": locked_line, "hr": f"{safe_float(data.get('l10_hit_rate'), 70.0):.0f}%", "gap": rank_gap, "swing": f"{swing_pct:+.2f}%"
    }

# --- [REST OF CODE REMAINS UNCHANGED: run_precision_research & UI] ---
def run_precision_research(command, metric, targets, m_kprs, m_hs, heat, pacing, opp_dpr, r_total, swing_pct, opp_team, theater, force_live):
    match = re.search(r"Grade\s+([A-Za-z0-9_]+)\s*\((.*?)\)", command, re.IGNORECASE)
    if not match: st.error("Format: Grade Player (Team) Line"); st.stop()
    t_p, t_t = match.group(1).lower().strip(), match.group(2).strip()
    u_line = float(re.findall(r"(\d+\.\d+|\d+)", command)[-1])
    
    if not force_live:
        archived = load_from_vault(t_p, opp_team, theater)
        if archived: return apply_sovereign_math(archived, t_p, u_line, t_t, opp_team, targets, m_kprs, m_hs, heat, pacing, opp_dpr, r_total, swing_pct, metric, theater)

    with st.status(f"🛰️ {theater} SCAN: {t_p.upper()}") as status:
        query = f"vlr.gg 2026 stats {t_p} {t_t} rank vs {opp_team}" if theater == "VALORANT" else f"HLTV 2026 stats {t_p} {t_t} world rank vs {opp_team}"
        res = tavily_client.search(query=query, max_results=3)
        web_data = "\n".join([r['content'] for r in res['results']])[:3000]

    prompt = f"JSON for {t_p} ({t_t}) vs {opp_team}. Data: {web_data}. KEYS: team_rank (int), opp_rank (int), base_kpr (float), hs_pct (float), rating_num (float), opening_win_pct (float), l10_hit_rate (float). No fractions."
    comp = groq_client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0)
    raw = json.loads(comp.choices[0].message.content)
    save_to_vault(t_p, opp_team, theater, raw)
    return apply_sovereign_math(raw, t_p, u_line, t_t, opp_team, targets, m_kprs, m_hs, heat, pacing, opp_dpr, r_total, swing_pct, metric, theater)

if prompt := st.chat_input("Grade Player (Team) Line"):
    with st.chat_message("assistant"):
        intel = run_precision_research(prompt, metric_sel, [t1, t2], [t1_k, t2_k], [t1_h, t2_h], heat_val, pacing_val, opp_dpr, r_total_v, swing_v, opp_name, theater_sel, force_live)
        
        st.markdown(f"""
            <div class="sovereign-card" style="border-top: 35px solid {intel['color']};">
                <div class="grade-display">{intel['grade']}</div>
                <div class="card-content">
                    {f'<div class="nuclear-alert">☢️ CEILING ALERT: LIGHT DAMPENING ACTIVE</div>' if intel['is_nuclear'] else ''}
                    <div class="player-name">{intel['player']}</div>
                    <div class="match-header">{intel['match']} (MAPS 1+2)</div>
                    <div style="display: flex; gap: 80px; justify-content: center;">
                        <div><div class="stat-lbl">Win Prob</div><div class="stat-val">{intel['prob']:.1f}%</div></div>
                        <div><div class="stat-lbl">{intel['metric']} PROJ</div><div class="stat-val" style="color: {intel['color']};">{intel['proj']:.1f}</div></div>
                        <div><div class="stat-lbl">Swing Boost</div><div class="stat-val">{intel['swing']}</div></div>
                    </div>
                    <div class="decision-line" style="color: {intel['color']};">{intel['d_text']} {intel['line']} {intel['metric']} {intel['arrow']}</div>
                    <div style="margin-top: 40px; font-family: 'JetBrains Mono'; color: rgba(255,255,255,0.4); font-size: 22px;">{intel['trace']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("PROJECTION", f"{intel['proj']:.1f}")
        c2.metric("DELTA", f"{intel['delta']:+.1f}")
        c3.metric("L10 HIT RATE", intel['hr'])
        c4.metric("GLOBAL KPR", intel['kpr'])
        c5.metric("RANK GAP", f"{intel['gap']:+d} Pos")
        c6.metric("NUCLEAR FLAG", "ACTIVE" if intel['is_nuclear'] else "CLEAN")