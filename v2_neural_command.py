import streamlit as st
import json
import os
import re
import numpy as np
from groq import Groq
from tavily import TavilyClient

# --- 1. CORE SETUP & MONOLITH V35.1 STYLING ---
st.set_page_config(page_title="Iron Guard V35.1", layout="wide", page_icon="📡")

# Session State Persistence
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

# --- 🛰️ GROUND-TRUTH MANIFEST (APRIL 2026) ---
MANIFEST = {
    "VALORANT": {
        "EF": {"full": "Eternal Fire", "rank": 35}, "PCIFIC": {"full": "PCIFIC Esports", "rank": 120},
        "FNC": {"full": "Fnatic", "rank": 4}, "VIT": {"full": "Team Vitality", "rank": 16},
        "SEN": {"full": "Sentinels", "rank": 1}, "LOUD": {"full": "LOUD", "rank": 5},
        "MIBR": {"full": "MIBR", "rank": 18}, "GENG": {"full": "Gen.G", "rank": 2}
    },
    "CS2": {
        "SPIRIT": {"full": "Team Spirit", "rank": 5}, "ASTR": {"full": "Astralis", "rank": 14},
        "VIT": {"full": "Team Vitality", "rank": 1}, "NAVI": {"full": "Natus Vincere", "rank": 2},
        "MOUZ": {"full": "MOUZ", "rank": 3}, "FAZE": {"full": "FaZe Clan", "rank": 4},
        "EF": {"full": "Eternal Fire", "rank": 8}, "1WIN": {"full": "1win", "rank": 67}
    }
}

CS2_ARCHETYPES = {"Anubis": 1.12, "Ancient": 1.12, "Dust 2": 1.15, "Inferno": 0.90, "Mirage": 1.05, "Nuke": 0.90, "Overpass": 1.00}
VAL_ROLES = {"Neon": "Duelist", "Phoenix": "Duelist", "Jett": "Duelist", "Waylay": "Duelist", "Reyna": "Duelist", "Raze": "Duelist", "Yoru": "Duelist", "Iso": "Duelist", "Clove": "Hybrid", "Gekko": "Initiator", "Sova": "Initiator", "Fade": "Initiator", "Skye": "Initiator", "Tejo": "Initiator", "Breach": "Initiator", "KAY/O": "Initiator", "Omen": "Controller", "Viper": "Controller", "Astra": "Controller", "Brimstone": "Controller", "Miks": "Controller", "Harbor": "Controller", "Cypher": "Sentinel", "Killjoy": "Sentinel", "Vyse": "Sentinel", "Veto": "Sentinel", "Sage": "Sentinel", "Deadlock": "Sentinel", "Chamber": "Sentinel"}
VAL_GRAVITY = {"Duelist": 1.15, "Hybrid": 1.10, "Initiator": 1.00, "Controller": 0.88, "Sentinel": 0.80}

def safe_float(v, d=0.0):
    try: return float(str(v).replace('%', '').strip()) if v else d
    except: return d

# --- 2. SOVEREIGN ENGINE (V35.1: GROUND-TRUTH) ---
def apply_sovereign_math(data, locked_player, locked_line, p_team_full, o_team_full, targets, m_kprs, heat, pacing, opp_dpr, r_total, swing_pct, duel_override, p_rank, o_rank, metric, theater):
    k_glob = safe_float(data.get('base_kpr'), 0.70)
    ok_win = safe_float(data.get('opening_win_pct'), 50.0)
    rank_gap = o_rank - p_rank

    hist_kills = [safe_float(k) for k in data.get('last_10_kills', []) if safe_float(k) > 10]
    hr_val = (len([k for k in hist_kills if k > locked_line]) / len(hist_kills)) * 100 if hist_kills else 70.0

    match_mult = 0.92 if rank_gap > 70 else 1.05 if rank_gap < -70 else 1.0
    duel_mult = 1.0 + (duel_override - 5.0) * 0.02
    
    per_map_proj = []
    for i in range(2):
        m_val = m_kprs[i] if m_kprs[i] > 0 else k_glob
        spec_mult = VAL_GRAVITY.get(VAL_ROLES.get(targets[i], "Initiator"), 1.0) if theater == "VALORANT" else CS2_ARCHETYPES.get(targets[i], 1.0)
        weighted_kpr = m_val * spec_mult * match_mult * (opp_dpr / 0.65 if opp_dpr > 0 else 1.0) * duel_mult * (1 - (heat / 100) * 0.12)
        per_map_proj.append(weighted_kpr * (r_total / 2))

    final_proj = sum(per_map_proj) * (1.08 if ok_win > 55 else 1.0)
    delta = final_proj - locked_line
    win_prob = (np.random.normal(final_proj, 5.5, 10000) > locked_line).mean() * 100

    return {
        "player": locked_player.upper(), "full_team": p_team_full, "full_opp": o_team_full,
        "grade": ("S" if delta > 6.0 else "A+" if delta > 3.0 else "B" if delta < -3.0 else "C"), 
        "color": ("#FFD700" if delta > 6.0 else "#00FF7F" if delta > 3.0 else "#FF4500" if delta < -3.0 else "#A0A0A0"), 
        "prob": win_prob, "kpr": f"{k_glob:.2f}", "proj": final_proj, "delta": delta, "is_nuke": (delta >= 10.0 and win_prob >= 85),
        "trace": f"{targets[0].upper()} | {targets[1].upper()}", "metric": metric, "line": locked_line, "hr": f"{hr_val:.0f}%", "gap": rank_gap
    }

def run_precision_research(cmd, metric, targets, m_kprs, heat, pacing, opp_dpr, r_total, swing, sync_duel, sync_ranks, opp_abbr, theater, live):
    theater_key = "VALORANT" if theater == "VALORANT" else "CS2"
    match = re.search(r"Grade\s+([A-Za-z0-9_]+)\s*\((.*?)\)", cmd, re.IGNORECASE)
    t_p, t_t_abbr = match.group(1).lower().strip(), match.group(2).upper().strip()
    u_line = float(re.findall(r"(\d+\.\d+|\d+)", cmd)[-1])
    
    # Manifest Resolution
    p_team_data = MANIFEST[theater_key].get(t_t_abbr, {"full": t_t_abbr, "rank": 60})
    o_team_data = MANIFEST[theater_key].get(opp_abbr.upper(), {"full": opp_abbr.upper(), "rank": 110})

    with st.status(f"🛰️ {theater} SCAN: {t_p.upper()} ({p_team_data['full']})"):
        domain = "vlr.gg" if theater == "VALORANT" else "hltv.org"
        q = f"site:{domain} {t_p} {p_team_data['full']} 2026 last 10 series combined map 1 2 kills vs {o_team_data['full']}"
        res = tavily_client.search(query=q, max_results=5)
        w_data = "\n".join([r['content'] for r in res['results']])[:4500]
        sys_msg = "Return JSON ONLY. Keys: base_kpr (float), opening_win_pct (float), last_10_kills (list of ints)."
        c = groq_client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": f"Extract stats for {t_p} on {p_team_data['full']}: {w_data}"}], response_format={"type": "json_object"}, temperature=0)
        raw = json.loads(c.choices[0].message.content)
    
    if sync_duel: st.session_state['auto_duel'] = safe_float(raw.get('opening_win_pct', 50.0)) / 10.0
    if sync_ranks:
        st.session_state['p_rank'] = p_team_data['rank']
        st.session_state['o_rank'] = o_team_data['rank']

    st.session_state['last_intel'] = apply_sovereign_math(raw, t_p, u_line, p_team_data['full'], o_team_data['full'], targets, m_kprs, heat, pacing, opp_dpr, r_total, swing, st.session_state['auto_duel'], st.session_state['p_rank'], st.session_state['o_rank'], metric, theater)
    st.rerun()

# --- 3. UI LAYER ---
with st.sidebar:
    st.header("📡 COMMAND CENTER")
    theater_sel = st.sidebar.radio("Theater", ["CS2", "VALORANT"])
    metric_sel = st.sidebar.segmented_control("Metric", options=["KILLS", "HEADSHOTS"], default="KILLS")
    
    with st.expander("👤 PLAYER TACTICAL", expanded=True):
        label = "Map" if theater_sel == "CS2" else "Agent"
        target_list = list(CS2_ARCHETYPES.keys()) if theater_sel == "CS2" else list(VAL_ROLES.keys())
        t1, t1_k = st.selectbox(f"{label} 1", target_list, help="HINT: Gravity check."), safe_float(st.text_input(f"M1 KPR", "", help="HINT: Leave blank for baseline."))
        t2, t2_k = st.selectbox(f"{label} 2", target_list), safe_float(st.text_input(f"M2 KPR", ""))
        st.write("---")
        sync_ranks = st.checkbox("🛰️ Auto-Sync Ranks", value=True, help="HINT: Uses the hard-coded Manifest.")
        st.session_state['p_rank'] = st.number_input("Your Rank", 1, 300, value=st.session_state['p_rank'], disabled=sync_ranks)
        sync_duel = st.checkbox("🛰️ Auto-Sync Open Duel", value=True)
        st.session_state['auto_duel'] = st.slider("Open Duel (1-10)", 1.0, 10.0, value=st.session_state['auto_duel'], step=0.1, disabled=sync_duel)
        r_total_v = safe_float(st.text_input("Total Rounds", "44.0"))
        heat_val = st.slider("Teammate Heat", 0, 100, 0)
        
    with st.expander("🛡️ OPPONENT TACTICAL", expanded=True):
        opp_name, opp_dpr = st.text_input("Opponent (Abbr)", "PCIFIC"), safe_float(st.text_input("Opponent DPR", "0.65"))
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
<div><div class="stat-lbl">{i['metric']} PROJ</div><div class="stat-val" style="color: {i['color']};">{i['proj']:.1f}</div></div>
<div><div class="stat-lbl">Open Duel</div><div class="stat-val">{st.session_state['auto_duel']:.1f}</div></div>
</div>
<div class="decision-line" style="color: {i['color']};">{"OVER" if i['delta'] > 0 else "UNDER"} {i['line']} {i['metric']} {"▲" if i['delta'] > 0 else "▼"}</div>
<div style="margin-top: 40px; font-family: 'JetBrains Mono'; color: rgba(255,255,255,0.4); font-size: 22px;">{i['trace']}</div>
</div></div>"""
    st.markdown(card_html, unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.metric("CONFIDENCE", "100%" if i['proj'] > 0 else "0%"); st.badge("Sovereign", color="primary")
    with c2: st.metric("DELTA", f"{i['delta']:+.1f}"); st.badge("Strike Delta", color="blue")
    with c3: st.metric("L10 HIT RATE", i['hr']); st.badge("Momentum", color="violet")
    with c4: st.metric("GLOBAL KPR", i['kpr']); st.badge("Historical", color="gray")
    with c5: st.metric("RANK GAP", f"{i['gap']:+d} Pos"); st.badge("Mismatch", color="orange")
    with c6: st.metric("NUCLEAR FLAG", "FLAGGED" if i['is_nuke'] else "CLEAN"); st.badge("Sanity", color="red" if i['is_nuke'] else "green")

if prompt := st.chat_input("Grade Player (Team) Line"):
    run_precision_research(prompt, metric_sel, [t1, t2], [t1_k, t2_k], heat_val, pacing_val, opp_dpr, r_total_v, 2.18, sync_duel, sync_ranks, opp_name, theater_sel, True)