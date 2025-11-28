# Agoda Hotel Scraper

A Python-based web scraper to extract hotel and room information from Agoda.com for a given location and date range.

## Features

- Scrapes hotel listings with infinite scroll support
- Extracts detailed room information including prices, amenities, and availability
- Supports configurable date ranges (up to 60-90 days)
- Outputs data in both CSV and JSON formats
- Built-in anti-detection measures with random delays
- Incremental saving to prevent data loss

## Requirements

- Python 3.10+
- Playwright browser automation

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

## Configuration

Edit `config.json` to customize scraping parameters:

```json
{
  "location": "Jaipur",
  "num_hotels": 50,
  "days_ahead": 60,
  "guests": 2,
  "rooms": 1,
  "delays": {
    "between_hotels": [2, 5],
    "between_dates": [1, 3],
    "scroll_pause": [0.5, 1.5]
  },
  "output_dir": "output"
}
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `location` | City/location to search | "Jaipur" |
| `num_hotels` | Number of hotels to scrape | 50 |
| `days_ahead` | Number of days to scrape (from today) | 60 |
| `guests` | Number of guests per room | 2 |
| `rooms` | Number of rooms | 1 |
| `delays.between_hotels` | Random delay range (seconds) between hotels | [2, 5] |
| `delays.between_dates` | Random delay range (seconds) between dates | [1, 3] |
| `delays.scroll_pause` | Random delay range (seconds) during scrolling | [0.5, 1.5] |
| `output_dir` | Directory for output files | "output" |

## Usage

Run the scraper:

```bash
python -m scraper.main
```

Or with a custom config file:

```bash
python -m scraper.main --config path/to/config.json
```

## Output

The scraper generates two output files in the `output/` directory:

### CSV Format
`agoda_rooms_YYYYMMDD_HHMMSS.csv`

```csv
hotel_name,date,room_type,price,currency,amenities,availability
Taj Rambagh Palace,2025-11-29,Deluxe Room,15000,INR,"Breakfast;WiFi;Free Cancellation",Available
```

### JSON Format
`agoda_rooms_YYYYMMDD_HHMMSS.json`

```json
{
  "scrape_date": "2025-11-28T10:30:00",
  "location": "Jaipur",
  "config": {...},
  "hotels": [
    {
      "name": "Taj Rambagh Palace",
      "url": "https://...",
      "rating": 9.2,
      "rooms": [...]
    }
  ]
}
```

## Estimated Runtime

- ~50 hotels × 60 dates = 3000 page loads
- With 2-5 second delays: approximately 2.5-4 hours
- Progress is saved incrementally every 5 hotels

## Anti-Detection Measures

- Random delays between requests
- Realistic browser fingerprint (viewport, user-agent)
- Human-like scrolling with variable speeds
- Session persistence across hotel scrapes
- Exponential backoff on errors

## Legal Notice

This scraper is intended for personal use and research purposes only. Please review Agoda's Terms of Service before using this tool. Respect rate limits and do not overload their servers.

## License

MIT License

