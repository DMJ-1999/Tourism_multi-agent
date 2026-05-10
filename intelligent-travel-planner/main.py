#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主程序入口 - 智能旅行规划系统"""

import sys
import io

# 设置标准输出编码为UTF-8，解决Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from datetime import date
from data.models import TravelRequest
from orchestration.coordinator import coordinator


def print_banner():
    """打印程序横幅"""
    banner = """
============================================================
                智能旅行规划系统
        Intelligent Travel Planning System

    基于LangChain多智能体架构，为您提供个性化的旅行规划服务
============================================================
"""
    print(banner)


def print_result(result):
    """打印规划结果"""
    print("\n" + "=" * 60)
    print(f"[旅行规划报告] - {result.destination}")
    print("=" * 60)

    print(f"\n目的地: {result.destination}")
    print(f"行程天数: {result.days}天")
    print(f"旅行人数: {result.traveler_count}人")
    print(f"预算: {result.budget:.0f}元")

    print("\n" + "-" * 60)
    print("[费用明细]")
    print("-" * 60)
    if result.itinerary:
        ticket_cost = result.itinerary.get("estimated_ticket_cost", 0)
        print(f"  门票费用: {ticket_cost:.0f}元")

    if result.accommodation:
        accommodation_cost = result.accommodation.get("estimated_cost", 0)
        print(f"  住宿费用: {accommodation_cost:.0f}元")

    if result.transportation:
        transport_cost = result.transportation.get("estimated_cost", 0)
        print(f"  交通费用: {transport_cost:.0f}元")

    print(f"\n  总费用: {result.total_cost:.0f}元")

    if result.is_within_budget:
        remaining = result.budget - result.total_cost
        print(f"  [OK] 预算充足，剩余 {remaining:.0f}元")
    else:
        overspend = result.total_cost - result.budget
        print(f"  [!] 预算超支 {overspend:.0f}元")

    print("\n" + "-" * 60)
    print("[行程安排]")
    print("-" * 60)
    if result.itinerary:
        plan_text = result.itinerary.get("plan", "暂无详细行程")
        if len(plan_text) > 500:
            plan_text = plan_text[:500] + "...(更多内容省略)"
        print(plan_text)

    print("\n" + "-" * 60)
    print("[旅行贴士]")
    print("-" * 60)
    for i, tip in enumerate(result.tips, 1):
        print(f"  {i}. {tip}")

    print("\n" + "=" * 60)
    print("[完成] 规划完成！祝您旅途愉快！")
    print("=" * 60 + "\n")


def main():
    """主函数"""
    print_banner()

    # 示例旅行请求
    # 用户可以根据需要修改这些参数
    request = TravelRequest(
        destination="北京",
        origin="上海",
        start_date=date(2025, 6, 15),
        end_date=date(2025, 6, 18),
        traveler_count=2,
        budget=5000.0,
        preferences={
            "interests": ["历史文化", "美食"],
            "accommodation_type": "舒适型",
            "transport_type": "train",
        },
    )

    print(f"正在为您规划 {request.destination} 的旅行...\n")

    # 执行规划
    result = coordinator.plan_trip(request)

    # 输出结果
    if result.success:
        print_result(result)
    else:
        print("[错误] 规划失败，请检查错误信息：")
        for error in result.errors:
            print(f"  - {error}")


def interactive_mode():
    """交互式模式"""
    print_banner()

    print("请输入您的旅行需求：\n")

    destination = input("目的地城市: ").strip()
    origin = input("出发城市: ").strip() or "北京"

    start_date_str = input("出发日期 (YYYY-MM-DD, 默认30天后): ").strip()
    end_date_str = input("返回日期 (YYYY-MM-DD, 默认出发后4天): ").strip()

    traveler_count = int(input("旅行人数 (默认1人): ").strip() or "1")
    budget = float(input("总预算 (元): ").strip() or "5000")

    # 处理日期
    from datetime import timedelta
    today = date.today()

    if start_date_str:
        start_date = date.fromisoformat(start_date_str)
    else:
        start_date = today + timedelta(days=30)

    if end_date_str:
        end_date = date.fromisoformat(end_date_str)
    else:
        end_date = start_date + timedelta(days=3)

    interests = input("兴趣偏好 (如: 历史文化,美食,自然风光): ").strip()
    preferences = {}
    if interests:
        preferences["interests"] = [i.strip() for i in interests.split(",")]

    # 创建请求
    request = TravelRequest(
        destination=destination,
        origin=origin,
        start_date=start_date,
        end_date=end_date,
        traveler_count=traveler_count,
        budget=budget,
        preferences=preferences,
    )

    print(f"\n正在为您规划 {destination} 的旅行...\n")

    # 执行规划
    result = coordinator.plan_trip(request)

    # 输出结果
    if result.success:
        print_result(result)
    else:
        print("[错误] 规划失败，请检查错误信息：")
        for error in result.errors:
            print(f"  - {error}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "-i":
        interactive_mode()
    else:
        main()
