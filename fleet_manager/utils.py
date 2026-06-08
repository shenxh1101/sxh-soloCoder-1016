import csv
import json
import os
from dataclasses import dataclass, field
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


@dataclass
class ValidationError:
    row_number: int
    field: str
    value: str
    error: str


@dataclass
class ValidationResult:
    valid_orders: List[Order] = field(default_factory=list)
    valid_vehicles: List[Vehicle] = field(default_factory=list)
    valid_drivers: List[Driver] = field(default_factory=list)
    errors: List[ValidationError] = field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    @property
    def error_count(self) -> int:
        return len(self.errors)


def _check_missing_fields(row: dict, required_fields: List[str], row_num: int) -> List[ValidationError]:
    errors = []
    for field in required_fields:
        if field not in row or row[field] is None or str(row[field]).strip() == "":
            errors.append(ValidationError(
                row_number=row_num,
                field=field,
                value=str(row.get(field, "")),
                error=f"字段 '{field}' 缺失或为空"
            ))
    return errors


def _parse_float(value: str, field: str, row_num: int) -> Tuple[float | None, List[ValidationError]]:
    errors = []
    try:
        return float(value), errors
    except (ValueError, TypeError):
        errors.append(ValidationError(
            row_number=row_num,
            field=field,
            value=str(value),
            error=f"字段 '{field}' 必须是数字，当前值为 '{value}'"
        ))
        return None, errors


def _parse_datetime(value: str, field: str, row_num: int, fmt: str = '%Y-%m-%d %H:%M:%S') -> Tuple[datetime | None, List[ValidationError]]:
    errors = []
    try:
        return datetime.strptime(value, fmt), errors
    except ValueError:
        errors.append(ValidationError(
            row_number=row_num,
            field=field,
            value=str(value),
            error=f"字段 '{field}' 日期格式错误，应为 '{fmt}'，当前值为 '{value}'"
        ))
        return None, errors


def _parse_date(value: str, field: str, row_num: int, fmt: str = '%Y-%m-%d') -> Tuple[date | None, List[ValidationError]]:
    errors = []
    try:
        return datetime.strptime(value, fmt).date(), errors
    except ValueError:
        errors.append(ValidationError(
            row_number=row_num,
            field=field,
            value=str(value),
            error=f"字段 '{field}' 日期格式错误，应为 '{fmt}'，当前值为 '{value}'"
        ))
        return None, errors


def load_orders(filepath: str, validate: bool = True) -> List[Order]:
    result = load_orders_with_validation(filepath)
    if result.has_errors:
        print_validation_errors(result.errors, "订单")
    return result.valid_orders


def load_orders_with_validation(filepath: str) -> ValidationResult:
    result = ValidationResult()
    required_fields = ['order_id', 'customer', 'origin', 'destination', 'cargo', 'weight', 'volume', 'delivery_deadline']
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            row_errors = _check_missing_fields(row, required_fields, row_num)
            if row_errors:
                result.errors.extend(row_errors)
                continue
            
            weight, weight_errors = _parse_float(row['weight'], 'weight', row_num)
            volume, volume_errors = _parse_float(row['volume'], 'volume', row_num)
            deadline, deadline_errors = _parse_datetime(row['delivery_deadline'], 'delivery_deadline', row_num)
            
            result.errors.extend(weight_errors)
            result.errors.extend(volume_errors)
            result.errors.extend(deadline_errors)
            
            if weight is not None and volume is not None and deadline is not None:
                if weight <= 0:
                    result.errors.append(ValidationError(
                        row_number=row_num,
                        field='weight',
                        value=str(weight),
                        error=f"重量必须大于0，当前值为 {weight}"
                    ))
                    continue
                if volume <= 0:
                    result.errors.append(ValidationError(
                        row_number=row_num,
                        field='volume',
                        value=str(volume),
                        error=f"体积必须大于0，当前值为 {volume}"
                    ))
                    continue
                if deadline < datetime.now():
                    result.errors.append(ValidationError(
                        row_number=row_num,
                        field='delivery_deadline',
                        value=deadline.strftime('%Y-%m-%d %H:%M:%S'),
                        error=f"送达截止时间已过"
                    ))
                
                order = Order(
                    order_id=row['order_id'],
                    customer=row['customer'],
                    origin=row['origin'],
                    destination=row['destination'],
                    cargo=row['cargo'],
                    weight=weight,
                    volume=volume,
                    delivery_deadline=deadline
                )
                result.valid_orders.append(order)
    
    return result


def load_vehicles(filepath: str, validate: bool = True) -> List[Vehicle]:
    result = load_vehicles_with_validation(filepath)
    if result.has_errors:
        print_validation_errors(result.errors, "车辆")
    return result.valid_vehicles


def load_vehicles_with_validation(filepath: str) -> ValidationResult:
    result = ValidationResult()
    required_fields = ['plate_number', 'vehicle_type', 'max_weight', 'max_volume', 'inspection_date']
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            row_errors = _check_missing_fields(row, required_fields, row_num)
            if row_errors:
                result.errors.extend(row_errors)
                continue
            
            max_weight, weight_errors = _parse_float(row['max_weight'], 'max_weight', row_num)
            max_volume, volume_errors = _parse_float(row['max_volume'], 'max_volume', row_num)
            inspection_date, inspection_errors = _parse_date(row['inspection_date'], 'inspection_date', row_num)
            fuel_consumption, fc_errors = _parse_float(row.get('fuel_consumption', '25.0'), 'fuel_consumption', row_num)
            
            result.errors.extend(weight_errors)
            result.errors.extend(volume_errors)
            result.errors.extend(inspection_errors)
            result.errors.extend(fc_errors)
            
            if max_weight is not None and max_volume is not None and inspection_date is not None and fuel_consumption is not None:
                if max_weight <= 0:
                    result.errors.append(ValidationError(
                        row_number=row_num,
                        field='max_weight',
                        value=str(max_weight),
                        error=f"载重限制必须大于0"
                    ))
                    continue
                if max_volume <= 0:
                    result.errors.append(ValidationError(
                        row_number=row_num,
                        field='max_volume',
                        value=str(max_volume),
                        error=f"体积限制必须大于0"
                    ))
                    continue
                if fuel_consumption <= 0:
                    result.errors.append(ValidationError(
                        row_number=row_num,
                        field='fuel_consumption',
                        value=str(fuel_consumption),
                        error=f"油耗必须大于0"
                    ))
                    continue
                
                days_left = (inspection_date - date.today()).days
                if days_left < -365:
                    result.errors.append(ValidationError(
                        row_number=row_num,
                        field='inspection_date',
                        value=inspection_date.strftime('%Y-%m-%d'),
                        error=f"年检日期异常，已过期超过1年"
                    ))
                    continue
                
                vehicle = Vehicle(
                    plate_number=row['plate_number'],
                    vehicle_type=row['vehicle_type'],
                    max_weight=max_weight,
                    max_volume=max_volume,
                    inspection_date=inspection_date,
                    fuel_consumption=fuel_consumption,
                    status=row.get('status', 'available')
                )
                result.valid_vehicles.append(vehicle)
    
    return result


def load_drivers(filepath: str, validate: bool = True) -> List[Driver]:
    result = load_drivers_with_validation(filepath)
    if result.has_errors:
        print_validation_errors(result.errors, "司机")
    return result.valid_drivers


def load_drivers_with_validation(filepath: str) -> ValidationResult:
    result = ValidationResult()
    required_fields = ['driver_id', 'name', 'phone']
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            row_errors = _check_missing_fields(row, required_fields, row_num)
            if row_errors:
                result.errors.extend(row_errors)
                continue
            
            max_hours, hours_errors = _parse_float(row.get('max_daily_hours', '8.0'), 'max_daily_hours', row_num)
            result.errors.extend(hours_errors)
            
            if max_hours is not None:
                if max_hours <= 0 or max_hours > 24:
                    result.errors.append(ValidationError(
                        row_number=row_num,
                        field='max_daily_hours',
                        value=str(max_hours),
                        error=f"日最大工时必须在 0-24 小时之间"
                    ))
                    continue
                
                driver = Driver(
                    driver_id=row['driver_id'],
                    name=row['name'],
                    phone=row['phone'],
                    max_daily_hours=max_hours
                )
                result.valid_drivers.append(driver)
    
    return result


def save_import_errors(
    errors: List[ValidationError],
    data_type: str,
    source_file: str,
    output_dir: str = "."
) -> None:
    if not errors:
        return
    
    import_errors_file = os.path.join(output_dir, "import_errors.json")
    
    existing_errors = []
    if os.path.exists(import_errors_file):
        try:
            with open(import_errors_file, 'r', encoding='utf-8') as f:
                existing_errors = json.load(f)
        except:
            existing_errors = []
    
    error_data = []
    for err in errors:
        error_data.append({
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "data_type": data_type,
            "source_file": source_file,
            "row_number": err.row_number,
            "field": err.field,
            "value": err.value,
            "error": err.error
        })
    
    existing_errors.extend(error_data)
    
    with open(import_errors_file, 'w', encoding='utf-8') as f:
        json.dump(existing_errors, f, ensure_ascii=False, indent=2)


def load_import_errors(output_dir: str = ".") -> List[dict]:
    import_errors_file = os.path.join(output_dir, "import_errors.json")
    if not os.path.exists(import_errors_file):
        return []
    
    try:
        with open(import_errors_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def clear_import_errors(output_dir: str = ".") -> None:
    import_errors_file = os.path.join(output_dir, "import_errors.json")
    if os.path.exists(import_errors_file):
        os.remove(import_errors_file)


def print_validation_errors(errors: List[ValidationError], data_type: str) -> None:
    if not errors:
        return
    
    print(f"\n⚠️  {data_type}数据校验发现 {len(errors)} 个问题：")
    print(f"{'-'*80}")
    
    rows = []
    for err in errors:
        rows.append([
            err.row_number,
            err.field,
            err.value,
            err.error
        ])
    
    print_table(["行号", "字段", "值", "错误说明"], rows)
    print(f"\nℹ️  以上行数据已跳过，错误信息已保存至 import_errors.json")


def save_trips(trips: List[Trip], filepath: str) -> None:
    data = []
    for trip in trips:
        history_data = []
        for entry in trip.history:
            history_data.append({
                'timestamp': entry.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'action_type': entry.action_type,
                'action': entry.action,
                'reason': entry.reason,
                'notes': entry.notes
            })
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
            'notes': trip.notes,
            'history': history_data
        })
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_trips(filepath: str) -> List[Trip]:
    from .models import TripHistoryEntry
    
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    trips = []
    for item in data:
        departure = datetime.strptime(item['departure_time'], '%Y-%m-%d %H:%M:%S') if item.get('departure_time') else None
        arrival = datetime.strptime(item['arrival_time'], '%Y-%m-%d %H:%M:%S') if item.get('arrival_time') else None
        
        history = []
        for h in item.get('history', []):
            ts = datetime.strptime(h['timestamp'], '%Y-%m-%d %H:%M:%S')
            history.append(TripHistoryEntry(
                timestamp=ts,
                action_type=h['action_type'],
                action=h['action'],
                reason=h.get('reason', ''),
                notes=h.get('notes', '')
            ))
        
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
            notes=item.get('notes', ''),
            history=history
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
