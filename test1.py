import asyncio
from playwright.async_api import async_playwright
from datetime import datetime, timedelta

# Scrape one hotel for given days
async def scrape_hotel(page, hotel_url, days=30):
    results = []
    for i in range(days):
        checkin = (datetime.today() + timedelta(days=i)).strftime("%Y-%m-%d")
        checkout = (datetime.today() + timedelta(days=i+1)).strftime("%Y-%m-%d")

        url = f"{hotel_url}?checkIn={checkin}&checkOut={checkout}"
        await page.goto(url, timeout=60000)

        # Use the same robust room selectors as the main scraper (see scraper/room_details.py)
        direct_room_selector = (
            '[data-ppapi="room-price"], '
            '[data-selenium="room-panel"], '
            '[data-selenium="room-name"], '
            '[data-testid*="room"], '
            '[class*="RoomGridItem"]'
        )

        # Wait for any typical room element to appear
        await page.wait_for_selector(direct_room_selector, timeout=30000)

        # Prefer room-name elements; fall back to panels if needed
        rooms = await page.query_selector_all('[data-selenium="room-name"]')
        if not rooms:
            rooms = await page.query_selector_all('[data-selenium="room-panel"]')

        for room in rooms:
            name = (await room.inner_text()).strip()
            results.append({
                "hotel": hotel_url,
                "date": checkin,
                "room": name
            })

        print(f"{hotel_url} → {checkin}: {len(rooms)} rooms scraped")

    return results

# Scrape multiple hotels concurrently
async def scrape_multiple_hotels(hotel_urls, days=30):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def scrape_with_page(url):
            page = await browser.new_page()
            try:
                return await scrape_hotel(page, url, days)
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                return []
            finally:
                try:
                    await page.close()
                except Exception:
                    # Page or browser may already be closed; ignore cleanup errors
                    pass

        tasks = [scrape_with_page(url) for url in hotel_urls]
        all_results = await asyncio.gather(*tasks, return_exceptions=False)

        await browser.close()
        return [item for sublist in all_results for item in sublist]

if __name__ == "__main__":
    # Replace with actual Agoda hotel URLs
    hotel_urls = [
        "https://www.agoda.com/the-lalit-jaipur_2/hotel/jaipur-in.html?countryId=35&finalPriceView=1&isShowMobileAppPrice=false&cid=-1&numberOfBedrooms=&familyMode=false&adults=2&children=0&rooms=1&maxRooms=0&checkIn=2025-12-2&isCalendarCallout=false&childAges=&numberOfGuest=0&missingChildAges=false&travellerType=1&showReviewSubmissionEntry=false&currencyCode=INR&isFreeOccSearch=false&tspTypes=15,8&los=1&searchrequestid=9bb56f5d-33c7-4dc5-a26b-f5c5d7202a55",
        "https://www.agoda.com/radisson-blu-jaipur/hotel/jaipur-in.html?countryId=35&finalPriceView=1&isShowMobileAppPrice=false&cid=-1&numberOfBedrooms=&familyMode=false&adults=2&children=0&rooms=1&maxRooms=0&checkIn=2025-12-2&isCalendarCallout=false&childAges=&numberOfGuest=0&missingChildAges=false&travellerType=1&showReviewSubmissionEntry=false&currencyCode=INR&isFreeOccSearch=false&los=1&searchrequestid=9bb56f5d-33c7-4dc5-a26b-f5c5d7202a55",
        "https://www.agoda.com/the-green-diamond/hotel/jaipur-in.html?countryId=35&finalPriceView=1&isShowMobileAppPrice=false&cid=-1&numberOfBedrooms=&familyMode=false&adults=2&children=0&rooms=1&maxRooms=0&checkIn=2025-12-2&isCalendarCallout=false&childAges=&numberOfGuest=0&missingChildAges=false&travellerType=1&showReviewSubmissionEntry=false&currencyCode=INR&isFreeOccSearch=false&los=1&searchrequestid=9bb56f5d-33c7-4dc5-a26b-f5c5d7202a55"
    ]
    print(hotel_urls)   
    results = asyncio.run(scrape_multiple_hotels(hotel_urls, days=30))

    print("\nFinal Results:")
    for r in results:
        print(r)
