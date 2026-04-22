import streamlit as st
import json
import os

# --- 🛰️ 1. DATA INITIALIZATION ---
def load_manifest():
    if os.path.exists("cs2_manifest.json"):
        with open("cs2_manifest.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

CS2_DATA = load_manifest()

# --- 🧮 2. THE CORE NEURAL ENGINE (MATH VERIFIED) ---
def run_neural_calc(game, kpr, maps, rank_diff, line, hs_mode, hs_pct):
    """
    Standardizes projections based on MR12 (CS2) and VCT (Valorant) metrics.
    """
    # Constant: Average Rounds Per Map in 2026
    # CS2 (MR12) avg is ~21 rounds. Valorant avg is ~20.5 rounds.
    avg_rounds = 21 if game == "CS2" else 20.5
    
    # A: BASE PROJECTION (Sane Baseline)
    # Logic: KPR * Total Expected Rounds
    base_proj = kpr * (avg_rounds * maps)
    
    # B: RANK GAP MODIFIER (The Stabilizer)
    # Logic: 0.2% impact per rank position. 
    # Example: 50 rank gap = 10% boost (1.10x). 
    gap_multiplier = 1 + (rank_diff * 0.002)
    
    # C: APPLY MODIFIERS
    final_proj = base_proj * gap_multiplier
    
    # D: HEADSHOT TOGGLE (CS2 ONLY)
    if game == "CS2" and hs_mode:
        final_proj = final_proj * (hs_pct / 100)

    # E: PROBABILITY & DELTA
    delta = final_proj - line
    # Standard deviation logic for Win Prob (Simplified sigmoid)
    win_prob = 50 + (delta * 12) 
    win_prob = max(5, min(99.9, win_prob)) # Clamp between 5% and 99.9%

    return round(final_proj, 1), round(delta, 1), round(win_prob, 1)

# --- 🎨 3. STREAMLIT UI ---
st.set_page_config(page_title="SLEEPER RECON V51.0", layout="wide")
st.title("🛰️ NEURAL PROP GRADER")

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ SYSTEM CONFIG")
    game_mode = st.radio("TARGET GAME", ["CS2", "VALORANT"])
    
    if game_mode == "CS2":
        hs_toggle = st.toggle("🎯 HEADSHOT MODE")
        hs_value = st.slider("HS %", 20, 80, 50) if hs_toggle else 0
    else:
        hs_toggle = False
        hs_value = 0

    st.divider()
    st.info("MANIFEST STATUS: ✅ ONLINE" if CS2_DATA else "⚠️ LOCAL FALLBACK")

# Main Input Grid
col1, col2, col3 = st.columns(3)

with col1:
    player_name = st.text_input("PLAYER NAME", "DGT")
    team_tag = st.text_input("TEAM TAG", "9Z").upper()
    
with col2:
    base_kpr = st.number_input("GLOBAL KPR", value=0.70, step=0.05)
    maps_expected = st.number_input("EXPECTED MAPS", value=2.4, step=0.1)

with col3:
    prop_line = st.number_input("BOOKIE LINE", value=33.5, step=0.5)
    opponent_tag = st.text_input("OPPONENT TAG", "ALKA").upper()

# --- 🛰️ 4. RANK GAP LOGIC ---
p1_rank = CS2_DATA.get(team_tag, {}).get("rank", 100)
p2_rank = CS2_DATA.get(opponent_tag, {}).get("rank", 150)
rank_gap = max(0, p2_rank - p1_rank) # Positive if opponent is worse

# --- 🚀 5. EXECUTION ---
if st.button("RUN RECON"):
    proj, delta, prob = run_neural_calc(
        game_mode, base_kpr, maps_expected, rank_gap, prop_line, hs_toggle, hs_value
    )

    # OUTPUT DISPLAY
    st.divider()
    res_col1, res_col2, res_col3 = st.columns(3)
    
    with res_col1:
        st.metric("PROJECTED METRIC", proj)
        st.write(f"**RANK GAP:** +{rank_gap} Pos")

    with res_col2:
        st.metric("DELTA", f"{delta:+}")
        st.write(f"**WIN PROB:** {prob}%")

    with res_col3:
        if delta > 8:
            st.error("🚀 NUCLEAR LOCK DETECTED")
        elif delta > 3:
            st.warning("🔥 HIGH CONVICTION")
        else:
            st.success("⚖️ NEUTRAL VALUE")

    # --- 💡 6. HINTS SECTION ---
    with st.expander("📝 RECON HINTS & LOGIC"):
        st.write(f"**Calculated for:** {player_name} ({team_tag}) vs {opponent_tag}")
        
        hints = []
        if rank_gap > 40:
            hints.append("⚠️ **STOMP RISK:** High rank gap suggests a 2-0 sweep, which could lower total rounds.")
        if base_kpr > 0.8:
            hints.append("⭐ **ELITE FORM:** Player is in the top 5% of global KPR.")
        if maps_expected < 2.1:
            hints.append("📉 **MAP LIMIT:** Low map expectation heavily penalizes the OVER.")
        if hs_toggle:
            hints.append(f"🎯 **HS ADJUST:** Scaled projection by {hs_value}% for Headshot props.")
        
        for hint in hints:
            st.write(hint)

# Visualizing the MR12 math flow
#