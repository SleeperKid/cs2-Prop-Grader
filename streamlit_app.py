import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os, json, re
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 🛡️ ARCHITECT'S UTILITIES
# ==========================================
def safe_float(value, default=0.0):
    """Bypasses ValueError crashes from empty cells or 'N/A' strings."""
    try:
        if pd.isna(value) or value == "N/A" or value == "":
            return default
        return float(value)
    except:
        return default

# ==========================================
# 📥 DATA & INTEL LOADERS
# ==========================================
def load_intel():
    if os.path.exists("intel_vault.json"):
        try:
            with open("intel_vault.json", "r") as f: return json.load(f)
        except: return {}
    return {}

@st.cache_data(ttl=300)
def load_vault():
    """Separates Domain Data to prevent cross-sport contamination."""
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        val_df = conn.read(spreadsheet=sheet_url, worksheet="VAL_DATA", ttl=0)
        cs_df = conn.read(spreadsheet=sheet_url, worksheet="CS2_DATA", ttl=0)
        val_df['Game'], cs_df['Game'] = 'Valorant', 'CS2'
        return pd.concat([val_df, cs_df], ignore_index=True)
    except Exception as e:
        st.error(f"Vault Connection Failure: {e}")
        return pd.DataFrame()
    
# ==========================================
# 🎨 SOVEREIGN CSS STYLING
# ==========================================
st.set_page_config(page_title="Prop Grader Elite V74", layout="wide", page_icon="🎯")
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white; border: none; padding: 18px; font-size: 20px; font-weight: bold; 
        border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.4); width: 100%;
    }
    .analyst-card { 
        padding: 40px; border-radius: 30px; text-align: center; 
        box-shadow: 0 15px 45px rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.15);
        margin-bottom: 25px; color: white;
    }
    .analyst-grade { font-size: 130px; font-weight: 900; margin: 0; line-height: 1; }
    .social-hook-box {
        background: rgba(88, 166, 255, 0.05); border: 1px dashed #58a6ff; 
        padding: 15px; border-radius: 10px; margin-top: 15px; color: #adbac7;
    }
    .share-container {
        background-color: #121212; border: 3px solid #FFD700; border-radius: 20px;
        padding: 30px; width: 420px; margin: 20px auto; color: white; text-align: center;
        box-shadow: 0 0 25px rgba(255, 215, 0, 0.4); font-family: 'Helvetica', sans-serif;
    }
    .hiro-grade { font-size: 100px; font-weight: 900; color: #FFD700; text-shadow: 0 0 20px rgba(255,215,0,0.7); line-height: 1; }
    .pill-over { background: #1b3a1e; border: 1px solid #2ea043; border-radius: 8px; padding: 8px 18px; display: inline-block; font-size: 24px; font-weight: 900; color: #3fb950; }
    .metric-grid { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 5px; border-top: 1px solid #333; padding-top: 15px; margin-top: 15px; }
    .metric-val { font-size: 16px; font-weight: bold; color: white; display: block; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 STATE MANAGEMENT
# ==========================================
st.set_page_config(page_title="Prop Grader Elite V74", layout="wide")
df = load_vault()

# Initialize keys to prevent 'KeyError' during hot-reloads
for key, val in {'m1_kpr': 0.82, 'm2_kpr': 0.82, 'p_tag': "", 'l10': "", 'm_context': ""}.items():
    if key not in st.session_state: st.session_state[key] = val

game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)

# ==========================================
# 🕵️ THE MANUAL SHIELD SELECTION
# ==========================================
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Intelligence")
    
    players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected = st.selectbox("Search Vault", ["Manual Entry"] + players)
    
    if selected != "Manual Entry":
        row = df[df['Player'] == selected].iloc[0]
        
        # 1. Update Identity & History
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Free Agent')} vs "
        
        # 2. THE SHIELD: Display Global KPR for context, but do NOT overwrite M1/M2
        if game_choice == "CS2":
            global_ref = safe_float(row.get('KPR'), 0.82)
            st.info(f"📊 Global KPR Baseline: **{global_ref}** (HLTV Rating 3.0)")
            # We reset inputs to the baseline only to clear previous player data,
            # but we don't pull M1/M2 from the sheet because they don't exist there.
            st.session_state.m1_kpr = global_ref
            st.session_state.m2_kpr = global_ref
        else:
            st.session_state.adr = safe_float(row.get('ADR'), 140.0)

    # UI INPUTS (Manual Override Enabled)
    st.text_input("Player Tag", value=st.session_state.p_tag, key="p_tag_input")
    
    if game_choice == "CS2":
        ck1, ck2 = st.columns(2)
        # Use key-based binding for better persistence in 2026 Streamlit
        m1_kpr = ck1.number_input("Map 1 KPR", value=st.session_state.m1_kpr, format="%.2f", step=0.01)
        m2_kpr = ck2.number_input("Map 2 KPR", value=st.session_state.m2_kpr, format="%.2f", step=0.01)
    else:
        adr = st.number_input("Base ADR", value=st.session_state.get('adr', 140.0))

    l10_data = st.text_area("L10 Data (CSV)", value=st.session_state.l10)

# ==========================================
# 🧠 CORE INITIALIZATION
# ==========================================
df = load_vault()
INTEL = load_intel()

# Sliders Session State initialization (MUST come before slider widgets)
for k in ['h2h_val', 'rank_val', 'map_val', 'int_val']:
    if k not in st.session_state: st.session_state[k] = 1.0

keys = ['p_tag', 'l10', 'kpr', 'm1_kpr', 'm2_kpr', 'adr', 'acs', 'm_context', 'w_rank', 'results', 'ai_advice', 'tourney_type', 'proj_maps', 'proj_agents', 'marketing_blurb', 'last_game']
for key in keys:
    if key not in st.session_state: 
        st.session_state[key] = "" if key not in ['kpr', 'm1_kpr', 'm2_kpr', 'adr', 'acs'] else 0.80

st.title("🎯 Prop Grader Elite")
game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)

# --- GAME SWITCHER SAFETY ---
if st.session_state.last_game != game_choice:
    st.session_state.proj_maps = ""
    st.session_state.proj_agents = ""
    st.session_state.last_game = game_choice
    st.rerun()

# ==========================================
# ⚙️ SIDEBAR: AI ADVISOR
# ==========================================
with st.sidebar:
    st.title("🛡️ Command Center")
    st.session_state.tourney_type = st.selectbox("Prestige", list(INTEL.get("tournaments", {}).keys()) or ["S-Tier"])

    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            client = Groq(api_key=api_key)
            # Combine Maps and Agents for Intelligence Feed
            intel_ctx = f"Maps: {st.session_state.proj_maps} | Context: {st.session_state.m_context}"
            if game_choice == "Valorant": intel_ctx += f" | Agent: {st.session_state.proj_agents}"
            
            prompt = f"""Expert Analyst (Temp 0.01). Context: {intel_ctx}. 
            Suggest 4 weights (0.85-1.15) for H2H, Tier, Map, Int. 
            STRICT RULE: Exactly 2 sentences per decision. Tone: Professional/Concise.
            Weights MUST be in brackets: [1.05]."""
            
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.01)
            st.session_state.ai_advice = res.choices[0].message.content
            
            # --- FIXED AUTO-SLIDER LOGIC ---
            weights = re.findall(r"\[(\d+(?:\.\d+)?)\]", st.session_state.ai_advice)
            if len(weights) >= 4:
                st.session_state.h2h_val = float(weights[0])
                st.session_state.rank_val = float(weights[1])
                st.session_state.map_val = float(weights[2])
                st.session_state.int_val = float(weights[3])
                st.rerun() # Refresh to move sliders

    if st.session_state.ai_advice: st.info(st.session_state.ai_advice)
    st.divider()
    # Sliders tied directly to session_state keys
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
    db_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected = st.selectbox("Database Search", ["Manual Entry"] + db_players)
    
    # --- ENHANCED COLUMN SCOUT FOR AUTO-POPULATION ---
    if selected != "Manual Entry":
        row = df[df['Player'] == selected].iloc[0]
        st.session_state.p_tag = str(row['Player'])
        st.session_state.l10 = str(row['L10']).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Team')} vs "
        
        if game_choice == "Valorant":
            # Check multiple common column names for Agents
            for col in ['Agent', 'Agents', 'Main', 'Character']:
                if col in row:
                    st.session_state.proj_agents = str(row[col])
                    break
            st.session_state.adr = float(row.get('ADR', 140))
        else:
            st.session_state.m1_kpr = float(row.get('M1_KPR', 0.82))
            st.session_state.m2_kpr = float(row.get('M2_KPR', 0.82))

    st.session_state.p_tag = st.text_input("Player Tag", value=st.session_state.p_tag)
    
    c_m1, c_m2 = st.columns(2)
    st.session_state.proj_maps = c_m1.text_input("Projected Maps", value=st.session_state.proj_maps)
    
    if game_choice == "Valorant":
        st.session_state.proj_agents = c_m2.text_input("Projected Agent", value=st.session_state.proj_agents)
        st.session_state.active_stat_type = "KILLS"
    else:
        st.session_state.active_stat_type = c_m2.selectbox("Stat Type", ["KILLS", "HEADSHOTS"])
    
    st.session_state.m_context = st.text_input("Match Context", value=st.session_state.m_context)
    st.session_state.w_rank = st.text_input("World Rank", value=st.session_state.w_rank)
    st.session_state.l10 = st.text_area("L10 Data (CSV)", value=st.session_state.l10)

    if game_choice == "CS2":
        ck1, ck2 = st.columns(2)
        st.session_state.m1_kpr = ck1.number_input("M1 KPR", value=float(st.session_state.m1_kpr), format="%.2f")
        st.session_state.m2_kpr = ck2.number_input("M2 KPR", value=float(st.session_state.m2_kpr), format="%.2f")
    else:
        st.session_state.adr = st.number_input("Base ADR", value=float(st.session_state.adr))

    st.divider()
    c1, c2 = st.columns(2)
    # Fixed explicitly typed inputs to prevent TypeErrors
    m_line = c1.number_input("Line", value=float(35.5), min_value=0.0, step=0.5)
    m_side = c1.selectbox("Side", ["Over", "Under"])
    m_odds = c2.number_input("Odds", value=int(-128))
    m_scope = c2.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

if st.button("🚀 GENERATE ELITE GRADE"):
    vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
    stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 2.5, 2.5)
    
    if game_choice == "CS2":
        if m_scope == "Map 1 Only": base_proj = st.session_state.m1_kpr * 24
        elif m_scope == "Maps 1 & 2": base_proj = (st.session_state.m1_kpr * 24) + (st.session_state.m2_kpr * 24)
        else: base_proj = ((st.session_state.m1_kpr + st.session_state.m2_kpr) / 2) * 24 * 2.6
    else:
        # 150 ADR-to-Kill Conversion for Val
        scope_mult = {"Map 1 Only": 1.0, "Maps 1 & 2": 2.0, "Full Match": 2.6}
        base_proj = (st.session_state.adr / 150) * 26 * scope_mult[m_scope]
    
    final_proj = base_proj * st.session_state.h2h_val * st.session_state.rank_val * st.session_state.map_val * st.session_state.int_val
    prob = (1 - norm.cdf(m_line, loc=final_proj, scale=stdev)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=final_proj, scale=stdev) * 100
    edge = prob - ((abs(m_odds)/(abs(m_odds)+100))*100 if m_odds < 0 else (100/(m_odds+100))*100)
    
    grade_data = {"S": (12, "ELITE"), "A+": (8, "STRONG"), "A": (3, "VALUE"), "B": (0, "MARGINAL")}
    g, u, lbl, grad = ("X", 0.0, "PASS", "linear-gradient(135deg, #4b0000 0%, #000000 100%)")
    for key, (val, name) in grade_data.items():
        if edge >= val: 
            g = key
            u = (2.5 if key=="S" else 2.0 if key=="A+" else 1.0 if key=="A" else 0.5)
            lbl = name
            grad = ("linear-gradient(135deg, #FFD700 0%, #8B6508 100%)" if key=="S" else "linear-gradient(135deg, #00FF00 0%, #004d00 100%)" if key=="A+" else "linear-gradient(135deg, #ADFF2F 0%, #228B22 100%)" if key=="A" else "linear-gradient(135deg, #2c3e50 0%, #000000 100%)")
            break

    # --- SOCIAL HOOK: HIGH TEMP FOR CREATIVITY ---
    api_key = st.secrets.get("GROQ_API_KEY")
    if api_key and g != "X":
        client = Groq(api_key=api_key)
        m_prompt = f"Meaningful betting logic (MAX 240 chars). No emojis. {st.session_state.p_tag} {m_side} {m_line}. Proj: {final_proj:.1f} | Edge: {edge:.1f}%. Why is this bet good?"
        st.session_state.marketing_blurb = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":m_prompt}], temperature=0.85).choices[0].message.content

    st.session_state.results = {"grade": g, "units": u, "proj": final_proj, "base": base_proj, "edge": edge, "prob": prob, "grad": grad, "label": lbl, "line": m_line, "side": m_side, "hit": (sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line))/len(vals)*100), "stat": st.session_state.active_stat_type}

# --- RESULTS DISPLAY ---
if st.session_state.results:
    res = st.session_state.results
    with col_r:
        st.markdown(f"""<div class="analyst-card" style="background: {res['grad']};">
            <div style="font-size: 20px; font-weight: bold; opacity: 0.8;">{res['label']}</div>
            <div style="font-size: 32px; font-weight: 900;">{st.session_state.p_tag.upper()} {res['side'].upper()} {res['line']}</div>
            <h1 class="analyst-grade">{res['grade']}</h1>
            <div style="font-size: 26px; font-weight: bold;">{res['units']} UNIT PLAY</div>
        </div>""", unsafe_allow_html=True)

        if st.session_state.marketing_blurb:
            st.markdown(f"""<div class="social-hook-box"><b>📝 Analyst Logic:</b><br>{st.session_state.marketing_blurb}</div>""", unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Projected", f"{res['proj']:.1f}"); m2.metric("L10 Hit", f"{res['hit']:.0f}%"); m3.metric("Edge", f"{res['edge']:.1f}%"); m4.metric("Conf", f"{res['prob']:.0f}%")
        st.progress(res['prob'] / 100)

        st.divider()
        if st.checkbox("Show Social Share Card"):
            p_class = "pill-over" if res['grade'] != "X" else "pill-pass"
            arrow = "▲" if res['side'] == 'Over' else '▼'
            st.markdown(f"""<div class="share-container">
                <div style="font-size:12px; opacity:0.6; margin-bottom:5px;">{game_choice.upper()} PROP ANALYSIS</div>
                <div class="share-player">{st.session_state.p_tag.upper()}</div>
                <div style="color: #58a6ff; font-weight: bold; font-size: 18px; margin-bottom: 15px;">{st.session_state.m_context}</div>
                <div style="border-top:1px solid #333; margin:15px 0;"></div>
                <div style="display:flex; justify-content:space-around; align-items:center;">
                    <div style="text-align:left;"><span style="font-size:10px; opacity:0.6;">LINE</span><br><b style="font-size:45px; line-height:1;">{res['line']}</b><br><span style="font-size:12px; font-weight:bold; color:#adbac7;">{res['stat']}</span></div>
                    <div><span style="font-size:10px; opacity:0.6;">GRADE</span><br><div class="hiro-grade">{res['grade']}</div></div>
                </div>
                <div style="margin:20px 0;"><div class="{p_class}">{arrow} {res['side'].upper() if res['grade'] != 'X' else 'PASS'}</div></div>
                <div style="background:#1c1c1c; border:1px solid #FFD700; border-radius:15px; padding:15px; margin-bottom:20px;"><span style="color:#FFD700; font-size:11px; font-weight:bold;">SUGGESTED PLAY</span><br><b style="font-size:28px;">{res['units']} UNITS</b></div>
                <div class="metric-grid">
                    <div><span class="metric-label">PROJ</span><b class="metric-val">{res['proj']:.1f}</b></div>
                    <div><span class="metric-label">EDGE</span><b class="metric-val">+{res['edge']:.1f}%</b></div>
                    <div><span class="metric-label">CONF</span><b class="metric-val">{res['prob']:.0f}%</b></div>
                    <div><span class="metric-label">L10 HIT</span><b class="metric-val">{res['hit']:.0f}%</b></div>
                </div>
                <div style="font-size:10px; letter-spacing:2px; color:#58a6ff; margin-top:20px; font-weight:bold;">ANALYSIS BY SLEEPER D. KID</div>
            </div>""", unsafe_allow_html=True)