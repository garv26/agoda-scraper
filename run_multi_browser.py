#!/usr/bin/env python3
"""
Multi-Browser Parallel Agoda Scraper

This script runs the parallel scraper with multiple browser instances,
each with a unique fingerprint to avoid bot detection.

Usage:
    # Test run: 3 browsers, 5 hotels, 2 days
    python run_multi_browser.py --browsers 3 --limit 5 --days 2

    # Production: 10 browsers, all hotels, 30 days
    python run_multi_browser.py --browsers 10 --days 30

    # With visible browsers for debugging
    python run_multi_browser.py --browsers 2 --limit 3 --days 1 --no-headless

    # Use pre-extracted hotel list
    python run_multi_browser.py --hotels-csv jaipur_hotels.csv --browsers 5 --days 30

Proxy Setup:
    Edit scraper/multi_browser_scraper.py and add your proxies to PROXY_LIST:
    
    PROXY_LIST = [
        "socks5://127.0.0.1:1081",  # SSH tunnel
        "socks5://your-vps-ip:1080", # VPS proxy
    ]
    
    Or set programmatically:
    from scraper.multi_browser_scraper import set_proxies
    set_proxies(["socks5://127.0.0.1:1081", ...])
"""

import asyncio
import logging
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Ensure logs directory exists
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Setup logging
log_filename = logs_dir / f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_filename),
    ],
)
logger = logging.getLogger(__name__)
logger.info(f"Log file: {log_filename}")

from scraper.multi_browser_scraper import (
    multi_browser_scrape, 
    load_hotels_from_csv,
    set_proxies,
)
from scraper.models import ScraperConfig


async def main():
    parser = argparse.ArgumentParser(
        description="Multi-Browser Parallel Agoda Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Test run (3 browsers, 5 hotels, 2 days):
    python run_multi_browser.py --browsers 3 --limit 5 --days 2

  Production run (10 browsers, 30 days):
    python run_multi_browser.py --browsers 10 --days 30

  Debug with visible browsers:
    python run_multi_browser.py --browsers 2 --limit 3 --no-headless

Memory Requirements:
  5 browsers  -> ~1 GB RAM
  10 browsers -> ~2 GB RAM
  20 browsers -> ~4 GB RAM
        """
    )
    
    parser.add_argument(
        "--hotels-csv", "-i",
        default="split_hotels/hotels_part_1.csv",
        help="Input CSV with hotel list (default: split_hotels/hotels_part_1.csv)"
    )
    
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output CSV file path (default: auto-generated in output/csv/)"
    )
    
    parser.add_argument(
        "--browsers", "-b",
        type=int,
        default=5,
        help="Number of browser instances (default: 5)"
    )
    
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=30,
        help="Days ahead to scrape (default: 30)"
    )
    
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Limit number of hotels (for testing)"
    )
    
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Start from hotel N (skip first N hotels)"
    )
    
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run with visible browsers (for debugging)"
    )
    
    parser.add_argument(
        "--skip-proxy-validation",
        action="store_true",
        help="Skip proxy validation (faster startup)"
    )
    
    parser.add_argument(
        "--delay-dates",
        type=float,
        nargs=2,
        default=[0.5, 1.5],
        metavar=("MIN", "MAX"),
        help="Delay between dates in seconds (default: 0.5 1.5)"
    )
    
    parser.add_argument(
        "--delay-hotels",
        type=float,
        nargs=2,
        default=[2.0, 5.0],
        metavar=("MIN", "MAX"),
        help="Delay between hotels in seconds (default: 2.0 5.0)"
    )
    
    parser.add_argument(
        "--proxy",
        type=str,
        action="append",
        help="Add a proxy (can be used multiple times). Format: socks5://ip:port"
    )
    
    args = parser.parse_args()
    
    # Set proxies if provided via command line
    if args.proxy:
        set_proxies(args.proxy)
        logger.info(f"Using {len(args.proxy)} proxies from command line")
    
    # Load hotels from CSV
    try:
        hotels = load_hotels_from_csv(args.hotels_csv)
    except FileNotFoundError:
        logger.error(f"Hotel CSV file not found: {args.hotels_csv}")
        logger.info("Please run the hotel listing scraper first, or specify a valid CSV file.")
        sys.exit(1)
    
    if not hotels:
        logger.error("No hotels loaded from CSV")
        sys.exit(1)
    
    logger.info(f"Loaded {len(hotels)} hotels from {args.hotels_csv}")
    
    # Apply offset and limit
    if args.offset > 0:
        hotels = hotels[args.offset:]
        logger.info(f"Skipped first {args.offset} hotels, {len(hotels)} remaining")
    
    if args.limit:
        hotels = hotels[:args.limit]
        logger.info(f"Limited to {len(hotels)} hotels")
    
    if not hotels:
        logger.error("No hotels to scrape after applying offset/limit")
        sys.exit(1)
    
    # Create config
    config = ScraperConfig(
        location="Jaipur",
        days_ahead=args.days,
        num_hotels=len(hotels),
    )
    
    # Calculate estimates
    total_requests = len(hotels) * args.days
    est_time_per_hotel = 12  # minutes (rough estimate)
    est_total_hours = (len(hotels) * est_time_per_hotel / 60) / args.browsers
    
    logger.info(f"\n{'='*60}")
    logger.info(f"  SCRAPING PLAN")
    logger.info(f"{'='*60}")
    logger.info(f"  Hotels:           {len(hotels)}")
    logger.info(f"  Days per hotel:   {args.days}")
    logger.info(f"  Total requests:   {total_requests}")
    logger.info(f"  Browser count:    {args.browsers}")
    logger.info(f"  Estimated time:   ~{est_total_hours:.1f} hours")
    logger.info(f"{'='*60}\n")
    
    # Confirm if large run
    if len(hotels) > 50 and not args.limit:
        logger.info("Large scraping job detected. Starting in 5 seconds...")
        logger.info("Press Ctrl+C to cancel.")
        await asyncio.sleep(5)
    
    # Run the scraper
    try:
        results = await multi_browser_scrape(
            hotels=hotels,
            config=config,
            num_browsers=args.browsers,
            headless=not args.no_headless,
            output_file=args.output,
            validate_proxies_first=not args.skip_proxy_validation,
            delay_between_dates=tuple(args.delay_dates),
            delay_between_hotels=tuple(args.delay_hotels),
        )
        
        logger.info(f"\nScraping complete! Total rooms scraped: {len(results)}")
        
    except KeyboardInterrupt:
        logger.info("\nScraping interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

