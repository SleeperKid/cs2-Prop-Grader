import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os
import json
from groq import Groq
import re
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 🧠 INTELLIGENCE VAULT LOADER
# ==========================================
def load_intel():
    """Loads the external Brain from JSON with error protection"""
    if os.path.exists("intel_vault.json"):
        try:
            with open("intel_vault.json", "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            st.error("⚠️ Typo detected in intel_vault.json!")
            return {}
    return {}

INTEL = load_intel()

# ==========================================
# 📥 THE ONLY LOAD_VAULT (GOOGLE SHEETS)
# ==========================================
@st.cache_data(ttl=10)
def load_vault():
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Load VAL
        try:
            val_df = conn.read(spreadsheet=sheet_url, worksheet="VAL_DATA", ttl=0)
            val_df['Game'] = 'Valorant'
        except:
            val_df = pd.DataFrame()

        # Load CS2
        try:
            cs_df = conn.read(spreadsheet=sheet_url, worksheet="CS2_DATA", ttl=0)
            cs_df['Game'] = 'CS2'
        except:
            cs_df = pd.DataFrame()
        
        # Diagnostics in the sidebar
        st.sidebar.write(f"📊 VAL Found: {len(val_df)}")
        st.sidebar.write(f"📊 CS2 Found: {len(cs_df)}")

        # Ensure CS2 has the columns the UI expects even if it's empty
        for col in ['Team', 'Agents', 'ADR', 'ACS']:
            if not cs_df.empty and col not in cs_df.columns: cs_df[col] = "N/A"
            if not val_df.empty and col not in val_df.columns: val_df[col] = "N/A"

        # Combine them
        if val_df.empty and cs_df.empty:
            return pd.DataFrame()
        
        return pd.concat([val_df, cs_df], ignore_index=True).fillna("N/A")
            
    except Exception as e:
        st.error(f"❌ Load Error: {e}")
        return pd.DataFrame()

# ==========================================
# 🎨 ELITE UI STYLING & HELPERS
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide", page_icon="🎯")
st.markdown("""<style>.main { background-color: #0e1117; } .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #238636; color: white; font-weight: bold; border: none; } .grade-card { padding: 30px; border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; margin-bottom: 20px; } .grade-text { font-size: 90px; font-weight: 900; margin: 0; line-height: 1; } .advice-box { background: #1c2128; padding: 15px; border-radius: 10px; border: 1px solid #30363d; font-size: 0.85rem; color: #58a6ff; margin-bottom: 10px; }</style>""", unsafe_allow_html=True)

def get_grade_details(edge):
    if edge >= 12.0: return "S", "linear-gradient(135deg, #FFD700, #FFA500)", "#FFD700", 2.5
    if edge >= 8.0: return "A+", "linear-gradient(135deg, #00FF00, #008000)", "#00FF00", 2.0
    if edge >= 3.0: return "A", "linear-gradient(135deg, #ADFF2F, #228B22)", "#ADFF2F", 1.0
    if edge >= 0.0: return "B", "linear-gradient(135deg, #F0E68C, #DAA520)", "#F0E68C", 0.5
    return "F", "linear-gradient(135deg, #8B0000, #000000)", "#FF4500", 0.0

def get_implied_prob(odds):
    return (abs(odds) / (abs(odds) + 100)) * 100 if odds < 0 else (100 / (odds + 100)) * 100

# ==========================================
# 📥 INITIALIZE DATA
# ==========================================
df = load_vault()

# Initialize Session States
states = {
    'h2h_val': 1.0, 'tier_val': 1.0, 'map_val': 1.0, 'int_val': 1.0, 
    'weight_advice': None, 'analysis_results': None, 
    'm_context_val': "Team vs Opponent", 'last_player': None, 
    'p_tag_val': "", 'l10_val': "", 'kpr_val': 0.80, 
    'stat_type_val': "Kills", 'tourney_val': "S-Tier (Elite)"
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

# ==========================================
# ⚙️ SIDEBAR: AI ADVISOR
# ==========================================
with st.sidebar:
    st.header("⚙️ Model Intelligence")
    if st.button("GET AI SLIDER ADVICE"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if not api_key: st.error("API Key missing.")
        else:
            client = Groq(api_key=api_key)
            with st.spinner("Analyzing Match Context..."):
                prompt = f"Act as a pro analyst. Analyze {st.session_state.m_context_val} for {st.session_state.tourney_val}. Return 4 weights (0.85-1.15) for H2H, Tier, Map, Intensity. Format: H2H: [X] | Tier: [X] | Map: [X] | Int: [X]"
                completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.0)
                st.session_state.weight_advice = completion.choices[0].message.content
                found_weights = re.findall(r"([0-1]\.\d+)", st.session_state.weight_advice)
                if len(found_weights) >= 4:
                    st.session_state.h2h_val = float(found_weights[0])
                    st.session_state.tier_val = float(found_weights[1])
                    st.session_state.map_val = float(found_weights[2])
                    st.session_state.int_val = float(found_weights[3])

    if st.session_state.weight_advice: 
        st.markdown(f'<div class="advice-box"><b>Vault Intelligence:</b><br>{st.session_state.weight_advice}</div>', unsafe_allow_html=True)
    
    st.divider()
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, key="h2h_val")
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, key="tier_val")
    map_w = st.slider("Map Fit", 0.80, 1.20, key="map_val")
    int_w = st.slider("Match Intensity", 0.70, 1.10, key="int_val")

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
st.title("🎯 Prop Grader Elite")

if df.empty:
    st.error("❌ The Vault is empty or disconnected. Check Sidebar for Error.")
else:
    col_l, col_r = st.columns([1, 1.2], gap="large")

    with col_l:
        st.subheader("📋 Prop & Context")
        game_choice = st.radio("Game", ["CS2", "Valorant"], horizontal=True)
        
        # Database Filtering
        db_players = df[df['Game'] == game_choice]['Player'].tolist()
        selected_name = st.selectbox("Database Search", ["Manual Entry"] + db_players)
        
        if selected_name != st.session_state.last_player and selected_name != "Manual Entry":
            p_row = df[df['Player'] == selected_name].iloc[0]
            st.session_state.p_tag_val = str(p_row['Player'])
            st.session_state.l10_val = str(p_row['L10'])
            st.session_state.kpr_val = float(p_row['KPR'])
            st.session_state.m_context_val = f"{p_row.get('Team', 'Team')} vs "
            st.session_state.last_player = selected_name
            st.rerun()

        st.text_input("Player Tag", key="p_tag_val")
        st.text_input("Matchup Context", key="m_context_val")
        l10_raw = st.text_area("L10 Stats (Comma Separated)", key="l10_val")
        base_rate = st.number_input("Base KPR", key="kpr_val", step=0.01)

        c1, c2 = st.columns(2)
        with c1: m_line, m_side = st.number_input("Line", value=35.5, step=0.5), st.selectbox("Side", ["Over", "Under"])
        with c2: m_odds, m_scope = st.number_input("Odds (American)", value=-128), st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

    if st.button("RUN ELITE ANALYSIS"):
        try:
            vals = [float(x.strip()) for x in l10_raw.split(",") if x.strip()]
            mean_v, stdev = np.mean(vals), max(np.std(vals, ddof=1) if len(vals) > 1 else 1.0, 1.0)
            hit_rate = (sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line)) / len(vals)) * 100
            
            # Dynamic Round Multiplier (26 for Val, 24 for CS2)
            game_mult = 26 if game_choice == "Valorant" else 24
            scope_map = {"Maps 1 & 2": 1.0, "Map 1 Only": 0.5, "Full Match": 1.25}
            
            proj = (base_rate * game_mult * scope_map.get(m_scope, 1.0)) * h2h_w * rank_w * map_w * int_w
            
            prob_under = norm.cdf(m_line, loc=proj, scale=stdev)
            model_prob = (1 - prob_under) * 100 if m_side == "Over" else prob_under * 100
            edge = model_prob - get_implied_prob(m_odds)
            grade, color, flat, units = get_grade_details(edge)
            
            st.session_state.analysis_results = {
                "p_tag": st.session_state.p_tag_val, "side": m_side, "line": m_line, 
                "grade": grade, "color": color, "units": units, "proj": proj, 
                "edge": edge, "hit_rate": hit_rate, "game": game_choice, "flat": flat
            }
        except Exception as e: st.error(f"Analysis Error: {e}")

    with col_r:
        if st.session_state.analysis_results:
            res = st.session_state.analysis_results
            arrow = "▲" if res['side'] == "Over" else "▼"
            st.markdown(f"""<div class="grade-card" style="background: {res['color']};">
                <div style="font-size: 28px; font-weight: 900;">{res['p_tag'].upper()}</div>
                <div style="font-size: 24px; font-weight: 900;">{arrow} {res['side'].upper()} {res['line']}</div>
                <h1 class="grade-text">{res['grade']}</h1>
                <div style="font-size: 20px; font-weight: bold;">{res['units']} UNIT PLAY</div>
            </div>""", unsafe_allow_html=True)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Projected", f"{res['proj']:.1f}")
            m2.metric("Edge", f"{res['edge']:.1f}%")
            m3.metric("L10 Hit", f"{res['hit_rate']:.0f}%")