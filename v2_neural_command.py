import streamlit as st
import json
import os
import re
import numpy as np
from groq import Groq
from tavily import TavilyClient

# --- 1. CORE SETUP & MONOLITH V39.0 STYLING ---
st.set_page_config(page_title="Iron Guard V39.0", layout="wide", page_icon="📡")

# Initialize Session State
if 'last_intel' not in st.session_state: st.session_state['last_intel'] = None
if 'auto_duel' not in st.session_state: st.session_state['auto_duel'] = 5.0
if 'p_rank' not in st.session_state: st.session_state['p_rank'] = 60
if 'o_rank' not in st.session_state: st.session_state['o_rank'] = 110

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=JetBrains+Mono:wght@500;800&display=swap');
    .stApp { background-color: #010204; color: #e0e0e0; }
    .sovereign-card {
        background: linear-gradient(135deg, #0d1117 0%, #1c2333 50%, #0d1117 100%);
        border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 50px; 
        padding: 70px; margin-bottom: 30px; box-shadow: 0 60px 150px rgba(0, 0, 0, 1);
        position: relative; overflow: hidden;
    }
    .nuke-play-badge {
        background: linear-gradient(90deg, #FFD700, #FF8C00); color: black;
        padding: 8px 20px; border-radius: 12px; font-family: 'Inter';
        font-size: 16px; font-weight: 900; display: inline-block; margin-bottom: 15px;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.4);
    }
    .grade-display { 
        font-family: 'Inter', sans-serif; font-weight: 900; letter-spacing: -60px; 
        line-height: 1; margin: 0; font-size: 850px; color: rgba(255, 255, 255, 0.05); 
        position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
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
except: st.error("📡 API ERROR: Check Secrets."); st.stop()

# --- 1. LOAD THE DATA FROM YOUR NEW MANIFEST ---
def load_live_ranks():
    manifest_path = "cs2_manifest.json"
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            return json.load(f)
    return {} # Return empty dict if file is missing

CS2_LIVE = load_live_ranks()

# --- 2. UPDATE YOUR MANIFEST DICTIONARY ---
MANIFEST = {
    "VALORANT": {
        "NAVI": {"full": "Natus Vincere", "rank": 18},
        "TL": {"full": "Team Liquid", "rank": 2},
        # ... your other Valorant teams
    },
    "CS2": CS2_LIVE  # 🚀 REMOVED THE EXTRA CURLY BRACES HERE
}

CS2_ARCHETYPES = {"Anubis": 1.12, "Ancient": 1.12, "Dust 2": 1.15, "Inferno": 0.90, "Mirage": 1.05, "Nuke": 0.90, "Overpass": 1.00}
VAL_GRAVITY = {"Duelist": 1.15, "Hybrid": 1.10, "Initiator": 1.00, "Controller": 0.88, "Sentinel": 0.80}
VAL_AGENTS = ["Neon", "Jett", "Waylay", "Phoenix", "Reyna", "Raze", "Yoru", "Iso", "Clove", "Gekko", "Sova", "Fade", "Skye", "Tejo", "Breach", "KAY/O", "Omen", "Viper", "Astra", "Brimstone", "Miks", "Harbor", "Cypher", "Killjoy", "Vyse", "Veto", "Sage", "Deadlock", "Chamber"]

def safe_float(v, d=0.0):
    try: return float(str(v).replace('%', '').strip()) if v else d
    except: return d

# --- 2. SOVEREIGN ENGINE (V39.0: AGENT-LOCKED) ---
def apply_sovereign_math(data, p_name, u_line, full_p, full_o, targets, m_vals, heat, pacing, opp_dpr, r_total, theater):
    raw_stat = safe_float(data.get('base_stat'), 150.0 if theater == "VALORANT" else 0.70)
    k_glob = (raw_stat / 150) if theater == "VALORANT" else raw_stat
    rank_gap = st.session_state['o_rank'] - st.session_state['p_rank']
    
    hist_kills = [safe_float(k) for k in data.get('last_10_kills', []) if safe_float(k) > 10]
    hr_val = (len([k for k in hist_kills if k > u_line]) / len(hist_kills)) * 100 if hist_kills else 70.0

    match_mult = 0.92 if rank_gap > 70 else 1.05 if rank_gap < -70 else 1.0
    duel_mult = 1.0 + (st.session_state['auto_duel'] - 5.0) * 0.02
    
    per_map_proj = []
    for i in range(2):
        m_kpr = (m_vals[i] / 150) if (theater == "VALORANT" and m_vals[i] > 0) else (m_vals[i] if m_vals[i] > 0 else k_glob)
        spec_mult = VAL_GRAVITY.get(targets[i], 1.0) if theater == "VALORANT" else CS2_ARCHETYPES.get(targets[i], 1.0)
        pacing_mult = 1.05 if pacing == "Fast" else 0.95 if pacing == "Slow" else 1.0
        
        weighted_kpr = m_kpr * spec_mult * match_mult * (opp_dpr / 0.65) * duel_mult * pacing_mult * (1 - (heat / 100) * 0.12)
        per_map_proj.append(weighted_kpr * (r_total / 2))

    final_proj = sum(per_map_proj) * (1.08 if safe_float(data.get('opening_win_pct')) > 55 else 1.0)
    delta = final_proj - u_line
    win_prob = (np.random.normal(final_proj, 5.5, 10000) > u_line).mean() * 100

    return {
        "player": p_name.upper(), "full_team": full_p, "full_opp": full_o,
        "grade": ("S" if delta > 6.0 else "A+" if delta > 3.0 else "B" if delta < -3.0 else "C"),
        "color": ("#FFD700" if delta > 6.0 else "#00FF7F" if delta > 3.0 else "#FF4500" if delta < -3.0 else "#A0A0A0"),
        "prob": win_prob, "stat_baseline": raw_stat, "proj": final_proj, "delta": delta,
        "is_nuke": (delta >= 10.0 and win_prob >= 85), "hr": f"{hr_val:.0f}%", "gap": rank_gap, "trace": f"{targets[0].upper()} | {targets[1].upper()}"
    }

def run_precision_research(cmd, targets, m_vals, heat, pacing, opp_dpr, r_total, sync_duel, sync_ranks, opp_abbr, theater):
    theater_key = "VALORANT" if theater == "VALORANT" else "CS2"
    domain = "vlr.gg" if theater == "VALORANT" else "hltv.org"
    
    match = re.search(r"Grade\s+([A-Za-z0-9_]+)\s*\((.*?)\)", cmd, re.IGNORECASE)
    t_p, t_t_abbr = match.group(1).lower().strip(), match.group(2).upper().strip()
    u_line = float(re.findall(r"(\d+\.\d+|\d+)", cmd)[-1])
    
    p_team = MANIFEST[theater_key].get(t_t_abbr, {"full": t_t_abbr, "rank": 60})
    o_team = MANIFEST[theater_key].get(opp_abbr.upper(), {"full": opp_abbr.upper(), "rank": 110})

    with st.status(f"🛰️ {theater} SCAN: {t_p.upper()} vs {o_team['full']}"):
        stat_target = "ADR (Average Damage Per Round)" if theater == "VALORANT" else "KPR (Kills Per Round)"
        q = f"site:{domain} {t_p} {p_team['full']} 2026 {stat_target} season stats combined totals"
        res = tavily_client.search(query=q, max_results=5)
        w_data = "\n".join([r['content'] for r in res['results']])[:4500]
        
        sys_msg = f"Return JSON ONLY. Focus on {t_p} ({p_team['full']})."
        user_p = f"Extract stats for {t_p}: {w_data}. Keys: base_stat (float), opening_win_pct (float), last_10_kills (list of ints)."
        
        c = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant", messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_p}],
            response_format={"type": "json_object"}, temperature=0
        )
        raw = json.loads(c.choices[0].message.content)

    if sync_duel: st.session_state['auto_duel'] = safe_float(raw.get('opening_win_pct', 50.0)) / 10.0
    if sync_ranks:
        st.session_state['p_rank'], st.session_state['o_rank'] = p_team['rank'], o_team['rank']

    st.session_state['last_intel'] = apply_sovereign_math(raw, t_p, u_line, p_team['full'], o_team['full'], targets, m_vals, heat, pacing, opp_dpr, r_total, theater)
    st.rerun()

# --- 3. UI LAYER ---
with st.sidebar:
    st.header("📡 COMMAND CENTER")
    theater_sel = st.sidebar.radio("Theater", ["VALORANT", "CS2"])
    
    with st.expander("👤 PLAYER TACTICAL", expanded=True):
        label = "Agent" if theater_sel == "VALORANT" else "Map"
        stat_lbl = "ADR" if theater_sel == "VALORANT" else "KPR"
        target_list = VAL_AGENTS if theater_sel == "VALORANT" else list(CS2_ARCHETYPES.keys())
        
        t1, t1_v = st.selectbox(f"{label} 1", target_list), safe_float(st.text_input(f"M1 {stat_lbl}", ""))
        t2, t2_v = st.selectbox(f"{label} 2", target_list), safe_float(st.text_input(f"M2 {stat_lbl}", ""))
        st.write("---")
        sync_ranks = st.checkbox("🛰️ Auto-Sync Ranks", value=True)
        st.session_state['p_rank'] = st.number_input("Team Rank", 1, 300, value=st.session_state['p_rank'], disabled=sync_ranks)
        sync_duel = st.checkbox("🛰️ Auto-Sync Open Duel", value=True)
        st.session_state['auto_duel'] = st.slider("Open Duel (1-10)", 1.0, 10.0, value=st.session_state['auto_duel'], step=0.1, disabled=sync_duel)
        r_total_v = safe_float(st.text_input("Total Rounds", "44.0"))
        heat_val = st.slider("Teammate Heat", 0, 100, 0)
        
    with st.expander("🛡️ OPPONENT TACTICAL", expanded=True):
        opp_name, opp_dpr = st.text_input("Opponent (Abbr)", "PCF"), safe_float(st.text_input("Opponent DPR", "0.65"))
        st.session_state['o_rank'] = st.number_input("Opponent Rank", 1, 300, value=st.session_state['o_rank'], disabled=sync_ranks)
        pacing_val = st.selectbox("Pacing", ["Auto", "Fast", "Slow"])

if st.session_state['last_intel']:
    i = st.session_state['last_intel']
    card_html = f"""
<div class="sovereign-card" style="border-top: 35px solid {i['color']};">
<div class="grade-display">{i['grade']}</div>
<div class="card-content">
{f'<div class="nuke-play-badge">🚀 NUKE PLAY: +10 DELTA LOCK</div>' if i['is_nuke'] else ''}
<div class="player-name">{i['player']}</div>
<div class="match-header">{i['full_team']} vs {i['full_opp']}</div>
<div style="display: flex; gap: 80px; justify-content: center;">
<div><div class="stat-lbl">Win Prob</div><div class="stat-val">{i['prob']:.1f}%</div></div>
<div><div class="stat-lbl">KILLS PROJ</div><div class="stat-val" style="color: {i['color']};">{i['proj']:.1f}</div></div>
<div><div class="stat-lbl">Open Duel</div><div class="stat-val">{st.session_state['auto_duel']:.1f}</div></div>
</div>
<div class="decision-line" style="color: {i['color']};">{"OVER" if i['delta'] > 0 else "UNDER"} {33.5} KILLS {"▲" if i['delta'] > 0 else "▼"}</div>
<div style="margin-top: 40px; font-family: 'JetBrains Mono'; color: rgba(255,255,255,0.4); font-size: 22px;">{i['trace']}</div>
</div></div>"""
    st.markdown(card_html, unsafe_allow_html=True)
    
    # 5-Column Grid: Metrics ONLY (No Badges)
    c1, c2, c3, c4, c5 = st.columns(5)
    stat_type = "ADR" if theater_sel == "VALORANT" else "KPR"
    with c1: st.metric("DELTA", f"{i['delta']:+.1f}")
    with c2: st.metric("L10 HIT RATE", i['hr'])
    with c3: st.metric(f"GLOBAL {stat_type}", f"{i['stat_baseline']:.1f}")
    with c4: st.metric("RANK GAP", f"{i['gap']:+d} Pos")
    with c5: st.metric("NUCLEAR FLAG", "FLAGGED" if i['is_nuke'] else "CLEAN")

if prompt := st.chat_input("Grade Player (Abbr) Line"):
    run_precision_research(prompt, [t1, t2], [t1_v, t2_v], heat_val, pacing_val, opp_dpr, r_total_v, sync_duel, sync_ranks, opp_name, theater_sel)