import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from scipy.stats import norm
from streamlit_gsheets import GSheetsConnection

# --- 🛠️ DATA PERSISTENCE & UTILITIES ---
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

# --- 🧠 AI ADVISOR: THE BRAIN ---
def run_ai_advisor():
    """Reads deep from the Intel Vault JSON and moves sliders."""
    full_intel = load_intel_vault()
    game_key = "CS2" if st.session_state.game_choice == "CS2" else "VAL"
    intel = full_intel.get(game_key, {})
    
    # 🟢 STEP 1: READ LIVE TEXT BOX DATA
    context = st.session_state.get('m_context', "").lower()
    maps = st.session_state.get('p_maps', "").lower()
    m1_kpr = st.session_state.get('m1_kpr_input', 0.82)
    tier_choice = st.session_state.get('tier_select', "S-Tier (Elite)")
    
    # Defaults
    analysis = {
        "w_h2h": {"val": 1.00, "note": "Matchup looks standard."},
        "w_tier": {"val": 1.00, "note": "Standard competition tier."},
        "w_map": {"val": 1.00, "note": "Neutral map fit."},
        "w_int": {"val": 1.00, "note": "Baseline momentum."}
    }

    # 🟢 STEP 2: PARSE TOURNAMENT PRESSURE
    tourney_data = intel.get("tournaments", {})
    if tier_choice in tourney_data:
        # Mapping Tier to Logic (Expert Guidance)
        if "S-Tier" in tier_choice: analysis["w_tier"]["val"] = 0.90
        elif "Regional" in tier_choice: analysis["w_tier"]["val"] = 1.15
        analysis["w_tier"]["note"] = f"TIER INTEL: {tourney_data[tier_choice]}"

    # 🟢 STEP 3: PARSE TEAM ARCHETYPES & STYLES
    for team, style_info in intel.get("team_styles", {}).items():
        if team.lower() in context:
            analysis["w_h2h"]["note"] = f"TEAM INTEL ({team}): {style_info}"
            if "Tactical Executioners" in style_info: analysis["w_h2h"]["val"] = 0.95
            if "Force-Buy Aggressors" in style_info: analysis["w_h2h"]["val"] = 1.10

    # 🟢 STEP 4: PARSE MAP DESCRIPTIONS
    for map_name, map_desc in intel.get("maps", {}).items():
        if map_name.lower() in maps:
            analysis["w_map"]["note"] = f"MAP INTEL ({map_name}): {map_desc}"
            if "High-exec" in map_desc or "Tactical" in map_desc: analysis["w_map"]["val"] = 0.95
            if "Aim Map" in map_desc or "Fast-paced" in map_desc: analysis["w_map"]["val"] = 1.15

    # 🟢 STEP 5: SYNC & RERUN
    st.session_state.w_h2h = analysis["w_h2h"]["val"]
    st.session_state.w_tier = analysis["w_tier"]["val"]
    st.session_state.w_map = analysis["w_map"]["val"]
    st.session_state.w_int = 1.05 if m1_kpr > 0.88 else 1.00
    st.session_state.ai_report = analysis
    st.rerun()

def sync_player_data():
    """Auto-populates fields and KPR upon selection."""
    if st.session_state.player_selector != "Manual Entry":
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        base_kpr = safe_float(row.get('KPR'), 0.82)
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Free Agent')} vs "
        # 🟢 THIS ENSURES THE KPR BOXES UPDATE ON SELECTION
        st.session_state.m1_kpr_input = base_kpr
        st.session_state.m2_kpr_input = base_kpr

# --- 🎨 UI INITIALIZATION ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# 🛡️ THE PERSISTENCE LOCK (No clearing on rerun)
if 'initialized' not in st.session_state:
    st.session_state.p_tag = ""
    st.session_state.m_context = ""
    st.session_state.p_maps = ""
    st.session_state.l10 = ""
    st.session_state.m1_kpr_input = 0.82
    st.session_state.m2_kpr_input = 0.82
    st.session_state.w_h2h = 1.0
    st.session_state.w_tier = 1.0
    st.session_state.w_map = 1.0
    st.session_state.w_int = 1.0
    st.session_state.ai_report = None
    st.session_state.results = None
    st.session_state.initialized = True

# --- 🛰️ SIDEBAR: AI ADVISOR ---
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    
    if st.button("🤖 CONSULT AI ADVISOR", use_container_width=True):
        run_ai_advisor()

    if st.session_state.ai_report:
        st.write("---")
        for k, data in st.session_state.ai_report.items():
            st.markdown(f"**{k.split('_')[1].upper()}: {data['val']:.2f}**")
            st.caption(data['note'])
    
    st.divider()
    # 🟢 SLIDERS ARE HARD-KEYED
    st.slider("H2H Advantage", 0.8, 1.2, key="w_h2h", step=0.05)
    st.slider("Opponent Tier", 0.8, 1.2, key="w_tier", step=0.05)
    st.slider("Map Fit", 0.8, 1.2, key="w_map", step=0.05)
    st.slider("Pressure/Form", 0.8, 1.2, key="w_int", step=0.05)

# --- 🕵️ MAIN BODY: OPERATIONS ---
st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
players = df[df['Game'] == st.session_state.game_choice]['Player'].tolist() if not df.empty else []

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Intelligence")
    st.selectbox("Search Database", ["Manual Entry"] + players, key="player_selector", on_change=sync_player_data)
    
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    st.text_input("Projected Maps", key="p_maps")
    
    # 🟢 TIER SELECTOR FOR AI
    tiers = list(load_intel_vault().get(st.session_state.game_choice, {}).get("tournaments", {}).keys())
    st.selectbox("Tournament Tier", tiers if tiers else ["S-Tier (Elite)"], key="tier_select")
    
    if st.session_state.game_choice == "CS2":
        c1, c2 = st.columns(2)
        # 🟢 USE KEY TO PREVENT WIPE
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
    else:
        st.number_input("Base ADR", key="adr", value=140.0)
        
    st.text_area("L10 Data (CSV)", key="l10")
    
    cl, cs = st.columns(2)
    m_line = cl.number_input("Prop Line", value=31.5, step=0.5)
    m_side = cs.selectbox("Target Side", ["Over", "Under"])
    
    if st.button("🚀 EXECUTE GRADING ENGINE", use_container_width=True):
        try:
            vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
            t_weight = st.session_state.w_h2h * st.session_state.w_tier * st.session_state.w_map * st.session_state.w_int
            
            # MATH
            proj = ((st.session_state.m1_kpr_input + st.session_state.m2_kpr_input) / 2) * 48 * t_weight
            edge = (proj - m_line) / m_line * 100 if m_side == "Over" else (m_line - proj) / m_line * 100
            
            st.session_state.results = {
                "grade": "S" if edge > 15 else "A", "edge": edge, "proj": proj, 
                "line": m_line, "side": m_side, "hit": 70, "prob": 88, "units": 2.5
            }
        except: st.error("Verification failed.")

# --- 💎 OUTPUT SECTION (NO CSS BLEED) ---
with col_r:
    if st.session_state.results:
        res = st.session_state.results
        st.metric("Mathematical Edge", f"+{res['edge']:.1f}%", delta=res['grade'])
        st.write(f"**AI Recommendation:** Projection is {res['proj']:.1f} kills.")
        
        st.write("---")
        
        # 🟢 CONDITIONAL SHARE CARD
        if st.checkbox("💎 Generate Sleeper D. Kid Social Card"):
            arrow = "▲" if res['side'] == "Over" else "▼"
            # 🛡️ THE CSS SHIELD (STRICT HTML)
            st.markdown(f"""
            <div style="background-color:#121212; border:2px solid #FFD700; border-radius:25px; padding:35px; width:450px; margin:auto; color:white; text-align:center; font-family:sans-serif;">
                <div style="color:#888; letter-spacing:3px; font-size:13px; margin-bottom:12px;">{st.session_state.game_choice.upper()} PROP ANALYSIS</div>
                <div style="font-size:50px; font-weight:900; margin:0; line-height:1;">{st.session_state.p_tag.upper()}</div>
                <div style="color:#4A90E2; font-size:18px; font-weight:bold; margin-bottom:25px; border-bottom:1px solid #333; padding-bottom:18px;">{st.session_state.m_context.upper()}</div>
                <div style="display:flex; justify-content:space-between; align-items:flex-start; padding:10px 0;">
                    <div style="text-align:left; flex:1;">
                        <div style="color:#888; font-size:11px; font-weight:bold;">THE PROP LINE</div>
                        <div style="font-size:80px; font-weight:900; line-height:1;">{res['line']}</div>
                        <span style="color:{'#00FF00' if res['side'] == 'Over' else '#FF0000'}; border:1px solid {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; padding:5px 12px; border-radius:8px; font-weight:900;">{arrow} {res['side'].upper()}</span>
                    </div>
                    <div style="width:140px; text-align:center;">
                        <div style="color:#888; font-size:11px; font-weight:bold; margin-bottom:12px;">MODEL GRADE</div>
                        <div style="font-size:110px; font-weight:900; color:#FFD700; text-shadow:0 0 25px rgba(255,215,0,0.5); line-height:0.9;">{res['grade']}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)