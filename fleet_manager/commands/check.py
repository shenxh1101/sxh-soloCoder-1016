import os
from datetime import date, datetime
from typing import List, Tuple
from ..models import Vehicle, Driver, Trip, Order
from ..utils import (
    load_vehicles, load_drivers, load_trips,
    load_orders, load_orders_status, print_table
)


def check_inspection(vehicles_file: str, warn_days: int = 30) -> Tuple[List[dict], List[dict]]:
    vehicles = load_vehicles(vehicles_file)
    today = date.today()
    
    expired = []
    expiring = []
    
    for vehicle in vehicles:
        days_left = vehicle.days_until_inspection(today)
        
        if days_left < 0:
            expired.append({
                "vehicle": vehicle,
                "days_overdue": abs(days_left)
            })
        elif days_left <= warn_days:
            expiring.append({
                "vehicle": vehicle,
                "days_left": days_left
            })
    
    return expired, expiring


def check_driver_hours(drivers_file: str, trips_file: str, output_dir: str = ".") -> List[dict]:
    drivers = load_drivers(drivers_file)
    trips = load_trips(trips_file)
    
    today = date.today()
    today_trips = [
        t for t in trips if t.departure_time and t.departure_time.date() == today]
    
    issues = []
    
    driver_hours = {}
    for driver in drivers:
        driver_hours[driver.driver_id] = {
            "driver": driver,
            "scheduled_hours": 0.0,
            "trips": []
        }
    
    for trip in today_trips:
        if trip.driver_id in driver_hours:
            driver_hours[trip.driver_id]["scheduled_hours"] += trip.estimated_hours
            driver_hours[trip.driver_id]["trips"].append(trip)
    
    for driver_id, info in driver_hours.items():
        driver = info["driver"]
        scheduled = info["scheduled_hours"]
        if scheduled > driver.max_daily_hours:
            issues.append({
                "driver": driver,
                "scheduled_hours": scheduled,
                "max_hours": driver.max_daily_hours,
                "overtime": scheduled - driver.max_daily_hours,
                "trips": info["trips"]
            })
    
    return issues


def check_load_capacity(vehicles_file: str, trips_file: str) -> List[dict]:
    vehicles = load_vehicles(vehicles_file)
    trips = load_trips(trips_file)
    
    issues = []
    vehicle_map = {v.plate_number: v for v in vehicles}
    
    for trip in trips:
        vehicle = vehicle_map.get(trip.vehicle_plate)
        if not vehicle:
            continue
        
        weight_over = trip.total_weight - vehicle.max_weight
        volume_over = trip.total_volume - vehicle.max_volume
        
        if weight_over > 0 or volume_over > 0:
            issues.append({
                "trip": trip,
                "vehicle": vehicle,
                "weight_over": max(0, weight_over),
                "volume_over": max(0, volume_over)
            })
    
    return issues


def check_schedule_conflicts(
    trips_file: str,
    output_dir: str = "."
) -> Tuple[List[dict], List[dict]]:
    trips = load_trips(trips_file)
    
    vehicle_conflicts = []
    driver_conflicts = []
    
    from collections import defaultdict
    
    vehicle_trips = defaultdict(list)
    driver_trips = defaultdict(list)
    
    for trip in trips:
        if not trip.departure_time or not trip.arrival_time:
            continue
        trip_date = trip.departure_time.date()
        vehicle_trips[(trip.vehicle_plate, trip_date)].append(trip)
        driver_trips[(trip.driver_id, trip_date)].append(trip)
    
    def find_overlaps(trip_list: List[Trip]) -> List[Tuple[Trip, Trip, str]]:
        overlaps = []
        trip_list.sort(key=lambda t: t.departure_time or datetime.min)
        
        for i in range(len(trip_list)):
            for j in range(i + 1, len(trip_list)):
                t1 = trip_list[i]
                t2 = trip_list[j]
                
                if t1.departure_time and t1.arrival_time and t2.departure_time and t2.arrival_time:
                    if t2.departure_time < t1.arrival_time:
                        overlap_minutes = int((t1.arrival_time - t2.departure_time).total_seconds() / 60)
                        overlaps.append((t1, t2, f"时间重叠 {overlap_minutes} 分钟"))
                    elif (t2.departure_time - t1.arrival_time).total_seconds() < 1800:
                        gap_minutes = int((t2.departure_time - t1.arrival_time).total_seconds() / 60)
                        overlaps.append((t1, t2, f"间隔仅 {gap_minutes} 分钟，建议调整"))
        
        return overlaps
    
    for (vehicle, trip_date), trip_list in vehicle_trips.items():
        overlaps = find_overlaps(trip_list)
        for t1, t2, detail in overlaps:
            vehicle_conflicts.append({
                "type": "车辆排班冲突",
                "vehicle": vehicle,
                "date": trip_date,
                "trip1_id": t1.trip_id,
                "trip1_route": t1.route_key,
                "trip1_departure": t1.departure_time.strftime("%H:%M") if t1.departure_time else "-",
                "trip1_arrival": t1.arrival_time.strftime("%H:%M") if t1.arrival_time else "-",
                "trip2_id": t2.trip_id,
                "trip2_route": t2.route_key,
                "trip2_departure": t2.departure_time.strftime("%H:%M") if t2.departure_time else "-",
                "trip2_arrival": t2.arrival_time.strftime("%H:%M") if t2.arrival_time else "-",
                "detail": detail
            })
    
    for (driver, trip_date), trip_list in driver_trips.items():
        overlaps = find_overlaps(trip_list)
        for t1, t2, detail in overlaps:
            driver_conflicts.append({
                "type": "司机排班冲突",
                "driver": driver,
                "date": trip_date,
                "trip1_id": t1.trip_id,
                "trip1_route": t1.route_key,
                "trip1_departure": t1.departure_time.strftime("%H:%M") if t1.departure_time else "-",
                "trip1_arrival": t1.arrival_time.strftime("%H:%M") if t1.arrival_time else "-",
                "trip2_id": t2.trip_id,
                "trip2_route": t2.route_key,
                "trip2_departure": t2.departure_time.strftime("%H:%M") if t2.departure_time else "-",
                "trip2_arrival": t2.arrival_time.strftime("%H:%M") if t2.arrival_time else "-",
                "detail": detail
            })
    
    return vehicle_conflicts, driver_conflicts


def run_checks(
    vehicles_file: str, drivers_file: str, orders_file: str,
    check_type: str = "all", output_dir: str = "."
) -> None:
    trips_file = os.path.join(output_dir, "trips.json")
    
    print(f"\n{'='*60}")
    print("安全与合规检查")
    print(f"{'='*60}")
    
    has_issues = False
    
    if check_type in ["all", "inspection"]:
        print(f"\n--- 车辆年检检查 ---")
        expired, expiring = check_inspection(vehicles_file)
        
        if expired:
            has_issues = True
            print(f"\n❌ 已过期车辆 ({len(expired)} 辆):")
            rows = []
            for item in expired:
                v = item["vehicle"]
                rows.append([
                    v.plate_number,
                    v.vehicle_type,
                    v.inspection_date.strftime("%Y-%m-%d"),
                    f"已过期{item['days_overdue']}天"
                ])
            print_table(["车牌号", "车型", "年检日期", "状态"], rows)
        else:
            print("✅ 无已过期年检")
        
        if expiring:
            has_issues = True
            print(f"\n⚠️  即将到期车辆 ({len(expiring)} 辆):")
            rows = []
            for item in expiring:
                v = item["vehicle"]
                status = f"剩余{item['days_left']}天"
                if item["days_left"] <= 7:
                    status += " (紧急)"
                rows.append([
                    v.plate_number,
                    v.vehicle_type,
                    v.inspection_date.strftime("%Y-%m-%d"),
                    status
                ])
            print_table(["车牌号", "车型", "年检日期", "剩余天数"], rows)
        else:
            print("✅ 无即将到期年检")
    
    if check_type in ["all", "hours"]:
        print(f"\n--- 司机工时检查 ---")
        issues = check_driver_hours(drivers_file, trips_file, output_dir)
        
        if issues:
            has_issues = True
            print(f"\n⚠️  工时超时长司机 ({len(issues)} 人):")
            rows = []
            for item in issues:
                d = item["driver"]
                rows.append([
                    d.driver_id,
                    d.name,
                    d.phone,
                    f"{item['scheduled_hours']:.1f}h",
                    f"{item['max_hours']:.1f}h",
                    f"+{item['overtime']:.1f}h"
                ])
            print_table(["司机ID", "姓名", "电话", "排班工时", "最大工时", "超时"], rows)
            
            for item in issues:
                print(f"\n📋 {item['driver'].name} 的超时班次:")
                trip_rows = []
                for t in item["trips"]:
                    trip_rows.append([
                        t.trip_id, t.route_key, f"{t.estimated_hours}h"])
                print_table(["班次ID", "路线", "时长"], trip_rows)
        else:
            print("✅ 所有司机工时合规")
    
    if check_type in ["all", "load"]:
        print(f"\n--- 车辆载重检查 ---")
        issues = check_load_capacity(vehicles_file, trips_file)
        
        if issues:
            has_issues = True
            print(f"\n⚠️  超载班次 ({len(issues)} 个):")
            rows = []
            for item in issues:
                t = item["trip"]
                v = item["vehicle"]
                rows.append([
                    t.trip_id,
                    v.plate_number,
                    f"{t.total_weight:.1f}t/{v.max_weight:.1f}t",
                    f"{t.total_volume:.1f}m³/{v.max_volume:.1f}m³",
                    f"+{item['weight_over']:.1f}t" if item["weight_over"] > 0 else "-",
                    f"+{item['volume_over']:.1f}m³" if item["volume_over"] > 0 else "-"
                ])
            print_table(
                ["班次ID", "车牌号", "载重/限重", "体积/限制", "载重超限", "体积超限"],
                rows
            )
        else:
            print("✅ 所有班次载重合规")
    
    if check_type in ["all", "schedule"]:
        print(f"\n--- 排班冲突检查 ---")
        vehicle_conflicts, driver_conflicts = check_schedule_conflicts(trips_file, output_dir)
        
        if vehicle_conflicts or driver_conflicts:
            has_issues = True
            
            if vehicle_conflicts:
                print(f"\n⚠️  车辆排班冲突 ({len(vehicle_conflicts)} 处):")
                rows = []
                for c in vehicle_conflicts:
                    rows.append([
                        c["vehicle"],
                        c["date"].strftime("%Y-%m-%d"),
                        f"{c['trip1_id']}\n{c['trip2_id']}",
                        f"{c['trip1_departure']}-{c['trip1_arrival']}\n{c['trip2_departure']}-{c['trip2_arrival']}",
                        f"{c['trip1_route']}\n{c['trip2_route']}",
                        c["detail"]
                    ])
                print_table(
                    ["车牌号", "日期", "班次ID", "时间段", "路线", "问题说明"],
                    rows
                )
            
            if driver_conflicts:
                print(f"\n⚠️  司机排班冲突 ({len(driver_conflicts)} 处):")
                rows = []
                for c in driver_conflicts:
                    rows.append([
                        c["driver"],
                        c["date"].strftime("%Y-%m-%d"),
                        f"{c['trip1_id']}\n{c['trip2_id']}",
                        f"{c['trip1_departure']}-{c['trip1_arrival']}\n{c['trip2_departure']}-{c['trip2_arrival']}",
                        f"{c['trip1_route']}\n{c['trip2_route']}",
                        c["detail"]
                    ])
                print_table(
                    ["司机ID", "日期", "班次ID", "时间段", "路线", "问题说明"],
                    rows
                )
        else:
            print("✅ 无排班冲突")
    
    if check_type == "all":
        print(f"\n{'='*60}")
        if has_issues:
            print("⚠️  发现需要关注上述问题！")
        else:
            print("✅ 所有检查通过！")
        print(f"{'='*60}")


def check_vehicle(plate_number: str, vehicles_file: str, trips_file: str, orders_file: str, output_dir: str = ".") -> None:
    vehicles = load_vehicles(vehicles_file)
    trips = load_trips(trips_file)
    orders = load_orders(orders_file)
    
    orders_status_file = os.path.join(output_dir, "orders_status.json")
    orders = load_orders_status(orders_status_file, orders)
    
    vehicle = next((v for v in vehicles if v.plate_number == plate_number), None)
    
    if not vehicle:
        print(f"❌ 未找到车辆 {plate_number}")
        return
    
    today = date.today()
    days_left = vehicle.days_until_inspection(today)
    
    print(f"\n{'='*60}")
    print(f"车辆详情 - {plate_number}")
    print(f"{'='*60}")
    
    info_rows = [
        ["车型", vehicle.vehicle_type],
        ["载重限制", f"{vehicle.max_weight}t"],
        ["体积限制", f"{vehicle.max_volume}m³"],
        ["油耗", f"{vehicle.fuel_consumption}L/100km"],
        ["当前位置", vehicle.current_location],
        ["状态", vehicle.status],
        ["年检日期", vehicle.inspection_date.strftime("%Y-%m-%d")],
        ["年检状态",
            "✅ 正常" if days_left > 30 else
            (f"⚠️  剩余{days_left}天" if days_left >= 0 else
            f"❌ 已过期{abs(days_left)}天")]
    ]
    print_table(["项目", "值"], info_rows)
    
    vehicle_trips = [t for t in trips if t.vehicle_plate == plate_number]
    if vehicle_trips:
        print(f"\n📋 运输记录 ({len(vehicle_trips)} 个班次:")
        rows = []
        for trip in vehicle_trips:
            trip_orders = [o for o in orders if o.order_id in trip.orders]
            customer_list = ", ".join([o.customer for o in trip_orders[:2]])
            if len(trip_orders) > 2:
                customer_list += f" 等"
            status_map = {
                "planned": "⏳ 待出发",
                "in_progress": "🚚 运输中",
                "completed": "✅ 已完成",
                "delayed": "⚠️  晚点"
            }
            rows.append([
                trip.trip_id,
                trip.route_key,
                customer_list,
                f"{len(trip.orders)}单",
                f"{trip.total_weight:.1f}t",
                status_map.get(trip.status, trip.status)
            ])
        print_table(
            ["班次ID", "路线", "客户", "订单数", "载重", "状态"],
            rows
        )
    else:
        print("\n该车辆暂无运输记录")
