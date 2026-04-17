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
# 🎨 SOVEREIGN CSS STYLING
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
    .intel-box { 
        background: linear-gradient(90deg, rgba(88,166,255,0.1) 0%, rgba(13,17,23,0) 100%); 
        padding: 20px; border-radius: 12px; border-left: 5px solid #58a6ff; margin-bottom: 20px;
    }
    .map-logic-box { 
        background: #1c2128; padding: 20px; border-radius: 15px; border: 1px solid #30363d; 
        margin-top: 15px; color: #adbac7; line-height: 1.6;
    }
    .share-container {
        background-color: #121212; border: 3px solid #FFD700; border-radius: 20px;
        padding: 30px; width: 400px; margin: auto; color: white; text-align: center;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.3);
    }
    .share-player { font-size: 50px; font-weight: 900; margin: 10px 0; letter-spacing: 2px; text-transform: uppercase; }
    .pill-over { background: #1b3a1e; border: 1px solid #2ea043; border-radius: 10px; padding: 10px 20px; display: inline-block; font-size: 24px; font-weight: 900; color: #3fb950; text-transform: uppercase; }
    .grade-box { font-size: 100px; font-weight: 900; color: #FFD700; text-shadow: 0 0 15px rgba(255,215,0,0.6); line-height: 1; }
    .suggested-play { background: #1c1c1c; border: 1px solid #FFD700; border-radius: 15px; padding: 15px; margin: 20px 0; }
    .metric-grid { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; margin-top: 20px; border-top: 1px solid #30363d; padding-top: 15px; }
    .metric-val { font-size: 16px; font-weight: bold; color: white; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 CORE INITIALIZATION
# ==========================================
df = load_vault()
INTEL = load_intel()

# Sliders
for k in ['h2h_val', 'rank_val', 'map_val', 'int_val']:
    if k not in st.session_state: st.session_state[k] = 1.0

# General State
keys = ['p_tag', 'l10', 'kpr', 'adr', 'acs', 'm_context', 'w_rank', 'results', 'ai_advice', 'tourney_type']
for key in keys:
    if key not in st.session_state: st.session_state[key] = "" if key not in ['kpr', 'adr', 'acs'] else 0.80

# --- FIX: Move Game Choice to top level so Sidebar can see it ---
st.title("🎯 Prop Grader Elite")
game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)

# ==========================================
# ⚙️ SIDEBAR: AI & AUTONOMOUS SLIDERS
# ==========================================
with st.sidebar:
    st.title("🛡️ Command Center")
    st.session_state.tourney_type = st.selectbox("Tournament Prestige", ["S-Tier", "A-Tier", "Qualifiers", "Showmatch"])

    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            client = Groq(api_key=api_key)
            p_intel = INTEL.get(st.session_state.p_tag, {})
            # Now game_choice is defined and accessible
            stat_context = f"KPR: {st.session_state.kpr}" if game_choice == "CS2" else f"ADR: {st.session_state.adr}, ACS: {st.session_state.acs}"
            
            prompt = f"""
            Expert Analyst Mode. Context: {st.session_state.m_context} | {st.session_state.tourney_type} | Player: {st.session_state.p_tag}. 
            Stats: {stat_context}. Intel: {p_intel}.
            Task: Weights for H2H, Tier, Map, Int. 
            Rules: MAX 4 sentences each. Include weights in brackets like [1.05].
            """
            completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.01)
            st.session_state.ai_advice = completion.choices[0].message.content
            
            weights = re.findall(r"\[(\d\.\d+)\]", st.session_state.ai_advice)
            if len(weights) >= 4:
                st.session_state.h2h_val, st.session_state.rank_val, st.session_state.map_val, st.session_state.int_val = map(float, weights[:4])
                st.rerun()

    if st.session_state.ai_advice: st.info(st.session_state.ai_advice)
    
    st.divider()
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, key="h2h_val")
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, key="rank_val")
    map_w = st.slider("Map Fit", 0.80, 1.20, key="map_val")
    int_w = st.slider("Match Intensity", 0.70, 1.10, key="int_val")

    with st.expander("📖 SLIDER STRATEGY GUIDE"):
        st.write("**H2H:** Boost for specific counter-strat archetypes.")
        st.write("**Tier:** Adjust based on Tournament Tier (S-Tier = lower KPR variance).")
        st.write("**Map:** Use intel-vault map explanations.")

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    if st.session_state.p_tag in INTEL:
        p_data = INTEL[st.session_state.p_tag]
        st.markdown(f"""<div class="intel-box"><span style="color:#58a6ff;font-weight:bold;">🔍 {st.session_state.p_tag.upper()} STRATEGY PROFILE</span><br><p style="color:#adbac7;margin-top:10px;">{p_data.get('notes','')}</p></div>""", unsafe_allow_html=True)

    db_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected = st.selectbox("Database Search", ["Manual Entry"] + db_players)
    
    if selected != "Manual Entry":
        row = df[df['Player'] == selected].iloc[0]
        st.session_state.p_tag, st.session_state.l10 = row['Player'], str(row['L10']).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Team')} vs "
        if game_choice == "CS2": st.session_state.kpr = float(row.get('KPR', 0.82))
        else: st.session_state.adr, st.session_state.acs = float(row.get('ADR', 140)), float(row.get('ACS', 220))

    st.session_state.p_tag = st.text_input("Player Tag", value=st.session_state.p_tag)
    st.session_state.m_context = st.text_input("Match Context", value=st.session_state.m_context)
    st.session_state.w_rank = st.text_input("Opponent World Rank", value=st.session_state.w_rank)
    st.session_state.l10 = st.text_area("L10 Data", value=st.session_state.l10)

    if game_choice == "CS2":
        active_base = st.number_input("Base KPR", value=st.session_state.kpr)
    else:
        c1, c2 = st.columns(2)
        v_adr = c1.number_input("Base ADR", value=st.session_state.adr)
        v_acs = c2.number_input("Base ACS", value=st.session_state.acs)
        active_base = (v_adr / 150) + (v_acs / 300) 

    c1, c2 = st.columns(2)
    with c1: m_line, m_side = st.number_input("Line", 35.5, step=0.5), st.selectbox("Side", ["Over", "Under"])
    with c2: m_odds, m_scope = st.number_input("Odds", -115), st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

if st.button("🚀 RUN ELITE ANALYSIS"):
    vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
    stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 2.5, 2.5)
    game_mult = 26 if game_choice == "Valorant" else 24
    scope_map = {"Maps 1 & 2": 1.0, "Map 1 Only": 0.5, "Full Match": 1.3}
    
    base_proj = active_base * game_mult * scope_map[m_scope]
    final_proj = base_proj * st.session_state.h2h_val * st.session_state.rank_val * st.session_state.map_val * st.session_state.int_val
    prob = (1 - norm.cdf(m_line, loc=final_proj, scale=stdev)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=final_proj, scale=stdev) * 100
    edge = prob - ((abs(m_odds)/(abs(m_odds)+100))*100 if m_odds < 0 else (100/(m_odds+100))*100)
    hit_rate = (sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line))/len(vals)*100)

    st.session_state.results = {
        "grade": "S" if edge >= 12 else "A+" if edge >= 8 else "A" if edge >= 3 else "B", 
        "units": 2.5 if edge >= 12 else 2.0 if edge >= 8 else 1.0 if edge >= 3 else 0.5, 
        "proj": final_proj, "base": base_proj, "edge": edge, "prob": prob, 
        "m_line": m_line, "m_side": m_side, "scope": m_scope, "hit": hit_rate, "game": game_choice
    }

# --- RESULTS DISPLAY ---
if st.session_state.results:
    res = st.session_state.results
    with col_r:
        # 🗺️ PROJECTED MAPS LOGIC BOX
        st.markdown(f"""<div class="map-logic-box"><b style="color:#58a6ff;">🗺️ PROJECTED MAPS LOGIC</b><br>
            • Baseline: {res['base']:.1f} | Weighted: <b>{res['proj']:.1f} Kills</b><br>
            • Multiplier: x{(st.session_state.h2h_val*st.session_state.rank_val*st.session_state.map_val*st.session_state.int_val):.2f}</div>""", unsafe_allow_html=True)

        st.divider()
        if st.checkbox("Show Social Share Card"):
            arrow = "▲" if res['m_side'] == "Over" else "▼"
            st.markdown(f"""
            <div class="share-container">
                <div style="font-size: 14px; letter-spacing: 3px; opacity: 0.7;">{res['game'].upper()} PROP ANALYSIS</div>
                <div class="share-player">{st.session_state.p_tag.upper()}</div>
                <div style="color: #58a6ff; font-weight: bold; font-size: 18px; margin-bottom: 15px;">{st.session_state.m_context}</div>
                <div style="border-top: 1px solid #30363d; margin: 15px 0;"></div>
                <div style="display: flex; justify-content: space-around; align-items: center;">
                    <div style="text-align: left;">
                        <small style="opacity:0.7">THE PROP LINE</small><br>
                        <b style="font-size: 40px;">{res['m_line']}</b><br>
                        <small style="opacity:0.7">KILLS</small>
                    </div>
                    <div>
                        <small style="opacity:0.7">MODEL GRADE</small><br>
                        <div class="grade-box">{res['grade']}</div>
                    </div>
                </div>
                <div style="margin: 20px 0;"><div class="pill-over">{arrow} {res['m_side'].upper()}</div></div>
                <div class="suggested-play">
                    <small style="color: #FFD700; letter-spacing: 2px;">SUGGESTED PLAY</small><br>
                    <b style="font-size: 28px;">{res['units']} UNITS</b>
                </div>
                <div class="metric-grid">
                    <div style="font-size: 10px; opacity: 0.7;">PROJ<br><b class="metric-val">{res['proj']:.1f}</b></div>
                    <div style="font-size: 10px; opacity: 0.7;">EDGE<br><b class="metric-val">+{res['edge']:.1f}%</b></div>
                    <div style="font-size: 10px; opacity: 0.7;">CONF<br><b class="metric-val">{res['prob']:.0f}%</b></div>
                    <div style="font-size: 10px; opacity: 0.7;">L10 HIT<br><b class="metric-val">{res['hit']:.0f}%</b></div>
                </div>
                <div style="font-size: 10px; margin-top: 20px; letter-spacing: 2px; color: #58a6ff;">ANALYSIS BY SLEEPER D. KID</div>
            </div>
            """, unsafe_allow_html=True)