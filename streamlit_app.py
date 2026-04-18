import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os, json, re
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 🛡️ DATA HYDRATION & REPOSITORY
# ==========================================
def safe_float(value, default=0.0):
    try:
        if pd.isna(value) or str(value).strip() in ["N/A", "", "None"]: return default
        return float(value)
    except: return default

def parse_l10(l10_str):
    if not l10_str or str(l10_str).strip() == "N/A": return []
    try:
        clean_str = str(l10_str).replace('"', '').replace("'", "")
        return [int(x.strip()) for x in clean_str.split(",") if x.strip().isdigit()]
    except: return []

def load_intel(game_choice):
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
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    conn = st.connection("gsheets", type=GSheetsConnection)
    val_df = conn.read(spreadsheet=sheet_url, worksheet="VAL_DATA", ttl=0)
    cs_df = conn.read(spreadsheet=sheet_url, worksheet="CS2_DATA", ttl=0)
    val_df['Game'], cs_df['Game'] = 'Valorant', 'CS2'
    return pd.concat([val_df, cs_df], ignore_index=True).fillna("N/A")

# ==========================================
# 🎨 UI & STYLING
# ==========================================
st.set_page_config(page_title="Prop Grader Elite V140", layout="wide", page_icon="🎯")
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
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 SOVEREIGN STATE MANAGEMENT
# ==========================================
if 'h2h_val' not in st.session_state: st.session_state.h2h_val = 1.0
if 'lan_boost' not in st.session_state: st.session_state.lan_boost = 1.0
if 'econ_adj' not in st.session_state: st.session_state.econ_adj = 1.0
if 'map_veto' not in st.session_state: st.session_state.map_veto = 1.0
if 'ai_advice' not in st.session_state: st.session_state.ai_advice = ""
if 'results' not in st.session_state: st.session_state.results = None

st.title("🎯 Prop Grader Elite")
st.caption("Strategic Context: V140 Active Slider Injection | MR12 Multi-KPR")

game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)
intel_context = load_intel(game_choice)

# ==========================================
# ⚙️ SIDEBAR: COMMAND CENTER
# ==========================================
with st.sidebar:
    st.header("🛡️ Strategic Weights")
    
    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            client = Groq(api_key=api_key)
            prompt = f"Expert {game_choice} Analyst. Tournament Tiers: {intel_context.get('tournaments')}. Archetypes: {intel_context.get('strat_archetypes')}. Suggest 4 weights (0.85-1.15) for H2H, LAN, Econ, Map in brackets [1.05]."
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.01)
            advice = res.choices[0].message.content
            st.session_state.ai_advice = advice
            
            # V140: Slider Auto-Injection
            weights = re.findall(r"\[(\d+(?:\.\d+)?)\]", advice)
            if len(weights) >= 4:
                st.session_state.h2h_val = float(weights[0])
                st.session_state.lan_boost = float(weights[1])
                st.session_state.econ_adj = float(weights[2])
                st.session_state.map_veto = float(weights[3])
                st.rerun()

    if st.session_state.ai_advice: st.info(st.session_state.ai_advice)
    
    # Use key parameter to link sliders to session state
    st.slider("H2H Advantage", 0.80, 1.20, key="h2h_val")
    st.slider("LAN/Rio Crowd Factor", 0.90, 1.10, key="lan_boost")
    st.slider("Economy Discipline", 0.85, 1.15, key="econ_adj")
    st.slider("Map Pool Depth", 0.95, 1.05, key="map_veto")

# ==========================================
# 🕵️ DEEP PROFILE ANALYZER
# ==========================================
col_l, col_r = st.columns([1, 1.2], gap="large")
df = load_vault()

with col_l:
    st.subheader("🕵️ Vault Intelligence")
    active_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected = st.selectbox("Search Vault", ["Manual Entry"] + active_players)
    
    p_tag_val, m_context_val, l10_val = "Player", "", ""
    kpr_baseline = 0.82 if game_choice == "CS2" else 135.0
    
    if selected != "Manual Entry":
        row = df[df['Player'] == selected].iloc[0]
        p_tag_val = str(row['Player'])
        m_context_val = f"{row.get('Team', 'Team')} vs "
        l10_val = str(row['L10'])
        kpr_baseline = safe_float(row.get('KPR' if game_choice == "CS2" else 'ADR'), kpr_baseline)

    p_tag = st.text_input("Player Tag", value=p_tag_val)
    m_context = st.text_input("Match Context", value=m_context_val)
    opp_rank = st.number_input("Opponent World Rank", value=10, step=1)
    
    if game_choice == "CS2":
        ck1, ck2 = st.columns(2)
        m1_kpr = ck1.number_input("Map 1 Projected KPR", value=float(kpr_baseline), format="%.2f")
        m2_kpr = ck2.number_input("Map 2 Projected KPR", value=float(kpr_baseline), format="%.2f")
    else:
        base_stat = st.number_input("Projected ADR", value=float(kpr_baseline))

    l10_data = st.text_area("L10 Match History (Comma Separated)", value=l10_val)
    m_line = st.number_input("Prop Line", value=35.5, step=0.5)
    m_side = st.selectbox("Side", ["Over", "Under"])
    m_odds = st.number_input("Odds", value=-120)

if st.button("🚀 GENERATE V140 ELITE GRADE"):
    l10_list = parse_l10(l10_data)
    stdev = max(np.std(l10_list, ddof=1) if len(l10_list) > 1 else 3.5, 3.5)
    
    # 1. Base Projection
    if game_choice == "CS2":
        base_proj = (m1_kpr * 24) + (m2_kpr * 24)
    else:
        base_proj = (base_stat / 150) * 26 * 2.0 
    
    # 2. V135 Streak Logic
    streak_bonus = 1.0
    streak_hits = 0
    if len(l10_list) >= 5:
        streak_hits = sum(1 for x in l10_list[:5] if x > m_line)
        if streak_hits >= 4: streak_bonus = 1.05
        elif streak_hits <= 1: streak_bonus = 0.95
    
    # 3. Comprehensive Weights (Linked to Sidebar)
    final_proj = base_proj * st.session_state.h2h_val * st.session_state.lan_boost * st.session_state.econ_adj * st.session_state.map_veto * streak_bonus
    
    prob = (1 - norm.cdf(m_line, loc=final_proj, scale=stdev)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=final_proj, scale=stdev) * 100
    implied = (abs(m_odds)/(abs(m_odds)+100))*100 if m_odds < 0 else (100/(m_odds+100))*100
    edge = prob - implied
    
    st.session_state.results = {
        "player": p_tag, "context": m_context,
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
            <p style="font-size: 18px; opacity: 0.8; margin-bottom: 0;">{res['context']} (Rank #{opp_rank})</p>
            <h2 style="margin-top: 0;">{res['player']}</h2>
            <h1 class="analyst-grade">{res['grade']}</h1>
            <div style="font-size: 26px; font-weight: bold;">{res['units']} UNIT PLAY</div>
        </div>""", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        c1.metric("Projected Total", f"{res['proj']:.1f}")
        c2.metric("Edge (%)", f"{res['edge']:.1f}%")
        st.write(f"**Win Probability:** {res['prob']:.1f}%")