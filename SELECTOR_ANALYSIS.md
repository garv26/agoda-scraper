# Agoda Scraper Selector Analysis

## Current Selectors Being Used

### Room Name/Type Selectors (lines 646-653 in room_details.py)

The scraper currently tries these selectors in order to extract room names:

1. **`span[data-selenium="room-name"]`** - Primary selector
2. **`h3[data-selenium="room-name"]`** - Alternative for h3 tags  
3. **`span[data-element-name="room-type-name"]`** - Element name based
4. **`a[class*="room.*name"]`** - Class name pattern matching
5. **`span[class*="room.*title|room.*name"]`** - Title/name class patterns
6. **`div[data-selenium*="room.*name"]`** - Div-based room names

### Room Container Selectors (lines 495-509 in room_details.py)

The scraper looks for room containers using these selectors:

1. **`div[data-selenium="room-panel"]`** - Primary room panel container
2. **`div[data-element-name="room-item"]`** - Room item containers
3. **`div[data-selenium="room-item"]`** - Alternative room item
4. **`div[class*="MasterRoom"]`** - MasterRoom class pattern
5. **`tr[data-selenium*="room"]`** - Table row based rooms
6. **`div[class*="room.*grid|room.*item|RoomGrid"]`** - Grid/item patterns
7. **`div[data-ppapi*="room"]`** - PPAPI data attribute
8. **`section[data-element-name*="room"]`** - Section elements
9. **`div[class*="ChildRoomsList|RoomGridItem"]`** - Child room lists
10. **`div[class*="room-card|roomCard"]`** - Card-based layouts
11. **`div[data-testid*="room"]`** - Test ID based selectors

### Price Selectors (lines 690-698 in room_details.py)

For extracting room prices:

1. **`strong[data-ppapi="room-price"]`** - Primary price selector (MOST RELIABLE)
2. **`span[data-ppapi="room-price"]`** - Alternative span-based price
3. **`span[data-selenium="display-price"]`** - Display price
4. **`span[class*="price.*amount|final.*price"]`** - Price amount patterns
5. **`div[data-element-name="final-price"]`** - Final price element
6. **`span[class*="PropertyCardPrice"]`** - Property card price

### Price Format Patterns (lines 712-717 in room_details.py)

The scraper handles these price formats:

1. **`R . 3,939`** - Agoda's INR format (R with space and dot)
2. **`₹3,939`** - Rupee symbol format
3. **`Rs. 3939`** - Rupees abbreviation
4. **`INR 3939`** - Currency code format

## Validation Logic

### Room Name Validation (is_valid_room_name function, lines 63-127)

The scraper filters out invalid room names using these checks:

1. **Minimum length**: Must be at least 3 characters
2. **Question marks**: Rejects names with `?` (likely FAQ text)
3. **Question starters**: Filters "does", "what", "how", "is", "can", etc.
4. **Room type keywords**: Accepts names starting with valid room types:
   - deluxe, standard, superior, premium, executive, family, luxury
   - triple, quad, single, double, twin, suite, studio, room
   - villa, cottage, bungalow, apartment, penthouse, etc.
5. **Promotional text**: Filters names starting with promo text like:
   - "limited time", "last minute", "super saver", "special offer"
6. **Maximum length**: Rejects names longer than 80-120 characters
7. **Blacklist**: Filters UI elements like "select your room", "show more rooms"
8. **Garbage detection**: Filters concatenated keywords like multiple "wifi", "sponsored"

## Known Issues & Concerns

### Potential Issues with Current Selectors:

1. **Agoda's Dynamic Structure**: Agoda uses React and loads rooms dynamically via AJAX
   - The selectors may be outdated if Agoda changed their HTML structure
   - The `data-selenium`, `data-ppapi`, and `data-element-name` attributes are most reliable

2. **Room Name Extraction Fallback** (lines 664-670):
   - Uses regex pattern matching as fallback
   - Only accepts names with "Room" or "Suite" explicitly
   - This is restrictive and might miss valid room types

3. **Price Minimum Threshold** (line 726, 809):
   - Prices below 1000 INR are rejected
   - This filters out budget rooms and potential valid entries

4. **Flight/Cross-sell Filter** (lines 633-642):
   - Filters elements with flight-related keywords
   - Could be overly aggressive and filter valid rooms

## Recommendations for Verification

Since direct access to Agoda is blocked, here are alternative verification methods:

### 1. Check Debug HTML Files
The scraper saves debug HTML files to `output/debug_html/{session_id}/` (line 241-246). Review these files to see what's actually being captured.

### 2. Review Scraper Logs
Check for log messages that indicate which selectors are working:
- "Found {count} rooms using selector: {selector}" (line 515)
- "Found {count} room elements with selector: {selector}" (line 416)

### 3. Test with Sample Hotel URLs
Run the scraper on a few sample hotels and examine:
- What room_type values are extracted
- Whether prices are captured correctly
- If validation is too restrictive

### 4. Common Selector Issues

Based on the code analysis, here are likely issues:

**Issue 1: Room name selector might be outdated**
- Current: `span[data-selenium="room-name"]`
- Agoda may have changed to different attributes or tags

**Issue 2: Room container selector mismatch**  
- The code tries 11 different patterns but might miss the current structure
- Agoda might be using a new class name or structure not in the list

**Issue 3: Overly strict validation**
- The `is_valid_room_name()` function might be filtering out valid room types
- Example: Budget rooms under ₹1000 are rejected

**Issue 4: Regex fallback is too restrictive**
- Line 664: Only matches if text contains "Room" or "Suite"
- Misses: "Deluxe King", "Executive Twin", "Family Villa"

## Next Steps

1. **Review actual scraped data** - Check what room_type values are being extracted
2. **Compare with Agoda's current HTML** - Use browser DevTools on Agoda site
3. **Update selectors** - Based on findings from HTML inspection
4. **Adjust validation** - Relax overly strict filters if needed
5. **Test with sample hotels** - Verify improvements work correctly

## How to Inspect Agoda's Current Selectors

### Using Browser DevTools:

1. Open Agoda hotel page in browser
2. Open DevTools (F12)
3. Navigate to Elements tab
4. Find a room listing in the page
5. Right-click on room name → Inspect
6. Check the HTML structure and attributes:
   - Look for `data-selenium`, `data-ppapi`, `data-element-name` attributes
   - Note the tag name (div, span, h3, etc.)
   - Check class names
7. Repeat for price elements
8. Compare with selectors in `room_details.py`

### Key Elements to Check:

- **Room container**: The div/section that wraps each room
- **Room name/type**: The element containing room title
- **Price element**: The element showing the price value
- **Currency format**: How prices are formatted (R . X,XXX vs ₹X,XXX)

### Screenshot Key Areas:

1. Room listing section with multiple rooms
2. Individual room card/panel showing:
   - Room name
   - Price
   - Amenities
3. Expanded view (after clicking "Show more rooms")
4. HTML source of room elements in DevTools

## Code Locations for Updates

If selectors need updating, modify these sections in `room_details.py`:

- **Room name selectors**: Lines 646-653
- **Room container selectors**: Lines 495-509  
- **Price selectors**: Lines 690-698
- **Price patterns**: Lines 712-717
- **Validation logic**: Lines 63-127 (if too restrictive)

