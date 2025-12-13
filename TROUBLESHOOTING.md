# Troubleshooting Guide: Room Type Extraction Issues

## Common Symptoms and Solutions

### ❌ Symptom 1: "No Rooms Found" in room_type column

**What this means:** The scraper couldn't find any room elements on the page.

**Possible causes:**

1. **Room container selector is wrong**
   - Agoda changed the HTML structure
   - The `div[data-selenium="room-panel"]` selector doesn't match anymore
   
2. **Rooms didn't load before scraping**
   - JavaScript/AJAX didn't finish loading rooms
   - Network timeout occurred
   
3. **Page structure changed completely**
   - Agoda redesigned their room listing layout

**How to diagnose:**

```bash
# Check debug HTML files (if available)
ls -la output/debug_html/*/

# Analyze with the tool
python analyze_selectors.py output/debug_html/session/debug_hotel.html

# Look for this in logs:
# "Found 0 rooms using selector: ..."
```

**How to fix:**

1. Inspect Agoda manually (see QUICK_REFERENCE.md)
2. Find the correct room container selector
3. Update `scraper/room_details.py` line 497:

```python
room_selectors = [
    {'tag': 'NEW_TAG', 'attrs': {'NEW_ATTRIBUTE': 'NEW_VALUE'}},  # Add new selector
    {'tag': 'div', 'attrs': {'data-selenium': 'room-panel'}},      # Keep old as fallback
    # ... rest of selectors
]
```

---

### ❌ Symptom 2: Room type shows garbage text

**Examples of garbage:**
- "Show more rooms"
- "What time is check-in"
- "Limited Time Offer"
- "Free WiFi Breakfast Parking"
- "AgodaSponsored"

**What this means:** The scraper is grabbing the wrong HTML element.

**Possible causes:**

1. **Room name selector is targeting wrong element**
   - Getting UI text instead of actual room name
   - Grabbing promotional banners
   
2. **Validation isn't filtering properly**
   - Garbage text passes validation checks

**How to diagnose:**

Check the actual HTML selector being used:

```bash
# Look in debug HTML for what element has data-selenium="room-name"
grep -A 2 -B 2 'data-selenium="room-name"' output/debug_html/session/*.html
```

**How to fix:**

**Option A: Update selector**

If room name is in a different element:

```python
# scraper/room_details.py, line 647
name_selectors = [
    {'tag': 'CORRECT_TAG', 'attrs': {'data-selenium': 'CORRECT_VALUE'}},
    {'tag': 'span', 'attrs': {'data-selenium': 'room-name'}},  # Keep as fallback
    # ...
]
```

**Option B: Improve validation**

If valid room names are being extracted but validation is weak, strengthen it:

```python
# scraper/room_details.py, line 108-110
# Add more garbage text to blacklist
ROOM_NAME_BLACKLIST = [
    # ... existing items ...
    "your_garbage_text_here",  # Add patterns you see
]
```

---

### ❌ Symptom 3: Price column is empty (None/blank)

**What this means:** Price extraction failed.

**Possible causes:**

1. **Price selector is wrong**
   - Agoda changed price element structure
   - `data-ppapi="room-price"` doesn't exist anymore
   
2. **Price format changed**
   - Was "R . 3,939", now "₹3,939"
   - Regex pattern doesn't match new format
   
3. **Price validation too strict**
   - Prices below ₹1000 are rejected
   - Budget rooms are filtered out

**How to diagnose:**

```bash
# Check what price elements exist
grep -i "price\|₹\|rupee" output/debug_html/session/*.html | head -20

# Or use the analyzer
python analyze_selectors.py output/debug_html/session/debug_hotel.html
# Look at the "PRICE ANALYSIS" section
```

**How to fix:**

**Option A: Update price selector**

```python
# scraper/room_details.py, line 691
price_selectors = [
    {'tag': 'NEW_TAG', 'attrs': {'NEW_ATTRIBUTE': 'NEW_VALUE'}},  # Add new
    {'tag': 'strong', 'attrs': {'data-ppapi': 'room-price'}},      # Keep old
    # ...
]
```

**Option B: Update price pattern**

If price format changed:

```python
# scraper/room_details.py, line 712
price_patterns = [
    r'NEW_PATTERN_HERE',           # Add new format
    r'R\s*\.?\s*([\d,]+)',         # Keep old patterns
    # ...
]
```

**Option C: Lower price threshold**

If budget rooms are being filtered:

```python
# scraper/room_details.py, line 726 and 809
# Change from 1000 to lower value (e.g., 500)
if price >= 500:  # Was: if price >= 1000
    break
```

---

### ❌ Symptom 4: Valid room names are missing

**Example:** You see "Superior Suite" on Agoda but it's not in the output.

**What this means:** Validation is too strict and filtering valid rooms.

**Possible causes:**

1. **Room name doesn't start with recognized keyword**
   - "Garden View Room" rejected because "garden" not in ROOM_TYPE_KEYWORDS
   
2. **Room name too long**
   - Maximum 80-120 characters
   
3. **Contains promotional text**
   - "Deluxe Room - 20% off" rejected due to "%" symbol

**How to diagnose:**

```python
# Test validation manually
from scraper.room_details import is_valid_room_name

test_names = [
    "Superior Suite",
    "Garden View Room", 
    "Your actual room name here"
]

for name in test_names:
    result = is_valid_room_name(name)
    print(f"{name}: {result}")
```

**How to fix:**

**Option A: Add keywords**

```python
# scraper/room_details.py, line 46
ROOM_TYPE_KEYWORDS = [
    # ... existing keywords ...
    'garden', 'pool', 'ocean',  # Add new keywords
]
```

**Option B: Relax length limit**

```python
# scraper/room_details.py, line 86
if len(name) > 150:  # Was: 120
    return False
```

**Option C: Allow promotional suffixes**

```python
# scraper/room_details.py, line 84
if starts_with_room_type:
    if len(name) > 200:  # Was: 120, allow longer for promos
        return False
    return True
```

---

### ❌ Symptom 5: Duplicate room entries

**Example:** "Deluxe Room" appears 3 times with different prices.

**What this means:** Multiple room elements are being extracted for the same room.

**Possible causes:**

1. **Multiple selectors matching same elements**
   - Different selector patterns finding overlapping elements
   
2. **Deduplication not working**
   - `deduplicate_rooms()` function failing

**How to fix:**

Deduplication should already be happening (line 571), but if it's not working:

```python
# scraper/room_details.py, check line 967-993
# The deduplicate_rooms() function keeps lowest price
# If still seeing duplicates, add debug logging:

def deduplicate_rooms(rooms: list[RoomData]) -> list[RoomData]:
    room_dict = {}
    
    for room in rooms:
        key = room.room_type
        print(f"Processing: {key} - Price: {room.price}")  # DEBUG
        if key not in room_dict:
            room_dict[key] = room
        # ... rest of function
```

---

### ❌ Symptom 6: Room extraction is very slow

**What this means:** Scraper is waiting too long for elements.

**Possible causes:**

1. **Rooms loading via slow AJAX**
   - Network timeouts
   
2. **Too many retry attempts**
   - Multiple selectors all timing out

**How to fix:**

Adjust wait times in `scraper/room_details.py`:

```python
# Line 306-453: wait_for_room_listings()
# Reduce timeout values if too slow:

await page.wait_for_selector(selector, timeout=15000)  # Was: 30000
```

---

## Quick Diagnostic Script

Save this as `diagnose.py` and run it to test validation:

```python
#!/usr/bin/env python3
"""Quick diagnostic for room name validation."""

from scraper.room_details import is_valid_room_name

# Add your actual room names you see on Agoda
test_cases = [
    ("Deluxe Room", True),  # Should pass
    ("Superior Suite", True),  # Should pass
    ("Show more rooms", False),  # Should fail
    ("What time is check-in", False),  # Should fail
    # Add your own test cases:
    ("YOUR ROOM NAME HERE", True),  # Expected: True or False?
]

print("Room Name Validation Test")
print("=" * 60)

for room_name, expected in test_cases:
    result = is_valid_room_name(room_name)
    status = "✓" if result == expected else "✗ FAIL"
    print(f"{status} {room_name:<40} → {result} (expected: {expected})")

print("=" * 60)
```

Run it:
```bash
python diagnose.py
```

---

## Step-by-Step Debugging Process

### Step 1: Identify the symptom
- What's wrong with the data?
- Which column has issues?
- What does the bad data look like?

### Step 2: Check debug HTML
```bash
# Find most recent debug HTML
ls -lt output/debug_html/*/*.html | head -1

# Open in browser and search for:
# - Room listings (do you see rooms?)
# - Room names (are they visible?)
# - Prices (are they shown?)
```

### Step 3: Run the analyzer
```bash
python analyze_selectors.py output/debug_html/session/debug_hotel.html

# Look for selectors with ✓ (working) vs ✗ (not working)
```

### Step 4: Inspect Agoda manually
- Open Agoda hotel page in browser
- Press F12 (DevTools)
- Find room elements
- Compare attributes with code selectors

### Step 5: Update code
- Edit `scraper/room_details.py`
- Add/update selectors
- Keep old selectors as fallbacks

### Step 6: Test
```bash
# Run scraper on 1-2 hotels
# Check if room_type data is now correct
```

---

## Getting More Help

If you're still stuck, provide:

1. **Symptom:** What's wrong with the output data?
2. **Example:** Show actual bad data from CSV
3. **HTML:** Share HTML snippet from Agoda (DevTools)
4. **Logs:** Any error messages from scraper
5. **Version:** Which file/line you're looking at

Example report:

```
Symptom: Room type shows "No Rooms Found"

Example data:
hotel_name,room_type,price
"Hotel ABC","No Rooms Found",

HTML from Agoda (DevTools):
<div class="RoomCard" data-testid="room-option">
  <h3 class="RoomTitle">Deluxe Room</h3>
  <span class="PriceValue">R . 3,999</span>
</div>

Current selector (line 497):
div[data-selenium="room-panel"]

Issue: Agoda now uses data-testid instead of data-selenium
```

This makes it much easier to diagnose and fix!

---

## Prevention

To avoid selector issues in the future:

1. **Use multiple fallback selectors** (already done in code)
2. **Save debug HTML regularly** (already done)
3. **Monitor Agoda for changes** (manual check periodically)
4. **Test scraper on sample before full run**
5. **Keep this documentation updated**

---

## Quick Links

- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Fast verification checklist
- [HOW_TO_INSPECT_SELECTORS.md](HOW_TO_INSPECT_SELECTORS.md) - Manual inspection guide
- [SELECTOR_ANALYSIS.md](SELECTOR_ANALYSIS.md) - Technical selector details
- [analyze_selectors.py](analyze_selectors.py) - Testing tool
