"""Mock data provider for travel planning system."""

from typing import List, Optional
from .models import Attraction, Hotel, Flight, Train


class MockDataProvider:
    """Provider for mock travel data."""

    def __init__(self):
        self.attractions = self._init_attractions()
        self.hotels = self._init_hotels()
        self.flights = self._init_flights()
        self.trains = self._init_trains()

    def _init_attractions(self) -> List[Attraction]:
        """Initialize mock attractions data."""
        return [
            # 北京景点
            Attraction(
                id="bj001",
                name="故宫博物院",
                location="北京",
                category="历史文化",
                tags=["历史文化", "建筑", "博物馆", "必去"],
                ticket_price=60.0,
                opening_hours="08:30-17:00",
                rating=4.9,
                description="中国明清两代的皇家宫殿，世界上现存规模最大的宫殿型建筑",
                visit_duration=4.0,
            ),
            Attraction(
                id="bj002",
                name="天坛公园",
                location="北京",
                category="历史文化",
                tags=["历史文化", "建筑", "公园"],
                ticket_price=15.0,
                opening_hours="06:00-22:00",
                rating=4.7,
                description="明清皇帝祭天的场所，世界文化遗产",
                visit_duration=2.5,
            ),
            Attraction(
                id="bj003",
                name="颐和园",
                location="北京",
                category="历史文化",
                tags=["历史文化", "园林", "湖泊"],
                ticket_price=30.0,
                opening_hours="06:30-18:00",
                rating=4.8,
                description="中国现存规模最大的皇家园林",
                visit_duration=3.5,
            ),
            Attraction(
                id="bj004",
                name="八达岭长城",
                location="北京",
                category="历史文化",
                tags=["历史文化", "世界遗产", "徒步"],
                ticket_price=40.0,
                opening_hours="07:30-17:30",
                rating=4.8,
                description="万里长城的精华段落，世界文化遗产",
                visit_duration=4.0,
            ),
            Attraction(
                id="bj005",
                name="南锣鼓巷",
                location="北京",
                category="美食购物",
                tags=["美食", "购物", "胡同", "文化"],
                ticket_price=0.0,
                opening_hours="全天",
                rating=4.3,
                description="北京最古老的街区之一，充满老北京风情",
                visit_duration=2.0,
            ),
            Attraction(
                id="bj006",
                name="798艺术区",
                location="北京",
                category="艺术文化",
                tags=["艺术", "文化", "拍照"],
                ticket_price=0.0,
                opening_hours="10:00-18:00",
                rating=4.5,
                description="废弃工厂改造的当代艺术聚集地",
                visit_duration=2.5,
            ),
            # 上海景点
            Attraction(
                id="sh001",
                name="外滩",
                location="上海",
                category="城市风光",
                tags=["城市风光", "建筑", "夜景", "必去"],
                ticket_price=0.0,
                opening_hours="全天",
                rating=4.8,
                description="上海的标志性景观，欣赏万国建筑群",
                visit_duration=1.5,
            ),
            Attraction(
                id="sh002",
                name="东方明珠",
                location="上海",
                category="城市风光",
                tags=["城市风光", "地标", "观景"],
                ticket_price=220.0,
                opening_hours="08:00-21:30",
                rating=4.6,
                description="上海地标建筑，俯瞰城市全景",
                visit_duration=2.0,
            ),
            Attraction(
                id="sh003",
                name="豫园",
                location="上海",
                category="历史文化",
                tags=["历史文化", "园林", "美食"],
                ticket_price=40.0,
                opening_hours="09:00-16:30",
                rating=4.5,
                description="江南古典园林，周边有城隍庙小吃街",
                visit_duration=2.0,
            ),
            Attraction(
                id="sh004",
                name="田子坊",
                location="上海",
                category="美食购物",
                tags=["美食", "购物", "文艺"],
                ticket_price=0.0,
                opening_hours="10:00-21:00",
                rating=4.4,
                description="文艺小店和创意市集聚集地",
                visit_duration=2.0,
            ),
            # 杭州景点
            Attraction(
                id="hz001",
                name="西湖",
                location="杭州",
                category="自然风光",
                tags=["自然风光", "湖泊", "世界遗产", "必去"],
                ticket_price=0.0,
                opening_hours="全天",
                rating=4.9,
                description="杭州的灵魂，中国最美的湖泊之一",
                visit_duration=4.0,
            ),
            Attraction(
                id="hz002",
                name="灵隐寺",
                location="杭州",
                category="宗教文化",
                tags=["宗教", "文化", "古刹"],
                ticket_price=75.0,
                opening_hours="07:00-18:00",
                rating=4.7,
                description="江南著名古刹，环境清幽",
                visit_duration=2.5,
            ),
            Attraction(
                id="hz003",
                name="河坊街",
                location="杭州",
                category="美食购物",
                tags=["美食", "购物", "老街"],
                ticket_price=0.0,
                opening_hours="全天",
                rating=4.3,
                description="杭州历史文化街区，小吃云集",
                visit_duration=1.5,
            ),
            # 成都景点
            Attraction(
                id="cd001",
                name="大熊猫繁育研究基地",
                location="成都",
                category="自然生态",
                tags=["熊猫", "自然", "亲子", "必去"],
                ticket_price=55.0,
                opening_hours="07:30-18:00",
                rating=4.8,
                description="观赏国宝大熊猫的最佳地点",
                visit_duration=3.0,
            ),
            Attraction(
                id="cd002",
                name="宽窄巷子",
                location="成都",
                category="历史文化",
                tags=["历史文化", "美食", "购物"],
                ticket_price=0.0,
                opening_hours="全天",
                rating=4.5,
                description="成都历史文化街区，体验老成都生活",
                visit_duration=2.0,
            ),
            Attraction(
                id="cd003",
                name="锦里古街",
                location="成都",
                category="美食购物",
                tags=["美食", "古街", "文化"],
                ticket_price=0.0,
                opening_hours="全天",
                rating=4.4,
                description="成都版清明上河图，三国文化与成都民俗",
                visit_duration=1.5,
            ),
            # 西安景点
            Attraction(
                id="xa001",
                name="秦始皇兵马俑博物馆",
                location="西安",
                category="历史文化",
                tags=["历史文化", "世界遗产", "必去"],
                ticket_price=120.0,
                opening_hours="08:30-18:00",
                rating=4.9,
                description="世界第八大奇迹，震撼的历史遗迹",
                visit_duration=3.0,
            ),
            Attraction(
                id="xa002",
                name="大雁塔",
                location="西安",
                category="历史文化",
                tags=["历史文化", "佛教", "建筑"],
                ticket_price=40.0,
                opening_hours="08:00-18:30",
                rating=4.6,
                description="唐代佛教建筑艺术的杰作",
                visit_duration=1.5,
            ),
            Attraction(
                id="xa003",
                name="回民街",
                location="西安",
                category="美食购物",
                tags=["美食", "小吃", "文化"],
                ticket_price=0.0,
                opening_hours="全天",
                rating=4.3,
                description="西安著名美食街区，各种特色小吃",
                visit_duration=1.5,
            ),
        ]

    def _init_hotels(self) -> List[Hotel]:
        """Initialize mock hotels data."""
        return [
            # 北京酒店
            Hotel(
                id="h_bj001",
                name="北京王府井希尔顿酒店",
                location="北京",
                star_rating=5,
                price_per_night=1200.0,
                rating=4.7,
                facilities=["免费WiFi", "健身房", "游泳池", "餐厅", "停车场"],
                available_rooms=10,
                address="王府井东街8号",
            ),
            Hotel(
                id="h_bj002",
                name="北京前门建国饭店",
                location="北京",
                star_rating=4,
                price_per_night=600.0,
                rating=4.5,
                facilities=["免费WiFi", "餐厅", "停车场"],
                available_rooms=15,
                address="前门东大街3号",
            ),
            Hotel(
                id="h_bj003",
                name="北京胡同客栈",
                location="北京",
                star_rating=3,
                price_per_night=300.0,
                rating=4.2,
                facilities=["免费WiFi", "早餐"],
                available_rooms=8,
                address="南锣鼓巷附近",
            ),
            # 上海酒店
            Hotel(
                id="h_sh001",
                name="上海外滩华尔道夫酒店",
                location="上海",
                star_rating=5,
                price_per_night=2000.0,
                rating=4.9,
                facilities=["免费WiFi", "健身房", "游泳池", "餐厅", "SPA"],
                available_rooms=5,
                address="中山东一路2号",
            ),
            Hotel(
                id="h_sh002",
                name="上海新天地朗廷酒店",
                location="上海",
                star_rating=5,
                price_per_night=1500.0,
                rating=4.7,
                facilities=["免费WiFi", "健身房", "游泳池", "餐厅"],
                available_rooms=12,
                address="新天地马当路99号",
            ),
            Hotel(
                id="h_sh003",
                name="上海豫园老街客栈",
                location="上海",
                star_rating=3,
                price_per_night=350.0,
                rating=4.1,
                facilities=["免费WiFi", "早餐"],
                available_rooms=6,
                address="豫园附近",
            ),
            # 杭州酒店
            Hotel(
                id="h_hz001",
                name="杭州西湖国宾馆",
                location="杭州",
                star_rating=5,
                price_per_night=1800.0,
                rating=4.8,
                facilities=["免费WiFi", "健身房", "游泳池", "餐厅", "园林"],
                available_rooms=8,
                address="西湖区杨公堤18号",
            ),
            Hotel(
                id="h_hz002",
                name="杭州西湖边精品酒店",
                location="杭州",
                star_rating=4,
                price_per_night=700.0,
                rating=4.6,
                facilities=["免费WiFi", "餐厅", "停车场"],
                available_rooms=10,
                address="西湖区北山街",
            ),
            Hotel(
                id="h_hz003",
                name="杭州河坊街客栈",
                location="杭州",
                star_rating=3,
                price_per_night=280.0,
                rating=4.3,
                facilities=["免费WiFi", "早餐"],
                available_rooms=12,
                address="河坊街附近",
            ),
            # 成都酒店
            Hotel(
                id="h_cd001",
                name="成都香格里拉大酒店",
                location="成都",
                star_rating=5,
                price_per_night=1000.0,
                rating=4.7,
                facilities=["免费WiFi", "健身房", "游泳池", "餐厅"],
                available_rooms=15,
                address="锦江区滨江东路9号",
            ),
            Hotel(
                id="h_cd002",
                name="成都春熙路亚朵酒店",
                location="成都",
                star_rating=4,
                price_per_night=450.0,
                rating=4.5,
                facilities=["免费WiFi", "早餐", "停车场"],
                available_rooms=20,
                address="春熙路附近",
            ),
            Hotel(
                id="h_cd003",
                name="成都宽窄巷子民宿",
                location="成都",
                star_rating=3,
                price_per_night=250.0,
                rating=4.4,
                facilities=["免费WiFi", "厨房"],
                available_rooms=5,
                address="宽窄巷子附近",
            ),
            # 西安酒店
            Hotel(
                id="h_xa001",
                name="西安威斯汀大酒店",
                location="西安",
                star_rating=5,
                price_per_night=900.0,
                rating=4.6,
                facilities=["免费WiFi", "健身房", "游泳池", "餐厅"],
                available_rooms=18,
                address="曲江新区慈恩路66号",
            ),
            Hotel(
                id="h_xa002",
                name="西安钟楼饭店",
                location="西安",
                star_rating=4,
                price_per_night=400.0,
                rating=4.3,
                facilities=["免费WiFi", "餐厅", "停车场"],
                available_rooms=25,
                address="钟楼附近",
            ),
            Hotel(
                id="h_xa003",
                name="西安回民街客栈",
                location="西安",
                star_rating=2,
                price_per_night=150.0,
                rating=4.0,
                facilities=["免费WiFi"],
                available_rooms=10,
                address="回民街附近",
            ),
        ]

    def _init_flights(self) -> List[Flight]:
        """Initialize mock flights data."""
        return [
            # 北京出发
            Flight(
                id="f001",
                airline="中国国际航空",
                flight_number="CA1234",
                departure_city="北京",
                arrival_city="上海",
                departure_time="08:00",
                arrival_time="10:30",
                price=800.0,
                seat_class="经济舱",
            ),
            Flight(
                id="f002",
                airline="东方航空",
                flight_number="MU5678",
                departure_city="北京",
                arrival_city="上海",
                departure_time="14:00",
                arrival_time="16:30",
                price=750.0,
                seat_class="经济舱",
            ),
            Flight(
                id="f003",
                airline="中国国际航空",
                flight_number="CA1501",
                departure_city="北京",
                arrival_city="杭州",
                departure_time="09:00",
                arrival_time="11:30",
                price=700.0,
                seat_class="经济舱",
            ),
            Flight(
                id="f004",
                airline="四川航空",
                flight_number="3U8888",
                departure_city="北京",
                arrival_city="成都",
                departure_time="07:30",
                arrival_time="10:30",
                price=900.0,
                seat_class="经济舱",
            ),
            Flight(
                id="f005",
                airline="中国国际航空",
                flight_number="CA1201",
                departure_city="北京",
                arrival_city="西安",
                departure_time="08:30",
                arrival_time="10:30",
                price=650.0,
                seat_class="经济舱",
            ),
            # 上海出发
            Flight(
                id="f006",
                airline="东方航空",
                flight_number="MU5101",
                departure_city="上海",
                arrival_city="北京",
                departure_time="08:00",
                arrival_time="10:30",
                price=850.0,
                seat_class="经济舱",
            ),
            Flight(
                id="f007",
                airline="中国国际航空",
                flight_number="CA1701",
                departure_city="上海",
                arrival_city="成都",
                departure_time="09:30",
                arrival_time="12:30",
                price=950.0,
                seat_class="经济舱",
            ),
            Flight(
                id="f008",
                airline="东方航空",
                flight_number="MU5673",
                departure_city="上海",
                arrival_city="西安",
                departure_time="10:00",
                arrival_time="12:30",
                price=700.0,
                seat_class="经济舱",
            ),
            # 其他城市
            Flight(
                id="f009",
                airline="四川航空",
                flight_number="3U8989",
                departure_city="成都",
                arrival_city="北京",
                departure_time="14:00",
                arrival_time="17:00",
                price=850.0,
                seat_class="经济舱",
            ),
            Flight(
                id="f010",
                airline="中国国际航空",
                flight_number="CA1202",
                departure_city="西安",
                arrival_city="北京",
                departure_time="12:00",
                arrival_time="14:00",
                price=600.0,
                seat_class="经济舱",
            ),
        ]

    def _init_trains(self) -> List[Train]:
        """Initialize mock trains data."""
        return [
            # 北京出发高铁
            Train(
                id="t001",
                train_number="G1",
                train_type="高铁",
                departure_city="北京",
                arrival_city="上海",
                departure_time="07:00",
                arrival_time="11:30",
                price=553.0,
                seat_type="二等座",
            ),
            Train(
                id="t002",
                train_number="G5",
                train_type="高铁",
                departure_city="北京",
                arrival_city="上海",
                departure_time="09:00",
                arrival_time="13:30",
                price=553.0,
                seat_type="二等座",
            ),
            Train(
                id="t003",
                train_number="G35",
                train_type="高铁",
                departure_city="北京",
                arrival_city="杭州",
                departure_time="08:00",
                arrival_time="13:00",
                price=538.0,
                seat_type="二等座",
            ),
            Train(
                id="t004",
                train_number="G89",
                train_type="高铁",
                departure_city="北京",
                arrival_city="西安",
                departure_time="07:30",
                arrival_time="12:30",
                price=515.0,
                seat_type="二等座",
            ),
            Train(
                id="t005",
                train_number="G307",
                train_type="高铁",
                departure_city="北京",
                arrival_city="成都",
                departure_time="08:00",
                arrival_time="16:00",
                price=864.0,
                seat_type="二等座",
            ),
            # 上海出发高铁
            Train(
                id="t006",
                train_number="G2",
                train_type="高铁",
                departure_city="上海",
                arrival_city="北京",
                departure_time="08:00",
                arrival_time="12:30",
                price=553.0,
                seat_type="二等座",
            ),
            Train(
                id="t007",
                train_number="G7331",
                train_type="高铁",
                departure_city="上海",
                arrival_city="杭州",
                departure_time="07:30",
                arrival_time="08:30",
                price=73.0,
                seat_type="二等座",
            ),
            Train(
                id="t008",
                train_number="G1974",
                train_type="高铁",
                departure_city="上海",
                arrival_city="成都",
                departure_time="06:10",
                arrival_time="15:38",
                price=781.0,
                seat_type="二等座",
            ),
            # 其他城市
            Train(
                id="t009",
                train_number="G1701",
                train_type="高铁",
                departure_city="成都",
                arrival_city="西安",
                departure_time="07:30",
                arrival_time="11:00",
                price=263.0,
                seat_type="二等座",
            ),
            Train(
                id="t010",
                train_number="G90",
                train_type="高铁",
                departure_city="西安",
                arrival_city="北京",
                departure_time="13:00",
                arrival_time="18:00",
                price=515.0,
                seat_type="二等座",
            ),
        ]

    def search_attractions(
        self,
        location: str,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Attraction]:
        """Search attractions by location and filters."""
        results = [a for a in self.attractions if a.location == location]

        if categories:
            results = [a for a in results if a.category in categories]

        if tags:
            results = [a for a in results if any(tag in a.tags for tag in tags)]

        return results

    def search_hotels(
        self,
        location: str,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        star_rating: Optional[int] = None,
    ) -> List[Hotel]:
        """Search hotels by location and filters."""
        results = [h for h in self.hotels if h.location == location]

        if max_price:
            results = [h for h in results if h.price_per_night <= max_price]

        if min_rating:
            results = [h for h in results if h.rating >= min_rating]

        if star_rating:
            results = [h for h in results if h.star_rating == star_rating]

        return results

    def search_flights(
        self,
        departure_city: str,
        arrival_city: str,
    ) -> List[Flight]:
        """Search flights between cities."""
        return [
            f
            for f in self.flights
            if f.departure_city == departure_city and f.arrival_city == arrival_city
        ]

    def search_trains(
        self,
        departure_city: str,
        arrival_city: str,
    ) -> List[Train]:
        """Search trains between cities."""
        return [
            t
            for t in self.trains
            if t.departure_city == departure_city and t.arrival_city == arrival_city
        ]

    def get_attraction_by_id(self, attraction_id: str) -> Optional[Attraction]:
        """Get attraction by ID."""
        for a in self.attractions:
            if a.id == attraction_id:
                return a
        return None

    def get_hotel_by_id(self, hotel_id: str) -> Optional[Hotel]:
        """Get hotel by ID."""
        for h in self.hotels:
            if h.id == hotel_id:
                return h
        return None


# Global mock data instance
mock_data = MockDataProvider()
