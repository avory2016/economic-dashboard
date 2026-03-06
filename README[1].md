# Economic Signal Dashboard
**Google Trends + FRED Data · Auto-updates daily · Free · No server needed**

---

## What's in this repo

| File | Purpose |
|---|---|
| `index.html` | The dashboard (open in browser or host on GitHub Pages) |
| `fetch_data.py` | Python script that pulls all data daily |
| `data/trends_data.json` | Auto-updated data file |
| `.github/workflows/fetch_data.yml` | GitHub Actions — runs the fetch automatically every day |

---

## Setup in ~30 minutes

### Step 1 — Get a free FRED API key (2 min)
1. Go to **https://fred.stlouisfed.org/docs/api/api_key.html**
2. Click "Request API Key" — it's instant and free
3. Copy your key

---

### Step 2 — Create a GitHub account + repo (5 min)
1. Go to **https://github.com** → Sign up (free)
2. Click **New Repository**
   - Name it: `economic-dashboard`
   - Set to **Public** (required for free GitHub Pages)
   - Click **Create repository**

---

### Step 3 — Upload these files (5 min)
Upload the following files maintaining this exact folder structure:

```
economic-dashboard/
├── index.html
├── fetch_data.py
├── data/
│   └── trends_data.json
└── .github/
    └── workflows/
        └── fetch_data.yml
```

**Important:** The `.github/workflows/` folder must be named exactly that (with the dot).
In GitHub's file uploader, you can type the full path like `.github/workflows/fetch_data.yml`
and it will create the folders automatically.

---

### Step 4 — Add your FRED API key as a secret (3 min)
1. In your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `FRED_API_KEY`
4. Value: paste your key from Step 1
5. Click **Add secret**

---

### Step 5 — Enable GitHub Pages (2 min)
1. In your repo → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / folder: `/ (root)`
4. Click **Save**

Your dashboard will be live at:
`https://YOUR-USERNAME.github.io/economic-dashboard/`

---

### Step 6 — Run the first fetch manually (1 min)
1. Go to your repo → **Actions** tab
2. Click **Fetch Economic Data Daily** in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Wait ~2-3 minutes for it to complete
5. Refresh your dashboard — it now has live data!

---

## After that, everything is automatic
- GitHub runs the fetch every day at **8am ET**
- It commits the updated `trends_data.json` back to your repo
- Your dashboard auto-reflects the new data on next page load
- Your computer never needs to be on

---

## Customizing search terms
Open `fetch_data.py` and edit the `TRENDS_TERMS` dictionary.
Each category can have up to 5 search terms (Google Trends limit per request).

## Adding more FRED series
Browse series at **https://fred.stlouisfed.org** and add the series ID to the
`FRED_SERIES` list in `fetch_data.py`.

---

## Troubleshooting
- **pytrends rate limit error**: GitHub Actions will retry. If it keeps failing,
  add `time.sleep(10)` between categories in `fetch_data.py`.
- **FRED returns no data**: Check your API key is saved correctly in secrets.
- **Dashboard shows old data**: Hard refresh the page (Ctrl+Shift+R).
