import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from scipy.stats import norm
import os
import csv
from groq import Groq  # Swapped from google.genai
from datetime import datetime
from dotenv import load_dotenv

# --- 0. SETUP & STATE ---
load_dotenv()

def get_api_key(user_input):
    if user_input: return user_input
    if "GROQ_API_KEY" in st.secrets: return st.secrets["GROQ_API_KEY"]
    return os.getenv("GROQ_API_KEY")

if 'p_tag_val' not in st.session_state: st.session_state.p_tag_val = "donk"
if 'm_context_val' not in st.session_state: st.session_state.m_context_val = "Spirit vs FaZe"
if 'm_l10_val' not in st.session_state: st.session_state.m_l10_val = "46, 33, 45, 42, 30, 40, 33, 45, 45, 46"
if 'analysis_ready' not in st.session_state: st.session_state.analysis_ready = False
if 'scout_report' not in st.session_state: st.session_state.scout_report = None
if 'selected_game' not in st.session_state: st.session_state.selected_game = "CS2"

# --- ACCESS CONTROL ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔐 Sleeper D. Kid - Private Access")
        password = st.text_input("Enter Access Code", type="password")
        if st.button("Unlock Grader"):
            if "ACCESS_CODE" in st.secrets and password == st.secrets["ACCESS_CODE"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Invalid Code")
        return False
    return True

if not check_password():
    st.stop()

# --- 1. CORE FUNCTIONS ---
@st.cache_data(show_spinner="Generating Scout Report...", ttl=3600)
def get_groq_scout(game, player, label, api_key):
    """Fetch cached scout report from Groq Llama 3.3"""
    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", # High-quality model
            messages=[
                {"role": "system", "content": f"You are an elite {game} analyst. Provide a 2-sentence betting scout report."},
                {"role": "user", "content": f"Analyze {player} for a {label} prop."}
            ],
            temperature=0.7,
            max_tokens=100
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"AI Logic Offline: {str(e)}"

def get_implied_prob(odds):
    return (abs(odds) / (abs(odds) + 100)) * 100 if odds < 0 else (100 / (odds + 100)) * 100

def get_grade_details(edge):
    if edge >= 12.0: return "S", "linear-gradient(135deg, #FFD700, #FFA500)", "#FFD700", 2.5
    if edge >= 8.0: return "A+", "linear-gradient(135deg, #00FF00, #008000)", "#00FF00", 2.0
    if edge >= 3.0: return "A", "linear-gradient(135deg, #ADFF2F, #228B22)", "#ADFF2F", 1.0
    if edge >= 0.0: return "B", "linear-gradient(135deg, #F0E68C, #DAA520)", "#DAA520", 0.5
    return "F", "linear-gradient(135deg, #8B0000, #000000)", "#FF4500", 0.0

def log_prop(data):
    file_path = "prop_history.csv"
    try:
        df = pd.DataFrame([data])
        file_exists = os.path.isfile(file_path)
        df.to_csv(file_path, mode='a', header=not file_exists, index=False, quoting=csv.QUOTE_MINIMAL)
        st.session_state['log_success'] = f"Logged {data['Player']} to History!"
    except Exception as e:
        st.error(f"Error logging to file: {e}")

def update_prop_status(row_index, new_status):
    file_path = "prop_history.csv"
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            df.at[row_index, 'Result'] = new_status
            df.to_csv(file_path, index=False, quoting=csv.QUOTE_MINIMAL)
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Failed to update history: {e}")

# --- 2. PAGE CONFIG ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    [data-testid="stMetricValue"] { font-size: 1.6rem; color: #58a6ff; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #238636; color: white; font-weight: bold; border: none; }
    .grade-card { padding: 30px; border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; margin-bottom: 20px; position: relative; }
    .grade-text { font-size: 90px; font-weight: 900; margin: 0; line-height: 1; }
    .scout-report-box { background: #161b22; padding: 20px; border-radius: 15px; border-left: 5px solid #58a6ff; font-style: italic; color: #adbac7; margin-bottom: 20px; }
    .brand-tag { font-size: 10px; letter-spacing: 2px; opacity: 0.7; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ App Controls")
    st.session_state.selected_game = st.radio("Select Title", ["CS2", "Valorant"], horizontal=True)
    
    if st.button("🔄 RESET ALL FIELDS"):
        st.session_state.p_tag_val = ""
        st.session_state.m_context_val = ""
        st.session_state.m_l10_val = ""
        st.session_state.analysis_ready = False
        st.session_state.scout_report = None
        st.rerun()
    
    st.divider()
    st.header("🔑 AI Config")
    user_key = st.text_input("Groq API Key (Optional)", type="password")
    
    st.divider()
    st.header("⚖️ Contextual Weights")
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, 1.00, 0.05)
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, 1.00, 0.05)
    map_w = st.slider("Map Fit", 0.80, 1.20, 1.00, 0.05)
    int_w = st.slider("Match Intensity", 0.70, 1.10, 1.00, 0.05)

# --- 4. INPUTS ---
col1, col2 = st.columns([1, 1.2], gap="large")

with col1:
    st.subheader("📋 Prop Details")
    p_name = st.text_input("Player Tag", value=st.session_state.p_tag_val)
    team_context = st.text_input("Matchup Context", value=st.session_state.m_context_val)
    
    metric_options = ["Kills", "Headshots"] if st.session_state.selected_game == "CS2" else ["Kills"]
    metric_type = st.radio("Metric", metric_options, horizontal=True)
    
    c1, c2 = st.columns(2)
    with c1:
        m_line = st.number_input(f"Line", value=35.5 if metric_type == "Kills" else 15.5, step=0.5)
        m_side = st.selectbox("Side", ["Over", "Under"])
    with c2:
        m_odds = st.number_input("Odds", value=-128)
        m_format = st.selectbox("Scope", ["Map 1 Only", "Maps 1 & 2", "Maps 1, 2, & 3", "Full Match"], index=1)

    stat_source = "HLTV KPR/HSPR" if st.session_state.selected_game == "CS2" else "VLR.gg KPR"
    avg_rate = st.number_input(stat_source, value=0.90 if metric_type == "Kills" else 0.45)
    manual_data = st.text_area("L10 (comma separated)", value=st.session_state.m_l10_val)

# --- 5. EXECUTE ---
if st.button("RUN ELITE ANALYSIS"):
    try:
        vals = [float(x.strip()) for x in manual_data.split(",") if x.strip()]
        stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 1.0, 1.0)
        hits = sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line))
        hit_rate = (hits / len(vals)) * 100 if vals else 0
        
        mapping = {"Map 1 Only": 1.0, "Maps 1 & 2": 2.0, "Maps 1, 2, & 3": 3.0, "Full Match": 2.5}
        proj = (avg_rate * 21.5 * mapping.get(m_format, 1.0)) * h2h_w * rank_w * map_w * int_w
        
        prob_under = norm.cdf(m_line, loc=proj, scale=stdev)
        model_prob = (1 - prob_under) * 100 if m_side == "Over" else prob_under * 100
        edge = model_prob - get_implied_prob(m_odds)
        conf = min(max(((abs(edge) * 3) + (100 - (stdev/m_line * 100))), 0), 100)
        grade, color, flat, units = get_grade_details(edge)
        
        st.session_state.results = {
            "p_name": p_name, "team": team_context, "label": metric_type, "line": m_line, "side": m_side,
            "proj": proj, "edge": edge, "conf": conf, "grade": grade, "color": color, "flat": flat, "units": units,
            "vals": vals, "hit_rate": hit_rate, "volatility": stdev, "game": st.session_state.selected_game
        }
        st.session_state.analysis_ready = True
    except Exception as e: st.error(f"Error: {e}")

# --- 6. OUTPUTS ---
with col2:
    if st.session_state.get('analysis_ready'):
        res = st.session_state.results
        
        st.markdown(f"""
            <div class="grade-card" style="background: {res["color"]}; color: white;">
                <div style="font-size: 18px; opacity: 0.9;">{res["p_name"].upper()} ({res["game"]})</div>
                <h1 class="grade-text">{res["grade"]}</h1>
                <div style="font-weight: bold; font-size: 20px;">{res["units"]} UNIT PLAY</div>
                <div class="brand-tag">ANALYSIS BY SLEEPER D. KID</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.write(f"**Model Confidence:** {res['conf']:.1f}%")
        st.progress(res['conf'] / 100)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Projected", f"{res['proj']:.1f}")
        m2.metric("Edge", f"{res['edge']:+.1f}%")
        m3.metric("L10 Hit Rate", f"{res['hit_rate']:.0f}%")
        m4.metric("Volatility", f"{res['volatility']:.1f}")

        if st.button("🔍 ACTIVATE AI SCOUT"):
            api_key_to_use = get_api_key(user_key)
            if not api_key_to_use:
                st.error("No Groq API key found. Please enter one in the sidebar.")
            else:
                st.session_state.scout_report = get_groq_scout(res['game'], res['p_name'], res['label'], api_key_to_use)
            
        if st.session_state.get('scout_report'):
            st.markdown(f'<div class="scout-report-box">{st.session_state.scout_report}</div>', unsafe_allow_html=True)

        log_data = {"Date": datetime.now().strftime("%Y-%m-%d"), "Game": res["game"], "Player": res["p_name"], "Metric": res["label"], "Line": res["line"], "Side": res["side"], "Grade": res["grade"], "Units": res["units"], "Result": "Pending"}
        st.button("📥 LOG TO HISTORY", on_click=log_prop, args=(log_data,))

        df_chart = pd.DataFrame({"Match": range(1, len(res["vals"])+1), "Stat": res["vals"]})
        fig = px.bar(df_chart, x="Match", y="Stat", color_discrete_sequence=['#58a6ff'], height=200)
        fig.add_hline(y=res["line"], line_dash="dash", line_color="#ff7b72")
        st.plotly_chart(fig, use_container_width=True)

# --- 7. HISTORY & BANKROLL ---
st.divider()
if os.path.exists("prop_history.csv"):
    try:
        df_history = pd.read_csv("prop_history.csv")
        won_units = df_history[df_history['Result'] == 'Won']['Units'].sum()
        lost_units = df_history[df_history['Result'] == 'Lost']['Units'].sum()
        st.header(f"📈 Bankroll: {won_units - lost_units:+.1f}U")
        st.dataframe(df_history.sort_index(ascending=False), use_container_width=True)
        
        with st.expander("🛠️ Result Updater"):
            pending = df_history[df_history['Result'] == 'Pending']
            if not pending.empty:
                sel = st.selectbox("Settle Bet:", [f"{i}: {r['Player']} ({r['Metric']})" for i, r in pending.iterrows()])
                idx = int(sel.split(":")[0])
                c1, c2, c3 = st.columns(3)
                if c1.button("✅ WON"): update_prop_status(idx, "Won"); st.rerun()
                if c2.button("❌ LOST"): update_prop_status(idx, "Lost"); st.rerun()
                if c3.button("➖ PUSH"): update_prop_status(idx, "Push"); st.rerun()
    except Exception as e: st.error(f"History Error: {e}")