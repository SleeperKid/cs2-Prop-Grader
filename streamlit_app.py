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

def load_intel():
    if os.path.exists("intel_vault.json"):
        with open("intel_vault.json", "r") as f: return json.load(f)
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
# 🎨 UI & SOVEREIGN STYLING
# ==========================================
st.set_page_config(page_title="Prop Grader Elite V142", layout="wide", page_icon="🎯")
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .analyst-card { 
        padding: 40px; border-radius: 30px; text-align: center; 
        box-shadow: 0 15px 45px rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.15);
        margin-bottom: 25px; color: white;
    }
    .analyst-grade { font-size: 130px; font-weight: 900; margin: 0; line-height: 1; }
    .share-container {
        background-color: #121212; border: 3px solid #FFD700; border-radius: 20px;
        padding: 30px; width: 450px; margin: 20px auto; color: white; text-align: center;
        font-family: 'Courier New', monospace;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 SOVEREIGN STATE MANAGEMENT
# ==========================================
slider_keys = ['h2h_val', 'tier_val', 'map_val', 'int_val', 'lan_val', 'econ_val']
for k in slider_keys:
    if k not in st.session_state: st.session_state[k] = 1.0

if 'ai_advice' not in st.session_state: st.session_state.ai_advice = ""
if 'results' not in st.session_state: st.session_state.results = None

# ==========================================
# ⚙️ SIDEBAR: COMMAND CENTER
# ==========================================
df = load_vault()
IV = load_intel()

st.title("🎯 Prop Grader Elite")
game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)
game_key = "VAL" if "Val" in game_choice else "CS2"
foundation = IV.get(game_key, {})

with st.sidebar:
    st.header("🛡️ Strategic Weights")
    
    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            client = Groq(api_key=api_key)
            p_context = st.session_state.get('p_tag_input', 'Selected Player')
            m_context = st.session_state.get('m_context_input', '')
            
            prompt = f"""
            Analyze {game_choice} prop. 
            INTEL FOUNDATION: {foundation}
            MATCH: {p_context} in {m_context}.
            
            Scan the foundation for the team archetypes in the context.
            Suggest 6 weights (0.85-1.15) for H2H, Tier, Map, Intensity, LAN, Economy.
            Format EXACTLY like this: [1.05], [0.95], [1.10], [1.00], [1.02], [0.98].
            """
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.01)
            st.session_state.ai_advice = res.choices[0].message.content
            
            weights = re.findall(r"\[(\d+(?:\.\d+)?)\]", st.session_state.ai_advice)
            if len(weights) >= 6:
                for idx, k in enumerate(slider_keys):
                    st.session_state[k] = float(weights[idx])
                st.rerun()

    if st.session_state.ai_advice: st.info(st.session_state.ai_advice)
    
    st.slider("H2H Advantage", 0.80, 1.20, key="h2h_val")
    st.slider("Opponent Tier", 0.80, 1.20, key="tier_val")
    st.slider("Map Fit/Veto", 0.80, 1.20, key="map_val")
    st.slider("Match Intensity", 0.70, 1.10, key="int_val")
    st.slider("LAN/Rio Crowd", 0.90, 1.10, key="lan_val")
    st.slider("Economy (MR12)", 0.85, 1.15, key="econ_val")

# ==========================================
# 🕵️ VAULT PROFILE ANALYZER
# ==========================================
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Intelligence")
    active_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected = st.selectbox("Search Vault", ["Manual Entry"] + active_players)
    
    p_tag_val, m_context_val, l10_val = "Player", "", ""
    kpr_baseline = 0.82 if game_choice == "CS2" else 135.0
    
    if selected != "Manual Entry":
        row = df[df['Player'] == selected].iloc[0]
        p_tag_val, l10_val = str(row['Player']), str(row['L10'])
        m_context_val = f"{row.get('Team', 'Team')} vs "
        kpr_baseline = safe_float(row.get('KPR' if game_choice == "CS2" else 'ADR'), kpr_baseline)

    p_tag = st.text_input("Player Tag", value=p_tag_val, key="p_tag_input")
    m_context = st.text_input("Match Context", value=m_context_val, key="m_context_input")
    opp_rank = st.number_input("Opponent Rank", value=10, step=1)
    
    if game_choice == "CS2":
        ck1, ck2 = st.columns(2)
        m1_kpr = ck1.number_input("M1 KPR", value=float(kpr_baseline), format="%.2f")
        m2_kpr = ck2.number_input("M2 KPR", value=float(kpr_baseline), format="%.2f")
    else:
        base_stat = st.number_input("Projected ADR", value=float(kpr_baseline))

    l10_data = st.text_area("L10 Match History", value=l10_val)
    m_line = st.number_input("Line", value=35.5, step=0.5)
    m_side = st.selectbox("Side", ["Over", "Under"])
    m_odds = st.number_input("Odds", value=-120)

if st.button("🚀 GENERATE V142 ELITE GRADE"):
    l10_list = parse_l10(l10_data)
    stdev = max(np.std(l10_list, ddof=1) if len(l10_list) > 1 else 3.5, 3.5)
    base_proj = (m1_kpr * 24) + (m2_kpr * 24) if game_choice == "CS2" else (base_stat / 150) * 26 * 2.0 
    
    streak_bonus = 1.0
    streak_hits = sum(1 for x in l10_list[:5] if x > m_line) if len(l10_list) >= 5 else 0
    if streak_hits >= 4: streak_bonus = 1.05
    elif streak_hits <= 1 and len(l10_list) >= 5: streak_bonus = 0.95
    
    final_proj = base_proj * st.session_state.h2h_val * st.session_state.tier_val * \
                 st.session_state.map_val * st.session_state.int_val * \
                 st.session_state.lan_val * st.session_state.econ_val * streak_bonus
    
    prob = (1 - norm.cdf(m_line, loc=final_proj, scale=stdev)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=final_proj, scale=stdev) * 100
    implied = (abs(m_odds)/(abs(m_odds)+100))*100 if m_odds < 0 else (100/(m_odds+100))*100
    edge = prob - implied
    
    st.session_state.results = {
        "player": p_tag, "context": m_context, "line": m_line, "side": m_side,
        "grade": "S" if edge >= 12 else "A+" if edge >= 8 else "A" if edge >= 3 else "B",
        "units": 2.5 if edge >= 12 else 2.0 if edge >= 8 else 1.0,
        "proj": final_proj, "prob": prob, "edge": edge, "hits": streak_hits,
        "color": "linear-gradient(135deg, #FFD700 0%, #8B6508 100%)" if edge >= 12 else "linear-gradient(135deg, #00FF00 0%, #004d00 100%)"
    }

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
        
        if st.checkbox("Generate Social Media Card"):
            st.markdown(f"""
            <div class="share-container">
                <div style="color: #FFD700; font-weight: bold;">🎯 PROP GRADER ELITE</div>
                <hr style="border: 1px solid #333;">
                <div style="font-size: 24px;">{res['player']}</div>
                <div style="font-size: 16px; opacity: 0.7;">{res['context']}</div>
                <div style="font-size: 40px; margin: 15px 0;">{res['line']} {res['side'].upper()}</div>
                <div style="font-size: 80px; font-weight: 900; color: #FFD700;">{res['grade']}</div>
                <div style="font-size: 20px;">{res['units']} UNITS | {res['prob']:.1f}% PROB</div>
            </div>
            """, unsafe_allow_html=True)