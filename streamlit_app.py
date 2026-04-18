import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from groq import Groq 
from streamlit_gsheets import GSheetsConnection

# --- ⚙️ UTILITIES & DATA ---
def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val == "N/A" or val == "": return default
        return float(val)
    except: return default

@st.cache_data(ttl=300)
def load_vault():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        val_df = conn.read(spreadsheet=sheet_url, worksheet="VAL_DATA", ttl=0)
        cs_df = conn.read(spreadsheet=sheet_url, worksheet="CS2_DATA", ttl=0)
        val_df['Game'], cs_df['Game'] = 'Valorant', 'CS2'
        return pd.concat([val_df, cs_df], ignore_index=True).replace("N/A", np.nan)
    except: return pd.DataFrame()

def load_intel_vault():
    if os.path.exists("intel_vault.json"):
        with open("intel_vault.json", "r") as f: return json.load(f)
    return {}

# --- 🧠 GROQ AI ADVISOR (V117: EXPLICIT NUMERICAL OUTPUT) ---
def run_ai_advisor():
    """Llama 3.3 Scout: Forces numerical slider values into the report text."""
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    intel = load_intel_vault()
    
    context = st.session_state.m_context
    maps = st.session_state.p_maps
    game = st.session_state.game_choice
    is_hs = st.session_state.get('prop_type_select') == "Headshot Kills"
    
    sys_prompt = f"""
    You are 'Sleeper D. Kid' AI Scout. Recommend sliders (0.80-1.20) for H2H, Tier, and Map.
    
    OUTPUT RULES:
    1. Your 'report' field MUST explicitly state the numerical value for each slider.
    2. Format example: "H2H (1.05): Reason. Tier (0.90): Reason. Map (1.10): Reason."
    3. Use Vault Archetypes or World Rank only. Do NOT invent history.
    4. Only mention Headshots if HS is True ({is_hs}).
    
    VAULT: {json.dumps(intel.get(game, {}))}
    
    RETURN JSON: {{ "h2h": float, "tier": float, "map": float, "report": "str" }}
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys_prompt},
                      {"role": "user", "content": f"Context: {context} | Map: {maps}"}],
            response_format={"type": "json_object"}
        )
        res = json.loads(completion.choices[0].message.content)
        
        # Hard-Sync to State Sliders
        st.session_state.w_h2h = res.get("h2h", 1.0)
        st.session_state.w_tier = res.get("tier", 1.0)
        st.session_state.w_map = res.get("map", 1.0)
        st.session_state.ai_note = res.get("report", "Analysis finished.")
        st.rerun()
    except Exception as e:
        st.error(f"Advisor Error: {e}")

def sync_player_data():
    """🟢 STATE-SANCTUARY: Only overwrites on FRESH player selection."""
    if st.session_state.player_selector != "Manual Entry":
        if st.session_state.player_selector != st.session_state.get('last_player_locked'):
            row = df[df['Player'] == st.session_state.player_selector].iloc[0]
            base = safe_float(row.get('KPR'), 0.82)
            
            st.session_state.p_tag = str(row.get('Player', ''))
            st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
            st.session_state.m_context = f"{row.get('Team', 'FA')} vs "
            st.session_state.m1_kpr_input = base
            st.session_state.m2_kpr_input = base
            st.session_state.hs_pct_input = safe_float(row.get('HS%'), 45.0)
            st.session_state.last_player_locked = st.session_state.player_selector

# --- 🎨 UI BOOT ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

if 'initialized' not in st.session_state:
    st.session_state.update({
        'p_tag': "", 'm_context': "", 'p_maps': "", 'opp_rank_input': 15, 
        'l10': "", 'm1_kpr_input': 0.82, 'm2_kpr_input': 0.82, 'hs_pct_input': 45.0,
        'w_h2h': 1.0, 'w_tier': 1.0, 'w_map': 1.0, 'w_int': 1.0, 
        'ai_note': "", 'results': None, 'last_player_locked': None, 'initialized': True
    })

st.markdown("""
<style>
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
        color: black !important; font-weight: 900 !important; font-size: 22px !important;
        border: none; border-radius: 15px; height: 60px; margin-top: 20px;
    }
    .metric-card { background: #1a1c23; border: 1px solid #333; border-radius: 12px; padding: 15px; text-align: center; }
    .stat-lbl { color: #888; font-size: 10px; font-weight: bold; text-transform: uppercase; }
    .stat-val { font-size: 24px; font-weight: 900; margin-top: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 🕵️ MAIN OPERATIONS ---
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.radio("Game", ["CS2", "Valorant"], key="game_choice", horizontal=True)
    st.selectbox("Search", ["Manual Entry"] + (df[df['Game'] == st.session_state.game_choice]['Player'].tolist() if not df.empty else []), key="player_selector", on_change=sync_player_data)
    
    # 🟢 IRONCLAD INPUTS: Linked solely to keys, NO 'value=' parameter.
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context") 
    st.text_input("Projected Maps", key="p_maps")
    st.number_input("Opponent Rank", key="opp_rank_input")
    
    if st.session_state.game_choice == "CS2":
        st.selectbox("Prop Type", ["Kills", "Headshot Kills"], key="prop_type_select")
        c1, c2, c3 = st.columns(3)
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
        c3.number_input("HS%", key="hs_pct_input", format="%.1f")
    else:
        st.number_input("Base ADR", key="adr_input", value=140.0) # ADR is static, can use value
        st.selectbox("Role", ["Duelist", "Support"], key="val_role_select")
    
    st.text_area("L10 Data (CSV)", key="l10")
    l_c1, l_c2 = st.columns(2)
    m_line = l_c1.number_input("Prop Line", value=28.5, step=0.5)
    m_side = l_c2.selectbox("Side", ["Over", "Under"], key="side_select")

    if st.button("🚀 EXECUTE GRADE", use_container_width=True):
        try:
            v_list = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
            l10_avg = sum(v_list) / len(v_list)
            
            # 📐 QUANT LOCK MATH
            raw_weights = st.session_state.w_h2h * st.session_state.w_tier * st.session_state.w_map * st.session_state.w_int
            capped_weights = min(1.30, max(0.70, raw_weights))
            
            proj = l10_avg * capped_weights
            if st.session_state.game_choice == "CS2" and st.session_state.get('prop_type_select') == "Headshot Kills":
                proj *= (st.session_state.hs_pct_input / 100)
            elif st.session_state.game_choice == "Valorant":
                proj *= (1.12 if st.session_state.val_role_select == "Duelist" else 0.92)
            
            # 🟢 SYMMETRIC EDGE
            raw_edge = ((proj - m_line) / m_line * 100) if m_side == "Over" else ((m_line - proj) / m_line * 100)
            hit = (sum(1 for v in v_list if (v > m_line if m_side == "Over" else v < m_line)) / len(v_list)) * 100
            
            # Grade Selection
            abs_edge = abs(raw_edge)
            grade = "B"
            if raw_edge > 18 and hit >= 70: grade = "S"
            elif abs_edge > 22: grade = "A+"
            elif hit >= 80 and abs_edge > 5: grade = "A+"
            elif abs_edge > 10 and hit >= 50: grade = "A"
            
            conf = min(99, max(40, (80 + (abs_edge / 1.5) if hit > 60 else 70 + (abs_edge / 2))))
            st.session_state.results = {"grade": grade, "proj": proj, "edge": raw_edge, "line": m_line, "side": m_side, "hit": hit, "conf": conf, "units": 2.5 if grade == "S" else 1.0}
        except: st.error("L10 Calculation Error.")

# --- 💎 OUTPUT SECTION ---
with col_r:
    with st.sidebar:
        if st.button("🤖 CONSULT GROQ SCOUT", use_container_width=True): run_ai_advisor()
        if st.session_state.ai_note: st.info(st.session_state.ai_note)
        st.slider("H2H Advantage", 0.8, 1.2, key="w_h2h", step=0.05)
        st.slider("Opponent Tier", 0.8, 1.2, key="w_tier", step=0.05)
        st.slider("Map Fit", 0.8, 1.2, key="w_map", step=0.05)
        st.slider("Pressure/Form", 0.8, 1.2, key="w_int", step=0.05)

    if st.session_state.results:
        res = st.session_state.results
        
        # 🟢 THE "CONSIDER THE UNDER" ALERT
        # If the model strongly disagrees with your chosen side, fire a warning.
        if res['edge'] < -15:
            st.warning(f"⚠️ HIGH VALUE OPPOSITE DETECTED! Model projects {res['proj']:.1f} vs Line {res['line']}. Consider taking the {'UNDER' if res['side'] == 'Over' else 'OVER'}.", icon="🚨")

        # 🟢 Internal Board
        st.markdown(f"""
        <div style="background:#1a1c23; border: 1px solid #333; border-radius:15px; padding:25px; text-align:center; margin-bottom:15px;">
            <div style="color:#888; font-size:12px; font-weight:bold;">MODEL GRADE</div>
            <div style="font-size: 110px; font-weight: 900; color: #FFD700; line-height:1; white-space: nowrap;">{res['grade']}</div>
            <div style="color:{'#00FF00' if res['side'] == 'Over' else '#FF4B4B'}; font-weight:bold; font-size:24px;">{res['side'].upper()} {res['line']}</div>
        </div>""", unsafe_allow_html=True)
        
        g1, g2, g3, g4 = st.columns(4)
        g1.markdown(f"""<div class="metric-card"><div class="stat-lbl">PROJ</div><div class="stat-val">{res['proj']:.1f}</div></div>""", unsafe_allow_html=True)
        g2.markdown(f"""<div class="metric-card"><div class="stat-lbl">EDGE %</div><div class="stat-val" style="color:#FFD700;">{res['edge']:+.1f}%</div></div>""", unsafe_allow_html=True)
        g3.markdown(f"""<div class="metric-card"><div class="stat-lbl">HIT %</div><div class="stat-val" style="color:#00FF00;">{res['hit']:.0f}%</div></div>""", unsafe_allow_html=True)
        g4.markdown(f"""<div class="metric-card"><div class="stat-lbl">CONF</div><div class="stat-val">{res['conf']:.0f}%</div></div>""", unsafe_allow_html=True)

        if st.checkbox("💎 Generate Social Media Share Card"):
            arrow = "▲" if res['side'] == "Over" else "▼"
            # 🛡️ THE CSS SHIELD (STRICT HTML)
            st.markdown(f"""
<div style="background-color:#121212; border:2px solid #FFD700; border-radius:20px; padding:35px; width:450px; margin:auto; color:white; text-align:center; font-family:sans-serif;">
<div style="font-size:48px; font-weight:900; margin:0; line-height:1;">{st.session_state.p_tag.upper()}</div>
<div style="color:#4A90E2; font-size:18px; font-weight:bold; margin:10px 0 20px 0;">{st.session_state.m_context.upper()}</div>
<div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px;">
<div style="text-align:left; flex:1;">
<div style="color:#888; font-size:11px; font-weight:bold;">PROP LINE</div>
<div style="font-size:75px; font-weight:900; line-height:1;">{res['line']}</div>
<span style="color:{'#00FF00' if res['side'] == 'Over' else '#FF0000'}; border:1px solid {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; padding:4px 10px; border-radius:8px; font-weight:900; font-size:14px;">{arrow} {res['side'].upper()}</span>
</div>
<div style="text-align:center; min-width:160px;">
<div style="color:#888; font-size:11px; font-weight:bold;">GRADE</div>
<div style="font-size:100px; font-weight:900; color:#FFD700; text-shadow:0 0 20px rgba(255,215,0,0.5); line-height:0.9; white-space:nowrap;">{res['grade']}</div>
</div>
</div>
<div style="background:rgba(255,215,0,0.1); border:1px solid #FFD700; border-radius:15px; padding:15px; margin-bottom:25px;">
<div style="color:#FFD700; font-size:12px; font-weight:bold;">CONFIDENCE: {res['conf']:.0f}% | {res['units']} UNITS</div>
</div>
<div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; border-top:1px solid #333; padding-top:20px;">
<div><div style="font-size:10px; color:#666; font-weight:bold;">PROJ {"KILLS" if st.session_state.game_choice == "CS2" else "HS"}</div><div style="font-size:22px; font-weight:900;">{res['proj']:.1f}</div></div>
<div><div style="font-size:10px; color:#666; font-weight:bold;">MODEL EDGE</div><div style="font-size:22px; font-weight:900;">{res['edge']:+.1f}%</div></div>
<div><div style="font-size:10px; color:#666; font-weight:bold;">L10 HIT</div><div style="font-size:22px; font-weight:900;">{res['hit']:.0f}%</div></div>
</div>
<div style="color: #4A90E2; letter-spacing: 4px; font-size: 11px; margin-top: 30px; font-weight: bold;">ANALYSIS BY SLEEPER D. KID</div>
</div>
""", unsafe_allow_html=True)