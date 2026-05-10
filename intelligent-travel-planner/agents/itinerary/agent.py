"""Itinerary planner agent implementation."""

from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base import (
    create_travel_model,
    ITINERARY_PLANNER_PROMPT,
)
from agents.itinerary.tools import (
    search_attractions,
    get_attraction_details,
    optimize_route,
    get_city_highlights,
)


class ItineraryPlannerAgent:
    """行程规划师Agent，负责设计每日活动路线。"""

    def __init__(self):
        self.model = create_travel_model()
        self.tools = [
            search_attractions,
            get_attraction_details,
            optimize_route,
            get_city_highlights,
        ]
        self.system_prompt = ITINERARY_PLANNER_PROMPT
        self.name = "itinerary_planner"

    def plan(
        self,
        destination: str,
        days: int,
        preferences: dict = None,
    ) -> dict:
        """
        规划旅行行程。

        Args:
            destination: 目的地
            days: 旅行天数
            preferences: 用户偏好

        Returns:
            行程规划结果
        """
        preferences = preferences or {}

        # 获取城市亮点
        highlights = get_city_highlights.invoke({"location": destination})

        # 搜索景点
        categories = preferences.get("categories")
        tags = preferences.get("tags", ["必去"])

        attractions_info = search_attractions.invoke({
            "location": destination,
            "categories": categories,
            "tags": tags,
        })

        # 构建规划请求
        prompt = f"""
请为以下旅行需求规划行程：

目的地：{destination}
天数：{days}天
用户偏好：{preferences.get('interests', '无特别偏好')}

{highlights}

{attractions_info}

请给出详细的每日行程安排建议。
"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt),
        ]

        response = self.model.invoke(messages)

        return {
            "destination": destination,
            "days": days,
            "plan": response.content,
            "highlights": highlights,
            "attractions_info": attractions_info,
        }


# 全局实例
itinerary_planner = ItineraryPlannerAgent()
