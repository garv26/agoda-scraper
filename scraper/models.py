"""Data models for Agoda scraper."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


@dataclass
class HotelInfo:
    """Basic hotel information from search results."""
    name: str
    url: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    base_price: Optional[float] = None
    currency: str = "INR"
    star_rating: Optional[int] = None
    location: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "url": self.url,
            "rating": self.rating,
            "review_count": self.review_count,
            "base_price": self.base_price,
            "currency": self.currency,
            "star_rating": self.star_rating,
            "location": self.location,
        }


@dataclass
class RoomData:
    """Room information for a specific date."""
    hotel_name: str
    date: str
    room_type: str
    price: Optional[float]
    currency: str
    amenities: list[str]
    is_available: bool
    cancellation_policy: Optional[str] = None
    meal_plan: Optional[str] = None
    max_occupancy: Optional[int] = None
    bed_type: Optional[str] = None
    # Hotel-level info for CSV export
    hotel_location: Optional[str] = None
    hotel_rating: Optional[float] = None
    hotel_star_rating: Optional[int] = None
    hotel_review_count: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hotel_name": self.hotel_name,
            "date": self.date,
            "room_type": self.room_type,
            "price": self.price,
            "currency": self.currency,
            "amenities": self.amenities,
            "is_available": self.is_available,
            "cancellation_policy": self.cancellation_policy,
            "meal_plan": self.meal_plan,
            "max_occupancy": self.max_occupancy,
            "bed_type": self.bed_type,
            "hotel_location": self.hotel_location,
            "hotel_rating": self.hotel_rating,
            "hotel_star_rating": self.hotel_star_rating,
            "hotel_review_count": self.hotel_review_count,
        }

    def to_csv_row(self) -> dict:
        """Convert to CSV row format."""
        return {
            "hotel_name": self.hotel_name,
            "hotel_location": self.hotel_location or "",
            "hotel_rating": self.hotel_rating if self.hotel_rating else "",
            "hotel_star_rating": self.hotel_star_rating if self.hotel_star_rating else "",
            "hotel_review_count": self.hotel_review_count if self.hotel_review_count else "",
            "date": self.date,
            "room_type": self.room_type,
            "price": self.price if self.price else "",
            "currency": self.currency,
            "amenities": ";".join(self.amenities) if self.amenities else "",
            "availability": "Available" if self.is_available else "Not Available",
            "cancellation_policy": self.cancellation_policy or "",
            "meal_plan": self.meal_plan or "",
        }


@dataclass
class HotelWithRooms:
    """Complete hotel data with all room information across dates."""
    info: HotelInfo
    rooms: list[RoomData] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            "name": self.info.name,
            "url": self.info.url,
            "rating": self.info.rating,
            "review_count": self.info.review_count,
            "star_rating": self.info.star_rating,
            "location": self.info.location,
            "rooms": [room.to_dict() for room in self.rooms],
        }


class DelayConfig(BaseModel):
    """Configuration for random delays."""
    between_hotels: tuple[float, float] = Field(default=(8.0, 14.0))
    between_dates: tuple[float, float] = Field(default=(2.0, 4.0))
    scroll_pause: tuple[float, float] = Field(default=(2.0, 4.0))


class ScraperConfig(BaseModel):
    """Main scraper configuration."""
    location: str = "Jaipur"
    num_hotels: int = 50
    days_ahead: int = 60
    guests: int = 2
    rooms: int = 1
    delays: DelayConfig = Field(default_factory=DelayConfig)
    output_dir: str = "output"
    headless: bool = True
    save_interval: int = 5  # Save progress every N hotels

    @classmethod
    def from_json_file(cls, filepath: str) -> "ScraperConfig":
        """Load configuration from JSON file."""
        import json
        with open(filepath, "r") as f:
            data = json.load(f)
        
        # Convert delay lists to tuples
        if "delays" in data:
            for key, value in data["delays"].items():
                if isinstance(value, list) and len(value) == 2:
                    data["delays"][key] = tuple(value)
        
        return cls(**data)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "location": self.location,
            "num_hotels": self.num_hotels,
            "days_ahead": self.days_ahead,
            "guests": self.guests,
            "rooms": self.rooms,
            "delays": {
                "between_hotels": list(self.delays.between_hotels),
                "between_dates": list(self.delays.between_dates),
                "scroll_pause": list(self.delays.scroll_pause),
            },
            "output_dir": self.output_dir,
        }


@dataclass
class ScrapeResult:
    """Complete scraping result."""
    scrape_date: datetime
    location: str
    config: ScraperConfig
    hotels: list[HotelWithRooms] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            "scrape_date": self.scrape_date.isoformat(),
            "location": self.location,
            "config": self.config.to_dict(),
            "total_hotels": len(self.hotels),
            "total_rooms": sum(len(h.rooms) for h in self.hotels),
            "hotels": [hotel.to_dict() for hotel in self.hotels],
            "errors": self.errors if self.errors else None,
        }

    def get_all_room_data(self) -> list[RoomData]:
        """Get flat list of all room data across all hotels."""
        all_rooms = []
        for hotel in self.hotels:
            all_rooms.extend(hotel.rooms)
        return all_rooms

