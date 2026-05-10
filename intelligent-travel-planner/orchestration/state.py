"""State definitions for travel planning workflow."""

from typing import TypedDict, Annotated, Optional, List, Any
from typing_extensions import NotRequired
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


class TravelPlanningState(TypedDict):
    """旅行规划系统状态。

    这个状态在多个Agent之间传递，记录整个规划过程的进度和结果。
    """

    # 基础消息流
    messages: Annotated[list[AnyMessage], add_messages]

    # 用户请求信息
    destination: NotRequired[str]
    origin: NotRequired[str]
    start_date: NotRequired[str]
    end_date: NotRequired[str]
    days: NotRequired[int]
    budget: NotRequired[float]
    traveler_count: NotRequired[int]
    preferences: NotRequired[dict]

    # 各Agent的输出结果
    itinerary_plan: NotRequired[dict]      # 行程规划结果
    accommodation_plan: NotRequired[dict]   # 住宿安排结果
    transportation_plan: NotRequired[dict]  # 交通安排结果
    budget_analysis: NotRequired[dict]      # 预算分析结果

    # 协调状态
    current_stage: NotRequired[str]         # 当前阶段
    planning_complete: NotRequired[bool]    # 规划是否完成
    requires_revision: NotRequired[bool]    # 是否需要修订
    revision_count: NotRequired[int]        # 修订次数

    # 最终结果
    final_plan: NotRequired[dict]           # 最终完整计划
    errors: NotRequired[List[str]]          # 错误信息


class AgentOutput(TypedDict):
    """单个Agent的输出格式。"""

    agent_name: str
    success: bool
    data: dict
    summary: str
    errors: Optional[List[str]]
