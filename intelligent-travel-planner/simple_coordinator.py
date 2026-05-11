"""四Agent协作系统 - 行程规划师 + 住宿协调员 + 餐饮推荐 + 预算审计员

使用Qwen LLM作为智能体的大脑，实现真正的自然语言理解
"""

from datetime import date
from typing import Dict, Any, List
from dataclasses import dataclass, field

from data.models import TravelRequest
from utils.llm import qwen_brain


@dataclass
class DailySchedule:
    """每日行程"""
    day: int
    date: str
    morning: Dict[str, Any]
    afternoon: Dict[str, Any]
    lunch: Dict[str, Any]
    dinner: Dict[str, Any]
    ticket_cost: float
    food_cost: float


@dataclass
class TravelResult:
    """旅行规划结果"""
    success: bool
    destination: str
    days: int
    traveler_count: int
    budget: float
    spend_all_budget: bool = False  # 是否要花光预算

    # 行程规划师输出
    daily_schedules: List[DailySchedule] = field(default_factory=list)
    attractions: list = field(default_factory=list)
    ticket_cost: float = 0.0

    # 住宿协调员输出
    hotels: list = field(default_factory=list)
    selected_hotel: Dict = field(default_factory=dict)
    accommodation_cost: float = 0.0

    # 餐饮推荐输出
    restaurants: list = field(default_factory=list)
    food_cost: float = 0.0

    # 预算审计员输出
    total_cost: float = 0.0
    is_within_budget: bool = True
    remaining_budget: float = 0.0
    budget_adjustments: list = field(default_factory=list)

    agent_steps: list = field(default_factory=list)


class Coordinator:
    """
    四Agent协作系统：

    1. 行程规划师 - 高德API搜索景点，生成每日行程
    2. 住宿协调员 - 高德API搜索酒店，根据预算选择
    3. 餐饮推荐 - 美团API推荐餐厅
    4. 预算审计员 - 计算总费用，根据用户意图调整
    """

    # 酒店价格参考（元/晚）
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

    def __init__(self):
        from utils.amap_api import amap_api
        from utils.meituan_api import meituan_api
        self.amap = amap_api
        self.meituan = meituan_api
        self.steps = []

    def plan_trip(self, request: TravelRequest) -> TravelResult:
        """执行四Agent协作规划"""
        print("\n" + "="*60)
        print(f"【开始规划】{request.destination} {request.traveler_count}人 预算{request.budget}元")
        print("="*60)

        self.steps = []
        days = (request.end_date - request.start_date).days + 1

        # 从用户偏好中提取意图信息
        preferences = request.preferences or {}
        spend_all = preferences.get("spend_all_budget", False) or self._detect_spend_all_intent(preferences)
        preference_level = preferences.get("preference_level", "舒适型")

        print(f"[用户偏好] 花光预算: {spend_all}, 消费档次: {preference_level}")

        try:
            # Agent 1: 行程规划师
            attractions, daily_schedules, ticket_cost = self._run_itinerary_agent(
                destination=request.destination,
                days=days,
                start_date=request.start_date,
                traveler_count=request.traveler_count,
            )

            # Agent 2: 住宿协调员
            hotels, selected_hotel, accommodation_cost = self._run_accommodation_agent(
                destination=request.destination,
                days=days,
                traveler_count=request.traveler_count,
                preference_level=preference_level,
            )

            # Agent 3: 餐饮推荐
            restaurants, food_cost = self._run_food_agent(
                destination=request.destination,
                days=days,
                traveler_count=request.traveler_count,
                preference_level=preference_level,
            )

            # Agent 4: 预算审计员
            result = self._run_budget_agent(
                destination=request.destination,
                days=days,
                traveler_count=request.traveler_count,
                budget=request.budget,
                spend_all=spend_all,
                preference_level=preference_level,
                ticket_cost=ticket_cost,
                accommodation_cost=accommodation_cost,
                food_cost=food_cost,
                hotels=hotels,
                selected_hotel=selected_hotel,
                attractions=attractions,
                daily_schedules=daily_schedules,
                restaurants=restaurants,
            )

            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return TravelResult(
                success=False,
                destination=request.destination,
                days=days,
                traveler_count=request.traveler_count,
                budget=request.budget,
            )

    def _detect_spend_all_intent(self, preferences: dict) -> bool:
        """检测用户是否想花光预算"""
        if not preferences:
            return False
        # 检测关键词
        keywords = ["花光", "全部花掉", "用完", "清空预算", "花完预算"]
        if preferences.get("intent"):
            intent = preferences["intent"].lower()
            return any(k in intent for k in keywords)
        return False

    def _run_itinerary_agent(self, destination: str, days: int, start_date: date, traveler_count: int) -> tuple:
        """Agent 1: 行程规划师"""
        print(f"\n【Agent 1: 行程规划师】搜索景点...")
        print("-"*40)

        # 调用高德API
        pois = self.amap.search_scenic_spots(destination, page_size=20)
        if not pois:
            pois = self._get_mock_attractions(destination)

        # 处理景点数据
        attractions = []
        for poi in pois:
            biz_ext = poi.get("biz_ext", {})
            cost = biz_ext.get("cost", "")

            # 处理价格（高德API可能返回空数组[]）
            if isinstance(cost, list):
                cost = "价格未知"
            elif not cost:
                cost = "价格未知"

            attractions.append({
                "id": poi.get("id", ""),
                "name": poi.get("name", "未知"),
                "address": poi.get("address", ""),
                "rating": self._safe_float(biz_ext.get("rating", 0)),
                "cost": cost,
            })

        attractions.sort(key=lambda x: x["rating"], reverse=True)

        # 生成每日行程
        daily_schedules = []
        attraction_idx = 0
        total_ticket = 0

        for day in range(1, days + 1):
            current_date = start_date + __import__('datetime').timedelta(days=day-1)

            morning = attractions[attraction_idx] if attraction_idx < len(attractions) else {"name": "自由活动", "cost": "0"}
            attraction_idx += 1
            afternoon = attractions[attraction_idx] if attraction_idx < len(attractions) else {"name": "自由活动", "cost": "0"}
            attraction_idx += 1

            # 计算门票
            day_ticket = 0
            for spot in [morning, afternoon]:
                if spot.get("name") != "自由活动":
                    cost_str = spot.get("cost", "50")
                    try:
                        cost_num = ''.join(filter(str.isdigit, str(cost_str)))
                        day_ticket += int(cost_num) if cost_num else 50
                    except:
                        day_ticket += 50
            day_ticket *= traveler_count
            total_ticket += day_ticket

            daily_schedules.append(DailySchedule(
                day=day,
                date=current_date.strftime("%Y-%m-%d"),
                morning=morning,
                afternoon=afternoon,
                lunch={"name": "待推荐"},
                dinner={"name": "待推荐"},
                ticket_cost=day_ticket,
                food_cost=200 * traveler_count,
            ))

        print(f"  找到{len(attractions)}个景点，门票总计{total_ticket}元")
        self.steps.append({"agent": "行程规划师", "action": "搜索景点+生成行程", "result": f"{len(attractions)}个景点"})

        return attractions, daily_schedules, total_ticket

    def _run_accommodation_agent(
        self, destination: str, days: int, traveler_count: int, preference_level: str = "舒适型"
    ) -> tuple:
        """Agent 2: 住宿协调员"""
        print(f"\n【Agent 2: 住宿协调员】搜索酒店...")
        print("-"*40)

        nights = max(1, days - 1)
        rooms = max(1, (traveler_count + 1) // 2)

        # 调用高德API
        hotel_pois = self.amap.search_hotels(destination, page_size=10)
        if not hotel_pois:
            hotel_pois = self._get_mock_hotels(destination)

        # 处理酒店数据
        hotels = []
        for poi in hotel_pois:
            biz_ext = poi.get("biz_ext", {})
            cost = biz_ext.get("cost", "")

            # 处理价格显示
            if isinstance(cost, list) or not cost:
                # 使用参考价格
                prices = self.HOTEL_PRICES.get(destination, self.HOTEL_PRICES["北京"])
                cost = f"¥{prices['舒适型']}起"

            hotels.append({
                "id": poi.get("id", ""),
                "name": poi.get("name", "未知"),
                "address": poi.get("address", ""),
                "rating": self._safe_float(biz_ext.get("rating", 0)),
                "cost": cost,
            })

        hotels.sort(key=lambda x: x["rating"], reverse=True)

        # 根据用户偏好选择酒店档次
        prices = self.HOTEL_PRICES.get(destination, self.HOTEL_PRICES["北京"])
        selected_price = prices.get(preference_level, prices["舒适型"])
        selected_hotel = {
            "name": hotels[0]["name"] if hotels else "推荐酒店",
            "price_per_night": selected_price,
            "level": preference_level,
        }
        accommodation_cost = selected_hotel["price_per_night"] * nights * rooms

        print(f"  找到{len(hotels)}家酒店，选择{preference_level}，住宿预算{accommodation_cost}元")
        self.steps.append({
            "agent": "住宿协调员",
            "action": f"搜索酒店+选择{preference_level}",
            "result": f"{len(hotels)}家酒店"
        })

        return hotels, selected_hotel, accommodation_cost

    def _run_food_agent(
        self, destination: str, days: int, traveler_count: int, preference_level: str = "舒适型"
    ) -> tuple:
        """Agent 3: 餐饮推荐 - 使用美团开放平台API搜索真实餐厅数据"""
        print(f"\n【Agent 3: 餐饮推荐】搜索餐厅...")
        print("-"*40)

        # 调用美团开放平台API搜索餐厅（未配置API时自动降级到参考数据）
        restaurants = self.meituan.search_restaurants(destination, page_size=10)

        # 根据用户偏好选择餐饮档次
        food_budget_per_person = self.FOOD_BUDGET.get(preference_level, self.FOOD_BUDGET["舒适型"])
        food_cost = food_budget_per_person * days * traveler_count

        source = "美团API" if self.meituan.is_available() else "参考数据"
        print(f"  找到{len(restaurants)}家餐厅({source})，选择{preference_level}餐饮，预算{food_cost}元")
        self.steps.append({
            "agent": "餐饮推荐",
            "action": f"美团API搜索餐厅+选择{preference_level}",
            "result": f"{len(restaurants)}家餐厅({source})"
        })

        return restaurants, food_cost

    def _run_budget_agent(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        spend_all: bool,
        preference_level: str = "舒适型",
        ticket_cost: float = 0,
        accommodation_cost: float = 0,
        food_cost: float = 0,
        hotels: list = None,
        selected_hotel: dict = None,
        attractions: list = None,
        daily_schedules: list = None,
        restaurants: list = None,
    ) -> TravelResult:
        """Agent 4: 预算审计员 - 使用LLM进行智能预算规划"""
        print(f"\n【Agent 4: 预算审计员】计算费用...")
        print("-"*40)

        nights = max(1, days - 1)
        rooms = max(1, (traveler_count + 1) // 2)
        adjustments = []

        # 获取价格档位
        prices = self.HOTEL_PRICES.get(destination, self.HOTEL_PRICES["北京"])

        # 初始计算
        total = ticket_cost + accommodation_cost + food_cost
        remaining = budget - total

        print(f"  初始费用: 门票{ticket_cost} + 住宿{accommodation_cost} + 餐饮{food_cost} = {total}元")
        print(f"  剩余预算: {remaining}元")

        # 如果用户想花光预算，使用LLM智能分配
        if spend_all and remaining > 500:
            print(f"\n  用户要求花光预算，开始智能升级...")

            # 使用LLM生成个性化升级建议
            llm_adjustments = self._get_llm_budget_suggestions(
                destination=destination,
                days=days,
                traveler_count=traveler_count,
                budget=budget,
                remaining=remaining,
                current_hotel_price=selected_hotel.get("price_per_night", prices["舒适型"]),
                current_food_budget=self.FOOD_BUDGET["舒适型"],
                prices=prices,
            )

            if llm_adjustments:
                # 验证LLM建议是否在预算范围内
                new_total = ticket_cost + llm_adjustments.get("new_accommodation_cost", 0) + llm_adjustments.get("new_food_cost", 0)

                if new_total <= budget:
                    # 在预算范围内，使用LLM建议
                    adjustments.extend(llm_adjustments["suggestions"])
                    accommodation_cost = llm_adjustments.get("new_accommodation_cost", accommodation_cost)
                    food_cost = llm_adjustments.get("new_food_cost", food_cost)
                    selected_hotel["level"] = llm_adjustments.get("hotel_level", "舒适型")
                    selected_hotel["price_per_night"] = llm_adjustments.get("new_hotel_price", selected_hotel.get("price_per_night"))
                else:
                    # LLM建议超出预算，使用规则方法
                    print(f"  [警告] LLM建议超出预算({new_total}元)，使用规则方法")
                    rule_result = self._rule_based_upgrade(
                        remaining=remaining,
                        nights=nights,
                        rooms=rooms,
                        days=days,
                        traveler_count=traveler_count,
                        prices=prices,
                    )
                    adjustments.extend(rule_result["suggestions"])
                    accommodation_cost = rule_result.get("new_accommodation_cost", accommodation_cost)
                    food_cost = rule_result.get("new_food_cost", food_cost)
                    selected_hotel["level"] = rule_result.get("hotel_level", "舒适型")
                    selected_hotel["price_per_night"] = rule_result.get("new_hotel_price", selected_hotel.get("price_per_night"))
            else:
                # 降级到规则方法
                rule_result = self._rule_based_upgrade(
                    remaining=remaining,
                    nights=nights,
                    rooms=rooms,
                    days=days,
                    traveler_count=traveler_count,
                    prices=prices,
                )
                adjustments.extend(rule_result["suggestions"])
                accommodation_cost = rule_result.get("new_accommodation_cost", accommodation_cost)
                food_cost = rule_result.get("new_food_cost", food_cost)
                selected_hotel["level"] = rule_result.get("hotel_level", "舒适型")
                selected_hotel["price_per_night"] = rule_result.get("new_hotel_price", selected_hotel.get("price_per_night"))

            total = ticket_cost + accommodation_cost + food_cost
            remaining = budget - total

            print(f"  升级后总费用: {total}元，剩余{remaining}元")

        # 最终计算
        is_within_budget = total <= budget

        print(f"\n  最终总费用: {total}元")
        print(f"  预算状态: {'充足' if is_within_budget else '超支'}")

        self.steps.append({
            "agent": "预算审计员",
            "action": "计算费用" + ("+LLM智能升级" if adjustments else ""),
            "result": f"总费用{total}元，{'剩余' if is_within_budget else '超支'}{abs(remaining)}元"
        })

        return TravelResult(
            success=True,
            destination=destination,
            days=days,
            traveler_count=traveler_count,
            budget=budget,
            spend_all_budget=spend_all,
            daily_schedules=daily_schedules,
            attractions=attractions,
            ticket_cost=ticket_cost,
            hotels=hotels,
            selected_hotel=selected_hotel,
            accommodation_cost=accommodation_cost,
            restaurants=restaurants,
            food_cost=food_cost,
            total_cost=total,
            is_within_budget=is_within_budget,
            remaining_budget=remaining,
            budget_adjustments=adjustments,
            agent_steps=self.steps,
        )

    def _get_llm_budget_suggestions(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        remaining: float,
        current_hotel_price: float,
        current_food_budget: float,
        prices: dict,
    ) -> Dict[str, Any]:
        """使用LLM生成个性化预算升级建议"""
        if not qwen_brain.is_available():
            return {}

        nights = max(1, days - 1)
        rooms = max(1, (traveler_count + 1) // 2)

        prompt = f"""作为旅行预算规划师，用户希望花光全部预算以获得更好的体验。

当前情况：
- 目的地: {destination}
- 旅行天数: {days}天，{nights}晚
- 人数: {traveler_count}人，需要{rooms}间房
- 总预算: {budget}元
- 当前已用预算: {budget - remaining}元（门票等固定支出）
- 剩余可分配预算: {remaining}元
- 当前住宿: {current_hotel_price}元/晚
- 当前餐饮预算: {current_food_budget}元/人/天

住宿价格参考：
- 经济型: {prices["经济型"]}元/晚
- 舒适型: {prices["舒适型"]}元/晚
- 高档型: {prices["高档型"]}元/晚
- 豪华型: {prices["豪华型"]}元/晚

计算公式：
- 住宿总费用 = 酒店价格/晚 × {nights}晚 × {rooms}间
- 餐饮总费用 = 餐饮预算/人/天 × {days}天 × {traveler_count}人
- 总费用 = 住宿总费用 + 餐饮总费用 + {budget - remaining}元（固定支出）

用户明确要求花光预算，请升级住宿和餐饮档次：
1. 新的总费用应接近{budget}元（允许小额剩余作为备用金）
2. 建议升级住宿档次（如从舒适型升级到高档型）
3. 建议升级餐饮标准（增加人均餐饮预算）
4. 给出具体的升级建议和带来的体验提升

请给出预算分配建议，以JSON格式返回：
```json
{{
    "new_hotel_price": 建议的酒店价格（元/晚，应高于当前{current_hotel_price}元）,
    "new_food_budget": 建议的餐饮预算（元/人/天，应高于当前{current_food_budget}元）,
    "hotel_level": "建议的酒店档次（高档型或豪华型）",
    "suggestions": ["升级建议1", "升级建议2", ...]
}}
```"""

        try:
            result = qwen_brain.parse_json_response(prompt)
            if not result:
                return {}

            new_hotel_price = float(result.get("new_hotel_price", current_hotel_price))
            new_food_budget = float(result.get("new_food_budget", current_food_budget))
            suggestions = result.get("suggestions", [])

            return {
                "new_hotel_price": new_hotel_price,
                "new_food_budget": new_food_budget,
                "new_accommodation_cost": new_hotel_price * nights * rooms,
                "new_food_cost": new_food_budget * days * traveler_count,
                "hotel_level": result.get("hotel_level", "舒适型"),
                "suggestions": suggestions,
            }
        except Exception as e:
            print(f"[错误] LLM预算建议生成失败: {e}")
            return {}

    def _rule_based_upgrade(
        self,
        remaining: float,
        nights: int,
        rooms: int,
        days: int,
        traveler_count: int,
        prices: dict,
        current_accommodation_cost: float = 0,
        current_food_cost: float = 0,
    ) -> Dict[str, Any]:
        """规则驱动的预算升级（降级方案）"""
        # 住宿占60%，餐饮占40%
        extra_hotel = int(remaining * 0.6)
        extra_food = remaining - extra_hotel

        base_hotel_price = prices["舒适型"]
        base_food_budget = self.FOOD_BUDGET["舒适型"]

        new_hotel_price = base_hotel_price + (extra_hotel // nights // rooms)
        new_food_per_person = base_food_budget + (extra_food // days // traveler_count)

        # 确保不超过高档型价格
        new_hotel_price = min(new_hotel_price, prices["高档型"])
        new_food_per_person = min(new_food_per_person, self.FOOD_BUDGET["高档型"])

        # 确定档次名称
        if new_hotel_price >= prices["豪华型"] * 0.9:
            level = "豪华型"
        elif new_hotel_price >= prices["高档型"] * 0.9:
            level = "高档型"
        else:
            level = "舒适型优选"

        suggestions = [
            f"住宿升级为{level}（约{new_hotel_price}元/晚）",
            f"餐饮升级为优选标准（约{new_food_per_person}元/人/天）",
        ]

        return {
            "suggestions": suggestions,
            "new_hotel_price": new_hotel_price,
            "new_food_budget": new_food_per_person,
            "new_accommodation_cost": new_hotel_price * nights * rooms,
            "new_food_cost": new_food_per_person * days * traveler_count,
            "hotel_level": level,
        }

    def _safe_float(self, value) -> float:
        try:
            return float(value)
        except:
            return 0.0

    def _get_mock_attractions(self, destination: str) -> list:
        return []

    def _get_mock_hotels(self, destination: str) -> list:
        return []


# 全局实例
coordinator = Coordinator()
