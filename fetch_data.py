#!/usr/bin/env python3
"""
Economic Signal Fetcher - SerpAPI Google Trends + FRED
"""
import json, os, requests, time
from datetime import datetime

FRED_KEY    = os.environ.get("FRED_API_KEY", "")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
OUT_FILE    = "data/trends_data.json"

TRENDS_TERMS = {
    "jobs": {
        "label": "Jobs Market", "color": "#00CC99",
        "terms": ["how to find a job", "how to get unemployment", "layoffs", "job search", "how to file for unemployment"]
    },
    "consumer_spending": {
        "label": "Consumer Spending", "color": "#4da6ff",
        "terms": ["how to save money", "buy now pay later", "cancel subscription", "grocery budget", "coupon codes"]
    },
    "financial_stress": {
        "label": "Financial Stress", "color": "#ff7b54",
        "terms": ["how to pay off debt", "bankruptcy", "debt consolidation", "payday loan", "credit card debt"]
    },
    "economic_sentiment": {
        "label": "Economic Sentiment", "color": "#c77dff",
        "terms": ["recession", "inflation", "cost of living", "economy getting worse", "economic collapse"]
    },
    "housing": {
        "label": "Housing / Real Estate", "color": "#f9c74f",
        "terms": ["how to buy a house", "mortgage rates", "rent prices", "affordable housing", "eviction"]
    },
}

FRED_SERIES = [
    ("ICSA",        "Initial Jobless Claims",  "Thousands"),
    ("UNRATE",      "Unemployment Rate",        "%"),
    ("CPIAUCSL",    "CPI Inflation",            "Index"),
    ("UMCSENT",     "Consumer Sentiment",       "Index"),
    ("MORTGAGE30US","30-Yr Mortgage Rate",      "%"),
    ("HOUST",       "Housing Starts",           "K Units"),
    ("RSAFS",       "Retail Sales",             "M $"),
    ("DRCCLACBS",   "Credit Card Delinquency",  "%"),
]

def calc_trend(values):
    if len(values) < 14: return "flat"
    r = sum(values[-7:]) / 7
    p = sum(values[-14:-7]) / 7
    if p == 0: return "flat"
    pct = (r - p) / p
    return "up" if pct > 0.05 else ("down" if pct < -0.05 else "flat")

def fetch_trends_serpapi():
    print("\n── Google Trends (SerpAPI) ──")
    if not SERPAPI_KEY:
        print("  No SERPAPI_KEY — skipping")
        return {}

    categories_out = {}

    for cat_key, cat in TRENDS_TERMS.items():
        print(f"  [{cat['label']}]")
        term_data = {}

        for term in cat["terms"]:
            try:
                r = requests.get("https://serpapi.com/search", params={
                    "engine":       "google_trends",
                    "q":            term,
                    "geo":          "US",
                    "date":         "today 3-m",
                    "data_type":    "TIMESERIES",
                    "api_key":      SERPAPI_KEY,
                }, timeout=15)
                data = r.json()

                timeline = data.get("interest_over_time", {}).get("timeline_data", [])
                if not timeline:
                    print(f"    Empty: {term}")
                    continue

                dates, values = [], []
                for point in timeline:
                    dates.append(point["date"].split(" ")[0])  # take first date of range
                    val = point.get("values", [{}])[0].get("extracted_value", 0)
                    values.append(int(val))

                if not values:
                    continue

                term_data[term] = {
                    "dates": dates,
                    "values": values,
                    "normalized_latest": values[-1],
                    "avg_30d": round(sum(values[-30:]) / len(values[-30:]), 1),
                    "avg_90d": round(sum(values) / len(values), 1),
                    "trend_direction": calc_trend(values),
                }
                print(f"    OK: {term} = {values[-1]}")
                time.sleep(1)

            except Exception as e:
                print(f"    Error: {term}: {e}")
                time.sleep(2)

        index = 0
        if term_data:
            vals = [v["normalized_latest"] for v in term_data.values()]
            index = round(sum(vals) / len(vals), 1)

        categories_out[cat_key] = {
            "label": cat["label"],
            "color": cat["color"],
            "index": index,
            "terms": term_data,
        }
        print(f"  Index: {index}")
        time.sleep(2)

    return categories_out

def fetch_fred():
    print("\n── FRED ──")
    if not FRED_KEY:
        print("  No FRED_API_KEY")
        return {}
    fred_out = {}
    for series_id, label, units in FRED_SERIES:
        try:
            r = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={"series_id": series_id, "api_key": FRED_KEY,
                        "file_type": "json", "sort_order": "asc",
                        "observation_start": "2023-01-01", "limit": 200},
                timeout=10)
            obs   = r.json().get("observations", [])
            clean = [(o["date"], float(o["value"])) for o in obs if o["value"] != "."]
            if not clean: continue
            dates, values = [c[0] for c in clean], [c[1] for c in clean]
            latest = values[-1]
            prev   = values[-2] if len(values) > 1 else latest
            pct    = round((latest - prev) / prev * 100, 2) if prev else 0
            fred_out[series_id] = {
                "label": label, "units": units, "dates": dates, "values": values,
                "latest": round(latest, 2), "prev": round(prev, 2), "pct_change": pct,
                "trend_direction": "up" if pct > 0.1 else ("down" if pct < -0.1 else "flat"),
            }
            print(f"  {label}: {round(latest,2)}")
        except Exception as e:
            print(f"  Error {series_id}: {e}")
    return fred_out

def main():
    print(f"Fetch started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    trends = fetch_trends_serpapi()
    fred   = fetch_fred()

    # If trends is empty, fall back to FRED-derived scores
    if not any(cat["terms"] for cat in trends.values()):
        print("\n  Trends empty — no fallback needed, saving what we have")

    output = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "timeframe": "today 3-m",
        "categories": trends,
        "fred": fred,
    }
    os.makedirs("data", exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✓ Saved to {OUT_FILE}")

if __name__ == "__main__":
    main()
