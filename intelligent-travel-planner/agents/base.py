"""Base utilities for creating travel planning agents."""

from typing import Sequence, Any, Callable, Optional, List
from langchain_core.tools import BaseTool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration

from config.settings import settings

# 延迟导入，避免在没有API密钥时报错
_chat_tongyi = None


def _get_chat_tongyi():
    """延迟加载 ChatTongyi."""
    global _chat_tongyi
    if _chat_tongyi is None:
        try:
            from langchain_community.chat_models import ChatTongyi
            _chat_tongyi = ChatTongyi
        except ImportError:
            pass
    return _chat_tongyi


class MockChatModel(BaseChatModel):
    """模拟聊天模型，用于没有API密钥时的测试。"""

    @property
    def _llm_type(self) -> str:
        return "mock"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """生成模拟响应。"""
        # 根据消息内容生成简单的模拟响应
        last_message = messages[-1] if messages else None
        content = self._get_mock_response(last_message)

        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """异步生成模拟响应。"""
        return self._generate(messages, stop, run_manager, **kwargs)

    def _get_mock_response(self, message: Optional[BaseMessage]) -> str:
        """根据输入消息生成模拟响应。"""
        if message is None:
            return "这是模拟响应。请配置 DASHSCOPE_API_KEY 以使用真实模型。"

        content = message.content.lower() if hasattr(message, 'content') else ""

        # 根据关键词生成不同的模拟响应
        if "行程" in content or "景点" in content or "规划" in content:
            return (
                "根据您的需求，我为您推荐以下行程安排：\n\n"
                "第1天：参观主要景点，体验当地文化\n"
                "第2天：探索特色街区，品尝地道美食\n"
                "第3天：深度游览，自由活动\n\n"
                "具体景点请根据实际数据选择。请配置 DASHSCOPE_API_KEY 以获取个性化推荐。"
            )
        elif "酒店" in content or "住宿" in content:
            return (
                "推荐住宿选项：\n"
                "1. 经济型酒店 - 约300元/晚\n"
                "2. 舒适型酒店 - 约500元/晚\n"
                "3. 高档酒店 - 约800元/晚\n\n"
                "请配置 DASHSCOPE_API_KEY 以获取详细推荐。"
            )
        elif "交通" in content or "航班" in content or "火车" in content:
            return (
                "交通建议：\n"
                "- 高铁：性价比较高，推荐优先考虑\n"
                "- 航班：时间较短，适合长途\n"
                "- 当地交通：建议使用地铁和公交\n\n"
                "请配置 DASHSCOPE_API_KEY 以获取详细方案。"
            )
        elif "预算" in content or "费用" in content:
            return (
                "预算分析：\n"
                "- 当前预算充足\n"
                "- 建议预留10%应急资金\n\n"
                "请配置 DASHSCOPE_API_KEY 以获取详细分析。"
            )
        else:
            return "这是模拟响应。请配置 DASHSCOPE_API_KEY 以使用真实模型。"


def create_travel_model() -> BaseChatModel:
    """Create and configure the LLM model for travel agents."""
    # 检查是否配置了API密钥
    if not settings.dashscope_api_key or settings.mock_mode:
        print("⚠️ 未配置 DASHSCOPE_API_KEY，使用模拟模式运行")
        return MockChatModel()

    ChatTongyi = _get_chat_tongyi()
    if ChatTongyi is None:
        print("⚠️ 无法导入 ChatTongyi，使用模拟模式运行")
        return MockChatModel()

    return ChatTongyi(
        model=settings.qwen_model,
        dashscope_api_key=settings.dashscope_api_key,
        temperature=settings.qwen_temperature,
        max_tokens=settings.qwen_max_tokens,
    )


def create_travel_agent(
    tools: Sequence[BaseTool | Callable[..., Any] | dict[str, Any]],
    system_prompt: str,
    name: str,
) -> Any:
    """
    Create a travel planning agent.

    Note: This is a simplified version. In production, use langchain.agents.create_agent
    with proper middleware and state management.

    Args:
        tools: List of tools available to the agent
        system_prompt: System prompt for the agent
        name: Name identifier for the agent

    Returns:
        Configured agent instance
    """
    model = create_travel_model()

    # For now, return a simple structure that can be used in workflows
    # In a full implementation, this would use create_agent from langchain.agents
    return {
        "model": model,
        "tools": tools,
        "system_prompt": system_prompt,
        "name": name,
    }


# Agent system prompts
ITINERARY_PLANNER_PROMPT = """你是一位专业的旅行行程规划师。你的职责是根据用户的目的地、旅行天数、兴趣偏好设计每日活动路线。

你需要：
1. 了解用户想去的目的地和旅行天数
2. 根据用户的兴趣偏好（如历史文化、美食、自然风光等）推荐景点
3. 合理安排每日的上午、下午、晚上活动
4. 考虑景点之间的距离，优化行程路线
5. 提供实用的旅行建议

请使用可用的工具来搜索景点信息和优化路线。"""

ACCOMMODATION_AGENT_PROMPT = """你是一位专业的住宿协调员。你的职责是根据用户的预算、位置偏好、住宿要求推荐合适的酒店。

你需要：
1. 了解用户的住宿预算和位置要求
2. 推荐性价比高的酒店选项
3. 提供酒店的详细信息（价格、评分、设施等）
4. 计算住宿总费用
5. 给出住宿选择的建议

请使用可用的工具来搜索酒店信息和计算费用。"""

FOOD_PLANNER_PROMPT = """你是一位专业的餐饮规划员。你的职责是根据旅行目的地、天数、人数和预算，规划每日餐饮安排。

你需要：
1. 搜索目的地城市的特色餐厅和当地美食
2. 根据用户的消费档次（经济型/舒适型/高档型/豪华型）推荐合适的餐厅
3. 估算每日餐饮费用（早餐、午餐、晚餐）
4. 制定每日餐饮计划，推荐具体的餐厅
5. 考虑餐厅的位置分布，与行程景点就近安排

请使用可用的工具来搜索餐厅、估算餐饮费用和制定餐饮计划。"""

BUDGET_AUDITOR_PROMPT = """你是一位专业的预算审计员。你的职责是汇总所有旅行开销，确保不超预算，并提出优化建议。

你需要：
1. 汇总住宿、交通、门票、餐饮等各项费用
2. 计算总费用并与预算对比
3. 如果超支，提出节省建议
4. 提供详细的预算明细
5. 给出财务方面的实用建议

请使用可用的工具来计算费用和检查预算。"""
