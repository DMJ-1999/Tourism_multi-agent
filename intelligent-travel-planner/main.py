#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主程序入口 - 智能旅行规划系统。

用法:
    python main.py              # 经典模式（默认示例）
    python main.py -i           # 经典模式（交互式）
    python main.py --unified    # 统一模式（五大模块协同）
    python main.py --unified -i # 统一模式（交互式）
"""

import sys
import io

# 设置标准输出编码为UTF-8，解决Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from datetime import date, timedelta
from data.models import TravelRequest


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


def print_classic_result(result):
    """打印经典模式规划结果。"""
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

    if result.food:
        food_cost = result.food.get("estimated_cost", 0)
        print(f"  餐饮费用: {food_cost:.0f}元")

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


def print_unified_result(result):
    """打印统一模式规划结果（含五大模块信息）。"""
    print("\n" + "=" * 60)
    print(f"[统一旅行规划报告] - {result.destination}")
    print("=" * 60)

    print(f"\n目的地: {result.destination}")
    print(f"行程天数: {result.days}天")
    print(f"旅行人数: {result.traveler_count}人")
    print(f"预算: {result.budget:.0f}元")
    print(f"消费档次: {result.preference_level}")

    # 模块执行日志
    print("\n" + "-" * 60)
    print("[五大模块执行追踪]")
    print("-" * 60)
    for log_entry in result.execution_log:
        print(f"  {log_entry}")

    # 费用明细
    print("\n" + "-" * 60)
    print("[费用明细]")
    print("-" * 60)
    if result.itinerary:
        ticket_cost = result.itinerary.get("estimated_ticket_cost", 0)
        print(f"  门票费用: {ticket_cost:.0f}元")
    if result.accommodation:
        accommodation_cost = result.accommodation.get("estimated_cost", 0)
        print(f"  住宿费用: {accommodation_cost:.0f}元")
    if result.food:
        food_cost = result.food.get("estimated_cost", 0)
        print(f"  餐饮费用: {food_cost:.0f}元")
    # 餐饮费用从总费用反推
    known = (result.itinerary.get("estimated_ticket_cost", 0)
             + result.accommodation.get("estimated_cost", 0)
             + result.food.get("estimated_cost", 0))
    food_cost = max(0, result.total_cost - known)
    print(f"  餐饮费用: {food_cost:.0f}元")

    print(f"\n  总费用: {result.total_cost:.0f}元")
    if result.is_within_budget:
        remaining = result.budget - result.total_cost
        print(f"  [OK] 预算充足，剩余 {remaining:.0f}元")
    else:
        overspend = result.total_cost - result.budget
        print(f"  [!] 预算超支 {overspend:.0f}元")

    # 质量评估
    if result.evaluation:
        print("\n" + "-" * 60)
        print("[结果评估模块] 方案质量评估")
        print("-" * 60)
        eval_report = result.evaluation
        print(f"  综合评分: {eval_report.overall_score}/100 ({eval_report.grade})")
        print(f"  预算效率: {eval_report.budget_efficiency}/100")
        print(f"  行程可行性: {eval_report.schedule_feasibility}/100")
        print(f"  兴趣覆盖: {eval_report.interest_coverage}/100")
        print(f"  地理连贯性: {eval_report.geographic_coherence}/100")
        print(f"  约束满足: {eval_report.constraint_satisfaction}/100")
        if eval_report.issues:
            print(f"  问题: {', '.join(eval_report.issues[:3])}")
        if eval_report.suggestions:
            print(f"  建议: {', '.join(eval_report.suggestions[:3])}")

    # 工具调用统计
    if hasattr(result, 'execution_plan') and result.execution_plan:
        plan = result.execution_plan
        print(f"\n[规划模块] 共 {len(plan.tasks)} 个子任务, {len(plan.execution_order)} 个执行层级")

    # 修订记录
    if result.revision_count > 0:
        print(f"\n[修订] 预算修订 {result.revision_count} 次")
        if hasattr(result, "savings_tips") and result.savings_tips:
            for tip in result.savings_tips:
                print(f"  - {tip}")

    print("\n" + "-" * 60)
    print("[旅行贴士]")
    print("-" * 60)
    for i, tip in enumerate(result.tips, 1):
        print(f"  {i}. {tip}")

    print("\n" + "=" * 60)
    print("[完成] 五大模块协同规划完成！祝您旅途愉快！")
    print("=" * 60 + "\n")


def build_sample_request():
    """构建示例旅行请求。"""
    return TravelRequest(
        destination="北京",
        origin="上海",
        start_date=date(2025, 6, 15),
        end_date=date(2025, 6, 18),
        traveler_count=2,
        budget=5000.0,
        preferences={
            "interests": ["历史文化", "美食"],
            "preference_level": "舒适型",
            "transport_type": "train",
        },
    )


def build_interactive_request():
    """交互式构建旅行请求。"""
    print("请输入您的旅行需求：\n")

    destination = input("目的地城市: ").strip()
    origin = input("出发城市: ").strip() or "北京"

    start_date_str = input("出发日期 (YYYY-MM-DD, 默认30天后): ").strip()
    end_date_str = input("返回日期 (YYYY-MM-DD, 默认出发后4天): ").strip()

    traveler_count = int(input("旅行人数 (默认1人): ").strip() or "1")
    budget = float(input("总预算 (元): ").strip() or "5000")

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
    preferences: dict = {}
    if interests:
        preferences["interests"] = [i.strip() for i in interests.split(",")]

    pref_level = input("消费档次 (经济型/舒适型/高档型/豪华型, 默认舒适型): ").strip() or "舒适型"
    preferences["preference_level"] = pref_level

    return TravelRequest(
        destination=destination,
        origin=origin,
        start_date=start_date,
        end_date=end_date,
        traveler_count=traveler_count,
        budget=budget,
        preferences=preferences,
    )


def run_classic(interactive: bool = False):
    """经典模式 —— 使用原始 TravelPlanningCoordinator。"""
    from orchestration.coordinator import coordinator

    print_banner()
    request = build_interactive_request() if interactive else build_sample_request()
    print(f"\n[经典模式] 正在为您规划 {request.destination} 的旅行...\n")
    result = coordinator.plan_trip(request)

    if result.success:
        print_classic_result(result)
    else:
        print("[错误] 规划失败，请检查错误信息：")
        for error in result.errors:
            print(f"  - {error}")


def run_unified(interactive: bool = False):
    """统一模式 —— 使用 UnifiedTravelCoordinator（五大模块协同）。"""
    from unified_coordinator import unified_coordinator

    print_banner()
    print("  [统一模式] 五大 AI Agent 模块协同工作")
    print("  规划模块 | 记忆模块 | 工具调用模块 | 行动执行模块 | 结果评估模块")
    print("=" * 60)

    request = build_interactive_request() if interactive else build_sample_request()
    print(f"\n[统一模式] 正在为您规划 {request.destination} 的旅行...\n")

    result = unified_coordinator.plan_trip(request)

    if result.success:
        print_unified_result(result)
    else:
        print("[错误] 规划失败，请检查错误信息：")
        for error in result.errors:
            print(f"  - {error}")

    # 可选：收集反馈
    if interactive and result.success:
        print("\n" + "-" * 60)
        feedback_input = input("请为本次规划评分 (1-5, 直接回车跳过): ").strip()
        if feedback_input:
            try:
                rating = float(feedback_input)
                comments = input("改进建议 (可选): ").strip()
                plan_id = f"unified_{date.today().isoformat()}"
                fb = unified_coordinator.collect_feedback(plan_id, rating, comments)
                print(f"  感谢反馈！评分: {fb['rating']}/5")
                if fb.get("suggested_improvements"):
                    print(f"  系统将根据反馈优化后续方案")
            except ValueError:
                pass

        # 保存会话
        unified_coordinator.save_session()
        print("  会话已保存。")

    # 打印工具调用统计
    stats = unified_coordinator.get_tool_call_stats()
    if stats["total_calls"] > 0:
        print(f"\n[工具调用统计] 共 {stats['total_calls']} 次, 成功率 {stats['success_rate']:.0%}")


if __name__ == "__main__":
    use_unified = "--unified" in sys.argv
    interactive = "-i" in sys.argv

    if use_unified:
        run_unified(interactive)
    else:
        run_classic(interactive)
