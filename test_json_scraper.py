#!/usr/bin/env python3
"""Test script to verify JSON API interception and parsing."""

import asyncio
import logging
from datetime import datetime, timedelta
from scraper.browser import BrowserManager
from scraper.models import HotelInfo, ScraperConfig
from scraper.room_details import scrape_hotel_rooms

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_json_scraper():
    """Test the JSON API scraping approach on a single hotel."""
    
    # Test hotel - Laxmi Palace Heritage Boutique Hotel in Jaipur
    test_hotel = HotelInfo(
        name="Laxmi Palace Heritage Boutique Hotel",
        url="https://www.agoda.com/laxmi-palace-heritage-boutique-hotel/hotel/jaipur-in.html",
        location="Jaipur",
        rating=9.0,
        star_rating=3,
        review_count=123,
        base_price=5000.0,
        currency="INR"
    )
    
    # Configuration for testing
    config = ScraperConfig(
        location="Jaipur",
        num_hotels=1,
        days_ahead=3,  # Test just 3 days
        guests=2,
        rooms=1,
        delays={
            "between_hotels": [2, 3],
            "between_dates": [0.5, 1.0],
            "scroll_pause": [0.3, 0.7]
        },
        output_dir="output"
    )
    
    logger.info("=" * 80)
    logger.info("Testing JSON API Scraper")
    logger.info("=" * 80)
    logger.info(f"Hotel: {test_hotel.name}")
    logger.info(f"Testing {config.days_ahead} days ahead")
    logger.info("=" * 80)
    
    # Create browser
    browser_manager = BrowserManager(headless=False)
    page = await browser_manager.start()
    
    try:
        # Test scraping for tomorrow
        check_in = datetime.now() + timedelta(days=1)
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"\n🔍 Scraping for check-in date: {check_in.date()}")
        
        rooms = await scrape_hotel_rooms(
            page=page,
            hotel=test_hotel,
            check_in=check_in,
            config=config,
            session_id=session_id
        )
        
        # Display results
        logger.info("\n" + "=" * 80)
        logger.info(f"✅ RESULTS: Found {len(rooms)} rooms")
        logger.info("=" * 80)
        
        for i, room in enumerate(rooms, 1):
            logger.info(f"\n📍 Room {i}:")
            logger.info(f"   Name: {room.room_type}")
            logger.info(f"   Price: ₹{room.price} {room.currency}" if room.price else "   Price: Not Available")
            logger.info(f"   Available: {room.is_available}")
            if room.bed_type:
                logger.info(f"   Bed Type: {room.bed_type}")
            if room.meal_plan:
                logger.info(f"   Meal Plan: {room.meal_plan}")
            if room.max_occupancy:
                logger.info(f"   Max Occupancy: {room.max_occupancy}")
            if room.amenities:
                logger.info(f"   Amenities: {', '.join(room.amenities[:5])}")
                if len(room.amenities) > 5:
                    logger.info(f"              ... and {len(room.amenities) - 5} more")
        
        logger.info("\n" + "=" * 80)
        logger.info("Check the following for debugging:")
        logger.info(f"  - API sample JSON: output/api_samples/{session_id}_sample.json")
        logger.info(f"  - Debug HTML: output/debug_html/{session_id}/")
        logger.info("=" * 80)
        
        # Validate results
        if rooms:
            success = True
            for room in rooms:
                # Check if we got garbage room names (the old problem)
                if "Free WiFi See details" in room.room_type:
                    logger.error(f"❌ FAILED: Still getting garbage room names: {room.room_type}")
                    success = False
                elif room.room_type in ["No Rooms Found", "Error"]:
                    logger.warning(f"⚠️  WARNING: {room.room_type}")
                    success = False
            
            if success:
                logger.info("\n✅ SUCCESS: JSON scraping is working correctly!")
            else:
                logger.warning("\n⚠️  Some issues detected - check logs above")
        else:
            logger.error("\n❌ FAILED: No rooms found")
        
    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}", exc_info=True)
    
    finally:
        await browser_manager.close()


if __name__ == "__main__":
    asyncio.run(test_json_scraper())
