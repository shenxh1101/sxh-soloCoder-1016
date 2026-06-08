import argparse
import sys
import os
from datetime import date

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from .commands.plan import generate_plan, show_plan
from .commands.check import run_checks, check_vehicle
from .commands.cost import run_cost_analysis
from .commands.delay import run_delay_command
from .commands.report import run_report


def main():
    parser = argparse.ArgumentParser(
        description="公路运输调度管理工具 - 快速核算班次、车辆和司机安排",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令示例:
  生成运输计划:
    python -m fleet_manager.main plan --orders data/orders.csv --vehicles data/vehicles.csv --drivers data/drivers.csv
  
  查看当前计划:
    python -m fleet_manager.main plan --show
  
  安全合规检查:
    python -m fleet_manager.main check --type all
    python -m fleet_manager.main check --type inspection
    python -m fleet_manager.main check --type schedule
    python -m fleet_manager.main check --vehicle 京A12345
  
  成本分析:
    python -m fleet_manager.main cost --mode trips
    python -m fleet_manager.main cost --mode route --origin 北京 --destination 上海
    python -m fleet_manager.main cost --mode order
  
  调度管理:
    python -m fleet_manager.main delay --action query --vehicle 京A12345
    python -m fleet_manager.main delay --action history --trip T0001
    python -m fleet_manager.main delay --action depart --trip T0001
    python -m fleet_manager.main delay --action arrive --trip T0001
    python -m fleet_manager.main delay --action complete --trip T0001
    python -m fleet_manager.main delay --action depart --trip T0001 --actual-time "2026-06-08 08:30:00"
    python -m fleet_manager.main delay --action reassign --trip T0001 --new-vehicle 京B67890 --reason "车辆故障"
    python -m fleet_manager.main delay --action delay --trip T0001 --minutes 30 --reason "交通拥堵"
    python -m fleet_manager.main delay --action simulate --trip T0001 --minutes 60
  
  报表生成:
    python -m fleet_manager.main report --type daily
    python -m fleet_manager.main report --type dashboard
    python -m fleet_manager.main report --type anomaly
    python -m fleet_manager.main report --type driver --driver D001
    python -m fleet_manager.main report --type all
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    plan_parser = subparsers.add_parser("plan", help="生成运输计划")
    plan_parser.add_argument("--orders", default="data/orders.csv", help="订单数据文件路径")
    plan_parser.add_argument("--vehicles", default="data/vehicles.csv", help="车辆数据文件路径")
    plan_parser.add_argument("--drivers", default="data/drivers.csv", help="司机数据文件路径")
    plan_parser.add_argument("--show", action="store_true", help="查看当前运输计划")
    plan_parser.add_argument("--output-dir", default=".", help="输出目录")
    
    check_parser = subparsers.add_parser("check", help="安全合规检查")
    check_parser.add_argument("--type", default="all", choices=["all", "inspection", "hours", "load", "schedule"], help="检查类型")
    check_parser.add_argument("--orders", default="data/orders.csv", help="订单数据文件路径")
    check_parser.add_argument("--vehicles", default="data/vehicles.csv", help="车辆数据文件路径")
    check_parser.add_argument("--drivers", default="data/drivers.csv", help="司机数据文件路径")
    check_parser.add_argument("--vehicle", help="查询指定车辆详情")
    check_parser.add_argument("--output-dir", default=".", help="输出目录")
    
    cost_parser = subparsers.add_parser("cost", help="成本分析")
    cost_parser.add_argument("--mode", default="trips", choices=["trips", "route", "order", "all"], help="成本分析模式")
    cost_parser.add_argument("--origin", help="起点城市（route模式）")
    cost_parser.add_argument("--destination", help="终点城市（route模式）")
    cost_parser.add_argument("--orders", default="data/orders.csv", help="订单数据文件路径")
    cost_parser.add_argument("--vehicles", default="data/vehicles.csv", help="车辆数据文件路径")
    cost_parser.add_argument("--output-dir", default=".", help="输出目录")
    
    delay_parser = subparsers.add_parser("delay", help="调度管理（流水账/出发/到达/完成/改派/晚点/查询）")
    delay_parser.add_argument("--action", default="query", choices=["query", "history", "depart", "arrive", "complete", "reassign", "delay", "simulate"], help="操作类型")
    delay_parser.add_argument("--trip", help="班次ID")
    delay_parser.add_argument("--vehicle", help="车牌号")
    delay_parser.add_argument("--new-vehicle", help="新车牌号（reassign模式）")
    delay_parser.add_argument("--new-driver", help="新司机ID（reassign模式）")
    delay_parser.add_argument("--minutes", type=int, default=0, help="晚点分钟数（delay/simulate模式）")
    delay_parser.add_argument("--reason", default="", help="原因说明")
    delay_parser.add_argument("--actual-time", help="实际时间（补录历史数据，格式：YYYY-MM-DD HH:MM:SS）")
    delay_parser.add_argument("--orders", default="data/orders.csv", help="订单数据文件路径")
    delay_parser.add_argument("--vehicles", default="data/vehicles.csv", help="车辆数据文件路径")
    delay_parser.add_argument("--drivers", default="data/drivers.csv", help="司机数据文件路径")
    delay_parser.add_argument("--output-dir", default=".", help="输出目录")
    
    report_parser = subparsers.add_parser("report", help="生成报表")
    report_parser.add_argument("--type", default="daily", choices=["daily", "dashboard", "anomaly", "driver", "all"], help="报表类型")
    report_parser.add_argument("--driver", help="司机ID（driver模式）")
    report_parser.add_argument("--orders", default="data/orders.csv", help="订单数据文件路径")
    report_parser.add_argument("--vehicles", default="data/vehicles.csv", help="车辆数据文件路径")
    report_parser.add_argument("--drivers", default="data/drivers.csv", help="司机数据文件路径")
    report_parser.add_argument("--output-dir", default=".", help="输出目录")
    report_parser.add_argument("--no-save", action="store_true", help="不保存到文件，仅显示")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == "plan":
            if args.show:
                show_plan(args.output_dir)
            else:
                if not os.path.exists(args.orders):
                    print(f"❌ 订单文件不存在: {args.orders}")
                    print("请先准备数据文件，或使用 --help 查看示例数据创建方法。")
                    sys.exit(1)
                if not os.path.exists(args.vehicles):
                    print(f"❌ 车辆文件不存在: {args.vehicles}")
                    sys.exit(1)
                if not os.path.exists(args.drivers):
                    print(f"❌ 司机文件不存在: {args.drivers}")
                    sys.exit(1)
                generate_plan(args.orders, args.vehicles, args.drivers, args.output_dir)
        
        elif args.command == "check":
            if args.vehicle:
                trips_file = os.path.join(args.output_dir, "trips.json")
                check_vehicle(args.vehicle, args.vehicles, trips_file, args.orders, args.output_dir)
            else:
                run_checks(args.vehicles, args.drivers, args.orders, args.type, args.output_dir)
        
        elif args.command == "cost":
            run_cost_analysis(args.vehicles, args.orders, args.mode, args.origin, args.destination, args.output_dir)
        
        elif args.command == "delay":
            run_delay_command(
                args.action,
                trip_id=args.trip,
                vehicle_plate=args.vehicle,
                new_vehicle=args.new_vehicle,
                new_driver=args.new_driver,
                delay_minutes=args.minutes,
                reason=args.reason,
                actual_time=args.actual_time,
                vehicles_file=args.vehicles,
                drivers_file=args.drivers,
                orders_file=args.orders,
                output_dir=args.output_dir
            )
        
        elif args.command == "report":
            run_report(
                args.type,
                args.vehicles,
                args.drivers,
                args.orders,
                driver_id=args.driver,
                output_dir=args.output_dir,
                save_to_file=not args.no_save
            )
    
    except FileNotFoundError as e:
        print(f"❌ 文件未找到: {e}")
        print("请确保数据文件路径正确，或先创建示例数据。")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
