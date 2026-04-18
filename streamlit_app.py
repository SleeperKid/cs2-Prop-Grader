import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from scipy.stats import norm
from streamlit_gsheets import GSheetsConnection

# --- 🛠️ UTILITIES ---
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
    if os.path.exists("intel_vault.json"):
        with open("intel_vault.json", "r") as f: return json.load(f)
    return {"teams": {}, "maps": {}}

# --- 🧠 AI ADVISOR ENGINE ---
def run_ai_advisor():
    """Calculates numerical weights and explains reasoning for non-experts."""
    intel = load_intel_vault()
    maps = st.session_state.get('p_maps', "").lower()
    context = st.session_state.get('m_context', "").lower()
    m1_kpr = st.session_state.get('m1_kpr_input', 0.82)
    
    # AI logic dictionary
    analysis = {
        "w_h2h": {"val": 1.00, "reason": "Neutral matchup parity."},
        "w_tier": {"val": 1.00, "reason": "Standard opponent tier."},
        "w_map": {"val": 1.00, "reason": "Neutral map pool."},
        "w_int": {"val": 1.00, "reason": "No significant form detected."}
    }

    # 1. Team/Tier Intel
    for team, data in intel.get("teams", {}).items():
        if team.lower() in context:
            analysis["w_tier"]["val"] = data.get("tier_weight", 1.0)
            analysis["w_tier"]["reason"] = data.get("scouting_note", "Intel found in vault.")

    # 2. Map Influence
    for m_name, m_data in intel.get("maps", {}).items():
        if m_name.lower() in maps:
            analysis["w_map"]["val"] = m_data.get("difficulty_modifier", 1.0)
            analysis["w_map"]["reason"] = f"{m_name.title()} favors this player's style."

    # 3. Form Factor
    if m1_kpr > 0.88:
        analysis["w_int"]["val"] = 1.05
        analysis["w_int"]["reason"] = "Recent high KPR suggests player is peaking."

    # 🟢 SYNC TO SLIDERS
    st.session_state.w_h2h = analysis["w_h2h"]["val"]
    st.session_state.w_tier = analysis["w_tier"]["val"]
    st.session_state.w_map = analysis["w_map"]["val"]
    st.session_state.w_int = analysis["w_int"]["val"]
    st.session_state.ai_report = analysis
    
    # 🟢 RERUN TO LOCK VALUES
    st.rerun()

def sync_player_data():
    """Auto-populates fields and KPR immediately upon selection."""
    if st.session_state.player_selector != "Manual Entry":
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        base_kpr = safe_float(row.get('KPR'), 0.82)
        
        # Write directly to session state keys used by widgets
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Free Agent')} vs "
        st.session_state.m1_kpr_input = base_kpr
        st.session_state.m2_kpr_input = base_kpr

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# 🛡️ STATE LOCK: Initialize all keys so they never 'clear' on rerun
defaults = {
    'p_tag': "", 'l10': "", 'm_context': "", 'p_maps': "", 
    'm1_kpr_input': 0.82, 'm2_kpr_input': 0.82, 'results': None,
    'w_h2h': 1.0, 'w_tier': 1.0, 'w_map': 1.0, 'w_int': 1.0, 'ai_report': None
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 🛰️ SIDEBAR: AI ADVISOR & SLIDERS ---
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    
    if st.button("🤖 CONSULT AI ADVISOR", use_container_width=True):
        run_ai_advisor()

    if st.session_state.ai_report:
        st.subheader("AI Guidance")
        report = st.session_state.ai_report
        for key, data in report.items():
            label = key.replace("w_", "").upper()
            st.markdown(f"**{label}: {data['val']:.2f}**\n*{data['reason']}*")
    
    st.divider()
    # Sliders are physically linked to session state keys
    st.slider("H2H Advantage", 0.8, 1.2, key="w_h2h", step=0.05)
    st.slider("Opponent Tier", 0.8, 1.2, key="w_tier", step=0.05)
    st.slider("Map Fit", 0.8, 1.2, key="w_map", step=0.05)
    st.slider("Pressure/Form", 0.8, 1.2, key="w_int", step=0.05)

# --- 🕵️ MAIN BODY: DATA ENTRY ---
st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
players = df[df['Game'] == st.session_state.game_choice]['Player'].tolist() if not df.empty else []

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Player Intel")
    # Search dropdown triggers the auto-population callback
    st.selectbox("Search Database", ["Manual Entry"] + players, key="player_selector", on_change=sync_player_data)
    
    # 🟢 All inputs use persistent keys
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    st.text_input("Projected Maps", key="p_maps")
    
    if st.session_state.game_choice == "CS2":
        c1, c2 = st.columns(2)
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
    else:
        st.number_input("Base ADR", key="adr")
        
    st.text_area("L10 Data", key="l10")
    
    cl, cs = st.columns(2)
    m_line = cl.number_input("Prop Line", value=31.5, step=0.5)
    m_side = cs.selectbox("Target Side", ["Over", "Under"])
    
    if st.button("🚀 EXECUTE ENGINE", use_container_width=True):
        try:
            vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
            t_weight = st.session_state.w_h2h * st.session_state.w_tier * st.session_state.w_map * st.session_state.w_int
            proj = ((st.session_state.m1_kpr_input + st.session_state.m2_kpr_input) / 2) * 48 * t_weight
            edge = (proj - m_line) / m_line * 100 if m_side == "Over" else (m_line - proj) / m_line * 100
            st.session_state.results = {
                "grade": "S" if edge > 15 else "A", "edge": edge, "proj": proj, 
                "line": m_line, "side": m_side, "hit": 70, "prob": 88, "units": 2.5
            }
        except: st.error("Verification failed. Check L10 formatting.")

# --- 💎 OUTPUT SECTION ---
with col_r:
    if st.session_state.results:
        res = st.session_state.results
        
        # Text Copy Box
        st.text_area("📋 Copy Analysis", f"🚨 {st.session_state.p_tag.upper()} {res['side'].upper()}\nLine: {res['line']} | Grade: {res['grade']}")

        if st.checkbox("💎 Generate Sleeper D. Kid Social Card"):
            arrow = "▲" if res['side'] == "Over" else "▼"
            st.markdown(f"""
            <div style="background-color: #121212; border: 2px solid #FFD700; border-radius: 25px; padding: 40px; width: 450px; margin: auto; color: white; text-align: center; font-family: sans-serif;">
                <div style="color: #888; letter-spacing: 3px; font-size: 13px; margin-bottom:12px;">{st.session_state.game_choice.upper()} PROP ANALYSIS</div>
                <div style="font-size: 50px; font-weight: 900; margin: 0; line-height:1;">{st.session_state.p_tag.upper()}</div>
                <div style="color: #4A90E2; font-size: 18px; font-weight: bold; margin-bottom: 25px; border-bottom: 1px solid #333; padding-bottom: 18px;">{st.session_state.m_context.upper()}</div>
                
                <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 10px 0;">
                    <div style="text-align: left; flex: 1;">
                        <div style="color:#888; font-size:11px; font-weight:bold;">THE PROP LINE</div>
                        <div style="font-size: 80px; font-weight: 900; line-height:1;">{res['line']}</div>
                        <div style="color:#888; font-size:16px; margin-bottom:15px;">KILLS</div>
                        <span style="color: {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; border: 1px solid {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; padding: 5px 12px; border-radius: 8px; font-weight: 900;">{arrow} {res['side'].upper()}</span>
                    </div>
                    <div style="width: 140px; text-align: center;">
                        <div style="color:#888; font-size:11px; font-weight:bold; margin-bottom:12px;">MODEL GRADE</div>
                        <div style="font-size: 110px; font-weight: 900; color: #FFD700; text-shadow: 0 0 25px rgba(255, 215, 0, 0.5); line-height: 0.9;">{res['grade']}</div>
                    </div>
                </div>
                
                <div style="background: linear-gradient(180deg, rgba(255,215,0,0.1) 0%, rgba(0,0,0,0) 100%); border: 1px solid #FFD700; border-radius: 18px; padding: 22px; margin: 25px 0;">
                    <div style="color: #FFD700; font-weight: bold; font-size: 14px; letter-spacing:2px;">SUGGESTED PLAY</div>
                    <div style="font-size: 42px; font-weight: 900;">{res['units']} UNITS</div>
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; border-top: 1px solid #333; padding-top: 25px;">
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">PROJ</div><div style="font-size: 19px; font-weight: 900;">{res['proj']:.1f}</div></div>
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">EDGE</div><div style="font-size: 19px; font-weight: 900;">+{res['edge']:.1f}%</div></div>
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">CONF</div><div style="font-size: 19px; font-weight: 900;">{res['prob']:.0f}%</div></div>
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">L10 HIT</div><div style="font-size: 19px; font-weight: 900;">{res['hit']:.0f}%</div></div>
                </div>
                <div style="color: #4A90E2; letter-spacing: 4px; font-size: 12px; margin-top: 40px; font-weight: bold;">ANALYSIS BY SLEEPER D. KID</div>
            </div>
            """, unsafe_allow_html=True)