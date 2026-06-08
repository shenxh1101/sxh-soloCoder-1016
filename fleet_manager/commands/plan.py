import os
from datetime import datetime
from typing import List, Dict, Tuple
from ..models import Order, Vehicle, Driver, Trip
from ..utils import (
    load_orders, load_vehicles, load_drivers,
    save_trips, save_orders_status, load_orders_status, load_trips,
    get_route_distance, estimate_travel_hours,
    calculate_fuel_cost, calculate_toll_cost,
    generate_id, print_table
)


def group_orders_by_route(orders: List[Order]) -> Dict[str, List[Order]]:
    groups: Dict[str, List[Order]] = {}
    for order in orders:
        if order.status == "pending":
            key = order.route_key
            if key not in groups:
                groups[key] = []
            groups[key].append(order)
    return groups


def merge_orders_for_vehicle(
    orders: List[Order], vehicle: Vehicle
) -> Tuple[List[Order], float, float]:
    selected = []
    total_weight = 0.0
    total_volume = 0.0
    
    sorted_orders = sorted(orders, key=lambda o: o.delivery_deadline)
    
    for order in sorted_orders:
        new_weight = total_weight + order.weight
        new_volume = total_volume + order.volume
        if new_weight <= vehicle.max_weight and new_volume <= vehicle.max_volume:
            selected.append(order)
            total_weight = new_weight
            total_volume = new_volume
    
    return selected, total_weight, total_volume


def find_available_driver(drivers: List[Driver], required_hours: float) -> Driver | None:
    for driver in drivers:
        if driver.status == "available" and driver.can_work(required_hours):
            return driver
    return None


def generate_plan(
    orders_file: str, vehicles_file: str, drivers_file: str,
    output_dir: str = "."
) -> List[Trip]:
    orders = load_orders(orders_file)
    vehicles = load_vehicles(vehicles_file)
    drivers = load_drivers(drivers_file)
    
    orders_status_file = os.path.join(output_dir, "orders_status.json")
    trips_file = os.path.join(output_dir, "trips.json")
    
    orders = load_orders_status(orders_status_file, orders)
    
    existing_trips = load_trips(trips_file)
    used_trip_ids = {t.trip_id for t in existing_trips}
    
    route_groups = group_orders_by_route(orders)
    
    trips: List[Trip] = []
    trip_seq = 1
    used_vehicles = set()
    used_drivers = set()
    
    print(f"\n{'='*60}")
    print("生成运输计划")
    print(f"{'='*60}")
    print(f"待处理订单数: {len([o for o in orders if o.status == 'pending'])}")
    print(f"可用车辆数: {len([v for v in vehicles if v.status == 'available'])}")
    print(f"可用司机数: {len([d for d in drivers if d.status == 'available'])}")
    
    for route_key, route_orders in sorted(route_groups.items()):
        origin, destination = route_key.split("->")
        
        available_vehicles = [
            v for v in vehicles 
            if v.status == "available" 
            and v.plate_number not in used_vehicles
            and v.is_inspection_valid()
        ]
        
        if not available_vehicles:
            print(f"\n⚠️  路线 {route_key}: 无可用车辆，跳过")
            continue
        
        remaining_orders = route_orders.copy()
        
        for vehicle in available_vehicles:
            if not remaining_orders:
                break
            
            distance = get_route_distance(origin, destination)
            hours = estimate_travel_hours(distance)
            
            driver = find_available_driver(
                [d for d in drivers if d.driver_id not in used_drivers],
                hours
            )
            
            if not driver:
                print(f"⚠️  路线 {route_key}: 无可用司机，剩余 {len(remaining_orders)} 个订单未分配")
                break
            
            selected_orders, total_weight, total_volume = merge_orders_for_vehicle(
                remaining_orders, vehicle
            )
            
            if not selected_orders:
                print(f"⚠️  路线 {route_key}: 车辆 {vehicle.plate_number} 容量不足")
                continue
            
            while generate_id("T", trip_seq) in used_trip_ids:
                trip_seq += 1
            
            trip_id = generate_id("T", trip_seq)
            trip_seq += 1
            
            fuel_cost = calculate_fuel_cost(distance, vehicle.fuel_consumption)
            toll_cost = calculate_toll_cost(distance)
            
            trip = Trip(
                trip_id=trip_id,
                vehicle_plate=vehicle.plate_number,
                driver_id=driver.driver_id,
                origin=origin,
                destination=destination,
                orders=[o.order_id for o in selected_orders],
                total_weight=total_weight,
                total_volume=total_volume,
                estimated_distance=distance,
                estimated_hours=hours,
                estimated_fuel_cost=fuel_cost,
                estimated_toll_cost=toll_cost,
                departure_time=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0),
                status="planned"
            )
            
            trips.append(trip)
            used_vehicles.add(vehicle.plate_number)
            used_drivers.add(driver.driver_id)
            driver.daily_hours_used += hours
            
            for order in selected_orders:
                order.status = "assigned"
                order.assigned_trip = trip_id
                remaining_orders.remove(order)
        
        if remaining_orders:
            print(f"ℹ️  路线 {route_key}: 剩余 {len(remaining_orders)} 个订单需后续安排")
    
    all_trips = existing_trips + trips
    
    save_trips(all_trips, trips_file)
    save_orders_status(orders, orders_status_file)
    
    print(f"\n{'='*60}")
    print("计划生成完成")
    print(f"{'='*60}")
    
    if trips:
        print(f"\n新增 {len(trips)} 个运输班次：")
        rows = []
        for trip in trips:
            driver_name = next((d.name for d in drivers if d.driver_id == trip.driver_id), trip.driver_id)
            rows.append([
                trip.trip_id,
                trip.vehicle_plate,
                driver_name,
                trip.route_key,
                f"{len(trip.orders)}单",
                f"{trip.total_weight:.1f}t",
                f"{trip.total_volume:.1f}m³",
                f"{trip.estimated_distance}km",
                f"{trip.estimated_hours}h",
                f"¥{trip.total_cost:.2f}"
            ])
        
        print_table(
            ["班次ID", "车牌号", "司机", "路线", "订单数", "总重", "总体积", "里程", "时长", "预估费用"],
            rows
        )
    else:
        print("\n没有新生成的运输班次。")
    
    unassigned = [o for o in orders if o.status == "pending"]
    if unassigned:
        print(f"\n⚠️  未分配订单 {len(unassigned)} 个：")
        for o in unassigned[:5]:
            print(f"   - {o.order_id}: {o.customer} {o.route_key} {o.weight}t")
        if len(unassigned) > 5:
            print(f"   ... 还有 {len(unassigned) - 5} 个")
    
    return all_trips


def show_plan(output_dir: str = ".") -> None:
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    
    if not trips:
        print("暂无运输计划。")
        return
    
    print(f"\n{'='*80}")
    print("当前运输计划")
    print(f"{'='*80}")
    print(f"总班次: {len(trips)}")
    
    planned = [t for t in trips if t.status == "planned"]
    in_progress = [t for t in trips if t.status == "in_progress"]
    completed = [t for t in trips if t.status == "completed"]
    
    print(f"待出发: {len(planned)} | 运输中: {len(in_progress)} | 已完成: {len(completed)}")
    
    rows = []
    for trip in trips:
        status_map = {
            "planned": "⏳ 待出发",
            "in_progress": "🚚 运输中",
            "completed": "✅ 已完成",
            "delayed": "⚠️  晚点"
        }
        status = status_map.get(trip.status, trip.status)
        rows.append([
            trip.trip_id,
            trip.vehicle_plate,
            trip.driver_id,
            trip.route_key,
            f"{len(trip.orders)}单",
            f"{trip.estimated_distance}km",
            f"{trip.estimated_hours}h",
            status
        ])
    
    print_table(
        ["班次ID", "车牌号", "司机ID", "路线", "订单数", "里程", "时长", "状态"],
        rows
    )
