"""Main orchestration module for Agoda scraper."""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .browser import BrowserManager, random_delay
from .hotel_listing import scrape_hotel_listings
from .room_details import scrape_hotel_rooms_for_dates
from .models import ScraperConfig, HotelWithRooms, ScrapeResult
from .output import OutputManager, generate_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


async def run_scraper(config: ScraperConfig, headless: bool = True) -> ScrapeResult:
    """
    Main scraping function that orchestrates the entire process.
    
    Args:
        config: Scraper configuration
        headless: Whether to run browser in headless mode
    
    Returns:
        ScrapeResult with all scraped data
    """
    start_time = datetime.now()
    logger.info(f"Starting Agoda scraper for {config.location}")
    logger.info(f"Configuration: {config.num_hotels} hotels, {config.days_ahead} days")
    
    # Initialize result
    result = ScrapeResult(
        scrape_date=start_time,
        location=config.location,
        config=config,
    )
    
    # Initialize output manager
    output = OutputManager(config)
    logger.info(f"Output files will be saved to: {output.output_dir}")
    
    # Start browser
    browser_manager = BrowserManager(headless=headless)
    
    try:
        page = await browser_manager.start()
        logger.info("Browser started successfully")
        
        # Step 1: Get hotel listings
        logger.info("="*50)
        logger.info("Step 1: Scraping hotel listings...")
        logger.info("="*50)
        
        start_date = datetime.now() + timedelta(days=1)
        hotels = await scrape_hotel_listings(page, config, start_date)
        
        if not hotels:
            logger.error("No hotels found. Aborting.")
            result.errors.append("No hotels found in search results")
            return result
        
        logger.info(f"Found {len(hotels)} hotels")
        
        # Limit to configured number
        hotels = hotels[:config.num_hotels]
        logger.info(f"Will scrape {len(hotels)} hotels")
        
        # Step 2: Scrape room details for each hotel
        logger.info("="*50)
        logger.info("Step 2: Scraping room details for each hotel...")
        logger.info("="*50)
        
        for idx, hotel in enumerate(hotels, 1):
            logger.info(f"\n[{idx}/{len(hotels)}] Processing: {hotel.name}")
            
            try:
                # Create hotel with rooms object
                hotel_with_rooms = HotelWithRooms(info=hotel)
                
                # Scrape rooms for all dates with immediate CSV saving
                rooms = await scrape_hotel_rooms_for_dates(
                    page, 
                    hotel, 
                    config, 
                    start_date,
                    on_rooms_scraped=output.append_rooms_to_csv  # Save immediately after each date
                )
                
                hotel_with_rooms.rooms = rooms
                result.hotels.append(hotel_with_rooms)
                
                logger.info(f"  -> Scraped {len(rooms)} room records")
                
            except Exception as e:
                error_msg = f"Error scraping {hotel.name}: {str(e)}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                
                # Create placeholder entry
                hotel_with_rooms = HotelWithRooms(info=hotel)
                result.hotels.append(hotel_with_rooms)
            
            # Save progress periodically
            if idx % config.save_interval == 0:
                output.save_progress(result)
                logger.info(f"Progress saved ({idx}/{len(hotels)} hotels)")
            
            # Add delay between hotels
            if idx < len(hotels):
                await random_delay(*config.delays.between_hotels)
        
        # Step 3: Save final results
        logger.info("="*50)
        logger.info("Step 3: Saving final results...")
        logger.info("="*50)
        
        output.save_final_json(result)
        
        # Calculate duration
        duration = datetime.now() - start_time
        logger.info(f"\nScraping completed in {duration}")
        
        # Generate and print summary
        summary = generate_summary(result)
        logger.info(summary)
        
        # Log output file paths
        paths = output.get_file_paths()
        logger.info(f"\nOutput files:")
        logger.info(f"  CSV:  {paths['csv']}")
        logger.info(f"  JSON: {paths['json']}")
        
    except Exception as e:
        logger.error(f"Fatal error during scraping: {e}")
        result.errors.append(f"Fatal error: {str(e)}")
        raise
        
    finally:
        await browser_manager.close()
        logger.info("Browser closed")
    
    return result


def load_config(config_path: Optional[str] = None) -> ScraperConfig:
    """
    Load configuration from file or use defaults.
    
    Args:
        config_path: Path to config JSON file
    
    Returns:
        ScraperConfig object
    """
    if config_path:
        logger.info(f"Loading config from: {config_path}")
        return ScraperConfig.from_json_file(config_path)
    
    # Try default locations
    default_paths = ["config.json", "scraper/config.json", "../config.json"]
    for path in default_paths:
        if Path(path).exists():
            logger.info(f"Loading config from: {path}")
            return ScraperConfig.from_json_file(path)
    
    logger.info("Using default configuration")
    return ScraperConfig()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Agoda Hotel Scraper - Scrape hotel and room data from Agoda.com"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration JSON file",
        default=None,
    )
    
    parser.add_argument(
        "--location", "-l",
        type=str,
        help="Location/city to search (overrides config)",
        default=None,
    )
    
    parser.add_argument(
        "--hotels", "-n",
        type=int,
        help="Number of hotels to scrape (overrides config)",
        default=None,
    )
    
    parser.add_argument(
        "--days", "-d",
        type=int,
        help="Number of days to scrape (overrides config)",
        default=None,
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output directory (overrides config)",
        default=None,
    )
    
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (for debugging)",
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load configuration
    config = load_config(args.config)
    
    # Override with command line arguments
    if args.location:
        config.location = args.location
    if args.hotels:
        config.num_hotels = args.hotels
    if args.days:
        config.days_ahead = args.days
    if args.output:
        config.output_dir = args.output
    
    headless = not args.no_headless
    
    # Run the scraper
    try:
        result = asyncio.run(run_scraper(config, headless=headless))
        
        if result.errors:
            logger.warning(f"Completed with {len(result.errors)} errors")
            sys.exit(1)
        else:
            logger.info("Scraping completed successfully!")
            sys.exit(0)
            
    except KeyboardInterrupt:
        logger.info("\nScraping interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

