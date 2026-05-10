"""Transportation agent implementation."""

from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base import (
    create_travel_model,
    TRANSPORTATION_AGENT_PROMPT,
)
from agents.transportation.tools import (
    search_flights,
    search_trains,
    estimate_local_transport,
    compare_transport_options,
    get_round_trip_cost,
)


class TransportationAgent:
    """交通调度员Agent，负责规划往返交通和当地交通。"""

    def __init__(self):
        self.model = create_travel_model()
        self.tools = [
            search_flights,
            search_trains,
            estimate_local_transport,
            compare_transport_options,
            get_round_trip_cost,
        ]
        self.system_prompt = TRANSPORTATION_AGENT_PROMPT
        self.name = "transportation_agent"

    def plan_transportation(
        self,
        origin: str,
        destination: str,
        days: int,
        traveler_count: int = 1,
        preferences: dict = None,
    ) -> dict:
        """
        规划交通方案。

        Args:
            origin: 出发城市
            destination: 目的地
            days: 天数
            traveler_count: 人数
            preferences: 用户偏好

        Returns:
            交通规划结果
        """
        preferences = preferences or {}

        # 比较交通方式
        comparison = compare_transport_options.invoke({
            "departure_city": origin,
            "arrival_city": destination,
        })

        # 获取往返费用
        preferred_type = preferences.get("transport_type", "train")
        round_trip = get_round_trip_cost.invoke({
            "departure_city": origin,
            "arrival_city": destination,
            "transport_type": preferred_type,
        })

        # 估算当地交通
        local_transport = estimate_local_transport.invoke({
            "city": destination,
            "days": days,
        })

        # 构建规划请求
        prompt = f"""
请为以下旅行需求规划交通方案：

出发地：{origin}
目的地：{destination}
天数：{days}天
人数：{traveler_count}人
偏好：{preferences.get('transport_preference', '无特别要求')}

{comparison}

{round_trip}

{local_transport}

请给出完整的交通建议，包括往返交通和当地交通方案。
"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt),
        ]

        response = self.model.invoke(messages)

        return {
            "origin": origin,
            "destination": destination,
            "days": days,
            "traveler_count": traveler_count,
            "plan": response.content,
            "comparison": comparison,
            "round_trip": round_trip,
            "local_transport": local_transport,
        }


# 全局实例
transportation_agent = TransportationAgent()
