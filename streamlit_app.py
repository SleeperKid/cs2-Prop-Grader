import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from scipy.stats import norm
from streamlit_gsheets import GSheetsConnection

# --- ⚙️ UTILITIES & DATA ---
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

# --- 🧠 AI & STATE ENGINE ---
def run_ai_advisor():
    """Reads deep intel and nudges sliders."""
    full_intel = load_intel_vault()
    game_key = "CS2" if st.session_state.game_choice == "CS2" else "VAL"
    intel = full_intel.get(game_key, {})
    
    # Read current state
    context = st.session_state.m_context.lower()
    maps = st.session_state.p_maps.lower()
    m1_kpr = st.session_state.m1_kpr_input
    tier_choice = st.session_state.tier_select
    
    analysis = {
        "w_h2h": {"val": 1.00, "note": "Neutral."},
        "w_tier": {"val": 1.00, "note": "Standard."},
        "w_map": {"val": 1.00, "note": "Standard."},
        "w_int": {"val": 1.00, "note": "Standard."}
    }

    # Intel Logic
    for team, style in intel.get("team_styles", {}).items():
        if team.lower() in context:
            analysis["w_tier"]["note"] = f"Intel: {style}"
            if "Tactical" in style: analysis["w_tier"]["val"] = 0.90
            if "Aggressors" in style: analysis["w_tier"]["val"] = 1.10

    for m_name, m_desc in intel.get("maps", {}).items():
        if m_name.lower() in maps:
            analysis["w_map"]["note"] = f"Map: {m_desc[:50]}..."
            if "High-exec" in m_desc: analysis["w_map"]["val"] = 0.95
            if "Aim Map" in m_desc: analysis["w_map"]["val"] = 1.10

    # Apply & Rerun
    st.session_state.w_h2h = analysis["w_h2h"]["val"]
    st.session_state.w_tier = analysis["w_tier"]["val"]
    st.session_state.w_map = analysis["w_map"]["val"]
    st.session_state.w_int = 1.05 if m1_kpr > 0.88 else 1.00
    st.session_state.ai_report = analysis
    st.rerun()

def sync_player_data():
    """Auto-populates and locks data to state."""
    if st.session_state.player_selector != "Manual Entry":
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        base_kpr = safe_float(row.get('KPR'), 0.82)
        
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Free Agent')} vs "
        st.session_state.m1_kpr_input = base_kpr
        st.session_state.m2_kpr_input = base_kpr

# --- 🎨 UI CONFIG ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# Initialize all keys globally to prevent resets
defaults = {
    'p_tag': "", 'm_context': "", 'p_maps': "", 'l10': "", 
    'm1_kpr_input': 0.82, 'm2_kpr_input': 0.82, 'w_h2h': 1.0, 
    'w_tier': 1.0, 'w_map': 1.0, 'w_int': 1.0, 'ai_report': None, 'results': None
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 🛰️ SIDEBAR: AI & WEIGHTS ---
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    if st.button("🤖 CONSULT AI ADVISOR", use_container_width=True):
        run_ai_advisor()
    
    if st.session_state.ai_report:
        for k, data in st.session_state.ai_report.items():
            st.caption(f"**{k.upper()}: {data['val']}** - {data['note']}")
    
    st.divider()
    st.slider("H2H Advantage", 0.8, 1.2, key="w_h2h", step=0.05)
    st.slider("Opponent Tier", 0.8, 1.2, key="w_tier", step=0.05)
    st.slider("Map Fit", 0.8, 1.2, key="w_map", step=0.05)
    st.slider("Pressure/Form", 0.8, 1.2, key="w_int", step=0.05)

# --- 🕵️ MAIN BODY: DATA ENTRY ---
st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
players = df[df['Game'] == st.session_state.game_choice]['Player'].tolist() if not df.empty else []

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Intelligence")
    st.selectbox("Search Database", ["Manual Entry"] + players, key="player_selector", on_change=sync_player_data)
    
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    st.text_input("Projected Maps", key="p_maps")
    
    # Tournament Tier
    t_intel = load_intel_vault().get(st.session_state.game_choice, {}).get("tournaments", {})
    st.selectbox("Tournament Tier", list(t_intel.keys()) if t_intel else ["S-Tier (Elite)"], key="tier_select")
    
    if st.session_state.game_choice == "CS2":
        c1, c2 = st.columns(2)
        # 🟢 CRITICAL: Removed 'value=' to allow 'key=' to manage state without resetting
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
    else:
        st.number_input("Base ADR", key="adr", value=140.0)
        
    st.text_area("L10 Data (CSV)", key="l10")
    
    # Lines
    l_c1, l_c2 = st.columns(2)
    m_line = l_c1.number_input("Prop Line", value=31.5, step=0.5)
    m_side = l_c2.selectbox("Side", ["Over", "Under"])

    if st.button("🚀 EXECUTE GRADING ENGINE", use_container_width=True):
        try:
            v_list = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
            weights = st.session_state.w_h2h * st.session_state.w_tier * st.session_state.w_map * st.session_state.w_int
            
            # MATH
            avg_kpr = (st.session_state.m1_kpr_input + st.session_state.m2_kpr_input) / 2
            proj = avg_kpr * 48 * weights
            edge = (proj - m_line) if m_side == "Over" else (m_line - proj)
            edge_pct = (edge / m_line) * 100
            hit_rate = (sum(1 for v in v_list if (v > m_line if m_side == "Over" else v < m_line)) / len(v_list)) * 100
            
            st.session_state.results = {
                "grade": "S" if edge_pct > 18 else "A+" if edge_pct > 10 else "A",
                "proj": proj, "edge": edge_pct, "line": m_line, "side": m_side,
                "hit": hit_rate, "prob": 85 + (edge_pct/5), "units": 2.5 if edge_pct > 18 else 1.0
            }
        except: st.error("Data error. Check L10 values.")

# --- 📊 MODEL BREAKDOWN & SOCIAL CARD ---
with col_r:
    if st.session_state.results:
        res = st.session_state.results
        
        # 🟢 RESTORED DETAILS
        st.subheader("📊 Model Breakdown")
        m1, m2, m3 = st.columns(3)
        m1.metric("Projection", f"{res['proj']:.1f}")
        m2.metric("Edge", f"+{res['edge']:.1f}%", delta=res['grade'])
        m3.metric("L10 Hit", f"{res['hit']:.0f}%")
        
        st.write("---")
        
        if st.checkbox("💎 Generate Sleeper D. Kid Social Card"):
            arrow = "▲" if res['side'] == "Over" else "▼"
            # CSS Shielded Card
            st.markdown(f"""
            <div style="background-color:#121212; border:2px solid #FFD700; border-radius:20px; padding:35px; width:450px; margin:auto; color:white; text-align:center; font-family:sans-serif;">
                <div style="color:#888; font-size:12px; margin-bottom:10px;">{st.session_state.game_choice.upper()} PROP ANALYSIS</div>
                <div style="font-size:48px; font-weight:900; margin:0;">{st.session_state.p_tag.upper()}</div>
                <div style="color:#4A90E2; font-size:18px; margin-bottom:20px;">{st.session_state.m_context.upper()}</div>
                <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div style="text-align:left;">
                        <div style="color:#888; font-size:11px;">PROP LINE</div>
                        <div style="font-size:75px; font-weight:900; line-height:1;">{res['line']}</div>
                        <span style="color:{'#00FF00' if res['side'] == 'Over' else '#FF0000'}; border:1px solid {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; padding:4px 10px; border-radius:8px; font-weight:900;">{arrow} {res['side'].upper()}</span>
                    </div>
                    <div style="text-align:center;">
                        <div style="color:#888; font-size:11px;">MODEL GRADE</div>
                        <div style="font-size:100px; font-weight:900; color:#FFD700; text-shadow:0 0 20px rgba(255,215,0,0.5); line-height:0.9;">{res['grade']}</div>
                    </div>
                </div>
                <div style="background:rgba(255,215,0,0.1); border:1px solid #FFD700; border-radius:15px; padding:15px; margin:20px 0;">
                    <div style="font-size:32px; font-weight:900;">{res['units']} UNITS</div>
                </div>
                <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:5px;">
                    <div><div style="font-size:10px; color:#666;">PROJ</div><div style="font-size:16px; font-weight:900;">{res['proj']:.1f}</div></div>
                    <div><div style="font-size:10px; color:#666;">EDGE</div><div style="font-size:16px; font-weight:900;">+{res['edge']:.1f}%</div></div>
                    <div><div style="font-size:10px; color:#666;">CONF</div><div style="font-size:16px; font-weight:900;">{res['prob']:.0f}%</div></div>
                    <div><div style="font-size:10px; color:#666;">L10 HIT</div><div style="font-size:16px; font-weight:900;">{res['hit']:.0f}%</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)