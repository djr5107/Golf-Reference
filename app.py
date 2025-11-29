# app.py – Free Kaggle + GitHub PGA Hole-by-Hole Explorer (2009–2025)
import streamlit as st
import pandas as pd
import os
import requests
from io import StringIO

# Free sources
KAGGLE_2015_2022_URL = "https://www.kaggle.com/datasets/robikscube/pga-tour-golf-data-20152022/download"  # Manual download fallback
GITHUB_CLEANED_CSV = "https://raw.githubusercontent.com/daronprater/PGA-Tour-Data-Science-Project/master/pgatour_cleaned.csv"
GITHUB_PGA_STATS = "https://raw.githubusercontent.com/upjohnc/Golf-Statistics/master/data/PGA%20Stats.csv"

DELAY = 1.0

# Sample fallback (144 rows)
SAMPLE_DF = pd.DataFrame({
    "tournament_name": ["Demo Open"] * 144,
    "year": [2025] * 144,
    "player_name": (["Scottie Scheffler"] * 18 + ["Rory McIlroy"] * 18) * 4,
    "round": [1,2,3,4] * 36,
    "hole": list(range(1, 19)) * 8,
    "par": [4, 4, 5, 3, 4, 4, 4, 5, 3, 4, 4, 4, 5, 3, 4, 4, 3, 4] * 8,
    "strokes": [4, 3, 5, 3, 4, 4, 4, 5, 2, 4, 4, 4, 5, 3, 4, 4, 3, 4] * 8,
})
SAMPLE_DF["to_par"] = SAMPLE_DF["strokes"] - SAMPLE_DF["par"]

@st.cache_data(ttl=3600)
def load_kaggle_data(year_range="2015-2022"):
    """Load/merge Kaggle + GitHub CSVs"""
    os.makedirs("data", exist_ok=True)
    merged_path = "data/merged_pga_holes.csv"
    if os.path.exists(merged_path):
        return pd.read_csv(merged_path)
    
    dfs = []
    
    # GitHub: 2010-2017 (daronprater)
    try:
        r = requests.get(GITHUB_CLEANED_CSV, timeout=30)
        df_github = pd.read_csv(StringIO(r.text))
        df_github = df_github[['tournament', 'player_name', 'round', 'hole', 'par', 'strokes', 'sg_total']].copy()
        df_github['year'] = 2010  # Approx; filter by year in app
        df_github['tournament_name'] = df_github['tournament']
        df_github['to_par'] = df_github['strokes'] - df_github['par']
        dfs.append(df_github)
        st.info("Loaded GitHub 2010-2017 data")
    except Exception as e:
        st.warning(f"GitHub load failed: {e}")
    
    # Kaggle: 2015-2022 (robikscube) - Use direct if CLI not avail
    # For cloud: Assume user uploads CSV or use sample; local: os.system("kaggle datasets download -d robikscube/pga-tour-golf-data-20152022 -p data --unzip")
    try:
        # Placeholder: Load from local 'data/pga_tour_2015_to_2022.csv' (user download)
        if os.path.exists("data/pga_tour_2015_to_2022.csv"):
            df_kaggle = pd.read_csv("data/pga_tour_2015_to_2022.csv")
            df_kaggle = df_kaggle[['tournament_name', 'year', 'player_name', 'round', 'hole', 'score', 'par', 'sg_total']].rename(columns={'score': 'strokes'})
            df_kaggle['to_par'] = df_kaggle['strokes'] - df_kaggle['par']
            dfs.append(df_kaggle)
            st.info("Loaded Kaggle 2015-2022 data")
    except Exception as e:
        st.warning(f"Kaggle load failed (download manually): {e}")
    
    # GitHub: Additional stats (2004-2020)
    try:
        r = requests.get(GITHUB_PGA_STATS, timeout=30)
        df_stats = pd.read_csv(StringIO(r.text))
        # Assume columns like 'tournament', 'player', 'hole', 'strokes', 'par'
        df_stats['year'] = 2010  # Filter later
        df_stats['tournament_name'] = df_stats.get('tournament', 'Unknown')
        df_stats['player_name'] = df_stats.get('player', 'Unknown')
        df_stats['to_par'] = df_stats['strokes'] - df_stats['par']
        dfs.append(df_stats)
        st.info("Loaded additional GitHub stats")
    except Exception as e:
        st.warning(f"Stats load failed: {e}")
    
    if dfs:
        merged = pd.concat(dfs, ignore_index=True).drop_duplicates()
        merged.to_csv(merged_path, index=False)
        return merged
    return SAMPLE_DF

# ———————————————— Streamlit App ————————————————
st.set_page_config(page_title="PGA Hole-by-Hole Explorer", layout="wide")
st.title("🏌️ Free PGA Tour Hole-by-Hole Explorer (Kaggle + GitHub)")
st.caption("2009–2022 Historical • Merge Datasets • No Costs")

# Sidebar
st.sidebar.header("Load Data")
year = st.sidebar.slider("Filter Year", 2009, 2025, 2022)
if st.sidebar.button("📥 Download & Merge Free Datasets"):
    with st.spinner("Fetching from Kaggle/GitHub..."):
        df = load_kaggle_data()
        st.session_state.df = df
        st.rerun()

# Load data
if "df" not in st.session_state:
    df = SAMPLE_DF
else:
    df = st.session_state.df
    df = df[df['year'] == year]  # Filter

st.success(f"Loaded {len(df)} hole records from {df['player_name'].nunique()} players")

# Filters
col1, col2 = st.columns(2)
tourney = col1.selectbox("Tournament", sorted(df["tournament_name"].unique()))
golfer = col2.selectbox("Golfer", ["All"] + sorted(df["player_name"].unique()))

data = df[(df["tournament_name"] == tourney) & (df["player_name"] == golfer) if golfer != "All" else (df["tournament_name"] == tourney)].copy()

# Scorecard
if not data.empty:
    pivot = data.pivot_table(index="round", columns="hole", values="strokes", aggfunc="first").fillna("—")

    st.subheader(f"Scorecard: {tourney} ({year}) | {golfer}")
    def color_score(val):
        if val == "—": return ""
        v = float(val)
        if v <= 3: return "color: green; font-weight: bold"
        if v == 4: return "color: black"
        return "color: red"
    st.dataframe(pivot.style.applymap(color_score), use_container_width=True)

    col1, col2 = st.columns(2)
    col1.metric("Avg Strokes", f"{data['strokes'].mean():.1f}")
    col2.metric("Birdies", (data["to_par"] < 0).sum())

# Course
with st.expander("Course (Pars/Yardages)"):
    course = data.groupby("hole")["par"].mean().round(0)
    st.bar_chart(course)

# Raw
with st.expander("Raw Data"):
    st.dataframe(data.head(10))

st.info("💡 Download Kaggle CSVs manually to 'data/' folder for full load. For 2023–2025, use GitHub scrapers locally.")
