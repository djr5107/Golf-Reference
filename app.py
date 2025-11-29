# app.py – Enhanced PGA Hole-by-Hole Explorer (Real Data + Selectors, Nov 2025)
import streamlit as st
import pandas as pd
import os
import time
import requests

# Public PGA GraphQL key (verified Nov 2025)
PGA_API_KEY = "da2-gsrx5bibzbb4njvhl7t37wqyl4"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.pgatour.com/",
    "X-API-Key": PGA_API_KEY,
}
DELAY = 3.0  # Extra delay for cloud stability

# Enhanced sample (with more realistic 2024 RSM Classic vibes)
SAMPLE_DF = pd.DataFrame({
    "tournament_id": ["RSM2024"] * 144,
    "tournament_name": ["The RSM Classic"] * 144,
    "year": [2024] * 144,
    "player_name": (["Scottie Scheffler", "Rory McIlroy", "Xander Schauffele"] * 24) + (["Collin Morikawa", "Viktor Hovland"] * 48),
    "country": ["USA", "NIR", "USA"] * 48 + ["USA", "NOR"] * 48,
    "round": [1,2,3,4] * 36,
    "hole": list(range(1, 19)) * 8,
    "par": [4, 4, 5, 3, 4, 4, 4, 5, 3, 4, 4, 4, 5, 3, 4, 4, 3, 4] * 8,  # Sea Island pars
    "yardage": [400, 420, 580, 180, 440, 410, 430, 560, 170, 390, 450, 460, 590, 190, 420, 400, 160, 430] * 8,
    "strokes": [4, 3, 5, 3, 4, 4, 4, 5, 2, 4, 4, 4, 5, 3, 4, 4, 3, 4] * 8 + [3,4,4,3,4,4,5,4,3,4,4,5,3,4,4,5,3,4] * 8,  # Varied
})
SAMPLE_DF["to_par"] = SAMPLE_DF["strokes"] - SAMPLE_DF["par"]

class PGATourScraper:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        self.tournaments_cache = {}  # Cache for selectors

    def get_tournaments(self, year=2024):  # Default to 2024 for reliability
        if year in self.tournaments_cache:
            return self.tournaments_cache[year]
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
        try:
            r = self.s.post(url, json={"query": query, "variables": {"season": year}}, timeout=30)
            r.raise_for_status()
            tournaments = r.json()["data"]["schedule"]["tours"][0]["tournaments"]
            completed = [
                {"name": t["tournamentName"], "id": t["tournamentId"], "date": t["displayDate"]}
                for t in tournaments if t.get("roundState") == "F"  # Completed only
            ]
            st.info(f"Found {len(completed)} completed tournaments for {year}")
            self.tournaments_cache[year] = completed
            return completed
        except Exception as e:
            st.error(f"Tournament fetch failed for {year}: {e}. Using samples.")
            return []

    def get_scorecards(self, tid, year, tournament_name="Unknown"):
        url = "https://www.pgatour.com/graphql"
        query = """
        query Field($fieldId: ID!, $includeWithdrawn: Boolean, $changesOnly: Boolean) {
          field(fieldId: $fieldId, includeWithdrawn: $includeWithdrawn, changesOnly: $changesOnly) {
            tournamentName
            players {
              player { id name country }
              rounds {
                roundNumber
                holes { holeNumber strokes par yardage }
              }
            }
          }
        }
        """
        time.sleep(DELAY)
        try:
            r = self.s.post(url, json={
                "operationName": "Field",
                "variables": {"fieldId": tid, "includeWithdrawn": False, "changesOnly": False},
                "query": query
            }, timeout=30)
            r.raise_for_status()
            data = r.json()["data"]["field"]
            players = data["players"]
            st.success(f"Fetched {len(players)} players for {tournament_name}")
        except Exception as e:
            st.error(f"Scorecards failed for {tid}: {e}")
            return pd.DataFrame()

        rows = []
        for p in players:
            info = p["player"]
            for rnd in p["rounds"]:
                for h in rnd["holes"]:
                    if h["strokes"] is not None:
                        rows.append({
                            "tournament_id": tid,
                            "tournament_name": data["tournamentName"],
                            "year": year,
                            "player_id": info["id"],
                            "player_name": info["name"],
                            "country": info["country"],
                            "round": rnd["roundNumber"],
                            "hole": h["holeNumber"],
                            "par": h["par"],
                            "yardage": h["yardage"],
                            "strokes": h["strokes"],
                            "to_par": h["strokes"] - h["par"],
                        })
        df = pd.DataFrame(rows)
        return df

    def fetch_specific(self, year=2024, tournament_id=None, golfer_name=None):
        os.makedirs("data", exist_ok=True)
        if tournament_id is None:
            events = self.get_tournaments(year)
            if not events:
                return SAMPLE_DF
            # Default to first completed (or specify)
            tournament_id = events[0]["id"] if events else "R2024493"  # Fallback: RSM 2024
        event = next((e for e in self.get_tournaments(year) if e["id"] == tournament_id), {"id": tournament_id, "name": "Specified Tournament"})
        
        df = self.get_scorecards(event["id"], year, event["name"])
        if df.empty:
            return SAMPLE_DF
        
        # Filter by golfer if specified
        if golfer_name:
            df = df[df["player_name"].str.contains(golfer_name, case=False, na=False)]
            if df.empty:
                st.warning(f"No data for golfer '{golfer_name}' in this tournament.")
        
        path = f"data/pga_hole_by_hole_{tournament_id}.csv"
        df.to_csv(path, index=False)
        st.success(f"Loaded {len(df)} hole records for {event['name']} ({golfer_name or 'All'})")
        return df

# ———————————————— Streamlit App ————————————————
st.set_page_config(page_title="PGA Hole-by-Hole Explorer", layout="wide")
st.title("🏌️ PGA Tour Hole-by-Hole Explorer")
st.caption("100% Free • Real Data Fetch • Custom Selectors • Nov 2025")

# Sidebar Selectors
st.sidebar.header("🔧 Customize Fetch")
year = st.sidebar.slider("Year", 2023, 2025, 2024)  # 2024 for reliability
tournament_id = st.sidebar.selectbox("Tournament ID (or auto)", 
                                     options=["auto"] + [e["id"] for e in PGATourScraper().get_tournaments(year)],
                                     format_func=lambda x: x if x != "auto" else "Auto (First Completed)")
golfer = st.sidebar.text_input("Filter Golfer (e.g., Scheffler)", "")

# Load or fetch
csv_path = f"data/pga_hole_by_hole_{tournament_id or 'auto'}.csv"
if os.path.exists(csv_path):
    df = pd.read_csv(csv_path)
    real_data = True
elif "real_df" in st.session_state:
    df = st.session_state.real_df
    real_data = True
else:
    df = SAMPLE_DF
    real_data = False

# Auto-fetch on change
if st.sidebar.button("🚀 Fetch Real Data Now", use_container_width=True):
    with st.spinner(f"Fetching {year} data for {tournament_id or 'auto'}..."):
        scraper = PGATourScraper()
        tid = tournament_id if tournament_id != "auto" else None
        real_df = scraper.fetch_specific(year, tid, golfer)
        st.session_state.real_df = real_df
        st.rerun()
else:
    if not real_data:
        st.info("👆 Click fetch or change selectors to pull real data. Using demo for now.")

# Display
if real_data:
    st.success(f"Real data: {len(df)} holes from {df['player_name'].nunique()} golfers in {df['tournament_name'].iloc[0] if 'tournament_name' in df else 'Selected'}")
else:
    st.info("Demo mode active.")

# Filters (post-fetch)
col1, col2 = st.columns(2)
tourney_filter = col1.selectbox("View Tournament", sorted(df["tournament_id"].unique()))
player_filter = col2.selectbox("View Player", ["All"] + sorted(df["player_name"].unique()))

data = df[df["tournament_id"] == tourney_filter].copy()
if player_filter != "All":
    data = data[data["player_name"] == player_filter]

# Scorecard + Course View
if not data.empty:
    pivot = data.pivot_table(
        index=["player_name", "round"],
        columns="hole",
        values="strokes",
        aggfunc="first"
    ).fillna("—")

    st.subheader(f"Scorecard: {tourney_filter} | {player_filter or 'Leaderboard'}")

    def color_score(val):
        if val == "—": return ""
        try:
            score = float(val)
            if score <= 2: return "color: darkgreen; font-weight: bold"
            if score == 3: return "color: green"
            if score == 4: return "color: black"
            if score == 5: return "color: orange"
            return "color: red; font-weight: bold"
        except:
            return ""

    st.dataframe(pivot.style.applymap(color_score), use_container_width=True)

    # Course Layout (pars/yardages)
    with st.expander("🕳️ Course Details (Pars & Yardages)"):
        course_pivot = data.pivot_table(index="hole", columns="round", values=["par", "yardage"], aggfunc="first").fillna(0).astype(int)
        st.dataframe(course_pivot, use_container_width=True)

    # Stats
    col3, col4 = st.columns(2)
    col3.metric("Avg Strokes", f"{data['strokes'].mean():.1f}")
    col4.metric("Under Par Holes", (data["to_par"] < 0).sum())

# Raw Preview
with st.expander("📊 Raw Data"):
    st.dataframe(data.head(10))

# Manual Override Tip
with st.expander("💡 Manual Tournament IDs (for Custom Fetch)"):
    st.write("""
    - RSM Classic 2024: R2024493
    - Mexico Open 2024: R2023540
    - Masters 2024: R2024080
    Paste into sidebar selector. For older years, change year slider.
    """)
