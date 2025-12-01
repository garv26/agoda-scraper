"""Hotel listing scraper for Agoda search results."""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode, quote
from playwright.async_api import Page
from bs4 import BeautifulSoup

from .models import HotelInfo, ScraperConfig
from .browser import scroll_to_bottom, random_delay, wait_for_element, safe_click

logger = logging.getLogger(__name__)


# Agoda search URL components
AGODA_BASE_URL = "https://www.agoda.com"
AGODA_SEARCH_PATH = "/search"

# City ID mapping for common locations (discovered from Agoda URLs)
CITY_IDS = {
    "jaipur": 8845,
    "delhi": 8810,
    "mumbai": 3790,
    "bangalore": 3798,
    "goa": 3721,
    "chennai": 3804,
    "kolkata": 3788,
    "hyderabad": 3816,
    "agra": 3834,
    "udaipur": 8843,
    "pune": 3815,
    "ahmedabad": 3820,
    "lucknow": 8813,
    "varanasi": 8848,
    "shimla": 3833,
    "manali": 3831,
    "rishikesh": 3832,
    "mussoorie": 3825,
    "darjeeling": 3806,
    "ooty": 3821,
}


def build_search_url(
    location: str,
    check_in: datetime,
    check_out: datetime,
    guests: int = 2,
    rooms: int = 1,
) -> str:
    """
    Build Agoda search URL with the given parameters.
    
    Args:
        location: City or location name
        check_in: Check-in date
        check_out: Check-out date
        guests: Number of guests
        rooms: Number of rooms
    
    Returns:
        Complete search URL
    """
    # Get city ID if available for more accurate search
    city_id = CITY_IDS.get(location.lower())
    
    params = {
        "checkIn": check_in.strftime("%Y-%m-%d"),
        "checkOut": check_out.strftime("%Y-%m-%d"),
        "rooms": rooms,
        "adults": guests,
        "children": 0,
        "priceCur": "INR",
        "los": 1,  # Length of stay
        "textToSearch": location,
    }
    
    # Add city ID if available for better results
    if city_id:
        params["city"] = city_id
    
    # Build URL
    url = f"{AGODA_BASE_URL}{AGODA_SEARCH_PATH}?{urlencode(params)}"
    return url


async def navigate_to_search(
    page: Page,
    config: ScraperConfig,
    check_in: Optional[datetime] = None,
) -> bool:
    """
    Navigate to Agoda search results page.
    
    Args:
        page: Playwright page instance
        config: Scraper configuration
        check_in: Check-in date (defaults to tomorrow)
    
    Returns:
        True if navigation successful, False otherwise
    """
    if check_in is None:
        check_in = datetime.now() + timedelta(days=1)
    
    check_out = check_in + timedelta(days=1)
    
    url = build_search_url(
        location=config.location,
        check_in=check_in,
        check_out=check_out,
        guests=config.guests,
        rooms=config.rooms,
    )
    
    logger.info(f"Navigating to search URL: {url}")
    
    try:
        await page.goto(url, wait_until="domcontentloaded")
        
        # Wait for the page to load
        await random_delay(1, 2)  # Reduced from (2, 4)
        
        # Handle potential popups or overlays
        await dismiss_popups(page)

        # Wait for network to settle
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        
        # Wait for hotel cards to appear - selectors based on actual Agoda structure
        # From browser inspection: hotels are in "group" with name "Property Card"
        selectors_to_try = [
            '[data-selenium="hotel-name"]',  # Hotel name element inside card
            'a[href*="/hotel/"][href*=".html"]',  # Hotel links with /hotel/ path
            '[data-element-name="property-card"]',
            '.PropertyCard',
            'li[data-hotelid]',
            '[role="listitem"] a[href*="hotel"]', 
            
            '[data-testid="property-card"]',
            '[class*="PropertyCard"]',
            'ol[data-selenium="hotel-list"] li',
            '[data-element-name="property-card-container"]', # From accessibility tree
        ]
        
        for selector in selectors_to_try:
            if await wait_for_element(page, selector, timeout=10000):
                logger.info(f"Found hotel cards with selector: {selector}")
                return True

         # If no specific selector found, try scrolling to trigger lazy load
        logger.warning("No hotel cards found initially, scrolling to trigger lazy load...")
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 500)")
            await random_delay(1, 2)
            
            # Re-check selectors after scroll
            for selector in selectors_to_try:
                if await wait_for_element(page, selector, timeout=3000):
                    logger.info(f"Found hotel cards after scroll with selector: {selector}")
                    return True
        
        # If no specific selector found, check if we have any content
        content = await page.content()
        if "hotel" in content.lower() or "property" in content.lower():
            logger.warning("Hotel cards found but with unknown structure")
            return True
            
        logger.error("Failed to find hotel listings on the page")
        return False
        
    except Exception as e:
        logger.error(f"Navigation failed: {e}")
        return False


async def dismiss_popups(page: Page):
    """Dismiss common popups and overlays on Agoda."""
    popup_selectors = [
        '[data-selenium="close-button"]',
        '.ab-close-button',
        '.close-modal',
        '[aria-label="Close"]',
        'button[class*="close"]',
        '.popup-close',
        '#onetrust-accept-btn-handler',  # Cookie consent
    ]
    
    for selector in popup_selectors:
        try:
            await safe_click(page, selector, timeout=1000)
            await random_delay(0.3, 0.5)
        except Exception:
            pass


async def scrape_hotel_listings(
    page: Page,
    config: ScraperConfig,
    check_in: Optional[datetime] = None,
) -> list[HotelInfo]:
    """
    Scrape hotel listings from Agoda search results.
    
    Args:
        page: Playwright page instance
        config: Scraper configuration
        check_in: Check-in date for the search
    
    Returns:
        List of HotelInfo objects
    """
    # Navigate to search results
    if not await navigate_to_search(page, config, check_in):
        logger.error("Failed to navigate to search results")
        return []
    
    # Scroll to load more hotels
    logger.info(f"Scrolling to load at least {config.num_hotels} hotels...")
    
    # Try different selectors for counting hotels
    # [data-selenium="hotel-name"] is confirmed to work from testing
    count_selectors = [
        '[data-selenium="hotel-name"]',  # This works! Found in browser testing
        '[data-selenium="hotel-item"]',
        '.PropertyCard',
        '[data-element-name="property-card"]',
        'li[data-hotelid]',
        'a[href*="/hotel/"][href*=".html"]',  # Hotel links
    ]
    
    hotel_count = 0
    used_selector = None
    
    for selector in count_selectors:
        elements = await page.query_selector_all(selector)
        if len(elements) > 0:
            used_selector = selector
            hotel_count = len(elements)
            break
    
    if used_selector:
        logger.info(f"Using selector '{used_selector}' for counting hotels")
        # Scroll until we have enough hotels
        hotel_count = await scroll_to_bottom(
            page,
            scroll_pause_range=config.delays.scroll_pause,
            max_scrolls=150,  # Increased for loading more hotels
            target_count=config.num_hotels,
            count_selector=used_selector,
        )
        logger.info(f"Loaded {hotel_count} hotels after scrolling")
    else:
        logger.warning("No working selector found, scrolling without counting")
        # Just scroll for a while
        await scroll_to_bottom(
            page,
            scroll_pause_range=config.delays.scroll_pause,
            max_scrolls=50,  # Increased
        )
    
    # Parse the page content
    html = await page.content()
    hotels = parse_hotel_listings(html, config.num_hotels)
    
    logger.info(f"Extracted {len(hotels)} hotels from search results")
    return hotels


def parse_hotel_listings(html: str, max_hotels: int = 50) -> list[HotelInfo]:
    """
    Parse hotel listings from HTML content.
    
    Args:
        html: HTML content of the search results page
        max_hotels: Maximum number of hotels to extract
    
    Returns:
        List of HotelInfo objects
    """
    soup = BeautifulSoup(html, "lxml")
    hotels = []
    
    # Try multiple selector patterns for hotel cards
    # Based on Agoda's actual structure observed in browser inspection
    # From accessibility tree: listitem containing "Property Card" groups
    card_selectors = [
        {'tag': 'li', 'attrs': {'data-selenium': 'hotel-item'}},
        {'tag': 'div', 'attrs': {'data-element-name': 'property-card'}},
        {'tag': 'li', 'attrs': {'data-hotelid': True}},
        {'tag': 'li', 'attrs': {'class': re.compile(r'PropertyCard', re.I)}},
        {'tag': 'div', 'attrs': {'class': re.compile(r'PropertyCard', re.I)}},
        {'tag': 'div', 'attrs': {'data-cy': re.compile(r'property-card', re.I)}},
        # Pattern: listitem with "Property Card" in role=group
        {'tag': 'li', 'attrs': {'role': 'listitem'}},

         # Additional selectors
        {'tag': 'div', 'attrs': {'data-testid': re.compile(r'property', re.I)}},
        {'tag': 'div', 'attrs': {'class': re.compile(r'property-card', re.I)}},
    ]
    
    hotel_cards = []
    for selector in card_selectors:
        hotel_cards = soup.find_all(selector['tag'], attrs=selector['attrs'])
        if hotel_cards:
            logger.debug(f"Found {len(hotel_cards)} hotels using selector: {selector}")
            break
    
    if not hotel_cards:
        # Fallback: find all list items that contain hotel links
        # Agoda uses anchor tags with hotel URLs
        all_links = soup.find_all('a', href=re.compile(r'/hotel/|/hotels/', re.I))
        seen_hotels = set()
        for link in all_links:
            href = link.get('href', '')
            if href and 'hotel' in href.lower() and href not in seen_hotels:
                # Get parent container
                normalized = re.sub(r'\?.*$', '', href)  # Remove query params
                if normalized not in seen_hotels:
                    parent = link.find_parent(['li', 'div', 'article'])
                    if parent and parent not in hotel_cards:
                        hotel_cards.append(parent)
                        seen_hotels.add(normalized)
    
    if not hotel_cards:
        # Last resort: try to find any list items with hotel-like content
        hotel_cards = soup.find_all('li', class_=re.compile(r'hotel|property', re.I))
    
    for card in hotel_cards[:max_hotels]:
        hotel = extract_hotel_from_card(card)
        if hotel:
            hotels.append(hotel)
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_hotels = []
    for hotel in hotels:
        if hotel.url not in seen_urls:
            seen_urls.add(hotel.url)
            unique_hotels.append(hotel)
    
    return unique_hotels[:max_hotels]


def extract_hotel_from_card(card) -> Optional[HotelInfo]:
    """
    Extract hotel information from a single hotel card element.
    
    Args:
        card: BeautifulSoup element representing a hotel card
    
    Returns:
        HotelInfo object or None if extraction fails
    """
    try:
        # Extract hotel URL first (most reliable)
        url = None
        link = card.find('a', href=re.compile(r'/hotel.*\.html|/hotels/', re.I))
        if link:
            href = link.get('href', '')
            if href.startswith('/'):
                url = AGODA_BASE_URL + href
            elif href.startswith('http'):
                url = href
        
        if not url:
            # Try any link with hotel in href
            for a_tag in card.find_all('a', href=True):
                href = a_tag['href']
                if 'hotel' in href.lower():
                    if href.startswith('/'):
                        url = AGODA_BASE_URL + href
                    elif href.startswith('http'):
                        url = href
                    break
        
        if not url:
            return None
        
        # Extract hotel name from link text or nearby elements
        name = None
        
        # Try to get name from the link that has the hotel URL
        if link:
            # The link text or aria-label might have the name
            name = link.get('aria-label') or link.get('title')
            if not name:
                # Look for text in nested elements
                name_elem = link.find(['h3', 'h2', 'h4', 'span', 'div'], 
                                      attrs={'data-selenium': re.compile(r'hotel-name|property-name', re.I)})
                if name_elem:
                    name = name_elem.get_text(strip=True)
        
        if not name:
            # Try various name selectors
            name_selectors = [
                {'tag': 'h3', 'attrs': {'data-selenium': 'hotel-name'}},
                {'tag': 'span', 'attrs': {'data-selenium': 'hotel-name'}},
                {'tag': 'h3', 'attrs': {'class': re.compile(r'PropertyCard.*name|hotel.*name', re.I)}},
                {'tag': 'div', 'attrs': {'class': re.compile(r'property.*name|hotel.*name', re.I)}},
            ]
            
            for selector in name_selectors:
                elem = card.find(selector['tag'], attrs=selector['attrs'])
                if elem:
                    name = elem.get_text(strip=True)
                    break
        
        if not name:
            # Try any h3 or prominent text
            for tag in ['h3', 'h2', 'h4']:
                elem = card.find(tag)
                if elem:
                    name = elem.get_text(strip=True)
                    if name and len(name) > 3:
                        break
        
        if not name:
            # Extract from URL as last resort
            # URL format: /hotel-name/hotel/city-in.html
            url_match = re.search(r'/([^/]+)/hotel/', url)
            if url_match:
                name = url_match.group(1).replace('-', ' ').title()
        
        if not name:
            return None
        
        # Clean up name
        name = re.sub(r'\s+', ' ', name).strip()
        if len(name) < 3:
            return None
        
        # Extract rating from text containing pattern like "8.9" or "Excellent 8.9"
        # From browser inspection: "Average rating Very good 7.3 out of 10 with 473 review"
        rating = None
        card_text = card.get_text(' ', strip=True)  # Use space separator for better parsing
        
        # Look for rating patterns - ordered by specificity
        rating_patterns = [
            r'(\d+\.?\d*)\s*out of\s*10',  # "7.3 out of 10"
            r'Average rating.*?(\d+\.?\d*)',  # "Average rating ... 7.3"
            r'(\d+\.?\d*)\s*(?:Exceptional|Excellent|Very good|Good|Superb|Fabulous)',  # "7.3 Very good"
            r'(?:Exceptional|Excellent|Very good|Good|Superb|Fabulous)\s*(\d+\.?\d*)',  # "Very good 7.3"
            r'/\s*10\s*(\d+\.?\d*)',  # "/10 7.3"
        ]
        
        for pattern in rating_patterns:
            rating_match = re.search(pattern, card_text, re.I)
            if rating_match:
                try:
                    rating = float(rating_match.group(1))
                    if rating > 10:  # Likely not a rating
                        rating = None
                    else:
                        break  # Found valid rating
                except ValueError:
                    pass
        
        if not rating:
            rating_selectors = [
                {'tag': 'div', 'attrs': {'data-element-name': 'review-score'}},
                {'tag': 'span', 'attrs': {'class': re.compile(r'review.*score|rating', re.I)}},
            ]
            for selector in rating_selectors:
                elem = card.find(selector['tag'], attrs=selector['attrs'])
                if elem:
                    rating_text = elem.get_text(strip=True)
                    rating = extract_number(rating_text)
                    if rating and rating <= 10:
                        break
                    rating = None
        
        # Extract review count - patterns like "473 review" or "2,385 reviews"
        # From browser inspection: "with 473 review" or just "473 reviews"
        review_count = None
        review_patterns = [
            r'with\s*([\d,]+)\s*review',  # "with 473 review"
            r'([\d,]+)\s*review',  # "473 reviews"
            r'([\d,]+)\s*rating',  # "473 ratings"
        ]
        
        for pattern in review_patterns:
            review_match = re.search(pattern, card_text, re.I)
            if review_match:
                try:
                    review_count = int(review_match.group(1).replace(',', ''))
                    break
                except ValueError:
                    pass
        
        # Extract price - look for patterns like "R . 3,586" or "₹ 3,586"
        # From browser inspection: "R . 3,939" (with non-breaking space \xa0)
        base_price = None
        currency = "INR"
        
        # Look for price patterns in text - multiple formats observed
        price_patterns = [
            r'R\s*\.?\s*([\d,]+)',  # "R . 3,939" or "R. 3,939"
            r'₹\s*([\d,]+)',  # "₹3,939"
            r'Rs\.?\s*([\d,]+)',  # "Rs. 3939" or "Rs 3939"
            r'INR\s*([\d,]+)',  # "INR 3939"
            # Final price pattern (not original/strikethrough)
            r'(?<!Original price[:\s])(?<![\d,])([\d,]{4,})\s*$',  # Standalone 4+ digit number at end
        ]
        
        for pattern in price_patterns:
            price_match = re.search(pattern, card_text)
            if price_match:
                price_str = price_match.group(1).replace(',', '').replace('\xa0', '')
                try:
                    base_price = float(price_str)
                    # Sanity check - price should be reasonable
                    if base_price > 100 and base_price < 1000000:
                        break
                    else:
                        base_price = None
                except ValueError:
                    pass
        
        if not base_price:
            price_selectors = [
                {'tag': 'span', 'attrs': {'data-selenium': 'display-price'}},
                {'tag': 'div', 'attrs': {'data-element-name': 'final-price'}},
                {'tag': 'span', 'attrs': {'class': re.compile(r'price', re.I)}},
            ]
            for selector in price_selectors:
                elem = card.find(selector['tag'], attrs=selector['attrs'])
                if elem:
                    price_text = elem.get_text(strip=True)
                    base_price = extract_price(price_text)
                    if base_price:
                        break
        
        # Extract star rating - patterns like "3 stars out of 5" or "3-star"
        star_rating = None
        star_patterns = [
            r'(\d)\s*stars?\s*out of\s*5',  # "3 stars out of 5"
            r'(\d)\s*-?\s*star',  # "3-star" or "3 star"
            r'(\d)\s*★',  # "3★"
        ]
        for pattern in star_patterns:
            star_match = re.search(pattern, card_text, re.I)
            if star_match:
                try:
                    star_rating = int(star_match.group(1))
                    if 1 <= star_rating <= 5:
                        break
                    star_rating = None
                except ValueError:
                    pass
        
        # Extract location - patterns like "Gopalbari, Jaipur - City center 627 m from Rail"
        # Location is usually in a div with class containing "mt-4" or near star rating
        location = None
        
        # Try to find location selectors first
        location_selectors = [
            {'tag': 'div', 'attrs': {'class': re.compile(r'a3315-mt-4|location|address', re.I)}},
            {'tag': 'span', 'attrs': {'data-element-name': re.compile(r'location|address', re.I)}},
            {'tag': 'div', 'attrs': {'data-selenium': re.compile(r'area-city|location', re.I)}},
        ]
        
        for selector in location_selectors:
            elem = card.find(selector['tag'], attrs=selector['attrs'])
            if elem:
                location_text = elem.get_text(' ', strip=True)
                # Extract location part (before "tooltip" or after star rating text)
                # Pattern: "3 stars out of 5 tooltip ... Area, City - distance"
                loc_match = re.search(r'(?:tooltip[^A-Z]*)?([A-Z][a-zA-Z\s]+,\s*[A-Za-z\s]+)(?:\s*-\s*|\s+)(?:City center|[0-9]+\s*(?:m|km))', location_text, re.I)
                if loc_match:
                    location = loc_match.group(1).strip()
                    break
        
        # Fallback: look for location patterns in card text
        if not location:
            # Pattern: "Area, City" followed by distance info
            loc_patterns = [
                r'([A-Z][a-zA-Z\s]+,\s*[A-Za-z\s]+)(?:\s*-\s*City center|\s+\d+\s*(?:m|km)\s+from)',
                r'([A-Z][a-zA-Z\s]+,\s*Jaipur)',  # Specific for Jaipur
                r'([A-Z][a-zA-Z\s]+,\s*[A-Za-z]+)\s*-\s*\d+',  # "Area, City - 123"
            ]
            for pattern in loc_patterns:
                loc_match = re.search(pattern, card_text)
                if loc_match:
                    location = loc_match.group(1).strip()
                    # Clean up - remove trailing punctuation and extra spaces
                    location = re.sub(r'[,\s]+$', '', location)
                    if len(location) > 3 and len(location) < 100:
                        break
                    location = None
        
        return HotelInfo(
            name=name,
            url=url,
            rating=rating,
            review_count=review_count,
            base_price=base_price,
            currency=currency,
            star_rating=star_rating,
            location=location,
        )
        
    except Exception as e:
        logger.debug(f"Error extracting hotel from card: {e}")
        return None


def extract_number(text: str) -> Optional[float]:
    """Extract a number from text."""
    if not text:
        return None
    
    # Remove common formatting
    text = text.replace(',', '').replace(' ', '')
    
    # Find number pattern
    match = re.search(r'[\d.]+', text)
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return None


def extract_price(text: str) -> Optional[float]:
    """Extract price value from text."""
    if not text:
        return None
    
    # Remove currency symbols and formatting
    text = re.sub(r'[₹$€£,\s]', '', text)
    
    # Find number
    match = re.search(r'[\d.]+', text)
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return None


def build_hotel_url_with_dates(
    base_url: str,
    check_in: datetime,
    check_out: datetime,
    guests: int = 2,
    rooms: int = 1,
) -> str:
    """
    Modify a hotel URL to include specific dates.
    
    Args:
        base_url: Original hotel URL
        check_in: Check-in date
        check_out: Check-out date
        guests: Number of guests
        rooms: Number of rooms
    
    Returns:
        URL with date parameters
    """
    # Parse existing URL and add/replace date parameters
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    
    parsed = urlparse(base_url)
    params = parse_qs(parsed.query)
    
    # Update date parameters
    params['checkIn'] = [check_in.strftime('%Y-%m-%d')]
    params['checkOut'] = [check_out.strftime('%Y-%m-%d')]
    params['adults'] = [str(guests)]
    params['rooms'] = [str(rooms)]
    params['children'] = ['0']
    
    # Flatten the params dict
    flat_params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
    
    # Rebuild URL
    new_query = urlencode(flat_params)
    new_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment,
    ))
    
    return new_url

