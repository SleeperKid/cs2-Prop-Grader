import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 🛡️ ARCHITECT'S UTILITIES
# ==========================================
def safe_float(val, default=0.0):
    """Prevents the 'ValueError' by shielding against 'N/A' or empty cells."""
    try:
        if pd.isna(val) or val == "N/A" or val == "": return default
        return float(val)
    except: return default

@st.cache_data(ttl=300)
def load_vault():
    """High-performance data fetch from Google Sheets."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        # Separate pulls for sport isolation
        val_df = conn.read(spreadsheet=sheet_url, worksheet="VAL_DATA", ttl=0)
        cs_df = conn.read(spreadsheet=sheet_url, worksheet="CS2_DATA", ttl=0)
        val_df['Game'], cs_df['Game'] = 'Valorant', 'CS2'
        return pd.concat([val_df, cs_df], ignore_index=True).replace("N/A", np.nan)
    except Exception as e:
        st.error(f"Vault Connection Failure: {e}")
        return pd.DataFrame()

# ==========================================
# 🧠 UI STATE ENGINE (The Auto-Pop Fix)
# ==========================================
def sync_player_data():
    """
    The Callback Engine: This fires the instant a player is selected.
    It updates the session state BEFORE the widgets render.
    """
    if st.session_state.player_selector != "Manual Entry":
        # Search the cached dataframe
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        
        # Force update state keys
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        
        # Team context
        team = str(row.get('Team', 'Free Agent'))
        st.session_state.m_context = f"{team} vs "
        
        # Valorant ADR persistence
        if st.session_state.game_choice == "Valorant":
            st.session_state.adr = safe_float(row.get('ADR'), 140.0)

# ==========================================
# 🎨 PRODUCTION STYLING
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# Initialize state keys if they don't exist
for key, val in {'p_tag': "", 'l10': "", 'm_context': "", 'adr': 140.0, 'results': None}.items():
    if key not in st.session_state: st.session_state[key] = val

st.markdown("""
<style>
    .main { background-color: #0e1117; }
    /* Suggested Play Box */
    .suggested-play {
        background: linear-gradient(180deg, rgba(255,215,0,0.1) 0%, rgba(0,0,0,0) 100%);
        border: 1px solid #FFD700; border-radius: 15px; padding: 20px; margin: 20px 0;
    }
    /* Glow Grade */
    .glow-s {
        font-size: 120px; font-weight: 900; color: #FFD700;
        text-shadow: 0 0 20px rgba(255, 215, 0, 0.5); line-height: 1;
    }
    .pill-over { color: #00FF00; border: 1px solid #00FF00; padding: 5px 15px; border-radius: 8px; font-weight: bold; }
    .pill-under { color: #FF0000; border: 1px solid #FF0000; padding: 5px 15px; border-radius: 8px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🕵️ INPUT SECTION
# ==========================================
game_choice = st.radio("Target Game", ["CS2", "Valorant"], key="game_choice", horizontal=True)
players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Intelligence")
    st.selectbox("Search Database", ["Manual Entry"] + players, key="player_selector", on_change=sync_player_data)
    
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    
    if game_choice == "CS2":
        c1, c2 = st.columns(2)
        m1_kpr = c1.number_input("Map 1 KPR (Manual)", value=0.82, format="%.2f")
        m2_kpr = c2.number_input("Map 2 KPR (Manual)", value=0.82, format="%.2f")
    else:
        st.number_input("Base ADR", key="adr")
        
    l10_data = st.text_area("L10 Data (CSV)", key="l10")
    
    st.divider()
    # Analysis Controls
    c_line, c_odds = st.columns(2)
    m_line = c_line.number_input("Line", value=31.5, step=0.5)
    m_side = c_line.selectbox("Side", ["Over", "Under"])
    m_odds = c_odds.number_input("Odds", value=-128)
    m_scope = c_odds.selectbox("Scope", ["Full Match", "Map 1 Only", "Maps 1 & 2"])

# ==========================================
# 🚀 CALCULATION ENGINE
# ==========================================
if st.button("🚀 GENERATE SLEEPER D. KID GRADE"):
    try:
        vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
        if not vals: st.warning("Please enter L10 data."); st.stop()
        
        # Simple Math Mockup (Replace with your specific Normal Distribution logic)
        mean_val = np.mean(vals)
        std_val = max(np.std(vals), 2.5)
        
        # Projection Logic
        if game_choice == "CS2":
            base = (m1_kpr + m2_kpr) / 2 * 24 * 2.2 # MR12 Full Match
        else:
            base = (st.session_state.adr / 150) * 26 * 2.2
            
        prob = (1 - norm.cdf(m_line, loc=base, scale=std_val)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=base, scale=std_val) * 100
        edge = prob - 50 # Simplified edge for card rendering
        hit_rate = (sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line)) / len(vals)) * 100
        
        st.session_state.results = {
            "grade": "S" if edge > 15 else "A+" if edge > 8 else "A" if edge > 2 else "B",
            "units": 2.5 if edge > 15 else 1.0,
            "proj": base, "edge": edge, "prob": prob, "hit": hit_rate,
            "line": m_line, "side": m_side
        }
    except Exception as e:
        st.error(f"Calculation Error: {e}")

# ==========================================
# 💎 THE SOCIAL CARD (Sleeper D. Kid Edition)
# ==========================================
if st.session_state.results:
    res = st.session_state.results
    with col_r:
        pill_style = "pill-over" if res['side'] == "Over" else "pill-under"
        arrow = "▲" if res['side'] == "Over" else "▼"
        
        st.markdown(f"""
        <div style="background-color: #121212; border: 2px solid #FFD700; border-radius: 25px; padding: 40px; width: 450px; margin: auto; color: white; text-align: center; font-family: sans-serif;">
            <div style="color: #888; letter-spacing: 3px; font-size: 14px; margin-bottom:10px;">{game_choice.upper()} PROP ANALYSIS</div>
            <div style="font-size: 55px; font-weight: 900; margin: 0; line-height:1;">{st.session_state.p_tag.upper()}</div>
            <div style="color: #4A90E2; font-size: 18px; font-weight: bold; margin-bottom: 25px; border-bottom: 1px solid #333; padding-bottom: 15px;">
                {st.session_state.m_context.upper()}
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0;">
                <div style="text-align: left;">
                    <div style="color:#888; font-size:12px; font-weight:bold;">THE PROP LINE</div>
                    <div style="font-size: 85px; font-weight: 900; line-height:1;">{res['line']}</div>
                    <div style="color:#888; font-size:18px; margin-bottom:15px;">KILLS</div>
                    <span class="{pill_style}">{arrow} {res['side'].upper()}</span>
                </div>
                <div style="text-align: center;">
                    <div style="color:#888; font-size:12px; font-weight:bold; margin-bottom:5px;">MODEL GRADE</div>
                    <div class="glow-s">{res['grade']}</div>
                </div>
            </div>
            
            <div class="suggested-play">
                <div style="color: #FFD700; letter-spacing: 2px; font-weight: bold; font-size: 14px;">SUGGESTED PLAY</div>
                <div style="font-size: 42px; font-weight: 900;">{res['units']} UNITS</div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; border-top: 1px solid #333; padding-top: 25px;">
                <div><div style="font-size: 10px; color: #666; font-weight:bold;">PROJ</div><div style="font-size: 20px; font-weight: 900;">{res['proj']:.1f}</div></div>
                <div><div style="font-size: 10px; color: #666; font-weight:bold;">EDGE</div><div style="font-size: 20px; font-weight: 900;">+{max(res['edge'],0):.1f}%</div></div>
                <div><div style="font-size: 10px; color: #666; font-weight:bold;">CONF</div><div style="font-size: 20px; font-weight: 900;">{res['prob']:.0f}%</div></div>
                <div><div style="font-size: 10px; color: #666; font-weight:bold;">L10 HIT</div><div style="font-size: 20px; font-weight: 900;">{res['hit']:.0f}%</div></div>
            </div>
            
            <div style="color: #4A90E2; letter-spacing: 4px; font-size: 12px; margin-top: 40px; font-weight: bold;">ANALYSIS BY SLEEPER D. KID</div>
        </div>
        """, unsafe_allow_html=True)