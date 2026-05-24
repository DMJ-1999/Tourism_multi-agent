"""Tools for food planner agent — 使用美团开放平台 API 搜索真实餐厅数据。"""

from typing import Optional
from langchain_core.tools import tool

from utils.meituan_api import meituan_api


@tool
def search_restaurants_by_city(
    city: str,
    cuisine_type: Optional[str] = None,
    page_size: int = 10,
) -> str:
    """
    搜索指定城市的餐厅（美团开放平台 + 参考数据降级）。

    Args:
        city: 城市名称
        cuisine_type: 菜系类型（如：火锅、川菜、本帮菜等），可选
        page_size: 返回数量

    Returns:
        餐厅列表信息
    """
    restaurants = meituan_api.search_restaurants(
        city=city,
        keyword=cuisine_type,
        page_size=page_size,
    )

    if not restaurants:
        return f"未找到 {city} 的餐厅信息{'（菜系: ' + cuisine_type + '）' if cuisine_type else ''}。"

    keyword = cuisine_type or "美食"
    result_lines = [f"【{city}{keyword}餐厅推荐】共 {len(restaurants)} 家：\n"]

    for i, r in enumerate(restaurants, 1):
        dishes = "、".join(r.get("signature_dishes", [])[:3])
        result_lines.append(
            f"{i}. {r['name']}\n"
            f"   地址: {r.get('address', '')}\n"
            f"   菜系: {r.get('cuisine', '未知')}\n"
            f"   评分: {r.get('rating', 0)}/5.0\n"
            f"   人均: ¥{r.get('avg_price', '未知')}\n"
            f"   招牌菜: {dishes}\n"
            f"   区域: {r.get('location', '')}\n"
        )

    return "\n".join(result_lines)


@tool
def get_restaurant_detail(restaurant_name: str, city: str) -> str:
    """
    获取指定餐厅的详细信息。

    Args:
        restaurant_name: 餐厅名称
        city: 所在城市

    Returns:
        餐厅详细信息
    """
    restaurants = meituan_api.search_restaurants(city=city, keyword=restaurant_name, page_size=5)

    if not restaurants:
        return f"未找到 {restaurant_name} 的详细信息。"

    r = restaurants[0]
    dishes = "、".join(r.get("signature_dishes", [])[:5])
    return (
        f"餐厅详情：{r['name']}\n"
        f"地址: {r.get('address', '')}\n"
        f"菜系: {r.get('cuisine', '未知')}\n"
        f"评分: {r.get('rating', 0)}/5.0\n"
        f"人均消费: ¥{r.get('avg_price', '未知')}\n"
        f"招牌菜: {dishes}\n"
        f"区域: {r.get('location', '')}"
    )


@tool
def search_local_cuisine(
    city: str,
    meal_type: str = "all",
) -> str:
    """
    搜索城市的地方特色美食。

    Args:
        city: 城市名称
        meal_type: 用餐类型（breakfast/lunch/dinner/all）

    Returns:
        地方特色美食推荐
    """
    cuisine_map = {
        "北京": ["北京菜", "北京小吃", "火锅"],
        "上海": ["本帮菜", "上海小吃", "江浙菜"],
        "杭州": ["杭帮菜", "面馆", "江浙菜"],
        "成都": ["川菜", "火锅", "成都小吃"],
        "西安": ["陕菜", "西安小吃", "面馆"],
        "南京": ["淮扬菜", "南京小吃", "江浙菜"],
        "苏州": ["苏帮菜", "苏州小吃", "面馆"],
        "重庆": ["川菜", "火锅", "重庆小吃"],
        "广州": ["粤菜", "茶餐厅", "广州小吃"],
        "深圳": ["粤菜", "潮汕菜", "海鲜"],
    }

    cuisine_types = cuisine_map.get(city, ["地方特色", "小吃", "中餐"])

    all_results = []
    for ctype in cuisine_types[:3]:
        restaurants = meituan_api.search_restaurants(city=city, keyword=ctype, page_size=5)
        if restaurants:
            all_results.append(f"\n--- {ctype} ---")
            for r in restaurants[:4]:
                all_results.append(
                    f"  • {r['name']} ({r.get('cuisine', '')}) "
                    f"人均¥{r.get('avg_price', '?')} | 评分{r.get('rating', 0)}"
                )

    if not all_results:
        return f"未找到 {city} 的特色美食信息。"

    header = f"【{city}地方特色美食指南】"
    if meal_type != "all":
        header += f" - {meal_type}"

    return header + "\n".join(all_results)


@tool
def calculate_food_cost(
    city: str,
    days: int,
    traveler_count: int,
    dining_level: str = "舒适型",
) -> str:
    """
    估算旅行期间的餐饮总费用。

    Args:
        city: 城市名称
        days: 旅行天数
        traveler_count: 人数
        dining_level: 餐饮档次（经济型/舒适型/高档型/豪华型）

    Returns:
        餐饮费用估算
    """
    daily_per_person = {
        "经济型": 120,
        "舒适型": 200,
        "高档型": 350,
        "豪华型": 500,
    }

    daily = daily_per_person.get(dining_level, 200)
    total = daily * days * traveler_count

    return (
        f"【{city}】{days}天餐饮费用估算：\n"
        f"  餐饮档次: {dining_level}\n"
        f"  人均每日: ¥{daily} (早餐¥{daily*0.2:.0f} + 午餐¥{daily*0.4:.0f} + 晚餐¥{daily*0.4:.0f})\n"
        f"  天数: {days}天\n"
        f"  人数: {traveler_count}人\n"
        f"  总计: ¥{daily} × {days}天 × {traveler_count}人 = ¥{total}"
    )


@tool
def recommend_dining_plan(
    city: str,
    days: int,
    preference_level: str = "舒适型",
) -> str:
    """
    为旅行制定每日餐饮计划推荐。

    Args:
        city: 城市名称
        days: 旅行天数
        preference_level: 消费偏好

    Returns:
        每日餐饮推荐计划
    """
    all_restaurants = meituan_api.search_restaurants(city=city, page_size=20)

    if not all_restaurants:
        return f"无法为 {city} 生成餐饮计划，数据不足。"

    # 按评分排序
    sorted_restaurants = sorted(all_restaurants, key=lambda x: x.get("rating", 0), reverse=True)

    budget_per_meal = {
        "经济型": 40,
        "舒适型": 80,
        "高档型": 150,
        "豪华型": 250,
    }

    per_meal = budget_per_meal.get(preference_level, 80)

    result_lines = [
        f"【{city} {days}天餐饮推荐计划】（{preference_level}，人均每餐约¥{per_meal}）\n"
    ]

    for day in range(1, days + 1):
        result_lines.append(f"第{day}天：")
        # 轮换选取餐厅
        lunch_idx = (day - 1) * 2 % len(sorted_restaurants)
        dinner_idx = ((day - 1) * 2 + 1) % len(sorted_restaurants)

        lunch = sorted_restaurants[lunch_idx]
        dinner = sorted_restaurants[dinner_idx]

        result_lines.append(
            f"  午餐: {lunch['name']} ({lunch.get('cuisine', '')}) "
            f"人均¥{lunch.get('avg_price', '?')} | 评分{lunch.get('rating', 0)}"
        )
        result_lines.append(
            f"  晚餐: {dinner['name']} ({dinner.get('cuisine', '')}) "
            f"人均¥{dinner.get('avg_price', '?')} | 评分{dinner.get('rating', 0)}"
        )
        result_lines.append("")

    return "\n".join(result_lines)
