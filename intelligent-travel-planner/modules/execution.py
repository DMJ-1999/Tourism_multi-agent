"""行动执行模块 —— 基于 LangGraph StateGraph 编排四个 ReAct Agent。

核心架构：
  每个 Agent 节点内部运行完整的 ReAct 循环:
    LLM.bind_tools(tools) → LLM 自主决策调用工具 → 执行工具
    → ToolMessage 返回 LLM → 循环直到给出最终答案

  LangGraph 编排四个 Agent:
    START
      │
      ▼
    [itinerary_agent]        ← 行程规划师 (ReAct, 5 tools, 高德API)
      │
      ├── Send ──→ [accommodation_agent]   ← 住宿协调员 (ReAct, 4 tools, 高德API)
      └── Send ──→ [food_agent]            ← 餐饮规划员 (ReAct, 5 tools, 美团API)
      │               │
      └───────────────┘
              │
              ▼
    [budget_agent]           ← 预算审计员 (ReAct, 5 tools)
              │
              ▼
    [evaluate]               ← 结果评估 (规则/LLM 评分)
              │
      ┌───────┴────────┐
      │ add_conditional_edges
      │                   │
      budget OK?          revisions >= 3?
      │                   │
      ▼                   ▼
     END            [revise] ──→ budget_agent (loop)
"""

from typing import Annotated, Any, Callable, Literal, TypedDict

from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Send
from langchain_core.messages import BaseMessage

from utils.logger import get_logger

logger = get_logger(__name__)


# ==================== 状态定义 ====================

class AgentState(TypedDict, total=False):
    """LangGraph 全局状态。

    messages 使用 add_messages reducer，新消息追加而非覆盖。
    其他字段默认覆盖策略。
    """

    # ── 对话消息（所有 Agent 共享，ReAct 工具调用记录）──
    messages: Annotated[list[BaseMessage], add_messages]

    # ── 输入参数（不可变）──
    destination: str
    origin: str
    days: int
    traveler_count: int
    budget: float
    preference_level: str

    # ── Agent 输出 ──
    itinerary_result: dict
    accommodation_result: dict
    food_result: dict
    budget_result: dict
    evaluation_result: dict

    # ── 控制流 ──
    total_cost: float
    is_within_budget: bool
    revision_count: int
    max_revisions: int
    errors: list[str]


def build_initial_state(
    destination: str,
    origin: str,
    days: int,
    traveler_count: int,
    budget: float,
    preference_level: str = "舒适型",
) -> AgentState:
    """构建初始状态。"""
    return AgentState(
        messages=[],
        destination=destination,
        origin=origin,
        days=days,
        traveler_count=traveler_count,
        budget=budget,
        preference_level=preference_level,
        itinerary_result={},
        accommodation_result={},
        food_result={},
        budget_result={},
        evaluation_result={},
        total_cost=0.0,
        is_within_budget=True,
        revision_count=0,
        max_revisions=3,
        errors=[],
    )


# ==================== Agent 运行器 ====================

def run_react_agent(
    model: Any,
    tools: list,
    system_prompt: str,
    user_task: str,
    *,
    max_iterations: int = 6,
) -> dict:
    """运行一个完整的 ReAct Agent 循环。

    这是将 LLM 变成真正 Agent 的核心函数：
    1. 将 tools 绑定到 LLM (bind_tools)
    2. LLM 自主决定调用哪些工具、何时调用
    3. 工具结果返回 LLM，形成推理闭环
    4. 直到 LLM 输出最终答案（无 tool_calls）

    Args:
        model: ChatModel 实例（如 ChatTongyi）
        tools: 工具列表
        system_prompt: 系统提示词
        user_task: 用户任务描述
        max_iterations: 最大工具调用轮次

    Returns:
        {"messages": [...], "final_response": str}
    """
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage

    if not tools:
        # 无工具时直接调用 LLM
        response = model.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_task),
        ])
        return {
            "messages": [response],
            "final_response": response.content if hasattr(response, "content") else str(response),
        }

    # 关键：将工具绑定到 LLM，启用 function-calling
    model_with_tools = model.bind_tools(tools)
    tool_map = {t.name: t for t in tools}

    messages: list = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_task),
    ]

    for iteration in range(max_iterations):
        response = model_with_tools.invoke(messages)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            # LLM 认为已经可以给出最终答案
            return {
                "messages": messages,
                "final_response": response.content if hasattr(response, "content") else str(response),
            }

        # 执行 LLM 请求的每一个工具调用
        for tc in tool_calls:
            tool_name = tc.get("name", "")
            tool_args = tc.get("args", {})
            logger.info(f"  [ReAct] tool={tool_name} args={str(tool_args)[:100]}")

            tool = tool_map.get(tool_name)
            if tool:
                try:
                    raw = tool.invoke(tool_args)
                    result_str = str(raw) if not isinstance(raw, str) else raw
                except Exception as e:
                    result_str = f"工具执行错误 [{tool_name}]: {e}"
            else:
                result_str = f"未知工具: {tool_name}"

            messages.append(ToolMessage(
                content=result_str,
                tool_call_id=tc.get("id", ""),
            ))

    # 达到最大迭代次数，强制总结
    messages.append(HumanMessage(content="请基于已获取的所有信息，给出最终答案。"))
    final = model.invoke(messages)
    return {
        "messages": messages,
        "final_response": final.content if hasattr(final, "content") else str(final),
    }


# ==================== LangGraph 图构建器 ====================

class TravelGraphBuilder:
    """LangGraph 工作流构建器。

    将四个 ReAct Agent 注册为图节点，编译为可执行图。

    用法:
        builder = TravelGraphBuilder()
        builder.register_agents(
            itinerary_agent=fn1,
            accommodation_agent=fn2,
            food_agent=fn3,
            budget_agent=fn4,
            evaluate_node=fn5,
            revise_node=fn6,
        )
        graph = builder.compile()
        result = graph.invoke(build_initial_state(...))
    """

    def __init__(self) -> None:
        self._agents: dict[str, Callable[[AgentState], dict]] = {}

    def register_agents(
        self,
        *,
        itinerary_agent: Callable[[AgentState], dict],
        accommodation_agent: Callable[[AgentState], dict],
        food_agent: Callable[[AgentState], dict],
        budget_agent: Callable[[AgentState], dict],
        evaluate_node: Callable[[AgentState], dict],
        revise_node: Callable[[AgentState], dict],
    ) -> None:
        """注册六个节点的处理函数。

        每个函数签名为 (AgentState) -> dict，返回部分状态更新。
        """
        self._agents = {
            "itinerary": itinerary_agent,
            "accommodation": accommodation_agent,
            "food": food_agent,
            "budget": budget_agent,
            "evaluate": evaluate_node,
            "revise": revise_node,
        }
        logger.info("6 个节点已注册: " + ", ".join(self._agents.keys()))

    def compile(self) -> Any:
        """构建并编译 LangGraph 工作流。

        Returns:
            CompiledStateGraph (LangChain Runnable)
        """
        graph = StateGraph(AgentState)

        # 注册节点
        for name, handler in self._agents.items():
            graph.add_node(name, handler)

        # ── 边定义 ──

        # START → itinerary
        graph.add_edge(START, "itinerary")

        # itinerary → fan-out (Send) → accommodation ‖ food
        graph.add_conditional_edges(
            "itinerary",
            self._fanout_after_itinerary,
            path_map=["accommodation", "food"],
        )

        # accommodation → budget (汇聚)
        graph.add_edge("accommodation", "budget")

        # food → budget (汇聚)
        graph.add_edge("food", "budget")

        # budget → evaluate
        graph.add_edge("budget", "evaluate")

        # evaluate → 条件边
        graph.add_conditional_edges(
            "evaluate",
            self._decide_after_evaluate,
            path_map=["revise", END],
        )

        # revise → budget (重新审计)
        graph.add_edge("revise", "budget")

        compiled = graph.compile()
        logger.info("LangGraph 工作流编译完成")
        return compiled

    # ── 条件路由 ──

    def _fanout_after_itinerary(self, state: AgentState) -> list[Send]:
        """itinerary 完成后 fan-out 到两个并行 Agent。

        accommodation 和 food 互不依赖，
        LangGraph Send API 让它们并发执行。
        """
        logger.info("[LangGraph] fan-out → accommodation ‖ food")
        return [
            Send("accommodation", state),
            Send("food", state),
        ]

    def _decide_after_evaluate(
        self, state: AgentState
    ) -> Literal["revise", "__end__"]:
        """评估后条件路由。"""
        is_ok = state.get("is_within_budget", True)
        revision_count = state.get("revision_count", 0)
        max_revisions = state.get("max_revisions", 3)

        if is_ok:
            logger.info("[LangGraph] 预算充足 → END")
            return "__end__"

        if revision_count < max_revisions:
            logger.info(f"[LangGraph] 超支 → revise ({revision_count + 1}/{max_revisions})")
            return "revise"

        logger.info(f"[LangGraph] 已达最大修订次数 → END")
        return "__end__"
