"""Tools for itinerary planner agent - 集成高德地图API."""

from typing import List, Optional
from langchain_core.tools import tool

from data.mock_data import mock_data

# 尝试导入高德API
try:
    from utils.amap_api import amap_api
    HAS_AMAP = True
except ImportError:
    HAS_AMAP = False
    print("警告: 未安装requests库，高德API不可用")


@tool
def search_attractions(
    location: str,
    categories: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> str:
    """
    搜索指定城市的景点信息。

    Args:
        location: 城市名称（如：北京、上海、杭州等）
        categories: 景点类别列表（如：历史文化、自然风光、美食购物等）
        tags: 景点标签列表（如：必去、世界遗产、亲子等）

    Returns:
        景点列表信息的字符串
    """
    results = []

    # 1. 首先尝试使用高德API获取真实数据
    if HAS_AMAP:
        try:
            amap_results = amap_api.search_scenic_spots(location, page_size=10)
            if amap_results:
                results.append(f"【高德地图 - {location}热门景点】\n")
                for i, poi in enumerate(amap_results[:10], 1):
                    name = poi.get("name", "未知")
                    address = poi.get("address", "")
                    type_code = poi.get("typecode", "")
                    rating = poi.get("biz_ext", {}).get("rating", "暂无")
                    cost = poi.get("biz_ext", {}).get("cost", "暂无")

                    results.append(
                        f"{i}. {name}\n"
                        f"   地址: {address}\n"
                        f"   评分: {rating if rating != '暂无' else '暂无评分'}\n"
                        f"   参考票价: {cost if cost != '暂无' else '暂无'}\n"
                    )

                # 如果高德API返回了结果，直接返回
                if len(results) > 1:
                    return "\n".join(results)
        except Exception as e:
            print(f"高德API调用失败: {e}")

    # 2. 回退到模拟数据
    attractions = mock_data.search_attractions(
        location=location,
        categories=categories,
        tags=tags,
    )

    if not attractions:
        return f"未找到 {location} 的景点信息，请检查城市名称是否正确。"

    result_lines = [f"在 {location} 找到 {len(attractions)} 个景点：\n"]

    for i, attr in enumerate(attractions, 1):
        tags_str = "、".join(attr.tags[:4])
        result_lines.append(
            f"{i}. {attr.name}\n"
            f"   类别: {attr.category}\n"
            f"   标签: {tags_str}\n"
            f"   门票: {attr.ticket_price}元\n"
            f"   评分: {attr.rating}/5.0\n"
            f"   开放时间: {attr.opening_hours}\n"
            f"   建议游览: {attr.visit_duration}小时\n"
            f"   简介: {attr.description[:50]}...\n"
        )

    return "\n".join(result_lines)


@tool
def get_attraction_details(attraction_id: str) -> str:
    """
    获取景点的详细信息。

    Args:
        attraction_id: 景点ID

    Returns:
        景点详细信息的字符串
    """
    # 优先使用高德API获取真实数据
    if HAS_AMAP:
        try:
            poi = amap_api.get_poi_detail(attraction_id)
            if poi:
                biz_ext = poi.get("biz_ext", {})
                cost = biz_ext.get("cost", "暂无")
                if isinstance(cost, list) or not cost:
                    cost = "暂无"
                return (
                    f"景点详情（高德地图）：{poi.get('name', '未知')}\n"
                    f"地址: {poi.get('address', '未知')}\n"
                    f"类型: {poi.get('type', '未知')}\n"
                    f"电话: {poi.get('tel', '暂无')}\n"
                    f"评分: {biz_ext.get('rating', '暂无')}\n"
                    f"参考票价: {cost}\n"
                    f"景点ID: {attraction_id}"
                )
        except Exception as e:
            print(f"高德API获取景点详情失败: {e}")

    # 降级到模拟数据
    attraction = mock_data.get_attraction_by_id(attraction_id)
    if attraction:
        return (
            f"景点详情（离线参考数据）：{attraction.name}\n"
            f"位置: {attraction.location}\n"
            f"类别: {attraction.category}\n"
            f"标签: {'、'.join(attraction.tags)}\n"
            f"门票价格: {attraction.ticket_price}元\n"
            f"评分: {attraction.rating}/5.0\n"
            f"开放时间: {attraction.opening_hours}\n"
            f"建议游览时长: {attraction.visit_duration}小时\n"
            f"景点介绍: {attraction.description}\n"
            f"景点ID: {attraction.id}"
        )

    return f"未找到景点ID: {attraction_id}"


@tool
def optimize_route(
    attraction_ids: List[str],
    days: int,
    daily_hours: int = 8,
) -> str:
    """
    优化景点游览路线，按天分配景点。

    注：路线优化需要景点游览时长等结构化数据（高德API不提供），因此使用离线参考数据。

    Args:
        attraction_ids: 景点ID列表
        days: 旅行天数
        daily_hours: 每天可用于游览的小时数（默认8小时）

    Returns:
        优化后的行程安排字符串
    """
    attractions = []
    for aid in attraction_ids:
        attr = mock_data.get_attraction_by_id(aid)
        if attr:
            attractions.append(attr)

    if not attractions:
        return "未找到有效的景点信息"

    # 简单的行程优化：按评分排序，然后按时间分配
    attractions.sort(key=lambda x: x.rating, reverse=True)

    daily_itinerary = []
    current_day = 1
    current_hours = 0
    day_plan = []

    for attr in attractions:
        if current_hours + attr.visit_duration > daily_hours:
            if day_plan:
                daily_itinerary.append((current_day, day_plan.copy()))
            current_day += 1
            current_hours = 0
            day_plan = []

            if current_day > days:
                break

        day_plan.append(attr)
        current_hours += attr.visit_duration

    if day_plan and current_day <= days:
        daily_itinerary.append((current_day, day_plan))

    # 格式化输出
    result_lines = [f"优化后的{days}天行程安排：\n"]

    total_cost = 0.0
    for day, day_attractions in daily_itinerary:
        result_lines.append(f"第{day}天：")
        day_cost = 0.0
        for attr in day_attractions:
            result_lines.append(f"  - {attr.name}（建议游览{attr.visit_duration}小时，门票{attr.ticket_price}元）")
            day_cost += attr.ticket_price
        result_lines.append(f"  当日门票费用: {day_cost}元\n")
        total_cost += day_cost

    result_lines.append(f"总门票费用: {total_cost}元")

    if len(daily_itinerary) < days:
        result_lines.append(f"\n提示：当前景点可安排{len(daily_itinerary)}天，还剩{days - len(daily_itinerary)}天可安排其他活动。")

    return "\n".join(result_lines)


@tool
def get_city_highlights(location: str) -> str:
    """
    获取城市的旅行亮点和推荐活动。

    Args:
        location: 城市名称

    Returns:
        城市旅行亮点信息
    """
    results = []

    # 尝试高德API获取热门景点
    if HAS_AMAP:
        try:
            pois = amap_api.search_scenic_spots(location, page_size=5)
            if pois:
                results.append(f"【{location}热门景点推荐】\n")
                for i, poi in enumerate(pois, 1):
                    name = poi.get("name", "")
                    results.append(f"{i}. {name}")
                results.append("")
        except Exception as e:
            print(f"获取城市亮点失败: {e}")

    # 使用模拟数据补充
    attractions = mock_data.search_attractions(location=location)

    if attractions:
        # 分类统计
        categories = {}
        must_visit = []
        free_attractions = []

        for attr in attractions:
            if attr.category not in categories:
                categories[attr.category] = []
            categories[attr.category].append(attr.name)

            if "必去" in attr.tags:
                must_visit.append(attr.name)

            if attr.ticket_price == 0:
                free_attractions.append(attr.name)

        results.append(f"【{location}旅行亮点】\n")

        if must_visit:
            results.append("必去景点：" + "、".join(must_visit[:3]) + "\n")

        results.append("景点类别分布：")
        for cat, names in categories.items():
            results.append(f"  {cat}: {', '.join(names[:2])}等{len(names)}个")

        if free_attractions:
            results.append(f"\n免费景点: {', '.join(free_attractions)}")

    return "\n".join(results) if results else f"未找到 {location} 的旅游信息"


@tool
def search_restaurants(location: str, cuisine_type: str = None) -> str:
    """
    搜索指定城市的餐厅信息（使用高德API）。

    Args:
        location: 城市名称
        cuisine_type: 菜系类型（可选）

    Returns:
        餐厅列表信息
    """
    if not HAS_AMAP:
        return f"高德API不可用，无法搜索{location}的餐厅信息"

    try:
        restaurants = amap_api.search_restaurants(location, page_size=10)
        if not restaurants:
            return f"未找到{location}的餐厅信息"

        results = [f"【{location}热门餐厅推荐】\n"]
        for i, r in enumerate(restaurants[:10], 1):
            name = r.get("name", "未知")
            address = r.get("address", "")
            rating = r.get("biz_ext", {}).get("rating", "暂无")
            results.append(f"{i}. {name}\n   地址: {address}\n   评分: {rating}\n")

        return "\n".join(results)
    except Exception as e:
        return f"搜索餐厅失败: {str(e)}"
