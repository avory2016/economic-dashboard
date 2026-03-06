#!/usr/bin/env python3
"""
Economic Signal Fetcher - FRED-only version
Derives category scores from FRED data (Google Trends blocked on GitHub IPs)
"""
import json, os, requests
from datetime import datetime

FRED_KEY = os.environ.get("FRED_API_KEY", "")
OUT_FILE = "data/trends_data.json"

FRED_SERIES = [
    ("ICSA",        "Initial Jobless Claims",    "Thousands"),
    ("UNRATE",      "Unemployment Rate",          "%"),
    ("CPIAUCSL",    "CPI Inflation",              "Index"),
    ("UMCSENT",     "Consumer Sentiment",         "Index"),
    ("MORTGAGE30US","30-Yr Mortgage Rate",        "%"),
    ("HOUST",       "Housing Starts",             "K Units"),
    ("RSAFS",       "Retail Sales",               "M $"),
    ("DRCCLACBS",   "Credit Card Delinquency",    "%"),
]

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

def normalize(values, invert=False):
    """Normalize a list of values to 0-100. invert=True means higher raw = lower score."""
    if not values: return []
    mn, mx = min(values), max(values)
    if mx == mn: return [50] * len(values)
    normed = [(v - mn) / (mx - mn) * 100 for v in values]
    if invert:
        normed = [100 - v for v in normed]
    return [round(v, 1) for v in normed]

def make_term(dates, values, invert=False):
    normed = normalize(values, invert)
    if not normed: return None
    latest = normed[-1]
    avg30  = round(sum(normed[-30:]) / len(normed[-30:]), 1) if len(normed) >= 2 else latest
    avg90  = round(sum(normed) / len(normed), 1)
    recent = sum(normed[-4:]) / 4 if len(normed) >= 4 else latest
    prior  = sum(normed[-8:-4]) / 4 if len(normed) >= 8 else latest
    pct    = (recent - prior) / prior if prior else 0
    trend  = "up" if pct > 0.05 else ("down" if pct < -0.05 else "flat")
    return {
        "dates": dates, "values": normed,
        "normalized_latest": round(latest),
        "avg_30d": avg30, "avg_90d": avg90,
        "trend_direction": trend,
    }

def build_categories(fred):
    """Derive category scores from FRED series."""
    cats = {
        "jobs": {"label": "Jobs Market", "color": "#00CC99", "terms": {}},
        "consumer_spending": {"label": "Consumer Spending", "color": "#4da6ff", "terms": {}},
        "financial_stress": {"label": "Financial Stress", "color": "#ff7b54", "terms": {}},
        "economic_sentiment": {"label": "Economic Sentiment", "color": "#c77dff", "terms": {}},
        "housing": {"label": "Housing / Real Estate", "color": "#f9c74f", "terms": {}},
    }

    # Jobs: ICSA (invert=higher claims = worse), UNRATE (invert)
    if "ICSA" in fred:
        t = make_term(fred["ICSA"]["dates"], fred["ICSA"]["values"], invert=True)
        if t: cats["jobs"]["terms"]["Jobless Claims (inverted)"] = t
    if "UNRATE" in fred:
        t = make_term(fred["UNRATE"]["dates"], fred["UNRATE"]["values"], invert=True)
        if t: cats["jobs"]["terms"]["Unemployment Rate (inverted)"] = t

    # Consumer Spending: RSAFS (higher = better spending), UMCSENT
    if "RSAFS" in fred:
        t = make_term(fred["RSAFS"]["dates"], fred["RSAFS"]["values"], invert=False)
        if t: cats["consumer_spending"]["terms"]["Retail Sales"] = t
    if "UMCSENT" in fred:
        t = make_term(fred["UMCSENT"]["dates"], fred["UMCSENT"]["values"], invert=False)
        if t: cats["consumer_spending"]["terms"]["Consumer Sentiment"] = t

    # Financial Stress: DRCCLACBS (invert=higher delinquency = worse), ICSA
    if "DRCCLACBS" in fred:
        t = make_term(fred["DRCCLACBS"]["dates"], fred["DRCCLACBS"]["values"], invert=True)
        if t: cats["financial_stress"]["terms"]["Credit Card Delinquency (inverted)"] = t
    if "UNRATE" in fred:
        t = make_term(fred["UNRATE"]["dates"], fred["UNRATE"]["values"], invert=True)
        if t: cats["financial_stress"]["terms"]["Unemployment (inverted)"] = t

    # Economic Sentiment: UMCSENT, RSAFS, CPIAUCSL (invert)
    if "UMCSENT" in fred:
        t = make_term(fred["UMCSENT"]["dates"], fred["UMCSENT"]["values"], invert=False)
        if t: cats["economic_sentiment"]["terms"]["Consumer Sentiment"] = t
    if "CPIAUCSL" in fred:
        t = make_term(fred["CPIAUCSL"]["dates"], fred["CPIAUCSL"]["values"], invert=True)
        if t: cats["economic_sentiment"]["terms"]["Inflation (inverted)"] = t

    # Housing: HOUST (higher starts = healthier), MORTGAGE30US (invert=lower rate = better)
    if "HOUST" in fred:
        t = make_term(fred["HOUST"]["dates"], fred["HOUST"]["values"], invert=False)
        if t: cats["housing"]["terms"]["Housing Starts"] = t
    if "MORTGAGE30US" in fred:
        t = make_term(fred["MORTGAGE30US"]["dates"], fred["MORTGAGE30US"]["values"], invert=True)
        if t: cats["housing"]["terms"]["Mortgage Rate (inverted)"] = t

    # Compute index for each category
    for k, cat in cats.items():
        vals = [v["normalized_latest"] for v in cat["terms"].values() if v]
        cat["index"] = round(sum(vals) / len(vals), 1) if vals else 0
        print(f"  {cat['label']}: index={cat['index']}, terms={len(cat['terms'])}")

    return cats

def main():
    print(f"Fetch started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    fred       = fetch_fred()
    print("\n── Building category scores from FRED ──")
    categories = build_categories(fred)
    output     = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "timeframe": "today 3-m",
        "categories": categories,
        "fred": fred,
    }
    os.makedirs("data", exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✓ Saved to {OUT_FILE}")

if __name__ == "__main__":
    main()
