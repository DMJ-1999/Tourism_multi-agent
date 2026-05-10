"""Tools for budget auditor agent."""

from typing import Dict, List, Optional
from langchain_core.tools import tool


@tool
def calculate_total_cost(
    accommodation_cost: float = 0.0,
    transport_cost: float = 0.0,
    ticket_cost: float = 0.0,
    food_cost: float = 0.0,
    other_cost: float = 0.0,
) -> str:
    """
    计算旅行总费用。

    Args:
        accommodation_cost: 住宿费用
        transport_cost: 交通费用
        ticket_cost: 门票费用
        food_cost: 餐饮费用
        other_cost: 其他费用

    Returns:
        费用汇总
    """
    total = (
        accommodation_cost
        + transport_cost
        + ticket_cost
        + food_cost
        + other_cost
    )

    result_lines = [
        "费用汇总：",
        f"  住宿: ¥{accommodation_cost:.0f}",
        f"  交通: ¥{transport_cost:.0f}",
        f"  门票: ¥{ticket_cost:.0f}",
        f"  餐饮: ¥{food_cost:.0f}",
        f"  其他: ¥{other_cost:.0f}",
        f"─────────────",
        f"  总计: ¥{total:.0f}",
    ]

    return "\n".join(result_lines)


@tool
def check_budget(
    total_cost: float,
    budget: float,
    traveler_count: int = 1,
) -> str:
    """
    检查是否超预算。

    Args:
        total_cost: 总费用
        budget: 预算
        traveler_count: 人数

    Returns:
        预算检查结果
    """
    per_person_cost = total_cost / traveler_count
    per_person_budget = budget / traveler_count
    diff = budget - total_cost

    if diff >= 0:
        result_lines = [
            f"✅ 预算检查通过！",
            f"",
            f"总预算: ¥{budget:.0f}",
            f"总费用: ¥{total_cost:.0f}",
            f"剩余: ¥{diff:.0f}",
            f"",
            f"人均费用: ¥{per_person_cost:.0f}",
            f"人均预算: ¥{per_person_budget:.0f}",
        ]
    else:
        result_lines = [
            f"⚠️ 预算超支！",
            f"",
            f"总预算: ¥{budget:.0f}",
            f"总费用: ¥{total_cost:.0f}",
            f"超支: ¥{abs(diff):.0f}",
            f"",
            f"人均费用: ¥{per_person_cost:.0f}",
            f"人均预算: ¥{per_person_budget:.0f}",
        ]

    return "\n".join(result_lines)


@tool
def suggest_savings(
    accommodation_cost: float,
    transport_cost: float,
    ticket_cost: float,
    food_cost: float,
    overspend: float,
) -> str:
    """
    提供节省费用的建议。

    Args:
        accommodation_cost: 住宿费用
        transport_cost: 交通费用
        ticket_cost: 门票费用
        food_cost: 餐饮费用
        overspend: 超支金额

    Returns:
        节省建议
    """
    suggestions = []
    total_current = accommodation_cost + transport_cost + ticket_cost + food_cost

    # 分析各项费用占比
    suggestions.append(f"需要节省 ¥{overspend:.0f} 才能符合预算。\n")
    suggestions.append("费用构成分析：")
    suggestions.append(f"  住宿: ¥{accommodation_cost:.0f} ({accommodation_cost/total_current*100:.0f}%)")
    suggestions.append(f"  交通: ¥{transport_cost:.0f} ({transport_cost/total_current*100:.0f}%)")
    suggestions.append(f"  门票: ¥{ticket_cost:.0f} ({ticket_cost/total_current*100:.0f}%)")
    suggestions.append(f"  餐饮: ¥{food_cost:.0f} ({food_cost/total_current*100:.0f}%)\n")

    suggestions.append("💡 节省建议：")

    if accommodation_cost > total_current * 0.35:
        savings = accommodation_cost * 0.2
        suggestions.append(
            f"  1. 选择更低价格的酒店，可节省约¥{savings:.0f}"
        )

    if transport_cost > total_current * 0.3:
        savings = transport_cost * 0.15
        suggestions.append(
            f"  2. 选择火车代替航班，可节省约¥{savings:.0f}"
        )

    if ticket_cost > total_current * 0.15:
        suggestions.append(
            "  3. 选择免费景点或购买联票，减少门票支出"
        )

    suggestions.append(
        "  4. 减少一天行程或选择周边更经济的目的地"
    )

    suggestions.append(
        "  5. 自带零食和水，减少景区内的额外消费"
    )

    return "\n".join(suggestions)


@tool
def estimate_food_cost(
    days: int,
    traveler_count: int,
    food_budget_level: str = "medium",
) -> str:
    """
    估算餐饮费用。

    Args:
        days: 天数
        traveler_count: 人数
        food_budget_level: 餐饮预算级别（budget/medium/luxury）

    Returns:
        餐饮费用估算
    """
    daily_budgets = {
        "budget": 100,      # 经济型：早餐20+午餐40+晚餐40
        "medium": 200,      # 中等：早餐30+午餐80+晚餐90
        "luxury": 400,      # 豪华：早餐50+午餐150+晚餐200
    }

    daily_budget = daily_budgets.get(food_budget_level, 200)
    total = daily_budget * days * traveler_count

    return (
        f"餐饮费用估算（{food_budget_level}级别）：\n"
        f"  每人每日: ¥{daily_budget}\n"
        f"  天数: {days}天\n"
        f"  人数: {traveler_count}人\n"
        f"  总计: ¥{daily_budget} × {days}天 × {traveler_count}人 = ¥{total}"
    )


@tool
def generate_budget_report(
    destination: str,
    days: int,
    traveler_count: int,
    accommodation_cost: float,
    transport_cost: float,
    ticket_cost: float,
    food_cost: float,
    other_cost: float,
    budget: float,
) -> str:
    """
    生成完整的预算报告。

    Args:
        destination: 目的地
        days: 天数
        traveler_count: 人数
        accommodation_cost: 住宿费用
        transport_cost: 交通费用
        ticket_cost: 门票费用
        food_cost: 餐饮费用
        other_cost: 其他费用
        budget: 预算

    Returns:
        预算报告
    """
    total = accommodation_cost + transport_cost + ticket_cost + food_cost + other_cost
    diff = budget - total

    status = "✅ 预算充足" if diff >= 0 else "⚠️ 预算超支"

    lines = [
        "=" * 40,
        f"   旅行预算报告 - {destination}",
        "=" * 40,
        f"",
        f"行程信息：",
        f"  目的地: {destination}",
        f"  天数: {days}天",
        f"  人数: {traveler_count}人",
        f"",
        f"费用明细：",
        f"  ├─ 住宿: ¥{accommodation_cost:.0f}",
        f"  ├─ 交通: ¥{transport_cost:.0f}",
        f"  ├─ 门票: ¥{ticket_cost:.0f}",
        f"  ├─ 餐饮: ¥{food_cost:.0f}",
        f"  └─ 其他: ¥{other_cost:.0f}",
        f"",
        f"─────────────────────",
        f"  总费用: ¥{total:.0f}",
        f"  预算: ¥{budget:.0f}",
        f"  {status}: ¥{abs(diff):.0f}",
        f"",
        f"人均费用: ¥{total/traveler_count:.0f}",
        "=" * 40,
    ]

    return "\n".join(lines)
