import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os
import json
from groq import Groq
import re
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 📥 DATA & INTELLIGENCE LOADERS
# ==========================================
def load_intel():
    """Loads player-specific tactical notes from JSON"""
    if os.path.exists("intel_vault.json"):
        try:
            with open("intel_vault.json", "r") as f:
                return json.load(f)
        except: return {}
    return {}

@st.cache_data(ttl=600)
def load_vault():
    """THE BULLETPROOF VAULT: Connects to Google Sheets"""
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        val_df = conn.read(spreadsheet=sheet_url, worksheet="VAL_DATA", ttl=0)
        cs_df = conn.read(spreadsheet=sheet_url, worksheet="CS2_DATA", ttl=0)
        
        val_df['Game'] = 'Valorant'
        cs_df['Game'] = 'CS2'
        
        for col in ['Team', 'Agents', 'ADR', 'ACS']:
            if col not in cs_df.columns: cs_df[col] = "N/A"
            if col not in val_df.columns: val_df[col] = "N/A"
            
        return pd.concat([val_df, cs_df], ignore_index=True).fillna("N/A")
    except Exception as e:
        st.error(f"Vault Connection Error: {e}")
        return pd.DataFrame()

# ==========================================
# 🎨 UI STYLING
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide", page_icon="🎯")
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .grade-card { padding: 30px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.1); text-align: center; }
    .grade-text { font-size: 100px; font-weight: 900; margin: 0; line-height: 1; }
    .intel-box { background: #1c2128; padding: 20px; border-radius: 10px; border-left: 5px solid #58a6ff; margin: 10px 0; }
    .context-box { background: #161b22; padding: 15px; border-radius: 8px; border: 1px solid #30363d; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ SIDEBAR: AI ADVISOR & SLIDER GUIDE
# ==========================================
with st.sidebar:
    st.title("🛡️ Elite Command")
    
    # 🧠 AI ADVISOR (GROQ RESTORED)
    st.subheader("🤖 AI Match Advisor")
    m_context = st.text_input("Match Context", placeholder="e.g. FaZe vs G2 (Playoffs)")
    
    if st.button("CONSULT AI ADVISOR"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if not api_key: st.error("Missing GROQ_API_KEY in Secrets.")
        else:
            client = Groq(api_key=api_key)
            with st.spinner("Analyzing match variables..."):
                prompt = f"Analyze {m_context}. Suggest 4 weights (0.85-1.15) for: H2H, Opponent Tier, Map Fit, Match Intensity. Format: H2H: X | Tier: X | Map: X | Int: X. Explain why briefly."
                completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                st.session_state.ai_advice = completion.choices[0].message.content
    
    if "ai_advice" in st.session_state:
        st.info(st.session_state.ai_advice)

    st.divider()
    
    # 🎚️ SLIDERS
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, 1.0, help="1.10 = 10% boost for favorable player matchup")
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, 1.0, help="0.90 = 10% reduction vs Elite/S-Tier teams")
    map_w = st.slider("Map Fit", 0.80, 1.20, 1.0, help="Adjust based on player's comfort on current map")
    int_w = st.slider("Match Intensity", 0.70, 1.10, 1.0, help="Low (0.8) for groups, High (1.1) for Grand Finals")

    st.divider()
    
    # 📖 SLIDER STRATEGY GUIDE (RESTORED)
    with st.expander("📖 SLIDER STRATEGY GUIDE"):
        st.markdown("""
        **H2H Advantage:** - Bump up if player historically 'owns' this opponent.
        - Bump down if facing a 'nemesis' (e.g., ZywOo vs s1mple).
        
        **Opponent Tier:**
        - **1.10+:** vs Tier 2/3 teams (Stat padding).
        - **0.90:** vs Top 5 World Ranked teams.
        
        **Map Fit:**
        - Check recent HLTV/VLR map stats. Bump up for 'Comfort' maps (e.g., Mirage for NiKo).
        
        **Intensity:**
        - **0.85:** Meaningless seeding matches.
        - **1.05:** Major Playoffs / High Stakes.
        """)

# ==========================================
# 📥 INITIALIZE
# ==========================================
INTEL = load_intel()
df = load_vault()

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
st.title("🎯 Prop Grader Elite")

if df.empty:
    st.error("Vault empty. Check GSheets connection.")
else:
    col_l, col_r = st.columns([1, 1.2], gap="large")

    with col_l:
        st.subheader("📋 Input Scenario")
        game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)
        
        db_players = df[df['Game'] == game_choice]['Player'].tolist()
        selected_name = st.selectbox("Database Search", ["Manual Entry"] + db_players)
        
        # Data Selection Logic
        if selected_name != "Manual Entry":
            p_row = df[df['Player'] == selected_name].iloc[0]
            p_tag = p_row['Player']
            l10_data = str(p_row['L10']).replace('"', '')
            base_kpr = float(p_row['KPR'])
            p_team = p_row.get('Team', 'N/A')
            p_agents = p_row.get('Agents', 'N/A')
        else:
            p_tag = st.text_input("Player Tag")
            l10_data = st.text_area("L10 (CSV)")
            base_kpr = st.number_input("Base KPR", 0.80)
            p_team, p_agents = "N/A", "N/A"

        c1, c2 = st.columns(2)
        with c1:
            m_line = st.number_input("Line", 35.5, step=0.5)
            m_side = st.selectbox("Side", ["Over", "Under"])
        with c2:
            m_odds = st.number_input("Odds", -115)
            m_scope = st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

        # 🧬 DEEP PROFILE BOX (RESTORED)
        if p_tag in INTEL:
            st.markdown(f"""
            <div class="intel-box">
                <b>🔍 Vault Intelligence: {p_tag}</b><br>
                {INTEL[p_tag].get('notes', 'No deep notes found.')}
            </div>
            """, unsafe_allow_html=True)

    if st.button("🚀 CALCULATE ELITE GRADE"):
        try:
            # MATH ENGINE
            vals = [float(x.strip()) for x in l10_data.split(",") if x.strip()]
            stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 2.0, 2.0)
            game_mult = 26 if game_choice == "Valorant" else 24
            scope_map = {"Maps 1 & 2": 1.0, "Map 1 Only": 0.5, "Full Match": 1.3}
            
            # Weighted Projection
            base_proj = base_kpr * game_mult * scope_map[m_scope]
            final_proj = base_proj * h2h_w * rank_w * map_w * int_w
            
            # Probabilities
            prob_under = norm.cdf(m_line, loc=final_proj, scale=stdev)
            model_prob = (1 - prob_under) * 100 if m_side == "Over" else prob_under * 100
            
            implied = (abs(m_odds) / (abs(m_odds) + 100)) * 100 if m_odds < 0 else (100 / (m_odds + 100)) * 100
            edge = model_prob - implied
            
            # Grades
            if edge >= 12: g, c, u = "S", "linear-gradient(135deg, #FFD700, #FFA500)", 2.5
            elif edge >= 8: g, c, u = "A+", "linear-gradient(135deg, #00FF00, #008000)", 2.0
            elif edge >= 3: g, c, u = "A", "linear-gradient(135deg, #ADFF2F, #228B22)", 1.0
            else: g, c, u = "B", "#1c2128", 0.5

            with col_r:
                # 🃏 GRADE CARD
                st.markdown(f"""
                <div class="grade-card" style="background: {c}; color: white;">
                    <div style="font-size: 20px; font-weight: bold;">{p_tag.upper()} {m_side.upper()} {m_line}</div>
                    <h1 class="grade-text">{g}</h1>
                    <div style="font-size: 24px; font-weight: bold;">{u} UNIT PLAY</div>
                </div>
                """, unsafe_allow_html=True)

                # 🗺️ PROJECTED MAP CONTEXTUAL BOX (RESTORED)
                st.markdown(f"""
                <div class="context-box">
                    <b>🗺️ Projection Logic Breakdown:</b><br>
                    • Baseline ({m_scope}): <b>{base_proj:.1f}</b><br>
                    • Weighted Adjustments: <b>x{(h2h_w*rank_w*map_w*int_w):.2f}</b><br>
                    • Final Elite Projection: <b>{final_proj:.1f} Kills</b>
                </div>
                """, unsafe_allow_html=True)

                st.divider()
                m1, m2, m3 = st.columns(3)
                m1.metric("Edge", f"{edge:.1f}%")
                m2.metric("Model Prob", f"{model_prob:.1f}%")
                m3.metric("L10 Hit", f"{(sum(1 for v in vals if (v > m_line if m_side == 'Over' else v < m_line))/len(vals)*100):.0f}%")

                # 🤳 SOCIAL SHARE
                st.subheader("🤳 Share Card")
                st.code(f"🎯 PROP GRADER ELITE\n🔥 {p_tag.upper()} {m_side.upper()} {m_line}\n📊 GRADE: {g}\n💰 UNITS: {u}\n📈 EDGE: {edge:.1f}%")

        except Exception as e: st.error(f"Error: {e}")