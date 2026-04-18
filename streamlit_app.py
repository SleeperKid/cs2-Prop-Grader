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

def sync_player_data():
    """Callback for instant UI population."""
    if st.session_state.player_selector != "Manual Entry":
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        team = str(row.get('Team', 'Free Agent'))
        st.session_state.m_context = f"{team} vs "
        if st.session_state.game_choice == "Valorant":
            st.session_state.adr = safe_float(row.get('ADR'), 140.0)

# ==========================================
# 🎨 UI CONFIG & CSS
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# Initialize persistent state
for key, val in {'p_tag': "", 'l10': "", 'm_context': "", 'adr': 140.0, 'results': None}.items():
    if key not in st.session_state: st.session_state[key] = val

st.markdown("""
<style>
    .glow-s { font-size: 120px; font-weight: 900; color: #FFD700; text-shadow: 0 0 20px rgba(255, 215, 0, 0.5); line-height: 1; }
    .suggested-play { background: linear-gradient(180deg, rgba(255,215,0,0.1) 0%, rgba(0,0,0,0) 100%); border: 1px solid #FFD700; border-radius: 15px; padding: 20px; margin: 20px 0; }
    .pill-over { color: #00FF00; border: 1px solid #00FF00; padding: 5px 15px; border-radius: 8px; font-weight: bold; }
    .pill-under { color: #FF0000; border: 1px solid #FF0000; padding: 5px 15px; border-radius: 8px; font-weight: bold; }
    .ai-box { background-color: #1a1c23; border-left: 5px solid #4A90E2; padding: 15px; border-radius: 8px; margin-top: 10px; font-style: italic; color: #d1d1d1; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🛰️ SIDEBAR: ONLY ADVISOR & SLIDERS
# ==========================================
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    
    st.write("### Contextual Weights")
    w_h2h = st.slider("H2H Advantage", 0.8, 1.2, 1.0, 0.05)
    w_tier = st.slider("Opponent Tier", 0.8, 1.2, 1.0, 0.05)
    w_map = st.slider("Map Suitability", 0.8, 1.2, 1.0, 0.05)
    w_int = st.slider("Pressure/Form", 0.8, 1.2, 1.0, 0.05)
    
    st.divider()
    st.subheader("🤖 AI Advisor")
    if st.session_state.results:
        res = st.session_state.results
        analysis = f"""**Projection:** {res['proj']:.1f} | **Edge:** {res['edge']:.1f}%
        
        Recent form (L10: {res['hit']:.0f}%) suggests high synergy with this {res['side']} lean. 
        {'🔥 High Conviction Play.' if res['grade'] == 'S' else '✅ Standard Value Play.'}"""
        st.markdown(f'<div class="ai-box">{analysis}</div>', unsafe_allow_html=True)
    else:
        st.info("Execute engine to generate AI analysis.")

# ==========================================
# 🕵️ MAIN BODY: DATA ENTRY & OUTPUT
# ==========================================
st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
players = df[df['Game'] == st.session_state.game_choice]['Player'].tolist() if not df.empty else []

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Intelligence")
    st.selectbox("Search Database", ["Manual Entry"] + players, key="player_selector", on_change=sync_player_data)
    
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    
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
        
        # Grading Summary
        st.metric("Model Edge", f"+{res['edge']:.1f}%", delta=res['grade'])
        
        # Social Card Shield
        if res['grade'] in ["S", "A+", "A"]:
            if st.checkbox("💎 Generate Sleeper D. Kid Social Card"):
                pill = "pill-over" if res['side'] == "Over" else "pill-under"
                arrow = "▲" if res['side'] == "Over" else "▼"
                
                st.markdown(f"""
                <div style="background-color: #121212; border: 2px solid #FFD700; border-radius: 25px; padding: 40px; width: 450px; margin: auto; color: white; text-align: center;">
                    <div style="color: #888; letter-spacing: 3px; font-size: 14px; margin-bottom:10px;">{st.session_state.game_choice.upper()} PROP ANALYSIS</div>
                    <div style="font-size: 55px; font-weight: 900; margin: 0; line-height:1;">{st.session_state.p_tag.upper()}</div>
                    <div style="color: #4A90E2; font-size: 18px; font-weight: bold; margin-bottom: 25px; border-bottom: 1px solid #333; padding-bottom: 15px;">{st.session_state.m_context.upper()}</div>
                    
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0;">
                        <div style="text-align: left;">
                            <div style="color:#888; font-size:12px; font-weight:bold;">THE PROP LINE</div>
                            <div style="font-size: 85px; font-weight: 900; line-height:1;">{res['line']}</div>
                            <div style="color:#888; font-size:18px; margin-bottom:15px;">KILLS</div>
                            <span class="{pill}">{arrow} {res['side'].upper()}</span>
                        </div>
                        <div>
                            <div style="color:#888; font-size:12px; font-weight:bold; margin-bottom:5px;">MODEL GRADE</div>
                            <div class="glow-s">{res['grade']}</div>
                        </div>
                    </div>
                    
                    <div class="suggested-play">
                        <div style="color: #FFD700; font-weight: bold; font-size: 14px;">SUGGESTED PLAY</div>
                        <div style="font-size: 42px; font-weight: 900;">{res['units']} UNITS</div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; border-top: 1px solid #333; padding-top: 25px;">
                        <div><div style="font-size: 10px; color: #666; font-weight:bold;">PROJ</div><div style="font-size: 20px; font-weight: 900;">{res['proj']:.1f}</div></div>
                        <div><div style="font-size: 10px; color: #666; font-weight:bold;">EDGE</div><div style="font-size: 20px; font-weight: 900;">+{res['edge']:.1f}%</div></div>
                        <div><div style="font-size: 10px; color: #666; font-weight:bold;">CONF</div><div style="font-size: 20px; font-weight: 900;">{res['prob']:.0f}%</div></div>
                        <div><div style="font-size: 10px; color: #666; font-weight:bold;">L10 HIT</div><div style="font-size: 20px; font-weight: 900;">{res['hit']:.0f}%</div></div>
                    </div>
                    <div style="color: #4A90E2; letter-spacing: 4px; font-size: 12px; margin-top: 40px;">ANALYSIS BY SLEEPER D. KID</div>
                </div>
                """, unsafe_allow_html=True)