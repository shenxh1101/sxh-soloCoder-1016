import csv
import json
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple, Optional
from .models import Order, Vehicle, Driver, Trip, DailyReport


ROUTE_DISTANCES: Dict[str, float] = {
    "北京->上海": 1200.0,
    "北京->广州": 2100.0,
    "北京->深圳": 2150.0,
    "上海->广州": 1400.0,
    "上海->深圳": 1450.0,
    "广州->深圳": 150.0,
    "北京->杭州": 1100.0,
    "上海->杭州": 180.0,
    "北京->成都": 1800.0,
    "上海->成都": 1900.0,
    "广州->成都": 1600.0,
    "北京->南京": 900.0,
    "上海->南京": 300.0,
    "北京->武汉": 1050.0,
    "上海->武汉": 800.0,
    "广州->武汉": 900.0,
}

FUEL_PRICE: float = 7.5
TOLL_RATE: float = 0.8
AVERAGE_SPEED: float = 60.0


def get_route_distance(origin: str, destination: str) -> float:
    key = f"{origin}->{destination}"
    reverse_key = f"{destination}->{origin}"
    return ROUTE_DISTANCES.get(key, ROUTE_DISTANCES.get(reverse_key, 500.0))


def calculate_fuel_cost(distance: float, fuel_consumption: float = 25.0) -> float:
    return round((distance / 100.0) * fuel_consumption * FUEL_PRICE, 2)


def calculate_toll_cost(distance: float) -> float:
    return round(distance * TOLL_RATE, 2)


def estimate_travel_hours(distance: float) -> float:
    return round(distance / AVERAGE_SPEED, 1)


def generate_id(prefix: str, seq: int) -> str:
    return f"{prefix}{seq:04d}"


def load_orders(filepath: str) -> List[Order]:
    orders = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            deadline = datetime.strptime(row['delivery_deadline'], '%Y-%m-%d %H:%M:%S')
            order = Order(
                order_id=row['order_id'],
                customer=row['customer'],
                origin=row['origin'],
                destination=row['destination'],
                cargo=row['cargo'],
                weight=float(row['weight']),
                volume=float(row['volume']),
                delivery_deadline=deadline
            )
            orders.append(order)
    return orders


def load_vehicles(filepath: str) -> List[Vehicle]:
    vehicles = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            inspection = datetime.strptime(row['inspection_date'], '%Y-%m-%d').date()
            vehicle = Vehicle(
                plate_number=row['plate_number'],
                vehicle_type=row['vehicle_type'],
                max_weight=float(row['max_weight']),
                max_volume=float(row['max_volume']),
                inspection_date=inspection,
                fuel_consumption=float(row.get('fuel_consumption', '25.0'))
            )
            vehicles.append(vehicle)
    return vehicles


def load_drivers(filepath: str) -> List[Driver]:
    drivers = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            driver = Driver(
                driver_id=row['driver_id'],
                name=row['name'],
                phone=row['phone'],
                max_daily_hours=float(row.get('max_daily_hours', '8.0'))
            )
            drivers.append(driver)
    return drivers


def save_trips(trips: List[Trip], filepath: str) -> None:
    data = []
    for trip in trips:
        data.append({
            'trip_id': trip.trip_id,
            'vehicle_plate': trip.vehicle_plate,
            'driver_id': trip.driver_id,
            'origin': trip.origin,
            'destination': trip.destination,
            'orders': trip.orders,
            'total_weight': trip.total_weight,
            'total_volume': trip.total_volume,
            'estimated_distance': trip.estimated_distance,
            'estimated_hours': trip.estimated_hours,
            'estimated_fuel_cost': trip.estimated_fuel_cost,
            'estimated_toll_cost': trip.estimated_toll_cost,
            'departure_time': trip.departure_time.strftime('%Y-%m-%d %H:%M:%S') if trip.departure_time else None,
            'arrival_time': trip.arrival_time.strftime('%Y-%m-%d %H:%M:%S') if trip.arrival_time else None,
            'status': trip.status,
            'delay_minutes': trip.delay_minutes,
            'reassigned': trip.reassigned,
            'notes': trip.notes
        })
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_trips(filepath: str) -> List[Trip]:
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    trips = []
    for item in data:
        departure = datetime.strptime(item['departure_time'], '%Y-%m-%d %H:%M:%S') if item['departure_time'] else None
        arrival = datetime.strptime(item['arrival_time'], '%Y-%m-%d %H:%M:%S') if item['arrival_time'] else None
        trip = Trip(
            trip_id=item['trip_id'],
            vehicle_plate=item['vehicle_plate'],
            driver_id=item['driver_id'],
            origin=item['origin'],
            destination=item['destination'],
            orders=item['orders'],
            total_weight=item['total_weight'],
            total_volume=item['total_volume'],
            estimated_distance=item['estimated_distance'],
            estimated_hours=item['estimated_hours'],
            estimated_fuel_cost=item['estimated_fuel_cost'],
            estimated_toll_cost=item['estimated_toll_cost'],
            departure_time=departure,
            arrival_time=arrival,
            status=item['status'],
            delay_minutes=item['delay_minutes'],
            reassigned=item['reassigned'],
            notes=item['notes']
        )
        trips.append(trip)
    return trips


def save_orders_status(orders: List[Order], filepath: str) -> None:
    data = []
    for order in orders:
        data.append({
            'order_id': order.order_id,
            'status': order.status,
            'assigned_trip': order.assigned_trip
        })
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_orders_status(filepath: str, orders: List[Order]) -> List[Order]:
    if not os.path.exists(filepath):
        return orders
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    status_map = {item['order_id']: item for item in data}
    for order in orders:
        if order.order_id in status_map:
            order.status = status_map[order.order_id]['status']
            order.assigned_trip = status_map[order.order_id]['assigned_trip']
    return orders


def print_table(headers: List[str], rows: List[List[str]]) -> None:
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    
    separator = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"
    header_line = "|" + "|".join(f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)) + "|"
    
    print(separator)
    print(header_line)
    print(separator)
    for row in rows:
        print("|" + "|".join(f" {str(cell):<{col_widths[i]}} " for i, cell in enumerate(row)) + "|")
    print(separator)
