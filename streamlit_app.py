import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os, json, re
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 📥 DATA LOADERS
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
        for col in ['Team', 'Agents', 'ADR', 'ACS']:
            if col not in cs_df.columns: cs_df[col] = "N/A"
            if col not in val_df.columns: val_df[col] = "N/A"
        return pd.concat([val_df, cs_df], ignore_index=True).fillna("N/A")
    except Exception as e:
        st.error(f"Vault Connection Error: {e}"); return pd.DataFrame()

# ==========================================
# 🎨 HIGH-GLOSS ELITE STYLING
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide", page_icon="🎯")
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white; border: none; padding: 15px 32px;
        font-size: 18px; font-weight: bold; border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3); transition: 0.3s; width: 100%;
    }
    div.stButton > button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(46,160,67,0.4); }
    .grade-card { 
        padding: 40px; border-radius: 25px; text-align: center; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 25px;
    }
    .grade-text { font-size: 120px; font-weight: 900; margin: 0; line-height: 1; text-shadow: 3px 3px 10px rgba(0,0,0,0.3); }
    .context-box { background: #161b22; padding: 20px; border-radius: 12px; border: 1px solid #30363d; margin-top: 20px; }
    .intel-box { background: rgba(88, 166, 255, 0.1); padding: 20px; border-radius: 12px; border-left: 5px solid #58a6ff; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 SESSION STATE & INITIALIZATION
# ==========================================
df = load_vault()
INTEL = load_intel()

if 'p_tag' not in st.session_state: st.session_state.p_tag = ""
if 'l10' not in st.session_state: st.session_state.l10 = ""
if 'kpr' not in st.session_state: st.session_state.kpr = 0.80
if 'm_context' not in st.session_state: st.session_state.m_context = ""

# ==========================================
# ⚙️ SIDEBAR
# ==========================================
with st.sidebar:
    st.title("🛡️ Command Center")
    st.subheader("🤖 AI Advisor")
    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            client = Groq(api_key=api_key)
            prompt = f"Analyze {st.session_state.m_context}. Suggest 4 weights (0.85-1.15) for: H2H, Tier, Map, Int. Format: H2H: X | Tier: X | Map: X | Int: X"
            completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
            st.session_state.ai_advice = completion.choices[0].message.content
    
    if "ai_advice" in st.session_state: st.info(st.session_state.ai_advice)
    
    st.divider()
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, 1.0)
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, 1.0)
    map_w = st.slider("Map Fit", 0.80, 1.20, 1.0)
    int_w = st.slider("Match Intensity", 0.70, 1.10, 1.0)

    with st.expander("📖 SLIDER STRATEGY GUIDE"):
        st.write("H2H: +10% if player owns matchup. Tier: -10% vs Top 5 teams. Map: +5% for comfort maps. Int: +5% for Playoffs.")

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
st.title("🎯 Prop Grader Elite")

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("📋 Scenario Input")
    game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)
    
    # Dropdown Logic
    db_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected = st.selectbox("Database Search", ["Manual Entry"] + db_players)
    
    if selected != "Manual Entry":
        row = df[df['Player'] == selected].iloc[0]
        st.session_state.p_tag = row['Player']
        st.session_state.l10 = str(row['L10']).replace('"', '')
        st.session_state.kpr = float(row['KPR'])
        st.session_state.m_context = f"{row.get('Team', 'Team')} vs "

    # Main Inputs
    st.session_state.p_tag = st.text_input("Player Tag", value=st.session_state.p_tag)
    st.session_state.m_context = st.text_input("Match Context (Auto-filled)", value=st.session_state.m_context)
    st.session_state.l10 = st.text_area("L10 Data (Keep Visible)", value=st.session_state.l10)
    st.session_state.kpr = st.number_input("Base KPR", value=st.session_state.kpr, step=0.01)

    c1, c2 = st.columns(2)
    with c1:
        m_line, m_side = st.number_input("Line", 35.5, step=0.5), st.selectbox("Side", ["Over", "Under"])
    with c2:
        m_odds, m_scope = st.number_input("Odds", -115), st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

    if st.session_state.p_tag in INTEL:
        st.markdown(f'<div class="intel-box"><b>🔍 Vault Intel:</b><br>{INTEL[st.session_state.p_tag].get("notes", "")}</div>', unsafe_allow_html=True)

if st.button("🚀 GENERATE ELITE GRADE"):
    try:
        vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
        stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 2.0, 2.0)
        game_mult = 26 if game_choice == "Valorant" else 24
        scope_map = {"Maps 1 & 2": 1.0, "Map 1 Only": 0.5, "Full Match": 1.3}
        
        proj = (st.session_state.kpr * game_mult * scope_map[m_scope]) * h2h_w * rank_w * map_w * int_w
        model_prob = (1 - norm.cdf(m_line, loc=proj, scale=stdev)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=proj, scale=stdev) * 100
        implied = (abs(m_odds)/(abs(m_odds)+100))*100 if m_odds < 0 else (100/(m_odds+100))*100
        edge = model_prob - implied
        
        if edge >= 12: g, c, u, lbl = "S", "linear-gradient(135deg, #FFD700, #FFA500)", 2.5, "ELITE VALUE"
        elif edge >= 8: g, c, u, lbl = "A+", "linear-gradient(135deg, #00FF00, #008000)", 2.0, "STRONG PLAY"
        elif edge >= 3: g, c, u, lbl = "A", "linear-gradient(135deg, #ADFF2F, #228B22)", 1.0, "VALUE PLAY"
        else: g, c, u, lbl = "B", "#1c2128", 0.5, "MARGINAL"

        with col_r:
            st.markdown(f"""<div class="grade-card" style="background: {c}; color: white;">
                <div style="font-size: 20px; font-weight: bold; opacity: 0.8;">{lbl}</div>
                <div style="font-size: 32px; font-weight: 900;">{st.session_state.p_tag.upper()} {m_side.upper()} {m_line}</div>
                <h1 class="grade-text">{g}</h1>
                <div style="font-size: 26px; font-weight: bold;">{u} UNIT PLAY</div>
            </div>""", unsafe_allow_html=True)

            st.markdown(f"""<div class="context-box"><b>🗺️ Projection Logic Breakdown:</b><br>
                Baseline: {(st.session_state.kpr * game_mult * scope_map[m_scope]):.1f} | 
                Weighted: {proj:.1f} Kills | Edge: {edge:.1f}%</div>""", unsafe_allow_html=True)

            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("L10 Hit", f"{(sum(1 for v in vals if (v > m_line if m_side == 'Over' else v < m_line))/len(vals)*100):.0f}%")
            m2.metric("Model Prob", f"{model_prob:.1f}%")
            m3.metric("Volatility", f"{stdev:.1f}")

            st.subheader("🤳 Social Share Card")
            st.code(f"🎯 PROP GRADER ELITE\n🔥 {st.session_state.p_tag.upper()} {m_side.upper()} {m_line}\n📊 GRADE: {g}\n💰 UNITS: {u}\n📈 EDGE: {edge:.1f}%\n🤖 AI Analysis: {h2h_w}/{rank_w}/{map_w}")

    except Exception as e: st.error(f"Error: {e}")