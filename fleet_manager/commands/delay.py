import os
from datetime import datetime, date, timedelta
from typing import List, Dict
from ..models import Trip, Vehicle, Driver, Order
from ..utils import (
    load_trips, save_trips,
    load_vehicles, load_drivers, load_orders,
    load_orders_status, save_orders_status,
    print_table
)


def reassign_trip(
    trip_id: str,
    new_vehicle: str | None = None,
    new_driver: str | None = None,
    reason: str = "",
    output_dir: str = "."
) -> Trip | None:
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    
    trip = next((t for t in trips if t.trip_id == trip_id), None)
    if not trip:
        print(f"❌ 未找到班次 {trip_id}")
        return None
    
    old_vehicle = trip.vehicle_plate
    old_driver = trip.driver_id
    
    if new_vehicle:
        trip.vehicle_plate = new_vehicle
    if new_driver:
        trip.driver_id = new_driver
    
    trip.reassigned = True
    notes_parts = []
    if reason:
        notes_parts.append(f"改派原因: {reason}")
    if new_vehicle:
        notes_parts.append(f"车辆: {old_vehicle} -> {new_vehicle}")
    if new_driver:
        notes_parts.append(f"司机: {old_driver} -> {new_driver}")
    notes_parts.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if trip.notes:
        trip.notes += "\n" + "; ".join(notes_parts)
    else:
        trip.notes = "; ".join(notes_parts)
    
    save_trips(trips, trips_file)
    return trip


def record_delay(
    trip_id: str,
    delay_minutes: int,
    reason: str = "",
    output_dir: str = "."
) -> Trip | None:
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    
    trip = next((t for t in trips if t.trip_id == trip_id), None)
    if not trip:
        print(f"❌ 未找到班次 {trip_id}")
        return None
    
    trip.delay_minutes += delay_minutes
    trip.status = "delayed"
    
    if trip.arrival_time:
        trip.arrival_time += timedelta(minutes=delay_minutes)
    
    notes = f"晚点{delay_minutes}分钟"
    if reason:
        notes += f"，原因: {reason}"
    notes += f"，时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    if trip.notes:
        trip.notes += "\n" + notes
    else:
        trip.notes = notes
    
    save_trips(trips, trips_file)
    return trip


def mark_departure(
    trip_id: str,
    actual_time: datetime | None = None,
    output_dir: str = "."
) -> Trip | None:
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    
    trip = next((t for t in trips if t.trip_id == trip_id), None)
    if not trip:
        print(f"❌ 未找到班次 {trip_id}")
        return None
    
    if trip.status not in ["planned", "delayed"]:
        print(f"⚠️  班次 {trip_id} 当前状态为 {trip.status}，无法标记出发")
        return None
    
    actual_time = actual_time or datetime.now()
    trip.departure_time = actual_time
    trip.status = "in_progress"
    
    estimated_arrival = actual_time + timedelta(hours=trip.estimated_hours)
    if trip.delay_minutes > 0:
        estimated_arrival += timedelta(minutes=trip.delay_minutes)
    trip.arrival_time = estimated_arrival
    
    notes = f"实际出发: {actual_time.strftime('%Y-%m-%d %H:%M:%S')}"
    if trip.notes:
        trip.notes += "\n" + notes
    else:
        trip.notes = notes
    
    save_trips(trips, trips_file)
    return trip


def mark_arrival(
    trip_id: str,
    actual_time: datetime | None = None,
    output_dir: str = "."
) -> Trip | None:
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    
    trip = next((t for t in trips if t.trip_id == trip_id), None)
    if not trip:
        print(f"❌ 未找到班次 {trip_id}")
        return None
    
    if trip.status != "in_progress":
        print(f"⚠️  班次 {trip_id} 当前状态为 {trip.status}，无法标记到达，请先标记出发")
        return None
    
    actual_time = actual_time or datetime.now()
    trip.arrival_time = actual_time
    
    if trip.departure_time:
        actual_duration = (actual_time - trip.departure_time).total_seconds() / 3600
        expected_duration = trip.estimated_hours + (trip.delay_minutes / 60)
        if actual_duration > expected_duration:
            additional_delay = int((actual_duration - expected_duration) * 60)
            trip.delay_minutes += additional_delay
    
    notes = f"实际到达: {actual_time.strftime('%Y-%m-%d %H:%M:%S')}"
    if trip.notes:
        trip.notes += "\n" + notes
    else:
        trip.notes = notes
    
    save_trips(trips, trips_file)
    return trip


def mark_complete(
    trip_id: str,
    actual_time: datetime | None = None,
    output_dir: str = "."
) -> Trip | None:
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    
    trip = next((t for t in trips if t.trip_id == trip_id), None)
    if not trip:
        print(f"❌ 未找到班次 {trip_id}")
        return None
    
    if trip.status not in ["in_progress", "delayed"]:
        if trip.status == "completed":
            print(f"ℹ️  班次 {trip_id} 已标记为完成")
            return trip
        print(f"⚠️  班次 {trip_id} 当前状态为 {trip.status}，无法标记完成")
        return None
    
    actual_time = actual_time or datetime.now()
    
    if not trip.arrival_time:
        trip.arrival_time = actual_time
    
    trip.status = "completed"
    
    notes = f"班次完成: {actual_time.strftime('%Y-%m-%d %H:%M:%S')}"
    if trip.notes:
        trip.notes += "\n" + notes
    else:
        trip.notes = notes
    
    save_trips(trips, trips_file)
    return trip


def simulate_delay_impact(
    trip_id: str,
    delay_minutes: int,
    drivers_file: str,
    vehicles_file: str,
    orders_file: str,
    output_dir: str = "."
) -> Dict:
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    drivers = load_drivers(drivers_file)
    vehicles = load_vehicles(vehicles_file)
    orders_status_file = os.path.join(output_dir, "orders_status.json")
    orders = load_orders(orders_file) if os.path.exists(orders_file) else []
    if orders:
        orders = load_orders_status(orders_status_file, orders)
    
    trip = next((t for t in trips if t.trip_id == trip_id), None)
    if not trip:
        print(f"❌ 未找到班次 {trip_id}")
        return {}
    
    driver = next((d for d in drivers if d.driver_id == trip.driver_id), None)
    vehicle = next((v for v in vehicles if v.plate_number == trip.vehicle_plate), None)
    
    trip_orders = [o for o in orders if o.order_id in trip.orders]
    
    new_arrival = None
    if trip.arrival_time:
        new_arrival = trip.arrival_time + timedelta(minutes=delay_minutes)
    elif trip.departure_time:
        new_arrival = trip.departure_time + timedelta(hours=trip.estimated_hours) + timedelta(minutes=delay_minutes)
    
    overtime_risk = False
    overtime_hours = 0.0
    if driver and new_arrival and trip.departure_time:
        actual_hours = (new_arrival - trip.departure_time).total_seconds() / 3600
        if actual_hours > driver.max_daily_hours:
            overtime_risk = True
            overtime_hours = actual_hours - driver.max_daily_hours
    
    delivery_risks = []
    if new_arrival:
        for order in trip_orders:
            if new_arrival > order.delivery_deadline:
                delay_hours = (new_arrival - order.delivery_deadline).total_seconds() / 3600
                delivery_risks.append({
                    "order_id": order.order_id,
                    "customer": order.customer,
                    "deadline": order.delivery_deadline,
                    "delay_hours": round(delay_hours, 1)
                })
    
    follow_on_trips = []
    if trip.departure_time:
        trip_date = trip.departure_time.date()
        same_vehicle_trips = [
            t for t in trips
            if t.vehicle_plate == trip.vehicle_plate
            and t.trip_id != trip_id
            and t.departure_time
            and t.departure_time.date() == trip_date
            and t.departure_time > trip.departure_time
        ]
        same_driver_trips = [
            t for t in trips
            if t.driver_id == trip.driver_id
            and t.trip_id != trip_id
            and t.departure_time
            and t.departure_time.date() == trip_date
            and t.departure_time > trip.departure_time
        ]
        follow_on_trips = list({t.trip_id: t for t in same_vehicle_trips + same_driver_trips}.values())
    
    return {
        "trip": trip,
        "driver": driver,
        "vehicle": vehicle,
        "orders": trip_orders,
        "delay_minutes": delay_minutes,
        "original_arrival": trip.arrival_time,
        "new_arrival": new_arrival,
        "overtime_risk": overtime_risk,
        "overtime_hours": overtime_hours,
        "delivery_risks": delivery_risks,
        "follow_on_trips": follow_on_trips
    }


def query_vehicle_tasks(
    plate_number: str,
    vehicles_file: str,
    output_dir: str = ".",
    query_date: date | None = None
) -> List[Trip]:
    query_date = query_date or date.today()
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    
    vehicle_trips = [
        t for t in trips
        if t.vehicle_plate == plate_number
        and t.departure_time
        and t.departure_time.date() == query_date
    ]
    
    vehicle_trips.sort(key=lambda t: t.departure_time or datetime.min)
    
    return vehicle_trips


def run_delay_command(
    action: str,
    trip_id: str | None = None,
    vehicle_plate: str | None = None,
    new_vehicle: str | None = None,
    new_driver: str | None = None,
    delay_minutes: int = 0,
    reason: str = "",
    vehicles_file: str = "data/vehicles.csv",
    drivers_file: str = "data/drivers.csv",
    orders_file: str = "data/orders.csv",
    output_dir: str = "."
) -> None:
    print(f"\n{'='*60}")
    print("调度管理")
    print(f"{'='*60}")
    
    if action == "depart" and trip_id:
        print(f"\n🚛 标记出发 - 班次 {trip_id}")
        trip = mark_departure(trip_id, None, output_dir)
        if trip:
            print(f"✅ 已标记出发！")
            print(f"   实际出发: {trip.departure_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   预计到达: {trip.arrival_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   当前状态: {trip.status}")
    
    elif action == "arrive" and trip_id:
        print(f"\n🏁 标记到达 - 班次 {trip_id}")
        trip = mark_arrival(trip_id, None, output_dir)
        if trip:
            print(f"✅ 已标记到达！")
            print(f"   实际到达: {trip.arrival_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   累计晚点: {trip.delay_minutes} 分钟")
            print(f"   当前状态: {trip.status}")
    
    elif action == "complete" and trip_id:
        print(f"\n✅ 标记完成 - 班次 {trip_id}")
        trip = mark_complete(trip_id, None, output_dir)
        if trip:
            print(f"✅ 已标记完成！")
            if trip.departure_time:
                print(f"   实际出发: {trip.departure_time.strftime('%Y-%m-%d %H:%M:%S')}")
            if trip.arrival_time:
                print(f"   实际到达: {trip.arrival_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   累计晚点: {trip.delay_minutes} 分钟")
            print(f"   当前状态: {trip.status}")
    
    elif action == "reassign" and trip_id:
        print(f"\n🔄 临时改派 - 班次 {trip_id}")
        trip = reassign_trip(trip_id, new_vehicle, new_driver, reason, output_dir)
        if trip:
            print(f"✅ 改派成功！")
            print(f"   车牌号: {trip.vehicle_plate}")
            print(f"   司机ID: {trip.driver_id}")
            if trip.notes:
                print(f"   备注: {trip.notes.split(chr(10))[-1]}")
    
    elif action == "delay" and trip_id and delay_minutes > 0:
        print(f"\n⏰ 记录晚点 - 班次 {trip_id}")
        trip = record_delay(trip_id, delay_minutes, reason, output_dir)
        if trip:
            print(f"✅ 晚点已记录！")
            print(f"   累计晚点: {trip.delay_minutes} 分钟")
            print(f"   当前状态: {trip.status}")
            if trip.arrival_time:
                print(f"   预计到达: {trip.arrival_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    elif action == "simulate" and trip_id and delay_minutes > 0:
        print(f"\n🔮 晚点影响模拟 - 班次 {trip_id}")
        impact = simulate_delay_impact(trip_id, delay_minutes, drivers_file, vehicles_file, orders_file, output_dir)
        if not impact:
            return
        
        trip = impact["trip"]
        driver = impact["driver"]
        print(f"\n📋 班次信息:")
        print(f"   路线: {trip.route_key}")
        print(f"   车辆: {trip.vehicle_plate}")
        print(f"   司机: {driver.name if driver else trip.driver_id}")
        print(f"   订单数: {len(impact['orders'])}")
        
        print(f"\n⏱️  时间影响:")
        print(f"   晚点时间: {delay_minutes} 分钟")
        if impact["original_arrival"]:
            print(f"   原预计到达: {impact['original_arrival'].strftime('%Y-%m-%d %H:%M:%S')}")
        if impact["new_arrival"]:
            print(f"   新预计到达: {impact['new_arrival'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        if impact["overtime_risk"]:
            print(f"\n⚠️  司机超时风险:")
            print(f"   预计超时: {impact['overtime_hours']:.1f} 小时")
        else:
            print(f"\n✅ 无司机超时风险")
        
        if impact["delivery_risks"]:
            print(f"\n⚠️  订单交付超时风险 ({len(impact['delivery_risks'])} 个):")
            rows = []
            for r in impact["delivery_risks"]:
                rows.append([
                    r["order_id"],
                    r["customer"],
                    r["deadline"].strftime("%Y-%m-%d %H:%M"),
                    f"+{r['delay_hours']:.1f}h"
                ])
            print_table(["订单ID", "客户", "要求送达", "超时"], rows)
        else:
            print(f"\n✅ 所有订单仍可按时交付")
        
        if impact["follow_on_trips"]:
            print(f"\n🔗 受影响的后续班次 ({len(impact['follow_on_trips'])} 个):")
            rows = []
            for t in impact["follow_on_trips"]:
                rows.append([
                    t.trip_id,
                    t.route_key,
                    t.departure_time.strftime("%H:%M") if t.departure_time else "-",
                    t.status
                ])
            print_table(["班次ID", "路线", "发车时间", "状态"], rows)
        else:
            print(f"\n✅ 无后续班次受影响")
    
    elif action == "query" and vehicle_plate:
        print(f"\n🚛 车辆当日任务 - {vehicle_plate}")
        today = date.today()
        trips = query_vehicle_tasks(vehicle_plate, vehicles_file, output_dir, today)
        
        if not trips:
            print(f"\nℹ️  该车今日无任务")
            return
        
        orders = load_orders(orders_file) if os.path.exists(orders_file) else []
        if orders:
            orders_status_file = os.path.join(output_dir, "orders_status.json")
            orders = load_orders_status(orders_status_file, orders)
        
        print(f"\n📅 {today.strftime('%Y-%m-%d')} 任务清单:")
        print()
        
        rows = []
        total_distance = 0.0
        total_orders = 0
        
        for trip in trips:
            trip_orders = [o for o in orders if o.order_id in trip.orders]
            customer_list = ", ".join([o.customer for o in trip_orders[:2]])
            if len(trip_orders) > 2:
                customer_list += f" 等{len(trip_orders) - 2}家"
            
            status_map = {
                "planned": "⏳ 待出发",
                "in_progress": "🚚 运输中",
                "completed": "✅ 已完成",
                "delayed": "⚠️  晚点"
            }
            status = status_map.get(trip.status, trip.status)
            
            if trip.delay_minutes > 0:
                status += f" (晚{trip.delay_minutes}分)"
            
            rows.append([
                trip.trip_id,
                trip.route_key,
                customer_list,
                f"{len(trip_orders)}单",
                f"{trip.estimated_distance}km",
                trip.departure_time.strftime("%H:%M") if trip.departure_time else "-",
                trip.arrival_time.strftime("%H:%M") if trip.arrival_time else "-",
                status
            ])
            total_distance += trip.estimated_distance
            total_orders += len(trip_orders)
        
        print_table(
            ["班次ID", "路线", "客户", "订单数", "里程", "发车", "到达", "状态"],
            rows
        )
        
        print(f"\n📊 今日汇总:")
        print(f"   班次数量: {len(trips)}")
        print(f"   订单总数: {total_orders}")
        print(f"   总里程: {total_distance:.0f}km")
        
        completed = [t for t in trips if t.status == "completed"]
        in_progress = [t for t in trips if t.status == "in_progress"]
        delayed = [t for t in trips if t.status == "delayed"]
        
        print(f"   已完成: {len(completed)}")
        print(f"   运输中: {len(in_progress)}")
        print(f"   晚点: {len(delayed)}")
    
    print(f"\n{'='*60}")
