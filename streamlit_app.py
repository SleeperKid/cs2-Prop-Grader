import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os, json, re
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 📥 DATA & INTEL LOADERS
# ==========================================
def load_intel():
    if os.path.exists("intel_vault.json"):
        try:
            with open("intel_vault.json", "r") as f: return json.load(f)
        except: return {}
    return {}

@st.cache_data(ttl=600)
def load_vault():
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        val_df = conn.read(spreadsheet=sheet_url, worksheet="VAL_DATA", ttl=0)
        cs_df = conn.read(spreadsheet=sheet_url, worksheet="CS2_DATA", ttl=0)
        val_df['Game'], cs_df['Game'] = 'Valorant', 'CS2'
        return pd.concat([val_df, cs_df], ignore_index=True).fillna("N/A")
    except Exception as e:
        st.error(f"Vault Connection Error: {e}"); return pd.DataFrame()

# ==========================================
# 🎨 UI STYLING
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide", page_icon="🎯")
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white; border: none; padding: 18px; font-size: 20px; font-weight: bold; 
        border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.4); width: 100%;
    }
    .grade-card { padding: 40px; border-radius: 30px; text-align: center; box-shadow: 0 15px 45px rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.15); }
    .grade-text { font-size: 130px; font-weight: 900; margin: 0; line-height: 1; color: white !important; }
    .intel-box { background: linear-gradient(90deg, rgba(88,166,255,0.1) 0%, rgba(13,17,23,0) 100%); padding: 20px; border-radius: 12px; border-left: 5px solid #58a6ff; margin-bottom: 20px; }
    .map-logic-box { background: #1c2128; padding: 20px; border-radius: 15px; border: 1px solid #30363d; margin-top: 15px; color: #adbac7; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 STATE MANAGEMENT (AUTO-SLIDER LOGIC)
# ==========================================
df = load_vault()
INTEL = load_intel()

# Initialize Slider States
if 'h2h_val' not in st.session_state: st.session_state.h2h_val = 1.0
if 'rank_val' not in st.session_state: st.session_state.rank_val = 1.0
if 'map_val' not in st.session_state: st.session_state.map_val = 1.0
if 'int_val' not in st.session_state: st.session_state.int_val = 1.0

keys = ['p_tag', 'l10', 'kpr', 'adr', 'acs', 'm_context', 'w_rank', 'results', 'ai_advice', 'tourney_type']
for key in keys:
    if key not in st.session_state: st.session_state[key] = "" if key not in ['kpr', 'adr', 'acs'] else 0.80

# ==========================================
# ⚙️ SIDEBAR: AI & AUTONOMOUS SLIDERS
# ==========================================
with st.sidebar:
    st.title("🛡️ Command Center")
    st.session_state.tourney_type = st.selectbox("Tournament Prestige", ["S-Tier", "A-Tier", "Qualifiers", "Showmatch"])

    st.subheader("🤖 AI Match Advisor")
    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            client = Groq(api_key=api_key)
            p_intel = INTEL.get(st.session_state.p_tag, {})
            # Feed specific game stats to AI
            stat_context = f"KPR: {st.session_state.kpr}" if "CS2" in str(df) else f"ADR: {st.session_state.adr}, ACS: {st.session_state.acs}"
            
            prompt = f"""
            SYSTEM: Betting Expert (Temp 0.01). 
            CONTEXT: {st.session_state.m_context} | {st.session_state.tourney_type} | Player Stats: {stat_context}.
            INTEL: {p_intel}.
            TASK: Suggest 4 weights (0.85-1.15) for H2H, Tier, Map, Intensity.
            RULES: 
            1. Max 4 sentences per weight.
            2. You MUST include the numeric weight in brackets like this: [1.05].
            """
            completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.01)
            response = completion.choices[0].message.content
            st.session_state.ai_advice = response
            
            # --- AUTO-ADJUST SLIDERS VIA REGEX ---
            weights = re.findall(r"\[(\d\.\d+)\]", response)
            if len(weights) >= 4:
                st.session_state.h2h_val = float(weights[0])
                st.session_state.rank_val = float(weights[1])
                st.session_state.map_val = float(weights[2])
                st.session_state.int_val = float(weights[3])
                st.rerun()

    if st.session_state.ai_advice: st.info(st.session_state.ai_advice)
    
    st.divider()
    # Sliders now tied to session_state keys
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, key="h2h_val")
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, key="rank_val")
    map_w = st.slider("Map Fit", 0.80, 1.20, key="map_val")
    int_w = st.slider("Match Intensity", 0.70, 1.10, key="int_val")

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
st.title("🎯 Prop Grader Elite")
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    if st.session_state.p_tag in INTEL:
        p_data = INTEL[st.session_state.p_tag]
        st.markdown(f"""<div class="intel-box"><span style="color:#58a6ff;font-weight:bold;">🔍 {st.session_state.p_tag.upper()} STRATEGY PROFILE</span><br><small>ARCHETYPE: {p_data.get('archetype','N/A')}</small><p style="color:#adbac7;margin-top:10px;">{p_data.get('notes','')}</p></div>""", unsafe_allow_html=True)

    game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)
    db_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected = st.selectbox("Database Search", ["Manual Entry"] + db_players)
    
    if selected != "Manual Entry":
        row = df[df['Player'] == selected].iloc[0]
        st.session_state.p_tag, st.session_state.l10 = row['Player'], str(row['L10']).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Team')} vs "
        # Dynamic Stat Loading
        if game_choice == "CS2": st.session_state.kpr = float(row.get('KPR', 0.80))
        else:
            st.session_state.adr = float(row.get('ADR', 140.0))
            st.session_state.acs = float(row.get('ACS', 220.0))

    st.session_state.p_tag = st.text_input("Player Tag", value=st.session_state.p_tag)
    st.session_state.m_context = st.text_input("Match Context", value=st.session_state.m_context)
    st.session_state.w_rank = st.text_input("Opponent World Rank", value=st.session_state.w_rank)
    st.session_state.l10 = st.text_area("L10 Data", value=st.session_state.l10)

    # --- GAME SPECIFIC STAT INPUTS ---
    if game_choice == "CS2":
        st.session_state.kpr = st.number_input("Base KPR (CS2 Focus)", value=st.session_state.kpr)
        active_base = st.session_state.kpr
    else:
        c1, c2 = st.columns(2)
        st.session_state.adr = c1.number_input("Base ADR (Val Focus)", value=st.session_state.adr)
        st.session_state.acs = c2.number_input("Base ACS (Val Focus)", value=st.session_state.acs)
        # For Valorant, we use a hybrid Base Rate for the math
        active_base = (st.session_state.adr / 150) + (st.session_state.acs / 300) 

    c1, c2 = st.columns(2)
    with c1: m_line, m_side = st.number_input("Line", 35.5, step=0.5), st.selectbox("Side", ["Over", "Under"])
    with c2: m_odds, m_scope = st.number_input("Odds", -115), st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

if st.button("🚀 RUN ELITE ANALYSIS"):
    vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
    stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 2.5, 2.5)
    game_mult = 26 if game_choice == "Valorant" else 24
    scope_map = {"Maps 1 & 2": 1.0, "Map 1 Only": 0.5, "Full Match": 1.3}
    
    # Calculate
    base_proj = active_base * game_mult * scope_map[m_scope]
    final_proj = base_proj * st.session_state.h2h_val * st.session_state.rank_val * st.session_state.map_val * st.session_state.int_val
    prob = (1 - norm.cdf(m_line, loc=final_proj, scale=stdev)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=final_proj, scale=stdev) * 100
    edge = prob - ((abs(m_odds)/(abs(m_odds)+100))*100 if m_odds < 0 else (100/(m_odds+100))*100)
    
    grad = "linear-gradient(135deg, #FFD700 0%, #8B6508 100%)" if edge >= 12 else "linear-gradient(135deg, #00FF00 0%, #004d00 100%)" if edge >= 8 else "linear-gradient(135deg, #ADFF2F 0%, #228B22 100%)" if edge >= 3 else "linear-gradient(135deg, #2c3e50 0%, #000000 100%)"
    st.session_state.results = {"grad": grad, "grade": "S" if edge >= 12 else "A+" if edge >= 8 else "A" if edge >= 3 else "B", "units": 2.5 if edge >= 12 else 2.0 if edge >= 8 else 1.0 if edge >= 3 else 0.5, "proj": final_proj, "base": base_proj, "edge": edge, "prob": prob, "vals": vals, "m_line": m_line, "m_side": m_side, "scope": m_scope}

if st.session_state.results:
    res = st.session_state.results
    with col_r:
        st.markdown(f"""<div class="grade-card" style="background: {res['grad']}; color: white;">
            <div style="font-size:34px; font-weight:900;">{st.session_state.p_tag.upper()} {res['m_side'].upper()} {res['m_line']}</div>
            <h1 class="grade-text">{res['grade']}</h1>
            <div style="font-size:28px; font-weight:bold;">{res['units']} UNIT PLAY</div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"""<div class="map-logic-box"><b style="color:#58a6ff;">🗺️ PROJECTED MAPS LOGIC:</b><br>
            • Baseline ({res['scope']}): {res['base']:.1f}<br>
            • Multipliers Applied: x{(st.session_state.h2h_val*st.session_state.rank_val*st.session_state.map_val*st.session_state.int_val):.2f}<br>
            • Final Elite Projection: <b>{res['proj']:.1f} Total Kills</b></div>""", unsafe_allow_html=True)

        st.divider()
        if st.checkbox("Show Social Share Card"):
            st.code(f"🎯 PROP GRADER ELITE\n🔥 {st.session_state.p_tag.upper()} {res['m_side'].upper()} {res['m_line']}\n📊 GRADE: {res['grade']}\n📈 EDGE: {res['edge']:.1f}%")