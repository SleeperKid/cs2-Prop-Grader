import streamlit as st
import pandas as pd
import os
from groq import Groq

# ==========================================
# 🎨 S-TIER UI OVERHAUL
# ==========================================
st.set_page_config(page_title="S-Tier Prop Grader", page_icon="🎯", layout="wide")

# Custom CSS for that Dark Mode "Pro" Feel
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    div[data-testid="stExpander"] { background-color: #161b22; border: none; }
    </style>
    """, unsafe_allow_html=True)

st.title("🎯 S-Tier Prop Grader")
st.caption("v2.1 Build | Hybrid Data Pipeline Active")
st.markdown("---")

# ==========================================
# 📥 DATA LOADING
# ==========================================
def load_data():
    if not os.path.exists("daily_stats.csv"):
        st.error("❌ 'daily_stats.csv' not found. Run miner.py on your desk!")
        return None
    df = pd.read_csv("daily_stats.csv")
    return df

df = load_data()

# ==========================================
# 🕹️ APP FEATURES
# ==========================================
if df is not None:
    # Sidebar Search & Filter
    st.sidebar.header("🔍 Filter Vault")
    game_filter = st.sidebar.selectbox("Select Game", ["All", "CS2", "Valorant"])
    
    filtered_df = df if game_filter == "All" else df[df['Game'] == game_filter]
    
    # Hero Section: Player Selection
    players = sorted(filtered_df['Player'].unique())
    selected_player = st.selectbox("Search for a Player:", players)
    
    if selected_player:
        p_data = filtered_df[filtered_df['Player'] == selected_player].iloc[0]
        
        # FEATURE 1: Professional Metric Cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Team", p_data['Team'])
        with col2:
            st.metric("Base KPR", f"{p_data['BaseKPR']:.2f}")
        with col3:
            st.metric("Expected Maps", p_data['ExpectedMaps'])
        with col4:
            st.metric("Game", p_data['Game'])

        # FEATURE 2: Clean Performance History
        st.subheader("📊 Recent Match Performance")
        st.info(f"Last 10 Match Totals (Maps 1 & 2): **{p_data['L10']}**")
        
        # FEATURE 3: AI Analysis Logic
        st.markdown("---")
        st.subheader("🤖 AI Performance Advisor")
        
        line_input = st.number_input(f"Enter the betting line for {selected_player}:", value=32.5, step=0.5)
        
        if st.button("Generate S-Tier Analysis"):
            api_key = st.secrets.get("GROQ_API_KEY")
            
            if not api_key:
                st.warning("🔑 API Key not found in Streamlit Secrets!")
            else:
                client = Groq(api_key=api_key)
                with st.spinner("Analyzing data via Llama-3..."):
                    try:
                        prompt = f"""
                        Analyze {selected_player} ({p_data['Game']}). 
                        Team: {p_data['Team']} | Base KPR: {p_data['BaseKPR']}
                        Recent Totals: {p_data['L10']}
                        Betting Line: {line_input}
                        
                        Provide a concise recommendation: OVER, UNDER, or PASS and explain why in 2 sentences.
                        """
                        completion = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama3-8b-8192",
                        )
                        st.success("Analysis Complete")
                        st.write(completion.choices[0].message.content)
                    except Exception as e:
                        st.error(f"AI Error: {e}")