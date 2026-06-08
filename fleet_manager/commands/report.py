import os
from datetime import date, datetime
from typing import List, Dict, Tuple
from ..models import Trip, Vehicle, Driver, Order, DailyReport
from ..utils import (
    load_trips, load_vehicles, load_drivers, load_orders,
    load_orders_status, print_table
)


def generate_driver_manifest(
    driver_id: str,
    drivers_file: str,
    vehicles_file: str,
    orders_file: str,
    output_dir: str = ".",
    report_date: date | None = None
) -> str:
    report_date = report_date or date.today()
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    drivers = load_drivers(drivers_file)
    vehicles = load_vehicles(vehicles_file)
    orders = load_orders(orders_file)
    
    orders_status_file = os.path.join(output_dir, "orders_status.json")
    orders = load_orders_status(orders_status_file, orders)
    
    driver = next((d for d in drivers if d.driver_id == driver_id), None)
    if not driver:
        return f"❌ 未找到司机 {driver_id}"
    
    driver_trips = [
        t for t in trips
        if t.driver_id == driver_id
        and t.departure_time
        and t.departure_time.date() == report_date
    ]
    driver_trips.sort(key=lambda t: t.departure_time or datetime.min)
    
    if not driver_trips:
        return f"ℹ️  司机 {driver.name}({driver_id}) {report_date.strftime('%Y-%m-%d')} 无任务"
    
    vehicle_map = {v.plate_number: v for v in vehicles}
    
    manifest_lines = []
    manifest_lines.append("=" * 70)
    manifest_lines.append("司 机 路 单")
    manifest_lines.append("=" * 70)
    manifest_lines.append(f"日期: {report_date.strftime('%Y年%m月%d日')}")
    manifest_lines.append(f"司机: {driver.name}")
    manifest_lines.append(f"工号: {driver.driver_id}")
    manifest_lines.append(f"联系电话: {driver.phone}")
    manifest_lines.append("")
    
    total_distance = 0.0
    total_hours = 0.0
    total_orders = 0
    
    for idx, trip in enumerate(driver_trips, 1):
        vehicle = vehicle_map.get(trip.vehicle_plate)
        trip_orders = [o for o in orders if o.order_id in trip.orders]
        
        manifest_lines.append(f"【班次 {idx}】")
        manifest_lines.append(f"  班次ID: {trip.trip_id}")
        manifest_lines.append(f"  车牌: {trip.vehicle_plate}")
        if vehicle:
            manifest_lines.append(f"  车型: {vehicle.vehicle_type}")
        manifest_lines.append(f"  路线: {trip.origin} → {trip.destination}")
        manifest_lines.append(f"  里程: {trip.estimated_distance}km")
        manifest_lines.append(f"  预计时长: {trip.estimated_hours}小时")
        
        if trip.departure_time:
            manifest_lines.append(f"  发车时间: {trip.departure_time.strftime('%H:%M')}")
        if trip.arrival_time:
            manifest_lines.append(f"  预计到达: {trip.arrival_time.strftime('%H:%M')}")
        
        manifest_lines.append(f"  载重: {trip.total_weight:.1f}t / 体积: {trip.total_volume:.1f}m³")
        manifest_lines.append("")
        manifest_lines.append(f"  配送订单 ({len(trip_orders)}个):")
        
        for o in trip_orders:
            manifest_lines.append(f"    - {o.order_id} | {o.customer} | {o.cargo}")
            manifest_lines.append(f"      {o.weight}t / {o.volume}m³ | 送达截止: {o.delivery_deadline.strftime('%H:%M')}")
        
        if trip.reassigned:
            manifest_lines.append(f"  ⚠️  临时改派")
        if trip.delay_minutes > 0:
            manifest_lines.append(f"  ⚠️  晚点 {trip.delay_minutes} 分钟")
        if trip.notes:
            last_note = trip.notes.split("\n")[-1]
            manifest_lines.append(f"  备注: {last_note}")
        
        manifest_lines.append("")
        
        total_distance += trip.estimated_distance
        total_hours += trip.estimated_hours
        total_orders += len(trip_orders)
    
    manifest_lines.append("-" * 70)
    manifest_lines.append("当日汇总")
    manifest_lines.append(f"  班次数量: {len(driver_trips)}")
    manifest_lines.append(f"  订单总数: {total_orders}")
    manifest_lines.append(f"  总里程: {total_distance:.0f}km")
    manifest_lines.append(f"  预计工时: {total_hours:.1f}h / 最大工时: {driver.max_daily_hours}h")
    
    overtime = total_hours - driver.max_daily_hours
    if overtime > 0:
        manifest_lines.append(f"  ⚠️  预计超时: {overtime:.1f}h")
    else:
        manifest_lines.append(f"  剩余工时: {driver.max_daily_hours - total_hours:.1f}h")
    
    manifest_lines.append("=" * 70)
    
    return "\n".join(manifest_lines)


def generate_anomaly_list(
    vehicles_file: str,
    drivers_file: str,
    orders_file: str,
    output_dir: str = ".",
    report_date: date | None = None
) -> Tuple[str, List[Dict]]:
    report_date = report_date or date.today()
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    vehicles = load_vehicles(vehicles_file)
    drivers = load_drivers(drivers_file)
    orders = load_orders(orders_file)
    
    orders_status_file = os.path.join(output_dir, "orders_status.json")
    orders = load_orders_status(orders_status_file, orders)
    
    anomalies = []
    
    for trip in trips:
        if trip.delay_minutes > 0:
            anomalies.append({
                "type": "晚点",
                "trip_id": trip.trip_id,
                "vehicle": trip.vehicle_plate,
                "driver": trip.driver_id,
                "route": trip.route_key,
                "detail": f"晚点 {trip.delay_minutes} 分钟",
                "severity": "高" if trip.delay_minutes > 60 else "中"
            })
        
        if trip.reassigned:
            anomalies.append({
                "type": "临时改派",
                "trip_id": trip.trip_id,
                "vehicle": trip.vehicle_plate,
                "driver": trip.driver_id,
                "route": trip.route_key,
                "detail": "车辆或司机临时调整",
                "severity": "中"
            })
        
        vehicle = next((v for v in vehicles if v.plate_number == trip.vehicle_plate), None)
        if vehicle:
            weight_over = trip.total_weight - vehicle.max_weight
            volume_over = trip.total_volume - vehicle.max_volume
            if weight_over > 0 or volume_over > 0:
                detail_parts = []
                if weight_over > 0:
                    detail_parts.append(f"载重超{weight_over:.1f}t")
                if volume_over > 0:
                    detail_parts.append(f"体积超{volume_over:.1f}m³")
                anomalies.append({
                    "type": "超载",
                    "trip_id": trip.trip_id,
                    "vehicle": trip.vehicle_plate,
                    "driver": trip.driver_id,
                    "route": trip.route_key,
                    "detail": ", ".join(detail_parts),
                    "severity": "高"
                })
        
        if trip.status == "delayed" and trip.arrival_time:
            trip_orders = [o for o in orders if o.order_id in trip.orders]
            for order in trip_orders:
                if trip.arrival_time > order.delivery_deadline:
                    delay_hours = (trip.arrival_time - order.delivery_deadline).total_seconds() / 3600
                    anomalies.append({
                        "type": "交付超时",
                        "trip_id": trip.trip_id,
                        "vehicle": trip.vehicle_plate,
                        "driver": trip.driver_id,
                        "route": trip.route_key,
                        "detail": f"订单 {order.order_id} 预计超时 {delay_hours:.1f}h",
                        "severity": "高"
                    })
    
    for vehicle in vehicles:
        days_left = vehicle.days_until_inspection(report_date)
        if days_left < 0:
            anomalies.append({
                "type": "年检过期",
                "trip_id": "-",
                "vehicle": vehicle.plate_number,
                "driver": "-",
                "route": "-",
                "detail": f"年检已过期 {abs(days_left)} 天",
                "severity": "高"
            })
        elif days_left <= 7:
            anomalies.append({
                "type": "年检临期",
                "trip_id": "-",
                "vehicle": vehicle.plate_number,
                "driver": "-",
                "route": "-",
                "detail": f"年检剩余 {days_left} 天",
                "severity": "中"
            })
    
    today_trips = [t for t in trips if t.departure_time and t.departure_time.date() == report_date]
    driver_hours = {}
    for trip in today_trips:
        if trip.driver_id not in driver_hours:
            driver_hours[trip.driver_id] = 0.0
        driver_hours[trip.driver_id] += trip.estimated_hours
    
    for driver in drivers:
        scheduled = driver_hours.get(driver.driver_id, 0)
        if scheduled > driver.max_daily_hours:
            anomalies.append({
                "type": "工时超时",
                "trip_id": "-",
                "vehicle": "-",
                "driver": driver.driver_id,
                "route": "-",
                "detail": f"司机 {driver.name} 排班 {scheduled:.1f}h，超时 {scheduled - driver.max_daily_hours:.1f}h",
                "severity": "中"
            })
    
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("异 常 清 单")
    report_lines.append("=" * 80)
    report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"异常总数: {len(anomalies)}")
    report_lines.append("")
    
    if anomalies:
        high = [a for a in anomalies if a["severity"] == "高"]
        medium = [a for a in anomalies if a["severity"] == "中"]
        report_lines.append(f"🔴 高危异常: {len(high)} 个")
        report_lines.append(f"🟡 中等异常: {len(medium)} 个")
        report_lines.append("")
        
        rows = []
        for a in sorted(anomalies, key=lambda x: {"高": 0, "中": 1, "低": 2}[x["severity"]]):
            severity_icon = "🔴" if a["severity"] == "高" else "🟡"
            rows.append([
                severity_icon + " " + a["type"],
                a["trip_id"],
                a["vehicle"],
                a["driver"],
                a["route"],
                a["detail"]
            ])
        
        col_widths = [12, 10, 12, 10, 20, 40]
        header = "|" + "|".join(f" {h:<{col_widths[i]}} " for i, h in enumerate(["类型", "班次", "车辆", "司机", "路线", "详情"])) + "|"
        separator = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"
        
        report_lines.append(separator)
        report_lines.append(header)
        report_lines.append(separator)
        for row in rows:
            report_lines.append("|" + "|".join(f" {str(cell):<{col_widths[i]}} " for i, cell in enumerate(row)) + "|")
        report_lines.append(separator)
    else:
        report_lines.append("✅ 无异常记录")
    
    report_lines.append("")
    report_lines.append("=" * 80)
    
    return "\n".join(report_lines), anomalies


def generate_daily_report(
    vehicles_file: str,
    drivers_file: str,
    orders_file: str,
    output_dir: str = ".",
    report_date: date | None = None
) -> Tuple[str, DailyReport]:
    report_date = report_date or date.today()
    trips_file = os.path.join(output_dir, "trips.json")
    trips = load_trips(trips_file)
    vehicles = load_vehicles(vehicles_file)
    drivers = load_drivers(drivers_file)
    orders = load_orders(orders_file)
    
    orders_status_file = os.path.join(output_dir, "orders_status.json")
    orders = load_orders_status(orders_status_file, orders)
    
    today_trips = [t for t in trips if t.departure_time and t.departure_time.date() == report_date]
    
    report = DailyReport(report_date=report_date)
    report.total_trips = len(today_trips)
    report.completed_trips = len([t for t in today_trips if t.status == "completed"])
    report.delayed_trips = len([t for t in today_trips if t.delay_minutes > 0])
    report.reassigned_trips = len([t for t in today_trips if t.reassigned])
    
    total_orders = 0
    total_cost = 0.0
    total_distance = 0.0
    
    for trip in today_trips:
        total_orders += len(trip.orders)
        total_cost += trip.total_cost
        total_distance += trip.estimated_distance
    
    report.total_orders = total_orders
    report.total_cost = total_cost
    report.total_revenue = total_cost * 1.5
    
    _, anomalies = generate_anomaly_list(vehicles_file, drivers_file, orders_file, output_dir, report_date)
    report.anomalies = [f"{a['type']}: {a['detail']}" for a in anomalies]
    
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("每 日 运 营 汇 总 报 告")
    report_lines.append("=" * 70)
    report_lines.append(f"报告日期: {report_date.strftime('%Y年%m月%d日')}")
    report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    
    report_lines.append("【运营概览】")
    report_lines.append(f"  总班次: {report.total_trips}")
    report_lines.append(f"  已完成: {report.completed_trips}")
    report_lines.append(f"  运输中: {len([t for t in today_trips if t.status == 'in_progress'])}")
    report_lines.append(f"  待出发: {len([t for t in today_trips if t.status == 'planned'])}")
    report_lines.append(f"  晚点班次: {report.delayed_trips}")
    report_lines.append(f"  临时改派: {report.reassigned_trips}")
    report_lines.append(f"  配送订单: {report.total_orders} 个")
    report_lines.append("")
    
    report_lines.append("【运力使用】")
    used_vehicles = {t.vehicle_plate for t in today_trips}
    used_drivers = {t.driver_id for t in today_trips}
    report_lines.append(f"  投入车辆: {len(used_vehicles)} / {len(vehicles)} 辆")
    report_lines.append(f"  出勤司机: {len(used_drivers)} / {len(drivers)} 人")
    report_lines.append(f"  总行驶里程: {total_distance:.0f} km")
    report_lines.append("")
    
    report_lines.append("【财务概览】")
    report_lines.append(f"  预估总收入: ¥{report.total_revenue:.2f}")
    report_lines.append(f"  预估总成本: ¥{report.total_cost:.2f}")
    report_lines.append(f"  预估利润: ¥{report.total_revenue - report.total_cost:.2f}")
    report_lines.append(f"  利润率: {(report.total_revenue - report.total_cost) / report.total_revenue * 100:.1f}%")
    report_lines.append("")
    
    if report.anomalies:
        report_lines.append(f"【异常记录】共 {len(report.anomalies)} 项")
        for i, anomaly in enumerate(report.anomalies, 1):
            report_lines.append(f"  {i}. {anomaly}")
        report_lines.append("")
    
    if today_trips:
        report_lines.append("【班次明细】")
        rows = []
        for trip in sorted(today_trips, key=lambda t: t.departure_time or datetime.min):
            driver = next((d for d in drivers if d.driver_id == trip.driver_id), None)
            driver_name = driver.name if driver else trip.driver_id
            
            status_map = {
                "planned": "⏳ 待出发",
                "in_progress": "🚚 运输中",
                "completed": "✅ 已完成",
                "delayed": "⚠️  晚点"
            }
            status = status_map.get(trip.status, trip.status)
            
            if trip.delay_minutes > 0:
                status += f" (晚{trip.delay_minutes}分)"
            if trip.reassigned:
                status += " (改派)"
            
            rows.append([
                trip.trip_id,
                trip.vehicle_plate,
                driver_name,
                trip.route_key,
                f"{len(trip.orders)}单",
                f"{trip.estimated_distance}km",
                trip.departure_time.strftime("%H:%M") if trip.departure_time else "-",
                status,
                f"¥{trip.total_cost:.2f}"
            ])
        
        col_widths = [10, 12, 10, 20, 8, 10, 8, 16, 12]
        headers = ["班次ID", "车牌号", "司机", "路线", "订单数", "里程", "发车", "状态", "费用"]
        separator = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"
        header_line = "|" + "|".join(f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)) + "|"
        
        report_lines.append(separator)
        report_lines.append(header_line)
        report_lines.append(separator)
        for row in rows:
            report_lines.append("|" + "|".join(f" {str(cell):<{col_widths[i]}} " for i, cell in enumerate(row)) + "|")
        report_lines.append(separator)
    
    report_lines.append("")
    report_lines.append("=" * 70)
    report_lines.append("报告结束")
    report_lines.append("=" * 70)
    
    return "\n".join(report_lines), report


def run_report(
    report_type: str,
    vehicles_file: str,
    drivers_file: str,
    orders_file: str,
    driver_id: str | None = None,
    output_dir: str = ".",
    save_to_file: bool = True
) -> None:
    report_date = date.today()
    
    if report_type == "driver" and driver_id:
        print(f"\n📄 生成司机路单...")
        manifest = generate_driver_manifest(driver_id, drivers_file, vehicles_file, orders_file, output_dir, report_date)
        print()
        print(manifest)
        
        if save_to_file:
            filename = f"driver_manifest_{driver_id}_{report_date.strftime('%Y%m%d')}.txt"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(manifest)
            print(f"\n💾 路单已保存至: {filepath}")
    
    elif report_type == "anomaly":
        print(f"\n📄 生成异常清单...")
        anomaly_report, _ = generate_anomaly_list(vehicles_file, drivers_file, orders_file, output_dir, report_date)
        print()
        print(anomaly_report)
        
        if save_to_file:
            filename = f"anomaly_report_{report_date.strftime('%Y%m%d')}.txt"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(anomaly_report)
            print(f"\n💾 异常清单已保存至: {filepath}")
    
    elif report_type == "daily":
        print(f"\n📄 生成每日汇总报告...")
        daily_report, _ = generate_daily_report(vehicles_file, drivers_file, orders_file, output_dir, report_date)
        print()
        print(daily_report)
        
        if save_to_file:
            filename = f"daily_report_{report_date.strftime('%Y%m%d')}.txt"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(daily_report)
            print(f"\n💾 日报已保存至: {filepath}")
    
    elif report_type == "all":
        print(f"\n📄 生成全套报表...")
        report_date = date.today()
        
        daily_report, _ = generate_daily_report(vehicles_file, drivers_file, orders_file, output_dir, report_date)
        anomaly_report, anomalies = generate_anomaly_list(vehicles_file, drivers_file, orders_file, output_dir, report_date)
        
        print()
        print(daily_report)
        print()
        print(anomaly_report)
        
        if save_to_file:
            daily_file = f"daily_report_{report_date.strftime('%Y%m%d')}.txt"
            anomaly_file = f"anomaly_report_{report_date.strftime('%Y%m%d')}.txt"
            
            with open(os.path.join(output_dir, daily_file), 'w', encoding='utf-8') as f:
                f.write(daily_report)
            with open(os.path.join(output_dir, anomaly_file), 'w', encoding='utf-8') as f:
                f.write(anomaly_report)
            
            print(f"\n💾 报表已保存:")
            print(f"   - {daily_file}")
            print(f"   - {anomaly_file}")
            
            drivers = load_drivers(drivers_file)
            trips_file = os.path.join(output_dir, "trips.json")
            trips = load_trips(trips_file)
            today_drivers = {t.driver_id for t in trips if t.departure_time and t.departure_time.date() == report_date}
            
            for d_id in today_drivers:
                manifest = generate_driver_manifest(d_id, drivers_file, vehicles_file, orders_file, output_dir, report_date)
                manifest_file = f"driver_manifest_{d_id}_{report_date.strftime('%Y%m%d')}.txt"
                with open(os.path.join(output_dir, manifest_file), 'w', encoding='utf-8') as f:
                    f.write(manifest)
                print(f"   - {manifest_file}")
