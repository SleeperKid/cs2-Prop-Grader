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
        for col in ['Team', 'Agents', 'ADR', 'ACS']:
            if col not in cs_df.columns: cs_df[col] = "N/A"
            if col not in val_df.columns: val_df[col] = "N/A"
        return pd.concat([val_df, cs_df], ignore_index=True).fillna("N/A")
    except Exception as e:
        st.error(f"Vault Connection Error: {e}"); return pd.DataFrame()

# ==========================================
# 🎨 PLATINUM UI STYLING (GRADIENTS & BUTTONS)
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide", page_icon="🎯")
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    /* PREMIUM BUTTON STYLING */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white; border: none; padding: 18px;
        font-size: 20px; font-weight: bold; border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4); transition: 0.3s; width: 100%;
        text-transform: uppercase; letter-spacing: 1px;
    }
    div.stButton > button:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(46,160,67,0.5); }
    
    /* GRADE CARD WRAPPER */
    .grade-card { 
        padding: 40px; border-radius: 30px; text-align: center; 
        box-shadow: 0 15px 45px rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.15);
        margin-bottom: 25px; transition: 0.5s;
    }
    .grade-text { font-size: 130px; font-weight: 900; margin: 0; line-height: 1; color: white !important; text-shadow: 4px 4px 15px rgba(0,0,0,0.4); }
    .label-text { font-size: 22px; font-weight: bold; color: white; opacity: 0.9; margin-bottom: 10px; text-transform: uppercase; }
    .sub-text { font-size: 28px; font-weight: 800; color: white; margin-top: 10px; }
    
    /* INTEL & CONTEXT BOXES */
    .intel-box { 
        background: linear-gradient(90deg, rgba(88,166,255,0.15) 0%, rgba(13,17,23,0) 100%); 
        padding: 25px; border-radius: 15px; border-left: 6px solid #58a6ff; margin: 15px 0;
    }
    .context-box { background: #1c2128; padding: 20px; border-radius: 15px; border: 1px solid #30363d; margin-top: 20px; color: #adbac7; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 STATE MANAGEMENT
# ==========================================
df = load_vault()
INTEL = load_intel()

if 'p_tag' not in st.session_state: st.session_state.p_tag = ""
if 'l10' not in st.session_state: st.session_state.l10 = ""
if 'kpr' not in st.session_state: st.session_state.kpr = 0.80
if 'm_context' not in st.session_state: st.session_state.m_context = ""

# ==========================================
# ⚙️ SIDEBAR & AI ADVISOR (TEMP 0.01)
# ==========================================
with st.sidebar:
    st.title("🛡️ Command Center")
    st.subheader("🤖 AI Advisor")
    
    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            client = Groq(api_key=api_key)
            # Pull Intel notes for AI awareness
            p_notes = INTEL.get(st.session_state.p_tag, {}).get('notes', "No specific scouting notes.")
            prompt = f"""Analyze {st.session_state.m_context}. 
            Deep Scout Notes: {p_notes}.
            Suggest 4 weights (0.85-1.15) for: H2H, Tier, Map, Intensity. 
            Format: H2H: X | Tier: X | Map: X | Int: X. Keep temp strict at 0.01."""
            
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile", 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.01 # DIALED DOWN FOR CONSISTENCY
            )
            st.session_state.ai_advice = completion.choices[0].message.content
    
    if "ai_advice" in st.session_state: st.info(st.session_state.ai_advice)
    
    st.divider()
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, 1.0)
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, 1.0)
    map_w = st.slider("Map Fit", 0.80, 1.20, 1.0)
    int_w = st.slider("Match Intensity", 0.70, 1.10, 1.0)

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
st.title("🎯 Prop Grader Elite")

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("📋 Scenario Input")
    game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)
    
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
    st.session_state.m_context = st.text_input("Match Context", value=st.session_state.m_context)
    st.session_state.l10 = st.text_area("L10 Performance Data", value=st.session_state.l10, height=100)
    st.session_state.kpr = st.number_input("Base KPR", value=st.session_state.kpr, format="%.2f")

    c1, c2 = st.columns(2)
    with c1:
        m_line, m_side = st.number_input("Line", 35.5, step=0.5), st.selectbox("Side", ["Over", "Under"])
    with c2:
        m_odds, m_scope = st.number_input("Odds", -115), st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

    # 🧬 DEEP PROFILE BOX (RESTORED & IMPROVED)
    if st.session_state.p_tag in INTEL:
        st.markdown(f"""
        <div class="intel-box">
            <span style="color: #58a6ff; font-weight: bold; font-size: 1.1rem;">🔍 DEEP SCOUT: {st.session_state.p_tag.upper()}</span><br>
            <p style="margin-top: 10px; color: #adbac7;">{INTEL[st.session_state.p_tag].get('notes', '')}</p>
        </div>
        """, unsafe_allow_html=True)

if st.button("🚀 RUN ELITE ANALYSIS"):
    try:
        vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
        stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 2.5, 2.5)
        game_mult = 26 if game_choice == "Valorant" else 24
        scope_map = {"Maps 1 & 2": 1.0, "Map 1 Only": 0.5, "Full Match": 1.3}
        
        proj = (st.session_state.kpr * game_mult * scope_map[m_scope]) * h2h_w * rank_w * map_w * int_w
        model_prob = (1 - norm.cdf(m_line, loc=proj, scale=stdev)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=proj, scale=stdev) * 100
        implied = (abs(m_odds)/(abs(m_odds)+100))*100 if m_odds < 0 else (100/(m_odds+100))*100
        edge = model_prob - implied
        
        # GRADIENT MAPPING
        if edge >= 12: 
            g, u, lbl = "S", 2.5, "ELITE VALUE"
            grad = "linear-gradient(135deg, #FFD700 0%, #B8860B 100%)" # GOLD
        elif edge >= 8: 
            g, u, lbl = "A+", 2.0, "STRONG PLAY"
            grad = "linear-gradient(135deg, #00FF00 0%, #006400 100%)" # GREEN
        elif edge >= 3: 
            g, u, lbl = "A", 1.0, "VALUE PLAY"
            grad = "linear-gradient(135deg, #ADFF2F 0%, #228B22 100%)" # LIME
        else: 
            g, u, lbl = "B", 0.5, "MARGINAL"
            grad = "linear-gradient(135deg, #2c3e50 0%, #000000 100%)" # DARK GRAY

        with col_r:
            # 🃏 PREMIUM GRADE CARD
            st.markdown(f"""
            <div class="grade-card" style="background: {grad};">
                <div class="label-text">{lbl}</div>
                <div class="sub-text" style="font-size: 34px;">{st.session_state.p_tag.upper()} {m_side.upper()} {m_line}</div>
                <h1 class="grade-text">{g}</h1>
                <div class="sub-text">{u} UNIT PLAY</div>
            </div>
            """, unsafe_allow_html=True)

            # 🗺️ CONTEXT BREAKDOWN
            st.markdown(f"""
            <div class="context-box">
                <b style="color: #58a6ff;">🗺️ PROJECTION LOGIC:</b><br>
                Baseline: {(st.session_state.kpr * game_mult * scope_map[m_scope]):.1f} | 
                Model Weighted: <b>{proj:.1f} Kills</b> | 
                Edge Over Bookie: <b>{edge:.1f}%</b>
            </div>
            """, unsafe_allow_html=True)

            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("L10 Hit", f"{(sum(1 for v in vals if (v > m_line if m_side == 'Over' else v < m_line))/len(vals)*100):.0f}%")
            m2.metric("Model Prob", f"{model_prob:.1f}%")
            m3.metric("Volatility", f"{stdev:.1f}")

            # 🤳 SOCIAL SHARE (WITH TOGGLE)
            st.divider()
            show_share = st.checkbox("Show Social Share Card")
            if show_share:
                st.subheader("🤳 Share Card")
                st.code(f"🎯 PROP GRADER ELITE\n🔥 {st.session_state.p_tag.upper()} {m_side.upper()} {m_line}\n📊 GRADE: {g}\n💰 UNITS: {u}\n📈 EDGE: {edge:.1f}%\n🤖 AI Analysis: {h2h_w}/{rank_w}/{map_w}")

    except Exception as e: st.error(f"Analysis Error: {e}")