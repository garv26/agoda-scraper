"""Browser automation utilities using Playwright."""

import asyncio
import logging
import random
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)


# Realistic user agents for Chrome on different platforms
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

# Common viewport sizes
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
]


class BrowserManager:
    """Manages Playwright browser instance with anti-detection features."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._user_agent = random.choice(USER_AGENTS)
        self._viewport = random.choice(VIEWPORTS)

    async def start(self) -> Page:
        """Initialize browser and return page instance."""
        self.playwright = await async_playwright().start()
        
        # Launch browser with anti-detection args
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certificate-errors",
                "--ignore-certificate-errors-spki-list",
            ]
        )

        # Create context with realistic fingerprint
        self.context = await self.browser.new_context(
            user_agent=self._user_agent,
            viewport=self._viewport,
            locale="en-US",
            timezone_id="Asia/Kolkata",
            geolocation={"latitude": 26.9124, "longitude": 75.7873},  # Jaipur coordinates
            permissions=["geolocation"],
        )

        # Add script to mask automation detection
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            window.chrome = {
                runtime: {}
            };
        """)

        self.page = await self.context.new_page()
        
        # Set default timeouts
        self.page.set_default_timeout(30000)
        self.page.set_default_navigation_timeout(60000)

        return self.page

    async def close(self):
        """Clean up browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def __aenter__(self) -> Page:
        return await self.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def random_delay(min_seconds: float, max_seconds: float):
    """Add a random delay to simulate human behavior."""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def scroll_to_bottom(
    page: Page,
    scroll_pause_range: tuple[float, float] = (0.5, 1.5),
    max_scrolls: int = 50,
    target_count: Optional[int] = None,
    count_selector: Optional[str] = None,
) -> int:
    """
    Scroll to the bottom of the page to load dynamic content.
    
    Args:
        page: Playwright page instance
        scroll_pause_range: Range for random pause between scrolls
        max_scrolls: Maximum number of scroll iterations
        target_count: Stop when this many elements are found (optional)
        count_selector: CSS selector to count elements (used with target_count)
    
    Returns:
        Number of elements found (if count_selector provided) or scroll count
    """
    last_height = 0
    scroll_count = 0
    no_change_count = 0
    
    while scroll_count < max_scrolls:
        # Get current scroll height
        current_height = await page.evaluate("document.body.scrollHeight")
        
        # Check if we've reached target count
        if target_count and count_selector:
            elements = await page.query_selector_all(count_selector)
            current_count = len(elements)
            if current_count >= target_count:
                logger.debug(f"Reached target count: {current_count} >= {target_count}")
                return current_count
            # Log progress every 10 scrolls
            if scroll_count % 10 == 0:
                logger.debug(f"Scroll {scroll_count}: Found {current_count} elements, need {target_count}")
        
        # Scroll down with larger distance to load more content faster
        scroll_distance = random.randint(600, 1200)
        await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
        
        # Wait for content to load
        await random_delay(*scroll_pause_range)
        
        # Check if we've stopped scrolling (reached bottom)
        new_height = await page.evaluate("document.body.scrollHeight")
        
        if new_height == last_height:
            no_change_count += 1
            if no_change_count >= 3:  # Quick exit if page stops loading
                # Try scrolling to absolute bottom once more
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await random_delay(*scroll_pause_range)
                final_height = await page.evaluate("document.body.scrollHeight")
                if final_height == new_height:
                    # One last check for elements
                    if target_count and count_selector:
                        elements = await page.query_selector_all(count_selector)
                        logger.debug(f"Final scroll: Found {len(elements)} elements")
                    break
        else:
            no_change_count = 0
            
        last_height = new_height
        scroll_count += 1
    
    # Return element count if selector provided
    if count_selector:
        elements = await page.query_selector_all(count_selector)
        return len(elements)
    
    return scroll_count


async def wait_for_element(
    page: Page,
    selector: str,
    timeout: int = 30000,
    state: str = "visible"
) -> bool:
    """
    Wait for an element to appear on the page.
    
    Args:
        page: Playwright page instance
        selector: CSS selector for the element
        timeout: Maximum wait time in milliseconds
        state: Element state to wait for ('visible', 'attached', 'hidden')
    
    Returns:
        True if element found, False otherwise
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout, state=state)
        return True
    except Exception:
        return False


async def wait_for_network_idle(page: Page, timeout: int = 30000):
    """
    Wait for network to become idle (no pending requests).
    
    Args:
        page: Playwright page instance
        timeout: Maximum wait time in milliseconds
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        # If network idle times out, just continue
        pass


async def wait_for_page_ready(page: Page, max_wait: int = 10):
    """
    Wait for page to be ready with dynamic content loaded.
    
    Args:
        page: Playwright page instance
        max_wait: Maximum seconds to wait
    """
    # Wait for DOM content
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=max_wait * 1000)
    except Exception:
        pass
    
    # Add a small delay for JavaScript execution
    await random_delay(1, 2)
    
    # Try to wait for network idle but don't block too long
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass


async def safe_click(page: Page, selector: str, timeout: int = 5000) -> bool:
    """
    Safely click an element if it exists.
    
    Args:
        page: Playwright page instance
        selector: CSS selector for the element to click
        timeout: Maximum wait time in milliseconds
    
    Returns:
        True if clicked successfully, False otherwise
    """
    try:
        element = await page.wait_for_selector(selector, timeout=timeout, state="visible")
        if element:
            await element.click()
            return True
    except Exception:
        pass
    return False


async def get_text_content(page: Page, selector: str, default: str = "") -> str:
    """
    Get text content from an element safely.
    
    Args:
        page: Playwright page instance
        selector: CSS selector for the element
        default: Default value if element not found
    
    Returns:
        Text content of the element or default value
    """
    try:
        element = await page.query_selector(selector)
        if element:
            text = await element.text_content()
            return text.strip() if text else default
    except Exception:
        pass
    return default


async def get_attribute(page: Page, selector: str, attribute: str, default: str = "") -> str:
    """
    Get attribute value from an element safely.
    
    Args:
        page: Playwright page instance
        selector: CSS selector for the element
        attribute: Attribute name to get
        default: Default value if element/attribute not found
    
    Returns:
        Attribute value or default
    """
    try:
        element = await page.query_selector(selector)
        if element:
            value = await element.get_attribute(attribute)
            return value if value else default
    except Exception:
        pass
    return default


async def human_like_type(page: Page, selector: str, text: str, delay_range: tuple[int, int] = (50, 150)):
    """
    Type text with human-like delays between keystrokes.
    
    Args:
        page: Playwright page instance
        selector: CSS selector for the input element
        text: Text to type
        delay_range: Range of delays between keystrokes in milliseconds
    """
    element = await page.wait_for_selector(selector, state="visible")
    if element:
        await element.click()
        for char in text:
            await element.type(char, delay=random.randint(*delay_range))
            

async def take_screenshot(page: Page, filename: str):
    """Take a screenshot for debugging purposes."""
    await page.screenshot(path=filename, full_page=True)

