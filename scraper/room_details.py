"""Room details scraper for individual Agoda hotel pages."""

import re
import logging
import asyncio
import os
import json
import random
from datetime import datetime, timedelta
from typing import Optional, Callable
from playwright.async_api import Page
from bs4 import BeautifulSoup

from .models import HotelInfo, RoomData, ScraperConfig
from .browser import random_delay, wait_for_element, safe_click, scroll_to_bottom
from .hotel_listing import build_hotel_url_with_dates

logger = logging.getLogger(__name__)

# Blacklist of known UI text that should not be treated as room names
ROOM_NAME_BLACKLIST = [
    "select your room",
    "show more rooms",
    "view all rooms",
    "see all rooms",
    "choose room",
    "book now",
    "check availability",
    "more options",
    "agodasponsored",
    "express check-in",
    "free wifi",
    "is car parking",
    "what bars are",
    "what is the price",
    "does the property",
    "offers connecting",
    "adjoining rooms",
    "how far is",
    "what time is",
    "what are the",
    "is there a",
    "can i bring",
    "do i need",
    "what kind of",
]

# Valid room type keywords - if name starts with these, it's a real room name
ROOM_TYPE_KEYWORDS = [
    'deluxe', 'standard', 'superior', 'premium', 'classic', 'executive', 
    'family', 'luxury', 'triple', 'quad', 'single', 'double', 'twin',
    'suite', 'studio', 'room', 'villa', 'cottage', 'bungalow', 'apartment',
    'penthouse', 'loft', 'chalet', 'cabin', 'maharaja', 'maharani',
    'king', 'queen', 'grand', 'junior', 'master', 'comfort', 'budget',
    'economy', 'day use', 'luxe'
]

# Promotional text that should NOT be room names (unless preceded by room type)
PROMO_STARTERS = [
    'limited time', 'last minute', 'super saver', 'super hot', 'special offer',
    'flash sale', 'early bird', 'member exclusive', 'best price', 'lowest price',
    'price includes', '% discount', '% off'
]


def is_valid_room_name(name: str) -> bool:
    """Check if the room name is valid (not a UI element or pure promotional text)."""
    if not name or len(name) < 3:
        return False
    
    name_lower = name.lower().strip()
    
    # Room names should never be questions
    if '?' in name:
        return False
    
    # Room names starting with question words are likely FAQ text
    question_starters = ['does ', 'what ', 'how ', 'is ', 'can ', 'do ', 'are ', 'will ', 'where ']
    if any(name_lower.startswith(q) for q in question_starters):
        return False
    
    # Check if name starts with a valid room type keyword
    starts_with_room_type = any(name_lower.startswith(kw) for kw in ROOM_TYPE_KEYWORDS)
    
    # If it starts with a room type keyword, it's valid (even with promo text appended)
    # e.g., "Triple Room (15% off on session of Spa...)" is valid
    if starts_with_room_type:
        # But still reject if it's too long (likely garbage concatenation)
        if len(name) > 120:
            return False
        return True
    
    # For names that DON'T start with room type keywords, apply stricter validation
    
    # Reject if it starts with promotional text
    for promo in PROMO_STARTERS:
        if name_lower.startswith(promo):
            return False
    
    # Reject if it's purely promotional (contains promo text and NO room type keyword)
    has_promo = any(promo in name_lower for promo in PROMO_STARTERS)
    has_room_type = any(kw in name_lower for kw in ROOM_TYPE_KEYWORDS)
    if has_promo and not has_room_type:
        return False
    
    # Reject if contains exclamation marks (purely promotional text)
    if '!' in name:
        return False
    
    # Check blacklist
    for blacklisted in ROOM_NAME_BLACKLIST:
        if blacklisted in name_lower:
            return False
    
    # Room name should not be too long (likely concatenated text)
    if len(name) > 80:
        return False
    
    # Should not contain multiple keywords concatenated (indicates garbage)
    garbage_indicators = ['express', 'wifi', 'sponsored', 'agoda', 'booking', 'check-in']
    garbage_count = sum(1 for kw in garbage_indicators if kw in name_lower)
    if garbage_count >= 2:
        return False
    
    # Should not start with "king" followed by random text (FAQ/description)
    if name_lower.startswith('king') and not any(rm in name_lower for rm in ['room', 'suite', 'bed', 'deluxe', 'standard']):
        if len(name) > 30:
            return False
    
    return True


def parse_room_grid_api(json_data: dict, hotel: HotelInfo, date_str: str) -> list[RoomData]:
    """
    Parse room data from the NEW Agoda room-grid API (v1).
    
    API endpoint: /api/v1/property/room-grid
    
    Args:
        json_data: The API response containing 'rooms' array
        hotel: Hotel information
        date_str: Date string YYYY-MM-DD
    
    Returns:
        List of RoomData objects
    """
    rooms = []
    
    room_list = json_data.get('rooms', [])
    if not room_list:
        logger.debug(f"No rooms found in room-grid API for {hotel.name}")
        return rooms
    
    logger.debug(f"Found {len(room_list)} rooms in room-grid API")
    
    for room in room_list:
        try:
            room_name = room.get('name', '').strip()
            
            if not room_name or not is_valid_room_name(room_name):
                logger.debug(f"Skipping invalid room name: {room_name}")
                continue
            
            # Extract facilities (amenities)
            amenities = []
            for facility in room.get('facilities', []):
                if isinstance(facility, dict) and facility.get('text'):
                    amenities.append(facility['text'])
            
            # Extract features (room size, occupancy, bed type)
            features = room.get('features', [])
            bed_type = None
            max_occupancy = None
            
            for feature in features:
                if isinstance(feature, dict):
                    text = feature.get('text', '')
                    feature_type = feature.get('type', '')
                    
                    if feature_type == 'BEDROOM_LAYOUT':
                        bed_type = text
                    elif feature_type == 'MAX_OCCUPANCY':
                        # Extract number from "Max X adults"
                        import re
                        match = re.search(r'(\d+)', text)
                        if match:
                            max_occupancy = int(match.group(1))
            
            # Process offers (pricing and availability)
            offers = room.get('offers', [])
            if not offers:
                # Room exists but no offers available
                rooms.append(RoomData(
                    hotel_name=hotel.name,
                    date=date_str,
                    room_type=room_name,
                    price=None,
                    currency="INR",
                    amenities=amenities,
                    is_available=False,
                    bed_type=bed_type,
                    max_occupancy=max_occupancy,
                    hotel_location=hotel.location,
                    hotel_rating=hotel.rating,
                    hotel_star_rating=hotel.star_rating,
                    hotel_review_count=hotel.review_count,
                ))
                continue
            
            # Process each offer for this room
            for offer in offers:
                try:
                    # Extract price from new API format
                    price_obj = offer.get('price', {})
                    price = None
                    if isinstance(price_obj, dict):
                        # Try new API format first: price.final.amountNumber
                        final_price = price_obj.get('final', {})
                        if isinstance(final_price, dict):
                            price = final_price.get('amountNumber') or final_price.get('amount')
                        
                        # Fallback to old format if not found
                        if not price:
                            price = price_obj.get('perNight', {}).get('exclusive', {}).get('display')
                        if not price:
                            price = price_obj.get('perRoomPerNight', {}).get('exclusive', {}).get('display')
                    
                    # Extract meal plan and cancellation from benefits
                    meal_plan = None
                    cancellation_policy = None
                    
                    benefits = offer.get('benefits', [])
                    for benefit in benefits:
                        if isinstance(benefit, dict):
                            text = benefit.get('text', '').lower()
                            if 'breakfast' in text or 'meal' in text:
                                meal_plan = benefit.get('text')
                            elif 'cancel' in text or 'refund' in text:
                                cancellation_policy = benefit.get('text')
                    
                    # Check policies for cancellation
                    if not cancellation_policy:
                        policies = offer.get('policies', [])
                        for policy in policies:
                            if isinstance(policy, dict):
                                title = policy.get('title', '').lower()
                                if 'cancel' in title or 'refund' in title:
                                    cancellation_policy = policy.get('title')
                                    break
                    
                    # Create room data
                    rooms.append(RoomData(
                        hotel_name=hotel.name,
                        date=date_str,
                        room_type=room_name,
                        price=float(price) if price else None,
                        currency="INR",
                        amenities=amenities,
                        is_available=True,
                        cancellation_policy=cancellation_policy,
                        meal_plan=meal_plan,
                        bed_type=bed_type,
                        max_occupancy=max_occupancy,
                        hotel_location=hotel.location,
                        hotel_rating=hotel.rating,
                        hotel_star_rating=hotel.star_rating,
                        hotel_review_count=hotel.review_count,
                    ))
                    
                    logger.debug(f"Parsed room offer: {room_name} - ₹{price}")
                    
                except Exception as e:
                    logger.warning(f"Error parsing offer for {room_name}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error parsing room from room-grid API: {e}")
            continue
    
    return deduplicate_rooms(rooms)


def parse_room_json(json_data: dict, hotel: HotelInfo, date_str: str) -> list[RoomData]:
    """
    Parse room data from Agoda's LEGACY roomGridData API response.
    
    Args:
        json_data: The full API response (could be nested in various ways)
        hotel: Hotel information
        date_str: Date string YYYY-MM-DD
    
    Returns:
        List of RoomData objects
    """
    rooms = []
    
    # NEW API FORMAT: Check for room-grid v1 format first
    if 'rooms' in json_data and isinstance(json_data.get('rooms'), list):
        # Check if this is the new format (has 'propertyId', 'propertyName', etc.)
        if 'propertyId' in json_data or 'propertyName' in json_data:
            logger.info(f"Detected NEW room-grid API format for {hotel.name}")
            return parse_room_grid_api(json_data, hotel, date_str)
    
    # LEGACY API FORMAT: Navigate to masterRooms array
    # The data might be at different paths depending on the API endpoint
    master_rooms = None
    
    # Try different possible paths
    if 'roomGridData' in json_data:
        room_grid = json_data.get('roomGridData', {})
        if isinstance(room_grid, dict):
            master_rooms = room_grid.get('masterRooms', [])
    elif 'datelessMasterRoomInfo' in json_data:
        master_rooms = json_data.get('datelessMasterRoomInfo', [])
    elif 'masterRooms' in json_data:
        master_rooms = json_data.get('masterRooms', [])
    elif 'data' in json_data and isinstance(json_data['data'], dict):
        master_rooms = json_data['data'].get('masterRooms', [])
    
    if not master_rooms:
        logger.warning(f"No masterRooms found in legacy JSON for {hotel.name}")
        return rooms
    
    logger.debug(f"Found {len(master_rooms)} master rooms in JSON")
    
    for master_room in master_rooms:
        try:
            # Extract room name (already clean!)
            room_name = master_room.get('name', '').strip()
            
            if not room_name or not is_valid_room_name(room_name):
                logger.debug(f"Skipping invalid room name: {room_name}")
                continue
            
            # Extract price
            price = master_room.get('cheapestPrice') or master_room.get('beforeDiscountPrice')
            
            # Check availability
            availability = master_room.get('firstRoomAvailability', 0)
            is_available = availability > 0 and price is not None
            
            # Extract amenities from multiple sources
            amenities = []
            
            # From amenities array
            if master_room.get('amenities'):
                for amenity in master_room['amenities']:
                    if isinstance(amenity, dict):
                        amenity_name = amenity.get('name') or amenity.get('title', '')
                        if amenity_name:
                            amenities.append(amenity_name)
                    elif isinstance(amenity, str):
                        amenities.append(amenity)
            
            # From features array
            if master_room.get('features'):
                for feature in master_room['features']:
                    if isinstance(feature, dict) and feature.get('title'):
                        title = feature['title']
                        # Skip size info, keep actual amenities
                        if 'Room size:' not in title and 'bed' not in title.lower():
                            amenities.append(title)
            
            # From facility groups
            if master_room.get('facilityGroups'):
                for group in master_room['facilityGroups']:
                    if isinstance(group, dict) and group.get('name'):
                        amenities.append(group['name'])
            
            # Clean amenities
            amenities = [a.strip() for a in amenities if a and isinstance(a, str)]
            amenities = list(set(amenities))  # Remove duplicates
            
            # Extract bed type
            bed_type = None
            bed_config = master_room.get('bedConfigurationSummary') or master_room.get('beddingConfig')
            if bed_config and isinstance(bed_config, dict):
                bed_type = bed_config.get('title') or bed_config.get('name')
            
            # If not found, check numberOfBeds field
            if not bed_type and master_room.get('numberOfBeds'):
                bed_type = master_room['numberOfBeds']
            
            # Extract meal plan from propagandaMessages
            meal_plan = None
            propaganda = master_room.get('propagandaMessages', [])
            for msg in propaganda:
                if isinstance(msg, dict):
                    title = msg.get('title', '').lower()
                    if 'breakfast' in title:
                        meal_plan = msg.get('title', 'Breakfast Included')
                        break
            
            # Also check filters in sub-rooms
            if not meal_plan and master_room.get('rooms'):
                for sub_room in master_room['rooms']:
                    filters = sub_room.get('filters', [])
                    for f in filters:
                        if isinstance(f, dict):
                            filter_name = f.get('name', '').lower()
                            if 'breakfast' in filter_name:
                                meal_plan = f.get('name', 'Breakfast Included')
                                break
                    if meal_plan:
                        break
            
            # Extract cancellation policy
            cancellation_policy = None
            if master_room.get('rooms'):
                for sub_room in master_room['rooms']:
                    # Check for cancellation info in filters or properties
                    filters = sub_room.get('filters', [])
                    for f in filters:
                        if isinstance(f, dict):
                            filter_id = f.get('id', '').lower()
                            filter_name = f.get('name', '').lower()
                            if 'refund' in filter_id or 'refund' in filter_name or 'cancel' in filter_name:
                                cancellation_policy = f.get('name')
                                break
                    if cancellation_policy:
                        break
            
            # Extract max occupancy
            max_occupancy = master_room.get('maxOccupancy')
            
            # Create RoomData object
            room_data = RoomData(
                hotel_name=hotel.name,
                date=date_str,
                room_type=room_name,
                price=float(price) if price else None,
                currency="INR",  # Could extract from API if available
                amenities=amenities,
                is_available=is_available,
                cancellation_policy=cancellation_policy,
                meal_plan=meal_plan,
                bed_type=bed_type,
                max_occupancy=max_occupancy,
                hotel_location=hotel.location,
                hotel_rating=hotel.rating,
                hotel_star_rating=hotel.star_rating,
                hotel_review_count=hotel.review_count,
            )
            
            rooms.append(room_data)
            logger.debug(f"Parsed room from JSON: {room_name} - ₹{price}")
            
        except Exception as e:
            logger.warning(f"Error parsing master room from JSON: {e}")
            continue
    
    return deduplicate_rooms(rooms)


async def scrape_hotel_rooms(
    page: Page,
    hotel: HotelInfo,
    check_in: datetime,
    config: ScraperConfig,
    session_id: Optional[str] = None,
) -> list[RoomData]:
    """
    Scrape room information for a specific hotel and date using JSON API interception.
    Falls back to HTML parsing if JSON is not available.
    
    Args:
        page: Playwright page instance
        hotel: Hotel information
        check_in: Check-in date
        config: Scraper configuration
        session_id: Optional session ID for debugging
    
    Returns:
        List of RoomData objects for all available rooms
    """
    check_out = check_in + timedelta(days=1)
    
    # Build URL with dates
    url = build_hotel_url_with_dates(
        hotel.url,
        check_in,
        check_out,
        guests=config.guests,
        rooms=config.rooms,
    )
    
    logger.debug(f"Navigating to hotel page: {url}")

    # Storage for API data
    api_data = {'received': False, 'json': None}
    
    async def intercept_room_api(response):
        """Intercept and capture room data API response."""
        try:
            url_str = response.url
            
            # NEW: The primary room data API endpoint (as of Dec 2024)
            if "/api/v1/property/room-grid" in url_str:
                status = response.status
                logger.info(f"[Room Grid API] {hotel.name} {check_in.date()} - status {status}")
                
                if status == 200:
                    try:
                        json_response = await response.json()
                        # Check if response contains actual room data
                        if isinstance(json_response, dict) and 'rooms' in json_response:
                            rooms_count = len(json_response.get('rooms', []))
                            if rooms_count > 0:
                                api_data['json'] = json_response
                                api_data['received'] = True
                                logger.info(f"[JSON API] ✅ {hotel.name} - Captured {rooms_count} rooms from room-grid API")
                            else:
                                logger.info(f"[JSON API] ⚠️  {hotel.name} - room-grid API returned 0 rooms (sold out: {json_response.get('isSoldOut', False)})")
                        else:
                            logger.debug(f"[JSON API] ⚠️  {hotel.name} - room-grid API has unexpected structure")
                                    
                    except Exception as e:
                        logger.warning(f"[JSON API] Parse error for {hotel.name}: {e}")
                else:
                    logger.warning(f"[JSON API] ❌ {hotel.name} - room-grid API Status {status}")
            
            # FALLBACK: Old API endpoints (BelowFoldParams/GetSecondaryData)
            elif "BelowFoldParams/GetSecondaryData" in url_str:
                status = response.status
                logger.debug(f"[Legacy API] {hotel.name} - GetSecondaryData called (status {status})")
                
                if status == 200 and not api_data['received']:
                    try:
                        json_response = await response.json()
                        # Check if this old endpoint actually contains room data (not just empty arrays)
                        rooms_count = 0
                        if isinstance(json_response, dict):
                            # Check roomGridData.masterRooms
                            if 'roomGridData' in json_response:
                                room_grid = json_response.get('roomGridData', {})
                                if isinstance(room_grid, dict):
                                    master_rooms = room_grid.get('masterRooms', [])
                                    rooms_count = len(master_rooms) if isinstance(master_rooms, list) else 0
                            # Check direct masterRooms
                            elif 'masterRooms' in json_response:
                                master_rooms = json_response.get('masterRooms', [])
                                rooms_count = len(master_rooms) if isinstance(master_rooms, list) else 0
                        
                        if rooms_count > 0:
                            api_data['json'] = json_response
                            api_data['received'] = True
                            logger.info(f"[JSON API] ✅ {hotel.name} - Captured {rooms_count} rooms from legacy API")
                        else:
                            logger.debug(f"[JSON API] ⚠️  {hotel.name} - legacy API has no rooms (sold out or wrong endpoint)")
                        
                        # Save sample for debugging (optional - first time only)
                        if session_id:
                            api_samples_dir = "output/api_samples"
                            os.makedirs(api_samples_dir, exist_ok=True)
                            sample_path = os.path.join(api_samples_dir, f"{session_id}_sample.json")
                            if not os.path.exists(sample_path):
                                with open(sample_path, 'w', encoding='utf-8') as f:
                                    json.dump(json_response, f, indent=2, ensure_ascii=False)
                                logger.debug(f"Saved API sample to {sample_path}")
                                    
                    except Exception as e:
                        logger.warning(f"[JSON API] Parse error for {hotel.name}: {e}")
                else:
                    logger.warning(f"[JSON API] ❌ {hotel.name} - Status {status}")
        except Exception as e:
            logger.debug(f"Response intercept error: {e}")

    page.on("response", intercept_room_api)

    try:
        # Add random delay before navigation to appear more human-like
        await random_delay(2, 5)
        
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)  # Increased initial wait
        
        # Dismiss any popups
        await dismiss_hotel_popups(page)
        
        # Human-like scrolling: variable scroll distances and delays
        scroll_positions = [0.25, 0.5, 0.75, 0.9]
        for pos in scroll_positions:
            # Variable scroll distance (more human-like)
            scroll_distance = random.randint(400, 800)
            await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            # Variable delays between scrolls (2-4 seconds)
            await random_delay(2, 4)
        
        # Use fixed delay instead of networkidle (less detectable)
        await asyncio.sleep(3)
        
        # Wait for API response (up to 15 seconds with longer intervals)
        for _ in range(15):
            if api_data['received']:
                break
            await asyncio.sleep(1)
        
        date_str = check_in.strftime("%Y-%m-%d")
        
        # Try JSON parsing first
        if api_data['received'] and api_data['json']:
            logger.info(f"[Parser] Using JSON API for {hotel.name}")
            rooms = parse_room_json(api_data['json'], hotel, date_str)
            
            if rooms:
                logger.info(f"[JSON Success] {hotel.name}: {len(rooms)} rooms extracted")
                return rooms
            else:
                logger.warning(f"[JSON Empty] {hotel.name}: No valid rooms in JSON, falling back to HTML")
        else:
            logger.info(f"[Parser] JSON API not received for {hotel.name}, using HTML fallback")
        
        # Fallback to HTML parsing
        room_loaded = await wait_for_room_listings(page)
        
        if not room_loaded:
            logger.warning(f"Room listings not found for {hotel.name} on {check_in.date()}")
            return [RoomData(
                hotel_name=hotel.name,
                date=date_str,
                room_type="No Rooms Found",
                price=None,
                currency=hotel.currency,
                amenities=[],
                is_available=False,
                hotel_location=hotel.location,
                hotel_rating=hotel.rating,
                hotel_star_rating=hotel.star_rating,
                hotel_review_count=hotel.review_count,
            )]
        
        # Expand room listings if there's a "Show more" button
        await expand_room_listings(page)
        
        # Scroll more to load all room content with longer pauses
        await scroll_to_bottom(page, scroll_pause_range=(2, 4), max_scrolls=8)
        
        # Use fixed delay instead of networkidle (less detectable)
        await asyncio.sleep(4)  # Longer wait for React to finish rendering
        
        # Parse room data from HTML
        html = await page.content()
        
        # Save rendered HTML for debugging
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_folder = os.path.join("output", "debug_html", session_id)
        os.makedirs(debug_folder, exist_ok=True)
        debug_html_path = os.path.join(debug_folder, f"debug_{hotel.name[:30].replace(' ', '_')}_{check_in.strftime('%Y%m%d')}.html")
        if not os.path.exists(debug_html_path):
            with open(debug_html_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.debug(f"Saved rendered HTML to {debug_html_path}")
        
        rooms = parse_room_listings(html, hotel, check_in)
        
        if not rooms:
            logger.warning(f"No rooms parsed from HTML for {hotel.name} on {check_in.date()}")
            return [RoomData(
                hotel_name=hotel.name,
                date=date_str,
                room_type="No Rooms Found",
                price=None,
                currency=hotel.currency,
                amenities=[],
                is_available=False,
                hotel_location=hotel.location,
                hotel_rating=hotel.rating,
                hotel_star_rating=hotel.star_rating,
                hotel_review_count=hotel.review_count,
            )]
        
        logger.info(f"[HTML Success] {hotel.name}: {len(rooms)} rooms extracted")
        return rooms
        
    except Exception as e:
        logger.error(f"Error scraping rooms for {hotel.name}: {e}")
        return [RoomData(
            hotel_name=hotel.name,
            date=check_in.strftime("%Y-%m-%d"),
            room_type="Error",
            price=None,
            currency=hotel.currency,
            amenities=[],
            is_available=False,
            hotel_location=hotel.location,
            hotel_rating=hotel.rating,
            hotel_star_rating=hotel.star_rating,
            hotel_review_count=hotel.review_count,
        )]


async def dismiss_hotel_popups(page: Page):
    """Dismiss popups on hotel detail pages."""
    popup_selectors = [
        '[data-selenium="close-button"]',
        '.ab-close-button',
        '[aria-label="Close"]',
        'button[class*="close"]',
        '.Modal__Close',
        '#onetrust-accept-btn-handler',
        '[data-element-name="close-button"]',
    ]
    
    for selector in popup_selectors:
        try:
            await safe_click(page, selector, timeout=1000)
            await random_delay(0.2, 0.4)
        except Exception:
            pass


async def wait_for_room_listings(page: Page, timeout: int = 30000) -> bool:
    """Wait for room listings to appear on the page."""
    import os
    
    # First, wait for initial page load
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass

    # Use fixed delay instead of networkidle (less detectable)
    await asyncio.sleep(3)
    
    # Try to click on the "Rooms" section/tab to trigger room loading
    rooms_tab_selectors = [
        'a:has-text("Rooms")',
        'button:has-text("Rooms")',
        '[data-element-name*="rooms"]',
        '[href*="#rooms"]',
        'a[href*="roomsAndRates"]',
        '[data-selenium*="room"]',
        # Scroll to rooms section anchor
        '#roomsAndRates',
        '#rooms',
    ]
    
    for selector in rooms_tab_selectors:
        try:
            elem = page.locator(selector).first
            if await elem.is_visible(timeout=2000):
                await elem.click()
                logger.debug(f"Clicked rooms tab with selector: {selector}")
                await asyncio.sleep(4)  # Longer wait after clicking
                break
        except Exception:
            continue
    
    # Human-like scrolling: variable scroll distances and delays
    scroll_positions = [0.2, 0.4, 0.6, 0.8, 0.95]
    for pos in scroll_positions:
        # Variable scroll distance (more human-like)
        scroll_distance = random.randint(300, 700)
        await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
        # Variable delays between scrolls (2-4 seconds)
        await random_delay(2, 4)
    
    # Use fixed delay instead of networkidle (less detectable)
    await asyncio.sleep(4)
    
    # Try a direct wait on typical room selectors before falling back to polling.
    # This helps ensure React has finished injecting the room grid into the DOM.
    direct_room_selector = (
        '[data-ppapi="room-price"], '
        '[data-selenium="room-panel"], '
        '[data-selenium="room-name"], '
        '[data-testid*="room"], '
        '[class*="RoomGridItem"]'
    )
    try:
        await page.wait_for_selector(direct_room_selector, timeout=timeout)
        logger.debug("Room selector appeared via direct wait")
        return True
    except Exception:
        # Fall back to the more exhaustive polling logic below
        pass
    
    # Additional wait for React to render
    await asyncio.sleep(3)
    
    # Poll for room elements with retry
    room_selectors = [
        '[data-ppapi="room-price"]',  # Price elements (most reliable)
        '[data-selenium="room-panel"]',
        '[data-selenium="room-name"]',
        '[data-element-name="room-item"]',
        '.MasterRoom',
        '.RoomGrid',
        '#roomsAndRates',
        '[class*="ChildRoomsList"]',
        '[class*="RoomGridItem"]',
        '[data-element-name*="room"]',
        # Additional selectors
        '[class*="room-grid"]',
        '[class*="RoomList"]',
        '[data-testid*="room"]',
        '[class*="room-card"]',
        'div[class*="room"]',
        # Price-based detection
        '[class*="Price"]',
        '[data-element-name="final-price"]',
    ]
    
    # Try multiple times with increasing wait
    for attempt in range(5):
        for selector in room_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    logger.debug(f"Found {count} room elements with selector: {selector}")
                    # Wait a bit more for all rooms to load
                    await asyncio.sleep(2)
                    return True
            except Exception:
                continue
        
        # Scroll more with variable distance and wait
        scroll_distance = random.randint(400, 800)
        await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
        await random_delay(2, 4)  # Longer, variable delays
    
    # Final check: look for actual price patterns in visible text
    try:
        has_prices = await page.evaluate('''() => {
            // Look for actual rendered price text like "₹" followed by numbers
            const priceRegex = /₹\s*[\d,]{3,}/;
            const bodyText = document.body.innerText;
            return priceRegex.test(bodyText);
        }''')
        if has_prices:
            logger.debug("Found price patterns in page text")
            return True
    except Exception:
        pass
    
    # Save debug HTML when rooms not found
    try:
        html = await page.content()
        debug_path = "output/debug_no_rooms.html"
        os.makedirs("output", exist_ok=True)
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.debug(f"Saved debug HTML to {debug_path}")
    except Exception:
        pass
    
    return False


async def expand_room_listings(page: Page):
    """Click 'Show more rooms' button if present."""
    expand_selectors = [
        '[data-selenium="show-more-rooms"]',
        'button[class*="ShowMore"]',
        '[data-element-name="show-more-rooms"]',
        'button:has-text("Show more")',
        'a:has-text("Show all rooms")',
    ]
    
    for selector in expand_selectors:
        try:
            clicked = await safe_click(page, selector, timeout=1000)  # Reduced from 2000
            if clicked:
                await random_delay(0.3, 0.7)  # Reduced from (1, 2)
                logger.debug("Expanded room listings")
                break
        except Exception:
            pass


def parse_room_listings(html: str, hotel: HotelInfo, check_in: datetime) -> list[RoomData]:
    """
    Parse room listings from hotel page HTML.
    
    Args:
        html: HTML content of the hotel page
        hotel: Hotel information object
        check_in: Check-in date
    
    Returns:
        List of RoomData objects
    """
    soup = BeautifulSoup(html, "lxml")
    rooms = []
    hotel_name = hotel.name
    date_str = check_in.strftime("%Y-%m-%d")
    
    # Try multiple selector patterns for room containers
    # Based on Agoda's actual structure from browser inspection
    room_selectors = [
        {'tag': 'div', 'attrs': {'data-selenium': 'room-panel'}},
        {'tag': 'div', 'attrs': {'data-element-name': 'room-item'}},
        {'tag': 'div', 'attrs': {'data-selenium': 'room-item'}},
        {'tag': 'div', 'attrs': {'class': re.compile(r'MasterRoom', re.I)}},
        {'tag': 'tr', 'attrs': {'data-selenium': re.compile(r'room', re.I)}},
        {'tag': 'div', 'attrs': {'class': re.compile(r'room.*grid|room.*item|RoomGrid', re.I)}},
        # Additional selectors based on Agoda's actual structure
        {'tag': 'div', 'attrs': {'data-ppapi': re.compile(r'room', re.I)}},
        {'tag': 'section', 'attrs': {'data-element-name': re.compile(r'room', re.I)}},
        # From accessibility tree: room containers have specific patterns
        {'tag': 'div', 'attrs': {'class': re.compile(r'ChildRoomsList|RoomGridItem', re.I)}},
        {'tag': 'div', 'attrs': {'class': re.compile(r'room-card|roomCard', re.I)}},
        {'tag': 'div', 'attrs': {'data-testid': re.compile(r'room', re.I)}},
    ]
    
    room_elements = []
    for selector in room_selectors:
        room_elements = soup.find_all(selector['tag'], attrs=selector['attrs'])
        if room_elements:
            logger.debug(f"Found {len(room_elements)} rooms using selector: {selector}")
            break
    
    if not room_elements:
        # Try alternative approach: look for price elements and find their containers
        price_elements = soup.find_all(attrs={'data-ppapi': 'room-price'})
        if price_elements:
            room_elements = [p.find_parent(['div', 'tr', 'section']) for p in price_elements if p.find_parent(['div', 'tr', 'section'])]
    
    if not room_elements:
        # Another approach: find room name elements and their containers
        room_name_elements = soup.find_all(attrs={'data-selenium': 'room-name'})
        if room_name_elements:
            room_elements = [n.find_parent(['div', 'tr', 'section']) for n in room_name_elements if n.find_parent(['div', 'tr', 'section'])]
    
    if not room_elements:
        # Last resort: look for elements with room-price data attribute specifically
        # This avoids picking up flight/cross-sell prices
        price_elements = soup.find_all(attrs={'data-ppapi': 'room-price'})
        if not price_elements:
            price_elements = soup.find_all(attrs={'data-element-name': 'final-price'})
        
        for price_elem in price_elements:
            # Find the parent container for this room
            parent = price_elem.find_parent(['div', 'section'], recursive=True)
            # Go up max 5 levels to find a reasonable container
            for _ in range(5):
                if parent and parent.name in ['div', 'section']:
                    # Exclude flight/cross-sell elements
                    elem_class = parent.get('class', [])
                    elem_text = str(parent.get('data-element-name', '')) + str(parent.get('data-component', ''))
                    if 'flight' in elem_text.lower() or 'cross-sell' in elem_text.lower():
                        break
                    if any('flight' in c.lower() for c in elem_class if isinstance(c, str)):
                        break
                    room_elements.append(parent)
                    break
                if parent:
                    parent = parent.parent
    
    # Parse each room
    for room_elem in room_elements:
        room_data = extract_room_data(room_elem, hotel, date_str)
        if room_data:
            rooms.append(room_data)
    
    # NOTE: Removed broad regex fallback that was extracting garbage like "king bed", "double bed"
    # Only extract from specific room elements with proper selectors
    if not rooms:
        logger.debug("No room elements found with specific selectors")
    
    # NEW FALLBACK: Extract room info from text patterns if no structured elements found
    if not rooms:
        logger.debug("Trying text-based room extraction as fallback")
        rooms = extract_rooms_from_text(soup, hotel, date_str)
    # Deduplicate by room type (keep the one with lowest price)
    rooms = deduplicate_rooms(rooms)
    
    return rooms

def extract_rooms_from_text(soup: BeautifulSoup, hotel: HotelInfo, date_str: str) -> list[RoomData]:
    """Fallback: Extract room info from page text using regex patterns."""
    rooms = []
    page_text = soup.get_text(' ', strip=True)
    
    # Look for room type patterns followed by prices
    room_patterns = [
        # "Deluxe Room ... ₹3,500" or "Deluxe Room ... R . 3,500"
        r'((?:Deluxe|Standard|Superior|Premium|Executive|Family|Luxury|Suite|Studio|Twin|Double|Single|Queen|King)[\s\w\-]*(?:Room|Suite|Bed)?)\s*(?:.*?)(?:₹|R\s*\.)\s*([\d,]+)',
    ]
    
    for pattern in room_patterns:
        matches = re.findall(pattern, page_text, re.I)
        for match in matches:
            room_type = match[0].strip()
            price_str = match[1].replace(',', '')
            
            if not is_valid_room_name(room_type):
                continue
                
            try:
                price = float(price_str)
                if 1000 <= price <= 500000:  # Reasonable hotel price range
                    rooms.append(RoomData(
                        hotel_name=hotel.name,
                        date=date_str,
                        room_type=room_type,
                        price=price,
                        currency="INR",
                        amenities=[],
                        is_available=True,
                        hotel_location=hotel.location,
                        hotel_rating=hotel.rating,
                        hotel_star_rating=hotel.star_rating,
                        hotel_review_count=hotel.review_count,
                    ))
            except ValueError:
                continue
    
    return rooms
    
def extract_room_data(room_elem, hotel: HotelInfo, date_str: str) -> Optional[RoomData]:
    """
    Extract room information from a room element.
    
    Args:
        room_elem: BeautifulSoup element representing a room
        hotel: Hotel information object
        date_str: Date string (YYYY-MM-DD)
    
    Returns:
        RoomData object or None if extraction fails
    """
    try:
        hotel_name = hotel.name
        room_text = room_elem.get_text(strip=True)
        
        # Skip flight/cross-sell elements - these contain flight prices, not room prices
        elem_attrs = str(room_elem.attrs)
        if any(x in elem_attrs.lower() for x in ['flight', 'cross-sell', 'airline', 'airport']):
            logger.debug("Skipping flight/cross-sell element")
            return None
        
        # Also check text content for flight-related keywords
        text_lower = room_text.lower()
        if any(x in text_lower for x in ['direct flight', 'book your airport', 'rent a car', 'passenger', 'airline']):
            logger.debug("Skipping element with flight-related text")
            return None
        
        # Extract room type/name
        room_type = None
        name_selectors = [
            {'tag': 'span', 'attrs': {'data-selenium': 'masterroom-title-name'}},
            {'tag': 'span', 'attrs': {'data-selenium': 'room-name'}},
            {'tag': 'h3', 'attrs': {'data-selenium': 'room-name'}},
            {'tag': 'span', 'attrs': {'data-element-name': 'room-type-name'}},
            {'tag': 'a', 'attrs': {'class': re.compile(r'room.*name', re.I)}},
            {'tag': 'span', 'attrs': {'class': re.compile(r'room.*title|room.*name', re.I)}},
            {'tag': 'div', 'attrs': {'data-selenium': re.compile(r'room.*name', re.I)}},
        ]
        
        for selector in name_selectors:
            elem = room_elem.find(selector['tag'], attrs=selector['attrs'])
            if elem:
                room_type = elem.get_text(strip=True)
                break
        
        if not room_type:
            # Only accept room names that contain "Room" or "Suite" explicitly
            # This avoids extracting bed types like "king bed", "double bed"
            room_match = re.search(
                r'\b((?:Deluxe|Standard|Superior|Premium|Classic|Executive|Family|Luxury|Triple|Quad)[\s\-]*(?:Room|Suite)(?:\s+(?:King|Queen|Twin|Double))?)',
                room_text,
                re.I
            )
            if room_match:
                room_type = room_match.group(1).strip()
        
        # If no room type found, skip this element - don't create false data
        if not room_type:
            logger.debug(f"Skipping room element - no valid room name found")
            return None
        
        # Clean up room type
        room_type = re.sub(r'\s+', ' ', room_type).strip()[:100]
        
        # Validate room name - reject if it's a UI element or garbage text
        if not is_valid_room_name(room_type):
            logger.debug(f"Skipping invalid room name: {room_type}")
            return None
        
        # Extract price
        # From browser inspection: price format is "R . X,XXX" with \xa0 (non-breaking space)
        price = None
        currency = "INR"
        
        # First try specific selectors (from browser inspection)
        price_selectors = [
            {'tag': 'strong', 'attrs': {'data-ppapi': 'room-price'}},  # Main price selector
            {'tag': 'span', 'attrs': {'data-ppapi': 'room-price'}},
            {'tag': 'span', 'attrs': {'data-selenium': 'display-price'}},
            {'tag': 'span', 'attrs': {'class': re.compile(r'price.*amount|final.*price', re.I)}},
            {'tag': 'div', 'attrs': {'data-element-name': 'final-price'}},
            {'tag': 'span', 'attrs': {'class': re.compile(r'PropertyCardPrice', re.I)}},
        ]
        
        for selector in price_selectors:
            elem = room_elem.find(selector['tag'], attrs=selector['attrs'])
            if elem:
                price_text = elem.get_text(strip=True)
                price = extract_price_value(price_text)
                currency = extract_currency(price_text)
                if price:
                    break
        
        # If no price found, try to extract from text using multiple patterns
        if not price:
            # Price patterns observed: "R . 3,939" or "₹3,939" or "INR 3939"
            price_patterns = [
                r'R\s*\.?\s*([\d,]+)',  # "R . 3,939" or "R.3939"
                r'₹\s*([\d,]+)',  # "₹3,939"
                r'Rs\.?\s*([\d,]+)',  # "Rs. 3939"
                r'INR\s*([\d,]+)',  # "INR 3939"
            ]
            
            for pattern in price_patterns:
                price_match = re.search(pattern, room_text)
                if price_match:
                    try:
                        price = float(price_match.group(1).replace(',', '').replace('\xa0', ''))
                        # Sanity check - hotel room prices typically 1000-500000 INR
                        # 1000 INR minimum helps filter out flight prices
                        if price >= 1000:
                            break
                        else:
                            price = None  # Reset if too low
                    except ValueError:
                        pass
        
        # Check availability - look for specific sold out elements, not just text
        is_available = True
        
        # Look for specific sold out elements
        sold_out_elem = room_elem.find(attrs={'data-selenium': re.compile(r'sold.*out', re.I)})
        if sold_out_elem:
            is_available = False
        
        # Also check for explicit sold out text near price area
        price_area = room_elem.find(attrs={'data-ppapi': 'room-price'}) or room_elem.find(class_=re.compile(r'price', re.I))
        if price_area:
            price_area_text = price_area.get_text(strip=True).lower()
            if 'sold out' in price_area_text or 'unavailable' in price_area_text:
                is_available = False
        
        # If we have a valid price, the room is generally available
        if price is not None and price > 0:
            is_available = True
        elif price is None:
            is_available = False
        
        # Extract amenities
        amenities = extract_amenities(room_elem)
        
        # Extract cancellation policy
        cancellation_policy = extract_cancellation_policy(room_elem)
        
        # Extract meal plan
        meal_plan = extract_meal_plan(room_elem)
        
        # Extract bed type
        bed_type = extract_bed_type(room_elem)
        
        # Extract max occupancy
        max_occupancy = extract_occupancy(room_elem)
        
        return RoomData(
            hotel_name=hotel_name,
            date=date_str,
            room_type=room_type,
            price=price,
            currency=currency,
            amenities=amenities,
            is_available=is_available,
            cancellation_policy=cancellation_policy,
            meal_plan=meal_plan,
            bed_type=bed_type,
            max_occupancy=max_occupancy,
            hotel_location=hotel.location,
            hotel_rating=hotel.rating,
            hotel_star_rating=hotel.star_rating,
            hotel_review_count=hotel.review_count,
        )
        
    except Exception as e:
        logger.debug(f"Error extracting room data: {e}")
        return None


def extract_price_value(text: str) -> Optional[float]:
    """Extract numeric price value from text."""
    if not text:
        return None
    
    # Remove "R ." or "R." prefix (Agoda's INR format)
    text = re.sub(r'R\s*\.?\s*', '', text)
    # Remove currency symbols and formatting
    text = re.sub(r'[₹$€£,\s\xa0]', '', text)
    
    # Find number - must start with a digit (not a dot)
    match = re.search(r'\d[\d,]*\.?\d*', text)
    if match:
        try:
            price = float(match.group().replace(',', ''))
            # Sanity check - prices should be reasonable for hotels (1000 to 500000 INR)
            # 1000 INR minimum helps filter out flight prices
            if 1000 <= price <= 500000:
                return price
        except ValueError:
            pass
    return None


def extract_currency(text: str) -> str:
    """Extract currency from price text."""
    if '₹' in text or 'INR' in text:
        return "INR"
    elif '$' in text or 'USD' in text:
        return "USD"
    elif '€' in text or 'EUR' in text:
        return "EUR"
    elif '£' in text or 'GBP' in text:
        return "GBP"
    return "INR"  # Default


def extract_amenities(room_elem) -> list[str]:
    """Extract room amenities from room element."""
    amenities = []
    
    # Look for amenity-related elements
    amenity_selectors = [
        {'tag': 'span', 'attrs': {'class': re.compile(r'amenity|feature|benefit', re.I)}},
        {'tag': 'li', 'attrs': {'class': re.compile(r'amenity|feature', re.I)}},
        {'tag': 'div', 'attrs': {'data-element-name': re.compile(r'amenity|benefit', re.I)}},
    ]
    
    for selector in amenity_selectors:
        elems = room_elem.find_all(selector['tag'], attrs=selector['attrs'])
        for elem in elems:
            text = elem.get_text(strip=True)
            if text and len(text) > 1 and len(text) < 100:
                amenities.append(text)
    
    # Look for common amenity keywords in the room text
    room_text = room_elem.get_text(strip=True).lower()
    keyword_amenities = {
        'wifi': 'WiFi',
        'wi-fi': 'WiFi',
        'breakfast': 'Breakfast',
        'parking': 'Parking',
        'pool': 'Pool Access',
        'gym': 'Gym Access',
        'spa': 'Spa Access',
        'air condition': 'Air Conditioning',
        'ac': 'Air Conditioning',
        'minibar': 'Minibar',
        'mini bar': 'Minibar',
        'room service': 'Room Service',
        'tv': 'TV',
        'balcony': 'Balcony',
        'sea view': 'Sea View',
        'city view': 'City View',
        'garden view': 'Garden View',
    }
    
    for keyword, amenity_name in keyword_amenities.items():
        if keyword in room_text and amenity_name not in amenities:
            amenities.append(amenity_name)
    
    return list(set(amenities))  # Remove duplicates


def extract_cancellation_policy(room_elem) -> Optional[str]:
    """Extract cancellation policy from room element."""
    cancellation_selectors = [
        {'tag': 'span', 'attrs': {'data-selenium': re.compile(r'cancellation', re.I)}},
        {'tag': 'div', 'attrs': {'class': re.compile(r'cancellation|refund', re.I)}},
        {'tag': 'span', 'attrs': {'class': re.compile(r'cancellation|refund', re.I)}},
    ]
    
    for selector in cancellation_selectors:
        elem = room_elem.find(selector['tag'], attrs=selector['attrs'])
        if elem:
            return elem.get_text(strip=True)
    
    # Check for keywords
    room_text = room_elem.get_text(strip=True).lower()
    if 'free cancellation' in room_text:
        return 'Free Cancellation'
    elif 'non-refundable' in room_text or 'nonrefundable' in room_text:
        return 'Non-refundable'
    elif 'partial refund' in room_text:
        return 'Partial Refund'
    
    return None


def extract_meal_plan(room_elem) -> Optional[str]:
    """Extract meal plan from room element."""
    meal_selectors = [
        {'tag': 'span', 'attrs': {'data-element-name': re.compile(r'meal|breakfast|board', re.I)}},
        {'tag': 'div', 'attrs': {'class': re.compile(r'meal|breakfast|board', re.I)}},
    ]
    
    for selector in meal_selectors:
        elem = room_elem.find(selector['tag'], attrs=selector['attrs'])
        if elem:
            return elem.get_text(strip=True)
    
    room_text = room_elem.get_text(strip=True).lower()
    if 'breakfast included' in room_text:
        return 'Breakfast Included'
    elif 'half board' in room_text:
        return 'Half Board'
    elif 'full board' in room_text:
        return 'Full Board'
    elif 'all inclusive' in room_text:
        return 'All Inclusive'
    elif 'room only' in room_text:
        return 'Room Only'
    
    return None


def extract_bed_type(room_elem) -> Optional[str]:
    """Extract bed type from room element."""
    bed_selectors = [
        {'tag': 'span', 'attrs': {'data-selenium': re.compile(r'bed', re.I)}},
        {'tag': 'div', 'attrs': {'class': re.compile(r'bed.*type|bed.*info', re.I)}},
    ]
    
    for selector in bed_selectors:
        elem = room_elem.find(selector['tag'], attrs=selector['attrs'])
        if elem:
            return elem.get_text(strip=True)
    
    room_text = room_elem.get_text(strip=True).lower()
    bed_types = ['king bed', 'queen bed', 'double bed', 'twin bed', 'single bed', 'sofa bed']
    for bed in bed_types:
        if bed in room_text:
            return bed.title()
    
    return None


def extract_occupancy(room_elem) -> Optional[int]:
    """Extract maximum occupancy from room element."""
    occ_selectors = [
        {'tag': 'span', 'attrs': {'data-selenium': re.compile(r'occupancy|guest', re.I)}},
        {'tag': 'div', 'attrs': {'class': re.compile(r'occupancy|capacity', re.I)}},
    ]
    
    for selector in occ_selectors:
        elem = room_elem.find(selector['tag'], attrs=selector['attrs'])
        if elem:
            text = elem.get_text(strip=True)
            match = re.search(r'(\d+)', text)
            if match:
                return int(match.group(1))
    
    return None


def deduplicate_rooms(rooms: list[RoomData]) -> list[RoomData]:
    """
    Deduplicate rooms by room type, keeping the one with lowest price.
    
    Args:
        rooms: List of RoomData objects
    
    Returns:
        Deduplicated list of RoomData objects
    """
    room_dict = {}
    
    for room in rooms:
        key = room.room_type
        if key not in room_dict:
            room_dict[key] = room
        else:
            existing = room_dict[key]
            # Keep the one with price if one doesn't have price
            if existing.price is None and room.price is not None:
                room_dict[key] = room
            # Keep the one with lower price if both have prices
            elif room.price is not None and existing.price is not None:
                if room.price < existing.price:
                    room_dict[key] = room
    
    return list(room_dict.values())


async def scrape_hotel_rooms_for_dates(
    page: Page,
    hotel: HotelInfo,
    config: ScraperConfig,
    start_date: Optional[datetime] = None,
    on_rooms_scraped: Optional[Callable[[list[RoomData]], None]] = None,
    session_id: Optional[str] = None,  # Add this line
) -> list[RoomData]:
    """
    Scrape room information for all dates in the configured range.
    
    Args:
        page: Playwright page instance
        hotel: Hotel information
        config: Scraper configuration
        start_date: Start date (defaults to tomorrow)
        on_rooms_scraped: Optional callback function called after each date's rooms are scraped.
                         Signature: on_rooms_scraped(rooms: list[RoomData]) -> None
                         This enables immediate saving to CSV after each batch.
    
    Returns:
        List of RoomData objects for all dates
    """
    if start_date is None:
        start_date = datetime.now() + timedelta(days=1)
    
    all_rooms = []
    
    for day_offset in range(config.days_ahead):
        check_in = start_date + timedelta(days=day_offset)
        
        logger.info(f"Scraping {hotel.name} for {check_in.date()} ({day_offset + 1}/{config.days_ahead})")
        
        rooms = await scrape_hotel_rooms(page, hotel, check_in, config, session_id=session_id)
        all_rooms.extend(rooms)
        
        # Call callback to save rooms immediately after each date
        if on_rooms_scraped and rooms:
            on_rooms_scraped(rooms)
        
        # Add delay between date requests
        if day_offset < config.days_ahead - 1:
            await random_delay(*config.delays.between_dates)
    
    return all_rooms

