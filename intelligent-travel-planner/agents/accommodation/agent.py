"""Accommodation agent implementation."""

from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base import (
    create_travel_model,
    ACCOMMODATION_AGENT_PROMPT,
)
from agents.accommodation.tools import (
    search_hotels,
    get_hotel_details,
    calculate_accommodation_cost,
    recommend_hotels_by_budget,
)


class AccommodationAgent:
    """住宿协调员Agent，负责推荐酒店和计算住宿费用。"""

    def __init__(self):
        self.model = create_travel_model()
        self.tools = [
            search_hotels,
            get_hotel_details,
            calculate_accommodation_cost,
            recommend_hotels_by_budget,
        ]
        self.system_prompt = ACCOMMODATION_AGENT_PROMPT
        self.name = "accommodation_agent"

    def find_accommodation(
        self,
        destination: str,
        nights: int,
        budget_per_night: float = None,
        room_count: int = 1,
        preferences: dict = None,
    ) -> dict:
        """
        查找并推荐住宿。

        Args:
            destination: 目的地
            nights: 住宿晚数
            budget_per_night: 每晚预算
            room_count: 房间数量
            preferences: 用户偏好

        Returns:
            住宿推荐结果
        """
        preferences = preferences or {}

        # 搜索酒店
        min_rating = preferences.get("min_rating", 4.0)
        star_rating = preferences.get("star_rating")

        hotels_info = search_hotels.invoke({
            "location": destination,
            "max_price": budget_per_night,
            "min_rating": min_rating,
            "star_rating": star_rating,
        })

        # 构建推荐请求
        prompt = f"""
请为以下住宿需求推荐合适的酒店：

目的地：{destination}
住宿晚数：{nights}晚
房间数量：{room_count}间
每晚预算：{'¥' + str(budget_per_night) if budget_per_night else '无限制'}
用户偏好：{preferences.get('accommodation_type', '无特别要求')}

{hotels_info}

请给出3个住宿推荐选项，并计算各自的总费用。
"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt),
        ]

        response = self.model.invoke(messages)

        return {
            "destination": destination,
            "nights": nights,
            "room_count": room_count,
            "recommendation": response.content,
            "hotels_info": hotels_info,
        }


# 全局实例
accommodation_agent = AccommodationAgent()
