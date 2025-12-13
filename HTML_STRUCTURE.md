# Agoda HTML Structure - Visual Guide

## Expected Room Listing Structure

```
┌─────────────────────────────────────────────────────────────┐
│ AGODA HOTEL PAGE                                            │
└─────────────────────────────────────────────────────────────┘

  ┌───────────────────────────────────────────────────────┐
  │ Rooms Section                                          │
  └───────────────────────────────────────────────────────┘
         │
         ├─ ROOM #1 ─────────────────────────────────────┐
         │  ┌────────────────────────────────────────────┤
         │  │ <div data-selenium="room-panel">          ││  ← ROOM CONTAINER
         │  │                                            ││    (lines 495-509 in code)
         │  │  ┌──────────────────────────────────────┐ ││
         │  │  │ Room Name/Type                        │ ││
         │  │  │ <span data-selenium="room-name">     │ ││  ← ROOM NAME
         │  │  │   Deluxe Room                         │ ││    (lines 646-653 in code)
         │  │  │ </span>                               │ ││
         │  │  └──────────────────────────────────────┘ ││
         │  │                                            ││
         │  │  ┌──────────────────────────────────────┐ ││
         │  │  │ Price                                 │ ││
         │  │  │ <strong data-ppapi="room-price">     │ ││  ← ROOM PRICE
         │  │  │   R . 3,939                          │ ││    (lines 690-698 in code)
         │  │  │ </strong>                             │ ││
         │  │  └──────────────────────────────────────┘ ││
         │  │                                            ││
         │  │  [Amenities, bed type, etc.]              ││
         │  │                                            ││
         │  └────────────────────────────────────────────┘│
         │                                                 │
         ├─ ROOM #2 ─────────────────────────────────────┤
         │  <div data-selenium="room-panel">              │
         │    <span data-selenium="room-name">            │
         │      Superior Suite                            │
         │    </span>                                     │
         │    <strong data-ppapi="room-price">            │
         │      R . 5,299                                 │
         │    </strong>                                   │
         │  </div>                                        │
         │                                                 │
         └─ ROOM #3 ─────────────────────────────────────┘
            ...more rooms...
```

## What the Scraper Does

```
Step 1: Find all room containers
   ┌─────────────────────────────────────────┐
   │ Look for elements matching:             │
   │ - div[data-selenium="room-panel"]       │
   │ - div[data-element-name="room-item"]    │
   │ - div[class*="RoomGridItem"]            │
   │ - ... more fallback selectors           │
   └─────────────────────────────────────────┘
           │
           ↓
   Result: List of room container elements


Step 2: For each room container, extract room name
   ┌─────────────────────────────────────────┐
   │ Within the container, find:             │
   │ - span[data-selenium="room-name"]       │
   │ - h3[data-selenium="room-name"]         │
   │ - ... more fallback selectors           │
   └─────────────────────────────────────────┘
           │
           ↓
   Result: Room name like "Deluxe Room"


Step 3: For each room container, extract price
   ┌─────────────────────────────────────────┐
   │ Within the container, find:             │
   │ - strong[data-ppapi="room-price"]       │
   │ - span[data-ppapi="room-price"]         │
   │ - ... more fallback selectors           │
   └─────────────────────────────────────────┘
           │
           ↓
   Result: Price like "R . 3,939"


Step 4: Validate room name
   ┌─────────────────────────────────────────┐
   │ Check if room name is valid:            │
   │ - Not a UI element (e.g., "Show more")  │
   │ - Not FAQ text (e.g., "What time is")   │
   │ - Not promotional (e.g., "Limited")     │
   │ - Contains room keywords                │
   │ - Length between 3-80 chars             │
   └─────────────────────────────────────────┘
           │
           ↓
   Result: Keep or discard this room


Step 5: Parse price value
   ┌─────────────────────────────────────────┐
   │ Extract number from price text:         │
   │ - Remove "R ." or "₹" prefix            │
   │ - Remove commas                          │
   │ - Parse as float                         │
   │ - Reject if < 1000 INR                   │
   └─────────────────────────────────────────┘
           │
           ↓
   Result: Price as number (e.g., 3939.0)
```

## How to Verify Structure in Browser

### Open DevTools and Inspect

```
Browser View                  DevTools View
┌──────────────────┐         ┌──────────────────────────┐
│ Deluxe Room      │   ←→    │ <div data-selenium=      │
│ WiFi • Breakfast │         │      "room-panel">       │
│ R . 3,939        │         │   <span data-selenium=   │
│ [Book Now]       │         │         "room-name">     │
└──────────────────┘         │     Deluxe Room          │
                             │   </span>                │
                             │   <strong data-ppapi=    │
                             │           "room-price">  │
                             │     R . 3,939            │
                             │   </strong>              │
                             │ </div>                   │
                             └──────────────────────────┘
```

### Use Element Inspector

```
1. Click inspector tool        2. Hover over room
   in DevTools                    on Agoda page

   🔍                             ┌──────────────┐
   ▼                              │ [Highlighted]│
                                  │  Deluxe Room │
                                  │  R . 3,939   │
                                  └──────────────┘
                                         ▼
                                  Shows HTML in
                                  DevTools panel
```

## Common HTML Patterns on Agoda

### Pattern 1: Standard Room Panel

```html
<div data-selenium="room-panel" class="RoomGridItem">
  <div class="RoomHeader">
    <span data-selenium="room-name">Deluxe Room</span>
  </div>
  <div class="RoomPrice">
    <strong data-ppapi="room-price">R . 3,939</strong>
  </div>
</div>
```

### Pattern 2: Alternative Layout

```html
<section class="RoomCard">
  <h3 class="RoomTitle" data-element-name="room-type-name">
    Superior Suite
  </h3>
  <div class="PriceSection">
    <span data-ppapi="room-price">R . 5,299</span>
  </div>
</section>
```

### Pattern 3: Table-Based Layout (Older)

```html
<tr data-selenium="room-row">
  <td class="room-name-cell">
    <a href="#">Executive Room</a>
  </td>
  <td class="price-cell">
    <span data-selenium="display-price">₹4,500</span>
  </td>
</tr>
```

## What to Look For

### ✅ Good Signs (Selector is Working)

- Room container has `data-selenium="room-panel"` attribute
- Room name is inside `<span data-selenium="room-name">`
- Price is in `<strong data-ppapi="room-price">`
- Structure matches the code's expectations

### ❌ Bad Signs (Selector Needs Update)

- Room container uses different attribute (e.g., `data-testid`)
- Room name is in different tag or attribute
- Price uses different format or attribute
- Structure has changed significantly

## Selector Priority

The scraper tries selectors in order (most specific → most generic):

```
Room Container Priority:
1. div[data-selenium="room-panel"]         ← Most specific
2. div[data-element-name="room-item"]
3. div[class*="RoomGridItem"]
...
11. div[class*=room]                       ← Most generic

If #1 finds elements → Use those
If not, try #2 → Use those
If not, try #3 → Use those
... and so on
```

**This is why you should add new selectors at the TOP of the list!**

## Debugging Flowchart

```
Scraper finds 0 rooms
         │
         ↓
    Is room section
    visible on page?
         │
    ┌────┴────┐
   NO        YES
    │          │
    │          ↓
    │     Room container
    │     selector wrong?
    │          │
    │     ┌────┴────┐
    │    YES       NO
    │     │          │
    │     ↓          ↓
    │   Update    Room name
    │   room      selector wrong?
    │   selectors    │
    │              ┌─┴──┐
    │             YES   NO
    │              │     │
    │              ↓     ↓
    │          Update  Validation
    │          name    too strict?
    │          selectors  │
    │                     │
    └─────────────────────┴──→ Check logs
                               & HTML
```

## Next Steps

1. Open Agoda hotel page
2. Use browser DevTools to inspect actual HTML
3. Compare with diagrams above
4. Note any differences
5. Update selectors in `scraper/room_details.py`

See [HOW_TO_INSPECT_SELECTORS.md](HOW_TO_INSPECT_SELECTORS.md) for detailed instructions.
