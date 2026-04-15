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

# --- 0. SETUP & STATE ---
load_dotenv()

def get_api_key(user_input):
    if user_input: return user_input
    if "GROQ_API_KEY" in st.secrets: return st.secrets["GROQ_API_KEY"]
    return os.getenv("GROQ_API_KEY")

if 'weight_advice' not in st.session_state: st.session_state.weight_advice = None
if 'scout_report' not in st.session_state: st.session_state.scout_report = None
if 'analysis_ready' not in st.session_state: st.session_state.analysis_ready = False
if 'show_slips' not in st.session_state: st.session_state.show_slips = False

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
@st.cache_data(show_spinner="Deep Scanning Stats & Context...", ttl=3600)
def get_weight_advice(game, player, matchup, maps, api_key):
    try:
        client = Groq(api_key=api_key)
        prompt = f"""
        Act as an elite {game} betting analyst. 
        Analyze the upcoming match: {matchup} specifically for the player: {player}.
        The expected maps are: {maps}.
        
        Using your knowledge of this player's historical skill, agent/role, and the teams involved, evaluate:
        1. PLAYER SKILL & ROLE: Is this player a star carry, aggressive duelist, or passive anchor?
        2. TEAM TIER: How elite are the opposing team's defenses and structure?
        3. MAP FIT: How does {player} historically perform on {maps}? (Adjust Map Fit weight heavily based on this).
        4. HEAD-TO-HEAD: Is this typically a high-stakes, intense matchup?
        
        Based on this, suggest 4 numerical weights (0.80 to 1.20) for:
        - H2H Advantage
        - Opponent Tier
        - Map Fit
        - Match Intensity
        
        Format EXACTLY as:
        **H2H:** [Value] | **Tier:** [Value] | **Map:** [Value] | **Int:** [Value]
        
        Below the weights, provide a 2-sentence data-driven justification mentioning {player}, the maps ({maps}), and the matchup. Do NOT give general advice.
        """
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return completion.choices[0].message.content
    except Exception as e: 
        return f"Advisor Offline. Error: {str(e)}"

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
            temperature=0.7,
            max_tokens=100
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
        df = pd.DataFrame([data])
        file_exists = os.path.isfile(file_path)
        df.to_csv(file_path, mode='a', header=not file_exists, index=False, quoting=csv.QUOTE_MINIMAL)
        st.session_state['log_success'] = f"Logged {data['Player']} to the Vault!"
        st.session_state.show_slips = False
    except: st.error("Logging failed.")

# --- 2. PAGE CONFIG ---
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

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ App Controls")
    selected_game = st.radio("Select Title", ["CS2", "Valorant"], horizontal=True)
    
    st.subheader("🤖 AI Weight Advisor")
    if st.button("GET AI SLIDER ADVICE"):
        api_to_use = get_api_key(st.text_input("Key Check", type="password", label_visibility="collapsed"))
        current_p = st.session_state.get('p_tag_val', '')
        current_m = st.session_state.get('m_context_val', '')
        current_maps = st.session_state.get('expected_maps_val', '')
        
        if not api_to_use:
            st.error("Enter Groq Key in AI Config")
        elif current_p == "" or current_m == "":
            st.warning("⚠️ Please type a Player Tag and Matchup Context first, hit Enter, then try again.")
        else:
            st.session_state.weight_advice = get_weight_advice(selected_game, current_p, current_m, current_maps, api_to_use)

    if st.session_state.weight_advice:
        st.markdown(f'<div class="advice-box">{st.session_state.weight_advice}</div>', unsafe_allow_html=True)

    st.divider()
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, 1.00, 0.05)
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, 1.00, 0.05)
    map_w = st.slider("Map Fit", 0.80, 1.20, 1.00, 0.05)
    int_w = st.slider("Match Intensity", 0.70, 1.10, 1.00, 0.05)

    st.divider()
    with st.expander(f"📖 {selected_game} Betting Cheat Sheet"):
        if selected_game == "Valorant":
            st.markdown("""
            **Agent Roles (KPR Impact):**
            * **Duelists (Jett, Raze, Neon):** High kills. Push 'Map Fit' > 1.05.
            * **Sentinels (Cypher, Killjoy):** Lower kills. Drop 'Map Fit' < 0.95.
            * **Initiators (Sova, Fade):** Assist heavy. Neutral 1.00.
            
            **Opponent Tiering:**
            * Facing **Sentinels, Fnatic, Gen.G?** Drop 'Tier' to 0.85.
            * Facing **Tier 2/Challengers?** Push 'Tier' to 1.15.
            """)
        else:
            st.markdown("""
            **CS2 Context Clues:**
            * **The "Donk" Factor:** Elite entry fraggers need high 'Intensity' weights.
            * **AWPers:** Impact depends on Map. Mirage/Dust2 = 1.10 Map Fit. Inferno/Nuke = 1.00.
            * **Opponent Tier:** Facing **NAVI/MOUZ?** Drop 'Tier' to 0.85 (Elite defense).
            """)

# --- 4. TOP TITLES ---
if selected_game == "CS2":
    st.title("🎯 CS2 Prop Grader Elite")
else:
    st.title("🛡️ Valorant Prop Grader Elite")

# --- 5. INPUTS ---
col1, col2 = st.columns([1, 1.2], gap="large")

with col1:
    st.subheader("📋 Prop Details")
    p_name = st.text_input("Player Tag", key="p_tag_val", value="donk")
    team_context = st.text_input("Matchup Context", key="m_context_val", value="Spirit vs FaZe")
    expected_maps = st.text_input("Expected Maps (Optional)", key="expected_maps_val", value="Mirage, Nuke")
    
    metric_type = st.radio("Metric", ["Kills", "Headshots"] if selected_game == "CS2" else ["Kills"], horizontal=True)
    
    c1, c2 = st.columns(2)
    with c1:
        m_line = st.number_input(f"Line", value=35.5, step=0.5)
        m_side = st.selectbox("Side", ["Over", "Under"])
    with c2:
        m_odds = st.number_input("Odds", value=-128)
        m_format = st.selectbox("Scope", ["Map 1 Only", "Maps 1 & 2", "Maps 1, 2, & 3", "Full Match"], index=1)

    avg_rate = st.number_input("Base KPR/HSPR", value=0.90)
    manual_data = st.text_area("L10 Stats (comma separated)", value="46, 33, 45, 42, 30, 40, 33, 45, 45, 46")

# --- 6. EXECUTE ---
if 'log_success' in st.session_state:
    st.success(st.session_state['log_success'])
    del st.session_state['log_success']

if st.button("RUN ELITE ANALYSIS"):
    try:
        vals = [float(x.strip()) for x in manual_data.split(",") if x.strip()]
        stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 1.0, 1.0)
        hits = sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line))
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
            "vals": vals, "hit_rate": (hits/len(vals))*100 if len(vals) > 0 else 0, "volatility": stdev, "game": selected_game
        }
        st.session_state.analysis_ready = True
    except Exception as e: st.error(f"Error: {e}")

# --- 7. OUTPUTS ---
with col2:
    if st.session_state.get('analysis_ready'):
        res = st.session_state.results
        
        # UPGRADED GRADE SQUARE UI
        arrow = "▲" if res["side"] == "Over" else "▼"
        grade_html = f"""
<div class="grade-card" style="background: {res["color"]}; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
<div style="font-size: 12px; text-transform: uppercase; letter-spacing: 2px; opacity: 0.8; margin-bottom: 5px;">{res["game"]} • {res["team"]}</div>
<div style="font-size: 28px; font-weight: 900; line-height: 1;">{res["p_name"].upper()}</div>
<div style="font-size: 16px; font-weight: bold; opacity: 0.9; margin-top: 5px; background: rgba(0,0,0,0.15); display: inline-block; padding: 4px 12px; border-radius: 5px;">{arrow} {res["side"].upper()} {res["line"]} {res["label"].upper()}</div>
<h1 class="grade-text" style="font-size: 110px; text-shadow: 2px 4px 10px rgba(0,0,0,0.2); margin: 10px 0;">{res["grade"]}</h1>
<div style="font-weight: bold; font-size: 20px; background: rgba(0,0,0,0.25); display: inline-block; padding: 8px 24px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2);">{res["units"]} UNIT PLAY</div>
</div>
"""
        st.markdown(grade_html, unsafe_allow_html=True)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Projected", f"{res['proj']:.1f}")
        m2.metric("Edge", f"{res['edge']:+.1f}%")
        m3.metric("L10 Hit", f"{res['hit_rate']:.0f}%")
        m4.metric("Volatility", f"{res['volatility']:.1f}")

        if st.button("🔍 ACTIVATE AI SCOUT"):
            api_key_to_use = get_api_key(None)
            if api_key_to_use:
                st.session_state.scout_report = get_groq_scout(res['game'], res['p_name'], res['label'], api_key_to_use)
        
        if st.session_state.get('scout_report'):
            st.markdown(f'<div class="scout-report-box">{st.session_state.scout_report}</div>', unsafe_allow_html=True)

        log_data = {
            "Date": datetime.now().strftime("%Y-%m-%d"), 
            "Game": res["game"], 
            "Player": res["p_name"], 
            "Matchup": res["team"],
            "Metric": res["label"], 
            "Line": res["line"], 
            "Side": res["side"], 
            "Grade": res["grade"], 
            "Edge (%)": round(res["edge"], 1),
            "Conf (%)": round(res["conf"], 1)
        }
        st.button("📥 SAVE TO VAULT", on_click=log_prop, args=(log_data,))

        if st.checkbox("📸 Generate Screenshot Share Card"):
            unit_text = "UNIT" if res["units"] == 1.0 else "UNITS"
            a_color = "#00FF00" if res["side"] == "Over" else "#FF4500"
            
            card_html = f"""
<div style="background-color: #0e1117; border: 3px solid {res["flat"]}; border-radius: 20px; padding: 30px; max-width: 480px; color: white; font-family: sans-serif; margin: 20px auto; box-shadow: 0 10px 30px rgba(0,0,0,0.5), 0 0 15px {res["flat"]}50;">
<div style="text-align: center; border-bottom: 2px solid #30363d; padding-bottom: 15px; margin-bottom: 20px;">
<div style="font-size: 12px; color: #adbac7; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 5px;">{res["game"]} PROP ANALYSIS</div>
<h2 style="margin: 0; font-size: 36px; font-weight: 900; background: linear-gradient(to right, white, #adbac7); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{res["p_name"].upper()}</h2>
<div style="color: #58a6ff; font-size: 16px; font-weight: bold; margin-top: 5px;">{res["team"]}</div>
</div>
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
<div style="flex: 1.2; text-align: left;">
<div style="font-size: 14px; color: #adbac7; text-transform: uppercase; letter-spacing: 1px;">THE PROP LINE</div>
<div style="font-size: 80px; font-weight: 900; line-height: 1; margin: 5px 0; color: white;">{res["line"]}</div>
<div style="font-size: 18px; color: #adbac7; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">{res["label"].upper()}</div>
<div style="font-size: 32px; font-weight: 900; color: {a_color}; background: {a_color}15; padding: 5px 15px; border-radius: 8px; display: inline-block;">{arrow} {res["side"].upper()}</div>
</div>
<div style="flex: 0.8; text-align: right;">
<div style="font-size: 14px; color: #adbac7; text-transform: uppercase; letter-spacing: 1px;">MODEL GRADE</div>
<div style="font-size: 130px; font-weight: 900; color: {res["flat"]}; line-height: 0.8; margin-top: 10px; text-shadow: 0 0 20px {res["flat"]};">{res["grade"]}</div>
</div>
</div>
<div style="background: linear-gradient(135deg, {res["flat"]}30, #161b22); border-radius: 12px; padding: 15px; text-align: center; border: 1px solid {res["flat"]}50; margin-bottom: 20px;">
<div style="font-size: 14px; color: {res["flat"]}; font-weight: bold; text-transform: uppercase; letter-spacing: 2px;">SUGGESTED PLAY</div>
<div style="font-size: 34px; font-weight: 900; color: white; margin-top: 5px;">{res["units"]} {unit_text}</div>
</div>
<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; border-top: 2px solid #30363d; padding-top: 20px;">
<div style="text-align: center; border-right: 1px solid #30363d;"><div style="font-size: 10px; color: #adbac7;">PROJ</div><div style="font-size: 18px; font-weight: bold;">{res["proj"]:.1f}</div></div>
<div style="text-align: center; border-right: 1px solid #30363d;"><div style="font-size: 10px; color: #adbac7;">EDGE</div><div style="font-size: 18px; font-weight: bold; color: {res["flat"]};">+{res["edge"]:.1f}%</div></div>
<div style="text-align: center; border-right: 1px solid #30363d;"><div style="font-size: 10px; color: #adbac7;">CONF</div><div style="font-size: 18px; font-weight: bold;">{res["conf"]:.0f}%</div></div>
<div style="text-align: center;"><div style="font-size: 10px; color: #adbac7;">L10 HIT</div><div style="font-size: 18px; font-weight: bold;">{res["hit_rate"]:.0f}%</div></div>
</div>
<div style="text-align: center; margin-top: 30px; border-top: 1px solid #30363d; padding-top: 15px;">
<div style="font-size: 13px; color: #58a6ff; font-weight: bold; letter-spacing: 4px; text-transform: uppercase;">ANALYSIS BY SLEEPER D. KID</div>
</div>
</div>
"""
            st.markdown(card_html, unsafe_allow_html=True)

# --- 8. THE PROP VAULT & SLIP BUILDER ---
st.divider()
st.header("🏦 The Prop Vault & Slip Builder")
st.markdown("Save props here during your research session. When ready, the engine will rank them and build optimal parlay combinations based on mathematical confidence.")

if os.path.exists("prop_vault.csv"):
    df_vault = pd.read_csv("prop_vault.csv")
    
    if not df_vault.empty:
        st.dataframe(df_vault, use_container_width=True)
        
        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("🔮 GENERATE SLIPS", type="primary"):
                st.session_state.show_slips = True
        with c2:
            if st.button("🗑️ CLEAR VAULT"):
                os.remove("prop_vault.csv")
                st.session_state.show_slips = False
                st.rerun()

        if st.session_state.show_slips:
            df_sorted = df_vault.sort_values(by="Conf (%)", ascending=False)
            
            st.divider()
            st.subheader("🔥 Elite Mathematical Pairings")
            
            p1, p2, p3 = st.columns(3)
            
            with p1:
                if len(df_sorted) >= 2:
                    st.markdown("""<div class="slip-card"><h3 style="color: #58a6ff; margin-top: 0;">⚡ 2-Pick Power Play</h3></div>""", unsafe_allow_html=True)
                    for i in range(2):
                        row = df_sorted.iloc[i]
                        arrow = "▲" if row['Side'] == 'Over' else "▼"
                        st.markdown(f"**{row['Player']}** {arrow} {row['Line']} {row['Metric']} <br><span style='color: #adbac7; font-size: 12px;'>Grade: {row['Grade']} | Conf: {row['Conf (%)']}%</span>", unsafe_allow_html=True)
                else:
                    st.info("Log at least 2 props to generate a 2-pick slip.")

            with p2:
                if len(df_sorted) >= 3:
                    st.markdown("""<div class="slip-card"><h3 style="color: #FFD700; margin-top: 0;">💥 3-Pick Flex Play</h3></div>""", unsafe_allow_html=True)
                    for i in range(3):
                        row = df_sorted.iloc[i]
                        arrow = "▲" if row['Side'] == 'Over' else "▼"
                        st.markdown(f"**{row['Player']}** {arrow} {row['Line']} {row['Metric']} <br><span style='color: #adbac7; font-size: 12px;'>Grade: {row['Grade']} | Conf: {row['Conf (%)']}%</span>", unsafe_allow_html=True)
                else:
                    st.info("Log at least 3 props to generate a 3-pick slip.")

            with p3:
                if len(df_sorted) >= 4:
                    st.markdown("""<div class="slip-card"><h3 style="color: #FF4500; margin-top: 0;">🎲 4-Pick Lotto</h3></div>""", unsafe_allow_html=True)
                    for i in range(4):
                        row = df_sorted.iloc[i]
                        arrow = "▲" if row['Side'] == 'Over' else "▼"
                        st.markdown(f"**{row['Player']}** {arrow} {row['Line']} {row['Metric']} <br><span style='color: #adbac7; font-size: 12px;'>Grade: {row['Grade']} | Conf: {row['Conf (%)']}%</span>", unsafe_allow_html=True)
                else:
                    st.info("Log at least 4 props to generate a 4-pick slip.")
    else:
        st.write("Your vault is currently empty. Run an analysis and click 'SAVE TO VAULT' to start building slips.")
