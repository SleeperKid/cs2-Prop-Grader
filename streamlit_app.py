import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os
from groq import Groq
import re
from datetime import datetime

# ==========================================
# 🎨 ELITE UI STYLING
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #238636; color: white; font-weight: bold; border: none; }
    .grade-card { padding: 30px; border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; margin-bottom: 20px; }
    .grade-text { font-size: 90px; font-weight: 900; margin: 0; line-height: 1; }
    .advice-box { background: #1c2128; padding: 15px; border-radius: 10px; border: 1px solid #30363d; font-size: 0.85rem; color: #58a6ff; margin-bottom: 10px; }
    .scout-report-box { background: #161b22; padding: 20px; border-radius: 15px; border-left: 5px solid #58a6ff; font-style: italic; color: #adbac7; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🧠 CORE ANALYTICS ENGINE
# ==========================================
def get_grade_details(edge):
    if edge >= 12.0: return "S", "linear-gradient(135deg, #FFD700, #FFA500)", "#FFD700", 2.5
    if edge >= 8.0: return "A+", "linear-gradient(135deg, #00FF00, #008000)", "#00FF00", 2.0
    if edge >= 3.0: return "A", "linear-gradient(135deg, #ADFF2F, #228B22)", "#ADFF2F", 1.0
    if edge >= 0.0: return "B", "linear-gradient(135deg, #F0E68C, #DAA520)", "#F0E68C", 0.5
    return "F", "linear-gradient(135deg, #8B0000, #000000)", "#FF4500", 0.0

def get_implied_prob(odds):
    return (abs(odds) / (abs(odds) + 100)) * 100 if odds < 0 else (100 / (odds + 100)) * 100

# ==========================================
# 📥 DATA & SESSION STATE
# ==========================================
states = {
    'h2h_val': 1.0, 'tier_val': 1.0, 'map_val': 1.0, 'int_val': 1.0,
    'weight_advice': None, 'analysis_results': None,
    'opp_rank_val': "N/A", 'expected_maps_val': "TBD", 'opening_val': "50%"
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

@st.cache_data
def load_vault():
    if os.path.exists("daily_stats.csv"):
        return pd.read_csv("daily_stats.csv")
    return pd.DataFrame(columns=["Player", "Game", "Team", "BaseKPR", "L10", "ExpectedMaps"])

df = load_vault()

# ==========================================
# ⚙️ SIDEBAR: AI ADVISOR & CHEAT SHEET
# ==========================================
with st.sidebar:
    st.header("⚙️ Model Intelligence")
    
    st.subheader("🤖 AI Weight Advisor")
    st.caption("AI will analyze your 'Deep Context' inputs to adjust sliders.")
    
    if st.button("GET AI SLIDER ADVICE"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if not api_key:
            st.error("API Key missing in Secrets.")
        else:
            client = Groq(api_key=api_key)
            with st.spinner("AI analyzing deep context..."):
                # UPGRADED PROMPT: Feeds the UI inputs to the AI
                prompt = f"""
                Act as an Esports Betting Syndicate Analyst.
                Player: {st.session_state.get('p_tag_input', 'Unknown')}
                Opponent Rank: {st.session_state.opp_rank_val}
                Projected Maps: {st.session_state.expected_maps_val}
                Opening Duel Rate: {st.session_state.opening_val}

                TASK: Output 4 Weights (0.85-1.15) for our model.
                FORMAT: H2H: [X] | Tier: [X] | Map: [X] | Int: [X]
                FOLLOWED BY: A 2-sentence 'Cheat Sheet' explanation.
                """
                completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                advice = completion.choices[0].message.content
                st.session_state.weight_advice = advice
                
                # Regex to move the sliders
                found_weights = re.findall(r"([0-1]\.\d+)", advice)
                if len(found_weights) >= 4:
                    st.session_state.h2h_val = float(found_weights[0])
                    st.session_state.tier_val = float(found_weights[1])
                    st.session_state.map_val = float(found_weights[2])
                    st.session_state.int_val = float(found_weights[3])
                    st.toast("🎯 Sliders Synced to Context!", icon="✅")

    # SIDEBAR CHEAT SHEET
    if st.session_state.weight_advice:
        st.markdown(f'<div class="advice-box"><b>AI Slider Cheat Sheet:</b><br>{st.session_state.weight_advice}</div>', unsafe_allow_html=True)

    st.divider()
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, key="h2h_val", step=0.05)
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, key="tier_val", step=0.05)
    map_w = st.slider("Map Fit", 0.80, 1.20, key="map_val", step=0.05)
    int_w = st.slider("Match Intensity", 0.70, 1.10, key="int_val", step=0.05)

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
st.title("🎯 Prop Grader Elite")
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("📋 Prop & Context")
    game_choice = st.radio("Game", ["CS2", "Valorant"], horizontal=True)
    db_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    
    selected_name = st.selectbox("Database Search", ["Manual Entry"] + db_players)
    
    # Auto-fill Logic
    if selected_name != "Manual Entry":
        p_row = df[df['Player'] == selected_name].iloc[0]
        p_tag = st.text_input("Player Tag", value=p_row['Player'], key="p_tag_input")
        l10_raw = st.text_area("L10 Stats", value=str(p_row['L10']))
        base_kpr = st.number_input("Base KPR", value=float(p_row['BaseKPR']))
        st.session_state.opp_rank_val = str(p_row.get('Rank', "N/A"))
        st.session_state.expected_maps_val = str(p_row.get('ExpectedMaps', "TBD"))
    else:
        p_tag = st.text_input("Player Tag", value="donk", key="p_tag_input")
        l10_raw = st.text_area("L10 Stats", value="46, 33, 45, 42, 30")
        base_kpr = st.number_input("Base KPR", value=0.90)

    # NEW: CONTEXTUAL DATA SECTION
    with st.expander("🧠 Deep Context (Feeds AI Advisor)", expanded=True):
        st.text_input("Opponent World Rank", key="opp_rank_val")
        st.text_input("Projected Maps", key="expected_maps_val")
        st.text_input("Opening Duel Success %", key="opening_val")

    c1, c2 = st.columns(2)
    with c1:
        m_line = st.number_input("Line", value=35.5, step=0.5)
        m_side = st.selectbox("Side", ["Over", "Under"])
    with c2:
        m_odds = st.number_input("Odds", value=-128)
        m_scope = st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

if st.button("RUN ELITE ANALYSIS"):
    try:
        vals = [float(x.strip()) for x in l10_raw.split(",") if x.strip()]
        mean_v = np.mean(vals)
        stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 1.0, 1.0)
        cv = stdev / mean_v 
        hit_rate = sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line)) / len(vals)
        
        mapping = {"Maps 1 & 2": 2.0, "Map 1 Only": 1.0, "Full Match": 2.5}
        proj = (base_kpr * 21.5 * mapping.get(m_scope, 2.0)) * h2h_w * rank_w * map_w * int_w
        
        prob_under = norm.cdf(m_line, loc=proj, scale=stdev)
        model_prob = (1 - prob_under) * 100 if m_side == "Over" else prob_under * 100
        edge = model_prob - get_implied_prob(m_odds)
        
        grade, color, flat, units = get_grade_details(edge)
        if cv > 0.25: units = max(0.5, units - 0.5)
        
        st.session_state.analysis_results = {
            "p_tag": p_tag, "side": m_side, "line": m_line, "grade": grade,
            "color": color, "flat": flat, "units": units, "proj": proj, "edge": edge, 
            "hit_rate": hit_rate * 100, "cv": cv, "game": game_choice
        }
    except Exception as e:
        st.error(f"Analysis Error: {e}")

# ==========================================
# 📊 OUTPUTS & SHARE CARD
# ==========================================
with col_r:
    if st.session_state.analysis_results:
        res = st.session_state.analysis_results
        arrow = "▲" if res["side"] == "Over" else "▼"
        
        st.markdown(f"""
            <div class="grade-card" style="background: {res["color"]}; color: white;">
                <div style="font-size: 28px; font-weight: 900;">{res["p_tag"].upper()}</div>
                <div style="font-size: 18px;">{arrow} {res["side"].upper()} {res["line"]}</div>
                <h1 class="grade-text">{res["grade"]}</h1>
                <div style="font-size: 20px; font-weight: bold;">{res["units"]} UNIT PLAY</div>
            </div>
            """, unsafe_allow_html=True)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Projected", f"{res['proj']:.1f}")
        m2.metric("Edge", f"{res['edge']:+.1f}%")
        m3.metric("L10 Hit", f"{res['hit_rate']:.0f}%")

        if st.checkbox("📸 Generate Social Share Card"):
            card_html = f"""
            <div style="background-color: #0e1117; border: 3px solid {res["flat"]}; border-radius: 20px; padding: 30px; max-width: 450px; color: white; margin: 10px auto; text-align: center;">
                <h2 style="margin: 0; font-size: 32px;">{res["p_tag"].upper()}</h2>
                <div style="color: {res["flat"]}; font-size: 100px; font-weight: 900; line-height: 1;">{res["grade"]}</div>
                <div style="font-size: 24px; font-weight: bold;">{arrow} {res["side"].upper()} {res["line"]}</div>
                <div style="background: {res["flat"]}30; padding: 10px; margin-top: 15px; border-radius: 10px;">
                    <b>{res["units"]} UNIT PLAY</b> | Edge: {res["edge"]:+.1f}%
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)