import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os, json, re
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 🛡️ DATA HYDRATION & INTEL REPOSITORY
# ==========================================
def safe_float(value, default=0.0):
    try:
        if pd.isna(value) or str(value).strip() in ["N/A", "", "None"]: return default
        return float(value)
    except: return default

def parse_l10(l10_str):
    """V132 Standard: Parses comma-separated strings into usable integer lists."""
    if not l10_str or str(l10_str).strip() == "N/A": return []
    try:
        clean_str = str(l10_str).replace('"', '').replace("'", "")
        return [int(x.strip()) for x in clean_str.split(",") if x.strip().isdigit()]
    except: return []

def load_intel(game_choice):
    """Merged V138: Loads only the foundation for the active game choice."""
    if os.path.exists("intel_vault.json"):
        try:
            with open("intel_vault.json", "r") as f: 
                full_vault = json.load(f)
                key = "VAL" if "Val" in game_choice else "CS2"
                return full_vault.get(key, {})
        except: return {}
    return {}

@st.cache_data(ttl=0)
def load_vault():
    """GSheets Hub: Loads live data from the Vault."""
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        val_df = conn.read(spreadsheet=sheet_url, worksheet="VAL_DATA", ttl=0)
        cs_df = conn.read(spreadsheet=sheet_url, worksheet="CS2_DATA", ttl=0)
        val_df['Game'], cs_df['Game'] = 'Valorant', 'CS2'
        return pd.concat([val_df, cs_df], ignore_index=True).fillna("N/A")
    except Exception as e:
        st.error(f"Vault Connection Failure: {e}"); return pd.DataFrame()

# ==========================================
# 🎨 SOVEREIGN CSS STYLING
# ==========================================
st.set_page_config(page_title="Prop Grader Elite V138", layout="wide", page_icon="🎯")
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white; border: none; padding: 18px; border-radius: 12px; width: 100%; font-weight: bold;
    }
    .analyst-card { 
        padding: 40px; border-radius: 30px; text-align: center; 
        box-shadow: 0 15px 45px rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.15);
        margin-bottom: 25px; color: white;
    }
    .analyst-grade { font-size: 130px; font-weight: 900; margin: 0; line-height: 1; }
    .streak-bar { height: 10px; border-radius: 5px; margin-top: 5px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 CORE INITIALIZATION
# ==========================================
df = load_vault()

# Initialize Session States
if 'last_game' not in st.session_state: st.session_state.last_game = "CS2"
if 'ai_advice' not in st.session_state: st.session_state.ai_advice = ""
if 'results' not in st.session_state: st.session_state.results = None

st.title("🎯 Prop Grader Elite")
st.caption("Strategic Context: V138 Merged Intel | MR12 Multipliers Active")

game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)
intel_context = load_intel(game_choice)

if st.session_state.last_game != game_choice:
    st.session_state.last_game = game_choice
    st.session_state.results = None
    st.rerun()

# ==========================================
# ⚙️ SIDEBAR: COMMAND CENTER (V138 WEIGHTS)
# ==========================================
with st.sidebar:
    st.header("🛡️ Strategic Weights")
    
    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            client = Groq(api_key=api_key)
            # Prompt uses the merged foundation categories
            prompt = f"Expert {game_choice} Analyst. Tournament Tiers: {intel_context.get('tournaments')}. Archetypes: {intel_context.get('strat_archetypes')}. Suggest 4 weights (0.85-1.15) for H2H, LAN, Econ, Map in brackets [1.05]."
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.01)
            st.session_state.ai_advice = res.choices[0].message.content
            st.rerun()

    if st.session_state.ai_advice: st.info(st.session_state.ai_advice)
    
    h2h_val = st.slider("H2H Advantage", 0.80, 1.20, 1.0)
    lan_boost = st.slider("LAN/Rio Crowd Factor", 0.90, 1.10, 1.0)
    econ_adj = st.slider("Economy Discipline (MR12)", 0.85, 1.15, 1.0)
    map_veto = st.slider("Map Pool Depth", 0.95, 1.05, 1.0)

# ==========================================
# 🕵️ VAULT PROFILE ANALYZER
# ==========================================
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("📊 Deep Profile Intel")
    active_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected = st.selectbox("Search Vault", ["Manual Entry"] + active_players)
    
    p_tag, l10_raw = "Player", ""
    kpr_baseline = 0.82 if game_choice == "CS2" else 135.0 # ADR default for Val
    
    if selected != "Manual Entry":
        row = df[df['Player'] == selected].iloc[0]
        p_tag, l10_raw = str(row['Player']), str(row['L10'])
        kpr_baseline = safe_float(row.get('KPR' if game_choice == "CS2" else 'ADR'), kpr_baseline)

    p_tag = st.text_input("Player Tag", value=p_tag)
    base_stat = st.number_input("Base KPR" if game_choice == "CS2" else "Base ADR", value=float(kpr_baseline))
    l10_data = st.text_area("L10 Match History (Comma Separated)", value=l10_raw)
    
    m_line = st.number_input("Line", value=35.5, step=0.5)
    m_side = st.selectbox("Side", ["Over", "Under"])
    m_odds = st.number_input("Odds", value=-120)

if st.button("🚀 GENERATE V138 ELITE GRADE"):
    l10_list = parse_l10(l10_data)
    stdev = max(np.std(l10_list, ddof=1) if len(l10_list) > 1 else 3.5, 3.5)
    
    # 1. Base Scaling (MR12 24-round standard)
    if game_choice == "CS2":
        base_proj = base_stat * 24 * 2.0
    else:
        base_proj = (base_stat / 150) * 26 * 2.0 # Normalized Val ADR to Kills
    
    # 2. V138 Momentum Logic (5-Game Window)
    streak_bonus = 1.0
    streak_hits = 0
    if len(l10_list) >= 5:
        streak_hits = sum(1 for x in l10_list[:5] if x > m_line)
        if streak_hits >= 4: streak_bonus = 1.05
        elif streak_hits <= 1: streak_bonus = 0.95
    
    # 3. Comprehensive Weights
    final_proj = base_proj * h2h_val * lan_boost * econ_adj * map_veto * streak_bonus
    
    # 4. Probability Engine
    prob = (1 - norm.cdf(m_line, loc=final_proj, scale=stdev)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=final_proj, scale=stdev) * 100
    implied = (abs(m_odds)/(abs(m_odds)+100))*100 if m_odds < 0 else (100/(m_odds+100))*100
    edge = prob - implied
    
    st.session_state.results = {
        "grade": "S" if edge >= 12 else "A+" if edge >= 8 else "A" if edge >= 3 else "B",
        "units": 2.5 if edge >= 12 else 2.0 if edge >= 8 else 1.0,
        "proj": final_proj, "prob": prob, "edge": edge, "hits": streak_hits,
        "color": "linear-gradient(135deg, #FFD700 0%, #8B6508 100%)" if edge >= 12 else "linear-gradient(135deg, #00FF00 0%, #004d00 100%)"
    }

# ==========================================
# 📊 RESULTS DISPLAY
# ==========================================
if st.session_state.results:
    res = st.session_state.results
    with col_r:
        st.markdown(f"""<div class="analyst-card" style="background: {res['color']};">
            <h1 class="analyst-grade">{res['grade']}</h1>
            <div style="font-size: 26px; font-weight: bold;">{res['units']} UNIT PLAY</div>
        </div>""", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        c1.metric("Projected Total", f"{res['proj']:.1f}")
        c2.metric("Edge (%)", f"{res['edge']:.1f}%")
        
        st.write(f"**Win Probability:** {res['prob']:.1f}%")
        if res['hits'] >= 4:
            st.success(f"🔥 STREAK ACTIVE: Player cleared line in {res['hits']}/5 recent matches.")
        elif res['hits'] <= 1 and len(parse_l10(l10_data)) >= 5:
            st.error(f"❄️ SLUMP ACTIVE: Player cleared line in {res['hits']}/5 recent matches.")