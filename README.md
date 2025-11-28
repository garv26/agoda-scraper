# Agoda Hotel Scraper

A Python-based web scraper to extract hotel and room information from Agoda.com for a given location and date range. Built with Playwright for handling dynamic JavaScript content.

## Features

- 🏨 **Hotel Discovery** - Scrapes hotel listings with infinite scroll support
- 🛏️ **Room Details** - Extracts room types, prices, amenities, and availability for each date
- 📍 **Rich Hotel Data** - Captures hotel name, location, star rating, review rating, and review count
- 📅 **Date Range Support** - Scrape room availability across multiple days
- 💾 **Dual Output** - Exports to both CSV and JSON formats
- 🔄 **Incremental Saving** - Saves progress after each date to prevent data loss
- 🛡️ **Anti-Detection** - Randomized user agents, realistic browser fingerprints, and human-like delays

## Project Structure

```
start/
├── config.json           # Scraping configuration
├── requirements.txt      # Python dependencies
├── README.md             # This file
├── scraper/
│   ├── __init__.py
│   ├── main.py           # Entry point and orchestration
│   ├── browser.py        # Playwright browser setup with anti-detection
│   ├── hotel_listing.py  # Hotel search and listing extraction
│   ├── room_details.py   # Individual hotel room scraping
│   ├── models.py         # Data classes (HotelInfo, RoomData, etc.)
│   └── output.py         # CSV and JSON export functions
└── output/               # Generated data files (gitignored)
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

### Basic Usage

```bash
python -m scraper.main
```

### Command Line Arguments

Override configuration values via CLI:

```bash
python -m scraper.main --location "Delhi" --hotels 20 --days 7
```

| Argument | Short | Description |
|----------|-------|-------------|
| `--config` | `-c` | Path to custom configuration JSON file |
| `--location` | `-l` | City to search (overrides config) |
| `--hotels` | `-n` | Number of hotels to scrape (overrides config) |
| `--days` | `-d` | Number of days ahead to scrape (overrides config) |
| `--output` | `-o` | Output directory (overrides config) |
| `--no-headless` | | Run browser in visible mode (for debugging) |
| `--verbose` | `-v` | Enable verbose/debug logging |

### Examples

```bash
# Scrape 10 hotels in Delhi for 3 days
python -m scraper.main -l "Delhi" -n 10 -d 3

# Use custom config file with verbose logging
python -m scraper.main -c my_config.json -v

# Debug mode with visible browser
python -m scraper.main --no-headless --hotels 2 --days 1
```

## Output

The scraper generates output files in the `output/` directory:

### CSV Format

**File:** `agoda_rooms_YYYYMMDD_HHMMSS.csv`

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

### JSON Format

**File:** `agoda_rooms_YYYYMMDD_HHMMSS.json`

```json
{
  "scrape_date": "2025-11-28T20:04:01.123456",
  "location": "Jaipur",
  "config": {
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
  },
  "total_hotels": 30,
  "total_rooms": 429,
  "hotels": [
    {
      "name": "Hotel Ratangarh Palace",
      "url": "https://www.agoda.com/hotel-ratangarh-palace/...",
      "rating": 7.3,
      "review_count": 473,
      "star_rating": 3,
      "location": "Gopalbari, Jaipur",
      "rooms": [
        {
          "hotel_name": "Hotel Ratangarh Palace",
          "date": "2025-11-29",
          "room_type": "Luxury Rooms",
          "price": 4268.0,
          "currency": "INR",
          "amenities": ["Wi-Fi [free]", "Air Conditioning", "Breakfast"],
          "is_available": true,
          "cancellation_policy": null,
          "meal_plan": "Breakfast Included",
          "hotel_location": "Gopalbari, Jaipur",
          "hotel_rating": 7.3,
          "hotel_star_rating": 3,
          "hotel_review_count": 473
        }
      ]
    }
  ],
  "errors": null
}
```

### Progress File

**File:** `agoda_progress_YYYYMMDD_HHMMSS.json`

Saves intermediate progress during scraping to allow recovery from interruptions.

## Estimated Runtime

| Hotels | Days | Total Requests | Estimated Time |
|--------|------|----------------|----------------|
| 10 | 5 | ~50 | 3-5 minutes |
| 30 | 5 | ~150 | 10-15 minutes |
| 50 | 30 | ~1500 | 1-2 hours |
| 50 | 60 | ~3000 | 2-4 hours |

Progress is saved incrementally after each date's room data is scraped.

## Anti-Detection Measures

The scraper implements several techniques to avoid detection:

- **Randomized User Agents** - Rotates between 4 Chrome user agent strings (Windows/Mac, Chrome 119/120)
- **Realistic Viewports** - Uses common screen resolutions (1920×1080, 1366×768, 1536×864, 1440×900)
- **Browser Fingerprint Masking** - Hides `navigator.webdriver` property
- **Fake Browser Properties** - Sets fake `navigator.plugins`, `navigator.languages`, and `window.chrome`
- **Geolocation Spoofing** - Sets timezone to `Asia/Kolkata` and geolocation to Jaipur coordinates
- **Human-like Delays** - Random pauses between actions using configurable delay ranges
- **Chromium Args** - Disables automation-controlled features (`--disable-blink-features=AutomationControlled`)

## Troubleshooting

### Common Issues

1. **No hotels found**
   - Check if Agoda is accessible from your location
   - Try running with `--no-headless` to see the browser
   - Increase delays in `config.json`

2. **Scraping too slow**
   - Reduce delays in `config.json`
   - Reduce `days_ahead` for faster runs

3. **Missing room data**
   - Some hotels may have dynamic loading issues
   - Check `output/debug_*.html` files for page snapshots

4. **Blocked by Agoda**
   - Increase delays between requests
   - Consider using proxies (not implemented by default)

5. **Browser crashes**
   - Ensure you have enough memory
   - Try with `--no-headless` to debug

## Dependencies

```
playwright==1.49.0
beautifulsoup4==4.12.3
pydantic==2.10.2
lxml==5.3.0
```

## Legal Notice

⚠️ **Disclaimer:** This scraper is intended for personal use, research, and educational purposes only.

- Review Agoda's Terms of Service before using this tool
- Respect rate limits and do not overload their servers
- The scraped data should not be used for commercial purposes without permission
- The developers are not responsible for any misuse of this tool

## License

MIT License
