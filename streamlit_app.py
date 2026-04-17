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
    """Loads the deep strategy database"""
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
# 🎨 ARCHITECT UI STYLING
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
    .grade-card { 
        padding: 40px; border-radius: 30px; text-align: center; 
        box-shadow: 0 15px 45px rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.15);
    }
    .grade-text { font-size: 130px; font-weight: 900; margin: 0; line-height: 1; color: white !important; }
    .intel-box { 
        background: linear-gradient(90deg, rgba(88,166,255,0.1) 0%, rgba(13,17,23,0) 100%); 
        padding: 20px; border-radius: 12px; border-left: 5px solid #58a6ff; margin-bottom: 20px;
    }
    .map-logic-box { 
        background: #1c2128; padding: 20px; border-radius: 15px; 
        border: 1px solid #30363d; margin-top: 15px; color: #adbac7; line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 STATE MANAGEMENT
# ==========================================
df = load_vault()
INTEL = load_intel()

keys = ['p_tag', 'l10', 'kpr', 'm_context', 'w_rank', 'results', 'ai_advice', 'tourney_type']
for key in keys:
    if key not in st.session_state: st.session_state[key] = "" if key != 'kpr' else 0.80

# ==========================================
# ⚙️ SIDEBAR: AI & SLIDERS
# ==========================================
with st.sidebar:
    st.title("🛡️ Command Center")
    
    # 🏆 TOURNAMENT DROPDOWN (RESTORED)
    st.session_state.tourney_type = st.selectbox(
        "Tournament Prestige", 
        ["S-Tier (Major/Elite)", "A-Tier (Pro League)", "B-Tier (Regional)", "Qualifiers", "Showmatch"],
        index=0
    )

    st.subheader("🤖 AI Match Advisor")
    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if api_key:
            client = Groq(api_key=api_key)
            # Pull DEEP Intel for AI
            player_intel = INTEL.get(st.session_state.p_tag, {})
            
            prompt = f"""
            SYSTEM ROLE: Pro Esports Betting Analyst (Temp: 0.01).
            CONTEXT: {st.session_state.m_context} | Tournament: {st.session_state.tourney_type} | Opponent Rank: {st.session_state.w_rank}.
            
            DEEP DATA ACCESS:
            - Player Strategy/Archetype: {player_intel.get('archetype', 'Standard')}
            - Team Playstyle: {player_intel.get('team_style', 'Balanced')}
            - Map Explanations: {player_intel.get('map_notes', 'N/A')}
            - Extra Scouting: {player_intel.get('notes', 'None')}

            TASK: Suggest 4 weights (0.85-1.15) for: H2H, Tier, Map, Intensity.
            REQUIREMENT: For each slider, provide EXACTLY 4 sentences explaining how the Strategy Archetype and Tournament Type influenced your decision.
            """
            
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile", 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.01
            )
            st.session_state.ai_advice = completion.choices[0].message.content
    
    if st.session_state.ai_advice: st.info(st.session_state.ai_advice)
    
    st.divider()
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, 1.0)
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, 1.0)
    map_w = st.slider("Map Fit", 0.80, 1.20, 1.0)
    int_w = st.slider("Match Intensity", 0.70, 1.10, 1.0)

    with st.expander("📖 SLIDER STRATEGY GUIDE"):
        st.write("**H2H:** Boost for specific counter-strat archetypes.")
        st.write("**Tier:** Adjust based on Tournament Tier (S-Tier = lower KPR variance).")
        st.write("**Map:** Use intel-vault map explanations.")

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
st.title("🎯 Prop Grader Elite")

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    # 🧬 DEEP PROFILE SECTION (FULLY INTEGRATED)
    if st.session_state.p_tag in INTEL:
        p_data = INTEL[st.session_state.p_tag]
        st.markdown(f"""
        <div class="intel-box">
            <span style="color:#58a6ff;font-weight:bold;font-size:1.1rem;">🔍 {st.session_state.p_tag.upper()} STRATEGY PROFILE</span><br>
            <small style="color:#8b949e;">ARCHETYPE: {p_data.get('archetype', 'N/A')} | STYLE: {p_data.get('team_style', 'N/A')}</small>
            <p style="color:#adbac7;margin-top:10px;">{p_data.get('notes', '')}</p>
        </div>
        """, unsafe_allow_html=True)

    st.subheader("📋 Scenario Input")
    game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)
    
    db_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected = st.selectbox("Database Search", ["Manual Entry"] + db_players)
    
    if selected != "Manual Entry":
        row = df[df['Player'] == selected].iloc[0]
        st.session_state.p_tag, st.session_state.l10 = row['Player'], str(row['L10']).replace('"', '')
        st.session_state.kpr, st.session_state.m_context = float(row['KPR']), f"{row.get('Team', 'Team')} vs "

    st.session_state.p_tag = st.text_input("Player Tag", value=st.session_state.p_tag)
    st.session_state.m_context = st.text_input("Match Context", value=st.session_state.m_context)
    st.session_state.w_rank = st.text_input("Opponent World Rank", value=st.session_state.w_rank)
    st.session_state.l10 = st.text_area("L10 Data", value=st.session_state.l10)
    st.session_state.kpr = st.number_input("Base KPR", value=st.session_state.kpr)

    c1, c2 = st.columns(2)
    with c1: m_line, m_side = st.number_input("Line", 35.5, step=0.5), st.selectbox("Side", ["Over", "Under"])
    with c2: m_odds, m_scope = st.number_input("Odds", -115), st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

if st.button("🚀 RUN ELITE ANALYSIS"):
    vals = [float(x.strip()) for x in st.session_state.l10.split(",") if x.strip()]
    stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 2.5, 2.5)
    game_mult = 26 if game_choice == "Valorant" else 24
    scope_map = {"Maps 1 & 2": 1.0, "Map 1 Only": 0.5, "Full Match": 1.3}
    
    base_proj = st.session_state.kpr * game_mult * scope_map[m_scope]
    final_proj = base_proj * h2h_w * rank_w * map_w * int_w
    prob = (1 - norm.cdf(m_line, loc=final_proj, scale=stdev)) * 100 if m_side == "Over" else norm.cdf(m_line, loc=final_proj, scale=stdev) * 100
    edge = prob - ((abs(m_odds)/(abs(m_odds)+100))*100 if m_odds < 0 else (100/(m_odds+100))*100)
    
    grad = "linear-gradient(135deg, #FFD700 0%, #8B6508 100%)" if edge >= 12 else "linear-gradient(135deg, #00FF00 0%, #004d00 100%)" if edge >= 8 else "linear-gradient(135deg, #ADFF2F 0%, #228B22 100%)" if edge >= 3 else "linear-gradient(135deg, #2c3e50 0%, #000000 100%)"
    st.session_state.results = {"grad": grad, "grade": "S" if edge >= 12 else "A+" if edge >= 8 else "A" if edge >= 3 else "B", "units": 2.5 if edge >= 12 else 2.0 if edge >= 8 else 1.0 if edge >= 3 else 0.5, "proj": final_proj, "base": base_proj, "edge": edge, "prob": prob, "vals": vals, "m_line": m_line, "m_side": m_side, "scope": m_scope}

# --- RESULTS DISPLAY ---
if st.session_state.results:
    res = st.session_state.results
    with col_r:
        st.markdown(f"""<div class="grade-card" style="background: {res['grad']};">
            <div style="font-size:20px; font-weight:bold; color:white;">{st.session_state.tourney_type.upper()}</div>
            <div style="font-size:34px; font-weight:900; color:white;">{st.session_state.p_tag.upper()} {res['m_side'].upper()} {res['m_line']}</div>
            <h1 class="grade-text">{res['grade']}</h1>
            <div style="font-size:28px; font-weight:bold; color:white;">{res['units']} UNIT PLAY</div>
        </div>""", unsafe_allow_html=True)

        # 🗺️ PROJECTED MAPS LOGIC BOX (RESTORED)
        st.markdown(f"""
        <div class="map-logic-box">
            <b style="color:#58a6ff; font-size:1.1rem;">🗺️ PROJECTED MAPS LOGIC:</b><br>
            • <b>Scope Selection:</b> {res['scope']}<br>
            • <b>KPR Baseline:</b> {st.session_state.kpr:.2f} over {game_mult} projected rounds.<br>
            • <b>Math:</b> ({st.session_state.kpr:.2f} KPR × {game_mult} Rnds) × {scope_map[res['scope']]} Scope.<br>
            • <b>Multipliers:</b> x{(h2h_w*rank_w*map_w*int_w):.2f} (Weights applied).<br>
            • <b>Final Projection:</b> <span style="color:white; font-weight:bold;">{res['proj']:.1f} Total Kills</span>
        </div>
        """, unsafe_allow_html=True)

        st.divider()
        show_share = st.checkbox("Show Social Share Card")
        if show_share:
            st.code(f"🎯 PROP GRADER ELITE\n🔥 {st.session_state.p_tag.upper()} {res['m_side'].upper()} {res['m_line']}\n📊 GRADE: {res['grade']}\n📈 EDGE: {res['edge']:.1f}%\n🏆 {st.session_state.tourney_type}")