import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os
from groq import Groq
import re

# ==========================================
# 🎨 UI & STYLING
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
# 🧠 ANALYTICS ENGINE
# ==========================================
def get_grade_details(edge):
    if edge >= 12.0: return "S", "linear-gradient(135deg, #FFD700, #FFA500)", "#FFD700", 2.5
    if edge >= 8.0: return "A+", "linear-gradient(135deg, #00FF00, #008000)", "#00FF00", 2.0
    if edge >= 3.0: return "A", "linear-gradient(135deg, #ADFF2F, #228B22)", "#ADFF2F", 1.0
    if edge >= 0.0: return "B", "linear-gradient(135deg, #F0E68C, #DAA520)", "#DAA520", 0.5
    return "F", "linear-gradient(135deg, #8B0000, #000000)", "#FF4500", 0.0

def get_implied_prob(odds):
    return (abs(odds) / (abs(odds) + 100)) * 100 if odds < 0 else (100 / (odds + 100)) * 100

# ==========================================
# 📥 DATA LOADING
# ==========================================
@st.cache_data
def load_vault():
    if os.path.exists("daily_stats.csv"):
        return pd.read_csv("daily_stats.csv")
    return pd.DataFrame(columns=["Player", "Game", "Team", "BaseKPR", "L10", "ExpectedMaps"])

df = load_vault()

# Initialize session states for sliders
if 'h2h_val' not in st.session_state: st.session_state.h2h_val = 1.0
if 'tier_val' not in st.session_state: st.session_state.tier_val = 1.0
if 'map_val' not in st.session_state: st.session_state.map_val = 1.0
if 'int_val' not in st.session_state: st.session_state.int_val = 1.0

# ==========================================
# 🛠️ SIDEBAR CONTROLS
# ==========================================
with st.sidebar:
    st.header("⚙️ Model Weights")
    st.session_state.h2h_val = st.slider("H2H Advantage", 0.80, 1.20, st.session_state.h2h_val, 0.05)
    st.session_state.tier_val = st.slider("Opponent Tier", 0.80, 1.20, st.session_state.tier_val, 0.05)
    st.session_state.map_val = st.slider("Map Fit", 0.80, 1.20, st.session_state.map_val, 0.05)
    st.session_state.int_val = st.slider("Match Intensity", 0.70, 1.10, st.session_state.int_val, 0.05)
    
    st.divider()
    if st.button("♻️ CLEAR DATA CACHE"):
        st.cache_data.clear()
        st.rerun()

# ==========================================
# 🎯 MAIN INTERFACE
# ==========================================
st.title("🎯 Prop Grader Elite")

col_left, col_right = st.columns([1, 1.2], gap="large")

with col_left:
    st.subheader("📋 Prop Selection")
    
    # Player Selection from Database
    game_choice = st.radio("Title", ["CS2", "Valorant"], horizontal=True)
    db_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    
    selected_name = st.selectbox("Database Search", ["Manual Entry"] + db_players)
    
    # Auto-fill if player selected
    if selected_name != "Manual Entry":
        p_row = df[df['Player'] == selected_name].iloc[0]
        p_tag = st.text_input("Player Tag", value=p_row['Player'])
        l10_raw = st.text_area("L10 Stats", value=str(p_row['L10']))
        base_kpr = st.number_input("Base KPR", value=float(p_row['BaseKPR']))
    else:
        p_tag = st.text_input("Player Tag", value="donk")
        l10_raw = st.text_area("L10 Stats", value="46, 33, 45, 42, 30")
        base_kpr = st.number_input("Base KPR", value=0.90)

    c1, c2 = st.columns(2)
    with c1:
        m_line = st.number_input("Line", value=35.5, step=0.5)
        m_side = st.selectbox("Side", ["Over", "Under"])
    with c2:
        m_odds = st.number_input("Odds", value=-128)
        m_scope = st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

# ==========================================
# 🚀 ANALYSIS EXECUTION
# ==========================================
with col_right:
    if st.button("RUN ELITE ANALYSIS"):
        try:
            # 1. Math Processing
            vals = [float(x.strip()) for x in l10_raw.split(",") if x.strip()]
            mean_v = np.mean(vals)
            stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 1.0, 1.0)
            cv = stdev / mean_v 
            
            # 2. Projection Logic
            map_multiplier = {"Maps 1 & 2": 2.0, "Map 1 Only": 1.0, "Full Match": 2.5}.get(m_scope, 2.0)
            proj = (base_kpr * 21.5 * map_multiplier) * st.session_state.h2h_val * st.session_state.tier_val * st.session_state.map_val * st.session_state.int_val
            
            # 3. Probability & Edge
            prob_under = norm.cdf(m_line, loc=proj, scale=stdev)
            model_prob = (1 - prob_under) * 100 if m_side == "Over" else prob_under * 100
            edge = model_prob - get_implied_prob(m_odds)
            
            # 4. Grading
            grade, color, flat, units = get_grade_details(edge)
            if cv > 0.25: # Penalty for high volatility
                units = max(0.5, units - 0.5)
                if grade == "S": grade = "A+"

            # 5. UI DISPLAY
            arrow = "▲" if m_side == "Over" else "▼"
            st.markdown(f"""
                <div class="grade-card" style="background: {color}; color: white;">
                    <div style="font-size: 28px; font-weight: 900;">{p_tag.upper()}</div>
                    <div style="font-size: 18px;">{arrow} {m_side.upper()} {m_line}</div>
                    <h1 class="grade-text">{grade}</h1>
                    <div style="font-size: 20px; font-weight: bold;">{units} UNIT PLAY</div>
                </div>
                """, unsafe_allow_html=True)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Projected", f"{proj:.1f}")
            m2.metric("Edge", f"{edge:+.1f}%")
            m3.metric("Volatility (CV)", f"{cv:.2f}")

        except Exception as e:
            st.error(f"Analysis Failed: {e}")

    # AI Section
    st.markdown("---")
    if st.button("🔍 ACTIVATE AI SCOUT"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if not api_key:
            st.error("Missing Groq API Key in Secrets.")
        else:
            client = Groq(api_key=api_key)
            with st.spinner("Consulting AI..."):
                prompt = f"Analyze {p_tag} for a {m_line} kills prop. Recent scores: {l10_raw}. Provide a 2-sentence sharp betting scout report."
                chat = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile")
                st.info(chat.choices[0].message.content)