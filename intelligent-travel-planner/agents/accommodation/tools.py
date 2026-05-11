"""Tools for accommodation agent - 使用高德地图API搜索真实酒店数据."""

from typing import Optional
from langchain_core.tools import tool

from data.mock_data import mock_data

try:
    from utils.amap_api import amap_api
    HAS_AMAP = True
except ImportError:
    HAS_AMAP = False


def _format_amap_hotels(pois: list, location: str) -> str:
    """将高德POI数据格式化为酒店列表文本."""
    result_lines = [f"【高德地图 - {location}真实酒店数据】\n"]
    for i, poi in enumerate(pois, 1):
        name = poi.get("name", "未知")
        address = poi.get("address", "")
        biz_ext = poi.get("biz_ext", {})
        rating = biz_ext.get("rating", "暂无")
        cost = biz_ext.get("cost", "")
        if isinstance(cost, list) or not cost:
            cost = "价格未知"

        result_lines.append(
            f"{i}. {name}\n"
            f"   地址: {address}\n"
            f"   评分: {rating if rating != '暂无' else '暂无评分'}\n"
            f"   参考价格: {cost}\n"
            f"   酒店ID: {poi.get('id', '')}\n"
        )
    return "\n".join(result_lines)


def _get_hotels_from_amap(location: str, page_size: int = 10) -> list:
    """从高德API获取酒店POI列表."""
    if not HAS_AMAP:
        return []
    try:
        return amap_api.search_hotels(location, page_size=page_size)
    except Exception as e:
        print(f"高德API搜索酒店失败: {e}")
        return []


@tool
def search_hotels(
    location: str,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    star_rating: Optional[int] = None,
) -> str:
    """
    搜索指定城市的酒店信息。

    Args:
        location: 城市名称
        max_price: 最高每晚价格
        min_rating: 最低评分
        star_rating: 星级要求

    Returns:
        酒店列表信息
    """
    # 优先使用高德地图API获取真实数据
    amap_pois = _get_hotels_from_amap(location)
    if amap_pois:
        return _format_amap_hotels(amap_pois, location)

    # 高德API不可用时降级到模拟数据
    hotels = mock_data.search_hotels(
        location=location,
        max_price=max_price,
        min_rating=min_rating,
        star_rating=star_rating,
    )

    if not hotels:
        return f"未找到 {location} 的酒店信息，请检查城市名称或网络连接。"

    result_lines = [f"在 {location} 找到 {len(hotels)} 家酒店（离线参考数据）：\n"]

    for i, hotel in enumerate(hotels, 1):
        stars = "⭐" * hotel.star_rating
        facilities = "、".join(hotel.facilities[:3])
        result_lines.append(
            f"{i}. {hotel.name}\n"
            f"   星级: {stars}\n"
            f"   价格: ¥{hotel.price_per_night}/晚\n"
            f"   评分: {hotel.rating}/5.0\n"
            f"   可用房间: {hotel.available_rooms}间\n"
            f"   设施: {facilities}\n"
            f"   地址: {hotel.address}\n"
            f"   酒店ID: {hotel.id}\n"
        )

    return "\n".join(result_lines)


@tool
def get_hotel_details(hotel_id: str) -> str:
    """
    获取酒店的详细信息。

    Args:
        hotel_id: 酒店ID

    Returns:
        酒店详细信息
    """
    # 优先使用高德API获取真实详情
    if HAS_AMAP:
        try:
            poi = amap_api.get_poi_detail(hotel_id)
            if poi:
                name = poi.get("name", "未知")
                address = poi.get("address", "未知")
                biz_ext = poi.get("biz_ext", {})
                rating = biz_ext.get("rating", "暂无")
                cost = biz_ext.get("cost", "暂无")
                return (
                    f"酒店详情（高德地图）：{name}\n"
                    f"地址: {address}\n"
                    f"评分: {rating}\n"
                    f"参考价格: {cost}\n"
                    f"酒店ID: {hotel_id}"
                )
        except Exception as e:
            print(f"高德API获取酒店详情失败: {e}")

    # 降级到模拟数据
    hotel = mock_data.get_hotel_by_id(hotel_id)
    if not hotel:
        return f"未找到酒店ID: {hotel_id}"

    facilities = "、".join(hotel.facilities)
    return (
        f"酒店详情（离线参考数据）：{hotel.name}\n"
        f"位置: {hotel.location}\n"
        f"星级: {'⭐' * hotel.star_rating}\n"
        f"价格: ¥{hotel.price_per_night}/晚\n"
        f"评分: {hotel.rating}/5.0\n"
        f"可用房间: {hotel.available_rooms}间\n"
        f"设施: {facilities}\n"
        f"地址: {hotel.address}\n"
        f"酒店ID: {hotel.id}"
    )


@tool
def calculate_accommodation_cost(
    price_per_night: float,
    nights: int,
    room_count: int = 1,
) -> str:
    """
    计算住宿总费用。

    Args:
        price_per_night: 每晚价格
        nights: 住宿晚数
        room_count: 房间数量（默认1间）

    Returns:
        住宿费用计算结果
    """
    total = price_per_night * nights * room_count

    return (
        f"住宿费用计算：\n"
        f"  每晚价格: ¥{price_per_night}\n"
        f"  住宿晚数: {nights}晚\n"
        f"  房间数量: {room_count}间\n"
        f"  总费用: ¥{price_per_night} × {nights}晚 × {room_count}间 = ¥{total}"
    )


@tool
def recommend_hotels_by_budget(
    location: str,
    total_budget: float,
    nights: int,
    room_count: int = 1,
) -> str:
    """
    根据预算推荐酒店。

    Args:
        location: 城市名称
        total_budget: 住宿总预算
        nights: 住宿晚数
        room_count: 房间数量

    Returns:
        符合预算的酒店推荐
    """
    max_price_per_night = total_budget / (nights * room_count)

    # 优先使用高德API
    amap_pois = _get_hotels_from_amap(location)
    if amap_pois:
        result_lines = [
            f"【高德地图】根据您的预算（¥{total_budget}），在{location}推荐以下酒店：\n"
        ]
        for i, poi in enumerate(amap_pois[:5], 1):
            name = poi.get("name", "未知")
            address = poi.get("address", "")
            biz_ext = poi.get("biz_ext", {})
            rating = biz_ext.get("rating", "暂无")
            cost = biz_ext.get("cost", "")
            if isinstance(cost, list) or not cost:
                cost = "价格未知"
            result_lines.append(
                f"{i}. {name}\n"
                f"   地址: {address}\n"
                f"   评分: {rating}\n"
                f"   参考价格: {cost}\n"
            )
        return "\n".join(result_lines)

    # 降级到模拟数据
    hotels = mock_data.search_hotels(location=location)
    affordable_hotels = [
        h for h in hotels
        if h.price_per_night <= max_price_per_night
    ]

    if not affordable_hotels:
        return (
            f"根据您的预算，在{location}未找到合适的酒店。\n"
            f"您的预算为¥{total_budget}，需要{room_count}间房，住{nights}晚。\n"
            f"建议：降低酒店档次或增加预算。"
        )

    affordable_hotels.sort(key=lambda x: x.rating, reverse=True)

    result_lines = [
        f"根据您的预算（¥{total_budget}），在{location}推荐以下酒店（离线参考数据）：\n"
    ]

    for i, hotel in enumerate(affordable_hotels[:3], 1):
        total_cost = hotel.price_per_night * nights * room_count
        stars = "⭐" * hotel.star_rating
        result_lines.append(
            f"{i}. {hotel.name} {stars}\n"
            f"   价格: ¥{hotel.price_per_night}/晚\n"
            f"   {nights}晚×{room_count}间总计: ¥{total_cost}\n"
            f"   评分: {hotel.rating}/5.0\n"
        )

    return "\n".join(result_lines)
