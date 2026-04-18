import streamlit as st
import pandas as pd
import numpy as np
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

# ==========================================
# 🧠 AI ADVISOR ENGINE (Auto-Adjust Logic)
# ==========================================
def ai_advisor_engine():
    """
    Analyzes context and maps to auto-adjust sliders.
    This creates the 'Smart' layer of the product.
    """
    # Baseline
    weights = {"h2h": 1.0, "tier": 1.0, "map": 1.0, "int": 1.0}
    reasons = []

    context = st.session_state.m_context.lower()
    maps = st.session_state.p_maps.lower()
    p_tag = st.session_state.p_tag.lower()

    # 1. Map Heuristics (Example Logic)
    if any(m in maps for m in ["anubis", "ancient"]):
        weights["map"] = 1.10
        reasons.append("🔥 Map Fit: High-fragging maps detected.")
    elif "nuke" in maps or "inferno" in maps:
        weights["map"] = 0.95
        reasons.append("🛡️ Map Fit: Tactical/Lower-frag maps detected.")

    # 2. Matchup Heuristics
    if "vs spirit" in context or "vs vitality" in context:
        weights["tier"] = 0.90
        reasons.append("⚠️ Tier: Elite opponent; expect resistance.")
    
    # 3. Pressure/Form
    if "final" in context or "playoff" in context:
        weights["int"] = 1.05
        reasons.append("🏆 Pressure: High-stakes environment boost.")

    # Update Session State for Sliders
    st.session_state.w_h2h = weights["h2h"]
    st.session_state.w_tier = weights["tier"]
    st.session_state.w_map = weights["map"]
    st.session_state.w_int = weights["int"]
    st.session_state.ai_thoughts = reasons

def sync_player_data():
    if st.session_state.player_selector != "Manual Entry":
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Free Agent')} vs "
        ai_advisor_engine() # Trigger smart update on load

# ==========================================
# 🎨 UI CONFIG & CSS
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# Initialize persistent state keys
defaults = {
    'p_tag': "", 'l10': "", 'm_context': "", 'p_maps': "", 
    'adr': 140.0, 'results': None, 'ai_thoughts': [],
    'w_h2h': 1.0, 'w_tier': 1.0, 'w_map': 1.0, 'w_int': 1.0
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

st.markdown("""
<style>
    .glow-s { font-size: 110px; font-weight: 900; color: #FFD700; text-shadow: 0 0 20px rgba(255, 215, 0, 0.5); line-height: 1; }
    .suggested-play { background: linear-gradient(180deg, rgba(255,215,0,0.1) 0%, rgba(0,0,0,0) 100%); border: 1px solid #FFD700; border-radius: 15px; padding: 20px; margin: 15px 0; }
    .ai-box { background-color: #1a1c23; border-left: 5px solid #4A90E2; padding: 15px; border-radius: 8px; margin-top: 10px; font-size: 13px; color: #d1d1d1; }
    .pill-over { color: #00FF00; border: 1px solid #00FF00; padding: 5px 12px; border-radius: 8px; font-weight: bold; font-size: 14px; }
    .pill-under { color: #FF0000; border: 1px solid #FF0000; padding: 5px 12px; border-radius: 8px; font-weight: bold; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🛰️ SIDEBAR: AI ADVISOR & AUTO-SLIDERS
# ==========================================
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    
    st.subheader("🤖 AI Advisor")
    if st.session_state.ai_thoughts:
        thought_html = "".join([f"<li>{t}</li>" for t in st.session_state.ai_thoughts])
        st.markdown(f'<div class="ai-box"><ul>{thought_html}</ul></div>', unsafe_allow_html=True)
    else:
        st.info("Enter Maps or Context to trigger AI analysis.")
    
    st.divider()
    st.write("### Contextual Weights")
    w_h2h = st.slider("H2H Advantage", 0.8, 1.2, st.session_state.w_h2h, 0.05)
    w_tier = st.slider("Opponent Tier", 0.8, 1.2, st.session_state.w_tier, 0.05)
    w_map = st.slider("Map Fit", 0.8, 1.2, st.session_state.w_map, 0.05)
    w_int = st.slider("Pressure/Form", 0.8, 1.2, st.session_state.w_int, 0.05)
    
    if st.button("🔄 Refresh AI Recommendation", use_container_width=True):
        ai_advisor_engine()
        st.rerun()

# ==========================================
# 🕵️ MAIN BODY: DATA ENTRY
# ==========================================
st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
players = df[df['Game'] == st.session_state.game_choice]['Player'].tolist() if not df.empty else []

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Intelligence")
    st.selectbox("Search Database", ["Manual Entry"] + players, key="player_selector", on_change=sync_player_data)
    
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    st.text_input("Projected Maps", key="p_maps", placeholder="e.g. Mirage, Anubis")
    
    if st.session_state.game_choice == "CS2":
        c1, c2 = st.columns(2)
        m1_kpr = c1.number_input("Map 1 KPR", value=0.82)
        m2_kpr = c2.number_input("Map 2 KPR", value=0.82)
    else:
        st.number_input("Base ADR", key="adr")
        
    st.text_area("L10 Data (CSV)", key="l10")
    
    st.divider()
    cl, cs = st.columns(2)
    m_line = cl.number_input("Prop Line", value=31.5, step=0.5)
    m_side = cs.selectbox("Target Side", ["Over", "Under"])
    
    if st.button("🚀 EXECUTE ENGINE", use_container_width=True):
        try:
            vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
            t_weight = w_h2h * w_tier * w_map * w_int
            std = max(np.std(vals), 2.5)
            
            if st.session_state.game_choice == "CS2":
                proj = ((m1_kpr + m2_kpr) / 2) * 48 * t_weight
            else:
                proj = (st.session_state.adr / 150) * 52 * t_weight
            
            prob = (1 - norm.cdf(m_line, loc=proj, scale=std)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=proj, scale=std) * 100
            edge = prob - 50
            hit = (sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line)) / len(vals)) * 100
            grade = "S" if edge > 15 else "A+" if edge > 10 else "A" if edge > 5 else "B"
            
            st.session_state.results = {
                "grade": grade, "units": 2.5 if edge > 15 else 1.0 if edge > 5 else 0.5,
                "proj": proj, "edge": edge, "prob": prob, "hit": hit,
                "line": m_line, "side": m_side
            }
        except Exception as e: st.error(f"Error: {e}")

with col_r:
    if st.session_state.results:
        res = st.session_state.results
        st.metric("Model Edge", f"+{res['edge']:.1f}%", delta=res['grade'])
        
        if res['grade'] in ["S", "A+", "A"]:
            if st.checkbox("💎 Generate Sleeper D. Kid Social Card"):
                pill = "pill-over" if res['side'] == "Over" else "pill-under"
                arrow = "▲" if res['side'] == "Over" else "▼"
                st.markdown(f"""
                <div style="background-color: #121212; border: 2px solid #FFD700; border-radius: 25px; padding: 40px; width: 450px; margin: auto; color: white; text-align: center;">
                    <div style="color: #888; letter-spacing: 3px; font-size: 14px; margin-bottom:10px;">{st.session_state.game_choice.upper} PROP ANALYSIS</div>
                    <div style="font-size: 50px; font-weight: 900; margin: 0; line-height:1;">{st.session_state.p_tag.upper()}</div>
                    <div style="color: #4A90E2; font-size: 16px; font-weight: bold; margin-bottom: 25px; border-bottom: 1px solid #333; padding-bottom: 15px;">{st.session_state.m_context.upper()}</div>
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0;">
                        <div style="text-align: left;">
                            <div style="color:#888; font-size:12px; font-weight:bold;">THE PROP LINE</div>
                            <div style="font-size: 80px; font-weight: 900; line-height:1;">{res['line']}</div>
                            <div style="color:#888; font-size:16px; margin-bottom:15px;">KILLS</div>
                            <span class="{pill}">{arrow} {res['side'].upper()}</span>
                        </div>
                        <div>
                            <div style="color:#888; font-size:12px; font-weight:bold; margin-bottom:5px;">MODEL GRADE</div>
                            <div class="glow-s">{res['grade']}</div>
                        </div>
                    </div>
                    <div class="suggested-play">
                        <div style="color: #FFD700; font-weight: bold; font-size: 14px;">SUGGESTED PLAY</div>
                        <div style="font-size: 40px; font-weight: 900;">{res['units']} UNITS</div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; border-top: 1px solid #333; padding-top: 25px;">
                        <div><div style="font-size: 10px; color: #666; font-weight:bold;">PROJ</div><div style="font-size: 18px; font-weight: 900;">{res['proj']:.1f}</div></div>
                        <div><div style="font-size: 10px; color: #666; font-weight:bold;">EDGE</div><div style="font-size: 18px; font-weight: 900;">+{res['edge']:.1f}%</div></div>
                        <div><div style="font-size: 10px; color: #666; font-weight:bold;">CONF</div><div style="font-size: 18px; font-weight: 900;">{res['prob']:.0f}%</div></div>
                        <div><div style="font-size: 10px; color: #666; font-weight:bold;">L10 HIT</div><div style="font-size: 18px; font-weight: 900;">{res['hit']:.0f}%</div></div>
                    </div>
                    <div style="color: #4A90E2; letter-spacing: 4px; font-size: 12px; margin-top: 40px; font-weight: bold;">ANALYSIS BY SLEEPER D. KID</div>
                </div>
                """, unsafe_allow_html=True)