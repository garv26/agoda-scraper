
"""
Multi-browser parallel scraper with rotating proxy support.

This module provides:
- Multiple browser instances running in parallel
- Each browser has a unique fingerprint (user agent, viewport, timezone)
- Optional rotating proxy support (SOCKS5/HTTP)
- Thread-safe CSV writing
- Queue-based hotel distribution for load balancing

Key Benefits:
1. SPEED: N browsers = ~N times faster (limited by network/memory)
2. STEALTH: Different fingerprints reduce bot detection
3. RESILIENCE: One browser crash doesn't affect others
4. SCALABILITY: Easy to add more browsers or proxies
"""

import asyncio
import csv
import logging
import random
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Callable
from dataclasses import dataclass, field

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from .models import ScraperConfig, HotelInfo, RoomData
from .room_details import scrape_hotel_rooms
from .browser import random_delay

logger = logging.getLogger(__name__)


# ============================================
# USER AGENT POOL - Each browser gets unique UA
# ============================================
USER_AGENTS = [
    # Chrome on Windows (various versions)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
]

# Viewport sizes for diversity
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1680, "height": 1050},
    {"width": 2560, "height": 1440},
    {"width": 1280, "height": 720},
    {"width": 1600, "height": 900},
]

# Timezone/locale combinations
LOCALES = [
    ("en-US", "America/New_York"),
    ("en-US", "America/Los_Angeles"),
    ("en-GB", "Europe/London"),
    ("en-IN", "Asia/Kolkata"),
    ("en-AU", "Australia/Sydney"),
]


# ============================================
# PROXY CONFIGURATION
# ============================================
# Add your proxies here. Leave empty to run without proxies.
#
# SOCKS5 format: "socks5://ip:port" or "socks5://user:pass@ip:port"
# HTTP format: "http://ip:port" or "http://user:pass@ip:port"
#
# Examples:
#   SSH tunnel proxies: "socks5://127.0.0.1:1081"
#   VPS proxies: "socks5://your-vps-ip:1080"
#   Paid proxies: "http://user:pass@proxy.example.com:8080"

PROXY_LIST: List[str] = [
    # Add your proxies here:
    # "socks5://127.0.0.1:1081",
    # "socks5://127.0.0.1:1082",
    # "socks5://your-vps-ip:1080",
]


@dataclass
class BrowserWorker:
    """
    Represents a browser worker with its unique configuration.
    
    Each worker has:
    - Unique user agent
    - Unique viewport size
    - Unique locale/timezone
    - Optional dedicated proxy
    """
    worker_id: int
    user_agent: str
    viewport: dict
    locale: str
    timezone: str
    proxy: Optional[dict] = None
    hotels_processed: int = 0
    rooms_scraped: int = 0
    errors: int = 0
    is_busy: bool = False


class ThreadSafeCSVWriter:
    """
    Thread-safe CSV writer for concurrent writes from multiple browsers.
    
    Uses a threading lock to ensure only one browser writes at a time,
    preventing data corruption.
    """
    
    def __init__(self, filepath: str, headers: List[str]):
        self.filepath = Path(filepath)
        self.headers = headers
        self.lock = threading.Lock()
        self._init_csv()
        self.rows_written = 0
    
    def _init_csv(self):
        """Initialize CSV with headers."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()
    
    def append_rows(self, rows: List[dict]):
        """Append rows to CSV in a thread-safe manner."""
        if not rows:
            return
        with self.lock:
            with open(self.filepath, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writerows(rows)
            self.rows_written += len(rows)


async def create_browser_with_fingerprint(
    playwright,
    worker: BrowserWorker,
    headless: bool = True,
) -> tuple[Browser, Page]:
    """
    Launch a NEW browser instance with unique fingerprint.
    
    Each browser is a completely separate process with:
    - Unique user agent
    - Unique viewport
    - Unique timezone/locale
    - Unique geolocation (randomized around Jaipur)
    - Optional dedicated proxy
    
    This makes each browser appear as a different user to Agoda.
    """
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-infobars",
        "--window-position=0,0",
        "--ignore-certificate-errors",
        f"--window-size={worker.viewport['width']},{worker.viewport['height']}",
    ]
    
    # Launch with or without proxy
    launch_kwargs = {
        "headless": headless,
        "args": launch_args,
    }
    
    if worker.proxy:
        launch_kwargs["proxy"] = worker.proxy
        logger.info(f"[Browser {worker.worker_id}] Using proxy: {worker.proxy['server']}")
    
    browser = await playwright.chromium.launch(**launch_kwargs)
    
    # Randomize geolocation slightly around Jaipur to appear as different users
    geo_lat = 26.9124 + random.uniform(-0.5, 0.5)
    geo_lon = 75.7873 + random.uniform(-0.5, 0.5)
    
    # Create context with unique fingerprint
    context = await browser.new_context(
        user_agent=worker.user_agent,
        viewport=worker.viewport,
        locale=worker.locale,
        timezone_id=worker.timezone,
        geolocation={"latitude": geo_lat, "longitude": geo_lon},
        permissions=["geolocation"],
    )
    
    # Anti-detection script - makes browser appear more human
    await context.add_init_script("""
        // Hide webdriver property
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        
        // Fake plugins array
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' },
                ];
                plugins.length = 3;
                return plugins;
            }
        });
        
        // Fake languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en', 'hi']
        });
        
        // Fake chrome object
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        // Fake permissions API
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)
    
    page = await context.new_page()
    
    # Longer timeouts for proxied connections
    timeout = 45000 if worker.proxy else 30000
    nav_timeout = 90000 if worker.proxy else 60000
    page.set_default_timeout(timeout)
    page.set_default_navigation_timeout(nav_timeout)
    
    logger.info(f"[Browser {worker.worker_id}] Launched - UA: {worker.user_agent[:50]}... | Viewport: {worker.viewport['width']}x{worker.viewport['height']}")
    
    return browser, page


async def test_proxy(playwright, proxy_url: str) -> bool:
    """
    Test if a proxy is working by trying to load a simple page.
    
    Returns True if proxy works, False otherwise.
    """
    try:
        browser = await playwright.chromium.launch(
            headless=True,
            proxy={"server": proxy_url},
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        # Try to load httpbin which returns our IP
        await page.goto("https://httpbin.org/ip", timeout=30000)
        content = await page.content()
        
        await browser.close()
        
        if "origin" in content:
            logger.info(f"✓ Proxy working: {proxy_url}")
            return True
        return False
        
    except Exception as e:
        logger.warning(f"✗ Proxy failed: {proxy_url} - {e}")
        return False


async def validate_proxies(playwright) -> List[str]:
    """
    Test all configured proxies and return only working ones.
    """
    if not PROXY_LIST:
        logger.info("No proxies configured - running with direct connection")
        return []
    
    logger.info(f"Testing {len(PROXY_LIST)} proxies...")
    
    working = []
    for proxy_url in PROXY_LIST:
        if await test_proxy(playwright, proxy_url):
            working.append(proxy_url)
    
    logger.info(f"Working proxies: {len(working)}/{len(PROXY_LIST)}")
    return working


async def scrape_with_retry(
    page: Page,
    hotel: HotelInfo,
    check_in: datetime,
    config: ScraperConfig,
    session_id: str,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> List[RoomData]:
    """
    Scrape hotel rooms with retry logic for network errors.
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            rooms = await scrape_hotel_rooms(
                page, hotel, check_in, config, session_id=session_id
            )
            return rooms
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            
            # Check if it's a retryable error
            retryable = any(x in error_str for x in [
                'err_internet_disconnected',
                'err_connection_reset',
                'err_connection_refused',
                'err_network_changed',
                'timeout',
                'net::err',
            ])
            
            if retryable and attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)  # Exponential backoff
                logger.warning(f"Retry {attempt + 1}/{max_retries} for {hotel.name} after {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            else:
                break
    
    # All retries failed, return error placeholder
    logger.error(f"All retries failed for {hotel.name} on {check_in.date()}: {last_error}")
    return [RoomData(
        hotel_name=hotel.name,
        date=check_in.strftime("%Y-%m-%d"),
        room_type="Error",
        price=None,
        currency=hotel.currency or "INR",
        amenities=[],
        is_available=False,
        hotel_location=hotel.location,
        hotel_rating=hotel.rating,
        hotel_star_rating=hotel.star_rating,
        hotel_review_count=hotel.review_count,
    )]


async def browser_worker_task(
    playwright,
    worker: BrowserWorker,
    hotel_queue: asyncio.Queue,
    config: ScraperConfig,
    start_date: datetime,
    csv_writer: ThreadSafeCSVWriter,
    session_id: str,
    headless: bool,
    results: List[RoomData],
    results_lock: asyncio.Lock,
    delay_between_dates: tuple = (0.5, 1.5),
    delay_between_hotels: tuple = (2.0, 5.0),
    max_retries: int = 3,
):
    """
    Long-running worker task that processes hotels from a shared queue.
    
    Each worker:
    1. Launches its own browser with unique fingerprint
    2. Pulls hotels from the queue
    3. Scrapes all dates for each hotel (with retry on network errors)
    4. Writes results to CSV immediately
    5. Continues until queue is empty
    """
    browser = None
    page = None
    
    try:
        # Launch dedicated browser for this worker
        browser, page = await create_browser_with_fingerprint(playwright, worker, headless)
        
        while True:
            try:
                # Get next hotel from queue (with timeout)
                hotel, hotel_idx, total_hotels = await asyncio.wait_for(
                    hotel_queue.get(), 
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                # Check if we should exit
                if hotel_queue.empty():
                    break
                continue
            
            worker.is_busy = True
            proxy_info = f" [proxy: {worker.proxy['server'][:30]}...]" if worker.proxy else ""
            
            try:
                logger.info(f"[Browser {worker.worker_id}] [{hotel_idx+1}/{total_hotels}] {hotel.name}{proxy_info}")
                
                hotel_rooms = []
                consecutive_errors = 0
                
                # Scrape each date for this hotel
                for day_offset in range(config.days_ahead):
                    check_in = start_date + timedelta(days=day_offset)
                    
                    try:
                        # Use retry wrapper
                        rooms = await scrape_with_retry(
                            page, hotel, check_in, config, session_id, max_retries
                        )
                        hotel_rooms.extend(rooms)
                        
                        # Check if we got real data or error placeholder
                        if rooms and rooms[0].room_type != "Error":
                            consecutive_errors = 0
                        else:
                            consecutive_errors += 1
                        
                        # Write to CSV immediately (thread-safe)
                        if rooms:
                            csv_writer.append_rows([r.to_csv_row() for r in rooms])
                        
                        # If too many consecutive errors, browser might be broken
                        if consecutive_errors >= 5:
                            logger.warning(f"[Browser {worker.worker_id}] Too many errors, restarting browser...")
                            # Close and restart browser
                            if page:
                                await page.close()
                            if browser:
                                await browser.close()
                            browser, page = await create_browser_with_fingerprint(playwright, worker, headless)
                            consecutive_errors = 0
                            await asyncio.sleep(3)  # Wait after restart
                        
                        # Delay between dates
                        if day_offset < config.days_ahead - 1:
                            await random_delay(*delay_between_dates)
                            
                    except Exception as e:
                        logger.warning(f"[Browser {worker.worker_id}] Error on {hotel.name} date {check_in.date()}: {e}")
                        worker.errors += 1
                        consecutive_errors += 1
                
                # Update stats
                worker.hotels_processed += 1
                worker.rooms_scraped += len(hotel_rooms)
                
                # Store in results
                async with results_lock:
                    results.extend(hotel_rooms)
                
                logger.info(f"[Browser {worker.worker_id}] ✓ {hotel.name}: {len(hotel_rooms)} rooms")
                
                # Delay between hotels (staggered by worker ID to desync)
                base_delay = delay_between_hotels[0] + (worker.worker_id * 0.3)
                max_delay = delay_between_hotels[1] + (worker.worker_id * 0.5)
                await random_delay(base_delay, max_delay)
                
            except Exception as e:
                logger.error(f"[Browser {worker.worker_id}] ✗ Failed {hotel.name}: {e}")
                worker.errors += 1
                
            finally:
                worker.is_busy = False
                hotel_queue.task_done()
                
    except Exception as e:
        logger.error(f"[Browser {worker.worker_id}] Worker crashed: {e}")
        
    finally:
        # Cleanup browser resources
        if page:
            try:
                await page.close()
            except:
                pass
        if browser:
            try:
                await browser.close()
            except:
                pass
        
        logger.info(
            f"[Browser {worker.worker_id}] Shutdown - "
            f"Hotels: {worker.hotels_processed}, Rooms: {worker.rooms_scraped}, Errors: {worker.errors}"
        )


async def multi_browser_scrape(
    hotels: List[HotelInfo],
    config: ScraperConfig,
    num_browsers: int = 5,
    headless: bool = True,
    output_file: Optional[str] = None,
    validate_proxies_first: bool = True,
    delay_between_dates: tuple = (0.5, 1.5),
    delay_between_hotels: tuple = (2.0, 5.0),
) -> List[RoomData]:
    """
    Main function to scrape hotels using multiple browser instances.
    
    Args:
        hotels: List of hotels to scrape
        config: Scraper configuration
        num_browsers: Number of parallel browser instances
        headless: Run browsers in headless mode
        output_file: Output CSV file path
        validate_proxies_first: Test proxies before starting
        delay_between_dates: (min, max) seconds between date scrapes
        delay_between_hotels: (min, max) seconds between hotel scrapes
    
    Returns:
        List of all scraped room data
    """
    start_time = datetime.now()
    start_date = datetime.now() + timedelta(days=1)
    session_id = start_time.strftime("%Y%m%d_%H%M%S")
    
    # Setup output file
    if output_file is None:
        output_file = f"output/csv/multi_browser_{session_id}.csv"
    
    # CSV headers
    csv_headers = [
        "hotel_name", "hotel_location", "hotel_rating", "hotel_star_rating",
        "hotel_review_count", "date", "room_type", "price", "currency",
        "amenities", "availability", "cancellation_policy", "meal_plan",
    ]
    csv_writer = ThreadSafeCSVWriter(output_file, csv_headers)
    
    # Results storage
    results: List[RoomData] = []
    results_lock = asyncio.Lock()
    
    logger.info(f"\n{'='*70}")
    logger.info(f"  MULTI-BROWSER PARALLEL SCRAPER WITH PROXY ROTATION")
    logger.info(f"{'='*70}")
    logger.info(f"  Hotels to scrape:    {len(hotels)}")
    logger.info(f"  Days per hotel:      {config.days_ahead}")
    logger.info(f"  Browser instances:   {num_browsers}")
    logger.info(f"  Total page requests: {len(hotels) * config.days_ahead}")
    logger.info(f"  Proxies configured:  {len(PROXY_LIST)}")
    logger.info(f"  Output file:         {output_file}")
    logger.info(f"{'='*70}\n")
    
    async with async_playwright() as playwright:
        # Validate proxies if configured
        working_proxies = []
        if validate_proxies_first and PROXY_LIST:
            working_proxies = await validate_proxies(playwright)
        elif PROXY_LIST:
            working_proxies = PROXY_LIST.copy()
        
        # Create workers with unique fingerprints
        random.shuffle(USER_AGENTS)
        workers = []
        
        for i in range(num_browsers):
            locale, timezone = LOCALES[i % len(LOCALES)]
            
            # Assign proxy if available
            proxy = None
            if working_proxies:
                proxy_url = working_proxies[i % len(working_proxies)]
                proxy = {"server": proxy_url}
            
            worker = BrowserWorker(
                worker_id=i,
                user_agent=USER_AGENTS[i % len(USER_AGENTS)],
                viewport=VIEWPORTS[i % len(VIEWPORTS)],
                locale=locale,
                timezone=timezone,
                proxy=proxy,
            )
            workers.append(worker)
        
        # Create hotel queue
        hotel_queue: asyncio.Queue = asyncio.Queue()
        for idx, hotel in enumerate(hotels):
            await hotel_queue.put((hotel, idx, len(hotels)))
        
        # Start all browser workers
        worker_tasks = [
            asyncio.create_task(
                browser_worker_task(
                    playwright=playwright,
                    worker=worker,
                    hotel_queue=hotel_queue,
                    config=config,
                    start_date=start_date,
                    csv_writer=csv_writer,
                    session_id=session_id,
                    headless=headless,
                    results=results,
                    results_lock=results_lock,
                    delay_between_dates=delay_between_dates,
                    delay_between_hotels=delay_between_hotels,
                )
            )
            for worker in workers
        ]
        
        # Progress monitoring task
        async def monitor_progress():
            while not hotel_queue.empty() or any(w.is_busy for w in workers):
                completed = sum(w.hotels_processed for w in workers)
                rooms = sum(w.rooms_scraped for w in workers)
                errors = sum(w.errors for w in workers)
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = completed / elapsed * 3600 if elapsed > 0 else 0
                remaining = len(hotels) - completed
                eta_hours = remaining / rate if rate > 0 else 0
                
                logger.info(
                    f"[Progress] Hotels: {completed}/{len(hotels)} | "
                    f"Rooms: {rooms} | Errors: {errors} | "
                    f"Rate: {rate:.0f}/hr | ETA: {eta_hours:.1f}h"
                )
                await asyncio.sleep(60)  # Log every minute
        
        monitor_task = asyncio.create_task(monitor_progress())
        
        # Wait for all hotels to be processed
        await hotel_queue.join()
        
        # Cancel monitor and wait for workers
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        await asyncio.gather(*worker_tasks, return_exceptions=True)
    
    # Final summary
    duration = datetime.now() - start_time
    total_hotels = sum(w.hotels_processed for w in workers)
    total_rooms = sum(w.rooms_scraped for w in workers)
    total_errors = sum(w.errors for w in workers)
    rate = total_hotels / duration.total_seconds() * 3600 if duration.total_seconds() > 0 else 0
    
    logger.info(f"\n{'='*70}")
    logger.info(f"  SCRAPING COMPLETE")
    logger.info(f"{'='*70}")
    logger.info(f"  Duration:          {duration}")
    logger.info(f"  Hotels processed:  {total_hotels}")
    logger.info(f"  Total rooms:       {total_rooms}")
    logger.info(f"  Total errors:      {total_errors}")
    logger.info(f"  Rate:              {rate:.0f} hotels/hour")
    logger.info(f"  Output file:       {output_file}")
    logger.info(f"{'='*70}")
    
    # Per-browser stats
    logger.info(f"\n  Per-browser statistics:")
    for w in workers:
        proxy_str = f" (proxy)" if w.proxy else ""
        logger.info(f"    Browser {w.worker_id}{proxy_str}: {w.hotels_processed} hotels, {w.rooms_scraped} rooms, {w.errors} errors")
    
    logger.info(f"{'='*70}\n")
    
    return results


def load_hotels_from_csv(filepath: str) -> List[HotelInfo]:
    """
    Load hotel list from a CSV file.
    
    Expected columns: name, url, rating, review_count, star_rating, location
    """
    hotels = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                hotels.append(HotelInfo(
                    name=row.get("name", "Unknown"),
                    url=row.get("url", ""),
                    rating=float(row["rating"]) if row.get("rating") and row["rating"].strip() else None,
                    review_count=int(float(row["review_count"])) if row.get("review_count") and row["review_count"].strip() else None,
                    star_rating=int(float(row["star_rating"])) if row.get("star_rating") and row["star_rating"].strip() else None,
                    location=row.get("location"),
                ))
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid row: {e}")
                continue
    
    logger.info(f"Loaded {len(hotels)} hotels from {filepath}")
    return hotels


def set_proxies(proxy_list: List[str]):
    """
    Set the proxy list programmatically.
    
    Args:
        proxy_list: List of proxy URLs
                   Format: "socks5://ip:port" or "http://user:pass@ip:port"
    
    Example:
        set_proxies([
            "socks5://127.0.0.1:1081",
            "socks5://127.0.0.1:1082",
        ])
    """
    global PROXY_LIST
    PROXY_LIST = proxy_list.copy()
    logger.info(f"Set {len(PROXY_LIST)} proxies")

