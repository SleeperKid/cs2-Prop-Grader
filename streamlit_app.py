import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os
import json
from groq import Groq
import re

# ==========================================
# 🧠 INTELLIGENCE VAULT LOADER
# ==========================================
def load_intel():
    """Loads the external Brain from JSON"""
    if os.path.exists("intel_vault.json"):
        with open("intel_vault.json", "r") as f:
            return json.load(f)
    return {}

INTEL = load_intel()

# ==========================================
# 🎨 ELITE UI STYLING
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #238636; color: white; font-weight: bold; border: none; }
    .grade-card { padding: 30px; border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; margin-bottom: 20px; }
    .grade-text { font-size: 90px; font-weight: 900; margin: 0; line-height: 1; }
    .advice-box { background: #1c2128; padding: 15px; border-radius: 10px; border: 1px solid #30363d; font-size: 0.85rem; color: #58a6ff; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🧠 CORE ANALYTICS ENGINE
# ==========================================
def get_grade_details(edge):
    """Assigns grades and gradients based on edge percentage"""
    if edge >= 12.0: return "S", "linear-gradient(135deg, #FFD700, #FFA500)", "#FFD700", 2.5
    if edge >= 8.0: return "A+", "linear-gradient(135deg, #00FF00, #008000)", "#00FF00", 2.0
    if edge >= 3.0: return "A", "linear-gradient(135deg, #ADFF2F, #228B22)", "#ADFF2F", 1.0
    if edge >= 0.0: return "B", "linear-gradient(135deg, #F0E68C, #DAA520)", "#F0E68C", 0.5
    return "F", "linear-gradient(135deg, #8B0000, #000000)", "#FF4500", 0.0

def get_implied_prob(odds):
    """Calculates implied probability from American odds"""
    return (abs(odds) / (abs(odds) + 100)) * 100 if odds < 0 else (100 / (odds + 100)) * 100

# ==========================================
# 📥 DATA & SESSION STATE
# ==========================================
# Ensures persistence across interactions
states = {
    'h2h_val': 1.0, 'tier_val': 1.0, 'map_val': 1.0, 'int_val': 1.0,
    'weight_advice': None, 'analysis_results': None,
    'm_context_val': "Team vs Opponent", 'opp_rank_val': "N/A", 
    'expected_maps_val': "TBD", 'opening_val': "50%",
    'map1_rate': "0.00", 'map2_rate': "0.00",
    'last_player': None, 'p_tag_val': "donk", 'l10_val': "46, 33, 45", 'kpr_val': 0.90,
    'stat_type_val': "Kills", 'role_val': "Rifler"
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

@st.cache_data
def load_vault():
    if os.path.exists("daily_stats.csv"):
        return pd.read_csv("daily_stats.csv")
    return pd.DataFrame(columns=["Player", "Game", "Team", "BaseKPR", "L10", "ExpectedMaps", "Rank"])

df = load_vault()

# ==========================================
# ⚙️ SIDEBAR: THE AI ADVISOR (DETERMINISTIC)
# ==========================================
with st.sidebar:
    st.header("⚙️ Model Intelligence")
    
    if st.button("GET AI SLIDER ADVICE"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if not api_key:
            st.error("API Key missing in Secrets.")
        else:
            client = Groq(api_key=api_key)
            
            # Matchup Logic Splitting
            match_parts = st.session_state.m_context_val.split(' vs ')
            p_team = match_parts[0] if len(match_parts) > 0 else "Unknown"
            o_team = match_parts[1] if len(match_parts) > 1 else "the Opponent"
            
            # Pull Intel from JSON Brain
            map_name = st.session_state.expected_maps_val.split(',')[0].strip()
            map_data = INTEL.get("maps", {}).get(map_name, "Standard map dynamics.")
            role_info = INTEL.get("roles", {}).get(st.session_state.role_val, "")
            
            with st.spinner("Analyzing Matchup Context..."):
                prompt = f"""
                Act as a Professional Esports Betting Model. Deterministic Mode.
                
                CONTEXT:
                - PLAYER: {st.session_state.p_tag_val}
                - PLAYER_TEAM: {p_team}
                - OPPONENT_TEAM: {o_team}
                - OPPONENT_TEAM_WORLD_RANK: {st.session_state.opp_rank_val}
                
                MATCH DATA:
                - PROP_TYPE: {st.session_state.stat_type_val}
                - PLAYER_ROLE: {st.session_state.role_val} ({role_info})
                - MAP_INTEL: {map_name} - {map_data}
                - DEEP_STATS: Map1 Rate: {st.session_state.map1_rate} | Map2 Rate: {st.session_state.map2_rate} | Opening Duels: {st.session_state.opening_val}

                TASK:
                1. Assign 4 Weights (0.85 to 1.15) for our grading model.
                2. Be logical: If Opponent Rank is lower/stronger, increase 'Tier' weight. If map/role fit is high, increase 'Map' weight.
                3. FORMAT: H2H: [X] | Tier: [X] | Map: [X] | Int: [X]
                
                Output ONLY the weights and a 1-sentence justification.
                """
                
                # Temperature 0 for consistency
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile", 
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0
                )
                
                st.session_state.weight_advice = completion.choices[0].message.content
                found_weights = re.findall(r"([0-1]\.\d+)", st.session_state.weight_advice)
                
                if len(found_weights) >= 4:
                    st.session_state.h2h_val, st.session_state.tier_val, st.session_state.map_val, st.session_state.int_val = [float(x) for x in found_weights[:4]]
                    st.toast("🎯 Sliders Synced!", icon="✅")

    if st.session_state.weight_advice:
        st.markdown(f'<div class="advice-box"><b>Vault Intelligence:</b><br>{st.session_state.weight_advice}</div>', unsafe_allow_html=True)

    st.divider()
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, key="h2h_val", step=0.05)
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, key="tier_val", step=0.05)
    map_w = st.slider("Map Fit", 0.80, 1.20, key="map_val", step=0.05)
    int_w = st.slider("Match Intensity", 0.70, 1.10, key="int_val", step=0.05)

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
st.title("🎯 Prop Grader Elite")
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("📋 Prop & Context")
    game_choice = st.radio("Game", ["CS2", "Valorant"], horizontal=True)
    
    cat_col, role_col = st.columns(2)
    with cat_col:
        stat_type = st.radio("Stat Category", ["Kills", "Headshots"] if game_choice == "CS2" else ["Kills"], horizontal=True, key="stat_type_val")
    with role_col:
        if game_choice == "CS2":
            st.radio("Player Role", ["Rifler", "AWPer"], horizontal=True, key="role_val")

    db_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected_name = st.selectbox("Database Search", ["Manual Entry"] + db_players)
    
    # Gatekeeper logic to prevent resetting manual entries
    if selected_name != st.session_state.last_player:
        if selected_name != "Manual Entry":
            p_row = df[df['Player'] == selected_name].iloc[0]
            st.session_state.p_tag_val = str(p_row['Player'])
            st.session_state.l10_val = str(p_row['L10'])
            st.session_state.kpr_val = float(p_row['BaseKPR'])
            st.session_state.m_context_val = f"{p_row['Team']} vs "
            st.session_state.opp_rank_val = str(p_row.get('Rank', "N/A"))
            st.session_state.expected_maps_val = str(p_row.get('ExpectedMaps', "TBD"))
        st.session_state.last_player = selected_name
        st.rerun()

    p_tag = st.text_input("Player Tag", key="p_tag_val")
    match_ctx = st.text_input("Matchup Context", key="m_context_val")
    l10_raw = st.text_area(f"L10 {stat_type} Stats", key="l10_val")
    base_rate = st.number_input(f"Base {stat_type} Rate", key="kpr_val", step=0.01)

    with st.expander("🧠 Deep Context", expanded=True):
        st.text_input("Opponent World Rank", key="opp_rank_val")
        st.text_input("Projected Maps", key="expected_maps_val")
        st.text_input("Opening Duel Success %", key="opening_val")
        k_col1, k_col2 = st.columns(2)
        k_col1.text_input(f"Map 1 {stat_type}", key="map1_rate")
        k_col2.text_input(f"Map 2 {stat_type}", key="map2_rate")

    c1, c2 = st.columns(2)
    with c1:
        m_line = st.number_input("Line", value=35.5, step=0.5)
        m_side = st.selectbox("Side", ["Over", "Under"])
    with c2:
        m_odds = st.number_input("Odds", value=-128)
        m_scope = st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

if st.button("RUN ELITE ANALYSIS"):
    try:
        vals = [float(x.strip()) for x in l10_raw.split(",") if x.strip()]
        mean_v = np.mean(vals)
        stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 1.0, 1.0)
        cv = stdev / mean_v 
        hit_rate = (sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line)) / len(vals)) * 100
        
        mapping = {"Maps 1 & 2": 2.0, "Map 1 Only": 1.0, "Full Match": 2.5}
        proj = (base_rate * 21.5 * mapping.get(m_scope, 2.0)) * h2h_w * rank_w * map_w * int_w
        
        prob_under = norm.cdf(m_line, loc=proj, scale=stdev)
        model_prob = (1 - prob_under) * 100 if m_side == "Over" else prob_under * 100
        edge = model_prob - get_implied_prob(m_odds)
        
        # Hard-Mode Confidence Logic
        conf = min(max(((abs(edge) * 2) + (hit_rate * 0.4) - (cv * 120)), 0), 100)
        
        grade, color, flat, units = get_grade_details(edge)
        if cv > 0.25: units = max(0.5, units - 0.5)
        
        st.session_state.analysis_results = {
            "p_tag": p_tag, "matchup": match_ctx, "side": m_side, "line": m_line, "grade": grade,
            "color": color, "flat": flat, "units": units, "proj": proj, "edge": edge, 
            "hit_rate": hit_rate, "conf": conf, "game": game_choice, "stat_label": stat_type
        }
    except Exception as e:
        st.error(f"Analysis Error: {e}")

# ==========================================
# 📊 OUTPUTS & RENDERED SHARE CARD
# ==========================================
with col_r:
    if st.session_state.analysis_results:
        res = st.session_state.analysis_results
        
        # Dashboard UI Rendering
        p_name_up = res.get("p_tag", "Unknown").upper()
        m_info = res.get("matchup", "N/A")
        side_up = res.get("side", "Over")
        line_val = res.get("line", 0.0)
        proj_val = res.get("proj", 0.0)
        stat_lbl = res.get("stat_label", "Kills").upper()
        arrow_sym = "▲" if side_up == "Over" else "▼"
        arrow_hex = "#00FF00" if side_up == "Over" else "#FF4500"
        grade_grad = res.get('color', 'linear-gradient(135deg, #161b22, #0e1117)')
        grade_flat = res.get('flat', '#58a6ff')
        
        st.markdown(f"""
            <div class="grade-card" style="background: {grade_grad}; color: white;">
                <div style="font-size: 28px; font-weight: 900;">{p_name_up}</div>
                <div style="font-size: 14px; opacity: 0.8;">{m_info}</div>
                <div style="font-size: 24px; margin-top: 10px; color: {arrow_hex}; font-weight: 900;">{arrow_sym} {side_up.upper()} {line_val} {stat_lbl}</div>
                <h1 class="grade-text">{res.get('grade', '?')}</h1>
                <div style="font-size: 20px; font-weight: bold;">{res.get('units', 0)} UNIT PLAY</div>
            </div>
            """, unsafe_allow_html=True)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Projected", f"{proj_val:.1f}")
        m2.metric("Edge", f"{res.get('edge', 0):+.1f}%")
        m3.metric("L10 Hit", f"{res.get('hit_rate', 0):.0f}%")
        m4.metric("Conf", f"{res.get('conf', 0):.0f}%")

        if st.checkbox("📸 Generate Social Share Card"):
            # Direct markdown call to prevent "Magic String" code leaks
            st.markdown(f"""
            <div style="background: linear-gradient(145deg, #0e1117 0%, #1c2128 100%); border: 3px solid {grade_flat}; border-radius: 20px; padding: 30px; max-width: 480px; color: white; margin: 10px auto; text-align: center; box-shadow: 0 15px 35px rgba(0,0,0,0.6); font-family: sans-serif;">
                <div style="border-bottom: 2px solid rgba(255,255,255,0.1); padding-bottom: 15px; margin-bottom: 20px;">
                    <div style="font-size: 10px; color: #adbac7; text-transform: uppercase; letter-spacing: 3px;">{res.get('game', 'CS2')} {stat_lbl} ANALYSIS</div>
                    <h2 style="margin: 5px 0; font-size: 38px; font-weight: 900; letter-spacing: -1px;">{p_name_up}</h2>
                    <div style="color: #58a6ff; font-size: 15px; font-weight: 600;">{m_info}</div>
                </div>
                
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; text-align: left;">
                    <div style="flex: 1;">
                        <div style="font-size: 13px; color: #adbac7; font-weight: bold;">THE LINE</div>
                        <div style="font-size: 60px; font-weight: 900; line-height: 0.9; margin: 8px 0; letter-spacing: -2px;">{line_val}</div>
                        <div style="font-size: 30px; font-weight: 900; color: {arrow_hex};">{arrow_sym} {side_up.upper()}</div>
                    </div>
                    <div style="flex: 1; text-align: right;">
                        <div style="font-size: 13px; color: #adbac7; font-weight: bold;">MODEL GRADE</div>
                        <div style="font-size: 115px; font-weight: 900; background: {grade_grad}; -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 0.8;">{res.get('grade', '?')}</div>
                    </div>
                </div>

                <div style="background: {grade_grad}; border-radius: 12px; padding: 18px; margin-bottom: 25px;">
                    <div style="font-size: 36px; font-weight: 900; letter-spacing: -1px;">{res.get('units', 0)} UNIT PLAY</div>
                </div>

                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; border-top: 2px solid rgba(255,255,255,0.1); padding-top: 20px;">
                    <div><div style="font-size: 10px; color: #adbac7; font-weight: bold;">PROJ</div><div style="font-size: 18px; font-weight: 900;">{proj_val:.1f}</div></div>
                    <div><div style="font-size: 10px; color: #adbac7; font-weight: bold;">EDGE</div><div style="font-size: 18px; font-weight: 900; color: {grade_flat};">{res.get('edge', 0):+.1f}%</div></div>
                    <div><div style="font-size: 10px; color: #adbac7; font-weight: bold;">L10 HIT</div><div style="font-size: 18px; font-weight: 900;">{res.get('hit_rate', 0):.0f}%</div></div>
                    <div><div style="font-size: 10px; color: #adbac7; font-weight: bold;">CONF</div><div style="font-size: 18px; font-weight: 900;">{res.get('conf', 0):.0f}%</div></div>
                </div>

                <div style="margin-top: 30px; font-size: 11px; color: #adbac7; text-transform: uppercase; letter-spacing: 4px; font-weight: 800; opacity: 0.7;">
                    ANALYSIS BY <span style="color: white;">SLEEPER D. KID</span>
                </div>
            </div>
            """, unsafe_allow_html=True)