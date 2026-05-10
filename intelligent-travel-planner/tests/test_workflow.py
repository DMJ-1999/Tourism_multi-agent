"""Tests for travel planning workflow."""

import pytest
from datetime import date, timedelta

from data.models import TravelRequest
from data.mock_data import mock_data
from orchestration.coordinator import coordinator


class TestMockData:
    """测试模拟数据"""

    def test_search_attractions_beijing(self):
        """测试北京景点搜索"""
        attractions = mock_data.search_attractions("北京")
        assert len(attractions) > 0
        assert any(a.name == "故宫博物院" for a in attractions)

    def test_search_hotels_shanghai(self):
        """测试上海酒店搜索"""
        hotels = mock_data.search_hotels("上海")
        assert len(hotels) > 0
        assert all(h.location == "上海" for h in hotels)

    def test_search_flights(self):
        """测试航班搜索"""
        flights = mock_data.search_flights("北京", "上海")
        assert len(flights) > 0
        assert all(f.departure_city == "北京" for f in flights)
        assert all(f.arrival_city == "上海" for f in flights)

    def test_search_trains(self):
        """测试火车搜索"""
        trains = mock_data.search_trains("北京", "上海")
        assert len(trains) > 0
        assert all(t.departure_city == "北京" for t in trains)

    def test_get_attraction_by_id(self):
        """测试根据ID获取景点"""
        attraction = mock_data.get_attraction_by_id("bj001")
        assert attraction is not None
        assert attraction.name == "故宫博物院"

    def test_get_hotel_by_id(self):
        """测试根据ID获取酒店"""
        hotel = mock_data.get_hotel_by_id("h_bj001")
        assert hotel is not None
        assert "希尔顿" in hotel.name


class TestItineraryTools:
    """测试行程规划工具"""

    def test_search_attractions_tool(self):
        """测试景点搜索工具"""
        from agents.itinerary.tools import search_attractions

        result = search_attractions.invoke({"location": "北京"})
        assert "故宫" in result or "天坛" in result

    def test_get_attraction_details_tool(self):
        """测试景点详情工具"""
        from agents.itinerary.tools import get_attraction_details

        result = get_attraction_details.invoke({"attraction_id": "bj001"})
        assert "故宫" in result

    def test_optimize_route_tool(self):
        """测试路线优化工具"""
        from agents.itinerary.tools import optimize_route

        result = optimize_route.invoke({
            "attraction_ids": ["bj001", "bj002", "bj003"],
            "days": 2,
        })
        assert "第1天" in result
        assert "第2天" in result


class TestAccommodationTools:
    """测试住宿工具"""

    def test_search_hotels_tool(self):
        """测试酒店搜索工具"""
        from agents.accommodation.tools import search_hotels

        result = search_hotels.invoke({"location": "北京"})
        assert "酒店" in result

    def test_calculate_cost_tool(self):
        """测试费用计算工具"""
        from agents.accommodation.tools import calculate_accommodation_cost

        result = calculate_accommodation_cost.invoke({
            "price_per_night": 500,
            "nights": 3,
            "room_count": 1,
        })
        assert "1500" in result


class TestTransportationTools:
    """测试交通工具"""

    def test_search_flights_tool(self):
        """测试航班搜索工具"""
        from agents.transportation.tools import search_flights

        result = search_flights.invoke({
            "departure_city": "北京",
            "arrival_city": "上海",
        })
        assert "航班" in result

    def test_search_trains_tool(self):
        """测试火车搜索工具"""
        from agents.transportation.tools import search_trains

        result = search_trains.invoke({
            "departure_city": "北京",
            "arrival_city": "上海",
        })
        assert "火车" in result or "高铁" in result

    def test_estimate_local_transport_tool(self):
        """测试当地交通估算工具"""
        from agents.transportation.tools import estimate_local_transport

        result = estimate_local_transport.invoke({
            "city": "北京",
            "days": 3,
        })
        assert "地铁" in result


class TestBudgetTools:
    """测试预算工具"""

    def test_calculate_total_cost_tool(self):
        """测试总费用计算工具"""
        from agents.budget.tools import calculate_total_cost

        result = calculate_total_cost.invoke({
            "accommodation_cost": 1500,
            "transport_cost": 1000,
            "ticket_cost": 300,
            "food_cost": 600,
            "other_cost": 200,
        })
        assert "3600" in result

    def test_check_budget_tool(self):
        """测试预算检查工具"""
        from agents.budget.tools import check_budget

        result = check_budget.invoke({
            "total_cost": 3000,
            "budget": 5000,
        })
        assert "通过" in result or "充足" in result

    def test_check_budget_overspend(self):
        """测试超支情况"""
        from agents.budget.tools import check_budget

        result = check_budget.invoke({
            "total_cost": 6000,
            "budget": 5000,
        })
        assert "超支" in result


class TestTravelPlanningCoordinator:
    """测试旅行规划协调器"""

    @pytest.fixture
    def sample_request(self):
        """示例旅行请求"""
        return TravelRequest(
            destination="北京",
            origin="上海",
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=33),
            traveler_count=2,
            budget=5000.0,
            preferences={
                "interests": ["历史文化"],
            },
        )

    def test_init_state(self, sample_request):
        """测试状态初始化"""
        state = coordinator._init_state(sample_request, days=4)

        assert state["destination"] == "北京"
        assert state["origin"] == "上海"
        assert state["days"] == 4
        assert state["budget"] == 5000.0
        assert state["traveler_count"] == 2

    def test_generate_tips(self, sample_request):
        """测试贴士生成"""
        state = coordinator._init_state(sample_request, days=4)
        tips = coordinator._generate_tips(state)

        assert len(tips) > 0
        assert any("北京" in tip for tip in tips)


class TestIntegration:
    """集成测试"""

    @pytest.mark.skip(reason="需要API密钥")
    def test_full_planning_workflow(self):
        """测试完整规划流程"""
        request = TravelRequest(
            destination="上海",
            origin="北京",
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=33),
            traveler_count=1,
            budget=3000.0,
        )

        result = coordinator.plan_trip(request)

        assert result.success
        assert result.destination == "上海"
        assert result.total_cost > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
