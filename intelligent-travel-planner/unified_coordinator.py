"""统一协调器 —— 基于 LangGraph StateGraph 编排四个 ReAct Agent 的旅行规划系统。

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

五大模块对应关系:
  [规划模块]   → TaskDecomposer / PlanGenerator (任务分解)
  [记忆模块]   → ConversationMemory / UserProfile (用户画像)
  [工具调用]   → ToolRegistry (19 个工具注册,bind_tools 绑定)
  [行动执行]   → LangGraph StateGraph + run_react_agent()
  [结果评估]   → PlanEvaluator / ConstraintValidator
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from data.models import TravelRequest
from utils.logger import get_logger

# 五大模块
from modules.planning import TaskDecomposer, PlanGenerator, ExecutionPlan
from modules.memory import ConversationMemory, UserProfile, MemoryStore
from modules.tools import ToolRegistry
from modules.execution import (
    AgentState,
    TravelGraphBuilder,
    build_initial_state,
    run_react_agent,
)
from modules.evaluation import (
    PlanEvaluator,
    ConstraintValidator,
    FeedbackIntegrator,
    EvaluationReport,
)

# LLM 模型
from agents.base import (
    create_travel_model,
    ITINERARY_PLANNER_PROMPT,
    ACCOMMODATION_AGENT_PROMPT,
    FOOD_PLANNER_PROMPT,
    BUDGET_AUDITOR_PROMPT,
)

logger = get_logger(__name__)

# ==================== 参考数据 ====================

HOTEL_PRICES: dict[str, dict[str, float]] = {
    "北京": {"经济型": 200, "舒适型": 400, "高档型": 800, "豪华型": 1500},
    "上海": {"经济型": 250, "舒适型": 500, "高档型": 900, "豪华型": 1800},
    "杭州": {"经济型": 180, "舒适型": 350, "高档型": 700, "豪华型": 1200},
    "成都": {"经济型": 150, "舒适型": 300, "高档型": 600, "豪华型": 1000},
    "西安": {"经济型": 140, "舒适型": 280, "高档型": 550, "豪华型": 900},
}

FOOD_BUDGET_PER_DAY: dict[str, int] = {
    "经济型": 120,
    "舒适型": 200,
    "高档型": 350,
    "豪华型": 500,
}

DESTINATION_TIPS: dict[str, str] = {
    "北京": "故宫门票建议提前10天网上预约。",
    "上海": "外滩夜景最佳观赏时间为日落后半小时。",
    "杭州": "西湖游船建议选择下午，可欣赏日落。",
    "成都": "大熊猫基地建议早上7点到达，熊猫最活跃。",
    "西安": "兵马俑建议请讲解员，体验更佳。",
    "南京": "中山陵需要提前预约，周一闭馆。",
    "苏州": "拙政园建议早上开园时入园，人少景美。",
    "重庆": "重庆多坡道，建议穿舒适的鞋子。",
    "广州": "早茶建议早上8点前去，避免排队。",
    "深圳": "世界之窗建议预留一整天时间。",
}


# ==================== 结果模型 ====================

@dataclass
class UnifiedTravelResult:
    """统一旅行规划结果 —— 包含五大模块的完整输出。"""

    success: bool
    destination: str
    days: int
    traveler_count: int
    budget: float
    total_cost: float
    is_within_budget: bool
    preference_level: str

    itinerary: dict = field(default_factory=dict)
    accommodation: dict = field(default_factory=dict)
    food: dict = field(default_factory=dict)
    budget_report: str = ""

    evaluation: Optional[EvaluationReport] = None
    execution_plan: Optional[ExecutionPlan] = None
    execution_log: list[str] = field(default_factory=list)
    revision_count: int = 0

    tips: list = field(default_factory=list)
    errors: list = field(default_factory=list)


# ==================== 统一协调器 ====================

class UnifiedTravelCoordinator:
    """统一旅行规划协调器 —— 四个 ReAct Agent + LangGraph 编排。

    每个 Agent 通过 run_react_agent() 运行标准 ReAct 循环:
    - LLM.bind_tools(tools) 将工具绑定到模型
    - LLM 自主决定调用哪个工具、何时调用
    - 工具结果以 ToolMessage 返回 LLM 形成推理闭环
    - 循环直到 LLM 输出最终答案(无 tool_calls)

    LangGraph 编排流程:
    START → itinerary → [accommodation ‖ food] → budget → evaluate
                                                                ↑        │
                                                                │        ▼
                                                                └─ revise ←─ [conditional]
    """

    def __init__(self) -> None:
        # --- LLM 模型 (所有 Agent 共享) ---
        self.model = create_travel_model()

        # --- 规划模块 ---
        self.decomposer = TaskDecomposer()
        self.plan_generator = PlanGenerator(self.decomposer)

        # --- 记忆模块 ---
        self.memory_store = MemoryStore()
        self.conversation_memory = ConversationMemory()
        self.user_profile: Optional[UserProfile] = None

        # --- 工具调用模块 ---
        self.tool_registry = ToolRegistry()

        # --- 行动执行模块 (LangGraph) ---
        self.graph_builder = TravelGraphBuilder()

        # --- 结果评估模块 ---
        self.validator = ConstraintValidator()
        self.evaluator = PlanEvaluator(self.validator)
        self.feedback_integrator = FeedbackIntegrator()

        self._user_id = "default"

        logger.info("统一协调器初始化完成: 5个模块 + 4个ReAct Agent + LangGraph")

    # ==================== LangGraph 节点处理器 (ReAct Agent) ====================

    def _itinerary_node(self, state: AgentState) -> dict:
        """行程规划 ReAct Agent。

        LLM 自主调用 search_attractions / get_city_highlights / optimize_route
        等工具，规划每日行程。
        """
        logger.info(f"[ReAct] 行程规划师: {state['destination']}, {state['days']}天")

        tools = self.tool_registry.get_by_agent("itinerary")
        user_task = (
            f"请为{state['destination']}规划{state['days']}天的详细旅行行程。\n"
            f"旅行人数: {state['traveler_count']}人\n"
            f"消费偏好: {state['preference_level']}\n"
            f"请依次执行: 1)搜索景点 2)获取城市亮点 3)优化路线 4)给出每日行程安排。\n"
            f"最后以结构化格式输出每日的上午、下午、晚上活动。"
        )

        result = run_react_agent(self.model, tools, ITINERARY_PLANNER_PROMPT, user_task)

        # 结构化成本估算 (用于 LangGraph 状态管理)
        estimated_ticket = state["days"] * 2 * 60 * state["traveler_count"]

        return {
            "itinerary_result": {
                "final_response": result["final_response"],
                "estimated_ticket_cost": estimated_ticket,
            },
        }

    def _accommodation_node(self, state: AgentState) -> dict:
        """住宿协调 ReAct Agent。

        LLM 自主调用 search_hotels / recommend_hotels_by_budget /
        calculate_accommodation_cost 等工具。
        """
        logger.info(f"[ReAct] 住宿协调员: {state['destination']}")

        nights = max(1, state["days"] - 1)
        room_count = max(1, (state["traveler_count"] + 1) // 2)
        city_prices = HOTEL_PRICES.get(state["destination"], HOTEL_PRICES["北京"])
        price_per_night = city_prices.get(state["preference_level"], city_prices["舒适型"])

        tools = self.tool_registry.get_by_agent("accommodation")
        user_task = (
            f"请为{state['destination']}的{nights}晚住宿推荐酒店。\n"
            f"人数: {state['traveler_count']}人 (需{room_count}间房)\n"
            f"预算: 约¥{price_per_night}/间/晚\n"
            f"偏好: {state['preference_level']}\n"
            f"请搜索酒店、按预算推荐、计算住宿总费用。"
        )

        result = run_react_agent(self.model, tools, ACCOMMODATION_AGENT_PROMPT, user_task)

        estimated_cost = price_per_night * nights * room_count

        return {
            "accommodation_result": {
                "final_response": result["final_response"],
                "estimated_cost": estimated_cost,
                "room_count": room_count,
                "price_per_night": price_per_night,
                "nights": nights,
            },
        }

    def _food_node(self, state: AgentState) -> dict:
        """餐饮规划 ReAct Agent。

        LLM 自主调用 search_restaurants_by_city / search_local_cuisine /
        calculate_food_cost / recommend_dining_plan 等工具（美团API）。
        """
        logger.info(f"[ReAct] 餐饮规划员: {state['destination']}, {state['days']}天")

        food_cost = (
            FOOD_BUDGET_PER_DAY.get(state["preference_level"], 200)
            * state["days"]
            * state["traveler_count"]
        )

        tools = self.tool_registry.get_by_agent("food")
        user_task = (
            f"请为{state['destination']}的{state['days']}天旅行规划每日餐饮方案。\n"
            f"人数: {state['traveler_count']}人\n"
            f"餐饮档次: {state['preference_level']} (人均约¥{FOOD_BUDGET_PER_DAY.get(state['preference_level'], 200)}/天)\n"
            f"总餐饮预算参考: ¥{food_cost}\n"
            f"请搜索当地特色美食和餐厅、估算餐饮总费用、制定每日餐饮计划。"
        )

        result = run_react_agent(self.model, tools, FOOD_PLANNER_PROMPT, user_task)

        return {
            "food_result": {
                "final_response": result["final_response"],
                "estimated_cost": food_cost,
            },
        }

    def _budget_node(self, state: AgentState) -> dict:
        """预算审计 ReAct Agent。

        LLM 自主调用 calculate_total_cost / check_budget /
        suggest_savings / generate_budget_report 等工具。

        从上游 Agent 结果中汇总费用，由 LLM 审计并生成报告。
        """
        logger.info(f"[ReAct] 预算审计员: 预算 ¥{state['budget']}")

        # 从上游结果汇总结构化成本
        acc_cost = state.get("accommodation_result", {}).get("estimated_cost", 0)
        ticket_cost = state.get("itinerary_result", {}).get("estimated_ticket_cost", 0)
        food_cost = state.get("food_result", {}).get("estimated_cost", 0)

        tools = self.tool_registry.get_by_agent("budget")
        user_task = (
            f"请审计{state['destination']}{state['days']}天旅行的完整预算:\n"
            f"人数: {state['traveler_count']}人 | 总预算: ¥{state['budget']}\n"
            f"住宿: ¥{acc_cost:.0f} | "
            f"门票: ¥{ticket_cost:.0f} | 餐饮: ¥{food_cost:.0f}\n"
            f"请计算总费用、检查预算、生成完整报告。如超支请给出节省建议。"
        )

        result = run_react_agent(self.model, tools, BUDGET_AUDITOR_PROMPT, user_task)

        total = acc_cost + ticket_cost + food_cost

        return {
            "budget_result": {
                "final_response": result["final_response"],
                "total_cost": total,
                "is_within_budget": total <= state["budget"],
                "remaining": state["budget"] - total,
            },
            "total_cost": total,
            "is_within_budget": total <= state["budget"],
        }

    def _evaluate_node(self, state: AgentState) -> dict:
        """结果评估节点 (规则引擎 + LLM 增强)。

        对完整方案进行 5 维度质量评分和 6 项硬性约束校验。
        """
        logger.info(f"[评估] 综合评分: ¥{state.get('total_cost', 0):.0f} / ¥{state['budget']}")

        evaluation = self.evaluator.evaluate(
            destination=state["destination"],
            days=state["days"],
            traveler_count=state["traveler_count"],
            budget=state["budget"],
            total_cost=state.get("total_cost", 0),
            itinerary=state.get("itinerary_result", {}),
            accommodation=state.get("accommodation_result", {}),
        )
        return {"evaluation_result": evaluation}

    def _revise_node(self, state: AgentState) -> dict:
        """方案修订节点 —— 超支时调整住宿/门票后回到 budget 重新审计。"""
        revision_count = state.get("revision_count", 0) + 1
        budget_result = state.get("budget_result", {})
        overspend = budget_result.get("remaining", 0) * -1
        logger.info(f"[修订] 第{revision_count}次: 超支 ¥{overspend:.0f}")

        updates: dict = {"revision_count": revision_count}

        # 策略1: 降住宿
        acc = dict(state.get("accommodation_result", {}))
        if overspend > 500 and acc.get("estimated_cost", 0) > 300:
            room_count = acc.get("room_count", 1)
            nights = acc.get("nights", max(1, state["days"] - 1))
            new_price = max(150, acc.get("price_per_night", 350) - 100)
            new_cost = new_price * nights * room_count
            acc["estimated_cost"] = new_cost
            acc["price_per_night"] = new_price
            acc["adjusted"] = True
            updates["accommodation_result"] = acc

        # 策略2: 减景点
        elif overspend > 300:
            itin = dict(state.get("itinerary_result", {}))
            current_cost = itin.get("estimated_ticket_cost", 0)
            new_cost = max(0, current_cost - 60 * state["traveler_count"] * state["days"])
            itin["estimated_ticket_cost"] = new_cost
            itin["adjusted"] = True
            updates["itinerary_result"] = itin

        return updates

    # ==================== 核心规划流程 ====================

    def plan_trip(
        self, request: TravelRequest, user_id: str = "default"
    ) -> UnifiedTravelResult:
        """执行完整的旅行规划流程 —— LangGraph 编排五大模块 + 四个 ReAct Agent。"""
        days = (request.end_date - request.start_date).days + 1
        preference_level = (request.preferences or {}).get("preference_level", "舒适型")

        print(f"\n{'='*60}")
        print(f"  统一旅行规划系统 (LangGraph + ReAct Agent)")
        print(f"  目的地: {request.destination} | {days}天 | {request.traveler_count}人 | ¥{request.budget}")
        print(f"{'='*60}\n")

        # --- [记忆模块] 加载用户画像 ---
        self.load_user_profile(user_id)
        log: list[str] = [
            f"[记忆模块] 用户画像加载 (历史: {self.user_profile.total_trips_planned} 次)"
        ]

        # --- [规划模块] 任务分解 ---
        execution_plan = self.plan_generator.generate(
            destination=request.destination,
            days=days,
            traveler_count=request.traveler_count,
            budget=request.budget,
            preference_level=preference_level,
            special_requests=(request.preferences or {}).get("special_requests", ""),
        )
        log.append(
            f"[规划模块] {len(execution_plan.tasks)} 个子任务, "
            f"{len(execution_plan.execution_order)} 个层级"
        )

        try:
            # --- [行动执行模块] 构建初始状态 ---
            initial_state = build_initial_state(
                destination=request.destination,
                origin=request.origin,
                days=days,
                traveler_count=request.traveler_count,
                budget=request.budget,
                preference_level=preference_level,
            )

            # --- [工具调用模块] 注册 4 个 ReAct Agent + 2 个规则节点 ---
            self.graph_builder.register_agents(
                itinerary_agent=self._itinerary_node,
                accommodation_agent=self._accommodation_node,
                food_agent=self._food_node,
                budget_agent=self._budget_node,
                evaluate_node=self._evaluate_node,
                revise_node=self._revise_node,
            )
            graph = self.graph_builder.compile()

            # --- [行动执行模块] 执行 LangGraph 工作流 ---
            print("LangGraph 工作流启动 (ReAct Agent 模式):")
            print("  START → itinerary → [accommodation ‖ food] → budget")
            print("  → evaluate → conditional(OK→END / 超支→revise→budget)\n")

            final_state: AgentState = graph.invoke(initial_state)

            # 提取结果
            total_cost = final_state.get("total_cost", 0.0)
            is_within_budget = final_state.get("is_within_budget", True)
            revision_count = final_state.get("revision_count", 0)

            # --- 打印每个 Agent 的 ReAct 输出摘要 ---
            for agent_key, label in [
                ("itinerary_result", "行程规划师"),
                ("accommodation_result", "住宿协调员"),
                ("food_result", "餐饮规划员"),
                ("budget_result", "预算审计员"),
            ]:
                agent_result = final_state.get(agent_key, {})
                final_resp = agent_result.get("final_response", "")
                if final_resp:
                    preview = final_resp[:120].replace("\n", " ")
                    log.append(f"[ReAct] {label}: {preview}...")

            # --- [结果评估模块] ---
            evaluation = final_state.get("evaluation_result")
            if isinstance(evaluation, EvaluationReport):
                log.append(
                    f"[评估模块] {evaluation.overall_score}/100 ({evaluation.grade}), "
                    f"{len(evaluation.passed_constraints)} 通过 / {len(evaluation.failed_constraints)} 失败"
                )

            # --- [记忆模块] 更新用户画像 ---
            if self.user_profile:
                self.user_profile.update_from_request(
                    destination=request.destination,
                    days=days,
                    traveler_count=request.traveler_count,
                    budget=request.budget,
                    preference_level=preference_level,
                )
                self.save_user_profile()

            # 生成贴士
            tips = self._generate_tips(request.destination)
            if evaluation and isinstance(evaluation, EvaluationReport) and evaluation.suggestions:
                tips.insert(0, f"[质量建议] {evaluation.suggestions[0]}")

            budget_final_resp = final_state.get("budget_result", {}).get("final_response", "")

            result = UnifiedTravelResult(
                success=True,
                destination=request.destination,
                days=days,
                traveler_count=request.traveler_count,
                budget=request.budget,
                total_cost=total_cost,
                is_within_budget=is_within_budget,
                preference_level=preference_level,
                itinerary=final_state.get("itinerary_result", {}),
                accommodation=final_state.get("accommodation_result", {}),
                food=final_state.get("food_result", {}),
                budget_report=budget_final_resp,
                evaluation=evaluation if isinstance(evaluation, EvaluationReport) else None,
                execution_plan=execution_plan,
                execution_log=log,
                revision_count=revision_count,
                tips=tips,
            )

            print(f"\n{'='*60}")
            print(f"  规划完成 (LangGraph + ReAct)")
            print(f"  总费用: ¥{total_cost:.0f} | 预算: {'充足' if is_within_budget else '超支'}")
            if isinstance(evaluation, EvaluationReport):
                print(f"  质量评分: {evaluation.overall_score}/100 ({evaluation.grade})")
            print(f"  修订次数: {revision_count}")
            print(f"{'='*60}\n")

            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return UnifiedTravelResult(
                success=False,
                destination=request.destination,
                days=days,
                traveler_count=request.traveler_count,
                budget=request.budget,
                total_cost=0,
                is_within_budget=False,
                preference_level=preference_level,
                execution_log=log + [f"[错误] {str(e)}"],
                errors=[str(e)],
            )

    # ==================== 记忆模块接口 ====================

    def load_user_profile(self, user_id: str = "default") -> UserProfile:
        self._user_id = user_id
        self.user_profile = self.memory_store.load_profile(user_id)
        return self.user_profile

    def save_user_profile(self) -> None:
        if self.user_profile:
            self.memory_store.save_profile(self.user_profile)

    def add_conversation_turn(self, user_msg: str, assistant_msg: str) -> None:
        self.conversation_memory.add_user_message(user_msg)
        self.conversation_memory.add_assistant_message(assistant_msg)

    def get_memory_context(self) -> str:
        return self.conversation_memory.get_context()

    def save_session(self) -> None:
        self.memory_store.save_conversation(self.conversation_memory)
        if self.user_profile:
            self.memory_store.save_profile(self.user_profile)

    # ==================== 工具/评估接口 ====================

    def list_available_tools(self) -> list[str]:
        return self.tool_registry.list_all()

    def evaluate_plan(self, **kwargs: Any) -> EvaluationReport:
        return self.evaluator.evaluate(**kwargs)

    def collect_feedback(self, plan_id: str, rating: float, comments: str = "") -> dict:
        return self.feedback_integrator.collect_feedback(
            plan_id=plan_id, rating=rating, comments=comments,
        )

    # ==================== 辅助 ====================

    @staticmethod
    def _generate_tips(destination: str) -> list[str]:
        tips = [
            f"出发前请检查{destination}的天气预报，准备合适的衣物。",
            "建议提前预订景点门票，避免排队。",
            "保留一些应急现金，以备不时之需。",
            f"下载{destination}的离线地图，方便导航。",
            "注意保管好个人证件和贵重物品。",
        ]
        if destination in DESTINATION_TIPS:
            tips.append(DESTINATION_TIPS[destination])
        return tips


# 全局统一协调器实例
unified_coordinator = UnifiedTravelCoordinator()
