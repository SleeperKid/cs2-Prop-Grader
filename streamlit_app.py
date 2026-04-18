import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from scipy.stats import norm
from streamlit_gsheets import GSheetsConnection

# --- ⚙️ CORE UTILITIES ---
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

# --- 🧠 AI ENGINE (PERSISTENT DATA) ---
def run_ai_advisor():
    full_intel = load_intel_vault()
    game_key = "CS2" if st.session_state.game_choice == "CS2" else "VAL"
    intel = full_intel.get(game_key, {})
    
    context = st.session_state.m_context.lower()
    maps = st.session_state.p_maps.lower()
    rank = st.session_state.opp_rank_input
    
    analysis = {"w_h2h": 1.0, "w_tier": 1.0, "w_map": 1.0, "notes": []}

    # Rank & Intel Checks
    if rank <= 10: analysis["w_tier"] = 0.93; analysis["notes"].append(f"Top 10 Rank: Heavy Resistance.")
    
    for team, info in intel.get("team_styles", {}).items():
        if team.lower() in context:
            analysis["notes"].append(f"Intel: {info}")
            if "Aggressors" in info: analysis["w_h2h"] = 1.10

    # Auto-adjust Sliders
    st.session_state.w_h2h = analysis["w_h2h"]
    st.session_state.w_tier = analysis["w_tier"]
    st.session_state.ai_report = analysis
    st.rerun()

def sync_player_data():
    if st.session_state.player_selector != "Manual Entry":
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        base = safe_float(row.get('KPR'), 0.82)
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Free Agent')} vs "
        st.session_state.m1_kpr_input = base
        st.session_state.m2_kpr_input = base

# --- 🎨 UI & CUSTOM CSS ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# Persistence Keys
if 'initialized' not in st.session_state:
    st.session_state.update({
        'p_tag': "", 'm_context': "", 'p_maps': "", 'opp_rank_input': 15, 
        'l10': "", 'm1_kpr_input': 0.82, 'm2_kpr_input': 0.82, 
        'w_h2h': 1.0, 'w_tier': 1.0, 'w_map': 1.0, 'w_int': 1.0, 
        'results': None, 'initialized': True
    })

st.markdown("""
<style>
    /* 🚀 PREMIUM GLOW BUTTON */
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #FFD700 0%, #FFA500 100%);
        color: black; font-weight: 900; font-size: 20px;
        border: none; border-radius: 12px; height: 60px;
        box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3);
        transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(255, 215, 0, 0.5);
        color: white;
    }
    .metric-card { background: #1a1c23; border: 1px solid #333; border-radius: 15px; padding: 20px; text-align:center; }
</style>
""", unsafe_allow_html=True)

# --- 🛰️ SIDEBAR ---
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    if st.button("🤖 CONSULT AI ADVISOR"): run_ai_advisor()
    st.slider("H2H Advantage", 0.8, 1.2, key="w_h2h", step=0.05)
    st.slider("Opponent Tier", 0.8, 1.2, key="w_tier", step=0.05)
    st.slider("Map Fit", 0.8, 1.2, key="w_map", step=0.05)
    st.slider("Pressure/Form", 0.8, 1.2, key="w_int", step=0.05)

# --- 🕵️ MAIN BODY ---
st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
players = df[df['Game'] == st.session_state.game_choice]['Player'].tolist() if not df.empty else []

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Entry Intelligence")
    st.selectbox("Search Database", ["Manual Entry"] + players, key="player_selector", on_change=sync_player_data)
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    st.text_input("Projected Maps", key="p_maps")
    st.number_input("Opponent World Rank", key="opp_rank_input", min_value=1)
    
    if st.session_state.game_choice == "CS2":
        c1, c2 = st.columns(2)
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
    else:
        st.number_input("Base ADR", key="adr", value=140.0)
    
    st.text_area("L10 Data", key="l10")
    l1, l2 = st.columns(2)
    m_line = l1.number_input("Prop Line", value=31.5, step=0.5)
    m_side = l2.selectbox("Side", ["Over", "Under"])

    # 🚀 THE IMPROVED GRADE BUTTON
    if st.button("🚀 EXECUTE GRADING ENGINE", use_container_width=True):
        try:
            v_list = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
            weights = st.session_state.w_h2h * st.session_state.w_tier * st.session_state.w_map * st.session_state.w_int
            avg_kpr = (st.session_state.m1_kpr_input + st.session_state.m2_kpr_input) / 2
            proj = avg_kpr * 48 * weights
            edge = ((proj - m_line) / m_line * 100) if m_side == "Over" else ((m_line - proj) / m_line * 100)
            hit = (sum(1 for v in v_list if (v > m_line if m_side == "Over" else v < m_line)) / len(v_list)) * 100
            
            grade = "B"
            if edge > 22 and hit >= 70: grade = "S"
            elif edge > 15 and hit >= 60: grade = "A+"
            elif edge > 8: grade = "A"

            st.session_state.results = {"grade": grade, "proj": proj, "edge": edge, "line": m_line, "side": m_side, "hit": hit, "units": 2.5 if grade == "S" else 1.0}
        except: st.error("L10 Formatting Error.")

# --- 💎 OUTPUTS & CARD ---
with col_r:
    if st.session_state.results:
        res = st.session_state.results
        
        # Internal Dashboard Grade
        st.markdown(f"""<div class="metric-card">
            <div style="color:#888; font-size:12px; font-weight:bold;">MODEL GRADE</div>
            <div style="font-size: 110px; font-weight: 900; color: #FFD700; line-height:1;">{res['grade']}</div>
            <div style="color:{'#00FF00' if res['side'] == 'Over' else '#FF0000'}; font-size:24px; font-weight:bold;">{res['side'].upper()} {res['line']}</div>
        </div>""", unsafe_allow_html=True)
        
        st.divider()
        if st.checkbox("💎 Generate Sleeper D. Kid Social Card"):
            arrow = "▲" if res['side'] == "Over" else "▼"
            # 🟢 UPDATED SOCIAL CARD WITH ALL METRICS
            st.markdown(f"""
            <div style="background-color:#121212; border:2px solid #FFD700; border-radius:20px; padding:35px; width:450px; margin:auto; color:white; text-align:center; font-family:sans-serif;">
                <div style="color:#888; font-size:12px; letter-spacing:3px; margin-bottom:10px;">{st.session_state.game_choice.upper()} ANALYSIS</div>
                <div style="font-size:48px; font-weight:900; margin:0; line-height:1;">{st.session_state.p_tag.upper()}</div>
                <div style="color:#4A90E2; font-size:18px; font-weight:bold; margin-bottom:20px;">{st.session_state.m_context.upper()}</div>
                
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px;">
                    <div style="text-align:left;">
                        <div style="color:#888; font-size:11px; font-weight:bold;">PROP LINE</div>
                        <div style="font-size:75px; font-weight:900; line-height:1;">{res['line']}</div>
                        <span style="color:{'#00FF00' if res['side'] == 'Over' else '#FF0000'}; border:1px solid {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; padding:4px 10px; border-radius:8px; font-weight:900; font-size:14px;">{arrow} {res['side'].upper()}</span>
                    </div>
                    <div style="text-align:center; width:140px;">
                        <div style="color:#888; font-size:11px; font-weight:bold;">GRADE</div>
                        <div style="font-size:100px; font-weight:900; color:#FFD700; text-shadow:0 0 20px rgba(255,215,0,0.5); line-height:0.9;">{res['grade']}</div>
                    </div>
                </div>

                <div style="background:rgba(255,215,0,0.1); border:1px solid #FFD700; border-radius:15px; padding:15px; margin-bottom:25px;">
                    <div style="color:#FFD700; font-size:12px; font-weight:bold;">SUGGESTED PLAY</div>
                    <div style="font-size:36px; font-weight:900;">{res['units']} UNITS</div>
                </div>

                <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; border-top:1px solid #333; padding-top:20px;">
                    <div><div style="font-size:10px; color:#666;">PROJ {"KILLS" if st.session_state.game_choice == "CS2" else "HS"}</div><div style="font-size:22px; font-weight:900;">{res['proj']:.1f}</div></div>
                    <div><div style="font-size:10px; color:#666;">MODEL EDGE</div><div style="font-size:22px; font-weight:900;">+{res['edge']:.1f}%</div></div>
                    <div><div style="font-size:10px; color:#666;">L10 HIT</div><div style="font-size:22px; font-weight:900;">{res['hit']:.0f}%</div></div>
                </div>
                <div style="color: #4A90E2; letter-spacing: 4px; font-size: 11px; margin-top: 30px; font-weight: bold;">ANALYSIS BY SLEEPER D. KID</div>
            </div>
            """, unsafe_allow_html=True)