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
    except:
        return pd.DataFrame()

def load_intel_vault():
    if os.path.exists("intel_vault.json"):
        with open("intel_vault.json", "r") as f: return json.load(f)
    return {"teams": {}, "maps": {}}

# --- 🧠 AI ADVISOR: DEEP DATA READ ---
def run_ai_advisor():
    """Reads deep profile data, rank, and JSON to move sliders."""
    intel = load_intel_vault()
    
    # 🟢 FORCING THE READ: Pulling current widget values
    context = st.session_state.get('m_context', "").lower()
    maps = st.session_state.get('p_maps', "").lower()
    rank = safe_float(st.session_state.get('opp_rank', 0), 0)
    m1_kpr = st.session_state.get('m1_kpr_input', 0.82)
    
    analysis = {
        "w_h2h": {"val": 1.00, "note": "Neutral Matchup."},
        "w_tier": {"val": 1.00, "note": "Standard Tier."},
        "w_map": {"val": 1.00, "note": "Standard Map Fit."},
        "w_int": {"val": 1.00, "note": "Standard Momentum."}
    }

    # 1. Opponent Rank Logic (H2H Advantage)
    if rank > 0:
        if rank <= 5: 
            analysis["w_h2h"]["val"] = 0.90
            analysis["w_h2h"]["note"] = f"Opponent Rank #{int(rank)}: Expect low-frag tactical struggle."
        elif rank > 20:
            analysis["w_h2h"]["val"] = 1.10
            analysis["w_h2h"]["note"] = f"Opponent Rank #{int(rank)}: High frag potential vs lower tier."

    # 2. Intel Vault: Teams & Strategy
    for team, data in intel.get("teams", {}).items():
        if team.lower() in context:
            analysis["w_tier"]["val"] = data.get("tier_weight", 1.0)
            strat = data.get("strategy", "Standard")
            analysis["w_tier"]["note"] = f"Intel: {strat} | Tier Weight: {analysis['w_tier']['val']}"

    # 3. Intel Vault: Maps
    for m_name, data in intel.get("maps", {}).items():
        if m_name.lower() in maps:
            analysis["w_map"]["val"] = data.get("difficulty_modifier", 1.0)
            analysis["w_map"]["note"] = f"Map: {m_name.title()} is {data.get('type')}."

    # 4. Momentum (Internal KPR)
    if m1_kpr > 0.90:
        analysis["w_int"]["val"] = 1.05
        analysis["w_int"]["note"] = "Hot Streak: KPR is currently peaked."

    # 🟢 HARD-LOCK TO SLIDERS
    st.session_state.w_h2h = analysis["w_h2h"]["val"]
    st.session_state.w_tier = analysis["w_tier"]["val"]
    st.session_state.w_map = analysis["w_map"]["val"]
    st.session_state.w_int = analysis["w_int"]["val"]
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

# --- 🎨 UI INITIALIZATION ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# Initialize Persistence
if 'initialized' not in st.session_state:
    for k, v in {'p_tag': "", 'm_context': "", 'p_maps': "", 'opp_rank': 0, 'l10': "", 
                 'm1_kpr_input': 0.82, 'm2_kpr_input': 0.82, 'w_h2h': 1.0, 
                 'w_tier': 1.0, 'w_map': 1.0, 'w_int': 1.0, 'ai_report': None, 
                 'results': None, 'initialized': True}.items():
        st.session_state[k] = v

# --- 🛰️ SIDEBAR: AI ADVISOR ---
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    if st.button("🤖 CONSULT AI ADVISOR", use_container_width=True):
        run_ai_advisor()

    if st.session_state.ai_report:
        for k, data in st.session_state.ai_report.items():
            st.markdown(f"**{k.split('_')[1].upper()}: {data['val']:.2f}**")
            st.caption(data['note'])
    
    st.divider()
    st.slider("H2H Advantage", 0.8, 1.2, key="w_h2h", step=0.05)
    st.slider("Opponent Tier", 0.8, 1.2, key="w_tier", step=0.05)
    st.slider("Map Fit", 0.8, 1.2, key="w_map", step=0.05)
    st.slider("Pressure/Form", 0.8, 1.2, key="w_int", step=0.05)

# --- 🕵️ MAIN BODY: DEEP PROFILE ---
game_mode = st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
players = df[df['Game'] == game_mode]['Player'].tolist() if not df.empty else []

col1, col2 = st.columns([1, 1.2], gap="large")

with col1:
    st.subheader("🕵️ Deep Profile Intelligence")
    st.selectbox("Search Database", ["Manual Entry"] + players, key="player_selector", on_change=sync_player_data)
    
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    st.text_input("Projected Maps", key="p_maps")
    st.number_input("Opponent World Rank", key="opp_rank", min_value=0, step=1)
    
    if game_mode == "CS2":
        c1, c2 = st.columns(2)
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
    else:
        st.number_input("Base ADR", key="adr", value=140.0)
    
    st.text_area("L10 Data", key="l10")
    
    # Line Entry
    l_col1, l_col2 = st.columns(2)
    line = l_col1.number_input("Prop Line", value=31.5, step=0.5)
    side = l_col2.selectbox("Target Side", ["Over", "Under"])

    if st.button("🚀 EXECUTE GRADING ENGINE", use_container_width=True):
        try:
            vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
            weights = st.session_state.w_h2h * st.session_state.w_tier * st.session_state.w_map * st.session_state.w_int
            proj = ((st.session_state.m1_kpr_input + st.session_state.m2_kpr_input) / 2) * 48 * weights
            edge = (proj - line) / line * 100 if side == "Over" else (line - proj) / line * 100
            st.session_state.results = {"grade": "S" if edge > 15 else "A", "proj": proj, "edge": edge, "line": line, "side": side, "hit": 70, "prob": 88, "units": 2.5}
        except: st.error("Verification failed. Check L10 formatting.")

# --- 💎 OUTPUTS ---
with col2:
    if st.session_state.results:
        res = st.session_state.results
        st.metric("Mathematical Edge", f"+{res['edge']:.1f}%", delta=res['grade'])
        
        # Plain text share box (No HTML here)
        st.text_area("📋 Copy for Discord", f"🚨 {st.session_state.p_tag.upper()} {res['side'].upper()}\nLine: {res['line']} | Grade: {res['grade']}")
        
        if st.checkbox("💎 Generate Sleeper D. Kid Social Card"):
            arrow = "▲" if res['side'] == "Over" else "▼"
            # 🛡️ SHIELDED HTML RENDER
            st.markdown(f"""
            <div style="background-color: #121212; border: 2px solid #FFD700; border-radius: 25px; padding: 40px; width: 450px; margin: auto; color: white; text-align: center; font-family: sans-serif;">
                <div style="color: #888; letter-spacing: 3px; font-size: 13px; margin-bottom:12px;">{game_mode.upper()} PROP ANALYSIS</div>
                <div style="font-size: 50px; font-weight: 900; margin: 0; line-height:1;">{st.session_state.p_tag.upper()}</div>
                <div style="color: #4A90E2; font-size: 18px; font-weight: bold; margin-bottom: 25px; border-bottom: 1px solid #333; padding-bottom: 18px;">{st.session_state.m_context.upper()}</div>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 10px 0;">
                    <div style="text-align: left; flex: 1;">
                        <div style="color:#888; font-size:11px; font-weight:bold;">THE PROP LINE</div>
                        <div style="font-size: 80px; font-weight: 900; line-height:1;">{res['line']}</div>
                        <span style="color: {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; border: 1px solid {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; padding: 5px 12px; border-radius: 8px; font-weight: 900;">{arrow} {res['side'].upper()}</span>
                    </div>
                    <div style="width: 140px; text-align: center;">
                        <div style="color:#888; font-size:11px; font-weight:bold; margin-bottom:12px;">MODEL GRADE</div>
                        <div style="font-size: 110px; font-weight: 900; color: #FFD700; text-shadow: 0 0 25px rgba(255, 215, 0, 0.5); line-height: 0.9;">{res['grade']}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)