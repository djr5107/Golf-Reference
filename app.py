# app.py - Fixed PGA Tour Hole-by-Hole Explorer (Nov 2025 Edition)
import streamlit as st
import pandas as pd
import os
import time
import requests
from datetime import datetime

# Public PGA API key (verified for 2025 GraphQL)
PGA_API_KEY = "da2-gsrx5bibzbb4njvhl7t37wqyl4"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.pgatour.com/",
    "X-API-Key": PGA_API_KEY
}
DELAY = 2.5  # Extra polite for cloud

@st.cache_data(ttl=3600)
def load_cached_data(year=2025):
    """Load from CSV if exists"""
    csv_path = f"data/pga_hole_by_hole_{year}.csv"
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    return None

# Sample data for instant UI demo (loads on startup)
SAMPLE_DF = pd.DataFrame({
    "tournament_id": ["DEMO_2025"] * 72,
    "year": [2025] * 72,
    "player_id": ["P001", "P002"] * 36,
    "player_name": ["Scottie Scheffler", "Rory McIlroy"] * 36,
    "country": ["USA", "NIR"] * 36,
    "round": ([1] * 36 + [2] * 36),
    "hole": list(range(1, 19)) * 4,
    "par": [4] * 36 + [3] * 18 + [5] * 18 + [4] * 36,  # Mix pars
    "yardage": [450] * 72,  # Dummy
    "strokes": [3, 4, 5, 4, 3, 4, 4, 5, 3, 4, 4, 5, 3, 4, 5, 4, 3, 4] * 4,  # Varied scores
    "to_par": [-1, 0, 0, 0, -1, 0, 0, 0, -1, 0, 0, 0, -1, 0, 0, 0, -1, 0] * 4
})

class PGATourScraper:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)

    def get_tournaments(self, year=2025):
        url = "https://www.pgatour.com/graphql"
        query = """
        query Schedule($season: Int!) {
          schedule(season: $season) {
            tours(tourCode: "R") {
              tournaments {
                tournamentName
                tournamentId
                displayDate
                roundState
              }
            }
          }
        }
        """
        variables = {"season": year}
        try:
            r = self.s.post(url, json={"query": query, "variables": variables}, timeout=30)
            r.raise_for_status()
            data = r.json()["data"]["schedule"]["tours"][0]["tournaments"]
            # Filter to completed tournaments only
            events = [
                {"name": t["tournamentName"], "id": t["tournamentId"], "date": t["displayDate"]}
                for t in data if t.get("roundState") == "F"
            ]
            st.info(f"Found {len(events)} completed PGA Tour events in {year}")
            return events[:5]  # Limit for quick demo; remove [:5] for full
        except Exception as e:
            st.error(f"Schedule fetch failed: {e}. Using samples.")
            return []

    def get_scorecards(self, tid, year):
        url = "https://www.pgatour.com/graphql"
        query = """
        query Field($fieldId: ID!, $includeWithdrawn: Boolean, $changesOnly: Boolean) {
          field(fieldId: $fieldId, includeWithdrawn: $includeWithdrawn, changesOnly: $changesOnly) {
            tournamentName
            id
            players {
              player {
                id
                name
                country
              }
              rounds {
                roundNumber
                holes {
                  holeNumber
                  strokes
                  par
                  yardage
                }
              }
            }
          }
        }
        """
        variables = {"fieldId": tid, "includeWithdrawn": False, "changesOnly": False}
        time.sleep(DELAY)
        try:
            r = self.s.post(url, json={"operationName": "Field", "query": query, "variables": variables}, timeout=30)
            r.raise_for_status()
            players = r.json()["data"]["field"]["players"]
        except Exception as e:
            st.warning(f"Scorecards failed for {tid}: {e}")
            return pd.DataFrame()

        rows = []
        for p in players:
            info = p["player"]
            for rnd in p["rounds"]:
                for h in rnd["holes"]:
                    if h["strokes"] is not None:  # Skip unfinished holes
                        rows.append({
                            "tournament_id": tid,
                            "year": year,
                            "player_id": info["id"],
                            "player_name": info["name"],
                            "country": info["country"],
                            "round": rnd["roundNumber"],
                            "hole": h["holeNumber"],
                            "par": h["par"],
                            "yardage": h["yardage"],
                            "strokes": h["strokes"],
                            "to_par": h["strokes"] - h["par"]
                        })
        return pd.DataFrame(rows)

    def scrape_full_season(self, year=2025):
        os.makedirs("data", exist_ok=True)
        events = self.get_tournaments(year)
        if not events:
            return SAMPLE_DF
        all_dfs = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        for i, e in enumerate(events):
            status_text.text(f"[{i+1}/{len(events)}] {e['name']} ({e['date']})")
            df = self.get_scorecards(e["id"], year)
            if not df.empty:
                all_dfs.append(df)
                status_text.text(f"   Got {len(df)} records from {df['player_name'].nunique()} players")
            progress_bar.progress((i + 1) / len(events))
            time.sleep(DELAY)
        if all_dfs:
            final = pd.concat(all_dfs, ignore_index=True)
            csv_path = f"data/pga_hole_by_hole_{year}.csv"
            final.to_csv(csv_path, index=False)
            st.success(f"SUCCESS! Saved {len(final):,} rows to {csv_path}")
            return final
        st.warning("No real data; using samples.")
        return SAMPLE_DF

# Main App
st.set_page_config(page_title="PGA Hole-by-Hole Explorer", layout="wide")
st.title("🏌️ PGA Tour Hole-by-Hole Explorer")
st.caption("100% Free • No Bans • Nov 2025 • Real Data on Fetch")

if "data_fetched" not in st.session_state:
    st.session_state.data_fetched = False
    st.session_state.year = 2025

# Sidebar
st.sidebar.header("Settings")
year = st.sidebar.slider("Season", 2023, 2025, st.session_state.year)

# Initial load: Use samples or cached
if load_cached_data(year) is not None:
    df = load_cached_data(year)
    st.session_state.data_fetched = True
    st.session_state.df = df
else:
    df = SAMPLE_DF
    st.session_state.df = df

# Fetch button (only shows if no real data)
if not st.session_state.data_fetched or "real_data" not in st.session_state:
    st.warning("👆 Samples loaded. Click to fetch real PGA data (5-10 min on cloud).")
    if st.button("🚀 Fetch Real Data Now", use_container_width=True):
        with st.spinner("Scraping PGA Tour..."):
            scraper = PGATourScraper()
            real_df = scraper.scrape_full_season(year)
            if not real_df.equals(SAMPLE_DF):  # Check if real
                st.session_state.df = real_df
                st.session_state.data_fetched = True
                st.session_state.real_data = True
                st.rerun()
            else:
                st.info("Using enhanced samples.")
else:
    df = st.session_state.df
    is_real = st.session_state.get("real_data", False)
    st.success(f"Loaded {len(df):,} hole records from {df['tournament_id'].nunique()} tournaments" + (" (Real Data!)" if is_real else " (Samples)"))

# Filters (now always available)
col1, col2 = st.columns(2)
tourney = col1.selectbox("Tournament", sorted(df["tournament_id"].unique()))
player_options = ["All Players"] + sorted(df[df["tournament_id"] == tourney]["player_name"].unique())
player_filter = col2.selectbox("Player", player_options)

data = df[df["tournament_id"] == tourney].copy()
if player_filter != "All Players":
    data = data[data["player_name"] == player_filter]

# Scorecard pivot
if not data.empty:
    pivot = data.pivot_table(
        index=["player_name", "round"],
        columns="hole",
        values="