"""统一旅行规划系统 Web 界面 —— 五大 AI Agent 模块协同。

基于 Gradio 构建，提供：
- 聊天模式：自然语言对话式旅行规划
- 表单模式：结构化参数输入
- 模块可视化：展示五大模块的执行追踪
"""

from datetime import date, timedelta

import gradio as gr

from data.models import TravelRequest
from unified_coordinator import unified_coordinator
from utils.intent_parser import intent_parser as classic_intent_parser


def format_unified_response(result) -> str:
    """将统一结果格式化为 Markdown 展示文本。"""
    if not result.success:
        return f"## 规划失败\n\n错误信息: {'; '.join(result.errors)}"

    lines = [
        f"## 旅行规划报告 — {result.destination}",
        "",
        f"| 项目 | 详情 |",
        f"|------|------|",
        f"| 目的地 | {result.destination} |",
        f"| 天数 | {result.days}天 |",
        f"| 人数 | {result.traveler_count}人 |",
        f"| 预算 | ¥{result.budget:.0f} |",
        f"| 消费档次 | {result.preference_level} |",
        f"| 总费用 | ¥{result.total_cost:.0f} |",
        f"| 预算状态 | {'✅ 充足' if result.is_within_budget else '⚠️ 超支'} |",
    ]

    # 模块执行追踪
    if result.execution_log:
        lines.append("")
        lines.append("### 五大模块执行追踪")
        for log_entry in result.execution_log:
            lines.append(f"- {log_entry}")

    # 费用明细
    lines.append("")
    lines.append("### 费用明细")
    ticket_cost = result.itinerary.get("estimated_ticket_cost", 0)
    acc_cost = result.accommodation.get("estimated_cost", 0)
    trans_cost = result.transportation.get("estimated_cost", 0)
    food_cost = result.food.get("food_cost", 0)
    lines.append(f"| 类别 | 金额 |")
    lines.append(f"|------|------|")
    lines.append(f"| 🎫 门票 | ¥{ticket_cost:.0f} |")
    lines.append(f"| 🏨 住宿 | ¥{acc_cost:.0f} |")
    lines.append(f"| 🚄 交通 | ¥{trans_cost:.0f} |")
    lines.append(f"| 🍜 餐饮 | ¥{food_cost:.0f} |")
    lines.append(f"| **总计** | **¥{result.total_cost:.0f}** |")

    # 质量评估
    if result.evaluation:
        ev = result.evaluation
        lines.append("")
        lines.append("### 方案质量评估")
        lines.append(f"| 维度 | 评分 |")
        lines.append(f"|------|------|")
        lines.append(f"| 📊 综合评分 | **{ev.overall_score}/100 ({ev.grade}级)** |")
        lines.append(f"| 💰 预算效率 | {ev.budget_efficiency}/100 |")
        lines.append(f"| 📅 行程可行性 | {ev.schedule_feasibility}/100 |")
        lines.append(f"| 🎯 兴趣覆盖 | {ev.interest_coverage}/100 |")
        lines.append(f"| 🗺️ 地理连贯性 | {ev.geographic_coherence}/100 |")
        lines.append(f"| ✅ 约束满足 | {ev.constraint_satisfaction}/100 |")
        if ev.suggestions:
            lines.append(f"\n💡 改进建议: {ev.suggestions[0] if ev.suggestions else ''}")

    # 修订记录
    if result.revision_count > 0:
        lines.append("")
        lines.append(f"### 预算修订 ({result.revision_count}次)")
        for tip in result.savings_tips:
            lines.append(f"- {tip}")

    # 旅行贴士
    lines.append("")
    lines.append("### 旅行贴士")
    for i, tip in enumerate(result.tips, 1):
        lines.append(f"{i}. {tip}")

    return "\n".join(lines)


def chat_handler(message: str, history: list) -> str:
    """聊天模式处理器 —— 自然语言输入。"""
    if not message or not message.strip():
        return "请输入您的旅行需求，例如：'我想去杭州玩3天，2个人，预算6000元'"

    # 解析意图
    intent = classic_intent_parser.parse(message)

    # 构建 TravelRequest
    today = date.today()
    start_date = today + timedelta(days=7)
    end_date = start_date + timedelta(days=intent.days - 1)

    request = TravelRequest(
        destination=intent.destination,
        origin=intent.origin,
        start_date=start_date,
        end_date=end_date,
        traveler_count=intent.traveler_count,
        budget=intent.budget,
        preferences={
            "interests": intent.special_requests.split(",") if intent.special_requests else [],
            "preference_level": intent.preference_level,
            "spend_all_budget": intent.spend_all_budget,
        },
    )

    # 使用统一协调器
    result = unified_coordinator.plan_trip(request)
    unified_coordinator.add_conversation_turn(message, f"规划完成: {result.destination}")

    return format_unified_response(result)


def form_handler(
    destination: str,
    origin: str,
    days: int,
    traveler_count: int,
    budget: float,
    preference_level: str,
    interests: str,
) -> str:
    """表单模式处理器。"""
    if not destination:
        return "请填写目的地城市。"

    today = date.today()
    start_date = today + timedelta(days=7)
    end_date = start_date + timedelta(days=days - 1)

    request = TravelRequest(
        destination=destination,
        origin=origin or destination,
        start_date=start_date,
        end_date=end_date,
        traveler_count=traveler_count,
        budget=budget,
        preferences={
            "interests": [i.strip() for i in interests.split(",") if i.strip()] if interests else [],
            "preference_level": preference_level,
        },
    )

    result = unified_coordinator.plan_trip(request)
    return format_unified_response(result)


def create_unified_ui():
    """创建统一旅行规划系统 Gradio 界面。"""
    with gr.Blocks(
        title="统一旅行规划系统 — 五大 AI Agent 模块",
        theme=gr.themes.Soft(),
    ) as app:
        gr.Markdown("""
        # 统一旅行规划系统

        基于 **LangChain 多智能体架构**，**五大 AI Agent 模块**协同工作：

        | 模块 | 职责 |
        |------|------|
        | 🧠 规划模块 | 任务分解与执行计划生成 |
        | 🗂️ 记忆模块 | 多轮对话记忆与用户画像持久化 |
        | 🔧 工具调用模块 | 工具注册、LLM绑定、执行中间件 |
        | ⚡ 行动执行模块 | LangGraph 多智能体编排与并行执行 |
        | 📊 结果评估模块 | 多因子质量评分与约束校验 |
        """)

        with gr.Tabs():
            # 聊天模式
            with gr.TabItem("💬 聊天模式"):
                gr.Markdown("用自然语言描述您的旅行需求，例如：'我想去成都玩4天，两个人，预算8000元，喜欢美食和自然风光'")

                chat_interface = gr.ChatInterface(
                    fn=chat_handler,
                    chatbot=gr.Chatbot(height=500),
                    textbox=gr.Textbox(
                        placeholder="请输入您的旅行需求...",
                        container=False,
                        scale=7,
                    ),
                    title="",
                    description="",
                    examples=[
                        "我想去北京玩4天，两个人，预算8000元，喜欢历史文化",
                        "帮我规划成都3日游，预算5000元，想体验美食和熊猫",
                        "从上海出发去西安，5天，预算10000元",
                    ],
                )

            # 表单模式
            with gr.TabItem("📋 表单模式"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 旅行参数")

                        dest_input = gr.Dropdown(
                            label="目的地",
                            choices=["北京", "上海", "杭州", "成都", "西安", "南京", "苏州", "重庆", "广州", "深圳"],
                            value="北京",
                        )
                        origin_input = gr.Textbox(label="出发城市", value="北京")
                        days_slider = gr.Slider(label="旅行天数", minimum=1, maximum=14, value=4, step=1)
                        people_slider = gr.Slider(label="旅行人数", minimum=1, maximum=10, value=2, step=1)
                        budget_slider = gr.Slider(label="预算（元）", minimum=1000, maximum=50000, value=8000, step=500)
                        pref_dropdown = gr.Dropdown(
                            label="消费档次",
                            choices=["经济型", "舒适型", "高档型", "豪华型"],
                            value="舒适型",
                        )
                        interests_input = gr.Textbox(
                            label="兴趣偏好（逗号分隔）",
                            placeholder="历史文化, 美食, 自然风光",
                        )

                        submit_btn = gr.Button("开始规划", variant="primary", size="lg")

                    with gr.Column(scale=2):
                        gr.Markdown("### 规划结果")
                        form_output = gr.Markdown("等待规划...", label="规划输出")

                submit_btn.click(
                    fn=form_handler,
                    inputs=[
                        dest_input, origin_input, days_slider, people_slider,
                        budget_slider, pref_dropdown, interests_input,
                    ],
                    outputs=[form_output],
                )

            # 系统信息
            with gr.TabItem("ℹ️ 系统信息"):
                gr.Markdown("""
                ### 五大 AI Agent 模块详解

                #### 1. 规划模块 (Planning Module)
                - **TaskDecomposer**: 将自然语言请求分解为原子子任务
                - **PlanGenerator**: 生成带依赖关系的结构化执行计划
                - 支持 LLM 智能分解 + 规则兜底

                #### 2. 记忆模块 (Memory Module)
                - **ConversationMemory**: 多轮对话管理（滑动窗口 + 自动摘要压缩）
                - **UserProfile**: 用户偏好画像（跨会话持久化）
                - **MemoryStore**: JSON 文件持久化存储

                #### 3. 工具调用模块 (Tool Invocation Module)
                - **ToolRegistry**: 集中式工具注册中心（19个工具，4个智能体域）
                - **ToolExecutor**: 带日志/重试/异常处理的执行中间件
                - **create_agent_with_tools()**: 工具绑定到 LLM（function-calling）

                #### 4. 行动执行模块 (Action Execution Module)
                - **AgentOrchestrator**: 基于拓扑排序的工作流编排
                - 支持并行执行（住宿/交通/餐饮可并发）
                - 预算修订循环（最多3次迭代）

                #### 5. 结果评估模块 (Result Evaluation Module)
                - **PlanEvaluator**: 5维度质量评分（预算效率/行程可行性/兴趣覆盖/地理连贯性/约束满足）
                - **ConstraintValidator**: 6项硬性约束校验
                - **FeedbackIntegrator**: 用户反馈收集与偏好调整
                """)

                gr.Markdown("""
                ### 技术栈

                | 组件 | 技术 |
                |------|------|
                | Agent 框架 | LangChain / LangGraph |
                | LLM | Qwen (通义千问) via DashScope |
                | 数据验证 | Pydantic |
                | Web UI | Gradio |
                | 外部 API | 高德地图 / 美团开放平台 |
                | 工具定义 | @tool 装饰器 (langchain_core) |
                """)

    return app


if __name__ == "__main__":
    app = create_unified_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=False,
        show_error=True,
    )
