# Agoda Hotel Scraper

A high-performance Python web scraper to extract hotel and room information from Agoda.com. Features **multi-browser parallel processing** for fast, scalable scraping with advanced anti-detection measures and optional proxy support.

## Features

- 🚀 **Parallel Processing** - Multiple browser instances run simultaneously for N× speedup
- 🏨 **Hotel Discovery** - Scrapes hotel listings with infinite scroll support
- 🛏️ **Room Details** - Extracts room types, prices, amenities, and availability for each date
- 📍 **Rich Hotel Data** - Captures hotel name, location, star rating, review rating, and review count
- 📅 **Date Range Support** - Scrape room availability across multiple days (30+ days supported)
- 💾 **CSV Output** - Thread-safe incremental CSV writing with real-time progress
- 🔄 **Incremental Saving** - Saves progress after each date to prevent data loss
- 🛡️ **Advanced Anti-Detection** - Unique browser fingerprints per instance (user agent, viewport, timezone)
- 🌐 **Proxy Support** - Optional rotating proxy support (SOCKS5/HTTP) with validation
- 🔁 **Retry Logic** - Automatic retry on network errors with exponential backoff
- 📊 **Progress Monitoring** - Real-time progress tracking with ETA estimates

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
playwright install chromium
```

2. **Run the multi-browser scraper:**
```bash
# Test run: 3 browsers, 5 hotels, 2 days
python run_multi_browser.py --browsers 3 --limit 5 --days 2

# Production: 10 browsers, all hotels, 30 days
python run_multi_browser.py --browsers 10 --days 30
```

3. **Check results:**
   - CSV output: `output/csv/multi_browser_YYYYMMDD_HHMMSS.csv`
   - Logs: `logs/scraper_YYYYMMDD_HHMMSS.log`

**Note:** If you don't have a hotel CSV file, first extract hotel listings:
```bash
python -m scraper.main --location "Jaipur" --hotels 50 --days 1
```

## Project Structure

```
start/
├── config.json                    # Scraping configuration
├── requirements.txt               # Python dependencies
├── README.md                      # This file
├── run_multi_browser.py           # Main entry point for parallel scraping
├── jaipur_hotels2.csv             # Pre-extracted hotel list (example)
├── scraper/
│   ├── __init__.py
│   ├── main.py                    # Single-browser scraper (legacy)
│   ├── multi_browser_scraper.py   # Multi-browser parallel scraper ⭐
│   ├── browser.py                 # Playwright browser setup with anti-detection
│   ├── hotel_listing.py           # Hotel search and listing extraction
│   ├── room_details.py            # Individual hotel room scraping
│   ├── models.py                  # Data classes (HotelInfo, RoomData, etc.)
│   └── output.py                  # CSV and JSON export functions
├── output/                        # Generated data files (gitignored)
│   ├── csv/                       # CSV output files
│   └── debug_html/                # Debug HTML snapshots
└── logs/                          # Scraper log files
```

## Requirements

- Python 3.10+
- Playwright with Chromium

## Installation

1. **Clone the repository:**
```bash
git clone <repository_url>
cd start
```

2. **Create a virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Install Playwright browsers:**
```bash
playwright install chromium
```

## Configuration

Edit `config.json` to customize scraping parameters:

```json
{
  "location": "Jaipur",
  "num_hotels": 30,
  "days_ahead": 5,
  "guests": 2,
  "rooms": 1,
  "delays": {
    "between_hotels": [1, 2],
    "between_dates": [0.5, 1],
    "scroll_pause": [0.3, 0.7]
  },
  "output_dir": "output"
}
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `location` | City/location to search for hotels | `"Jaipur"` |
| `num_hotels` | Number of hotels to scrape | `30` |
| `days_ahead` | Number of days to scrape room data for | `5` |
| `guests` | Number of guests per room | `2` |
| `rooms` | Number of rooms to book | `1` |
| `delays.between_hotels` | Random delay range (seconds) between hotels | `[1, 2]` |
| `delays.between_dates` | Random delay range (seconds) between dates | `[0.5, 1]` |
| `delays.scroll_pause` | Random delay range (seconds) during scrolling | `[0.3, 0.7]` |
| `output_dir` | Directory for output files | `"output"` |

## Usage

### Two-Phase Approach

The scraper uses a two-phase approach for optimal performance:

1. **Phase 1: Extract Hotel Listings** (optional, if you don't have a hotel CSV)
   - Run the single-browser scraper to extract hotel listings
   - Outputs a CSV file with hotel names, URLs, and metadata

2. **Phase 2: Scrape Room Details** (main workflow)
   - Use the multi-browser parallel scraper with a pre-extracted hotel list
   - Multiple browsers process hotels in parallel for maximum speed

### Phase 1: Extract Hotel Listings (Optional)

If you already have a hotel CSV file, skip to Phase 2.

```bash
# Extract hotel listings for a location
python -m scraper.main --location "Jaipur" --hotels 50 --days 1
```

This creates a CSV file that you can use in Phase 2.

### Phase 2: Multi-Browser Parallel Scraping (Recommended)

This is the main entry point for production scraping:

```bash
# Basic usage: 5 browsers, 30 days, all hotels from CSV
python run_multi_browser.py --browsers 5 --days 30

# Test run: 3 browsers, 5 hotels, 2 days
python run_multi_browser.py --browsers 3 --limit 5 --days 2

# Production: 10 browsers, 30 days, custom hotel list
python run_multi_browser.py --hotels-csv jaipur_hotels2.csv --browsers 10 --days 30

# Debug mode with visible browsers
python run_multi_browser.py --browsers 2 --limit 3 --days 1 --no-headless

# With custom delays and proxies
python run_multi_browser.py --browsers 5 --days 30 \
    --delay-dates 0.5 1.5 \
    --delay-hotels 2.0 5.0 \
    --proxy socks5://127.0.0.1:1081
```

### Command Line Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--hotels-csv` | `-i` | Input CSV with hotel list | `jaipur_hotels2.csv` |
| `--output` | `-o` | Output CSV file path | Auto-generated in `output/csv/` |
| `--browsers` | `-b` | Number of browser instances | `5` |
| `--days` | `-d` | Days ahead to scrape | `30` |
| `--limit` | `-l` | Limit number of hotels (for testing) | None (all hotels) |
| `--offset` | | Start from hotel N (skip first N) | `0` |
| `--no-headless` | | Run with visible browsers | False |
| `--skip-proxy-validation` | | Skip proxy validation (faster startup) | False |
| `--delay-dates` | | Delay between dates (min max) | `0.5 1.5` |
| `--delay-hotels` | | Delay between hotels (min max) | `2.0 5.0` |
| `--proxy` | | Add a proxy (can be used multiple times) | None |

### Memory Requirements

| Browsers | RAM Usage |
|----------|-----------|
| 5 browsers | ~1 GB |
| 10 browsers | ~2 GB |
| 20 browsers | ~4 GB |

## Output

The multi-browser scraper generates CSV files in the `output/csv/` directory:

### CSV Format

**File:** `multi_browser_YYYYMMDD_HHMMSS.csv`

| Column | Description |
|--------|-------------|
| `hotel_name` | Name of the hotel |
| `hotel_location` | Hotel address/area |
| `hotel_rating` | Review score (e.g., 7.1, 9.2) |
| `hotel_star_rating` | Star rating (1-5) |
| `hotel_review_count` | Number of reviews |
| `date` | Check-in date (YYYY-MM-DD) |
| `room_type` | Room category name |
| `price` | Price per night |
| `currency` | Currency code (INR, USD, etc.) |
| `amenities` | Semicolon-separated list |
| `availability` | "Available" or "Not Available" |
| `cancellation_policy` | Cancellation terms |
| `meal_plan` | Meal inclusion (e.g., "Breakfast Included") |

**Example:**
```csv
hotel_name,hotel_location,hotel_rating,hotel_star_rating,hotel_review_count,date,room_type,price,currency,amenities,availability,cancellation_policy,meal_plan
Hotel Ratangarh Palace,"Gopalbari, Jaipur",7.3,3,473,2025-11-29,Luxury Rooms,4268.0,INR,Wi-Fi [free];Air Conditioning;Breakfast;City View,Available,,Breakfast Included
```

### Real-Time Progress

The scraper logs progress every minute with:
- Hotels processed / total
- Total rooms scraped
- Error count
- Processing rate (hotels/hour)
- Estimated time remaining (ETA)

Example output:
```
[Progress] Hotels: 45/100 | Rooms: 1350 | Errors: 2 | Rate: 12/hr | ETA: 4.6h
```

### Log Files

All scraping sessions are logged to `logs/scraper_YYYYMMDD_HHMMSS.log` with detailed information about each browser worker's activity.

## Estimated Runtime

With **5 browser instances** (default):

| Hotels | Days | Total Requests | Estimated Time |
|--------|------|----------------|----------------|
| 10 | 5 | ~50 | 1-2 minutes |
| 30 | 30 | ~900 | 15-20 minutes |
| 50 | 30 | ~1500 | 25-35 minutes |
| 100 | 30 | ~3000 | 50-70 minutes |
| 200 | 30 | ~6000 | 1.5-2.5 hours |

With **10 browser instances**:

| Hotels | Days | Total Requests | Estimated Time |
|--------|------|----------------|----------------|
| 50 | 30 | ~1500 | 15-20 minutes |
| 100 | 30 | ~3000 | 30-40 minutes |
| 200 | 30 | ~6000 | 1-1.5 hours |

**Note:** Actual runtime depends on network speed, proxy latency, and Agoda's response times. Progress is saved incrementally after each date's room data is scraped.

## Anti-Detection Measures

The multi-browser scraper implements advanced techniques to avoid detection:

### Per-Browser Unique Fingerprints

Each browser instance gets a **unique fingerprint**:
- **Diverse User Agents** - 20+ different user agents (Chrome, Firefox, Edge, Safari on Windows/Mac/Linux)
- **Unique Viewports** - 8 different screen resolutions (1920×1080, 1366×768, 2560×1440, etc.)
- **Different Locales/Timezones** - Rotates between en-US, en-GB, en-IN, en-AU with matching timezones
- **Randomized Geolocation** - Slight variations around target location coordinates

### Browser Fingerprint Masking

- **WebDriver Hiding** - Removes `navigator.webdriver` property
- **Fake Plugins** - Injects realistic `navigator.plugins` array
- **Language Spoofing** - Sets `navigator.languages` to match locale
- **Chrome Object** - Adds fake `window.chrome` object
- **Permissions API** - Patches permissions API to appear more human

### Network-Level Protection

- **Proxy Rotation** - Optional rotating proxy support (SOCKS5/HTTP)
- **Proxy Validation** - Tests proxies before use to ensure they work
- **Staggered Delays** - Each browser has slightly different delay patterns
- **Human-like Timing** - Random delays between dates (0.5-1.5s) and hotels (2-5s)

### Chromium Launch Args

- `--disable-blink-features=AutomationControlled` - Removes automation flags
- `--disable-dev-shm-usage` - Prevents shared memory issues
- `--no-sandbox` - Required for some proxy configurations
- `--disable-infobars` - Hides automation indicators

## Proxy Configuration

The scraper supports optional proxy rotation for additional anonymity and to avoid rate limiting.

### Setting Up Proxies

**Option 1: Edit `scraper/multi_browser_scraper.py`**

```python
PROXY_LIST = [
    "socks5://127.0.0.1:1081",  # SSH tunnel
    "socks5://127.0.0.1:1082",  # Another tunnel
    "socks5://your-vps-ip:1080", # VPS proxy
    "http://user:pass@proxy.example.com:8080",  # HTTP proxy with auth
]
```

**Option 2: Command Line**

```bash
python run_multi_browser.py --browsers 5 --days 30 \
    --proxy socks5://127.0.0.1:1081 \
    --proxy socks5://127.0.0.1:1082
```

**Option 3: Programmatically**

```python
from scraper.multi_browser_scraper import set_proxies
set_proxies(["socks5://127.0.0.1:1081", "socks5://127.0.0.1:1082"])
```

### Proxy Formats

- **SOCKS5:** `socks5://ip:port` or `socks5://user:pass@ip:port`
- **HTTP:** `http://ip:port` or `http://user:pass@ip:port`

Proxies are automatically validated before use (unless `--skip-proxy-validation` is used).

## Troubleshooting

### Common Issues

1. **No hotels found in CSV**
   - Ensure your hotel CSV has columns: `name`, `url`, `rating`, `review_count`, `star_rating`, `location`
   - Run Phase 1 scraper first to generate a hotel list

2. **Scraping too slow**
   - Increase `--browsers` count (more parallel instances)
   - Reduce `--days` for faster runs
   - Reduce delays: `--delay-dates 0.3 1.0 --delay-hotels 1.0 3.0`

3. **High memory usage**
   - Reduce `--browsers` count
   - Each browser uses ~200MB RAM

4. **Network errors / timeouts**
   - The scraper automatically retries on network errors (up to 3 times)
   - If using proxies, ensure they're working: `--skip-proxy-validation` to bypass validation
   - Increase delays between requests

5. **Blocked by Agoda**
   - Use proxies: `--proxy socks5://...`
   - Increase delays: `--delay-hotels 5.0 10.0`
   - Reduce browser count temporarily

6. **Browser crashes**
   - Check available memory (each browser needs ~200MB)
   - Try with `--no-headless` to see what's happening
   - Reduce `--browsers` count

7. **CSV file not updating**
   - CSV writes are thread-safe and happen immediately after each date
   - Check file permissions on `output/csv/` directory

## Dependencies

```
playwright==1.49.0
beautifulsoup4==4.12.3
pydantic==2.10.2
lxml==5.3.0
```

All dependencies are listed in `requirements.txt`. Install with:

```bash
pip install -r requirements.txt
playwright install chromium
```

## Legal Notice

⚠️ **Disclaimer:** This scraper is intended for personal use, research, and educational purposes only.

- Review Agoda's Terms of Service before using this tool
- Respect rate limits and do not overload their servers
- The scraped data should not be used for commercial purposes without permission
- The developers are not responsible for any misuse of this tool

## License

MIT License
