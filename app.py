# app.py
import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="PGA Hole-by-Hole Explorer", layout="wide")
st.title("PGA Tour Hole-by-Hole Explorer")
st.caption("100% free • Local data • No bans • Updated 2025")

if not os.path.exists("data"):
    st.error("No data found! First run: python pga_scraper.py")
    st.stop()

files = [f for f in os.listdir("data") if f.endswith(".csv")]
if not files:
    st.error("No CSV files in data folder. Run the scraper first!")
    st.stop()

latest = sorted(files)[-1]
df = pd.read_csv(f"data/{latest}")

st.success(f"Loaded {len(df):,} hole records from {df['tournament_id'].nunique()} tournaments")

col1, col2 = st.columns(2)
tourney = col1.selectbox("Tournament", sorted(df["tournament_id"].unique()))
player_filter = col2.selectbox("Player (optional)", ["All Players"] + sorted(df[df["tournament_id"]==tourney]["player_name"].unique()))

data = df[df["tournament_id"] == tourney]
if player_filter != "All Players":
    data = data[data["player_name"] == player_filter]

pivot = data.pivot_table(
    index=["player_name", "round"],
    columns="hole",
    values="strokes",
    aggfunc="first"
).reset_index().fillna("—")

st.subheader(f"{' → '.join(player_filter.split()) if player_filter != 'All Players' else 'Leaderboard'}")
st.dataframe(
    pivot.style.background_gradient(cmap="RdYlGn_r", low=5, high=3),
    use_container_width=True
)

with st.expander("Raw data table"):
    st.dataframe(data)
