"""Budget auditor agent implementation."""

from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base import (
    create_travel_model,
    BUDGET_AUDITOR_PROMPT,
)
from agents.budget.tools import (
    calculate_total_cost,
    check_budget,
    suggest_savings,
    estimate_food_cost,
    generate_budget_report,
)


class BudgetAuditorAgent:
    """预算审计员Agent，负责汇总费用和检查预算。"""

    def __init__(self):
        self.model = create_travel_model()
        self.tools = [
            calculate_total_cost,
            check_budget,
            suggest_savings,
            estimate_food_cost,
            generate_budget_report,
        ]
        self.system_prompt = BUDGET_AUDITOR_PROMPT
        self.name = "budget_auditor"

    def audit_budget(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        accommodation_cost: float = 0.0,
        transport_cost: float = 0.0,
        ticket_cost: float = 0.0,
        food_budget_level: str = "medium",
    ) -> Dict[str, Any]:
        """
        审计预算。

        Args:
            destination: 目的地
            days: 天数
            traveler_count: 人数
            budget: 总预算
            accommodation_cost: 住宿费用
            transport_cost: 交通费用
            ticket_cost: 门票费用
            food_budget_level: 餐饮预算级别

        Returns:
            预算审计结果
        """
        # 估算餐饮费用
        food_result = estimate_food_cost.invoke({
            "days": days,
            "traveler_count": traveler_count,
            "food_budget_level": food_budget_level,
        })

        # 从结果中提取金额
        food_cost = food_budget_level == "medium" and 200 * days * traveler_count or \
                    food_budget_level == "budget" and 100 * days * traveler_count or \
                    400 * days * traveler_count

        # 计算其他费用（购物、应急等）
        other_cost = days * traveler_count * 50  # 每天50元杂费

        # 计算总费用
        total_result = calculate_total_cost.invoke({
            "accommodation_cost": accommodation_cost,
            "transport_cost": transport_cost,
            "ticket_cost": ticket_cost,
            "food_cost": food_cost,
            "other_cost": other_cost,
        })

        total = accommodation_cost + transport_cost + ticket_cost + food_cost + other_cost

        # 检查预算
        budget_check = check_budget.invoke({
            "total_cost": total,
            "budget": budget,
            "traveler_count": traveler_count,
        })

        # 生成报告
        report = generate_budget_report.invoke({
            "destination": destination,
            "days": days,
            "traveler_count": traveler_count,
            "accommodation_cost": accommodation_cost,
            "transport_cost": transport_cost,
            "ticket_cost": ticket_cost,
            "food_cost": food_cost,
            "other_cost": other_cost,
            "budget": budget,
        })

        # 如果超支，提供建议
        savings_suggestion = ""
        if total > budget:
            savings_suggestion = suggest_savings.invoke({
                "accommodation_cost": accommodation_cost,
                "transport_cost": transport_cost,
                "ticket_cost": ticket_cost,
                "food_cost": food_cost,
                "overspend": total - budget,
            })

        # 构建分析请求
        prompt = f"""
请分析以下旅行预算情况：

目的地：{destination}
天数：{days}天
人数：{traveler_count}人
总预算：¥{budget}

{report}

{budget_check}

{('超支建议：' + savings_suggestion) if savings_suggestion else '预算充足，请给出优化建议。'}

请提供专业的预算分析和建议。
"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt),
        ]

        response = self.model.invoke(messages)

        return {
            "destination": destination,
            "days": days,
            "traveler_count": traveler_count,
            "budget": budget,
            "costs": {
                "accommodation": accommodation_cost,
                "transport": transport_cost,
                "tickets": ticket_cost,
                "food": food_cost,
                "other": other_cost,
            },
            "total_cost": total,
            "remaining": budget - total,
            "is_within_budget": total <= budget,
            "report": report,
            "analysis": response.content,
            "savings_suggestion": savings_suggestion,
        }


# 全局实例
budget_auditor = BudgetAuditorAgent()
