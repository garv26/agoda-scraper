"""Output handlers for CSV and JSON export."""

import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import RoomData, HotelWithRooms, ScrapeResult, ScraperConfig

logger = logging.getLogger(__name__)


class OutputManager:
    """Manages output file generation and incremental saving."""

    def __init__(self, config: ScraperConfig, output_dir: Optional[str] = None):
        self.config = config
        self.output_dir = Path(output_dir or config.output_dir)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create subdirectories for CSV and JSON
        self.csv_dir = self.output_dir / "csv"
        self.json_dir = self.output_dir / "json"
        self._ensure_output_dir()
        
        # File paths
        self.csv_path = self.csv_dir / f"agoda_rooms_{self.timestamp}.csv"
        self.json_path = self.json_dir / f"agoda_rooms_{self.timestamp}.json"
        self.progress_path = self.json_dir / f"agoda_progress_{self.timestamp}.json"
        
        # CSV headers - includes hotel-level info
        self.csv_headers = [
            "hotel_name",
            "hotel_location",
            "hotel_rating",
            "hotel_star_rating",
            "hotel_review_count",
            "date",
            "room_type",
            "price",
            "currency",
            "amenities",
            "availability",
            "cancellation_policy",
            "meal_plan",
        ]
        
        # Initialize CSV file with headers
        self._init_csv()
        
        # Progress tracking
        self.hotels_processed = 0
        self.total_rooms = 0

    def _ensure_output_dir(self):
        """Create output directory if it doesn't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)

    def _init_csv(self):
        """Initialize CSV file with headers."""
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_headers)
            writer.writeheader()
        logger.info(f"Initialized CSV file: {self.csv_path}")

    def append_rooms_to_csv(self, rooms: list[RoomData]):
        """
        Append room data to CSV file.
        
        Args:
            rooms: List of RoomData objects to append
        """
        if not rooms:
            return
            
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_headers)
            for room in rooms:
                writer.writerow(room.to_csv_row())
        
        self.total_rooms += len(rooms)
        logger.debug(f"Appended {len(rooms)} rooms to CSV")

    def save_progress(self, result: ScrapeResult):
        """
        Save current progress to JSON file.
        
        Args:
            result: Current ScrapeResult object
        """
        progress_data = {
            "timestamp": datetime.now().isoformat(),
            "hotels_processed": len(result.hotels),
            "total_rooms": sum(len(h.rooms) for h in result.hotels),
            "location": result.location,
            "config": result.config.to_dict(),
        }
        
        with open(self.progress_path, "w", encoding="utf-8") as f:
            json.dump(progress_data, f, indent=2)
        
        logger.debug(f"Progress saved: {len(result.hotels)} hotels, {progress_data['total_rooms']} rooms")

    def save_final_json(self, result: ScrapeResult):
        """
        Save complete result to JSON file.
        
        Args:
            result: Complete ScrapeResult object
        """
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved final JSON: {self.json_path}")

    def get_file_paths(self) -> dict:
        """Get paths to output files."""
        return {
            "csv": str(self.csv_path),
            "json": str(self.json_path),
            "progress": str(self.progress_path),
        }


def export_to_csv(rooms: list[RoomData], filepath: str):
    """
    Export room data to CSV file.
    
    Args:
        rooms: List of RoomData objects
        filepath: Output file path
    """
    # Ensure directory exists
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    headers = [
        "hotel_name",
        "date",
        "room_type",
        "price",
        "currency",
        "amenities",
        "availability",
        "cancellation_policy",
        "meal_plan",
    ]
    
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for room in rooms:
            writer.writerow(room.to_csv_row())
    
    logger.info(f"Exported {len(rooms)} rooms to CSV: {filepath}")


def export_to_json(result: ScrapeResult, filepath: str):
    """
    Export scrape result to JSON file.
    
    Args:
        result: ScrapeResult object
        filepath: Output file path
    """
    # Ensure directory exists
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    
    logger.info(f"Exported result to JSON: {filepath}")


def generate_summary(result: ScrapeResult) -> str:
    """
    Generate a summary of the scraping results.
    
    Args:
        result: ScrapeResult object
    
    Returns:
        Summary string
    """
    total_hotels = len(result.hotels)
    total_rooms = sum(len(h.rooms) for h in result.hotels)
    
    # Calculate statistics
    all_rooms = result.get_all_room_data()
    available_rooms = [r for r in all_rooms if r.is_available]
    rooms_with_price = [r for r in all_rooms if r.price is not None]
    
    avg_price = 0
    min_price = 0
    max_price = 0
    if rooms_with_price:
        prices = [r.price for r in rooms_with_price]
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
    
    # Get unique dates
    unique_dates = set(r.date for r in all_rooms)
    
    summary = f"""
=== Agoda Scraping Summary ===
Location: {result.location}
Scrape Date: {result.scrape_date.strftime('%Y-%m-%d %H:%M:%S')}

Hotels Scraped: {total_hotels}
Total Room Records: {total_rooms}
Unique Dates: {len(unique_dates)}

Availability:
  - Available: {len(available_rooms)} ({len(available_rooms)/len(all_rooms)*100:.1f}%)
  - Not Available: {len(all_rooms) - len(available_rooms)} ({(len(all_rooms) - len(available_rooms))/len(all_rooms)*100:.1f}%)

Pricing:
  - Rooms with Price: {len(rooms_with_price)}
  - Average Price: {avg_price:,.2f}
  - Min Price: {min_price:,.2f}
  - Max Price: {max_price:,.2f}

Errors: {len(result.errors)}
================================
"""
    return summary.strip()


def load_progress(progress_path: str) -> Optional[dict]:
    """
    Load progress from a previous run.
    
    Args:
        progress_path: Path to progress JSON file
    
    Returns:
        Progress data dictionary or None if not found
    """
    try:
        with open(progress_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning(f"Error loading progress: {e}")
        return None


def merge_csv_files(input_files: list[str], output_file: str):
    """
    Merge multiple CSV files into one.
    
    Args:
        input_files: List of input CSV file paths
        output_file: Output CSV file path
    """
    all_rows = []
    headers = None
    
    for filepath in input_files:
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if headers is None:
                headers = reader.fieldnames
            all_rows.extend(list(reader))
    
    if headers and all_rows:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(all_rows)
        
        logger.info(f"Merged {len(input_files)} CSV files into {output_file}")

