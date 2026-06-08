import os
from typing import List, Dict
from ..models import Trip, Vehicle, Order
from ..utils import (
    load_trips, load_vehicles, load_orders, load_orders_status,
    get_route_distance, calculate_fuel_cost, calculate_toll_cost,
    estimate_travel_hours, print_table
)


def estimate_route_cost(origin: str, destination: str, vehicle: Vehicle | None = None) -> Dict:
    distance = get_route_distance(origin, destination)
    fuel_consumption = vehicle.fuel_consumption if vehicle else 25.0
    
    fuel_cost = calculate_fuel_cost(distance, fuel_consumption)
    toll_cost = calculate_toll_cost(distance)
    hours = estimate_travel_hours(distance)
    
    return {
        "origin": origin,
        "destination": destination,
        "distance": distance,
        "fuel_cost": fuel_cost,
        "toll_cost": toll_cost,
        "total_cost": round(fuel_cost + toll_cost, 2),
        "estimated_hours": hours,
        "fuel_consumption": fuel_consumption
    }


def estimate_order_cost(order: Order, vehicle: Vehicle | None = None) -> Dict:
    result = estimate_route_cost(order.origin, order.destination, vehicle)
    result["order_id"] = order.order_id
    result["customer"] = order.customer
    result["cargo"] = order.cargo
    result["weight"] = order.weight
    result["volume"] = order.volume
    return result


def calculate_trip_cost(trip: Trip, vehicles: List[Vehicle]) -> Dict:
    vehicle = next((v for v in vehicles if v.plate_number == trip.vehicle_plate), None)
    result = estimate_route_cost(trip.origin, trip.destination, vehicle)
    result["trip_id"] = trip.trip_id
    result["vehicle_plate"] = trip.vehicle_plate
    result["orders_count"] = len(trip.orders)
    result["total_weight"] = trip.total_weight
    result["total_volume"] = trip.total_volume
    return result


def run_cost_analysis(
    vehicles_file: str, orders_file: str,
    mode: str = "trips",
    origin: str | None = None,
    destination: str | None = None,
    output_dir: str = "."
) -> None:
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    vehicles = load_vehicles(vehicles_file)
    orders = load_orders(orders_file)
    
    orders_status_file = os.path.join(output_dir, "orders_status.json")
    orders = load_orders_status(orders_status_file, orders)
    
    print(f"\n{'='*70}")
    print("成本分析")
    print(f"{'='*70}")
    
    if mode == "route" and origin and destination:
        print(f"\n📊 路线成本估算: {origin} -> {destination}")
        print(f"\n不同车型成本对比:")
        
        rows = []
        for vehicle in vehicles:
            if vehicle.status != "available":
                continue
            cost = estimate_route_cost(origin, destination, vehicle)
            rows.append([
                vehicle.plate_number,
                vehicle.vehicle_type,
                f"{vehicle.max_weight}t",
                f"{cost['distance']}km",
                f"{cost['estimated_hours']}h",
                f"¥{cost['fuel_cost']:.2f}",
                f"¥{cost['toll_cost']:.2f}",
                f"¥{cost['total_cost']:.2f}"
            ])
        
        print_table(
            ["车牌号", "车型", "载重", "里程", "时长", "油费", "过路费", "总成本"],
            rows
        )
        
        return
    
    if mode == "order":
        pending_orders = [o for o in orders if o.status == "pending"]
        
        if not pending_orders:
            print("\n✅ 所有订单已分配")
            return
        
        print(f"\n📊 订单成本估算 ({len(pending_orders)} 个待分配订单):")
        print()
        
        rows = []
        for order in pending_orders:
            cost = estimate_order_cost(order)
            rows.append([
                order.order_id,
                order.customer,
                order.route_key,
                order.cargo,
                f"{order.weight}t",
                f"{cost['distance']}km",
                f"¥{cost['fuel_cost']:.2f}",
                f"¥{cost['toll_cost']:.2f}",
                f"¥{cost['total_cost']:.2f}"
            ])
        
        print_table(
            ["订单ID", "客户", "路线", "货物", "重量", "里程", "油费", "过路费", "总成本"],
            rows
        )
        
        total_fuel = sum(r['fuel_cost'] for r in [estimate_order_cost(o) for o in pending_orders])
        total_toll = sum(r['toll_cost'] for r in [estimate_order_cost(o) for o in pending_orders])
        total = total_fuel + total_toll
        
        print(f"\n📈 待分配订单预估总成本:")
        print(f"   油费: ¥{total_fuel:.2f}")
        print(f"   过路费: ¥{total_toll:.2f}")
        print(f"   合计: ¥{total:.2f}")
        
        return
    
    if mode == "trips" or mode == "all":
        if not trips:
            print("\n⚠️  暂无运输计划")
            return
        
        print(f"\n📊 班次成本分析 ({len(trips)} 个班次):")
        print()
        
        rows = []
        total_fuel = 0.0
        total_toll = 0.0
        total_distance = 0.0
        
        for trip in trips:
            cost = calculate_trip_cost(trip, vehicles)
            total_fuel += cost["fuel_cost"]
            total_toll += cost["toll_cost"]
            total_distance += cost["distance"]
            
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
                trip.route_key,
                f"{cost['orders_count']}单",
                f"{cost['distance']}km",
                f"¥{cost['fuel_cost']:.2f}",
                f"¥{cost['toll_cost']:.2f}",
                f"¥{cost['total_cost']:.2f}",
                status
            ])
        
        print_table(
            ["班次ID", "车牌号", "路线", "订单数", "里程", "油费", "过路费", "总成本", "状态"],
            rows
        )
        
        print(f"\n📈 总计:")
        print(f"   总里程: {total_distance:.0f}km")
        print(f"   总油费: ¥{total_fuel:.2f}")
        print(f"   总过路费: ¥{total_toll:.2f}")
        print(f"   总成本: ¥{total_fuel + total_toll:.2f}")
        
        if mode == "all":
            completed = [t for t in trips if t.status == "completed"]
            if completed:
                print(f"\n💵 已完成班次成本:")
                completed_fuel = sum(calculate_trip_cost(t, vehicles)['fuel_cost'] for t in completed)
                completed_toll = sum(calculate_trip_cost(t, vehicles)['toll_cost'] for t in completed)
                print(f"   已完成 {len(completed)} 个班次")
                print(f"   已发生油费: ¥{completed_fuel:.2f}")
                print(f"   已发生过路费: ¥{completed_toll:.2f}")
                print(f"   已发生总成本: ¥{completed_fuel + completed_toll:.2f}")
    
    print(f"\n{'='*70}")
