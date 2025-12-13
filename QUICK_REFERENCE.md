# Quick Reference: Agoda Selectors to Verify

## 🎯 Priority Selectors to Check

### 1️⃣ Room Container (HIGHEST PRIORITY)
**What to find:** The `<div>` or `<section>` that wraps each room listing

**Current selector in code:**
```
div[data-selenium="room-panel"]
```

**How to check:**
1. Hover over a complete room listing on Agoda
2. In DevTools, find the outermost container
3. Check if it has `data-selenium="room-panel"` attribute

**If different:** Note the actual tag name and attributes

---

### 2️⃣ Room Name/Type (HIGH PRIORITY)
**What to find:** The element containing "Deluxe Room", "Standard Suite", etc.

**Current selector in code:**
```
span[data-selenium="room-name"]
```

**How to check:**
1. Click on the room name text in Agoda
2. Check the HTML element in DevTools
3. Note the tag and `data-selenium` attribute

**If different:** Note the actual selector

---

### 3️⃣ Room Price (HIGH PRIORITY)
**What to find:** The element showing the price number

**Current selector in code:**
```
strong[data-ppapi="room-price"]
```

**How to check:**
1. Click on a room price in Agoda
2. Check the HTML element in DevTools
3. Note the tag and `data-ppapi` attribute
4. Check the price format (e.g., "R . 3,939" vs "₹3,939")

**If different:** Note the actual selector and format

---

## ✅ Quick Verification Checklist

Open this in Agoda while inspecting:

- [ ] Find a room listing on Agoda
- [ ] Open DevTools (F12)
- [ ] Click element inspector (top-left in DevTools)

**Room Container:**
- [ ] Hover over entire room card
- [ ] Note the container's `data-selenium` attribute: __________________
- [ ] Does it match `room-panel`? YES / NO

**Room Name:**
- [ ] Click on room name text
- [ ] Note the element's tag: __________________
- [ ] Note the `data-selenium` attribute: __________________
- [ ] Does it match `span[data-selenium="room-name"]`? YES / NO
- [ ] Example room name extracted: __________________

**Room Price:**
- [ ] Click on price number
- [ ] Note the element's tag: __________________
- [ ] Note the `data-ppapi` attribute: __________________
- [ ] Does it match `strong[data-ppapi="room-price"]`? YES / NO
- [ ] Price format (e.g., "R . 3,939"): __________________

---

## 📸 Screenshots Needed

Take these screenshots for reference:

1. **Full page** - Shows multiple rooms
2. **Room element highlighted** - With DevTools showing HTML
3. **Room name element** - Zoomed in on name in DevTools
4. **Price element** - Zoomed in on price in DevTools

---

## 🔧 Quick Fix Guide

### If room container changed:

Edit `scraper/room_details.py` line ~497:
```python
room_selectors = [
    {'tag': 'NEW_TAG', 'attrs': {'data-selenium': 'NEW_ATTRIBUTE'}},
    # Keep old ones as fallback
    {'tag': 'div', 'attrs': {'data-selenium': 'room-panel'}},
    # ...
]
```

### If room name changed:

Edit `scraper/room_details.py` line ~647:
```python
name_selectors = [
    {'tag': 'NEW_TAG', 'attrs': {'data-selenium': 'NEW_ATTRIBUTE'}},
    # Keep old ones as fallback
    {'tag': 'span', 'attrs': {'data-selenium': 'room-name'}},
    # ...
]
```

### If price changed:

Edit `scraper/room_details.py` line ~691:
```python
price_selectors = [
    {'tag': 'NEW_TAG', 'attrs': {'data-ppapi': 'NEW_ATTRIBUTE'}},
    # Keep old ones as fallback
    {'tag': 'strong', 'attrs': {'data-ppapi': 'room-price'}},
    # ...
]
```

---

## 🚨 Most Common Issues

### Room names show garbage text
→ **Check:** Room name selector is grabbing wrong element
→ **Fix:** Update `name_selectors` with correct element

### "No Rooms Found" everywhere
→ **Check:** Room container selector not matching
→ **Fix:** Update `room_selectors` with correct container

### Prices are missing (None/empty)
→ **Check:** Price selector wrong or price format changed
→ **Fix:** Update `price_selectors` and price patterns

### Valid rooms being filtered out
→ **Check:** Validation too strict (e.g., min price ₹1000)
→ **Fix:** Adjust `is_valid_room_name()` or price thresholds

---

## 💡 Tips

- **Priority Order:** Selectors are tried in order - put most specific/reliable first
- **Keep Fallbacks:** Don't remove old selectors, just add new ones at the top
- **Test Changes:** Run on 1-2 hotels first before full scrape
- **Check Logs:** Look for "Found X rooms using selector: Y" messages

---

## 📚 More Help

- Full details: [SELECTOR_ANALYSIS.md](SELECTOR_ANALYSIS.md)
- Step-by-step guide: [HOW_TO_INSPECT_SELECTORS.md](HOW_TO_INSPECT_SELECTORS.md)
- Main README: [README_SELECTORS.md](README_SELECTORS.md)
- Analyze tool: `python analyze_selectors.py`
