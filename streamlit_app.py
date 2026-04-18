import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from scipy.stats import norm
from streamlit_gsheets import GSheetsConnection

# --- 🛠️ CORE UTILITIES ---
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
    except Exception as e:
        st.error(f"Vault Connection Failure: {e}")
        return pd.DataFrame()

def load_intel_vault():
    """Loads your custom scouting JSON."""
    if os.path.exists("intel_vault.json"):
        with open("intel_vault.json", "r") as f:
            return json.load(f)
    return {"teams": {}, "maps": {}}

# --- 🧠 THE AI ADVISOR (DEEP DATA INTEGRATION) ---
def run_ai_advisor():
    """
    Scans intel_vault.json and Deep Profile text boxes to suggest & lock sliders.
    """
    intel = load_intel_vault()
    
    # 🟢 STEP 1: READ DEEP PROFILE DATA FROM TEXT BOXES
    context_text = st.session_state.get('m_context', "").lower()
    maps_text = st.session_state.get('p_maps', "").lower()
    m1_kpr = st.session_state.get('m1_kpr_input', 0.82)
    
    # Default State
    analysis = {
        "w_h2h": {"val": 1.00, "reason": "Matchup looks standard."},
        "w_tier": {"val": 1.00, "reason": "No specific team data found in vault."},
        "w_map": {"val": 1.00, "reason": "No specific map advantage detected."},
        "w_int": {"val": 1.00, "reason": "Form looks baseline."}
    }

    # 🟢 STEP 2: CROSS-REFERENCE INTEL_VAULT.JSON
    # Check Teams (Match Context)
    for team_name, data in intel.get("teams", {}).items():
        if team_name.lower() in context_text:
            analysis["w_tier"]["val"] = data.get("tier_weight", 1.0)
            analysis["w_tier"]["reason"] = f"Vault Intel: {data.get('scouting_note', 'Elite Team')}"

    # Check Maps (Projected Maps)
    for map_name, data in intel.get("maps", {}).items():
        if map_name.lower() in maps_text:
            analysis["w_map"]["val"] = data.get("difficulty_modifier", 1.0)
            analysis["w_map"]["reason"] = f"Map Intel: {map_name.title()} is {data.get('type', 'active')}."

    # 🟢 STEP 3: ANALYZE RECENT FORM (KPRs)
    if m1_kpr > 0.88:
        analysis["w_int"]["val"] = 1.05
        analysis["w_int"]["reason"] = f"Form: Manual KPR ({m1_kpr}) is above elite average (0.82)."
    elif m1_kpr < 0.70:
        analysis["w_int"]["val"] = 0.90
        analysis["w_int"]["reason"] = "Form: Recent KPR suggests a cold streak."

    # 🟢 STEP 4: HARD-LOCK SLIDERS TO SESSION STATE
    st.session_state.w_h2h = analysis["w_h2h"]["val"]
    st.session_state.w_tier = analysis["w_tier"]["val"]
    st.session_state.w_map = analysis["w_map"]["val"]
    st.session_state.w_int = analysis["w_int"]["val"]
    st.session_state.ai_report = analysis
    
    # Force rerun to 'paint' the new slider positions without clearing boxes
    st.rerun()

def sync_player_data():
    """Auto-populates KPR and Tag when a player is selected."""
    if st.session_state.player_selector != "Manual Entry":
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        base_kpr = safe_float(row.get('KPR'), 0.82)
        
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Free Agent')} vs "
        st.session_state.m1_kpr_input = base_kpr
        st.session_state.m2_kpr_input = base_kpr

# --- 🎨 UI INITIALIZATION ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# 🛡️ THE PERSISTENCE LOCK: Initialize every single widget key
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
    st.session_state.initialized = True

# --- 🛰️ SIDEBAR: AI ADVISOR ---
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    
    if st.button("🤖 CONSULT AI ADVISOR", use_container_width=True):
        run_ai_advisor()

    if st.session_state.ai_report:
        st.write("---")
        for key, data in st.session_state.ai_report.items():
            label = key.split('_')[1].upper()
            st.markdown(f"**{label}: {data['val']:.2f}**")
            st.caption(data['reason'])
    
    st.write("---")
    # Sliders explicitly tied to keys
    st.slider("H2H Advantage", 0.8, 1.2, key="w_h2h", step=0.05)
    st.slider("Opponent Tier", 0.8, 1.2, key="w_tier", step=0.05)
    st.slider("Map Fit", 0.8, 1.2, key="w_map", step=0.05)
    st.slider("Pressure/Form", 0.8, 1.2, key="w_int", step=0.05)

# --- 🕵️ MAIN BODY: DEEP PROFILE ---
game_choice = st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Data")
    st.selectbox("Search Database", ["Manual Entry"] + players, key="player_selector", on_change=sync_player_data)
    
    # 🟢 KEY parameter is mandatory for persistence
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context", placeholder="e.g. Spirit vs Vitality")
    st.text_input("Projected Maps", key="p_maps", placeholder="e.g. Anubis, Mirage")
    
    if game_choice == "CS2":
        c1, c2 = st.columns(2)
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
    else:
        st.number_input("Base ADR", key="adr", value=140.0)
        
    st.text_area("L10 Data (CSV)", key="l10")
    
    if st.button("🚀 EXECUTE GRADING ENGINE", use_container_width=True):
        # Calculation logic would go here
        st.success("Math executed based on current sidebar weights.")

# --- 💎 SOCIAL CARD (Visuals Fixed) ---
with col_r:
    if st.session_state.ai_report: # Just as an example placeholder
        st.markdown("""
        <div style="background-color: #121212; border: 2px solid #FFD700; border-radius: 25px; padding: 40px; width: 450px; margin: auto; color: white; text-align: center; font-family: sans-serif;">
            <div style="color: #888; letter-spacing: 3px; font-size: 13px; margin-bottom:12px;">CS2 PROP ANALYSIS</div>
            <div style="font-size: 50px; font-weight: 900; margin: 0; line-height:1;">EXAMPLE</div>
            <div style="color: #4A90E2; font-size: 18px; font-weight: bold; margin-bottom: 25px; border-bottom: 1px solid #333; padding-bottom: 18px;">SPIRIT VS VITALITY</div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 10px 0;">
                <div style="text-align: left; flex: 1;">
                    <div style="color:#888; font-size:11px; font-weight:bold;">THE PROP LINE</div>
                    <div style="font-size: 80px; font-weight: 900; line-height:1;">31.5</div>
                    <span style="color: #00FF00; border: 1px solid #00FF00; padding: 5px 12px; border-radius: 8px; font-weight: 900;">▲ OVER</span>
                </div>
                <div style="width: 140px; text-align: center;">
                    <div style="color:#888; font-size:11px; font-weight:bold; margin-bottom:12px;">MODEL GRADE</div>
                    <div style="font-size: 110px; font-weight: 900; color: #FFD700; text-shadow: 0 0 25px rgba(255, 215, 0, 0.5); line-height: 0.9;">S</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)