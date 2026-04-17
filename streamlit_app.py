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
    /* HIRO SHARE CARD RESTORED */
    .share-container {
        background-color: #121212; border: 3px solid #FFD700; border-radius: 20px;
        padding: 30px; width: 420px; margin: 20px auto; color: white; text-align: center;
        box-shadow: 0 0 25px rgba(255, 215, 0, 0.4); font-family: 'Helvetica', sans-serif;
    }
    .share-player { font-size: 55px; font-weight: 900; margin: 5px 0; letter-spacing: 2px; text-transform: uppercase; }
    .hiro-grade { font-size: 100px; font-weight: 900; color: #FFD700; text-shadow: 0 0 20px rgba(255,215,0,0.7); line-height: 1; }
    .pill-over { background: #1b3a1e; border: 1px solid #2ea043; border-radius: 8px; padding: 8px 18px; display: inline-block; font-size: 24px; font-weight: 900; color: #3fb950; }
    .pill-pass { background: #3a1b1b; border: 1px solid #a02e2e; border-radius: 8px; padding: 8px 18px; display: inline-block; font-size: 24px; font-weight: 900; color: #b93f3f; }
    .metric-grid { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 5px; border-top: 1px solid #333; padding-top: 15px; margin-top: 15px; }
    .metric-val { font-size: 16px; font-weight: bold; color: white; display: block; }
    .metric-label { font-size: 9px; opacity: 0.6; text-transform: uppercase; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 CORE INITIALIZATION
# ==========================================
df = load_vault()
INTEL = load_intel()

for k in ['h2h_val', 'rank_val', 'map_val', 'int_val']:
    if k not in st.session_state: st.session_state[k] = 1.0

keys = ['p_tag', 'l10', 'kpr', 'm1_kpr', 'm2_kpr', 'adr', 'acs', 'm_context', 'w_rank', 'results', 'ai_advice', 'tourney_type', 'proj_maps', 'marketing_blurb']
for key in keys:
    if key not in st.session_state: 
        st.session_state[key] = "" if key not in ['kpr', 'm1_kpr', 'm2_kpr', 'adr', 'acs'] else 0.80

game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)
stat_options = ["KILLS", "HEADSHOTS"] if game_choice == "CS2" else ["KILLS"]

# ==========================================
# ⚙️ SIDEBAR: AI ADVISOR (CONCISE MODE)
# ==========================================
with st.sidebar:
    st.title("🛡️ Command Center")
    st.session_state.tourney_type = st.selectbox("Prestige", list(INTEL.get("tournaments", {}).keys()) or ["S-Tier"])

    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            client = Groq(api_key=api_key)
            found_maps = [f"{k}: {v}" for k, v in INTEL.get("maps", {}).items() if k.lower() in st.session_state.proj_maps.lower()]
            found_styles = [f"{k}: {v}" for k, v in INTEL.get("team_styles", {}).items() if k.lower() in st.session_state.m_context.lower()]
            
            # --- CONCISE 2-SENTENCE PROMPT ---
            prompt = f"""Expert Analyst. Context: {st.session_state.m_context}. Maps: {found_maps}. Intel: {found_styles}.
            Suggest 4 weights (0.85-1.15) for H2H, Tier, Map, Int. 
            STRICT RULE: MAX 2 sentences per decision. Brackets: [1.05]."""
            
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.01)
            st.session_state.ai_advice = res.choices[0].message.content
            
            weights = re.findall(r"\[(\d+(?:\.\d+)?)\]", st.session_state.ai_advice)
            if len(weights) >= 4:
                st.session_state.h2h_val, st.session_state.rank_val, st.session_state.map_val, st.session_state.int_val = map(float, weights[:4])
                st.rerun()

    if st.session_state.ai_advice: st.info(st.session_state.ai_advice)
    st.divider()
    st.slider("H2H Advantage", 0.80, 1.20, key="h2h_val")
    st.slider("Opponent Tier", 0.80, 1.20, key="rank_val")
    st.slider("Map Fit", 0.80, 1.20, key="map_val")
    st.slider("Match Intensity", 0.70, 1.10, key="int_val")

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Intelligence")
    db_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected = st.selectbox("Database Search", ["Manual Entry"] + db_players)
    if selected != "Manual Entry":
        row = df[df['Player'] == selected].iloc[0]
        st.session_state.p_tag, st.session_state.l10 = row['Player'], str(row['L10']).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Team')} vs "
        if game_choice == "CS2": st.session_state.m1_kpr, st.session_state.m2_kpr = float(row.get('M1_KPR', 0.82)), float(row.get('M2_KPR', 0.82))
        else: st.session_state.adr = float(row.get('ADR', 140))

    st.session_state.p_tag = st.text_input("Player Tag", value=st.session_state.p_tag)
    c_m1, c_m2 = st.columns(2)
    st.session_state.proj_maps = c_m1.text_input("Projected Maps", value=st.session_state.proj_maps)
    st.session_state.active_stat_type = c_m2.selectbox("Stat Type", stat_options)
    st.session_state.m_context = st.text_input("Context", value=st.session_state.m_context)
    st.session_state.w_rank = st.text_input("World Rank", value=st.session_state.w_rank)
    st.session_state.l10 = st.text_area("L10 Data", value=st.session_state.l10)

    if game_choice == "CS2":
        ck1, ck2 = st.columns(2)
        st.session_state.m1_kpr = ck1.number_input("M1 KPR", value=float(st.session_state.m1_kpr), format="%.2f")
        st.session_state.m2_kpr = ck2.number_input("M2 KPR", value=float(st.session_state.m2_kpr), format="%.2f")
    else: st.session_state.adr = st.number_input("ADR", value=float(st.session_state.adr))

    st.divider()
    c1, c2 = st.columns(2)
    with c1: m_line, m_side = st.number_input("Line", value=float(35.5), min_value=0.0, step=0.5), st.selectbox("Side", ["Over", "Under"])
    with c2: m_odds, m_scope = st.number_input("Odds", value=int(-128)), st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

if st.button("🚀 GENERATE ELITE GRADE"):
    vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
    stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 2.5, 2.5)
    
    if game_choice == "CS2":
        if m_scope == "Map 1 Only": base_proj = st.session_state.m1_kpr * 24
        elif m_scope == "Maps 1 & 2": base_proj = (st.session_state.m1_kpr * 24) + (st.session_state.m2_kpr * 24)
        else: base_proj = ((st.session_state.m1_kpr + st.session_state.m2_kpr) / 2) * 24 * 2.6
    else:
        scope_mult = {"Map 1 Only": 1.0, "Maps 1 & 2": 2.0, "Full Match": 2.6}
        base_proj = (st.session_state.adr / 150) * 26 * scope_mult[m_scope]
    
    final_proj = base_proj * st.session_state.h2h_val * st.session_state.rank_val * st.session_state.map_val * st.session_state.int_val
    prob = (1 - norm.cdf(m_line, loc=final_proj, scale=stdev)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=final_proj, scale=stdev) * 100
    edge = prob - ((abs(m_odds)/(abs(m_odds)+100))*100 if m_odds < 0 else (100/(m_odds+100))*100)
    
    if edge >= 12: g, u, lbl, grad = "S", 2.5, "ELITE VALUE", "linear-gradient(135deg, #FFD700 0%, #8B6508 100%)"
    elif edge >= 8: g, u, lbl, grad = "A+", 2.0, "STRONG PLAY", "linear-gradient(135deg, #00FF00 0%, #004d00 100%)"
    elif edge >= 3: g, u, lbl, grad = "A", 1.0, "VALUE PLAY", "linear-gradient(135deg, #ADFF2F 0%, #228B22 100%)"
    elif edge >= 0: g, u, lbl, grad = "B", 0.5, "MARGINAL", "linear-gradient(135deg, #2c3e50 0%, #000000 100%)"
    else: g, u, lbl, grad = "X", 0.0, "PASS / TRAP", "linear-gradient(135deg, #4b0000 0%, #000000 100%)"

    # --- ENHANCED SOCIAL HOOK ---
    api_key = st.secrets.get("GROQ_API_KEY")
    if api_key and g != "X":
        client = Groq(api_key=api_key)
        m_prompt = f"Meaningful betting analysis (MAX 240 chars). No emojis. Focus on the logical 'why'. Bet: {st.session_state.p_tag} {m_side} {m_line} {st.session_state.active_stat_type}. Proj: {final_proj:.1f} | Edge: {edge:.1f}%."
        m_res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":m_prompt}], temperature=0.85)
        st.session_state.marketing_blurb = m_res.choices[0].message.content

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
                <div style="font-size:12px; letter-spacing:3px; opacity:0.6; margin-bottom:5px;">{game_choice.upper()} PROP ANALYSIS</div>
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