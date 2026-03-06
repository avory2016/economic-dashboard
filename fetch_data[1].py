#!/usr/bin/env python3
"""
Economic Signal Fetcher
Pulls Google Trends (via pytrends) + FRED hard data daily.
Saves combined output to data/trends_data.json
"""

import json, os, time, requests
from datetime import datetime
from pytrends.request import TrendReq

FRED_KEY   = os.environ.get("FRED_API_KEY", "")
OUT_FILE   = "data/trends_data.json"
TIMEFRAME  = "today 3-m"

# ── Google Trends search terms ───────────────────────────────────────────────
TRENDS_TERMS = {
    "jobs": {
        "label": "Jobs Market",
        "color": "#00CC99",
        "terms": [
            "how to find a job",
            "how to get unemployment",
            "layoffs",
            "job search",
            "how to file for unemployment",
        ]
    },
    "consumer_spending": {
        "label": "Consumer Spending",
        "color": "#4da6ff",
        "terms": [
            "how to save money",
            "buy now pay later",
            "cancel subscription",
            "grocery budget",
            "coupon codes",
        ]
    },
    "financial_stress": {
        "label": "Financial Stress",
        "color": "#ff7b54",
        "terms": [
            "how to pay off debt",
            "bankruptcy",
            "debt consolidation",
            "can't afford rent",
            "payday loan",
        ]
    },
    "economic_sentiment": {
        "label": "Economic Sentiment",
        "color": "#c77dff",
        "terms": [
            "recession",
            "inflation",
            "cost of living",
            "economy getting worse",
            "economic collapse",
        ]
    },
    "housing": {
        "label": "Housing / Real Estate",
        "color": "#f9c74f",
        "terms": [
            "how to buy a house",
            "mortgage rates",
            "rent prices",
            "affordable housing",
            "eviction",
        ]
    },
}

# ── FRED series to pull ──────────────────────────────────────────────────────
# Each entry: (series_id, label, units_label)
FRED_SERIES = [
    ("ICSA",       "Initial Jobless Claims",        "Claims (thousands)"),
    ("UNRATE",     "Unemployment Rate",              "%"),
    ("CPIAUCSL",   "CPI Inflation (All Items)",      "Index"),
    ("UMCSENT",    "Consumer Sentiment (U of M)",    "Index"),
    ("MORTGAGE30US","30-Year Mortgage Rate",         "%"),
    ("HOUST",      "Housing Starts",                 "Thousands of Units"),
    ("RSAFS",      "Retail Sales",                   "Millions $"),
    ("DRCCLACBS",  "Credit Card Delinquency Rate",   "%"),
]

# ── Helpers ──────────────────────────────────────────────────────────────────
def calc_trend(values):
    if len(values) < 28:
        return "flat"
    recent = sum(values[-14:]) / 14
    prior  = sum(values[-28:-14]) / 14
    if prior == 0:
        return "flat"
    pct = (recent - prior) / prior
    return "up" if pct > 0.05 else ("down" if pct < -0.05 else "flat")

def compute_index(term_results):
    if not term_results:
        return 0
    return round(
        sum(v["normalized_latest"] for v in term_results.values()) / len(term_results), 1
    )

# ── Google Trends ────────────────────────────────────────────────────────────
def fetch_trends():
    print("\n── Google Trends ──")
    pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25), retries=3, backoff_factor=1.0)
    categories_out = {}

    for cat_key, cat in TRENDS_TERMS.items():
        print(f"  {cat['label']}...")
        term_data = {}

        for i in range(0, len(cat["terms"]), 5):
            batch = cat["terms"][i:i+5]
            try:
                pytrends.build_payload(batch, timeframe=TIMEFRAME, geo="US")
                df = pytrends.interest_over_time()
                if df.empty:
                    print(f"    No data: {batch}")
                    continue
                if "isPartial" in df.columns:
                    df = df.drop(columns=["isPartial"])
                for term in batch:
                    if term in df.columns:
                        vals  = df[term].tolist()
                        dates = [d.strftime("%Y-%m-%d") for d in df.index]
                        term_data[term] = {
                            "dates": dates,
                            "values": vals,
                            "normalized_latest": int(df[term].iloc[-1]),
                            "avg_30d": round(float(df[term].tail(30).mean()), 1),
                            "avg_90d": round(float(df[term].mean()), 1),
                            "trend_direction": calc_trend(vals),
                        }
                time.sleep(3)
            except Exception as e:
                print(f"    Error: {e}")
                time.sleep(15)

        categories_out[cat_key] = {
            "label": cat["label"],
            "color": cat["color"],
            "index": compute_index(term_data),
            "terms": term_data,
        }
        time.sleep(4)

    return categories_out

# ── FRED ─────────────────────────────────────────────────────────────────────
def fetch_fred():
    print("\n── FRED Economic Data ──")
    if not FRED_KEY:
        print("  No FRED_API_KEY set — skipping FRED data")
        return {}

    fred_out = {}
    base = "https://api.stlouisfed.org/fred/series/observations"

    for series_id, label, units in FRED_SERIES:
        try:
            r = requests.get(base, params={
                "series_id":       series_id,
                "api_key":         FRED_KEY,
                "file_type":       "json",
                "sort_order":      "asc",
                "observation_start": "2023-01-01",
                "limit":           200,
            }, timeout=10)
            obs = r.json().get("observations", [])

            # Filter out missing values
            clean = [(o["date"], float(o["value"])) for o in obs if o["value"] != "."]
            if not clean:
                continue

            dates  = [c[0] for c in clean]
            values = [c[1] for c in clean]
            latest = values[-1]
            prev   = values[-2] if len(values) > 1 else latest
            pct_chg = round((latest - prev) / prev * 100, 2) if prev != 0 else 0

            fred_out[series_id] = {
                "label":   label,
                "units":   units,
                "dates":   dates,
                "values":  values,
                "latest":  round(latest, 2),
                "prev":    round(prev, 2),
                "pct_change": pct_chg,
                "trend_direction": "up" if pct_chg > 0.1 else ("down" if pct_chg < -0.1 else "flat"),
            }
            print(f"  {label}: {round(latest,2)} {units}")
            time.sleep(0.5)

        except Exception as e:
            print(f"  Error {series_id}: {e}")

    return fred_out

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"Fetch started: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")

    trends    = fetch_trends()
    fred_data = fetch_fred()

    output = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "timeframe":    TIMEFRAME,
        "categories":   trends,
        "fred":         fred_data,
    }

    os.makedirs("data", exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Saved to {OUT_FILE}")
    print("\n── Summary ──")
    for k, v in trends.items():
        print(f"  {v['label']:<30} index={v['index']}")
    if fred_data:
        print(f"\n  FRED series fetched: {len(fred_data)}")

if __name__ == "__main__":
    main()
