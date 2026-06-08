from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, date


@dataclass
class Order:
    order_id: str
    customer: str
    origin: str
    destination: str
    cargo: str
    weight: float
    volume: float
    delivery_deadline: datetime
    status: str = "pending"
    assigned_trip: Optional[str] = None

    @property
    def route_key(self) -> str:
        return f"{self.origin}->{self.destination}"


@dataclass
class Vehicle:
    plate_number: str
    vehicle_type: str
    max_weight: float
    max_volume: float
    inspection_date: date
    status: str = "available"
    current_location: str = "warehouse"
    fuel_consumption: float = 25.0

    def is_inspection_valid(self, check_date: Optional[date] = None) -> bool:
        check_date = check_date or date.today()
        return check_date <= self.inspection_date

    def days_until_inspection(self, check_date: Optional[date] = None) -> int:
        check_date = check_date or date.today()
        return (self.inspection_date - check_date).days


@dataclass
class Driver:
    driver_id: str
    name: str
    phone: str
    max_daily_hours: float = 8.0
    daily_hours_used: float = 0.0
    status: str = "available"

    def can_work(self, additional_hours: float) -> bool:
        return (self.daily_hours_used + additional_hours) <= self.max_daily_hours

    def remaining_hours(self) -> float:
        return self.max_daily_hours - self.daily_hours_used


@dataclass
class TripHistoryEntry:
    timestamp: datetime
    action_type: str
    action: str
    reason: str = ""
    notes: str = ""


@dataclass
class Trip:
    trip_id: str
    vehicle_plate: str
    driver_id: str
    origin: str
    destination: str
    orders: List[str] = field(default_factory=list)
    total_weight: float = 0.0
    total_volume: float = 0.0
    estimated_distance: float = 0.0
    estimated_hours: float = 0.0
    estimated_fuel_cost: float = 0.0
    estimated_toll_cost: float = 0.0
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    status: str = "planned"
    delay_minutes: int = 0
    reassigned: bool = False
    notes: str = ""
    history: List[TripHistoryEntry] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return self.estimated_fuel_cost + self.estimated_toll_cost

    @property
    def route_key(self) -> str:
        return f"{self.origin}->{self.destination}"


@dataclass
class DailyReport:
    report_date: date
    total_trips: int = 0
    completed_trips: int = 0
    in_progress_trips: int = 0
    planned_trips: int = 0
    delayed_trips: int = 0
    reassigned_trips: int = 0
    total_orders: int = 0
    total_revenue: float = 0.0
    total_cost: float = 0.0
    anomalies: List[str] = field(default_factory=list)
