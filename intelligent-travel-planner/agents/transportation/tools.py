"""Tools for transportation agent."""

from typing import Optional
from langchain_core.tools import tool

from data.mock_data import mock_data


@tool
def search_flights(
    departure_city: str,
    arrival_city: str,
) -> str:
    """
    搜索两个城市之间的航班。

    Args:
        departure_city: 出发城市
        arrival_city: 到达城市

    Returns:
        航班列表信息
    """
    flights = mock_data.search_flights(
        departure_city=departure_city,
        arrival_city=arrival_city,
    )

    if not flights:
        return f"未找到从 {departure_city} 到 {arrival_city} 的航班信息。"

    result_lines = [f"从 {departure_city} 到 {arrival_city} 的航班：\n"]

    for i, flight in enumerate(flights, 1):
        result_lines.append(
            f"{i}. {flight.airline} {flight.flight_number}\n"
            f"   起飞: {flight.departure_time}\n"
            f"   到达: {flight.arrival_time}\n"
            f"   价格: ¥{flight.price}（{flight.seat_class}）\n"
            f"   航班ID: {flight.id}\n"
        )

    return "\n".join(result_lines)


@tool
def search_trains(
    departure_city: str,
    arrival_city: str,
) -> str:
    """
    搜索两个城市之间的火车。

    Args:
        departure_city: 出发城市
        arrival_city: 到达城市

    Returns:
        火车列表信息
    """
    trains = mock_data.search_trains(
        departure_city=departure_city,
        arrival_city=arrival_city,
    )

    if not trains:
        return f"未找到从 {departure_city} 到 {arrival_city} 的火车信息。"

    result_lines = [f"从 {departure_city} 到 {arrival_city} 的火车：\n"]

    for i, train in enumerate(trains, 1):
        result_lines.append(
            f"{i}. {train.train_type} {train.train_number}\n"
            f"   发车: {train.departure_time}\n"
            f"   到达: {train.arrival_time}\n"
            f"   价格: ¥{train.price}（{train.seat_type}）\n"
            f"   车次ID: {train.id}\n"
        )

    return "\n".join(result_lines)


@tool
def estimate_local_transport(
    city: str,
    days: int,
    daily_trips: int = 4,
) -> str:
    """
    估算当地交通费用。

    Args:
        city: 城市名称
        days: 天数
        daily_trips: 每天出行次数（默认4次）

    Returns:
        当地交通费用估算
    """
    # 不同城市的地铁/公交价格
    city_transport = {
        "北京": {"subway": 6, "bus": 2, "taxi_start": 13},
        "上海": {"subway": 5, "bus": 2, "taxi_start": 14},
        "杭州": {"subway": 4, "bus": 2, "taxi_start": 11},
        "成都": {"subway": 4, "bus": 2, "taxi_start": 8},
        "西安": {"subway": 4, "bus": 2, "taxi_start": 8},
    }

    transport_info = city_transport.get(city, {"subway": 5, "bus": 2, "taxi_start": 10})

    # 计算不同出行方式的费用
    subway_total = transport_info["subway"] * daily_trips * days
    bus_total = transport_info["bus"] * daily_trips * days
    taxi_estimate = transport_info["taxi_start"] * 1.5 * daily_trips * days  # 假设每次打车约1.5倍起步价

    result_lines = [
        f"{city}{days}天当地交通费用估算：\n",
        f"每日出行次数: {daily_trips}次\n",
        f"方式一：地铁出行",
        f"  单次票价: ¥{transport_info['subway']}起",
        f"  总费用: ¥{transport_info['subway']} × {daily_trips}次 × {days}天 = ¥{subway_total}\n",
        f"方式二：公交出行",
        f"  单次票价: ¥{transport_info['bus']}",
        f"  总费用: ¥{transport_info['bus']} × {daily_trips}次 × {days}天 = ¥{bus_total}\n",
        f"方式三：出租车出行（估算）",
        f"  起步价: ¥{transport_info['taxi_start']}",
        f"  总费用: 约¥{taxi_estimate:.0f}\n",
        f"建议：购买{days}日地铁通票或使用手机支付。",
    ]

    return "\n".join(result_lines)


@tool
def compare_transport_options(
    departure_city: str,
    arrival_city: str,
) -> str:
    """
    比较航班和火车的优缺点。

    Args:
        departure_city: 出发城市
        arrival_city: 到达城市

    Returns:
        交通方式比较
    """
    flights = mock_data.search_flights(departure_city, arrival_city)
    trains = mock_data.search_trains(departure_city, arrival_city)

    result_lines = [f"从 {departure_city} 到 {arrival_city} 的交通方式比较：\n"]

    if flights:
        min_flight_price = min(f.price for f in flights)
        result_lines.append(
            f"✈️ 航班：\n"
            f"   最低价格: ¥{min_flight_price}\n"
            f"   优点: 速度快，省时\n"
            f"   缺点: 价格较高，需要提前到达机场\n"
        )

    if trains:
        min_train_price = min(t.price for t in trains)
        result_lines.append(
            f"🚄 高铁/火车：\n"
            f"   最低价格: ¥{min_train_price}\n"
            f"   优点: 性价比高，准点率高，市中心出发\n"
            f"   缺点: 时间可能较长\n"
        )

    if flights and trains:
        savings = min(f.price for f in flights) - min(t.price for t in trains)
        if savings > 0:
            result_lines.append(f"💡 选择火车可节省约¥{savings}")
        else:
            result_lines.append(f"💡 航班价格更具优势")

    return "\n".join(result_lines)


@tool
def get_round_trip_cost(
    departure_city: str,
    arrival_city: str,
    transport_type: str = "train",
) -> str:
    """
    计算往返交通费用。

    Args:
        departure_city: 出发城市
        arrival_city: 目的城市
        transport_type: 交通类型（train或flight）

    Returns:
        往返交通费用
    """
    if transport_type == "flight":
        outbound = mock_data.search_flights(departure_city, arrival_city)
        inbound = mock_data.search_flights(arrival_city, departure_city)

        if outbound and inbound:
            min_outbound = min(f.price for f in outbound)
            min_inbound = min(f.price for f in inbound)
            total = min_outbound + min_inbound

            return (
                f"往返航班费用：\n"
                f"去程: {departure_city}→{arrival_city}，最低¥{min_outbound}\n"
                f"返程: {arrival_city}→{departure_city}，最低¥{min_inbound}\n"
                f"往返总计: ¥{total}"
            )
    else:
        outbound = mock_data.search_trains(departure_city, arrival_city)
        inbound = mock_data.search_trains(arrival_city, departure_city)

        if outbound and inbound:
            min_outbound = min(t.price for t in outbound)
            min_inbound = min(t.price for t in inbound)
            total = min_outbound + min_inbound

            return (
                f"往返火车费用：\n"
                f"去程: {departure_city}→{arrival_city}，最低¥{min_outbound}\n"
                f"返程: {arrival_city}→{departure_city}，最低¥{min_inbound}\n"
                f"往返总计: ¥{total}"
            )

    return f"未找到从 {departure_city} 到 {arrival_city} 的{transport_type}信息"
