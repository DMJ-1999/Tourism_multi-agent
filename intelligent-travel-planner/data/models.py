"""Data models for travel planning system."""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from enum import Enum


class TravelRequest(BaseModel):
    """User travel request."""

    destination: str = Field(description="旅行目的地")
    start_date: date = Field(description="出发日期")
    end_date: date = Field(description="返回日期")
    traveler_count: int = Field(default=1, description="旅行人数")
    budget: float = Field(description="总预算（元）")
    origin: str = Field(default="北京", description="出发城市")
    preferences: Optional[dict] = Field(default=None, description="用户偏好")


class Attraction(BaseModel):
    """Attraction model."""

    id: str = Field(description="景点ID")
    name: str = Field(description="景点名称")
    location: str = Field(description="景点位置")
    category: str = Field(description="景点类别")
    tags: List[str] = Field(default_factory=list, description="标签")
    ticket_price: float = Field(description="门票价格")
    opening_hours: str = Field(description="开放时间")
    rating: float = Field(description="评分")
    description: str = Field(description="景点描述")
    visit_duration: float = Field(default=2.0, description="建议游览时长（小时）")


class Hotel(BaseModel):
    """Hotel model."""

    id: str = Field(description="酒店ID")
    name: str = Field(description="酒店名称")
    location: str = Field(description="酒店位置")
    star_rating: int = Field(description="星级")
    price_per_night: float = Field(description="每晚价格")
    rating: float = Field(description="评分")
    facilities: List[str] = Field(default_factory=list, description="设施")
    available_rooms: int = Field(description="可用房间数")
    address: str = Field(default="", description="详细地址")


class Flight(BaseModel):
    """Flight model."""

    id: str = Field(description="航班ID")
    airline: str = Field(description="航空公司")
    flight_number: str = Field(description="航班号")
    departure_city: str = Field(description="出发城市")
    arrival_city: str = Field(description="到达城市")
    departure_time: str = Field(description="起飞时间")
    arrival_time: str = Field(description="到达时间")
    price: float = Field(description="票价")
    seat_class: str = Field(default="经济舱", description="舱位等级")


class Train(BaseModel):
    """Train model."""

    id: str = Field(description="车次ID")
    train_number: str = Field(description="车次号")
    train_type: str = Field(description="列车类型")
    departure_city: str = Field(description="出发城市")
    arrival_city: str = Field(description="到达城市")
    departure_time: str = Field(description="发车时间")
    arrival_time: str = Field(description="到达时间")
    price: float = Field(description="票价")
    seat_type: str = Field(default="二等座", description="座位类型")


class DailyItinerary(BaseModel):
    """Daily itinerary model."""

    day: int = Field(description="第几天")
    date: str = Field(description="日期")
    morning: Optional[str] = Field(default=None, description="上午活动")
    afternoon: Optional[str] = Field(default=None, description="下午活动")
    evening: Optional[str] = Field(default=None, description="晚上活动")
    meals: Optional[dict] = Field(default=None, description="餐饮安排")
    notes: Optional[str] = Field(default=None, description="注意事项")


class BudgetItem(BaseModel):
    """Budget item model."""

    category: str = Field(description="费用类别")
    item: str = Field(description="费用项目")
    amount: float = Field(description="金额")
    notes: Optional[str] = Field(default=None, description="备注")


class TravelPlan(BaseModel):
    """Complete travel plan model."""

    destination: str = Field(description="目的地")
    start_date: str = Field(description="开始日期")
    end_date: str = Field(description="结束日期")
    traveler_count: int = Field(description="旅行人数")
    daily_itineraries: List[DailyItinerary] = Field(default_factory=list, description="每日行程")
    hotels: List[Hotel] = Field(default_factory=list, description="推荐酒店")
    flights: List[Flight] = Field(default_factory=list, description="航班信息")
    trains: List[Train] = Field(default_factory=list, description="火车票信息")
    budget_items: List[BudgetItem] = Field(default_factory=list, description="预算明细")
    total_cost: float = Field(default=0.0, description="总费用")
    tips: List[str] = Field(default_factory=list, description="旅行贴士")
