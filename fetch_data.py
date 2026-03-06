#!/usr/bin/env python3
"""
Economic Signal Fetcher - Fast + timeout version
"""
import json, os, time, requests, signal
from datetime import datetime
from pytrends.request import TrendReq

FRED_KEY  = os.environ.get("FRED_API_KEY", "")
OUT_FILE  = "data/trends_data.json"
TIMEFRAME = "today 3-m"

TRENDS_TERMS = {
    "jobs": {
        "label": "Jobs Market", "color": "#00CC99",
        "terms": ["how to find a job","how to get unemployment","layoffs","job search","how to file for unemployment"]
    },
    "consumer_spending": {
        "label": "Consumer Spending", "color": "#4da6ff",
        "terms": ["how to save money","buy now pay later","cancel subscription","grocery budget","coupon codes"]
    },
    "financial_stress": {
        "label": "Financial Stress", "color": "#ff7b54",
        "terms": ["how to pay off debt","bankruptcy","debt consolidation","payday loan","credit card debt"]
    },
    "economic_sentiment": {
        "label": "Economic Sentiment", "color": "#c77dff",
        "terms": ["recession","inflation","cost of living","economy getting worse","economic collapse"]
    },
    "housing": {
        "label": "Housing / Real Estate", "color": "#f9c74f",
        "terms": ["how to buy a house","mortgage rates","rent prices","affordable housing","eviction"]
    },
}

FRED_SERIES = [
    ("ICSA","Initial Jobless Claims","Thousands"),
    ("UNRATE","Unemployment Rate","%"),
    ("CPIAUCSL","CPI Inflation","Index"),
    ("UMCSENT","Consumer Sentiment","Index"),
    ("MORTGAGE30US","30-Yr Mortgage Rate","%"),
    ("HOUST","Housing Starts","K Units"),
    ("RSAFS","Retail Sales","M $"),
    ("DRCCLACBS","Credit Card Delinquency","%"),
]

def calc_trend(values):
    if len(values) < 14: return "flat"
    r = sum(values[-7:]) / 7
    p = sum(values[-14:-7]) / 7
    if p == 0: return "flat"
    pct = (r - p) / p
    return "up" if pct > 0.05 else ("down" if pct < -0.05 else "flat")

def compute_index(term_results):
    if not term_results: return 0
    vals = [v["normalized_latest"] for v in term_results.values() if v["normalized_latest"] > 0]
    return round(sum(vals) / len(vals), 1) if vals else 0

class TimeoutError(Exception): pass

def timeout_handler(signum, frame):
    raise TimeoutError("Request timed out")

def fetch_batch(pytrends, batch, timeout_secs=45):
    """Fetch a batch of terms with a hard timeout."""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_secs)
    try:
        pytrends.build_payload(batch, timeframe=TIMEFRAME, geo="US")
        df = pytrends.interest_over_time()
        signal.alarm(0)  # cancel alarm
        return df
    except TimeoutError:
        print(f"    TIMEOUT on {batch}")
        signal.alarm(0)
        return None
    except Exception as e:
        signal.alarm(0)
        print(f"    Error on {batch}: {e}")
        return None

def fetch_trends():
    print("\n── Google Trends ──")
    pytrends = TrendReq(hl="en-US", tz=360, timeout=(8, 20), retries=1, backoff_factor=0.5)
    categories_out = {}

    for cat_key, cat in TRENDS_TERMS.items():
        print(f"  [{cat['label']}]")
        term_data = {}
        terms = cat["terms"]

        # Try all 5 at once first
        df = fetch_batch(pytrends, terms)
        if df is not None and not df.empty:
            if "isPartial" in df.columns:
                df = df.drop(columns=["isPartial"])
            for term in terms:
                if term in df.columns:
                    vals  = df[term].tolist()
                    dates = [d.strftime("%Y-%m-%d") for d in df.index]
                    term_data[term] = {
                        "dates": dates, "values": vals,
                        "normalized_latest": int(df[term].iloc[-1]),
                        "avg_30d": round(float(df[term].tail(30).mean()), 1),
                        "avg_90d": round(float(df[term].mean()), 1),
                        "trend_direction": calc_trend(vals),
                    }
                    print(f"    OK: {term} = {term_data[term]['normalized_latest']}")
        else:
            print(f"    Batch failed, skipping category")

        categories_out[cat_key] = {
            "label": cat["label"], "color": cat["color"],
            "index": compute_index(term_data),
            "terms": term_data,
        }
        print(f"  Index: {categories_out[cat_key]['index']}")
        time.sleep(5)

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
            latest, prev  = values[-1], values[-2] if len(values) > 1 else values[-1]
            pct = round((latest - prev) / prev * 100, 2) if prev else 0
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
    trends = fetch_trends()
    fred   = fetch_fred()
    output = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "timeframe": TIMEFRAME,
        "categories": trends,
        "fred": fred,
    }
    os.makedirs("data", exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✓ Saved to {OUT_FILE}")
    for k, v in trends.items():
        print(f"  {v['label']:<30} index={v['index']}  terms={len(v['terms'])}")

if __name__ == "__main__":
    main()
