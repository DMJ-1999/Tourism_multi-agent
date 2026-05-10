#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
四Agent协作系统 - 使用Qwen LLM作为智能体大脑

Agent 1: 行程规划师 - 高德API搜索景点
Agent 2: 住宿协调员 - 高德API搜索酒店
Agent 3: 餐饮推荐 - 美团API推荐餐厅
Agent 4: 预算审计员 - 计算费用，根据意图调整方案

支持对话上下文记忆
"""

import gradio as gr
from datetime import date, timedelta

from data.models import TravelRequest
from simple_coordinator import coordinator
from utils.intent_parser import IntentParser
from utils.llm import qwen_brain


# 创建意图解析器实例（保持对话上下文）
intent_parser = IntentParser()


def parse_input(text: str) -> TravelRequest:
    """使用LLM智能解析用户输入"""
    # 使用LLM意图解析器（带上下文记忆）
    parsed = intent_parser.parse(text)

    print(f"[解析结果] 目的地:{parsed.destination}, 天数:{parsed.days}, "
          f"人数:{parsed.traveler_count}, 预算:{parsed.budget}, "
          f"花光预算:{parsed.spend_all_budget}, 档次:{parsed.preference_level}")

    return TravelRequest(
        destination=parsed.destination,
        origin=parsed.origin,
        start_date=date.today() + timedelta(days=30),
        end_date=date.today() + timedelta(days=30 + parsed.days - 1),
        traveler_count=parsed.traveler_count,
        budget=parsed.budget,
        preferences={
            "intent": text,
            "spend_all_budget": parsed.spend_all_budget,
            "preference_level": parsed.preference_level,
            "special_requests": parsed.special_requests,
        },
    )


def format_result(result) -> str:
    """格式化输出"""
    if not result.success:
        return "## 规划失败\n\n请检查输入参数"

    output = []

    # 标题
    output.append(f"# {result.destination} {result.days}日游详细规划\n")
    output.append(f"**人数**: {result.traveler_count}人 | **预算**: {result.budget}元")
    if result.spend_all_budget:
        output.append(f" | **目标**: 花光预算")
    output.append("\n")

    # ========== 每日行程 ==========
    output.append("---\n## 每日详细行程\n")

    for schedule in result.daily_schedules:
        output.append(f"### 第{schedule.day}天 ({schedule.date})\n")

        # 上午
        output.append(f"**上午**: {schedule.morning.get('name', '自由活动')}\n")
        if schedule.morning.get('address'):
            output.append(f"> 地址: {schedule.morning['address'][:30]}\n")
        output.append(f"> 门票: {schedule.morning.get('cost', '免费')}\n\n")

        # 午餐
        output.append(f"**午餐**: 特色餐厅推荐\n\n")

        # 下午
        output.append(f"**下午**: {schedule.afternoon.get('name', '自由活动')}\n")
        if schedule.afternoon.get('address'):
            output.append(f"> 地址: {schedule.afternoon['address'][:30]}\n")
        output.append(f"> 门票: {schedule.afternoon.get('cost', '免费')}\n\n")

        # 晚餐
        output.append(f"**晚餐**: 特色美食推荐\n\n")

        # 当日费用
        output.append(f"*当日门票: {schedule.ticket_cost}元*\n\n---\n")

    # ========== 餐饮推荐 ==========
    output.append("\n## 特色餐厅推荐\n")
    output.append("| 餐厅 | 菜系 | 人均 | 招牌菜 | 评分 |\n")
    output.append("|------|------|------|--------|------|\n")

    for r in result.restaurants[:8]:
        dishes = r.get('signature_dishes', [])
        dish_str = dishes[0] if dishes else ""
        output.append(f"| {r['name']} | {r.get('cuisine', '')} | ¥{r.get('avg_price', 0)} | {dish_str} | ⭐{r.get('rating', 0)} |\n")

    # ========== 住宿推荐 ==========
    output.append(f"\n## 住宿推荐 ({result.selected_hotel.get('level', '舒适型')})\n")
    output.append("| 酒店 | 地址 | 价格 | 评分 |\n")
    output.append("|------|------|------|------|\n")

    for h in result.hotels[:5]:
        output.append(f"| {h['name']} | {h.get('address', '')[:25]}... | {h.get('cost', '价格未知')} | ⭐{h.get('rating', 0)} |\n")

    nights = max(1, result.days - 1)
    rooms = max(1, (result.traveler_count + 1) // 2)
    output.append(f"\n**住宿费用**: {result.accommodation_cost}元 ({nights}晚 x {rooms}间 x {result.selected_hotel.get('price_per_night', 350)}元/晚)\n")

    # ========== 预算调整 ==========
    if result.budget_adjustments:
        output.append("\n---\n## 预算优化建议\n")
        for adj in result.budget_adjustments:
            output.append(f"- {adj}\n")

    # ========== 费用汇总 ==========
    output.append("\n---\n## 费用汇总\n")
    output.append("| 项目 | 金额 | 说明 |\n")
    output.append("|------|------|------|\n")
    output.append(f"| 门票费用 | **{result.ticket_cost}元** | {result.days}天景点 |\n")
    output.append(f"| 住宿费用 | **{result.accommodation_cost}元** | {nights}晚{rooms}间 |\n")
    output.append(f"| 餐饮费用 | **{result.food_cost}元** | {result.days}天{result.traveler_count}人 |\n")
    output.append(f"| **总计** | **{result.total_cost}元** | |\n")

    status = "✅ 预算充足" if result.is_within_budget else "⚠️ 预算超支"
    output.append(f"\n> {status}，{'剩余' if result.is_within_budget else '超支'} **{abs(result.remaining_budget):.0f}元**\n")

    # ========== Agent协作记录 ==========
    output.append("\n---\n## Agent协作记录\n")

    for step in result.agent_steps:
        output.append(f"### {step['agent']}\n")
        output.append(f"- **动作**: {step['action']}\n")
        output.append(f"- **结果**: {step['result']}\n\n")

    return "".join(output)


def plan_travel(message: str, history: list) -> str:
    """执行规划"""
    if not message.strip():
        return "请输入您的旅行需求，例如：我想去北京玩4天，2个人，预算8000元"

    # 检测重置命令
    if message.strip() in ["重置", "reset", "清空", "新对话", "重新开始"]:
        intent_parser.reset()
        return "对话已重置，请输入新的旅行需求。"

    request = parse_input(message)
    result = coordinator.plan_trip(request)

    # 更新对话上下文
    intent_parser.update_result({
        "destination": result.destination,
        "days": result.days,
        "traveler_count": result.traveler_count,
        "budget": result.budget,
        "total_cost": result.total_cost,
    })

    return format_result(result)


# 创建界面
with gr.Blocks(title="智能旅行规划 - 四Agent协作") as demo:
    gr.Markdown("""
    # 智能旅行规划系统

    ### 四Agent协作架构

    | Agent | 职责 | 数据来源 |
    |-------|------|---------|
    | 行程规划师 | 搜索景点、生成每日行程 | 高德地图API |
    | 住宿协调员 | 搜索酒店、推荐住宿 | 高德地图API |
    | 餐饮推荐 | 推荐餐厅、招牌菜 | 美团API |
    | 预算审计员 | 计算费用、调整方案 | Qwen智能计算 |

    ### 智能功能
    - 支持多轮对话，自动记忆上下文
    - 自动识别"花光预算"、"全部花掉"等意图
    - 使用Qwen LLM理解自然语言
    - 根据预算自动升级住宿/餐饮档次

    ### 使用提示
    - 输入"重置"可以开始新的对话
    - 可以说"花掉全部预算"来修改之前的规划
    """)

    chatbot = gr.ChatInterface(
        fn=plan_travel,
        examples=[
            "我想去北京玩4天，2个人，预算8000元",
            "花掉全部预算",
            "我想去杭州玩3天，3个人，预算5000元",
            "升级到高档酒店",
            "重置",
        ],
        cache_examples=False,
    )


def main():
    import socket

    def find_port(start=8099, max_try=10):
        for port in range(start, start + max_try):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    return port
            except:
                continue
        return start

    port = find_port(8099)
    print(f"访问: http://localhost:{port}")

    demo.launch(server_name="0.0.0.0", server_port=port, share=False)


if __name__ == "__main__":
    main()
