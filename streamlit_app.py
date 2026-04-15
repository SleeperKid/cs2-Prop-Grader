import streamlit as st
import pandas as pd
import os
from groq import Groq

# ==========================================
# 🎨 UI CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="S-Tier Prop Grader", 
    page_icon="🎯", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# FIXED: Removed the "name_with" typo from the parameter
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

st.title("🎯 S-Tier Prop Grader")
st.markdown("---")

# ==========================================
# 📥 DATA ENGINE
# ==========================================
@st.cache_data(ttl=600)
def load_vault():
    file_path = "daily_stats.csv"
    if not os.path.exists(file_path):
        return None
    
    try:
        df = pd.read_csv(file_path)
        if 'L10' in df.columns:
            df['L10'] = df['L10'].fillna("No Data").astype(str)
        return df
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return None

df = load_vault()

# ==========================================
# 🕹️ APP LOGIC
# ==========================================
if df is None:
    st.warning("⚠️ **Daily Vault Not Found.**")
    st.info("Please run `python miner.py` on your local machine to generate the data.")
    st.stop()

if df.empty:
    st.error("❌ The data file is empty. Run the miner again.")
    st.stop()

# --- Sidebar Filters ---
st.sidebar.header("🔍 Filter Vault")
game_choice = st.sidebar.selectbox("Choose Game", ["All Games", "CS2", "Valorant"])

filtered_df = df if game_choice == "All Games" else df[df['Game'] == game_choice]

# --- Main Selection ---
players = sorted(filtered_df['Player'].unique())
selected_player = st.selectbox("🎯 Select a Player to Grade:", players)

if selected_player:
    p_data = filtered_df[filtered_df['Player'] == selected_player].iloc[0]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Team", p_data['Team'])
    with col2:
        st.metric("Avg KPR", f"{p_data['BaseKPR']:.2f}")
    with col3:
        st.metric("Game", p_data['Game'])

    st.subheader("📊 Recent Match Performance")
    l10_list = p_data['L10'].split(", ")
    st.markdown(" ".join([f"` {val} `" for val in l10_list]))
    
    st.markdown("---")
    st.subheader("🤖 AI Performance Advisor")
    
    line_val = st.number_input(f"Enter the current line for {selected_player}:", min_value=1.0, max_value=100.0, value=32.5, step=0.5)
    
    if st.button("Generate S-Tier Analysis"):
        api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
        
        if not api_key:
            st.error("🔑 **Missing Groq API Key.**")
        else:
            try:
                client = Groq(api_key=api_key)
                prompt = f"""
                Analyze this {p_data['Game']} player: {selected_player}
                Team: {p_data['Team']}
                Base KPR: {p_data['BaseKPR']}
                Recent Totals: {p_data['L10']}
                Betting Line: {line_val}
                
                Provide a sharp betting recommendation (OVER, UNDER, or PASS).
                """
                
                with st.spinner("Analyzing stats..."):
                    chat_completion = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="llama3-8b-8192",
                    )
                    st.markdown(f"### Result:\n{chat_completion.choices[0].message.content}")
            except Exception as e:
                st.error(f"AI Error: {e}")

st.sidebar.markdown("---")
if st.sidebar.button("Force Clear Cache"):
    st.cache_data.clear()