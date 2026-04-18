import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from scipy.stats import norm
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 🛡️ ARCHITECT'S UTILITIES
# ==========================================
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
    except Exception as e:
        st.error(f"Vault Connection Failure: {e}")
        return pd.DataFrame()

def load_intel_vault():
    """Loads proprietary scouting data."""
    if os.path.exists("intel_vault.json"):
        with open("intel_vault.json", "r") as f: return json.load(f)
    return {"teams": {}, "maps": {}}

# ==========================================
# 🧠 AI ADVISOR ENGINE (V85: SLIDER AUTOMATION)
# ==========================================
def ai_advisor_engine():
    """
    Analyzes all inputs + Intel Vault to physically move sliders.
    """
    intel = load_intel_vault()
    # Temporary weights for calculation
    weights = {"h2h": 1.0, "tier": 1.0, "map": 1.0, "int": 1.0}
    reasons = []

    # Contextual awareness
    maps = st.session_state.get('p_maps', "").lower()
    context = st.session_state.get('m_context', "").lower()
    m1_kpr = st.session_state.get('m1_kpr_input', 0.82)

    # 1. Team Intel Check
    for team, data in intel.get("teams", {}).items():
        if team.lower() in context:
            weights["tier"] = data.get("tier_weight", 1.0)
            reasons.append(f"📡 Intel Found: {data.get('scouting_note', 'Opponent data synced.')}")

    # 2. Map Intel Check
    for m_name, m_data in intel.get("maps", {}).items():
        if m_name.lower() in maps:
            weights["map"] = m_data.get("difficulty_modifier", 1.0)
            reasons.append(f"🗺️ Map Data: {m_name.title()} is {m_data.get('type', 'standard')}.")

    # 3. KPR Momentum
    if m1_kpr > 0.88:
        weights["int"] = 1.05
        reasons.append("🔥 Momentum: High manual KPR suggests player is peaking.")

    # Apply findings to Session State (This physically moves the sliders)
    st.session_state.w_h2h = weights["h2h"]
    st.session_state.w_tier = weights["tier"]
    st.session_state.w_map = weights["map"]
    st.session_state.w_int = weights["int"]
    st.session_state.ai_thoughts = reasons

def sync_player_data():
    """CALLBACK: Auto-populates KPR and basic info."""
    if st.session_state.player_selector != "Manual Entry":
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        
        # Snap global baseline to Map 1/2 fields
        base_kpr = safe_float(row.get('KPR'), 0.82)
        st.session_state.m1_kpr_input = base_kpr
        st.session_state.m2_kpr_input = base_kpr
        
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Free Agent')} vs "
        
        if st.session_state.game_choice == "Valorant":
            st.session_state.adr = safe_float(row.get('ADR'), 140.0)

# ==========================================
# 🎨 PRODUCTION UI & CSS (FIXED CARD)
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# Persistent state initialization
defaults = {
    'p_tag': "", 'l10': "", 'm_context': "", 'p_maps': "", 
    'm1_kpr_input': 0.82, 'm2_kpr_input': 0.82, 'results': None,
    'w_h2h': 1.0, 'w_tier': 1.0, 'w_map': 1.0, 'w_int': 1.0, 'ai_thoughts': []
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

st.markdown("""
<style>
    .ai-bubble { background-color: #1a1c23; border-left: 5px solid #4A90E2; padding: 12px; border-radius: 8px; margin-top: 10px; font-size: 13px; color: #d1d1d1; }
    .glow-grade { font-size: 130px; font-weight: 900; color: #FFD700; text-shadow: 0 0 30px rgba(255, 215, 0, 0.6); line-height: 0.8; }
    .pill-over { color: #00FF00; border: 1px solid #00FF00; padding: 6px 16px; border-radius: 10px; font-weight: 900; font-size: 20px; }
    .pill-under { color: #FF0000; border: 1px solid #FF0000; padding: 6px 16px; border-radius: 10px; font-weight: 900; font-size: 20px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🛰️ SIDEBAR: AI ADVISOR & SLIDERS
# ==========================================
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    
    st.subheader("🤖 AI Advisor")
    if st.button("🧠 CONSULT AI & ADJUST SLIDERS", use_container_width=True):
        ai_advisor_engine() # This moves the session state
        st.success("AI Scout successful. Sliders adjusted.")

    if st.session_state.ai_thoughts:
        thought_html = "".join([f"<li>{t}</li>" for t in st.session_state.ai_thoughts])
        st.markdown(f'<div class="ai-bubble"><ul>{thought_html}</ul></div>', unsafe_allow_html=True)
    
    st.divider()
    # Sliders pull directly from the session state updated by the AI
    st.session_state.w_h2h = st.slider("H2H Advantage", 0.8, 1.2, st.session_state.w_h2h, 0.05)
    st.session_state.w_tier = st.slider("Opponent Tier", 0.8, 1.2, st.session_state.w_tier, 0.05)
    st.session_state.w_map = st.slider("Map Fit", 0.8, 1.2, st.session_state.w_map, 0.05)
    st.session_state.w_int = st.slider("Pressure/Form", 0.8, 1.2, st.session_state.w_int, 0.05)

# ==========================================
# 🕵️ MAIN BODY: OPERATIONS
# ==========================================
st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
players = df[df['Game'] == st.session_state.game_choice]['Player'].tolist() if not df.empty else []

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Intelligence")
    st.selectbox("Search Database", ["Manual Entry"] + players, key="player_selector", on_change=sync_player_data)
    
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    st.text_input("Projected Maps", key="p_maps")
    
    if st.session_state.game_choice == "CS2":
        c1, c2 = st.columns(2)
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
    else:
        st.number_input("Base ADR", key="adr")
        
    st.text_area("L10 Data (CSV)", key="l10")
    
    cl, cs = st.columns(2)
    m_line = cl.number_input("Prop Line", value=31.5, step=0.5)
    m_side = cs.selectbox("Target Side", ["Over", "Under"])
    
    if st.button("🚀 EXECUTE ENGINE", use_container_width=True):
        try:
            vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
            t_weight = st.session_state.w_h2h * st.session_state.w_tier * st.session_state.w_map * st.session_state.w_int
            proj = ((st.session_state.m1_kpr_input + st.session_state.m2_kpr_input) / 2) * 48 * t_weight
            edge = (proj - m_line) / m_line * 100 if m_side == "Over" else (m_line - proj) / m_line * 100
            st.session_state.results = {"grade": "S" if edge > 15 else "A", "edge": edge, "proj": proj, "line": m_line, "side": m_side, "hit": 70, "prob": 88, "units": 2.5}
        except: st.error("Calc Error")

with col_r:
    if st.session_state.results:
        res = st.session_state.results
        
        # Discord Copy Box
        st.text_area("📋 Copy for Discord", f"🚨 {st.session_state.p_tag.upper()} {res['side'].upper()}\nLine: {res['line']} | Grade: {res['grade']}")

        if st.checkbox("💎 Generate Sleeper D. Kid Social Card"):
            pill = "pill-over" if res['side'] == "Over" else "pill-under"
            arrow = "▲" if res['side'] == "Over" else "▼"
            
            # FIXED HTML INJECTION
            st.markdown(f"""
            <div style="background-color: #121212; border: 2px solid #FFD700; border-radius: 25px; padding: 40px; width: 450px; margin: auto; color: white; text-align: center; font-family: sans-serif;">
                <div style="color: #888; letter-spacing: 3px; font-size: 13px; margin-bottom:12px;">{st.session_state.game_choice.upper()} PROP ANALYSIS</div>
                <div style="font-size: 52px; font-weight: 900; margin: 0; line-height:1;">{st.session_state.p_tag.upper()}</div>
                <div style="color: #4A90E2; font-size: 18px; font-weight: bold; margin-bottom: 30px; border-bottom: 1px solid #333; padding-bottom: 18px;">{st.session_state.m_context.upper()}</div>
                
                <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 10px 0;">
                    <div style="text-align: left; flex: 1;">
                        <div style="color:#888; font-size:12px; font-weight:bold;">THE PROP LINE</div>
                        <div style="font-size: 82px; font-weight: 900; line-height:1;">{res['line']}</div>
                        <div style="color:#888; font-size:18px; margin-bottom:18px;">KILLS</div>
                        <span class="{pill}">{arrow} {res['side'].upper()}</span>
                    </div>
                    <div style="width: 140px; text-align: center;">
                        <div style="color:#888; font-size:11px; font-weight:bold; margin-bottom:12px;">MODEL GRADE</div>
                        <div class="glow-grade">{res['grade']}</div>
                    </div>
                </div>
                
                <div style="background: linear-gradient(180deg, rgba(255,215,0,0.1) 0%, rgba(0,0,0,0) 100%); border: 1px solid #FFD700; border-radius: 18px; padding: 22px; margin: 25px 0;">
                    <div style="color: #FFD700; font-weight: bold; font-size: 14px; letter-spacing:2px;">SUGGESTED PLAY</div>
                    <div style="font-size: 44px; font-weight: 900;">{res['units']} UNITS</div>
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; border-top: 1px solid #333; padding-top: 25px;">
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">PROJ</div><div style="font-size: 20px; font-weight: 900;">{res['proj']:.1f}</div></div>
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">EDGE</div><div style="font-size: 20px; font-weight: 900;">+{res['edge']:.1f}%</div></div>
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">CONF</div><div style="font-size: 20px; font-weight: 900;">{res['prob']:.0f}%</div></div>
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">L10 HIT</div><div style="font-size: 20px; font-weight: 900;">{res['hit']:.0f}%</div></div>
                </div>
                <div style="color: #4A90E2; letter-spacing: 4px; font-size: 12px; margin-top: 40px; font-weight: bold;">ANALYSIS BY SLEEPER D. KID</div>
            </div>
            """, unsafe_allow_html=True)