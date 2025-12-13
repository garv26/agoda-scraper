# How to Inspect Agoda Selectors - Step by Step Guide

## Background

The scraper is experiencing issues with extracting room_type data. To fix this, we need to verify that the CSS selectors in the code match Agoda's current HTML structure.

Since the Agoda domain is blocked from automated access, you need to manually inspect the site using your browser's DevTools.

## Step-by-Step Instructions

### Step 1: Open an Agoda Hotel Page

1. Go to Agoda.com
2. Search for hotels in Jaipur (or any city)
3. Open any hotel detail page
4. Make sure rooms are visible on the page (scroll down if needed)

**Example URL from your CSV:**
```
https://www.agoda.com/artbuzz-jaipur/hotel/jaipur-in.html?adults=2&children=0&rooms=1&checkIn=2025-12-10
```

### Step 2: Open Browser DevTools

- **Chrome/Edge**: Press `F12` or `Ctrl+Shift+I` (Windows) / `Cmd+Option+I` (Mac)
- **Firefox**: Press `F12` or `Ctrl+Shift+I` (Windows) / `Cmd+Option+I` (Mac)
- **Safari**: Enable Developer menu first, then press `Cmd+Option+I`

### Step 3: Inspect Room Elements

#### Finding Room Containers

1. In the DevTools, click the **"Select element"** tool (top-left corner, looks like a cursor arrow)
2. Hover over a room listing on the page
3. The HTML element should highlight in DevTools
4. Look for the **parent container** that wraps the entire room

**What to record:**
- Tag name (e.g., `div`, `section`, `article`)
- Attributes:
  - `data-selenium="?"`
  - `data-ppapi="?"`
  - `data-element-name="?"`
  - `data-testid="?"`
  - `class="?"`

**Example:**
```html
<div data-selenium="room-panel" class="RoomGridItem">
  <!-- Room content here -->
</div>
```

#### Finding Room Name Elements

1. Use the element selector tool again
2. Click on the **room name/title** text
3. Check the element's HTML structure

**What to record:**
- Tag name (e.g., `span`, `h3`, `div`)
- Attributes (data-selenium, data-element-name, class, etc.)
- Full selector path if needed

**Example:**
```html
<span data-selenium="room-name" class="RoomTypeName">
  Deluxe Room
</span>
```

#### Finding Price Elements

1. Use the element selector tool
2. Click on the **price value** (the number)
3. Check the element's HTML structure

**What to record:**
- Tag name (e.g., `strong`, `span`)
- Attributes
- Price format (e.g., "R . 3,939" or "₹3,939")

**Example:**
```html
<strong data-ppapi="room-price" class="PropertyPrice">
  R . 3,939
</strong>
```

### Step 4: Take Screenshots

Take screenshots of:

1. **Full room listing section** - Shows multiple rooms visible
2. **Room element with DevTools** - Shows HTML structure highlighted
3. **Room name element** - Zoomed in on the name element
4. **Price element** - Zoomed in on the price element

### Step 5: Document Your Findings

Create a document (or GitHub issue) with:

1. **Room Container Selector:**
   ```
   Tag: div
   Attribute: data-selenium="room-panel"
   Class: RoomGridItem
   ```

2. **Room Name Selector:**
   ```
   Tag: span
   Attribute: data-selenium="room-name"
   Class: RoomTypeName
   ```

3. **Price Selector:**
   ```
   Tag: strong
   Attribute: data-ppapi="room-price"
   Class: PropertyPrice
   Format: "R . 3,939"
   ```

4. **Any changes from current code?**
   - [ ] Room container selector changed
   - [ ] Room name selector changed
   - [ ] Price selector changed
   - [ ] Price format changed

### Step 6: Compare with Current Code

Open `scraper/room_details.py` and compare your findings:

#### Current Room Container Selectors (lines 495-509):
```python
room_selectors = [
    {'tag': 'div', 'attrs': {'data-selenium': 'room-panel'}},
    {'tag': 'div', 'attrs': {'data-element-name': 'room-item'}},
    # ... more selectors
]
```

#### Current Room Name Selectors (lines 646-653):
```python
name_selectors = [
    {'tag': 'span', 'attrs': {'data-selenium': 'room-name'}},
    {'tag': 'h3', 'attrs': {'data-selenium': 'room-name'}},
    # ... more selectors
]
```

#### Current Price Selectors (lines 690-698):
```python
price_selectors = [
    {'tag': 'strong', 'attrs': {'data-ppapi': 'room-price'}},
    {'tag': 'span', 'attrs': {'data-ppapi': 'room-price'}},
    # ... more selectors
]
```

**Ask yourself:**
- Is the selector in the code list?
- Is it in the correct priority order?
- Are there new attributes that should be added?

## Common Issues and Solutions

### Issue 1: Room Name Shows as "No Rooms Found"

**Likely cause:** Room container selector doesn't match Agoda's current structure

**Solution:** Update `room_selectors` list in lines 495-509 with the correct selector

### Issue 2: Room Name Shows Garbage Text

**Possible causes:**
- Wrong element is being selected
- Validation is too strict

**Solutions:**
- Verify the room name selector matches the actual room title element
- Check if `is_valid_room_name()` function is filtering out valid names

### Issue 3: Prices Not Extracted

**Likely cause:** Price selector doesn't match or price format changed

**Solutions:**
- Update `price_selectors` in lines 690-698
- Check price format patterns in lines 712-717

### Issue 4: Valid Rooms Are Filtered Out

**Likely cause:** Validation logic is too restrictive

**Check these validations:**
- Line 726, 809: Minimum price of 1000 INR (might filter budget rooms)
- Lines 63-127: `is_valid_room_name()` function
- Lines 633-642: Flight/cross-sell filtering

## Advanced Debugging

### Check Saved HTML Files

The scraper saves debug HTML to `output/debug_html/{session_id}/`

1. Find the most recent session folder
2. Open the HTML files in a browser
3. Use DevTools to inspect the saved HTML
4. Compare with live Agoda page

### Enable Verbose Logging

In `room_details.py`, the logger shows which selectors work:

```python
logger.debug(f"Found {count} rooms using selector: {selector}")
```

Run the scraper with debug logging enabled to see which selectors are being used.

### Test with Single Hotel

Instead of running the full scraper, test with a single hotel:

```python
# In a test script
hotel = HotelInfo(
    name="Artbuzz Jaipur",
    url="https://www.agoda.com/artbuzz-jaipur/hotel/jaipur-in.html",
    # ... other fields
)

rooms = await scrape_hotel_rooms(page, hotel, check_in, config)
print(f"Found {len(rooms)} rooms")
for room in rooms:
    print(f"  - {room.room_type}: {room.price}")
```

## Reporting Your Findings

Once you've completed the inspection, create an issue or comment with:

1. **Screenshots** of room elements and DevTools
2. **HTML snippets** showing the actual structure
3. **Selector comparison** - what changed vs. what's in the code
4. **Recommended updates** - which lines in `room_details.py` need changes

## Example Report Template

```markdown
## Agoda Selector Inspection Results

### Date Inspected: 2025-12-09

### Room Container
- **Tag:** div
- **Primary Attribute:** data-selenium="room-panel"
- **Classes:** RoomGridItem PropertyCard
- **Status:** ✅ Matches current code / ❌ Changed from code

### Room Name
- **Tag:** span  
- **Primary Attribute:** data-selenium="room-name"
- **Classes:** RoomName
- **Example value:** "Deluxe Room"
- **Status:** ✅ Matches / ❌ Changed

### Room Price
- **Tag:** strong
- **Primary Attribute:** data-ppapi="room-price"
- **Format:** "R . 3,939"
- **Status:** ✅ Matches / ❌ Changed

### Required Code Changes
- [ ] None - selectors are correct
- [ ] Update room container selector
- [ ] Update room name selector
- [ ] Update price selector
- [ ] Adjust validation logic
- [ ] Update price format pattern

### Screenshots
[Attach screenshots here]

### Additional Notes
[Any other observations]
```

## Need Help?

If you're unsure about any findings or need help interpreting the HTML structure, share:
1. Screenshots of the DevTools showing the element
2. Copy of the HTML snippet
3. Description of what you're trying to extract

We can then analyze together and determine the correct selector updates needed.
