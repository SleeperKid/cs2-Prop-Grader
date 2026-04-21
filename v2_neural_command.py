import streamlit as st
import json
import os
import re
import numpy as np
from groq import Groq
from tavily import TavilyClient

# --- 1. CORE SETUP & MONOLITH V32.0 STYLING ---
st.set_page_config(page_title="Iron Guard V32.0", layout="wide", page_icon="📡")

if 'auto_duel' not in st.session_state:
    st.session_state['auto_duel'] = 5.0

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
        background: rgba(255, 69, 0, 0.2); color: #FF4500; border: 1px solid #FF4500;
        padding: 5px 15px; border-radius: 10px; font-family: 'JetBrains Mono';
        font-size: 14px; font-weight: 800; display: inline-block; margin-bottom: 15px;
    }
    .nuke-play-badge {
        background: linear-gradient(90deg, #FFD700, #FF8C00); color: black;
        padding: 8px 20px; border-radius: 12px; font-family: 'Inter';
        font-size: 16px; font-weight: 900; display: inline-block; margin-bottom: 15px;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.4);
    }
    .grade-display { 
        font-family: 'Inter', sans-serif; font-weight: 900; letter-spacing: -60px; 
        line-height: 1; margin: 0; font-size: 850px; color: rgba(255, 255, 255, 0.03); 
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
except Exception: st.error("📡 CONNECTION ERROR: Verify API Secrets."); st.stop()

# --- 🧠 THEATER DATA ---
CS2_ARCHETYPES = {"Anubis": 1.12, "Ancient": 1.12, "Dust 2": 1.15, "Inferno": 0.90, "Mirage": 1.05, "Nuke": 0.90, "Overpass": 1.00}
VAL_ROLES = {"Neon": "Duelist", "Phoenix": "Duelist", "Jett": "Duelist", "Waylay": "Duelist", "Reyna": "Duelist", "Raze": "Duelist", "Yoru": "Duelist", "Iso": "Duelist", "Clove": "Hybrid", "Gekko": "Initiator", "Sova": "Initiator", "Fade": "Initiator", "Skye": "Initiator", "Tejo": "Initiator", "Breach": "Initiator", "KAY/O": "Initiator", "Omen": "Controller", "Viper": "Controller", "Astra": "Controller", "Brimstone": "Controller", "Miks": "Controller", "Harbor": "Controller", "Cypher": "Sentinel", "Killjoy": "Sentinel", "Vyse": "Sentinel", "Veto": "Sentinel", "Sage": "Sentinel", "Deadlock": "Sentinel", "Chamber": "Sentinel"}
VAL_GRAVITY = {"Duelist": 1.15, "Hybrid": 1.10, "Initiator": 1.00, "Controller": 0.88, "Sentinel": 0.80}

def get_vault_path(theater): return "CS2_Tactical.json" if theater == "CS2" else "Val_Tactical.json"

def load_from_vault(player, opponent, theater):
    path = get_vault_path(theater)
    if not os.path.exists(path): return None
    with open(path, "r") as f:
        try:
            vault = json.load(f)
            for entry in [e for e in vault if isinstance(e, dict)]:
                if entry.get('player') == player.upper() and entry.get('opponent') == opponent.upper(): return entry.get('raw_data')
        except: return None
    return None

def save_to_vault(player, opponent, theater, raw_data):
    path = get_vault_path(theater)
    vault = []
    if os.path.exists(path):
        with open(path, "r") as f:
            try:
                l = json.load(f)
                vault = l if isinstance(l, list) else []
            except: vault = []
    updated = False
    for entry in vault:
        if isinstance(entry, dict) and entry.get('player') == player.upper() and entry.get('opponent') == opponent.upper():
            entry['raw_data'] = raw_data
            updated = True
            break
    if not updated: vault.append({"player": player.upper(), "opponent": opponent.upper(), "raw_data": raw_data})
    with open(path, "w") as f: json.dump(vault, f, indent=2)

def safe_float(v, d=0.0):
    try: return float(str(v).replace('%', '').strip()) if v else d
    except: return d

# --- 2. SOVEREIGN ENGINE (V32.0: STRIKE-POINT) ---
def apply_sovereign_math(data, locked_player, locked_line, locked_team, opp_team, targets, m_kprs, m_hs, heat, pacing, opp_dpr, r_total, swing_pct, duel_override, metric="KILLS", theater="CS2"):
    k_glob = safe_float(data.get('base_kpr'), 0.70)
    ok_win = safe_float(data.get('opening_win_pct'), 50.0)
    p_rank, o_rank = int(safe_float(data.get('team_rank', 60))), int(safe_float(data.get('opp_rank', 110)))
    rank_gap = o_rank - p_rank

    conf = 20 if opp_dpr > 0 else 0
    if m_kprs[0] > 0: conf += 40
    if m_kprs[1] > 0: conf += 40

    swing_mult = 1.0 + (swing_pct / 100)
    match_mult = 0.92 if rank_gap > 70 else 1.05 if rank_gap < -70 else 1.0
    ode_mult = (opp_dpr / 0.65 if opp_dpr > 0 else 1.0)
    pacing_mult = {"Fast": 1.05, "Slow": 0.95, "Auto": 1.0}.get(pacing, 1.0)
    duel_mult = 1.0 + (duel_override - 5.0) * 0.02
    
    per_map_proj = []
    per_map_hs = []
    for i in range(2):
        t_name = targets[i]
        m_val = m_kprs[i] if m_kprs[i] > 0 else (safe_float(data.get(f'map{i+1}_kpr')) or k_glob)
        specific_mult = VAL_GRAVITY.get(VAL_ROLES.get(t_name, "Initiator"), 1.0) if theater == "VALORANT" else CS2_ARCHETYPES.get(t_name, 1.0)
        weighted_kpr = m_val * specific_mult * swing_mult * match_mult * ode_mult * pacing_mult * duel_mult * (1 - (heat / 100) * 0.12)
        per_map_proj.append(weighted_kpr * (r_total / 2))
        per_map_hs.append(m_hs[i] if m_hs[i] > 0 else safe_float(data.get(f'map{i+1}_hs_pct'), 50.0))

    total_volume = sum(per_map_proj) * (1.08 if ok_win > 55 else 1.0)
    final_proj = total_volume * ( (np.mean(per_map_hs) / 100) * (1.8 if theater == "VALORANT" else 1.0) ) if metric == "HEADSHOTS" else total_volume
        
    is_dampened = False
    ceiling = locked_line * 1.5
    if final_proj > ceiling:
        is_dampened = True
        final_proj = ceiling + ((final_proj - ceiling) * 0.90)
        
    delta = final_proj - locked_line
    win_prob = (np.random.normal(final_proj, 5.5, 10000) > locked_line).mean() * 100
    
    # NUKE PLAY LOGIC: Stars Aligning
    is_nuke_play = False
    if delta > 10.0 and conf >= 85 and win_prob >= 85:
        is_nuke_play = True

    return {
        "player": locked_player.upper(), "match": f"{locked_team.upper()} vs {opp_team.upper()}", 
        "grade": ("S" if delta > 6.0 else "A+" if delta > 3.0 else "B" if delta < -3.0 else "C"), 
        "color": ("#FFD700" if delta > 6.0 else "#00FF7F" if delta > 3.0 else "#FF4500" if delta < -3.0 else "#A0A0A0"), 
        "arrow": ("▲" if delta > 3.0 else "▼" if delta < -3.0 else "—"), 
        "d_text": ("OVER" if delta > 0 else "UNDER"), "prob": win_prob,
        "kpr": f"{k_glob:.2f}", "proj": final_proj, "delta": delta, "is_dampened": is_dampened, "is_nuke": is_nuke_play, "conf": conf,
        "trace": f"{targets[0].upper()} | {targets[1].upper()}", 
        "metric": metric, "line": locked_line, "hr": f"{safe_float(data.get('l10_hit_rate'), 70.0):.0f}%", "gap": rank_gap, "swing": f"{swing_pct:+.2f}%"
    }

def run_precision_research(cmd, metric, targets, m_kprs, m_hs, heat, pacing, opp_dpr, r_total, swing, sync, opp, theater, live):
    match = re.search(r"Grade\s+([A-Za-z0-9_]+)\s*\((.*?)\)", cmd, re.IGNORECASE)
    if not match: st.error("Format: Grade Player (Team) Line"); st.stop()
    t_p, t_t = match.group(1).lower().strip(), match.group(2).strip()
    u_line = float(re.findall(r"(\d+\.\d+|\d+)", cmd)[-1])
    raw = load_from_vault(t_p, opp, theater) if not live else None
    if not raw:
        with st.status(f"🛰️ {theater} SCAN: {t_p.upper()}"):
            q = f"vlr.gg 2026 stats {t_p} {t_t} vs {opp}" if theater == "VALORANT" else f"HLTV 2026 stats {t_p} {t_t} vs {opp}"
            res = tavily_client.search(query=q, max_results=3)
            w_data = "\n".join([r['content'] for r in res['results']])[:3000]
            p = f"JSON for {t_p} ({t_t}) vs {opp}. Data: {w_data}. KEYS: team_rank (int), opp_rank (int), base_kpr (float), hs_pct (float), rating_num (float), opening_win_pct (float), l10_hit_rate (float)."
            c = groq_client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "user", "content": p}], response_format={"type": "json_object"}, temperature=0)
            raw = json.loads(c.choices[0].message.content)
            save_to_vault(t_p, opp, theater, raw)
    if sync: st.session_state['auto_duel'] = safe_float(raw.get('opening_win_pct', 50.0)) / 10.0
    return apply_sovereign_math(raw, t_p, u_line, t_t, opp, targets, m_kprs, m_hs, heat, pacing, opp_dpr, r_total, swing, st.session_state['auto_duel'], metric, theater)

# --- 3. UI LAYER ---
with st.sidebar:
    st.header("📡 COMMAND CENTER")
    theater_sel = st.sidebar.radio("Theater", ["CS2", "VALORANT"], help="HINT: Affects Agent Gravity/Map Archetypes.")
    force_live = st.sidebar.checkbox("Force Live Strike", value=True, help="HINT: Fresh 2026 scan.")
    metric_sel = st.sidebar.segmented_control("Metric", options=["KILLS", "HEADSHOTS"], default="KILLS", help="HINT: Target output.")
    with st.expander("👤 MAPS 1+2 TACTICAL", expanded=True):
        label = "Map" if theater_sel == "CS2" else "Agent"
        target_list = list(CS2_ARCHETYPES.keys()) if theater_sel == "CS2" else list(VAL_ROLES.keys())
        t1, t1_k = st.selectbox(f"{label} 1", target_list), safe_float(st.text_input(f"M1 KPR", ""), 0.0)
        t1_h = safe_float(st.text_input(f"M1 HS%", ""), 0.0) if metric_sel == "HEADSHOTS" else 0.0
        t2, t2_k = st.selectbox(f"{label} 2", target_list), safe_float(st.text_input(f"M2 KPR", ""), 0.0)
        t2_h = safe_float(st.text_input(f"M2 HS%", ""), 0.0) if metric_sel == "HEADSHOTS" else 0.0
        st.write("---")
        sync_on = st.checkbox("🛰️ Auto-Sync Open Duel", value=True, help="HINT: Pulls 2026 Opening stats.")
        duel_val = st.slider("Open Duel (HLTV Equiv)", 1.0, 10.0, value=st.session_state['auto_duel'], step=0.1, disabled=sync_on)
        if not sync_on: st.session_state['auto_duel'] = duel_val
        swing_v, r_total_v = safe_float(st.text_input("Round Swing %", "2.18"), 2.18), safe_float(st.text_input("Total Maps 1+2 Rounds", "44.0"), 44.0)
        heat_val = st.slider("Teammate Heat", 0, 100, 0)
    with st.expander("🛡️ OPPONENT TACTICAL", expanded=True):
        opp_name, opp_dpr = st.text_input("Opponent Team Name", "PCIFIC"), safe_float(st.text_input("Opponent DPR", "0.65"), 0.0)
        pacing_val = st.selectbox("Pacing", ["Auto", "Fast", "Slow"])

if prompt := st.chat_input("Grade Player (Team) Line"):
    with st.chat_message("assistant"):
        intel = run_precision_research(prompt, metric_sel, [t1, t2], [t1_k, t2_k], [t1_h, t2_h], heat_val, pacing_val, opp_dpr, r_total_v, swing_v, sync_on, opp_name, theater_sel, force_live)
        card_html = f"""
<div class="sovereign-card" style="border-top: 35px solid {intel['color']};">
<div class="grade-display">{intel['grade']}</div>
<div class="card-content">
{f'<div class="nuke-play-badge">🚀 NUKE PLAY: ALL STARS ALIGNED</div>' if intel['is_nuke'] else ''}
{f'<div class="nuclear-alert">☢️ CEILING ALERT: LIGHT DAMPENING ACTIVE</div>' if intel['is_dampened'] else ''}
<div class="player-name">{intel['player']}</div>
<div class="match-header">{intel['match']} (MAPS 1+2)</div>
<div style="display: flex; gap: 80px; justify-content: center;">
<div><div class="stat-lbl">Win Prob</div><div class="stat-val">{intel['prob']:.1f}%</div></div>
<div><div class="stat-lbl">{intel['metric']} PROJ</div><div class="stat-val" style="color: {intel['color']};">{intel['proj']:.1f}</div></div>
<div><div class="stat-lbl">Open Duel</div><div class="stat-val">{st.session_state['auto_duel']:.1f}</div></div>
</div>
<div class="decision-line" style="color: {intel['color']};">{intel['d_text']} {intel['line']} {intel['metric']} {intel['arrow']}</div>
<div style="margin-top: 40px; font-family: 'JetBrains Mono'; color: rgba(255,255,255,0.4); font-size: 22px;">{intel['trace']}</div>
</div>
</div>"""
        st.markdown(card_html, unsafe_allow_html=True)
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        
        nuke_color = "red" if intel['is_nuke'] else "green"
        nuke_label = "FLAGGED" if intel['is_nuke'] else "CLEAN"
        
        with c1: st.metric("MODEL CONF", f"{intel['conf']}%"); st.badge("Sovereign Conf", color="primary")
        with c2: st.metric("DELTA", f"{intel['delta']:+.1f}"); st.badge("Strike Delta", color="blue")
        with c3: st.metric("L10 HIT RATE", intel['hr']); st.badge("Momentum", color="violet")
        with c4: st.metric("GLOBAL KPR", intel['kpr']); st.badge("Historical", color="gray")
        with c5: st.metric("RANK GAP", f"{intel['gap']:+d} Pos"); st.badge("Mismatch", color="orange")
        with c6: st.metric("NUCLEAR FLAG", nuke_label); st.badge("Sanity Check", color=nuke_color)