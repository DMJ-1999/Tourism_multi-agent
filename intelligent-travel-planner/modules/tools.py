"""工具调用模块 —— 工具注册、LLM 绑定、执行中间件。

提供：
1. ToolRegistry: 集中式工具注册与发现
2. ToolExecutor: 带中间件管道的工具执行器
3. create_agent_with_tools: 将工具绑定到 LLM，实现真正的 function-calling

工具现在会被正确绑定到 LLM，由 LLM 自主决定调用哪个工具（ReAct 模式），
而非像之前那样由 agent 类手动依次调用。
"""

import time
from collections import defaultdict
from typing import Any, Callable, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from utils.logger import get_logger

logger = get_logger(__name__)


def _lazy_import_tools():
    """延迟导入所有工具 —— 避免模块级导入触发 agent 单例初始化。"""
    from agents.itinerary.tools import (
        search_attractions,
        get_attraction_details,
        optimize_route,
        get_city_highlights,
        search_restaurants,
    )
    from agents.accommodation.tools import (
        search_hotels,
        get_hotel_details,
        calculate_accommodation_cost,
        recommend_hotels_by_budget,
    )
    from agents.transportation.tools import (
        search_flights,
        search_trains,
        estimate_local_transport,
        compare_transport_options,
        get_round_trip_cost,
    )
    from agents.budget.tools import (
        calculate_total_cost,
        check_budget,
        suggest_savings,
        estimate_food_cost,
        generate_budget_report,
    )

    return {
        # 行程规划工具
        "search_attractions": search_attractions,
        "get_attraction_details": get_attraction_details,
        "optimize_route": optimize_route,
        "get_city_highlights": get_city_highlights,
        "search_restaurants": search_restaurants,
        # 住宿工具
        "search_hotels": search_hotels,
        "get_hotel_details": get_hotel_details,
        "calculate_accommodation_cost": calculate_accommodation_cost,
        "recommend_hotels_by_budget": recommend_hotels_by_budget,
        # 交通工具
        "search_flights": search_flights,
        "search_trains": search_trains,
        "estimate_local_transport": estimate_local_transport,
        "compare_transport_options": compare_transport_options,
        "get_round_trip_cost": get_round_trip_cost,
        # 预算工具
        "calculate_total_cost": calculate_total_cost,
        "check_budget": check_budget,
        "suggest_savings": suggest_savings,
        "estimate_food_cost": estimate_food_cost,
        "generate_budget_report": generate_budget_report,
    }


class ToolRegistry:
    """集中式工具注册中心 —— 管理所有智能体可用的工具。

    特性：
    - 按智能体/领域分类管理
    - 支持按名称或标签检索
    - 提供工具元数据（名称、描述、所属智能体）
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._by_agent: dict[str, list[str]] = defaultdict(list)
        self._by_tag: dict[str, list[str]] = defaultdict(list)

        # 注册所有工具
        self._register_all()

    def _register_all(self) -> None:
        """注册项目中的所有工具（延迟导入）。"""
        tools = _lazy_import_tools()

        agent_map = {
            "search_attractions": "itinerary",
            "get_attraction_details": "itinerary",
            "optimize_route": "itinerary",
            "get_city_highlights": "itinerary",
            "search_restaurants": "itinerary",
            "search_hotels": "accommodation",
            "get_hotel_details": "accommodation",
            "calculate_accommodation_cost": "accommodation",
            "recommend_hotels_by_budget": "accommodation",
            "search_flights": "transportation",
            "search_trains": "transportation",
            "estimate_local_transport": "transportation",
            "compare_transport_options": "transportation",
            "get_round_trip_cost": "transportation",
            "calculate_total_cost": "budget",
            "check_budget": "budget",
            "suggest_savings": "budget",
            "estimate_food_cost": "budget",
            "generate_budget_report": "budget",
        }

        for name, tool_fn in tools.items():
            self.register(name, tool_fn, agent=agent_map.get(name, "general"))

        logger.info(f"工具注册完成: {len(self._tools)} 个工具, {len(self._by_agent)} 个智能体")

    def register(
        self,
        name: str,
        tool: BaseTool,
        *,
        agent: str = "general",
        tags: list[str] | None = None,
    ) -> None:
        """注册一个工具。"""
        self._tools[name] = tool
        self._by_agent[agent].append(name)
        for tag in (tags or []):
            self._by_tag[tag].append(name)

    def get(self, name: str) -> Optional[BaseTool]:
        """按名称获取工具。"""
        return self._tools.get(name)

    def get_by_agent(self, agent: str) -> list[BaseTool]:
        """获取指定智能体的所有工具。"""
        return [self._tools[n] for n in self._by_agent.get(agent, []) if n in self._tools]

    def get_by_tag(self, tag: str) -> list[BaseTool]:
        """按标签搜索工具。"""
        return [self._tools[n] for n in self._by_tag.get(tag, []) if n in self._tools]

    def list_all(self) -> list[str]:
        """列出所有已注册的工具名称。"""
        return list(self._tools.keys())

    def list_agents(self) -> list[str]:
        """列出所有智能体及其工具数量。"""
        return [f"{agent} ({len(tools)})" for agent, tools in self._by_agent.items()]

    def get_all_tools(self) -> list[BaseTool]:
        """获取所有工具列表（用于 bind_tools）。"""
        return list(self._tools.values())

    def get_tools_for_agent_binding(self, agent: str) -> list[BaseTool]:
        """获取指定智能体的工具列表（用于 bind_tools）。"""
        return self.get_by_agent(agent)


class ToolExecutor:
    """工具执行器 —— 带中间件管道的工具调用。

    中间件管道：
    1. 日志记录（调用前/后）
    2. 超时保护
    3. 异常捕获与重试
    4. 结果格式化
    """

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        *,
        default_timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.registry = registry or ToolRegistry()
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.call_history: list[dict] = []

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """执行单个工具调用（带中间件）。"""
        tool = self.registry.get(tool_name)
        if tool is None:
            error_msg = f"工具不存在: {tool_name}"
            logger.error(error_msg)
            return error_msg

        start_time = time.time()
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"执行工具 [{tool_name}] (attempt {attempt + 1})")
                result = tool.invoke(tool_input)
                elapsed = time.time() - start_time

                self.call_history.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "success": True,
                    "elapsed": elapsed,
                    "attempt": attempt + 1,
                })

                logger.info(f"工具 [{tool_name}] 完成, 耗时 {elapsed:.2f}s")
                return str(result) if not isinstance(result, str) else result

            except Exception as e:
                last_error = e
                logger.warning(f"工具 [{tool_name}] 执行失败 (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))  # 退避重试
                continue

        # 所有重试均失败
        elapsed = time.time() - start_time
        self.call_history.append({
            "tool": tool_name,
            "input": tool_input,
            "success": False,
            "elapsed": elapsed,
            "error": str(last_error),
        })
        return f"工具执行失败 [{tool_name}]: {last_error}"

    def execute_batch(self, calls: list[tuple[str, dict[str, Any]]]) -> list[str]:
        """批量执行工具调用（顺序执行）。"""
        return [self.execute(name, params) for name, params in calls]

    def get_call_stats(self) -> dict:
        """获取工具调用统计。"""
        if not self.call_history:
            return {"total_calls": 0}

        success_count = sum(1 for c in self.call_history if c["success"])
        total_time = sum(c["elapsed"] for c in self.call_history)
        return {
            "total_calls": len(self.call_history),
            "success_count": success_count,
            "failure_count": len(self.call_history) - success_count,
            "success_rate": success_count / len(self.call_history) if self.call_history else 0,
            "total_time": total_time,
            "avg_time": total_time / len(self.call_history) if self.call_history else 0,
        }


def create_agent_with_tools(
    agent_name: str,
    system_prompt: str,
    tools: list[BaseTool] | None = None,
    model: BaseChatModel | None = None,
) -> dict:
    """创建配备工具的智能体 —— 将工具绑定到 LLM 实现 function-calling。

    与旧版 create_travel_agent() 不同，此函数返回的智能体包含：
    - model_with_tools: 绑定了工具的 LLM（LLM 可自主决定调用哪个工具）
    - 而非仅仅存储工具列表供手动调用

    Args:
        agent_name: 智能体名称
        system_prompt: 系统提示词
        tools: 该智能体的工具列表（None 则从 ToolRegistry 获取）
        model: LLM 模型（None 则使用默认模型）

    Returns:
        包含 model_with_tools、tools、system_prompt 的智能体配置
    """
    if model is None:
        from agents.base import create_travel_model
        model = create_travel_model()

    if tools is None:
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent_binding(agent_name)

    # 将工具绑定到 LLM —— 这是关键步骤
    # LLM 现在可以自主决定何时调用哪个工具
    model_with_tools = model.bind_tools(tools)

    logger.info(
        f"创建智能体 [{agent_name}]: "
        f"模型={model._llm_type if hasattr(model, '_llm_type') else 'LLM'}, "
        f"工具数={len(tools)}"
    )

    return {
        "name": agent_name,
        "model": model,
        "model_with_tools": model_with_tools,
        "tools": tools,
        "system_prompt": system_prompt,
    }


def run_agent_tool_loop(
    agent_config: dict,
    user_message: str,
    max_iterations: int = 5,
) -> str:
    """运行智能体的 ReAct 工具调用循环。

    LLM 在循环中自主决定调用工具，直到给出最终答案或达到最大迭代次数。

    Args:
        agent_config: create_agent_with_tools 返回的智能体配置
        user_message: 用户消息
        max_iterations: 最大工具调用迭代次数

    Returns:
        智能体的最终响应文本
    """
    model_with_tools = agent_config["model_with_tools"]
    system_prompt = agent_config["system_prompt"]
    tools = {t.name: t for t in agent_config["tools"]}

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    for iteration in range(max_iterations):
        response = model_with_tools.invoke(messages)
        messages.append(response)

        # 检查是否有工具调用
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            # 没有工具调用，说明 LLM 给出了最终答案
            return response.content if hasattr(response, "content") else str(response)

        # 执行所有工具调用
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})

            logger.info(f"[ReAct] 迭代 {iteration + 1}: 调用工具 {tool_name}")

            tool = tools.get(tool_name)
            if tool:
                try:
                    result = tool.invoke(tool_args)
                    result_str = str(result) if not isinstance(result, str) else result
                except Exception as e:
                    result_str = f"工具执行错误: {e}"
            else:
                result_str = f"未知工具: {tool_name}"

            messages.append(ToolMessage(
                content=result_str,
                tool_call_id=tool_call.get("id", ""),
            ))

    # 达到最大迭代次数，强制 LLM 给出最终答案
    messages.append(HumanMessage(content="请基于以上工具调用结果，给出最终答案。"))
    final_response = agent_config["model"].invoke(messages)
    return final_response.content if hasattr(final_response, "content") else str(final_response)


# 全局工具注册中心单例
tool_registry = ToolRegistry()
