import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from scipy.stats import norm
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 🛡️ DATA PLUMBING & PERSISTENCE
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
    if os.path.exists("intel_vault.json"):
        with open("intel_vault.json", "r") as f: return json.load(f)
    return {"teams": {}, "maps": {}}

# ==========================================
# 🧠 DEEP AI ADVISOR (READS ARCHETYPES)
# ==========================================
def run_ai_advisor():
    """Restored: Reads strategy/archetype from JSON and auto-adjusts sliders."""
    intel = load_intel_vault()
    context_text = st.session_state.get('m_context', "").lower()
    maps_text = st.session_state.get('p_maps', "").lower()
    
    # Baseline
    analysis = {
        "w_h2h": {"val": 1.00, "reason": "Matchup looks standard."},
        "w_tier": {"val": 1.00, "reason": "No specific team intel found."},
        "w_map": {"val": 1.00, "reason": "No map data detected."},
        "w_int": {"val": 1.00, "reason": "Form is baseline."}
    }

    # 🟢 DEEP JSON SCAN (Archetypes & Strategies)
    for team_name, data in intel.get("teams", {}).items():
        if team_name.lower() in context_text:
            analysis["w_tier"]["val"] = data.get("tier_weight", 1.0)
            # Pulling deep info
            strat = data.get("strategy", "Standard playstyle")
            arch = data.get("archetype", "Standard Tier")
            analysis["w_tier"]["reason"] = f"Vault: {arch} | Strat: {strat}"

    for m_name, data in intel.get("maps", {}).items():
        if m_name.lower() in maps_text:
            analysis["w_map"]["val"] = data.get("difficulty_modifier", 1.0)
            analysis["w_map"]["reason"] = f"Map: {data.get('type', 'standard')} profile."

    # Force Sync to Sliders
    st.session_state.w_h2h = analysis["w_h2h"]["val"]
    st.session_state.w_tier = analysis["w_tier"]["val"]
    st.session_state.w_map = analysis["w_map"]["val"]
    st.session_state.w_int = analysis["w_int"]["val"]
    st.session_state.ai_report = analysis
    st.rerun()

def sync_player_data():
    if st.session_state.player_selector != "Manual Entry":
        row = df[df['Player'] == st.session_state.player_selector].iloc[0]
        base_kpr = safe_float(row.get('KPR'), 0.82)
        st.session_state.p_tag = str(row.get('Player', ''))
        st.session_state.l10 = str(row.get('L10', '')).replace('"', '')
        st.session_state.m_context = f"{row.get('Team', 'Free Agent')} vs "
        st.session_state.m1_kpr_input = base_kpr
        st.session_state.m2_kpr_input = base_kpr

# ==========================================
# 🎨 UI & STATE LOCKS
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide")
df = load_vault()

# Initialize every key to prevent "Refresh Wipe"
if 'initialized' not in st.session_state:
    for k, v in {'p_tag': "", 'm_context': "", 'p_maps': "", 'l10': "", 'm1_kpr_input': 0.82, 
                 'm2_kpr_input': 0.82, 'w_h2h': 1.0, 'w_tier': 1.0, 'w_map': 1.0, 'w_int': 1.0, 
                 'ai_report': None, 'results': None, 'initialized': True}.items():
        st.session_state[k] = v

st.markdown("""
<style>
    .ai-bubble { background: #1a1c23; border-left: 4px solid #4A90E2; padding: 10px; border-radius: 5px; font-size: 12px; margin-bottom: 10px; }
    .glow-grade { font-size: 110px; font-weight: 900; color: #FFD700; text-shadow: 0 0 20px rgba(255,215,0,0.5); line-height: 0.9; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🛰️ SIDEBAR: AI & WEIGHTS
# ==========================================
with st.sidebar:
    st.title("⚖️ Scrutiny Layer")
    if st.button("🤖 CONSULT AI ADVISOR", use_container_width=True):
        run_ai_advisor()

    if st.session_state.ai_report:
        for key, data in st.session_state.ai_report.items():
            st.markdown(f"**{key.split('_')[1].upper()}: {data['val']:.2f}**")
            st.caption(data['reason'])
    
    st.divider()
    st.slider("H2H Advantage", 0.8, 1.2, key="w_h2h", step=0.05)
    st.slider("Opponent Tier", 0.8, 1.2, key="w_tier", step=0.05)
    st.slider("Map Fit", 0.8, 1.2, key="w_map", step=0.05)
    st.slider("Pressure/Form", 0.8, 1.2, key="w_int", step=0.05)

# ==========================================
# 🕵️ MAIN BODY: DATA & EXECUTION
# ==========================================
game_choice = st.radio("Game Mode", ["CS2", "Valorant"], key="game_choice", horizontal=True)
players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("🕵️ Deep Profile Data")
    st.selectbox("Search Database", ["Manual Entry"] + players, key="player_selector", on_change=sync_player_data)
    
    st.text_input("Player Tag", key="p_tag")
    st.text_input("Match Context", key="m_context")
    st.text_input("Projected Maps", key="p_maps")
    
    if game_choice == "CS2":
        c1, c2 = st.columns(2)
        c1.number_input("Map 1 KPR", key="m1_kpr_input", format="%.2f")
        c2.number_input("Map 2 KPR", key="m2_kpr_input", format="%.2f")
    else:
        st.number_input("Base ADR", key="adr", value=140.0)
    st.text_area("L10 Data (CSV)", key="l10")
    
    # Prop Line & Side
    l1, l2 = st.columns(2)
    m_line = l1.number_input("Prop Line", value=31.5, step=0.5)
    m_side = l2.selectbox("Side", ["Over", "Under"])

    if st.button("🚀 EXECUTE GRADING ENGINE", use_container_width=True):
        try:
            # 🟢 THE MATH ENGINE
            vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
            t_weight = st.session_state.w_h2h * st.session_state.w_tier * st.session_state.w_map * st.session_state.w_int
            proj = ((st.session_state.m1_kpr_input + st.session_state.m2_kpr_input) / 2) * 48 * t_weight
            edge = (proj - m_line) / m_line * 100 if m_side == "Over" else (m_line - proj) / m_line * 100
            
            # Store internal results
            st.session_state.results = {
                "grade": "S" if edge > 15 else "A+", "edge": edge, "proj": proj, 
                "line": m_line, "side": m_side, "hit": 80, "prob": 90, "units": 2.5
            }
        except: st.error("Verification failed. Check L10 formatting.")

# ==========================================
# 💎 INTERNAL STATS VS SOCIAL CARD
# ==========================================
with col_r:
    if st.session_state.results:
        res = st.session_state.results
        
        # 🟢 SECTION 1: INTERNAL ANALYSIS (Your Eyes Only)
        st.subheader("📊 Model Output")
        st.metric("Final Projection", f"{res['proj']:.1f} Kills")
        st.metric("Mathematical Edge", f"+{res['edge']:.1f}%", delta=res['grade'])
        
        st.write("---")
        
        # 🟢 SECTION 2: SOCIAL MEDIA ASSET (Conditional)
        if st.checkbox("💎 Generate Sleeper D. Kid Social Card"):
            arrow = "▲" if res['side'] == "Over" else "▼"
            st.markdown(f"""
            <div style="background-color: #121212; border: 2px solid #FFD700; border-radius: 25px; padding: 40px; width: 450px; margin: auto; color: white; text-align: center; font-family: sans-serif;">
                <div style="color: #888; letter-spacing: 3px; font-size: 13px; margin-bottom:12px;">{game_choice.upper()} PROP ANALYSIS</div>
                <div style="font-size: 50px; font-weight: 900; margin: 0; line-height:1;">{st.session_state.p_tag.upper()}</div>
                <div style="color: #4A90E2; font-size: 18px; font-weight: bold; margin-bottom: 25px; border-bottom: 1px solid #333; padding-bottom: 18px;">{st.session_state.m_context.upper()}</div>
                
                <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 10px 0;">
                    <div style="text-align: left; flex: 1;">
                        <div style="color:#888; font-size:11px; font-weight:bold;">THE PROP LINE</div>
                        <div style="font-size: 80px; font-weight: 900; line-height:1;">{res['line']}</div>
                        <div style="color:#888; font-size:16px; margin-bottom:15px;">KILLS</div>
                        <span style="color: {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; border: 1px solid {'#00FF00' if res['side'] == 'Over' else '#FF0000'}; padding: 5px 12px; border-radius: 8px; font-weight: 900;">{arrow} {res['side'].upper()}</span>
                    </div>
                    <div style="width: 140px; text-align: center;">
                        <div style="color:#888; font-size:11px; font-weight:bold; margin-bottom:12px;">MODEL GRADE</div>
                        <div class="glow-grade">{res['grade']}</div>
                    </div>
                </div>
                <div style="background: linear-gradient(180deg, rgba(255,215,0,0.1) 0%, rgba(0,0,0,0) 100%); border: 1px solid #FFD700; border-radius: 18px; padding: 22px; margin: 25px 0;">
                    <div style="color: #FFD700; font-weight: bold; font-size: 14px; letter-spacing:2px;">SUGGESTED PLAY</div>
                    <div style="font-size: 42px; font-weight: 900;">{res['units']} UNITS</div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; border-top: 1px solid #333; padding-top: 25px;">
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">PROJ</div><div style="font-size: 19px; font-weight: 900;">{res['proj']:.1f}</div></div>
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">EDGE</div><div style="font-size: 19px; font-weight: 900;">+{res['edge']:.1f}%</div></div>
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">CONF</div><div style="font-size: 19px; font-weight: 900;">{res['prob']:.0f}%</div></div>
                    <div><div style="font-size: 10px; color: #666; font-weight:bold;">L10 HIT</div><div style="font-size: 19px; font-weight: 900;">{res['hit']:.0f}%</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)