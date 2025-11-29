# pga_scraper.py
import requests, pandas as pd, time, os
from datetime import datetime

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
        url = "https://www.pgatour.com/graphql"
        query = """query Schedule($season: Int!){schedule(season:$season){tours{tourCode tournaments{tournamentName tournamentId displayDate roundState}}}}"""
        r = self.s.post(url, json={"query": query, "variables": {"season": year}})
        tours = r.json()["data"]["schedule"]["tours"]
        events = []
        for t in tours:
            if t["tourCode"] == "R":
                for e in t["tournaments"]:
                    events.append({"name": e["tournamentName"], "id": e["tournamentId"], "date": e["displayDate"]})
        print(f"Found {len(events)} PGA Tour events in {year}")
        return events

    def get_scorecards(self, tid, year):
        url = "https://www.pgatour.com/graphql"
        query = """query TournamentScorecards($tournamentId:ID!,$year:Int!){tournamentScorecards(tournamentId:$tournamentId,year:$year){players{player{id name country}rounds{roundNumber holes{holeNumber strokes par yardage}}}}}}"""
        time.sleep(DELAY)
        try:
            r = self.s.post(url, json={"query": query, "variables": {"tournamentId": tid, "year": year}})
            players = r.json()["data"]["tournamentScorecards"]["players"]
        except:
            print("   No data (probably ongoing or no ShotLink)")
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
        for i, e in enumerate(events):
            print(f"\n[{i+1}/{len(events)}] {e['name']} ({e['date']})")
            df = self.get_scorecards(e["id"], year)
            if not df.empty:
                all_dfs.append(df)
                print(f"   Got {len(df)} hole records from {df['player_name'].nunique()} players")
        if all_dfs:
            final = pd.concat(all_dfs, ignore_index=True)
            final.to_csv(f"data/pga_hole_by_hole_{year}.csv", index=False)
            print(f"\nSUCCESS! Saved {len(final):,} rows to data/pga_hole_by_hole_{year}.csv")
            return final
        return pd.DataFrame()

if __name__ == "__main__":
    scraper = PGATourScraper()
    scraper.scrape_full_season(2025)   # Change year if you want older seasons
