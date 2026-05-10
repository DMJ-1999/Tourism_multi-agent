"""Main coordinator for travel planning system."""

from datetime import date, datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from data.models import TravelRequest
from agents.itinerary.agent import itinerary_planner
from agents.accommodation.agent import accommodation_agent
from agents.transportation.agent import transportation_agent
from agents.budget.agent import budget_auditor
from utils.logger import get_logger

logger = get_logger()


@dataclass
class TravelPlanResult:
    """旅行规划结果。"""

    success: bool
    destination: str
    days: int
    traveler_count: int
    budget: float
    total_cost: float
    is_within_budget: bool
    itinerary: Dict[str, Any] = field(default_factory=dict)
    accommodation: Dict[str, Any] = field(default_factory=dict)
    transportation: Dict[str, Any] = field(default_factory=dict)
    budget_report: str = ""
    tips: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    savings_tips: list = field(default_factory=list)


class TravelPlanningCoordinator:
    """旅行规划协调器 - 多Agent协作的核心控制器。"""

    def __init__(self):
        self.itinerary_planner = itinerary_planner
        self.accommodation_agent = accommodation_agent
        self.transportation_agent = transportation_agent
        self.budget_auditor = budget_auditor
        self.max_revisions = 3

    def plan_trip(self, request: TravelRequest) -> TravelPlanResult:
        """执行完整的旅行规划流程。"""
        print(f"\n{'='*50}")
        print(f"开始规划旅行: {request.destination}")
        print(f"  人数: {request.traveler_count}人")
        print(f"  预算: {request.budget}元")
        print(f"{'='*50}\n")

        # 计算天数
        days = (request.end_date - request.start_date).days + 1

        # 初始化状态
        state = self._init_state(request, days)

        try:
            # 第一步：行程规划
            print("阶段1: 行程规划...")
            itinerary_result = self._run_itinerary_planning(state)
            state["itinerary_plan"] = itinerary_result

            # 第二步：住宿安排
            print("阶段2: 住宿安排...")
            accommodation_result = self._run_accommodation_planning(state)
            state["accommodation_plan"] = accommodation_result

            # 第三步：交通安排
            print("阶段3: 交通安排...")
            transportation_result = self._run_transportation_planning(state)
            state["transportation_plan"] = transportation_result

            # 第四步：预算审计
            print("阶段4: 预算审计...")
            budget_result = self._run_budget_audit(state)
            state["budget_analysis"] = budget_result

            # 检查是否需要修订（超支时调整方案）
            revision_count = 0
            savings_tips = []

            while not budget_result.get("is_within_budget", True) and revision_count < self.max_revisions:
                revision_count += 1
                overspend = budget_result.get("remaining", 0) * -1
                print(f"\n预算超支 {overspend:.0f}元，进行第{revision_count}次调整...")

                # 根据超支金额决定调整策略
                adjusted = False

                # 策略1: 调整住宿
                if overspend > 500 and state["accommodation_plan"].get("estimated_cost", 0) > 300:
                    accommodation_result, saved = self._adjust_accommodation(state, overspend)
                    state["accommodation_plan"] = accommodation_result
                    if saved > 0:
                        savings_tips.append(f"住宿调整为经济型，节省约{saved:.0f}元")
                        adjusted = True

                # 策略2: 减少景点数量
                if not adjusted and overspend > 300:
                    itinerary_result, saved = self._adjust_itinerary(state, overspend)
                    state["itinerary_plan"] = itinerary_result
                    if saved > 0:
                        savings_tips.append(f"减少付费景点，节省约{saved:.0f}元")
                        adjusted = True

                # 策略3: 调整餐饮预算
                if not adjusted and overspend > 0:
                    food_reduction = min(overspend, days * state["traveler_count"] * 50)
                    savings_tips.append(f"建议选择经济实惠的餐饮，每天可节省约50元/人")
                    adjusted = True

                # 重新审计预算
                budget_result = self._run_budget_audit(state)
                state["budget_analysis"] = budget_result

            # 生成最终结果
            result = self._generate_final_result(state, days, savings_tips)
            print(f"\n{'='*50}")
            print(f"旅行规划完成")
            print(f"  总费用: {result.total_cost:.0f}元")
            print(f"  预算状态: {'充足' if result.is_within_budget else '仍超支'}")
            print(f"{'='*50}\n")

            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return TravelPlanResult(
                success=False,
                destination=request.destination,
                days=days,
                traveler_count=request.traveler_count,
                budget=request.budget,
                total_cost=0,
                is_within_budget=False,
                errors=[str(e)],
            )

    def _init_state(self, request: TravelRequest, days: int) -> Dict[str, Any]:
        """初始化规划状态。"""
        return {
            "destination": request.destination,
            "origin": request.origin,
            "start_date": str(request.start_date),
            "end_date": str(request.end_date),
            "days": days,
            "budget": request.budget,
            "traveler_count": request.traveler_count,
            "preferences": request.preferences or {},
            "revision_count": 0,
        }

    def _run_itinerary_planning(self, state: Dict) -> Dict[str, Any]:
        """执行行程规划。"""
        preferences = state.get("preferences", {})

        result = self.itinerary_planner.plan(
            destination=state["destination"],
            days=state["days"],
            preferences=preferences,
        )

        # 计算门票费用: 每天约2个付费景点，平均60元/人/景点
        estimated_ticket_cost = state["days"] * 2 * 60 * state["traveler_count"]
        result["estimated_ticket_cost"] = estimated_ticket_cost
        print(f"  门票费用估算: {estimated_ticket_cost}元")

        return result

    def _run_accommodation_planning(self, state: Dict) -> Dict[str, Any]:
        """执行住宿规划。"""
        preferences = state.get("preferences", {})

        # 计算住宿晚数
        nights = max(1, state["days"] - 1)

        # 计算房间数（假设2人一间房）
        room_count = max(1, (state["traveler_count"] + 1) // 2)

        # 根据城市设定平均酒店价格
        hotel_prices = {
            "北京": 400,
            "上海": 450,
            "杭州": 350,
            "成都": 300,
            "西安": 280,
            "南京": 320,
            "苏州": 350,
            "重庆": 300,
            "广州": 380,
            "深圳": 400,
        }
        avg_price = hotel_prices.get(state["destination"], 350)

        # 计算实际住宿费用
        estimated_cost = avg_price * nights * room_count
        budget_per_night = avg_price

        result = self.accommodation_agent.find_accommodation(
            destination=state["destination"],
            nights=nights,
            budget_per_night=budget_per_night,
            room_count=room_count,
            preferences=preferences,
        )

        result["estimated_cost"] = estimated_cost
        result["room_count"] = room_count
        result["price_per_night"] = avg_price
        print(f"  住宿费用: {estimated_cost}元 ({nights}晚 x {room_count}间 x {avg_price}元/间/晚)")

        return result

    def _run_transportation_planning(self, state: Dict) -> Dict[str, Any]:
        """执行交通规划。"""
        preferences = state.get("preferences", {})

        result = self.transportation_agent.plan_transportation(
            origin=state["origin"],
            destination=state["destination"],
            days=state["days"],
            traveler_count=state["traveler_count"],
            preferences=preferences,
        )

        # 计算交通费用
        if state["origin"] == state["destination"]:
            # 同城旅游，只有当地交通
            estimated_cost = state["days"] * 50 * state["traveler_count"]  # 每天50元/人
            print(f"  交通费用: {estimated_cost}元 (当地交通)")
        else:
            # 异地旅游，往返 + 当地交通
            transport_prices = {
                ("北京", "上海"): 1100, ("上海", "北京"): 1100,
                ("北京", "杭州"): 1000, ("杭州", "北京"): 1000,
                ("北京", "成都"): 1500, ("成都", "北京"): 1500,
                ("北京", "西安"): 1000, ("西安", "北京"): 1000,
                ("上海", "杭州"): 150, ("杭州", "上海"): 150,
                ("上海", "成都"): 1400, ("成都", "上海"): 1400,
                ("成都", "西安"): 500, ("西安", "成都"): 500,
            }

            route = (state["origin"], state["destination"])
            price_per_person = transport_prices.get(route, 800)

            # 往返交通 + 当地交通
            estimated_cost = price_per_person * 2 * state["traveler_count"]
            estimated_cost += state["days"] * 50 * state["traveler_count"]  # 当地交通
            print(f"  交通费用: {estimated_cost}元 (往返{price_per_person*2}元/人 x {state['traveler_count']}人 + 当地交通)")

        result["estimated_cost"] = estimated_cost
        return result

    def _run_budget_audit(self, state: Dict) -> Dict[str, Any]:
        """执行预算审计。"""
        accommodation_cost = state.get("accommodation_plan", {}).get("estimated_cost", 0)
        transport_cost = state.get("transportation_plan", {}).get("estimated_cost", 0)
        ticket_cost = state.get("itinerary_plan", {}).get("estimated_ticket_cost", 0)

        result = self.budget_auditor.audit_budget(
            destination=state["destination"],
            days=state["days"],
            traveler_count=state["traveler_count"],
            budget=state["budget"],
            accommodation_cost=accommodation_cost,
            transport_cost=transport_cost,
            ticket_cost=ticket_cost,
        )

        print(f"  总费用: {result.get('total_cost', 0):.0f}元")
        print(f"  预算: {state['budget']:.0f}元")
        print(f"  状态: {'预算充足' if result.get('is_within_budget') else '预算超支'}")

        return result

    def _adjust_accommodation(self, state: Dict, overspend: float) -> tuple:
        """调整住宿以节省费用。"""
        current_cost = state.get("accommodation_plan", {}).get("estimated_cost", 0)
        room_count = state.get("accommodation_plan", {}).get("room_count", 1)
        nights = max(1, state["days"] - 1)

        # 降低住宿档次，每间房每晚节省100元
        new_price = max(150, state.get("accommodation_plan", {}).get("price_per_night", 350) - 100)
        new_cost = new_price * nights * room_count
        saved = current_cost - new_cost

        result = state.get("accommodation_plan", {}).copy()
        result["estimated_cost"] = new_cost
        result["price_per_night"] = new_price
        result["adjusted"] = True

        print(f"  住宿调整: {current_cost:.0f}元 -> {new_cost:.0f}元 (节省{saved:.0f}元)")

        return result, saved

    def _adjust_itinerary(self, state: Dict, overspend: float) -> tuple:
        """调整行程以节省费用。"""
        current_cost = state.get("itinerary_plan", {}).get("estimated_ticket_cost", 0)

        # 减少付费景点数量，每天减少1个
        new_cost = max(0, current_cost - 60 * state["traveler_count"] * state["days"])
        saved = current_cost - new_cost

        result = state.get("itinerary_plan", {}).copy()
        result["estimated_ticket_cost"] = new_cost
        result["adjusted"] = True

        print(f"  门票调整: {current_cost:.0f}元 -> {new_cost:.0f}元 (节省{saved:.0f}元)")

        return result, saved

    def _generate_final_result(self, state: Dict, days: int, savings_tips: list = None) -> TravelPlanResult:
        """生成最终规划结果。"""
        budget_analysis = state.get("budget_analysis", {})
        tips = self._generate_tips(state)

        # 添加节省建议到贴士
        if savings_tips:
            tips.extend(savings_tips)

        return TravelPlanResult(
            success=True,
            destination=state["destination"],
            days=days,
            traveler_count=state["traveler_count"],
            budget=state["budget"],
            total_cost=budget_analysis.get("total_cost", 0),
            is_within_budget=budget_analysis.get("is_within_budget", True),
            itinerary=state.get("itinerary_plan", {}),
            accommodation=state.get("accommodation_plan", {}),
            transportation=state.get("transportation_plan", {}),
            budget_report=budget_analysis.get("report", ""),
            tips=tips,
            savings_tips=savings_tips or [],
        )

    def _generate_tips(self, state: Dict) -> list:
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


# 全局协调器实例
coordinator = TravelPlanningCoordinator()
