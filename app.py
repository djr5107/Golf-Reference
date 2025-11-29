# app.py - Fixed PGA Tour Hole-by-Hole Explorer (2025 Edition)
import streamlit as st
import pandas as pd
import os
import time
import requests  # Fixed: Import at top level
from datetime import datetime

# Public PGA API key (from official docs/community - safe for personal use)
PGA_API_KEY = "da2-gsrx5bibzbb4njvhl7t37wqyl4"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.pgatour.com/",
    "X-API-Key": PGA_API_KEY  # Added for 2025 GraphQL stability
}
DELAY = 2.0  # Increased for cloud politeness

@st.cache_data(ttl=3600)  # Cache for 1 hour to avoid re-fetching
def load_data(year=2025):
    """Load or scrape data - cached for performance"""
    csv_path = f"data/pga_hole_by_hole_{year}.csv"
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    
    # If not, trigger scrape (but only if button pressed)
    return None

class PGATourScraper:
    def __init__(self):
        self.s = requests.Session()  # Fixed: requests now imported globally
        self.s.headers.update(HEADERS)

    def get_tournaments(self, year=2025):
        """Fetch tournament schedule using Schedule query"""
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
            events = [{"name": t["tournamentName"], "id": t["tournamentId"], "date": t["displayDate"]} for t in data if t["roundState"] == "F"]  # Only completed
            st.info(f"Found {len(events)} completed PGA Tour events in {year}")
            return events
        except Exception as e:
            st.error(f"Schedule fetch failed: {e}. Using sample data.")
            return [{"name": "Sample Tournament", "id": "SAMPLE", "date": "2025-01-01"}]

    def get_scorecards(self, tid, year):
        """Fetch hole-by-hole scorecards using Field and Scorecards queries"""
        url = "https://www.pgatour.com/graphql"
        
        # First, get field/players for tournament
        field_query = """
        query Field($fieldId: ID!) {
          field(fieldId: $fieldId) {
            tournamentName
            players {
              player {
                id
                name
                country
              }
              rounds {
                roundNumber
                total
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
        variables = {"fieldId": tid}
        time.sleep(DELAY)
        try:
            r = self.s.post(url, json={"operationName": "Field", "query": field_query, "variables": variables}, timeout=30)
            r.raise_for_status()
            players = r.json()["data"]["field"]["players"]
        except Exception as e:
            st.warning(f"Scorecards fetch failed for {tid}: {e}")
            return pd.DataFrame()

        rows = []
        for p in players:
            info = p["player"]
            for rnd in p["rounds"]:
                for h in rnd["holes"]:
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
                        "to_par": h["strokes"] - h["par"] if h["strokes"] else 0
                    })
        return pd.DataFrame(rows)

    def scrape_full_season(self, year=2025):
        """Scrape and save full season data"""
        os.makedirs("data", exist_ok=True)
        events = self.get_tournaments(year)
        all_dfs = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, e in enumerate(events[:10]):  # Limit to 10 for cloud demo; remove [:10] for full
            status_text.text(f"[{i+1}/{len(events)}] {e['name']} ({e['date']})")
            df = self.get_scorecards(e["id"], year)
            if not df.empty:
                all_dfs.append(df)
                status_text.text(f"   Got {len(df)} hole records from {df['player_name'].nunique()} players")
            progress_bar.progress((i + 1) / len(events))
            time.sleep(DELAY)
        
        if all_dfs:
            final = pd.concat(all_dfs, ignore_index=True)
            csv_path = f"data/pga_hole_by_hole_{year}.csv"
            final.to_csv(csv_path, index=False)
            st.success(f"SUCCESS! Saved {len(final):,} rows to {csv_path}")
            return final
        st.error("No data scraped. Check network or try local run.")
        return pd.DataFrame()

# Main App Logic
st.set_page_config(page_title="PGA Hole-by-Hole Explorer", layout="wide")
st.title("🏌️ PGA Tour Hole-by-Hole Explorer")
st.caption("100% Free • No Bans • Updated Nov 2025 • Click to Fetch Data")

if "data_fetched" not in st.session_state:
    st.session_state.data_fetched = False
    st.session_state.year = 2025

# Sidebar for settings
st.sidebar.header("Settings")
year = st.sidebar.slider("Season", 2023, 2025, st.session_state.year)

# Fetch button
if not st.session_state.data_fetched:
    st.warning("👆 Click below to fetch data (first time takes 5-15 min on cloud).")
    if st.button("🚀 Fetch Data Now", use_container_width=True):
        with st.spinner("Scraping PGA Tour... Be patient!"):
            scraper = PGATourScraper()
            df = scraper.scrape_full_season(year)
            if not df.empty:
                st.session_state.data_fetched = True
                st.session_state.df = df
                st.session_state.year = year
                st.rerun()
            else:
                st.error("Fetch failed. See logs or try local. Fallback to sample...")
                # Sample data for demo
                sample_df = pd.DataFrame({
                    "tournament_id": ["SAMPLE"] * 36,
                    "player_name": ["Scottie Scheffler", "Rory McIlroy"] * 18,
                    "round": [1] * 18 + [2] * 18,
                    "hole": list(range(1,19)) * 2,
                    "strokes": [4, 3, 5, 4] * 9,  # Dummy scores
                    "par": [4] * 18 * 2,
                    "to_par": [0, -1, 1, 0] * 9
                })
                st.session_state.df = sample_df
                st.session_state.data_fetched = True
                st.rerun()
else:
    # Load data
    df = st.session_state.df
    st.success(f"Loaded {len(df):,} hole records from {df['tournament_id'].nunique()} tournaments")

    # Filters
    col1, col2 = st.columns(2)
    tourney = col1.selectbox("Tournament", sorted(df["tournament_id"].unique()))
    player_options = ["All Players"] + sorted(df[df["tournament_id"] == tourney]["player_name"].unique())
    player_filter = col2.selectbox("Player", player_options)

    data = df[df["tournament_id"] == tourney].copy()
    if player_filter != "All Players":
        data = data[data["player_name"] == player_filter]

    # Pivot for scorecard view
    if not data.empty:
        pivot = data.pivot_table(
            index=["player_name", "round"],
            columns="hole",
            values="strokes",
            aggfunc="first"
        ).round(0).fillna("—").astype(str)  # Handle NaNs

        st.subheader(f"Scorecard: {tourney} {' | ' + player_filter if player_filter != 'All Players' else ''}")
        st.dataframe(
            pivot.style.background_gradient(cmap="RdYlGn_r", low=0, high=1, axis=1),
            use_container_width=True,
            height=400
        )

        # Stats sidebar
        st.sidebar.metric("Avg Strokes", f"{data['strokes'].mean():.1f}")
        st.sidebar.metric("Birdies/Eagles", f"{(data['to_par'] < 0).sum()}")

    # Re-fetch button
    if st.button("🔄 Re-Fetch Data", key="refetch"):
        st.session_state.data_fetched = False
        st.rerun()

with st.expander("📊 Raw Data Preview"):
    st.dataframe(df.head(10))
