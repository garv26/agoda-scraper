# Robustness Improvements for Agoda Scraper

## Overview
This document describes the improvements made to handle slow API responses and track failed hotels for retry.

## Changes Made

### 1. Increased API Wait Time with Progressive Delays
**File:** `scraper/room_details.py`

- **Before:** API wait timeout was 10 seconds with 1-second checks
- **After:** API wait timeout increased to 30 seconds with progressive delays
  - First 10 seconds: Check every 1 second
  - After 10 seconds: Check every 2 seconds (less frequent)
  - Added scroll trigger: If API not received after timeout, scrolls down to trigger lazy-loaded API calls

**Benefits:**
- Handles slow API responses that occur after scraping many hotels
- Reduces false "No Rooms Found" errors due to premature timeout
- Scroll trigger helps load API responses that require user interaction

### 2. Failed Hotels Tracking
**File:** `scraper/multi_browser_scraper.py`

- Added `FailedHotelsTracker` class to track hotels that failed to scrape rooms
- Thread-safe implementation for multi-browser parallel scraping
- Tracks failure reasons (API errors, no rooms found, etc.)

**Failure Detection Logic:**
- Hotels are marked as failed only if they have actual errors (not just "No Rooms Found")
- Distinguishes between:
  - **API Errors:** Likely slow API response or network issues
  - **No Rooms Found:** Legitimate sold-out or unavailable dates
  - **Sold Out:** Explicitly marked as sold out by API

### 3. Failed Hotels CSV Export
**File:** `scraper/multi_browser_scraper.py`

- Automatically saves failed hotels to `output/csv/failed_hotels_{session_id}.csv`
- CSV format matches hotel input format for easy retry
- Includes failure reason for each hotel

**CSV Columns:**
- `name`: Hotel name
- `url`: Hotel URL
- `rating`: Hotel rating
- `review_count`: Number of reviews
- `star_rating`: Star rating
- `location`: Hotel location
- `failure_reason`: Why the hotel failed (e.g., "API errors on 5/7 dates")

### 4. Improved Progress Monitoring
- Progress logs now include failed hotel count
- Final summary includes failed hotels count and CSV file path

## Usage

### Running the Scraper
The scraper automatically tracks failed hotels:

```bash
python run_multi_browser.py --browsers 5 --days 30 --hotels-csv jaipur_hotels.csv
```

After scraping completes, check for failed hotels:
```bash
ls output/csv/failed_hotels_*.csv
```

### Retrying Failed Hotels
To retry failed hotels, simply use the failed hotels CSV as input:

```bash
# Find the latest failed hotels file
LATEST_FAILED=$(ls -t output/csv/failed_hotels_*.csv | head -1)

# Retry with more browsers and longer delays
python run_multi_browser.py \
    --hotels-csv "$LATEST_FAILED" \
    --browsers 3 \
    --days 30 \
    --delay-dates 3.0 6.0 \
    --delay-hotels 10.0 20.0
```

**Tips for Retry:**
- Use fewer browsers (3-5) to reduce load
- Increase delays between dates and hotels
- Consider running during off-peak hours
- Some hotels may genuinely be sold out - check failure reasons

### Checking Results
After scraping, check the summary in logs:

```
[Progress] Hotels: 100/100 | Rooms: 2500 | Errors: 5 | Failed: 12 | Rate: 50/hr | ETA: 0.0h
```

Final summary will show:
```
Failed hotels:     12
Failed hotels CSV: output/csv/failed_hotels_20251210_103454.csv
```

## Technical Details

### API Wait Logic
```python
# Progressive wait: 30 seconds total
api_wait_timeout = 30
for check_num in range(max_checks):
    if api_data['received']:
        break
    if check_num > 10:  # After 10s, check less frequently
        await asyncio.sleep(2)
    else:
        await asyncio.sleep(1)

# Scroll trigger if still not received
if not api_data['received']:
    # Scroll to trigger lazy-loaded API calls
    for scroll_pos in [0.3, 0.6, 0.9]:
        await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {scroll_pos})")
        await asyncio.sleep(2)
        if api_data['received']:
            break
```

### Failure Detection
Hotels are marked as failed if:
1. 80%+ of dates returned "Error" (not "No Rooms Found")
2. No valid room data was extracted across all dates
3. Actual API errors occurred (not just sold-out dates)

This distinguishes between:
- **Temporary failures:** API slow/errors → Should retry
- **Permanent failures:** Sold out → Don't retry

## Benefits

1. **Reduced False Negatives:** Longer wait times catch slow API responses
2. **Better Error Tracking:** Know which hotels failed and why
3. **Easy Retry:** Failed hotels CSV can be used directly for retry
4. **Improved Reliability:** Progressive delays and scroll triggers help load data
5. **Better Monitoring:** Progress logs show failed hotel count

## Future Improvements

Potential enhancements:
- Automatic retry mechanism for failed hotels
- Exponential backoff for retries
- Separate tracking for "sold out" vs "API errors"
- Configurable API timeout per hotel
- Rate limiting detection and automatic slowdown

