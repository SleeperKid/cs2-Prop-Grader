import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from groq import Groq # 🟢 RESTORED GROQ
from streamlit_gsheets import GSheetsConnection

# --- ⚙️ CORE UTILITIES ---
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

# --- 🧠 GROQ AI ADVISOR: THE SCOUT ---
def run_ai_advisor():
    """Uses Groq to analyze Intel Vault and context for slider suggestions."""
    client = Groq(api_key=st.secrets["GROQ_API_KEY"]) # 🟢 PULLS FROM SECRETS
    intel = load_intel_vault()
    
    # 🟢 CONTEXT GATHERING
    context = st.session_state.m_context
    maps = st.session_state.p_maps
    game = st.session_state.game_choice
    is_hs = st.session_state.get('prop_type_select') == "Headshot Kills"
    
    # SYSTEM PROMPT: Explaining the Slider Mechanics
    sys_prompt = f"""
    You are the 'Sleeper D. Kid' AI Scout for {game}. 
    Analyze the Match Context and Maps against the Intel Vault data provided.
    
    SLIDER MECHANICS (Adjust between 0.80 and 1.20):
    - H2H: Adjust for individual matchup skill gap or team playstyle.
    - Tier: 0.90 for S-Tier discipline, 1.15 for B-Tier chaos.
    - Map: Adjust for map-specific fragging volume.
    
    CRITICAL: If 'Headshot Kills' is selected ({is_hs}), focus heavily on map verticality and HS% notes in the vault.
    
    INTEL VAULT: {json.dumps(intel.get(game, {}))}
    
    RETURN JSON ONLY:
    {{ "h2h": value, "tier": value, "map": value, "report": "Scouting note here" }}
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Context: {context} | Maps: {maps}"}
            ],
            response_format={"type": "json_object"}
        )
        
        res = json.loads(completion.choices[0].message.content)
        
        # SYNC TO SLIDERS
        st.session_state.w_h2h = res.get("h2h", 1.0)
        st.session_state.w_tier = res.get("tier", 1.0)
        st.session_state.w_map = res.get("map", 1.0)
        st.session_state.ai_note = res.get("report", "")
        st.rerun()
    except Exception as e:
        st.error(f"Groq Connection Failed: {e}")

def sync_player_data():
    """Callback for fresh player selection."""
    if st.session_state.player_selector != "Manual Entry":
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        base = safe_float(row.get('KPR'), 0.82)
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'FA')} vs "
        st.session_state.m1_kpr_input = base
        st.session_state.m2_kpr_input = base
        st.session_state.hs_pct_input = safe_float(row.get('HS%'), 45.0)

# --- 🎨 UI INITIALIZATION ---
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

if 'initialized' not in st.session_state:
    st.session_state.update({
        'p_tag': "", 'm_context': "", 'p_maps': "", 'opp_rank_input': 15, 'l10': "", 
        'm1_kpr_input': 0.82, 'm2_kpr_input': 0.82, 'hs_pct_input': 45.0,
        'w_h2h': 1.0, 'w_tier': 1.0, 'w_map': 1.0, 'w_int': 1.0, 
        'ai_note': "", 'results': None, 'initialized': True
    })

# --- 🛰️ SIDEBAR ---
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    if st.button("🤖 CONSULT GROQ AI", use_container_width=True): run_ai_advisor()
    
    if st.session_state.ai_note:
        st.info(st.session_state.ai_note)
    
    st.divider()
    st.slider("H2H Advantage", 0.8, 1.2, key="w_h2h", step=0.05)
    st.slider("Opponent Tier", 0.8, 1.2, key="w_tier", step=0.05)
    st.slider("Map Fit", 0.8, 1.2, key="w_map", step=0.05)
    st.slider("Pressure/Form", 0.8, 1.2, key="w_int", step=0.05)

# --- 🕵️ MAIN BODY ---
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.radio("Game", ["CS2", "Valorant"], key="game_choice", horizontal=True)
    st.selectbox("Search", ["Manual Entry"] + (df[df['Game'] == st.session_state.game_choice]['Player'].tolist() if not df.empty else []), key="player_selector", on_change=sync_player_data)
    
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context") # 🟢 LOCKED VIA KEY
    st.text_input("Projected Maps", key="p_maps")
    st.number_input("Opponent World Rank", key="opp_rank_input")
    
    if st.session_state.game_choice == "CS2":
        st.selectbox("Prop Type", ["Kills", "Headshot Kills"], key="prop_type_select")
        c1, c2, c3 = st.columns(3)
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
        c3.number_input("HS%", key="hs_pct_input", format="%.1f")
    else:
        st.number_input("Base ADR", key="adr_input", value=140.0)
        st.selectbox("Role", ["Duelist", "Support"], key="val_role_select")
    
    st.text_area("L10 Data", key="l10")
    l_c1, l_c2 = st.columns(2)
    m_line = l_c1.number_input("Prop Line", value=31.5, step=0.5)
    m_side = l_c2.selectbox("Side", ["Over", "Under"], key="side_select")

    if st.button("🚀 EXECUTE GRADE", use_container_width=True):
        try:
            v_list = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
            weights = st.session_state.w_h2h * st.session_state.w_tier * st.session_state.w_map * st.session_state.w_int
            
            if st.session_state.game_choice == "CS2":
                proj = ((st.session_state.m1_kpr_input + st.session_state.m2_kpr_input) / 2) * 48 * weights
                if st.session_state.get('prop_type_select') == "Headshot Kills":
                    proj = proj * (st.session_state.hs_pct_input / 100)
            else:
                proj = (st.session_state.adr_input / 140) * 42 * weights * (1.15 if st.session_state.val_role_select == "Duelist" else 0.95)
            
            edge = ((proj - m_line) / m_line * 100) if m_side == "Over" else ((m_line - proj) / m_line * 100)
            hit = (sum(1 for v in v_list if (v > m_line if m_side == "Over" else v < m_line)) / len(v_list)) * 100
            grade = "S" if edge > 22 and hit >= 70 else "A+" if edge > 15 and hit >= 60 else "A"

            st.session_state.results = {"grade": grade, "proj": proj, "edge": edge, "line": m_line, "side": m_side, "hit": hit, "units": 2.5 if grade == "S" else 1.0}
        except: st.error("Verification error.")

# --- 📊 OUTPUT ---
with col_r:
    if st.session_state.results:
        res = st.session_state.results
        
        # Decision Board
        st.markdown(f"""
        <div style="background:#1a1c23; border:1px solid #333; border-radius:15px; padding:25px; text-align:center; margin-bottom:20px;">
            <div style="font-size: 110px; font-weight: 900; color: #FFD700; line-height:1;">{res['grade']}</div>
            <div style="color:{'#00FF00' if res['side'] == 'Over' else '#FF0000'}; font-weight:bold; font-size:24px;">{res['side'].upper()} {res['line']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Professional Stats Grid
        g1, g2, g3 = st.columns(3)
        g1.metric("Projection", f"{res['proj']:.1f}")
        g2.metric("Edge", f"+{res['edge']:.1f}%")
        g3.metric("L10 Hit", f"{res['hit']:.0f}%")
        
        if st.checkbox("💎 Generate Social Media Card"):
            arrow = "▲" if res['side'] == "Over" else "▼"
            # 🛡️ THE CSS SHIELD (STRICT HTML)
            st.markdown(f"""
            <div style="background-color:#121212; border:2px solid #FFD700; border-radius:20px; padding:35px; width:450px; margin:auto; color:white; text-align:center; font-family:sans-serif;">
                <div style="font-size:48px; font-weight:900; margin:0; line-height:1;">{st.session_state.p_tag.upper()}</div>
                <div style="color:#4A90E2; font-size:18px; font-weight:bold; margin:10px 0 20px 0;">{st.session_state.m_context.upper()}</div>
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px;">
                    <div style="text-align:left;">
                        <div style="color:#888; font-size:11px; font-weight:bold;">PROP LINE</div>
                        <div style="font-size:75px; font-weight:900; line-height:1;">{res['line']}</div>
                        <span style="color:{'#00FF00' if res['side'] == 'Over' else '#FF0000'}; border:1px solid {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; padding:4px 10px; border-radius:8px; font-weight:900;">{arrow} {res['side'].upper()}</span>
                    </div>
                    <div style="text-align:center; width:140px;">
                        <div style="font-size:100px; font-weight:900; color:#FFD700; text-shadow:0 0 20px rgba(255,215,0,0.5); line-height:0.9;">{res['grade']}</div>
                    </div>
                </div>
                <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; border-top:1px solid #333; padding-top:20px;">
                    <div><div style="font-size:10px; color:#666; font-weight:bold;">PROJ</div><div style="font-size:22px; font-weight:900;">{res['proj']:.1f}</div></div>
                    <div><div style="font-size:10px; color:#666; font-weight:bold;">EDGE</div><div style="font-size:22px; font-weight:900;">+{res['edge']:.1f}%</div></div>
                    <div><div style="font-size:10px; color:#666; font-weight:bold;">L10 HIT</div><div style="font-size:22px; font-weight:900;">{res['hit']:.0f}%</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)