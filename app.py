# app.py
import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime

# Paste the ENTIRE PGATourScraper class and related code from pga_scraper.py here
# (I'll inline it below for convenience)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.pgatour.com/"
}
DELAY = 1.5

class PGATourScraper:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)

    def get_tournaments(self, year=2025):
        import requests
        url = "https://www.pgatour.com/graphql"
        query = """query Schedule($season: Int!){schedule(season:$season){tours{tourCode tournaments{tournamentName tournamentId displayDate roundState}}}}"""
        r = self.s.post(url, json={"query": query, "variables": {"season": year}})
        tours = r.json()["data"]["schedule"]["tours"]
        events = []
        for t in tours:
            if t["tourCode"] == "R":
                for e in t["tournaments"]:
                    events.append({"name": e["tournamentName"], "id": e["tournamentId"], "date": e["displayDate"]})
        st.write(f"Found {len(events)} PGA Tour events in {year}")
        return events

    def get_scorecards(self, tid, year):
        import requests
        url = "https://www.pgatour.com/graphql"
        query = """query TournamentScorecards($tournamentId:ID!,$year:Int!){tournamentScorecards(tournamentId:$tournamentId,year:$year){players{player{id name country}rounds{roundNumber holes{holeNumber strokes par yardage}}}}}}"""
        time.sleep(DELAY)
        try:
            r = self.s.post(url, json={"query": query, "variables": {"tournamentId": tid, "year": year}})
            players = r.json()["data"]["tournamentScorecards"]["players"]
        except:
            st.write("   No data (probably ongoing or no ShotLink)")
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
                        "to_par": h["strokes"] - h["par"]
                    })
        return pd.DataFrame(rows)

    def scrape_full_season(self, year=2025):
        os.makedirs("data", exist_ok=True)
        events = self.get_tournaments(year)
        all_dfs = []
        progress_bar = st.progress(0)
        for i, e in enumerate(events):
            status_text = st.empty()
            status_text.text(f"[{i+1}/{len(events)}] {e['name']} ({e['date']})")
            df = self.get_scorecards(e["id"], year)
            if not df.empty:
                all_dfs.append(df)
                status_text.text(f"   Got {len(df)} hole records from {df['player_name'].nunique()} players")
            progress_bar.progress((i + 1) / len(events))
        if all_dfs:
            final = pd.concat(all_dfs, ignore_index=True)
            final.to_csv(f"data/pga_hole_by_hole_{year}.csv", index=False)
            st.success(f"SUCCESS! Saved {len(final):,} rows to data/pga_hole_by_hole_{year}.csv")
            return final
        return pd.DataFrame()

# Main App
st.set_page_config(page_title="PGA Hole-by-Hole Explorer", layout="wide")
st.title("PGA Tour Hole-by-Hole Explorer")
st.caption("100% free • Local data • No bans • Updated 2025")

if "data_fetched" not in st.session_state:
    st.session_state.data_fetched = False

# Fetch data button (runs scraper if needed)
if not st.session_state.data_fetched:
    st.warning("No data found yet! Click below to fetch the latest PGA Tour data (takes ~10-20 min).")
    if st.button("🚀 Fetch 2025 Season Data Now", use_container_width=True):
        with st.spinner("Scraping PGA Tour data... This is a one-time process."):
            scraper = PGATourScraper()
            df = scraper.scrape_full_season(2025)
            if not df.empty:
                st.session_state.data_fetched = True
                st.session_state.df = df
                st.rerun()
            else:
                st.error("Failed to fetch data. Try again or check console logs.")
else:
    # Load and display data
    if "df" in st.session_state:
        df = st.session_state.df
    else:
        # Fallback load if session state cleared
        if os.path.exists("data"):
            files = [f for f in os.listdir("data") if f.endswith(".csv")]
            if files:
                latest = sorted(files)[-1]
                df = pd.read_csv(f"data/{latest}")
                st.session_state.df = df
            else:
                st.error("CSV missing after fetch. Refresh and try again.")
                st.stop()
        else:
            st.error("Data folder missing. Click 'Fetch Data' again.")
            st.stop()

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

    # Button to re-fetch if needed
    if st.button("🔄 Re-fetch Latest Data", key="refetch"):
        st.session_state.data_fetched = False
        st.rerun()
