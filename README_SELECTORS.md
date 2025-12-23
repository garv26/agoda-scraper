# Agoda Selector Inspection Guide

## Problem

The `room_type` column in the scraped data is showing incorrect or missing values. This suggests that the CSS selectors used to extract room information from Agoda's website may be outdated or incorrect.

## Solution Overview

Since Agoda.com is blocked from automated browser access, we need to manually inspect the site to verify the selectors. This directory contains tools and guides to help with this process.

## Quick Start

### Option 1: Manual Inspection (Recommended)

1. **Read the inspection guide**: [HOW_TO_INSPECT_SELECTORS.md](HOW_TO_INSPECT_SELECTORS.md)
2. **Open Agoda in your browser** and inspect room elements using DevTools
3. **Document your findings** using the template in the guide
4. **Update selectors** in `scraper/room_details.py` if needed

### Option 2: Analyze Saved HTML

If you have previously scraped data, debug HTML files are saved in `output/debug_html/`:

```bash
# List all debug HTML files
python analyze_selectors.py --list

# Analyze a specific file
python analyze_selectors.py output/debug_html/session_id/debug_hotel_name.html

# Analyze most recent file (auto-detected)
python analyze_selectors.py
```

### Option 3: Save and Analyze Agoda Page

1. Open an Agoda hotel page in your browser
2. Right-click → "Save As" → Select "Webpage, Complete"
3. Save as `agoda_sample.html`
4. Run the analyzer:

```bash
python analyze_selectors.py agoda_sample.html
```

## Files in This Repository

### Documentation

- **`SELECTOR_ANALYSIS.md`** - Detailed analysis of all selectors currently used in the scraper
- **`HOW_TO_INSPECT_SELECTORS.md`** - Step-by-step guide for manual selector inspection
- **`README_SELECTORS.md`** - This file

### Tools

- **`analyze_selectors.py`** - Python script to test selectors against HTML files

### Source Code

- **`scraper/room_details.py`** - Main scraper file containing all selector logic

## Current Selectors

### Room Containers

The scraper tries these selectors to find room listing containers:

```python
div[data-selenium="room-panel"]           # Primary
div[data-element-name="room-item"]        
div[class*="RoomGridItem"]
div[class*="MasterRoom"]
# ... and 7 more fallback selectors
```

### Room Names/Types

To extract the room name/type:

```python
span[data-selenium="room-name"]           # Primary
h3[data-selenium="room-name"]
span[data-element-name="room-type-name"]
# ... and 3 more fallback selectors
```

### Room Prices

To extract prices:

```python
strong[data-ppapi="room-price"]           # Primary (most reliable)
span[data-ppapi="room-price"]
span[data-selenium="display-price"]
# ... and 3 more fallback selectors
```

See [SELECTOR_ANALYSIS.md](SELECTOR_ANALYSIS.md) for complete details.

## Common Issues

### Issue 1: "No Rooms Found"

**Symptom**: `room_type` column shows "No Rooms Found"

**Likely Cause**: Room container selector doesn't match current HTML structure

**Fix**: 
1. Inspect room containers on Agoda
2. Update `room_selectors` list in `scraper/room_details.py` (lines 495-509)

### Issue 2: Incorrect Room Names

**Symptom**: `room_type` shows garbage text or UI elements

**Possible Causes**:
- Wrong element is being selected for room name
- Validation logic is filtering valid names

**Fix**:
1. Inspect room name elements on Agoda
2. Update `name_selectors` in `scraper/room_details.py` (lines 646-653)
3. Review `is_valid_room_name()` validation (lines 63-127)

### Issue 3: Missing Prices

**Symptom**: `price` column is empty or shows None

**Likely Cause**: Price selector outdated or price format changed

**Fix**:
1. Inspect price elements on Agoda
2. Update `price_selectors` in `scraper/room_details.py` (lines 690-698)
3. Check price format patterns (lines 712-717)

## How to Update Selectors

### 1. Identify the Issue

Run the analyzer on saved HTML or manually inspect Agoda:

```bash
python analyze_selectors.py saved_agoda_page.html
```

Look for selectors that show `✗` (not working).

### 2. Find Current Selectors on Agoda

Follow the guide in [HOW_TO_INSPECT_SELECTORS.md](HOW_TO_INSPECT_SELECTORS.md):

1. Open Agoda hotel page
2. Open DevTools (F12)
3. Inspect room elements
4. Note the actual attributes and tags

### 3. Update the Code

Edit `scraper/room_details.py`:

**For room containers** (lines 495-509):
```python
room_selectors = [
    {'tag': 'div', 'attrs': {'data-selenium': 'NEW-SELECTOR-HERE'}},
    # ... existing selectors as fallbacks
]
```

**For room names** (lines 646-653):
```python
name_selectors = [
    {'tag': 'span', 'attrs': {'data-selenium': 'NEW-SELECTOR-HERE'}},
    # ... existing selectors as fallbacks
]
```

**For prices** (lines 690-698):
```python
price_selectors = [
    {'tag': 'strong', 'attrs': {'data-ppapi': 'NEW-SELECTOR-HERE'}},
    # ... existing selectors as fallbacks
]
```

### 4. Test Your Changes

Run the scraper on a small sample:

```bash
# Test with a single hotel
python -c "from scraper.room_details import *; # your test code"
```

Or run the full scraper on a limited set:

```bash
# Modify config to scrape just 1-2 hotels
python run_multi_browser.py
```

### 5. Verify Results

Check the output CSV:

```bash
# View the room_type column
cut -d',' -f7 output/csv/latest_output.csv | head -20
```

Look for:
- ✅ Valid room names (e.g., "Deluxe Room", "Standard Suite")
- ❌ Invalid names (e.g., "No Rooms Found", garbage text)

## Debugging Tips

### Enable Debug Logging

The scraper logs which selectors work:

```python
logger.debug(f"Found {count} rooms using selector: {selector}")
```

Check logs to see which selectors are being used.

### Save Debug HTML

The scraper automatically saves HTML to `output/debug_html/{session_id}/` for the first few hotels. Review these files to see what the scraper is actually receiving.

### Test Individual Functions

You can test selector functions directly in Python:

```python
from bs4 import BeautifulSoup
from scraper.room_details import extract_room_data, is_valid_room_name

# Load HTML
with open('test.html', 'r') as f:
    html = f.read()

soup = BeautifulSoup(html, 'lxml')

# Test room name validation
test_names = ["Deluxe Room", "king bed", "Show more rooms"]
for name in test_names:
    valid = is_valid_room_name(name)
    print(f"{name}: {valid}")
```

## Validation Logic

The scraper has strict validation to filter out garbage data. If valid rooms are being filtered, you may need to adjust:

### Room Name Validation

File: `scraper/room_details.py`, lines 63-127

The `is_valid_room_name()` function filters:
- Names shorter than 3 characters
- Names with question marks
- FAQ-style text ("What time is...", "How far is...")
- Pure promotional text ("Limited Time Offer")
- UI elements ("Select your room", "Show more")
- Very long names (>80-120 chars)

**If legitimate room names are being filtered**, adjust the validation logic.

### Price Validation

File: `scraper/room_details.py`, lines 726, 809

Prices below ₹1,000 are rejected to filter out non-room prices.

**If you need to capture budget rooms**, lower this threshold.

## Getting Help

If you're unsure about:
1. What selectors to use
2. Whether validation is correct
3. How to interpret HTML structure

Please share:
- Screenshots of Agoda page with DevTools open
- HTML snippet of the room element
- Example room names that should be extracted
- Current scraper output showing the issue

## Next Steps

1. ✅ Read [HOW_TO_INSPECT_SELECTORS.md](HOW_TO_INSPECT_SELECTORS.md)
2. ✅ Inspect Agoda site using your browser
3. ✅ Document findings (use template in inspection guide)
4. ✅ Update selectors in `scraper/room_details.py`
5. ✅ Test changes with small sample
6. ✅ Verify correct data is extracted
7. ✅ Run full scraper

## Reference

- **Agoda Room Extraction**: `scraper/room_details.py`, function `parse_room_listings()` (line 476)
- **Selector Lists**: Lines 495-509 (containers), 646-653 (names), 690-698 (prices)
- **Validation Logic**: Lines 63-127 (`is_valid_room_name()`)
- **Price Parsing**: Lines 792-813 (`extract_price_value()`)
