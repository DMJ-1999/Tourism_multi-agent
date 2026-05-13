"""统一协调器 —— 整合五大 AI Agent 模块的旅行规划系统。

模块架构：
  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
  │ 1.规划模块   │  │ 2.记忆模块   │  │ 3.工具调用模块   │
  │ (任务分解)   │  │ (对话/画像)  │  │ (注册/绑定/执行) │
  └──────┬───────┘  └──────┬──────┘  └────────┬────────┘
         │                 │                   │
         └─────────────────┼───────────────────┘
                           │
              ┌────────────┴────────────┐
              │  4.行动执行模块          │
              │  (LangGraph 编排)        │
              └────────────┬────────────┘
                           │
              ┌────────────┴────────────┐
              │  5.结果评估模块          │
              │  (多因子评分/约束校验)   │
              └─────────────────────────┘
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from data.models import TravelRequest
from utils.llm import qwen_brain
from utils.logger import get_logger

# 五大模块
from modules.planning import TaskDecomposer, PlanGenerator, ExecutionPlan, SubTask, TaskStatus
from modules.memory import ConversationMemory, UserProfile, MemoryStore
from modules.tools import ToolRegistry, ToolExecutor, create_agent_with_tools
from modules.execution import AgentOrchestrator, build_execution_state, ExecutionState, ExecutionPhase
from modules.evaluation import PlanEvaluator, ConstraintValidator, FeedbackIntegrator, EvaluationReport

# 现有智能体类（复用已有逻辑）
from agents.itinerary.agent import itinerary_planner
from agents.accommodation.agent import accommodation_agent
from agents.transportation.agent import transportation_agent
from agents.budget.agent import budget_auditor

logger = get_logger(__name__)


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

    # 各智能体输出
    itinerary: dict = field(default_factory=dict)
    accommodation: dict = field(default_factory=dict)
    transportation: dict = field(default_factory=dict)
    food: dict = field(default_factory=dict)
    budget_report: str = ""

    # 评估报告
    evaluation: Optional[EvaluationReport] = None

    # 执行追踪
    execution_plan: Optional[ExecutionPlan] = None
    execution_log: list[str] = field(default_factory=list)
    revision_count: int = 0

    # 贴士与建议
    tips: list = field(default_factory=list)
    savings_tips: list = field(default_factory=list)
    errors: list = field(default_factory=list)


class UnifiedTravelCoordinator:
    """统一旅行规划协调器 —— 整合五大 AI Agent 模块。

    执行流程：
    1. [规划模块] 任务分解 → 生成 ExecutionPlan
    2. [记忆模块] 加载用户画像，注入对话上下文
    3. [工具调用模块] 为各智能体绑定工具
    4. [行动执行模块] 按 ExecutionPlan 编排执行
    5. [结果评估模块] 多维度质量评分 + 约束校验
    """

    # 酒店价格参考
    HOTEL_PRICES = {
        "北京": {"经济型": 200, "舒适型": 400, "高档型": 800, "豪华型": 1500},
        "上海": {"经济型": 250, "舒适型": 500, "高档型": 900, "豪华型": 1800},
        "杭州": {"经济型": 180, "舒适型": 350, "高档型": 700, "豪华型": 1200},
        "成都": {"经济型": 150, "舒适型": 300, "高档型": 600, "豪华型": 1000},
        "西安": {"经济型": 140, "舒适型": 280, "高档型": 550, "豪华型": 900},
    }

    # 餐饮人均预算参考（元/人/天）
    FOOD_BUDGET = {
        "经济型": 120,
        "舒适型": 200,
        "高档型": 350,
        "豪华型": 500,
    }

    def __init__(self) -> None:
        # --- 规划模块 ---
        self.decomposer = TaskDecomposer()
        self.plan_generator = PlanGenerator(self.decomposer)

        # --- 记忆模块 ---
        self.memory_store = MemoryStore()
        self.conversation_memory = ConversationMemory()
        self.user_profile: Optional[UserProfile] = None

        # --- 工具调用模块 ---
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)

        # --- 行动执行模块 ---
        self.orchestrator = AgentOrchestrator()

        # --- 结果评估模块 ---
        self.validator = ConstraintValidator()
        self.evaluator = PlanEvaluator(self.validator)
        self.feedback_integrator = FeedbackIntegrator()

        # --- 现有智能体 ---
        self.itinerary_planner = itinerary_planner
        self.accommodation_agent = accommodation_agent
        self.transportation_agent = transportation_agent
        self.budget_auditor = budget_auditor

        # --- 用户画像（延迟加载） ---
        self._user_id = "default"

        logger.info("统一协调器初始化完成: 5个模块已集成")

    # ==================== 记忆模块接口 ====================

    def load_user_profile(self, user_id: str = "default") -> UserProfile:
        """加载用户画像。"""
        self._user_id = user_id
        self.user_profile = self.memory_store.load_profile(user_id)
        logger.info(f"用户画像加载: {user_id}, 历史规划 {self.user_profile.total_trips_planned} 次")
        return self.user_profile

    def save_user_profile(self) -> None:
        """保存用户画像。"""
        if self.user_profile:
            self.memory_store.save_profile(self.user_profile)

    def add_conversation_turn(self, user_msg: str, assistant_msg: str) -> None:
        """记录一轮对话。"""
        self.conversation_memory.add_user_message(user_msg)
        self.conversation_memory.add_assistant_message(assistant_msg)

    def get_memory_context(self) -> str:
        """获取对话记忆上下文（注入 LLM 用）。"""
        return self.conversation_memory.get_context()

    def save_session(self) -> None:
        """持久化当前会话。"""
        self.memory_store.save_conversation(self.conversation_memory)
        if self.user_profile:
            self.memory_store.save_profile(self.user_profile)

    # ==================== 规划模块接口 ====================

    def decompose_task(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        preference_level: str = "舒适型",
        special_requests: str = "",
    ) -> ExecutionPlan:
        """使用规划模块分解任务。"""
        return self.plan_generator.generate(
            destination=destination,
            days=days,
            traveler_count=traveler_count,
            budget=budget,
            preference_level=preference_level,
            special_requests=special_requests,
        )

    # ==================== 核心规划流程 ====================

    def plan_trip(self, request: TravelRequest, user_id: str = "default") -> UnifiedTravelResult:
        """执行完整的旅行规划流程 —— 五大模块协同工作。"""
        log: list[str] = []

        # 计算天数
        days = (request.end_date - request.start_date).days + 1
        preference_level = (request.preferences or {}).get("preference_level", "舒适型")
        special_requests = (request.preferences or {}).get("special_requests", "")

        print(f"\n{'='*60}")
        print(f"  统一旅行规划系统启动")
        print(f"  目的地: {request.destination} | {days}天 | {request.traveler_count}人 | ¥{request.budget}")
        print(f"{'='*60}\n")

        # --- [记忆模块] 加载用户画像 ---
        self.load_user_profile(user_id)
        log.append(f"[记忆模块] 用户画像加载完成 (历史: {self.user_profile.total_trips_planned} 次)")

        # --- [规划模块] 任务分解 ---
        execution_plan = self.decompose_task(
            destination=request.destination,
            days=days,
            traveler_count=request.traveler_count,
            budget=request.budget,
            preference_level=preference_level,
            special_requests=special_requests,
        )
        log.append(f"[规划模块] 生成 {len(execution_plan.tasks)} 个子任务, {len(execution_plan.execution_order)} 个执行层级")

        # --- [行动执行模块] 构建执行状态 ---
        state = build_execution_state(
            destination=request.destination,
            origin=request.origin,
            days=days,
            traveler_count=request.traveler_count,
            budget=request.budget,
            preference_level=preference_level,
            spend_all_budget=(request.preferences or {}).get("spend_all_budget", False),
            special_requests=special_requests,
        )
        log.append(f"[执行模块] 执行状态初始化, {len(self.orchestrator.nodes)} 个工作流节点")

        try:
            # 阶段1: 行程规划
            print("阶段1: 行程规划...")
            itinerary_result = self._run_itinerary(state)
            state["itinerary_plan"] = itinerary_result
            log.append(f"[执行] 行程规划完成")

            # 阶段2: 住宿安排
            print("阶段2: 住宿安排...")
            accommodation_result = self._run_accommodation(state)
            state["accommodation_plan"] = accommodation_result
            log.append(f"[执行] 住宿安排完成")

            # 阶段3: 交通规划
            print("阶段3: 交通规划...")
            transportation_result = self._run_transportation(state)
            state["transportation_plan"] = transportation_result
            log.append(f"[执行] 交通规划完成")

            # 阶段4: 餐饮推荐（隐含在预算审计中）
            state["food_plan"] = {
                "food_cost": self.FOOD_BUDGET.get(preference_level, 200) * days * request.traveler_count,
                "preference_level": preference_level,
            }
            log.append(f"[执行] 餐饮预算设定完成")

            # 阶段5: 预算审计
            print("阶段4: 预算审计...")
            budget_result = self._run_budget_audit(state)
            state["budget_analysis"] = budget_result
            state["is_within_budget"] = budget_result.get("is_within_budget", True)
            state["total_cost"] = budget_result.get("total_cost", 0.0)
            log.append(f"[执行] 预算审计完成 (预算内: {state['is_within_budget']})")

            # 预算修订循环
            revision_count = 0
            savings_tips: list[str] = []

            while not state.get("is_within_budget", True) and revision_count < 3:
                revision_count += 1
                overspend = budget_result.get("remaining", 0) * -1
                print(f"\n预算超支 ¥{overspend:.0f}，第{revision_count}次修订...")
                log.append(f"[修订] 第{revision_count}次: 超支 ¥{overspend:.0f}")

                adjusted = False

                if overspend > 500 and state["accommodation_plan"].get("estimated_cost", 0) > 300:
                    accommodation_result, saved = self._adjust_accommodation(state, overspend)
                    state["accommodation_plan"] = accommodation_result
                    if saved > 0:
                        savings_tips.append(f"住宿调整为经济型，节省约 ¥{saved:.0f}")
                        adjusted = True

                if not adjusted and overspend > 300:
                    itinerary_result, saved = self._adjust_itinerary(state, overspend)
                    state["itinerary_plan"] = itinerary_result
                    if saved > 0:
                        savings_tips.append(f"减少付费景点，节省约 ¥{saved:.0f}")
                        adjusted = True

                if not adjusted:
                    savings_tips.append("建议选择经济实惠的餐饮，每天可节省约50元/人")

                budget_result = self._run_budget_audit(state)
                state["budget_analysis"] = budget_result
                state["is_within_budget"] = budget_result.get("is_within_budget", True)
                state["total_cost"] = budget_result.get("total_cost", state.get("total_cost", 0))

            # --- [结果评估模块] 质量评估 ---
            print("阶段5: 方案质量评估...")
            evaluation = self.evaluator.evaluate(
                destination=request.destination,
                days=days,
                traveler_count=request.traveler_count,
                budget=request.budget,
                total_cost=state.get("total_cost", 0),
                itinerary=state.get("itinerary_plan", {}),
                accommodation=state.get("accommodation_plan", {}),
                preferences=request.preferences,
            )
            log.append(
                f"[评估模块] 综合评分 {evaluation.overall_score}/100 ({evaluation.grade}), "
                f"{len(evaluation.passed_constraints)} 约束通过, {len(evaluation.failed_constraints)} 失败"
            )

            # --- [记忆模块] 更新用户画像 ---
            if self.user_profile:
                self.user_profile.update_from_request(
                    destination=request.destination,
                    days=days,
                    traveler_count=request.traveler_count,
                    budget=request.budget,
                    preference_level=preference_level,
                    interests=(request.preferences or {}).get("interests"),
                )
                self.save_user_profile()

            # 生成最终结果
            tips = self._generate_tips(state)
            tips.extend(savings_tips)
            if evaluation.suggestions:
                tips.append(f"[质量建议] {evaluation.suggestions[0]}")

            result = UnifiedTravelResult(
                success=True,
                destination=request.destination,
                days=days,
                traveler_count=request.traveler_count,
                budget=request.budget,
                total_cost=state.get("total_cost", 0),
                is_within_budget=state.get("is_within_budget", True),
                preference_level=preference_level,
                itinerary=state.get("itinerary_plan", {}),
                accommodation=state.get("accommodation_plan", {}),
                transportation=state.get("transportation_plan", {}),
                food=state.get("food_plan", {}),
                budget_report=budget_result.get("report", ""),
                evaluation=evaluation,
                execution_plan=execution_plan,
                execution_log=log,
                revision_count=revision_count,
                tips=tips,
                savings_tips=savings_tips,
            )

            print(f"\n{'='*60}")
            print(f"  规划完成")
            print(f"  总费用: ¥{result.total_cost:.0f} | 预算: {'充足' if result.is_within_budget else '超支'}")
            print(f"  质量评分: {evaluation.overall_score}/100 ({evaluation.grade})")
            print(f"{'='*60}\n")

            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            log.append(f"[错误] {str(e)}")
            return UnifiedTravelResult(
                success=False,
                destination=request.destination,
                days=days,
                traveler_count=request.traveler_count,
                budget=request.budget,
                total_cost=0,
                is_within_budget=False,
                preference_level=preference_level,
                execution_log=log,
                errors=[str(e)],
            )

    # ==================== 各阶段执行方法 ====================

    def _run_itinerary(self, state: ExecutionState) -> dict:
        """执行行程规划阶段。"""
        preferences = {"preferences": {"interests": state.get("special_requests", "")}}
        result = self.itinerary_planner.plan(
            destination=state["destination"],
            days=state["days"],
            preferences=preferences,
        )
        estimated_ticket = state["days"] * 2 * 60 * state["traveler_count"]
        result["estimated_ticket_cost"] = estimated_ticket
        return result

    def _run_accommodation(self, state: ExecutionState) -> dict:
        """执行住宿安排阶段。"""
        nights = max(1, state["days"] - 1)
        room_count = max(1, (state["traveler_count"] + 1) // 2)
        city_prices = self.HOTEL_PRICES.get(state["destination"], self.HOTEL_PRICES["北京"])
        price_per_night = city_prices.get(state["preference_level"], city_prices["舒适型"])

        result = self.accommodation_agent.find_accommodation(
            destination=state["destination"],
            nights=nights,
            budget_per_night=price_per_night,
            room_count=room_count,
            preferences={},
        )
        result["estimated_cost"] = price_per_night * nights * room_count
        result["room_count"] = room_count
        result["price_per_night"] = price_per_night
        return result

    def _run_transportation(self, state: ExecutionState) -> dict:
        """执行交通规划阶段。"""
        result = self.transportation_agent.plan_transportation(
            origin=state["origin"],
            destination=state["destination"],
            days=state["days"],
            traveler_count=state["traveler_count"],
            preferences={},
        )

        if state["origin"] == state["destination"]:
            cost = state["days"] * 50 * state["traveler_count"]
        else:
            transport_prices = {
                ("北京", "上海"): 1100, ("上海", "北京"): 1100,
                ("北京", "杭州"): 1000, ("杭州", "北京"): 1000,
                ("北京", "成都"): 1500, ("成都", "北京"): 1500,
                ("北京", "西安"): 1000, ("西安", "北京"): 1000,
                ("上海", "杭州"): 150, ("杭州", "上海"): 150,
                ("上海", "成都"): 1400, ("成都", "上海"): 1400,
                ("成都", "西安"): 500, ("西安", "成都"): 500,
            }
            price_per = transport_prices.get(
                (state["origin"], state["destination"]), 800
            )
            cost = price_per * 2 * state["traveler_count"]  # 往返
            cost += state["days"] * 50 * state["traveler_count"]  # 当地交通

        result["estimated_cost"] = cost
        return result

    def _run_budget_audit(self, state: ExecutionState) -> dict:
        """执行预算审计阶段。"""
        accommodation_cost = state.get("accommodation_plan", {}).get("estimated_cost", 0)
        transport_cost = state.get("transportation_plan", {}).get("estimated_cost", 0)
        ticket_cost = state.get("itinerary_plan", {}).get("estimated_ticket_cost", 0)
        food_cost = state.get("food_plan", {}).get("food_cost", 0)

        result = self.budget_auditor.audit_budget(
            destination=state["destination"],
            days=state["days"],
            traveler_count=state["traveler_count"],
            budget=state["budget"],
            accommodation_cost=accommodation_cost,
            transport_cost=transport_cost,
            ticket_cost=ticket_cost,
        )

        total = accommodation_cost + transport_cost + ticket_cost + food_cost
        result["total_cost"] = total
        result["remaining"] = state["budget"] - total
        result["is_within_budget"] = total <= state["budget"]

        return result

    # ==================== 预算修订方法 ====================

    def _adjust_accommodation(self, state: ExecutionState, overspend: float) -> tuple:
        """下调住宿以节省费用。"""
        current = state.get("accommodation_plan", {}).copy()
        current_cost = current.get("estimated_cost", 0)
        room_count = current.get("room_count", 1)
        nights = max(1, state["days"] - 1)
        new_price = max(150, current.get("price_per_night", 350) - 100)
        new_cost = new_price * nights * room_count
        saved = current_cost - new_cost
        current["estimated_cost"] = new_cost
        current["price_per_night"] = new_price
        current["adjusted"] = True
        return current, saved

    def _adjust_itinerary(self, state: ExecutionState, overspend: float) -> tuple:
        """减少付费景点以节省费用。"""
        current = state.get("itinerary_plan", {}).copy()
        current_cost = current.get("estimated_ticket_cost", 0)
        new_cost = max(0, current_cost - 60 * state["traveler_count"] * state["days"])
        saved = current_cost - new_cost
        current["estimated_ticket_cost"] = new_cost
        current["adjusted"] = True
        return current, saved

    # ==================== 辅助方法 ====================

    def _generate_tips(self, state: ExecutionState) -> list:
        """生成旅行贴士。"""
        destination = state["destination"]
        tips = [
            f"出发前请检查{destination}的天气预报，准备合适的衣物。",
            "建议提前预订景点门票，避免排队。",
            "保留一些应急现金，以备不时之需。",
            f"下载{destination}的离线地图，方便导航。",
            "注意保管好个人证件和贵重物品。",
        ]

        destination_tips = {
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

        if destination in destination_tips:
            tips.append(destination_tips[destination])

        return tips

    # ==================== 工具调用模块接口 ====================

    def list_available_tools(self) -> list[str]:
        """列出所有可用工具。"""
        return self.tool_registry.list_all()

    def get_tool_call_stats(self) -> dict:
        """获取工具调用统计。"""
        return self.tool_executor.get_call_stats()

    def create_agent_with_bound_tools(
        self,
        agent_name: str,
        system_prompt: str,
    ) -> dict:
        """使用工具调用模块创建绑定工具的智能体。"""
        tools = self.tool_registry.get_tools_for_agent_binding(agent_name)
        return create_agent_with_tools(
            agent_name=agent_name,
            system_prompt=system_prompt,
            tools=tools,
        )

    # ==================== 评估模块接口 ====================

    def evaluate_plan(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        total_cost: float,
        itinerary: dict,
        accommodation: dict,
        preferences: Optional[dict] = None,
    ) -> EvaluationReport:
        """对已有的旅行方案进行评估。"""
        return self.evaluator.evaluate(
            destination=destination,
            days=days,
            traveler_count=traveler_count,
            budget=budget,
            total_cost=total_cost,
            itinerary=itinerary,
            accommodation=accommodation,
            preferences=preferences,
        )

    def collect_feedback(self, plan_id: str, rating: float, comments: str = "") -> dict:
        """收集用户反馈。"""
        return self.feedback_integrator.collect_feedback(
            plan_id=plan_id,
            rating=rating,
            comments=comments,
        )


# 全局统一协调器实例
unified_coordinator = UnifiedTravelCoordinator()
