# Destined API

Swiss Ephemeris natal chart calculation backend for the Destined dating app.

## What it does
- Calculates natal charts with Astro.com-level accuracy
- Uses Swiss Ephemeris (pyswisseph) with Placidus house system
- Returns all planetary positions, house cusps, ASC, MC
- Includes soul profile and houses of love analysis

## Endpoints

### GET /health
Check the API is running.

### POST /chart
Calculate a natal chart.

**Request:**
```json
{
  "name": "Ingrid",
  "year": 1978,
  "month": 2,
  "day": 23,
  "hour": 2,
  "minute": 3,
  "lat": 10.9639,
  "lon": -74.7964,
  "utc_offset": -5,
  "has_time": true
}
```

### GET /geocode?q=Barranquilla+Colombia
City search proxy.

## Deploy to Render (free)

1. Push this folder to a GitHub repository
2. Go to render.com → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects render.yaml and deploys
5. Your API URL will be: https://destined-api.onrender.com

## Local development
```bash
pip install -r requirements.txt
python app.py
```
