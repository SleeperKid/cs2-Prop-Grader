import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os, json, re
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 🛡️ ARCHITECT'S DATA SHIELDS
# ==========================================
def safe_float(value, default=0.0):
    """Prevents app crashes from 'N/A' or empty cells."""
    try:
        if pd.isna(value) or str(value).strip() in ["N/A", "", "None"]: return default
        return float(value)
    except: return default

def load_intel():
    if os.path.exists("intel_vault.json"):
        try:
            with open("intel_vault.json", "r") as f: return json.load(f)
        except: return {}
    return {}

@st.cache_data(ttl=600)
def load_vault():
    """Isolated tab loading to maintain domain integrity."""
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
st.set_page_config(page_title="Prop Grader Elite V75", layout="wide", page_icon="🎯")
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
    .share-container {
        background-color: #121212; border: 3px solid #FFD700; border-radius: 20px;
        padding: 30px; width: 420px; margin: 20px auto; color: white; text-align: center;
        font-family: 'Helvetica', sans-serif;
    }
    .hiro-grade { font-size: 100px; font-weight: 900; color: #FFD700; line-height: 1; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 CORE INITIALIZATION
# ==========================================
df = load_vault()
INTEL = load_intel()

# Sliders Session State
for k in ['h2h_val', 'rank_val', 'map_val', 'int_val']:
    if k not in st.session_state: st.session_state[k] = 1.0

# General State
keys = ['p_tag', 'l10', 'kpr', 'm1_kpr', 'm2_kpr', 'adr', 'm_context', 'results', 'ai_advice', 'proj_maps', 'proj_agents', 'marketing_blurb', 'last_game']
for key in keys:
    if key not in st.session_state: 
        st.session_state[key] = "" if key not in ['kpr', 'm1_kpr', 'm2_kpr', 'adr'] else 0.82

st.title("🎯 Prop Grader Elite")
game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)

if st.session_state.last_game != game_choice:
    st.session_state.last_game = game_choice
    st.rerun()

# ==========================================
# ⚙️ SIDEBAR: AI ADVISOR
# ==========================================
with st.sidebar:
    st.title("🛡️ Command Center")
    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            client = Groq(api_key=api_key)
            prompt = f"Expert Analyst. Context: {st.session_state.proj_maps} | {st.session_state.m_context}. Suggest 4 weights (0.85-1.15) for H2H, Tier, Map, Int in brackets [1.05]."
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.01)
            st.session_state.ai_advice = res.choices[0].message.content
            weights = re.findall(r"\[(\d+(?:\.\d+)?)\]", st.session_state.ai_advice)
            if len(weights) >= 4:
                st.session_state.h2h_val, st.session_state.rank_val, st.session_state.map_val, st.session_state.int_val = map(float, weights[:4])
                st.rerun()

    if st.session_state.ai_advice: st.info(st.session_state.ai_advice)
    st.slider("H2H Advantage", 0.80, 1.20, key="h2h_val")
    st.slider("Opponent Tier", 0.80, 1.20, key="rank_val")
    st.slider("Map Fit", 0.80, 1.20, key="map_val")
    st.slider("Match Intensity", 0.70, 1.10, key="int_val")

# ==========================================
# 🎯 MAIN ANALYZER: DEEP PROFILE
# ==========================================
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Intelligence")
    active_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected = st.selectbox("Search Vault", ["Manual Entry"] + active_players)
    
    if selected != "Manual Entry":
        row = df[df['Player'] == selected].iloc[0]
        st.session_state.p_tag = str(row['Player'])
        st.session_state.l10 = str(row['L10']).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Team')} vs "
        
        # Pull Global Stats as Reference but SHIELD manual fields
        if game_choice == "CS2":
            st.session_state.kpr = safe_float(row.get('KPR'), 0.82)
            st.info(f"📊 Global KPR Baseline: **{st.session_state.kpr}**")
        else:
            st.session_state.adr = safe_float(row.get('ADR', row.get('KPR', 140.0)), 140.0)

    st.text_input("Player Tag", value=st.session_state.p_tag, key="p_tag_input")
    st.text_input("Projected Maps", value=st.session_state.proj_maps, key="proj_maps")
    
    if game_choice == "CS2":
        ck1, ck2 = st.columns(2)
        m1_kpr = ck1.number_input("M1 KPR", value=float(st.session_state.m1_kpr), format="%.2f")
        m2_kpr = ck2.number_input("M2 KPR", value=float(st.session_state.m2_kpr), format="%.2f")
    else:
        adr_val = st.number_input("Base ADR", value=float(st.session_state.adr))

    l10_data = st.text_area("L10 Data", value=st.session_state.l10)
    
    m_line = st.number_input("Line", value=35.5, step=0.5)
    m_side = st.selectbox("Side", ["Over", "Under"])
    m_odds = st.number_input("Odds", value=-128)

if st.button("🚀 GENERATE ELITE GRADE"):
    vals = [float(x.strip()) for x in l10_data.split(",") if x.strip()]
    stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 2.5, 2.5)
    
    if game_choice == "CS2":
        base_proj = (m1_kpr * 24) + (m2_kpr * 24)
    else:
        base_proj = (adr_val / 150) * 26 * 2.0
        
    final_proj = base_proj * st.session_state.h2h_val * st.session_state.rank_val * st.session_state.map_val * st.session_state.int_val
    prob = (1 - norm.cdf(m_line, loc=final_proj, scale=stdev)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=final_proj, scale=stdev) * 100
    edge = prob - ((abs(m_odds)/(abs(m_odds)+100))*100 if m_odds < 0 else (100/(m_odds+100))*100)
    
    # Grading Logic
    g = "S" if edge >= 12 else "A+" if edge >= 8 else "A" if edge >= 3 else "B"
    u = 2.5 if g=="S" else 2.0 if g=="A+" else 1.0 if g=="A" else 0.5
    grad = "linear-gradient(135deg, #FFD700 0%, #8B6508 100%)" if g=="S" else "linear-gradient(135deg, #00FF00 0%, #004d00 100%)"
    
    st.session_state.results = {"grade": g, "units": u, "proj": final_proj, "edge": edge, "prob": prob, "grad": grad, "line": m_line, "side": m_side}

# --- RESULTS DISPLAY ---
if st.session_state.results:
    res = st.session_state.results
    with col_r:
        st.markdown(f"""<div class="analyst-card" style="background: {res['grad']};">
            <h1 class="analyst-grade">{res['grade']}</h1>
            <div style="font-size: 26px; font-weight: bold;">{res['units']} UNIT PLAY</div>
        </div>""", unsafe_allow_html=True)
        st.metric("Projected", f"{res['proj']:.1f}")
        st.progress(res['prob'] / 100)