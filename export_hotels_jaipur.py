# export_hotels_jaipur.py
import asyncio, csv
from scraper.browser import BrowserManager
from scraper.hotel_listing import scrape_hotel_listings
from scraper.models import ScraperConfig
from datetime import datetime, timedelta

check_in = (datetime.now()  + timedelta(days=17))
async def main():
    cfg = ScraperConfig(location="Jaipur", num_hotels=4000, days_ahead=1)
    async with BrowserManager(headless=False) as page:
        hotels = await scrape_hotel_listings(page, cfg, check_in=check_in)
    print(f"Got {len(hotels)} hotels")
    with open("jaipur_hotels2.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "url", "rating", "review_count", "star_rating", "location"])
        for h in hotels:
            w.writerow([h.name, h.url, h.rating, h.review_count, h.star_rating, h.location])

if __name__ == "__main__":
    asyncio.run(main())