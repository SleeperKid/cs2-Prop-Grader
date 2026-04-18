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

# --- 🧠 AI ENGINE (V101: HS% & UNDER LOGIC) ---
def run_ai_advisor():
    """Deep-scans JSON to move sliders and provide meta-context."""
    full_intel = load_intel_vault()
    game_key = "CS2" if st.session_state.game_choice == "CS2" else "VAL"
    intel = full_intel.get(game_key, {})
    
    context = st.session_state.m_context.lower()
    maps = st.session_state.p_maps.lower()
    p_type = st.session_state.prop_type_select
    
    analysis = {"w_h2h": 1.0, "w_tier": 1.0, "w_map": 1.0, "w_int": 1.0, "notes": []}

    # 1. CS2 Headshot/Map Logic
    if game_key == "CS2":
        for map_name, desc in intel.get("maps", {}).items():
            if map_name.lower() in maps:
                analysis["notes"].append(f"Map Context: {desc}")
                if p_type == "Headshot Kills":
                    if "HS props" in desc or "HS%" in desc: 
                        analysis["w_map"] = 1.10 if "High HS" in desc else 0.90
    
    # 2. Valorant "Under" & Archetype Logic
    if game_key == "VAL":
        for team, style in intel.get("team_styles", {}).items():
            if team.lower() in context:
                analysis["notes"].append(f"Style Intel: {style}")
                if "Utility Executioners" in style and st.session_state.side_select == "Under":
                    analysis["w_tier"] = 1.08 # Confirmed: Executioners suppress kills
                    analysis["notes"].append("🔥 HIGH CONVICTION UNDER: Utility meta minimizes duels.")

    # Apply & Sync
    for k in ["w_h2h", "w_tier", "w_map"]:
        st.session_state[k] = analysis[k]
    st.session_state.ai_report = analysis
    st.rerun()

def sync_player_data():
    if st.session_state.player_selector != "Manual Entry":
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'FA')} vs "
        st.session_state.m1_kpr_input = safe_float(row.get('KPR'), 0.82)
        st.session_state.m2_kpr_input = safe_float(row.get('KPR'), 0.82)
        st.session_state.hs_pct_input = safe_float(row.get('HS%'), 45.0)

# --- 🎨 UI & CUSTOM CSS ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

if 'initialized' not in st.session_state:
    st.session_state.update({
        'p_tag': "", 'm_context': "", 'p_maps': "", 'opp_rank_input': 15, 
        'l10': "", 'm1_kpr_input': 0.82, 'm2_kpr_input': 0.82, 'hs_pct_input': 45.0,
        'w_h2h': 1.0, 'w_tier': 1.0, 'w_map': 1.0, 'w_int': 1.0, 'results': None, 'initialized': True
    })

# --- 🛰️ SIDEBAR ---
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    if st.button("🤖 CONSULT AI ADVISOR", use_container_width=True): run_ai_advisor()
    
    if st.session_state.get('ai_report'):
        for note in st.session_state.ai_report["notes"]:
            st.caption(f"• {note}")
    
    st.divider()
    st.slider("H2H Advantage", 0.8, 1.2, key="w_h2h", step=0.05)
    st.slider("Opponent Tier", 0.8, 1.2, key="w_tier", step=0.05)
    st.slider("Map Fit", 0.8, 1.2, key="w_map", step=0.05)
    st.slider("Pressure/Form", 0.8, 1.2, key="w_int", step=0.05)

# --- 🕵️ MAIN BODY ---
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
    st.selectbox("Search Database", ["Manual Entry"] + (df[df['Game'] == st.session_state.game_choice]['Player'].tolist() if not df.empty else []), key="player_selector", on_change=sync_player_data)
    
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    st.text_input("Projected Maps", key="p_maps")
    st.number_input("Opponent World Rank", key="opp_rank_input")
    
    # 🟢 PROTOTYPE OPTIMIZATION: CS2 HS & VAL ADR
    if st.session_state.game_choice == "CS2":
        st.selectbox("Prop Type", ["Kills", "Headshot Kills"], key="prop_type_select")
        c1, c2, c3 = st.columns(3)
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
        c3.number_input("Player HS%", key="hs_pct_input", format="%.1f")
    else:
        # Optimized VAL Math: Base ADR + Agent Coefficient
        st.number_input("Base ADR", key="adr_input", value=140.0)
        st.selectbox("Agent Archetype", ["Duelist", "Initiator", "Sentinel", "Controller"], key="val_role_select")
    
    st.text_area("L10 Data", key="l10")
    
    l_c1, l_c2 = st.columns(2)
    m_line = l_c1.number_input("Prop Line", value=31.5, step=0.5)
    m_side = l_c2.selectbox("Side", ["Over", "Under"], key="side_select")

    if st.button("🚀 EXECUTE GRADING ENGINE", use_container_width=True):
        try:
            v_list = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
            weights = st.session_state.w_h2h * st.session_state.w_tier * st.session_state.w_map * st.session_state.w_int
            
            if st.session_state.game_choice == "CS2":
                proj = ((st.session_state.m1_kpr_input + st.session_state.m2_kpr_input) / 2) * 48 * weights
                if st.session_state.prop_type_select == "Headshot Kills":
                    proj = proj * (st.session_state.hs_pct_input / 100)
            else:
                # Valorant Optimization: Rounds based on meta pacing (42 round avg for BO3)
                role_mod = 1.15 if st.session_state.val_role_select == "Duelist" else 0.95
                proj = (st.session_state.adr_input / 140) * 42 * weights * role_mod
            
            edge_pct = ((proj - m_line) / m_line * 100) if m_side == "Over" else ((m_line - proj) / m_line * 100)
            hit_rate = (sum(1 for v in v_list if (v > m_line if m_side == "Over" else v < m_line)) / len(v_list)) * 100
            
            # ELITE CALIBRATION: S-Grade requires 22% Edge & 70% Hit
            grade = "S" if edge_pct > 22 and hit_rate >= 70 else "A+" if edge_pct > 15 and hit_rate >= 60 else "A" if edge_pct > 8 else "B"

            st.session_state.results = {"grade": grade, "proj": proj, "edge": edge_pct, "line": m_line, "side": m_side, "hit": hit_rate, "units": 2.5 if grade == "S" else 1.0}
        except: st.error("Verification failed.")

# --- 💎 OUTPUT SECTION ---
with col_r:
    if st.session_state.results:
        res = st.session_state.results
        # 🟢 INTERNAL GRADE DASHBOARD (CSS Bleed Shielded)
        st.markdown(f"""
        <div style="background:#1a1c23; border: 1px solid #333; border-radius:15px; padding:25px; text-align:center;">
            <div style="color:#888; font-size:12px; font-weight:bold;">MODEL DECISION</div>
            <div style="font-size: 110px; font-weight: 900; color: #FFD700; line-height:1;">{res['grade']}</div>
            <div style="color:{'#00FF00' if res['side'] == 'Over' else '#FF0000'}; font-weight:bold; font-size:24px;">{res['side'].upper()} {res['line']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Projection", f"{res['proj']:.1f}")
        m2.metric("Edge", f"+{res['edge']:.1f}%")
        m3.metric("L10 Hit", f"{res['hit']:.0f}%")
        
        if st.checkbox("💎 Generate Social Media Share Card"):
            arrow = "▲" if res['side'] == "Over" else "▼"
            st.markdown(f"""
            <div style="background-color:#121212; border:2px solid #FFD700; border-radius:20px; padding:35px; width:450px; margin:auto; color:white; text-align:center; font-family:sans-serif;">
                <div style="font-size:48px; font-weight:900; margin:0; line-height:1;">{st.session_state.p_tag.upper()}</div>
                <div style="color:#4A90E2; font-size:18px; font-weight:bold; margin:10px 0 20px 0;">{st.session_state.m_context.upper()}</div>
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
            </div>
            """, unsafe_allow_html=True)