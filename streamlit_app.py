import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
import os
import json
from groq import Groq
import re
from streamlit_gsheets import GSheetsConnection


@st.cache_data(ttl=10)
def load_vault():
    # 1. IMMEDIATE HEARTBEAT
    st.sidebar.info("🔍 Vault: Attempting Connection...")
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        # 2. ATTEMPT DATA PULL
        val_df = conn.read(worksheet="VAL_DATA")
        cs_df = conn.read(worksheet="CS2_DATA")
        
        # 3. SUCCESS MARKERS
        st.sidebar.success(f"✅ VAL Rows Found: {len(val_df)}")
        st.sidebar.success(f"✅ CS2 Rows Found: {len(cs_df)}")
        
        # Align Game Tags
        val_df['Game'] = 'Valorant'
        cs_df['Game'] = 'CS2'
        
        # Merge Schema
        for col in ['Team', 'Agents', 'ADR', 'ACS']:
            if col not in cs_df.columns: cs_df[col] = "N/A"
            
        return pd.concat([val_df, cs_df], ignore_index=True)
        
    except Exception as e:
        # 4. ERROR VISIBILITY
        st.sidebar.error(f"❌ Connection Failed")
        st.error(f"Detailed Error: {e}") # This shows on the main page
        return pd.DataFrame()
# ==========================================
# 🧠 INTELLIGENCE VAULT LOADER
# ==========================================
def load_intel():
    """Loads the external Brain from JSON with error protection"""
    if os.path.exists("intel_vault.json"):
        try:
            with open("intel_vault.json", "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            st.error("⚠️ Typo detected in intel_vault.json! App is using default logic.")
            return {}
    return {}

INTEL = load_intel()

# ==========================================
# 🎨 ELITE UI STYLING
# ==========================================
st.set_page_config(page_title="Prop Grader Elite", layout="wide", page_icon="🎯")
st.markdown("""<style>.main { background-color: #0e1117; } .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #238636; color: white; font-weight: bold; border: none; } .grade-card { padding: 30px; border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; margin-bottom: 20px; } .grade-text { font-size: 90px; font-weight: 900; margin: 0; line-height: 1; } .advice-box { background: #1c2128; padding: 15px; border-radius: 10px; border: 1px solid #30363d; font-size: 0.85rem; color: #58a6ff; margin-bottom: 10px; }</style>""", unsafe_allow_html=True)

def get_grade_details(edge):
    if edge >= 12.0: return "S", "linear-gradient(135deg, #FFD700, #FFA500)", "#FFD700", 2.5
    if edge >= 8.0: return "A+", "linear-gradient(135deg, #00FF00, #008000)", "#00FF00", 2.0
    if edge >= 3.0: return "A", "linear-gradient(135deg, #ADFF2F, #228B22)", "#ADFF2F", 1.0
    if edge >= 0.0: return "B", "linear-gradient(135deg, #F0E68C, #DAA520)", "#F0E68C", 0.5
    return "F", "linear-gradient(135deg, #8B0000, #000000)", "#FF4500", 0.0

def get_implied_prob(odds):
    return (abs(odds) / (abs(odds) + 100)) * 100 if odds < 0 else (100 / (odds + 100)) * 100

# ==========================================
# 📥 DATA & SESSION STATE
# ==========================================
states = {
    'h2h_val': 1.0, 'tier_val': 1.0, 'map_val': 1.0, 'int_val': 1.0, 
    'weight_advice': None, 'analysis_results': None, 
    'm_context_val': "Team vs Opponent", 'opp_rank_val': "N/A", 
    'expected_maps_val': "TBD", 'opening_val': "50%", 
    'map1_rate': "0.00", 'map2_rate': "0.00", 
    'last_player': None, 'p_tag_val': "donk", 'l10_val': "46, 33, 45", 
    'kpr_val': 0.90, 'stat_type_val': "Kills", 'role_val': "Rifler",
    'tourney_val': "S-Tier (Elite)" 
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

@st.cache_data(ttl=3600)
def load_vault():
    """Loads and merges the split CSV files from the V36 Miner"""
    val_path = "val_daily_stats.csv"
    cs_path = "cs_daily_stats.csv"
    
    dfs = []
    
    # Load Valorant Data
    if os.path.exists(val_path):
        v_df = pd.read_csv(val_path)
        v_df['Game'] = 'Valorant'
        dfs.append(v_df)
        
    # Load CS2 Data and align schema
    if os.path.exists(cs_path):
        c_df = pd.read_csv(cs_path)
        c_df['Game'] = 'CS2'
        # Add N/A for Valorant-only columns to prevent merge errors
        for col in ['Team', 'Agents', 'ADR', 'ACS']:
            if col not in c_df.columns:
                c_df[col] = "N/A" if col in ['Team', 'Agents'] else 0.0
        dfs.append(c_df)

    if not dfs:
        return pd.DataFrame(columns=["Player", "Game", "Team", "KPR", "L10", "Agents"])
        
    final_df = pd.concat(dfs, ignore_index=True)
    # Ensure L10 strings are clean
    if 'L10' in final_df.columns:
        final_df['L10'] = final_df['L10'].astype(str).str.replace('"', '')
    
    return final_df

# ==========================================
# ⚙️ SIDEBAR: THE AI ADVISOR
# ==========================================
with st.sidebar:
    st.header("⚙️ Model Intelligence")
    if st.button("GET AI SLIDER ADVICE"):
        api_key = st.secrets.get("GROQ_API_KEY")
        if not api_key: st.error("API Key missing.")
        else:
            client = Groq(api_key=api_key)
            match_parts = st.session_state.m_context_val.split(' vs ')
            p_team = match_parts[0].strip() if len(match_parts) > 0 else "Unknown"
            o_team = match_parts[1].strip() if len(match_parts) > 1 else "Opponent"
            
            maps_split = [m.strip() for m in st.session_state.expected_maps_val.split(',')]
            m1, m2 = maps_split[0] if len(maps_split) > 0 else "TBD", maps_split[1] if len(maps_split) > 1 else "TBD"
            
            with st.spinner(f"Analyzing {st.session_state.tourney_val}..."):
                prompt = f"""
                Act as a Cold, Professional Esports Betting Analyst. Temp 0.1.
                MATCHUP: {p_team} vs {o_team} (Rank: {st.session_state.opp_rank_val})
                TOURNAMENT: {st.session_state.tourney_val}
                PROP: {st.session_state.stat_type_val} | ROLE: {st.session_state.role_val}

                STRATEGIC CONTEXT:
                - {p_team}: {INTEL.get('team_styles', {}).get(p_team)}
                - {o_team}: {INTEL.get('team_styles', {}).get(o_team)}
                - ARCHETYPES: {INTEL.get('strat_archetypes', {})}

                MAP INTEL: {m1}: {INTEL.get('maps', {}).get(m1)} | {m2}: {INTEL.get('maps', {}).get(m2)}

                TASK:
                1. Assign 4 Weights (0.85-1.15) for H2H, Tier, Map, and Intensity.
                2. If teams are 'Economic Disciplinarians', penalize 'Intensity'.
                3. If teams are 'Force-Buy Aggressors', boost 'Intensity'.
                4. FORMAT: H2H: [X] | Tier: [X] | Map: [X] | Int: [X]
                """
                completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.0)
                st.session_state.weight_advice = completion.choices[0].message.content
                found_weights = re.findall(r"([0-1]\.\d+)", st.session_state.weight_advice)
                if len(found_weights) >= 4:
                    st.session_state.h2h_val = min(max(float(found_weights[0]), 0.80), 1.20)
                    st.session_state.tier_val = min(max(float(found_weights[1]), 0.80), 1.20)
                    st.session_state.map_val = min(max(float(found_weights[2]), 0.80), 1.20)
                    st.session_state.int_val = min(max(float(found_weights[3]), 0.70), 1.10)
                    st.toast("🎯 Full Vault Sync!", icon="✅")

    if st.session_state.weight_advice: st.markdown(f'<div class="advice-box"><b>Vault Intelligence:</b><br>{st.session_state.weight_advice}</div>', unsafe_allow_html=True)
    st.divider()
    st.slider("H2H Advantage", 0.80, 1.20, key="h2h_val", step=0.05)
    st.slider("Opponent Tier", 0.80, 1.20, key="tier_val", step=0.05)
    st.slider("Map Fit", 0.80, 1.20, key="map_val", step=0.05)
    st.slider("Match Intensity", 0.70, 1.10, key="int_val", step=0.05)

    st.divider()
    if st.sidebar.button("♻️ Refresh Vault Data"):
        st.cache_data.clear()
        st.toast("Database Refreshed!", icon="🔄")
        st.rerun()

# ==========================================
# 🎯 MAIN ANALYZER
# ==========================================
st.title("🎯 Prop Grader Elite")
df = load_vault()
st.write("### Debug: Raw Data from Cloud")
st.write(df) # This will show the actual table on your website
col_l, col_r = st.columns([1, 1.2], gap="large")

with col_l:
    st.subheader("📋 Prop & Context")
    game_choice = st.radio("Game", ["CS2", "Valorant"], horizontal=True)
    
    tourney_options = ["S-Tier (Elite)", "A-Tier (International)", "Regional/Season Games", "Qualifiers & Grassroots"]
    st.selectbox("Tournament Tier", options=tourney_options, key="tourney_val")

    cat_col, role_col = st.columns(2)
    with cat_col: st.radio("Stat Category", ["Kills", "Headshots"] if game_choice == "CS2" else ["Kills"], horizontal=True, key="stat_type_val")
    with role_col: 
        if game_choice == "CS2": st.radio("Player Role", ["Rifler", "AWPer"], horizontal=True, key="role_val")

    db_players = df[df['Game'] == game_choice]['Player'].tolist() if not df.empty else []
    selected_name = st.selectbox("Database Search", ["Manual Entry"] + db_players)
    
    if selected_name != st.session_state.last_player:
        if selected_name != "Manual Entry":
            p_row = df[df['Player'] == selected_name].iloc[0]
            st.session_state.p_tag_val = str(p_row['Player'])
            st.session_state.l10_val = str(p_row['L10'])
            st.session_state.kpr_val = float(p_row['KPR'])
            st.session_state.m_context_val = f"{p_row['Team']} vs "
        st.session_state.last_player = selected_name
        st.rerun()

    st.text_input("Player Tag", key="p_tag_val")
    st.text_input("Matchup Context", key="m_context_val")
    l10_raw = st.text_area(f"L10 {st.session_state.stat_type_val} Stats", key="l10_val")
    base_rate = st.number_input(f"Base {st.session_state.stat_type_val} Rate (KPR)", key="kpr_val", step=0.01)
    
    with st.expander("🧠 Deep Context", expanded=True):
        st.text_input("Opponent World Rank", key="opp_rank_val")
        st.text_input("Projected Maps", key="expected_maps_val")
        st.text_input("Opening Duel Success %", key="opening_val")

    c1, c2 = st.columns(2)
    with c1: m_line, m_side = st.number_input("Line", value=35.5, step=0.5), st.selectbox("Side", ["Over", "Under"])
    with c2: m_odds, m_scope = st.number_input("Odds", value=-128), st.selectbox("Scope", ["Maps 1 & 2", "Map 1 Only", "Full Match"])

if st.button("RUN ELITE ANALYSIS"):
    try:
        vals = [float(x.strip()) for x in l10_raw.split(",") if x.strip()]
        mean_v, stdev = np.mean(vals), max(np.std(vals, ddof=1) if len(vals) > 1 else 1.0, 1.0)
        cv, hit_rate = stdev / mean_v, (sum(1 for v in vals if (v > m_line if m_side == "Over" else v < m_line)) / len(vals)) * 100
        
        # Dynamic Multiplier: 26 for Val, 24 for CS2
        game_mult = 26 if game_choice == "Valorant" else 24
        mapping = {"Maps 1 & 2": 1.0, "Map 1 Only": 0.5, "Full Match": 1.25} # Weights for scope
        
        # Core Projection Logic
        proj = (base_rate * game_mult * mapping.get(m_scope, 1.0)) * st.session_state.h2h_val * st.session_state.tier_val * st.session_state.map_val * st.session_state.int_val
        
        prob_under = norm.cdf(m_line, loc=proj, scale=stdev)
        model_prob = (1 - prob_under) * 100 if m_side == "Over" else prob_under * 100
        edge = model_prob - get_implied_prob(m_odds)
        conf = min(max(((abs(edge) * 2) + (hit_rate * 0.4) - (cv * 120)), 0), 100)
        
        # Kelly Criterion sizing
        grade, color, flat, units = get_grade_details(edge)
        if cv > 0.25: units = max(0.5, units - 0.5)
        
        st.session_state.analysis_results = {
            "p_tag": st.session_state.p_tag_val, "matchup": st.session_state.m_context_val, 
            "side": m_side, "line": m_line, "grade": grade, "color": color, "flat": flat, 
            "units": units, "proj": proj, "edge": edge, "hit_rate": hit_rate, "conf": conf, 
            "game": game_choice, "stat_label": st.session_state.stat_type_val
        }
    except Exception as e: st.error(f"Analysis Error: {e}")

# ==========================================
# 📊 RENDERED SHARE CARD
# ==========================================
with col_r:
    if st.session_state.analysis_results:
        res = st.session_state.analysis_results
        p_name_up, m_info, side_up, line_val = res["p_tag"].upper(), res["matchup"], res["side"], res["line"]
        arrow_sym, arrow_hex = ("▲", "#00FF00") if side_up == "Over" else ("▼", "#FF4500")
        grade_grad = res.get('color', 'linear-gradient(135deg, #161b22, #0e1117)')
        
        st.markdown(f'''<div class="grade-card" style="background: {grade_grad}; color: white;"><div style="font-size: 28px; font-weight: 900;">{p_name_up}</div><div style="font-size: 14px; opacity: 0.8;">{m_info}</div><div style="font-size: 24px; margin-top: 10px; color: {arrow_hex}; font-weight: 900;">{arrow_sym} {side_up.upper()} {line_val} {res["stat_label"].upper()}</div><h1 class="grade-text">{res["grade"]}</h1><div style="font-size: 20px; font-weight: bold;">{res["units"]} UNIT PLAY</div></div>''', unsafe_allow_html=True)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Projected", f"{res['proj']:.1f}")
        m2.metric("Edge", f"{res['edge']:.1f}%")
        m3.metric("L10 Hit", f"{res['hit_rate']:.0f}%")
        m4.metric("Conf", f"{res['conf']:.0f}%")
        
        if st.checkbox("📸 Generate Social Share Card"):
            st.markdown(f"""<div style="background: linear-gradient(145deg, #0e1117 0%, #1c2128 100%); border: 3px solid {res['flat']}; border-radius: 20px; padding: 30px; max-width: 480px; color: white; margin: 10px auto; text-align: center; font-family: sans-serif;"><div style="border-bottom: 2px solid rgba(255,255,255,0.1); padding-bottom: 15px; margin-bottom: 20px;"><div style="font-size: 10px; color: #adbac7; text-transform: uppercase; letter-spacing: 3px;">{res['game']} {res['stat_label'].upper()} ANALYSIS</div><h2 style="margin: 5px 0; font-size: 38px; font-weight: 900;">{p_name_up}</h2><div style="color: #58a6ff; font-size: 14px; font-weight: bold;">{m_info}</div></div><div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;"><div style="flex: 1;"><div style="font-size: 13px; color: #adbac7; font-weight: bold;">THE LINE</div><div style="font-size: 60px; font-weight: 900; line-height: 0.9;">{line_val}</div><div style="font-size: 30px; font-weight: 900; color: {arrow_hex};">{arrow_sym} {side_up.upper()}</div></div><div style="flex: 1; text-align: right;"><div style="font-size: 13px; color: #adbac7; font-weight: bold;">MODEL GRADE</div><div style="font-size: 115px; font-weight: 900; background: {grade_grad}; -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 0.8;">{res['grade']}</div></div></div><div style="background: {grade_grad}; border-radius: 12px; padding: 18px; margin-bottom: 25px;"><div style="font-size: 36px; font-weight: 900;">{res['units']} UNIT PLAY</div></div><div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; border-top: 2px solid rgba(255,255,255,0.1); padding-top: 20px;"><div><div style="font-size: 10px; color: #adbac7;">PROJ</div><div style="font-size: 18px; font-weight: 900;">{res['proj']:.1f}</div></div><div><div style="font-size: 10px; color: #adbac7;">EDGE</div><div style="font-size: 18px; font-weight: 900; color: {res['flat']};">{res['edge']:.1f}%</div></div><div><div style="font-size: 10px; color: #adbac7;">L10 HIT</div><div style="font-size: 18px; font-weight: 900;">{res['hit_rate']:.0f}%</div></div><div><div style="font-size: 10px; color: #adbac7;">CONF</div><div style="font-size: 18px; font-weight: 900;">{res['conf']:.0f}%</div></div></div></div>""", unsafe_allow_html=True)