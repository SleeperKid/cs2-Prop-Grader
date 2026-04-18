import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from scipy.stats import norm
from streamlit_gsheets import GSheetsConnection

# --- ⚙️ UTILITIES ---
def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val == "N/A" or val == "": return default
        return float(val)
    except: return default

@st.cache_data(ttl=300)
def load_vault():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        val_df = conn.read(spreadsheet=sheet_url, worksheet="VAL_DATA", ttl=0)
        cs_df = conn.read(spreadsheet=sheet_url, worksheet="CS2_DATA", ttl=0)
        val_df['Game'], cs_df['Game'] = 'Valorant', 'CS2'
        return pd.concat([val_df, cs_df], ignore_index=True).replace("N/A", np.nan)
    except: return pd.DataFrame()

def load_intel_vault():
    if os.path.exists("intel_vault.json"):
        with open("intel_vault.json", "r") as f: return json.load(f)
    return {}

# --- 🧠 AI ADVISOR: THE MATHEMATICAL SCOUT ---
def run_ai_advisor():
    """Analyzes context and JSON to move sliders and EXPLAIN why."""
    full_intel = load_intel_vault()
    game_key = "CS2" if st.session_state.game_choice == "CS2" else "VAL"
    intel = full_intel.get(game_key, {})
    
    # 🟢 STEP 1: READ LIVE CONTEXT
    context = st.session_state.m_context.lower()
    maps = st.session_state.p_maps.lower()
    prop_type = st.session_state.get('prop_type_select', 'Kills')
    
    # Initialize Suggestions
    sug = {
        "h2h": {"v": 1.00, "r": "Matchup looks neutral based on current 2026 seedings."},
        "tier": {"v": 1.00, "r": "Standard tournament pacing expected."},
        "map": {"v": 1.00, "r": "Map pool does not significantly alter frag volume."},
        "int": {"v": 1.00, "r": "Form is baseline."}
    }

    # 🟢 STEP 2: APPLY JSON LOGIC (Informing the Weights)
    # Tier/Tournament Logic
    if "final" in context or "major" in context:
        sug["tier"] = {"v": 0.93, "r": "Major Finals: Maximum utility discipline suppresses high frag counts."}

    # Map & Prop Type Logic (Headshots vs Kills)
    for m_name, desc in intel.get("maps", {}).items():
        if m_name.lower() in maps:
            if prop_type == "Headshot Kills":
                if "HS props" in desc or "HS%" in desc:
                    val = 1.10 if "High HS" in desc else 0.85
                    sug["map"] = {"v": val, "r": f"MAP INTEL ({m_name}): {desc}"}
            else:
                sug["map"] = {"v": 1.0, "r": f"MAP INTEL ({m_name}): {desc[:60]}..."}

    # Team Strategy Archetypes
    for team, style in intel.get("team_styles", {}).items():
        if team.lower() in context:
            if "Tactical Executioners" in style:
                sug["h2h"] = {"v": 0.90, "r": f"SCOUTING: {team} is a Tactical Executioner. Rounds are slow and methodical (Under lean)."}
            if "Force-Buy Aggressors" in style:
                sug["h2h"] = {"v": 1.15, "r": f"SCOUTING: {team} plays Chaos Meta. High frag frequency (Over lean)."}

    # 🟢 STEP 3: SYNC TO UI & RERUN
    st.session_state.w_h2h = sug["h2h"]["v"]
    st.session_state.w_tier = sug["tier"]["v"]
    st.session_state.w_map = sug["map"]["v"]
    st.session_state.ai_report = sug
    st.rerun()

# --- 🎨 UI INITIALIZATION ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# 🛡️ THE PERSISTENCE LOCK (Prevents Resets)
if 'initialized' not in st.session_state:
    st.session_state.update({
        'p_tag': "", 'm_context': "", 'p_maps': "", 'l10': "", 
        'm1_kpr_input': 0.82, 'm2_kpr_input': 0.82, 'hs_pct_input': 45.0,
        'w_h2h': 1.0, 'w_tier': 1.0, 'w_map': 1.0, 'w_int': 1.0, 
        'ai_report': None, 'results': None, 'initialized': True
    })

# --- 🛰️ SIDEBAR: AI ADVISOR ---
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    if st.button("🤖 CONSULT AI ADVISOR", use_container_width=True): run_ai_advisor()
    
    if st.session_state.ai_report:
        st.subheader("AI Numerical Suggestions")
        for k, d in st.session_state.ai_report.items():
            st.markdown(f"**{k.upper()}: {d['v']:.2f}**")
            st.caption(d['r'])
    
    st.divider()
    st.slider("H2H Advantage", 0.8, 1.2, key="w_h2h", step=0.05)
    st.slider("Opponent Tier", 0.8, 1.2, key="w_tier", step=0.05)
    st.slider("Map Fit", 0.8, 1.2, key="w_map", step=0.05)
    st.slider("Pressure/Form", 0.8, 1.2, key="w_int", step=0.05)

# --- 🕵️ MAIN BODY ---
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
    st.selectbox("Search Database", ["Manual Entry"] + (df[df['Game'] == st.session_state.game_choice]['Player'].tolist() if not df.empty else []), key="player_selector")
    
    # Widgets linked ONLY to keys (Sticky State)
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    st.text_input("Projected Maps", key="p_maps")
    
    if st.session_state.game_choice == "CS2":
        st.selectbox("Prop Type", ["Kills", "Headshot Kills"], key="prop_type_select")
        c1, c2, c3 = st.columns(3)
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
        c3.number_input("HS%", key="hs_pct_input", format="%.1f")
    else:
        st.number_input("Base ADR", key="adr_input", value=140.0)
        st.selectbox("Role", ["Duelist", "Support"], key="val_role_select")
    
    st.text_area("L10 Data", key="l10")
    m_line = st.number_input("Prop Line", value=31.5, step=0.5)
    m_side = st.selectbox("Side", ["Over", "Under"], key="side_select")

    if st.button("🚀 EXECUTE GRADING ENGINE", use_container_width=True):
        # Calculation logic
        v_list = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
        weights = st.session_state.w_h2h * st.session_state.w_tier * st.session_state.w_map * st.session_state.w_int
        
        if st.session_state.game_choice == "CS2":
            proj = ((st.session_state.m1_kpr_input + st.session_state.m2_kpr_input) / 2) * 48 * weights
            if st.session_state.get('prop_type_select') == "Headshot Kills":
                proj = proj * (st.session_state.hs_pct_input / 100)
        else:
            proj = (st.session_state.adr_input / 140) * 42 * weights * (1.15 if st.session_state.val_role_select == "Duelist" else 0.95)
        
        edge = ((proj - m_line) / m_line * 100) if m_side == "Over" else ((m_line - proj) / m_line * 100)
        hit = (sum(1 for v in v_list if (v > m_line if m_side == "Over" else v < m_line)) / len(v_list)) * 100
        
        st.session_state.results = {"grade": "S" if edge > 22 and hit >= 70 else "A", "proj": proj, "edge": edge, "line": m_line, "side": m_side, "hit": hit, "units": 2.5 if edge > 22 else 1.0}

# --- 📊 OUTPUT: DYNAMIC DASHBOARD & CARD ---
with col_r:
    if st.session_state.results:
        res = st.session_state.results
        st.markdown(f"""
        <div style="background:#1a1c23; border:1px solid #333; border-radius:15px; padding:25px; text-align:center; margin-bottom:20px;">
            <div style="color:#888; font-size:12px; font-weight:bold;">INTERNAL MODEL DECISION</div>
            <div style="font-size: 110px; font-weight: 900; color: #FFD700; line-height:1;">{res['grade']}</div>
            <div style="color:{'#00FF00' if res['side'] == 'Over' else '#FF0000'}; font-weight:bold; font-size:24px;">{res['side'].upper()} {res['line']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.checkbox("💎 Generate Social Media Share Card", key="show_social_card")
        if st.session_state.show_social_card:
            arrow = "▲" if res['side'] == "Over" else "▼"
            # 🟢 THE RE-DESIGNED SOCIAL CARD
            st.markdown(f"""
            <div style="background-color:#121212; border:2px solid #FFD700; border-radius:20px; padding:35px; width:450px; margin:auto; color:white; text-align:center; font-family:sans-serif;">
                <div style="color:#888; font-size:12px; letter-spacing:3px; margin-bottom:10px;">{st.session_state.game_choice.upper()} ANALYSIS</div>
                <div style="font-size:48px; font-weight:900; margin:0; line-height:1;">{st.session_state.p_tag.upper()}</div>
                <div style="color:#4A90E2; font-size:18px; font-weight:bold; margin:10px 0 20px 0;">{st.session_state.m_context.upper()}</div>
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px;">
                    <div style="text-align:left; flex:1;">
                        <div style="color:#888; font-size:11px; font-weight:bold;">PROP LINE</div>
                        <div style="font-size:75px; font-weight:900; line-height:1;">{res['line']}</div>
                        <span style="color:{'#00FF00' if res['side'] == 'Over' else '#FF0000'}; border:1px solid {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; padding:4px 10px; border-radius:8px; font-weight:900; font-size:14px;">{arrow} {res['side'].upper()}</span>
                    </div>
                    <div style="text-align:center; width:140px;">
                        <div style="color:#888; font-size:11px; font-weight:bold;">GRADE</div>
                        <div style="font-size:100px; font-weight:900; color:#FFD700; text-shadow:0 0 20px rgba(255,215,0,0.5); line-height:0.9;">{res['grade']}</div>
                    </div>
                </div>
                <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; border-top:1px solid #333; padding-top:20px;">
                    <div><div style="font-size:10px; color:#666; font-weight:bold;">PROJ</div><div style="font-size:22px; font-weight:900;">{res['proj']:.1f}</div></div>
                    <div><div style="font-size:10px; color:#666; font-weight:bold;">EDGE</div><div style="font-size:22px; font-weight:900;">+{res['edge']:.1f}%</div></div>
                    <div><div style="font-size:10px; color:#666; font-weight:bold;">L10 HIT</div><div style="font-size:22px; font-weight:900;">{res['hit']:.0f}%</div></div>
                </div>
                <div style="color: #4A90E2; letter-spacing: 4px; font-size: 11px; margin-top: 30px; font-weight: bold;">ANALYSIS BY SLEEPER D. KID</div>
            </div>
            """, unsafe_allow_html=True)