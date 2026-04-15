import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from scipy.stats import norm
import os
import csv
from groq import Groq
from datetime import datetime
from dotenv import load_dotenv
import re

# --- 0. SETUP & STATE ---
load_dotenv()

@st.cache_data
def load_data():
    if os.path.exists("daily_stats.csv"):
        return pd.read_csv("daily_stats.csv")
    return pd.DataFrame(columns=["Player", "Game", "Team", "Rank", "BaseKPR", "L10", "ExpectedMaps"])

df = load_data()

def get_api_key(user_input):
    if user_input: return user_input
    try:
        if "GROQ_API_KEY" in st.secrets: 
            return st.secrets["GROQ_API_KEY"]
    except: pass
    return os.getenv("GROQ_API_KEY")

# Persistent session states including new UI widgets
states = {
    'weight_advice': None, 'scout_report': None, 'analysis_ready': False, 
    'show_slips': False, 'results': None, 'last_selected': "Manual Entry",
    'p_tag_val': "donk", 'm_context_val': "Spirit vs FaZe", 'opp_rank_val': "N/A",
    'expected_maps_val': "Mirage, Nuke", 'kpr_val': 0.90,
    'l10_val': "46, 33, 45, 42, 30, 40, 33, 45, 45, 46",
    'map1_val': "0.00", 'map2_val': "0.00", 'opening_val': "50%",
    'h2h_val': 1.00, 'tier_val': 1.00, 'map_val': 1.00, 'int_val': 1.00,
    'player_selector': "Manual Entry", 'stat_val': "Kills", 'line_val': 35.5, 
    'side_val': "Over", 'odds_val': -128, 'scope_val': "Maps 1 & 2"
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 1. CORE FUNCTIONS ---

@st.cache_data(show_spinner="Analyzing Volatility & Deep Context...", ttl=3600)
def get_weight_advice(game, player, matchup, maps, l10_data, volatility, deep_stats, api_key):
    """Upgraded AI Engine using Deep Profile Context."""
    try:
        client = Groq(api_key=api_key)
        prompt = f"""
        Act as a Professional Esports Betting Syndicate Analyst.
        Match: {matchup} | Opponent Rank: {deep_stats['rank']} | Player: {player}
        
        DEEP DATA:
        - Map Context: {maps}
        - Map-Specific Performance: Map 1 KPR: {deep_stats['map1']}, Map 2 KPR: {deep_stats['map2']}
        - Opening Duel Success: {deep_stats['opening']}
        - Volatility (StdDev): {volatility:.2f}
        - L10 History: {l10_data}

        OUTPUT 4 WEIGHTS (Must be between 0.85 - 1.15 and MUST end in .00, .05, or .10):
        **H2H:** [Value] | **Tier:** [Value] | **Map:** [Value] | **Int:** [Value]

        JUSTIFICATION (2 sentences max): Interaction between role, map fitness, and opponent difficulty.
        """
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return completion.choices[0].message.content
    except Exception as e: return f"Advisor Offline: {str(e)}"

@st.cache_data(show_spinner="Generating Scout Report...", ttl=3600)
def get_groq_scout(game, player, label, api_key):
    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": f"You are an elite {game} analyst. Provide a 2-sentence betting scout report."},
                {"role": "user", "content": f"Analyze {player} for a {label} prop."}
            ],
            temperature=0.7, max_tokens=100
        )
        return completion.choices[0].message.content
    except: return "AI Scout is currently offline."

def get_implied_prob(odds):
    return (abs(odds) / (abs(odds) + 100)) * 100 if odds < 0 else (100 / (odds + 100)) * 100

def get_grade_details(edge):
    if edge >= 12.0: return "S", "linear-gradient(135deg, #FFD700, #FFA500)", "#FFD700", 2.5
    if edge >= 8.0: return "A+", "linear-gradient(135deg, #00FF00, #008000)", "#00FF00", 2.0
    if edge >= 3.0: return "A", "linear-gradient(135deg, #ADFF2F, #228B22)", "#ADFF2F", 1.0
    if edge >= 0.0: return "B", "linear-gradient(135deg, #F0E68C, #DAA520)", "#DAA520", 0.5
    return "F", "linear-gradient(135deg, #8B0000, #000000)", "#FF4500", 0.0

def log_prop(data):
    file_path = "prop_vault.csv"
    try:
        df_log = pd.DataFrame([data])
        df_log.to_csv(file_path, mode='a', header=not os.path.isfile(file_path), index=False)
        st.session_state['log_success'] = f"Logged {data['Player']} to the Vault!"
    except: st.error("Logging failed.")

# --- 2. UI STYLING ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide", page_icon="🎯")
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #238636; color: white; font-weight: bold; border: none; }
    .grade-card { padding: 30px; border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; margin-bottom: 20px; }
    .grade-text { font-size: 90px; font-weight: 900; margin: 0; line-height: 1; }
    .advice-box { background: #1c2128; padding: 15px; border-radius: 10px; border: 1px solid #30363d; font-size: 0.85rem; color: #58a6ff; margin-bottom: 10px; }
    .scout-report-box { background: #161b22; padding: 20px; border-radius: 15px; border-left: 5px solid #58a6ff; font-style: italic; color: #adbac7; margin-bottom: 20px; }
    .slip-card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 15px; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("⚙️ App Controls")
    selected_game = st.radio("Select Title", ["CS2", "Valorant"], horizontal=True)
    
    st.subheader("🤖 AI Weight Advisor")
    if st.button("GET AI SLIDER ADVICE"):
        api_to_use = get_api_key(None)
        if not api_to_use: 
            st.error("Check API Key Configuration")
        else:
            sync_success = False
            try:
                vals = [float(x.strip()) for x in st.session_state.l10_val.split(",") if x.strip()]
                v_std = np.std(vals) if len(vals) > 1 else 0.0
                deep_context = {
                    "rank": st.session_state.opp_rank_val,
                    "map1": st.session_state.map1_val,
                    "map2": st.session_state.map2_val,
                    "opening": st.session_state.opening_val
                }
                advice = get_weight_advice(
                    selected_game, st.session_state.p_tag_val, st.session_state.m_context_val, 
                    st.session_state.expected_maps_val, st.session_state.l10_val, v_std, deep_context, api_to_use
                )
                st.session_state.weight_advice = advice
                found_weights = re.findall(r"([0-1]\.\d+)", advice)
                
                if len(found_weights) >= 4:
                    st.session_state.h2h_val = float(found_weights[0])
                    st.session_state.tier_val = float(found_weights[1])
                    st.session_state.map_val = float(found_weights[2])
                    st.session_state.int_val = float(found_weights[3])
                    sync_success = True
                else:
                    st.error("AI returned improperly formatted weights. Try again.")
                    
            except Exception as e: 
                st.error(f"Sync Failed: {str(e)}")
            
            if sync_success:
                st.toast("🎯 Sliders Synced!", icon="✅")

    if st.session_state.weight_advice:
        st.markdown(f'<div class="advice-box">{st.session_state.weight_advice}</div>', unsafe_allow_html=True)

    st.divider()
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, key="h2h_val", step=0.05)
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, key="tier_val", step=0.05)
    map_w = st.slider("Map Fit", 0.80, 1.20, key="map_val", step=0.05)
    int_w = st.slider("Match Intensity", 0.70, 1.10, key="int_val", step=0.05)

# --- 4. TOP INTERFACE ---
st.title(f"🎯 {selected_game} Prop Grader Elite")
st.markdown("### 🔍 Database Search")

if not df.empty and "Game" in df.columns:
    filtered_df = df[df["Game"] == selected_game]
    player_names = filtered_df["Player"].tolist()
else:
    player_names = df["Player"].tolist() if not df.empty else []

selected_player = st.selectbox("Select a Player", ["Manual Entry"] + player_names, key="player_selector")

if selected_player != st.session_state.last_selected:
    st.session_state.last_selected = selected_player
    if selected_player != "Manual Entry":
        if not df.empty and "Game" in df.columns:
            p_data = filtered_df[filtered_df["Player"] == selected_player].iloc[0]
        else:
            p_data = df[df["Player"] == selected_player].iloc[0]

        st.session_state.p_tag_val = str(p_data["Player"])
        st.session_state.m_context_val = str(p_data["Team"])
        st.session_state.opp_rank_val = str(p_data.get("Rank", "N/A"))
        st.session_state.expected_maps_val = str(p_data.get("ExpectedMaps", "TBD"))
        st.session_state.kpr_val = float(p_data["BaseKPR"])
        st.session_state.l10_val = str(p_data["L10"])
        
        st.session_state.map1_val = "0.00"
        st.session_state.map2_val = "0.00"
        st.session_state.opening_val = "50%"
    st.rerun()

col1, col2 = st.columns([1, 1.2], gap="large")

with col1:
    st.subheader("📋 Prop Details")
    p_name = st.text_input("Player Tag", key="p_tag_val")
    team_context = st.text_input("Matchup Context", key="m_context_val")
    opp_rank = st.text_input("Opponent World Rank", key="opp_rank_val")
    expected_maps = st.text_input("Expected Maps", key="expected_maps_val")
    
    with st.expander("🧠 Deep Profile Insights (AI Context)", expanded=False):
        st.caption("Optional: Manually enter map-specific data to enhance the AI Advisor's accuracy.")
        st.text_input("Opening Duel Success", key="opening_val")
        c_map1, c_map2 = st.columns(2)
        with c_map1:
            st.text_input("Map 1 KPR/HSPR", key="map1_val")
        with c_map2:
            st.text_input("Map 2 KPR/HSPR", key="map2_val")
    
    c1, c2 = st.columns(2)
    with c1:
        m_label = st.selectbox("Stat Type", ["Kills", "Headshots"], key="stat_val")
        m_line = st.number_input("Line", step=0.5, key="line_val")
        m_side = st.selectbox("Side", ["Over", "Under"], key="side_val")
    with c2:
        m_format = st.selectbox("Scope", ["Map 1 Only", "Maps 1 & 2", "Maps 1, 2, & 3", "Full Match"], key="scope_val")
        m_odds = st.number_input("Odds", key="odds_val")

    avg_rate = st.number_input("Base KPR/HSPR", key="kpr_val", step=0.01)
    manual_data = st.text_area("L10 Stats", key="l10_val")

# --- 6. SHARP ANALYSIS ENGINE ---
if st.button("RUN ELITE ANALYSIS"):
    try:
        vals = [float(x.strip()) for x in manual_data.split(",") if x.strip()]
        mean_v = np.mean(vals)
        stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 1.0, 1.0)
        cv = stdev / mean_v 
        hits = sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line))
        mapping = {"Map 1 Only": 1.0, "Maps 1 & 2": 2.0, "Maps 1, 2, & 3": 3.0, "Full Match": 2.5}
        proj = (avg_rate * 21.5 * mapping.get(m_format, 1.0)) * h2h_w * rank_w * map_w * int_w
        prob_under = norm.cdf(m_line, loc=proj, scale=stdev)
        model_prob = (1 - prob_under) * 100 if m_side == "Over" else prob_under * 100
        edge = model_prob - get_implied_prob(m_odds)
        conf = min(max(((abs(edge) * 3) + (100 - (cv * 100))), 0), 100)
        grade, color, flat, units = get_grade_details(edge)
        if cv > 0.25:
            units = max(0.5, units - 0.5)
            if grade == "S": grade = "A+"
        
        st.session_state.results = {
            "p_name": p_name, "team": team_context, "label": m_label, "line": m_line, "side": m_side,
            "proj": proj, "edge": edge, "conf": conf, "grade": grade, "color": color, "flat": flat, "units": units,
            "vals": vals, "hit_rate": (hits/len(vals))*100, "volatility": stdev, "game": selected_game, "cv": cv
        }
        st.session_state.analysis_ready = True
    except Exception as e: st.error(f"Analysis Failed: {e}")

# --- 7. OUTPUTS ---
with col2:
    if st.session_state.get('analysis_ready'):
        res = st.session_state.results
        arrow = "▲" if res["side"] == "Over" else "▼"
        st.markdown(f"""
            <div class="grade-card" style="background: {res["color"]}; color: white;">
                <div style="font-size: 12px; text-transform: uppercase;">{res["game"]} • {res["team"]}</div>
                <div style="font-size: 28px; font-weight: 900;">{res["p_name"].upper()}</div>
                <div style="font-size: 18px;">{arrow} {res["side"].upper()} {res["line"]} {res["label"].upper()}</div>
                <h1 class="grade-text">{res["grade"]}</h1>
                <div style="font-size: 20px; font-weight: bold;">{res["units"]} UNIT PLAY</div>
            </div>
            """, unsafe_allow_html=True)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Projected", f"{res['proj']:.1f}")
        m2.metric("Edge", f"{res['edge']:+.1f}%")
        m3.metric("L10 Hit", f"{res['hit_rate']:.0f}%")
        m4.metric("Volatility (CV)", f"{res['cv']:.2f}")

        if st.button("🔍 ACTIVATE AI SCOUT"):
            api = get_api_key(None)
            if api: st.session_state.scout_report = get_groq_scout(res['game'], res['p_name'], res['label'], api)
        
        if st.session_state.scout_report:
            st.markdown(f'<div class="scout-report-box">{st.session_state.scout_report}</div>', unsafe_allow_html=True)

        log_data = {"Date": datetime.now().strftime("%Y-%m-%d"), "Game": res["game"], "Player": res["p_name"], "Grade": res["grade"], "Edge (%)": round(res["edge"], 1), "Conf (%)": round(res["conf"], 1)}
        st.button("📥 SAVE TO VAULT", on_click=log_prop, args=(log_data,))

        if st.checkbox("📸 Generate Screenshot Share Card"):
            unit_text, a_color = ("UNIT" if res["units"] == 1.0 else "UNITS"), ("#00FF00" if res["side"] == "Over" else "#FF4500")
            card_html = f"""
            <div style="background-color: #0e1117; border: 3px solid {res["flat"]}; border-radius: 20px; padding: 30px; max-width: 480px; color: white; font-family: sans-serif; margin: 20px auto; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                <div style="border-bottom: 2px solid #30363d; padding-bottom: 15px; margin-bottom: 20px;">
                    <div style="font-size: 12px; color: #adbac7; text-transform: uppercase; letter-spacing: 3px;">{res["game"]} PROP ANALYSIS</div>
                    <h2 style="margin: 0; font-size: 36px; font-weight: 900;">{res["p_name"].upper()}</h2>
                    <div style="color: #58a6ff; font-size: 16px; font-weight: bold;">{res["team"]}</div>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
                    <div style="flex: 1.2; text-align: left;">
                        <div style="font-size: 14px; color: #adbac7;">THE PROP LINE</div>
                        <div style="font-size: 80px; font-weight: 900; line-height: 1; margin: 5px 0;">{res["line"]}</div>
                        <div style="font-size: 32px; font-weight: 900; color: {a_color};">{arrow} {res["side"].upper()}</div>
                    </div>
                    <div style="flex: 0.8; text-align: right;">
                        <div style="font-size: 14px; color: #adbac7;">MODEL GRADE</div>
                        <div style="font-size: 130px; font-weight: 900; color: {res["flat"]}; line-height: 0.8;">{res["grade"]}</div>
                    </div>
                </div>
                <div style="background: linear-gradient(135deg, {res["flat"]}30, #161b22); border-radius: 12px; padding: 15px; text-align: center; border: 1px solid {res["flat"]}50;">
                    <div style="font-size: 14px; color: {res["flat"]}; font-weight: bold;">SUGGESTED PLAY</div>
                    <div style="font-size: 34px; font-weight: 900;">{res["units"]} {unit_text}</div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; border-top: 2px solid #30363d; padding-top: 20px; margin-top: 20px;">
                    <div style="text-align: center;"><div style="font-size: 10px; color: #adbac7;">PROJ</div><div style="font-size: 18px; font-weight: bold;">{res["proj"]:.1f}</div></div>
                    <div style="text-align: center;"><div style="font-size: 10px; color: #adbac7;">EDGE</div><div style="font-size: 18px; font-weight: bold; color: {res["flat"]};">+{res["edge"]:.1f}%</div></div>
                    <div style="text-align: center;"><div style="font-size: 10px; color: #adbac7;">CONF</div><div style="font-size: 18px; font-weight: bold;">{res["conf"]:.0f}%</div></div>
                    <div style="text-align: center;"><div style="font-size: 10px; color: #adbac7;">L10 HIT</div><div style="font-size: 18px; font-weight: bold;">{res["hit_rate"]:.0f}%</div></div>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)

# --- 8. VAULT & SLIPS ---
st.divider()
if os.path.exists("prop_vault.csv"):
    df_v = pd.read_csv("prop_vault.csv")
    if not df_v.empty:
        st.header("🏦 Prop Vault")
        st.dataframe(df_v, use_container_width=True)
        if st.button("🔮 GENERATE SLIPS"): st.session_state.show_slips = True
        if st.button("🗑️ CLEAR"):
            os.remove("prop_vault.csv")
            st.rerun()

        if st.session_state.get('show_slips'):
            df_s = df_v.sort_values(by="Conf (%)", ascending=False)
            cols = st.columns(3)
            titles = ["⚡ 2-Pick Power", "💥 3-Pick Flex", "🎲 4-Pick Lotto"]
            for i, count in enumerate([2, 3, 4]):
                with cols[i]:
                    if len(df_s) >= count:
                        st.markdown(f'<div class="slip-card"><h3>{titles[i]}</h3></div>', unsafe_allow_html=True)
                        for j in range(count):
                            r = df_s.iloc[j]
                            st.write(f"**{r['Player']}** {r['Side']} {r['Line']}")