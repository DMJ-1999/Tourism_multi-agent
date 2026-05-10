#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Web交互界面 - 智能旅行规划系统"""

import gradio as gr
import re
from datetime import date, datetime, timedelta
from typing import Optional

from data.models import TravelRequest
from orchestration.coordinator import coordinator


def parse_user_input(user_input: str) -> Optional[TravelRequest]:
    """
    解析用户自然语言输入，提取旅行需求。
    """
    # 默认值
    destination = "北京"
    origin = "北京"
    traveler_count = 1
    budget = 5000.0
    start_date = date.today() + timedelta(days=30)
    end_date = start_date + timedelta(days=3)
    preferences = {}

    text = user_input.strip()

    # 提取目的地 - 支持多种格式
    cities = ["北京", "上海", "杭州", "成都", "西安", "南京", "苏州", "重庆", "广州", "深圳",
              "武汉", "长沙", "厦门", "青岛", "大连", "三亚", "昆明", "大理", "丽江", "桂林"]

    # 尝试匹配 "去XXX"、"到XXX"、"XXX旅游"、"XXX玩"
    dest_patterns = [
        r'去([^，。！？\s]{2,10})(?:旅游|玩|旅游|游)',
        r'到([^，。！？\s]{2,10})(?:旅游|玩|旅游|游)',
        r'帮我规划[^的]*([北京上海杭州成都西安南京苏州重庆广州深圳武汉长沙厦门青岛大连三亚昆明大理丽江西安桂林])',
    ]

    for pattern in dest_patterns:
        match = re.search(pattern, text)
        if match:
            potential_dest = match.group(1)
            for city in cities:
                if city in potential_dest or potential_dest in city:
                    destination = city
                    break
            break

    # 如果上面没匹配到，直接在文本中查找城市名
    if destination == "北京":
        for city in cities:
            if city in text:
                destination = city
                break

    # 提取人数 - 支持多种格式：3人、3个人、三个人、一人等
    num_patterns = [
        r'(\d+)\s*[个]?[人位]',
        r'([一二三四五六七八九十两]+)\s*[个]?[人位]',
        r'[共总]?[计]?(\d+)[人位]',
    ]

    num_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
               "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "两": 2}

    for pattern in num_patterns:
        match = re.search(pattern, text)
        if match:
            num_str = match.group(1)
            if num_str.isdigit():
                traveler_count = int(num_str)
            elif num_str in num_map:
                traveler_count = num_map[num_str]
            break

    # 提取预算 - 支持多种格式：3000元、3000块、预算3000、5000以内等
    budget_patterns = [
        r'预算\s*[为约]?(\d+)',
        r'(\d+)\s*[元块]',
        r'[约]?(\d+)\s*[块元]?以[内下]',
    ]

    for pattern in budget_patterns:
        match = re.search(pattern, text)
        if match:
            budget = float(match.group(1))
            break

    # 提取天数 - 支持多种格式：3天、三日游、三天、玩3天等
    days_patterns = [
        r'(\d+)\s*[日天][游玩]?',
        r'([一二三四五六七八九十]+)\s*[日天][游玩]?',
        r'玩\s*(\d+)\s*[天日]',
        r'[共总]?[计]?(\d+)[天日]',
    ]

    days = None
    for pattern in days_patterns:
        match = re.search(pattern, text)
        if match:
            days_str = match.group(1)
            if days_str.isdigit():
                days = int(days_str)
            elif days_str in num_map:
                days = num_map[days_str]
            break

    if days:
        end_date = start_date + timedelta(days=days - 1)

    # 提取兴趣偏好
    interests = []
    interest_keywords = {
        "历史": "历史文化",
        "文化": "历史文化",
        "古迹": "历史文化",
        "美食": "美食",
        "吃": "美食",
        "好吃": "美食",
        "自然": "自然风光",
        "风景": "自然风光",
        "山水": "自然风光",
        "艺术": "艺术文化",
        "博物馆": "博物馆",
        "购物": "购物",
        "买买买": "购物",
        "亲子": "亲子",
        "带孩子": "亲子",
        "户外": "户外活动",
        "爬山": "户外活动",
        "摄影": "摄影",
        "拍照": "摄影",
        "休闲": "休闲",
        "度假": "休闲",
    }

    for keyword, interest in interest_keywords.items():
        if keyword in text:
            interests.append(interest)

    if interests:
        preferences["interests"] = list(set(interests))

    # 打印解析结果用于调试
    print(f"[解析结果] 目的地:{destination}, 天数:{days or 4}, 人数:{traveler_count}, 预算:{budget}")

    return TravelRequest(
        destination=destination,
        origin=origin,
        start_date=start_date,
        end_date=end_date,
        traveler_count=traveler_count,
        budget=budget,
        preferences=preferences if preferences else None,
    )


def format_result(result) -> str:
    """格式化规划结果为Markdown格式"""
    if not result.success:
        return f"## 规划失败\n\n错误信息：\n" + "\n".join(f"- {e}" for e in result.errors)

    output = []
    output.append(f"# 旅行规划报告 - {result.destination}")
    output.append("")
    output.append("## 基本信息")
    output.append(f"- **目的地**: {result.destination}")
    output.append(f"- **行程天数**: {result.days}天")
    output.append(f"- **旅行人数**: {result.traveler_count}人")
    output.append(f"- **预算**: {result.budget:.0f}元")
    output.append("")

    # 费用明细
    output.append("## 费用明细")
    output.append("| 项目 | 金额 | 说明 |")
    output.append("|------|------|------|")

    ticket_cost = 0
    accommodation_cost = 0
    transport_cost = 0

    if result.itinerary:
        ticket_cost = result.itinerary.get("estimated_ticket_cost", 0)
        output.append(f"| 门票费用 | {ticket_cost:.0f}元 | 约{result.days}天景点 |")

    if result.accommodation:
        accommodation_cost = result.accommodation.get("estimated_cost", 0)
        room_count = result.accommodation.get("room_count", 1)
        nights = max(1, result.days - 1)
        output.append(f"| 住宿费用 | {accommodation_cost:.0f}元 | {nights}晚{room_count}间房 |")

    if result.transportation:
        transport_cost = result.transportation.get("estimated_cost", 0)
        output.append(f"| 交通费用 | {transport_cost:.0f}元 | 往返+当地交通 |")

    # 餐饮和其他费用
    food_cost = result.days * result.traveler_count * 200  # 每天200元/人
    other_cost = result.days * result.traveler_count * 50   # 每天50元/人杂费

    output.append(f"| 餐饮费用 | {food_cost:.0f}元 | 约{result.days}天{result.traveler_count}人 |")
    output.append(f"| 其他费用 | {other_cost:.0f}元 | 杂费应急 |")

    output.append(f"| **总费用** | **{result.total_cost:.0f}元** | |")
    output.append("")

    # 预算状态
    if result.is_within_budget:
        remaining = result.budget - result.total_cost
        output.append(f"> **预算状态**: 预算充足，剩余 **{remaining:.0f}元**")
    else:
        overspend = result.total_cost - result.budget
        output.append(f"> **预算状态**: 预算超支 **{overspend:.0f}元**")
    output.append("")

    # 节省建议
    if hasattr(result, 'savings_tips') and result.savings_tips:
        output.append("## 调整建议")
        for tip in result.savings_tips:
            output.append(f"- {tip}")
        output.append("")

    # 行程安排
    output.append("## 行程安排")
    output.append("")
    if result.itinerary:
        plan_text = result.itinerary.get("plan", "暂无详细行程")
        output.append(plan_text)
    output.append("")

    # 旅行贴士
    output.append("## 旅行贴士")
    output.append("")
    for i, tip in enumerate(result.tips, 1):
        output.append(f"{i}. {tip}")

    return "\n".join(output)


def plan_travel(
    destination: str,
    origin: str,
    start_date: str,
    end_date: str,
    traveler_count: int,
    budget: float,
    interests: list,
) -> str:
    """执行旅行规划"""
    try:
        # 处理日期
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
        else:
            start = date.today() + timedelta(days=30)

        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            end = start + timedelta(days=3)

        # 构建偏好
        preferences = {}
        if interests:
            preferences["interests"] = interests

        # 创建请求
        request = TravelRequest(
            destination=destination,
            origin=origin,
            start_date=start,
            end_date=end,
            traveler_count=int(traveler_count),
            budget=float(budget),
            preferences=preferences if preferences else None,
        )

        # 执行规划
        result = coordinator.plan_trip(request)

        return format_result(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"## 错误\n\n规划过程中出现错误：{str(e)}"


def chat_with_agent(message: str, history: list) -> str:
    """对话式交互"""
    if not message.strip():
        return "请输入您的旅行需求，例如：我想去北京玩3天，2个人，预算5000元"

    try:
        # 解析用户输入
        request = parse_user_input(message)

        # 执行规划
        result = coordinator.plan_trip(request)

        return format_result(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"规划过程中出现错误：{str(e)}"


# 创建Gradio界面
with gr.Blocks(title="智能旅行规划系统") as demo:
    gr.Markdown(
        """
        # 智能旅行规划系统
        ### 基于LangChain多智能体架构的个性化旅行规划服务

        支持：北京、上海、杭州、成都、西安等热门城市

        ---
        """
    )

    with gr.Tabs():
        # Tab 1: 对话模式
        with gr.TabItem("对话模式"):
            gr.Markdown("用自然语言描述您的旅行需求，系统将自动解析并规划。")
            gr.Markdown("**示例**：我想去北京玩4天，2个人，预算8000元，喜欢历史文化")

            chatbot = gr.ChatInterface(
                fn=chat_with_agent,
                title="",
                description="输入您的旅行需求，例如：我想去杭州玩3天，3个人，预算3000元",
                examples=[
                    "我想去北京玩4天，2个人，预算8000元，喜欢历史文化",
                    "帮我规划一下杭州3日游，3个人，预算3000元",
                    "成都5天旅游攻略，4个人，预算15000元，喜欢美食",
                    "我想去西安玩3天，1个人，预算2000元",
                ],
                cache_examples=False,
            )

        # Tab 2: 表单模式
        with gr.TabItem("表单模式"):
            gr.Markdown("填写详细信息，获取精准规划。")

            with gr.Row():
                with gr.Column():
                    destination = gr.Dropdown(
                        choices=["北京", "上海", "杭州", "成都", "西安", "南京", "苏州", "重庆", "广州", "深圳"],
                        value="北京",
                        label="目的地",
                    )
                    origin = gr.Dropdown(
                        choices=["北京", "上海", "杭州", "成都", "西安", "南京", "苏州", "重庆", "广州", "深圳"],
                        value="北京",
                        label="出发城市",
                    )

                with gr.Column():
                    start_date = gr.Textbox(
                        value=(date.today() + timedelta(days=30)).strftime("%Y-%m-%d"),
                        label="出发日期",
                        placeholder="YYYY-MM-DD",
                    )
                    end_date = gr.Textbox(
                        value=(date.today() + timedelta(days=33)).strftime("%Y-%m-%d"),
                        label="返回日期",
                        placeholder="YYYY-MM-DD",
                    )

            with gr.Row():
                traveler_count = gr.Slider(
                    minimum=1,
                    maximum=10,
                    value=2,
                    step=1,
                    label="旅行人数",
                )
                budget = gr.Number(
                    value=5000,
                    label="预算（元）",
                )

            interests = gr.CheckboxGroup(
                choices=["历史文化", "自然风光", "美食", "艺术文化", "购物", "亲子", "户外活动"],
                label="兴趣偏好（可多选）",
            )

            plan_btn = gr.Button("开始规划", variant="primary", size="lg")

            output = gr.Markdown(label="规划结果")

            plan_btn.click(
                fn=plan_travel,
                inputs=[destination, origin, start_date, end_date, traveler_count, budget, interests],
                outputs=output,
            )

        # Tab 3: 使用说明
        with gr.TabItem("使用说明"):
            gr.Markdown(
                """
                ## 功能说明

                本系统由4个专业智能体协同工作：

                | 智能体 | 职责 |
                |--------|------|
                | 行程规划师 | 根据目的地和偏好设计每日活动路线 |
                | 住宿协调员 | 推荐合适的酒店并计算住宿费用 |
                | 交通调度员 | 规划往返交通和当地交通方案 |
                | 预算审计员 | 汇总费用并检查是否超预算 |

                ## 使用方式

                ### 对话模式
                直接用自然语言描述您的需求，系统会自动解析。

                **示例**：
                - "我想去北京玩4天，2个人，预算8000元"
                - "帮我规划一下杭州3日游，3个人，喜欢美食"

                ### 表单模式
                填写详细信息，获取更精准的规划结果。

                ## 注意事项

                1. 请确保已配置 `DASHSCOPE_API_KEY` 环境变量以获得智能推荐
                2. 支持的城市：北京、上海、杭州、成都、西安等
                3. 已接入高德地图API，提供真实的景点信息

                ## 技术栈

                - LangChain - 多智能体框架
                - 通义千问 Qwen - 大语言模型
                - 高德地图 - 景点/酒店数据
                - Gradio - Web界面
                """
            )


def find_free_port(start_port: int = 8098, max_attempts: int = 20) -> int:
    """寻找可用端口"""
    import socket
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return start_port + max_attempts


def main():
    """启动Web应用"""
    print("=" * 60)
    print("智能旅行规划系统 - Web界面")
    print("=" * 60)
    print()
    print("正在启动Web服务...")

    # 寻找可用端口
    port = find_free_port(8098)
    print(f"使用端口: {port}")
    print(f"启动后请在浏览器中打开: http://localhost:{port}")
    print()

    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
