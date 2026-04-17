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
# 📊 THE MATH ENGINE (VERIFIED & OPTIMIZED)
# ==========================================
# Calculations use the Normal Distribution (Gaussian) model:
# 1. Projection = (Base KPR * Game Multiplier * Scope) * (W1 * W2 * W3 * W4)
# 2. Probability = 1 - norm.cdf(Line, loc=Proj, scale=Stdev) [for Over]
# 3. Edge = Model Probability - Implied Probability (from Bookie Odds)

def get_implied_prob(odds):
    if odds < 0:
        return (abs(odds) / (abs(odds) + 100)) * 100
    return (100 / (odds + 100)) * 100

def get_grade_details(edge):
    """Restored High-Detail Grade mapping"""
    if edge >= 12.0: return "S", "linear-gradient(135deg, #FFD700, #FFA500)", "#FFD700", 2.5, "ELITE VALUE"
    if edge >= 8.0:  return "A+", "linear-gradient(135deg, #00FF00, #008000)", "#00FF00", 2.0, "STRONG PLAY"
    if edge >= 3.0:  return "A", "linear-gradient(135deg, #ADFF2F, #228B22)", "#ADFF2F", 1.0, "VALUE PLAY"
    if edge >= 0.0:  return "B", "linear-gradient(135deg, #F0E68C, #DAA520)", "#F0E68C", 0.5, "MARGINAL"
    return "F", "linear-gradient(135deg, #8B0000, #000000)", "#FF4500", 0.0, "NO VALUE"

# ==========================================
# 📥 CLOUD VAULT LOADER
# ==========================================
@st.cache_data(ttl=300)
def load_vault():
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        val_df = conn.read(spreadsheet=sheet_url, worksheet="VAL_DATA", ttl=0)
        cs_df = conn.read(worksheet="CS2_DATA", ttl=0) # Trying direct for CS2
        
        val_df['Game'] = 'Valorant'
        cs_df['Game'] = 'CS2'
        
        # Schema Normalization
        for col in ['Team', 'Agents', 'ADR', 'ACS']:
            if col not in cs_df.columns: cs_df[col] = "N/A"
            if col not in val_df.columns: val_df[col] = "N/A"
            
        return pd.concat([val_df, cs_df], ignore_index=True).fillna("N/A")
    except Exception as e:
        st.error(f"Vault Connection Error: {e}")
        return pd.DataFrame()

# ==========================================
# 🎨 UI & STYLING (RESTORATION)
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide", page_icon="🎯")
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .grade-card { padding: 30px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.1); text-align: center; }
    .grade-text { font-size: 100px; font-weight: 900; margin: 0; line-height: 1; }
    .share-card { background: #1c2128; padding: 20px; border-radius: 10px; border: 1px dashed #30363d; font-family: monospace; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ SIDEBAR & CHEAT SHEET
# ==========================================
with st.sidebar:
    st.title("🛡️ Pro Cheat Sheet")
    st.table(pd.DataFrame({
        "Grade": ["S", "A+", "A", "B"],
        "Edge": ["12%+", "8-12%", "3-8%", "0-3%"],
        "Units": ["2.5u", "2.0u", "1.0u", "0.5u"]
    }))
    
    st.divider()
    st.header("⚙️ Model Weights")
    h2h_w = st.slider("H2H Advantage", 0.80, 1.20, 1.0)
    rank_w = st.slider("Opponent Tier", 0.80, 1.20, 1.0)
    map_w = st.slider("Map Fit", 0.80, 1.20, 1.0)
    int_w = st.slider("Match Intensity", 0.70, 1.10, 1.0)
    
    st.divider()
    df = load_vault()
    if not df.empty:
        v_count = len(df[df['Game'] == 'Valorant'])
        c_count = len(df[df['Game'] == 'CS2'])
        st.success(f"📡 Vault Live: {v_count} VAL | {c_count} CS2")

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
st.title("🎯 Prop Grader Elite")

col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("📋 Input Scenarios")
    game_choice = st.radio("Target Game", ["CS2", "Valorant"], horizontal=True)
    
    db_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected_name = st.selectbox("Quick-Load Player", ["Manual Entry"] + db_players)
    
    # Auto-fill logic
    p_tag = st.text_input("Player Tag", value=selected_name if selected_name != "Manual Entry" else "")
    
    # Context Logic
    l10_val = ""
    kpr_val = 0.80
    if selected_name != "Manual Entry":
        row = df[df['Player'] == selected_name].iloc[0]
        l10_val = str(row['L10']).replace('"', '')
        kpr_val = float(row['KPR'])

    l10_raw = st.text_area("L10 Performance (CSV)", value=l10_val)
    base_kpr = st.number_input("Base KPR", value=kpr_val, step=0.01)
    
    c1, c2 = st.columns(2)
    with c1:
        m_line = st.number_input("Bookie Line", value=35.5, step=0.5)
        m_side = st.selectbox("Side", ["Over", "Under"])
    with c2:
        m_odds = st.number_input("Odds (American)", value=-115)
        m_scope = st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match (BO3)"])

if st.button("🚀 GENERATE ELITE GRADE"):
    try:
        # 1. Parse L10
        vals = [float(x.strip()) for x in l10_raw.split(",") if x.strip()]
        mean_l10 = np.mean(vals)
        stdev = max(np.std(vals, ddof=1) if len(vals) > 1 else 2.0, 2.0)
        
        # 2. Multipliers
        game_mult = 26 if game_choice == "Valorant" else 24
        scope_map = {"Maps 1 & 2": 1.0, "Map 1 Only": 0.5, "Full Match (BO3)": 1.3}
        
        # 3. Calculation
        proj = (base_kpr * game_mult * scope_map[m_scope]) * h2h_w * rank_w * map_w * int_w
        
        # 4. Probability Logic
        prob_under = norm.cdf(m_line, loc=proj, scale=stdev)
        model_prob = (1 - prob_under) * 100 if m_side == "Over" else prob_under * 100
        
        edge = model_prob - get_implied_prob(m_odds)
        grade, color, text_c, units, label = get_grade_details(edge)
        hit_rate = (sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line)) / len(vals)) * 100

        with col_r:
            # --- GRADE CARD ---
            st.markdown(f"""
                <div class="grade-card" style="background: {color};">
                    <div style="color: white; font-size: 20px; font-weight: bold; opacity: 0.9;">{label}</div>
                    <div style="color: white; font-size: 32px; font-weight: 900;">{p_tag.upper()} {m_side.upper()} {m_line}</div>
                    <h1 class="grade-text" style="color: white;">{grade}</h1>
                    <div style="color: white; font-size: 24px; font-weight: bold;">{units} UNIT PLAY</div>
                </div>
            """, unsafe_allow_html=True)
            
            # --- DATA GRID ---
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Projected", f"{proj:.1f}")
            m2.metric("Model Prob", f"{model_prob:.1f}%")
            m3.metric("Edge", f"{edge:.1f}%", delta=f"{edge:.1f}%")
            
            m4, m5, m6 = st.columns(3)
            m4.metric("L10 Hit Rate", f"{hit_rate:.0f}%")
            m5.metric("Volatility (SD)", f"{stdev:.1f}")
            m6.metric("Implied", f"{get_implied_prob(m_odds):.1f}%")
            
            # --- SHARE CARD ---
            st.subheader("🤳 Social Share Card")
            share_text = f"🎯 PROP GRADER ELITE\n🔥 {p_tag.upper()} {m_side.upper()} {m_line}\n📊 GRADE: {grade}\n💰 UNIT PLAY: {units}\n📈 EDGE: {edge:.1f}%\n🤖 Projections by Llama-3.3"
            st.code(share_text, language="text")
            st.info("👆 Copy the code block above to share your play!")

    except Exception as e:
        st.error(f"Calculation Error: {e}. Ensure L10 data is valid.")