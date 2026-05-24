# 智能旅行规划系统 (Intelligent Travel Planner)

基于 **LangChain + LangGraph** 多智能体架构的旅行规划系统。四个专业 Agent（行程规划师、住宿协调员、餐饮规划员、预算审计员）各自运行标准 **ReAct 循环**，由 LangGraph `StateGraph` 统一编排调度，实现并行执行、条件路由和预算修订闭环。

完整实现 AI Agent 五大核心模块（规划、记忆、工具调用、行动执行、结果评估），集成**高德地图**与**美团开放平台**实时数据。

---

## LangGraph 智能体编排流程

这是本项目的核心技术亮点 —— 用 LangGraph `StateGraph` 将四个 ReAct Agent 编排为带条件循环的有向图。LLM 在每个节点内自主决定工具调用，图结构根据预算是否超支动态路由，形成"执行→评估→修订→再执行"的闭环。

```
                        ┌─────────────────────┐
                        │    用户自然语言输入    │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │    规划模块 + 记忆模块  │
                        │  TaskDecomposer     │
                        │  UserProfile        │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   LangGraph 编译图    │
                        └──────────┬──────────┘
                                   │
                                   ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                      StateGraph 执行流程                      │
    │                                                              │
    │                          START                               │
    │                            │                                 │
    │                            ▼                                 │
    │              ┌─────────────────────────┐                     │
    │              │    itinerary_agent      │                     │
    │              │       行程规划师          │                     │
    │              │   (ReAct, 5 tools)      │                     │
    │              │       高德地图 API       │                     │
    │              └────────────┬────────────┘                     │
    │                           │                                  │
    │                    ┌──────┴──────┐                           │
    │                    │  add_conditional_edges                  │
    │                    │   (Send API)  │                          │
    │                    └──────┬──────┘                           │
    │                           │                                  │
    │              ┌────────────┼────────────┐                     │
    │              │            │            │                     │
    │              ▼            │            ▼                     │
    │  ┌──────────────────┐    │    ┌──────────────────┐          │
    │  │accommodation_agent│   │    │   food_agent      │          │
    │  │    住宿协调员       │   │    │    餐饮规划员       │          │
    │  │  (ReAct, 4 tools) │   │    │  (ReAct, 5 tools) │          │
    │  │    高德地图 API    │   │    │    美团开放平台     │          │
    │  └────────┬─────────┘    │    └────────┬─────────┘          │
    │           │              │             │                     │
    │           └──────────────┼─────────────┘                     │
    │                          │  (汇聚)                           │
    │                          ▼                                   │
    │              ┌─────────────────────────┐                     │
    │              │     budget_agent        │                     │
    │              │       预算审计员          │                     │
    │              │   (ReAct, 5 tools)      │                     │
    │              │    Qwen LLM + 规则引擎   │                     │
    │              └────────────┬────────────┘                     │
    │                           │                                  │
    │                           ▼                                  │
    │              ┌─────────────────────────┐                     │
    │              │      evaluate_node       │                     │
    │              │       结果评估            │                     │
    │              │   5维评分 + 6项约束校验   │                     │
    │              └────────────┬────────────┘                     │
    │                           │                                  │
    │                    ┌──────┴──────┐                           │
    │                    │ add_conditional_edges                    │
    │                    └──────┬──────┘                           │
    │                           │                                  │
    │              ┌────────────┼────────────┐                     │
    │              │            │            │                     │
    │         budget OK?   revisions < 3?  revisions >= 3?        │
    │              │            │            │                     │
    │              ▼            ▼            ▼                     │
    │            END      ┌──────────┐     END                    │
    │                     │  revise  │                             │
    │                     │  修订节点  │                             │
    │                     │ 降住宿/减景点│                            │
    │                     └────┬─────┘                             │
    │                          │                                   │
    │                          └──→ budget_agent (loop)            │
    └──────────────────────────────────────────────────────────────┘
```

### 编排关键点

| 机制 | LangGraph API | 作用 |
|------|--------------|------|
| **并行 fan-out** | `add_conditional_edges` + `Send` | 行程规划完成后，住宿协调员与餐饮规划员并发执行，互不阻塞 |
| **汇聚** | `add_edge("accommodation", "budget")` + `add_edge("food", "budget")` | 两个并行分支都完成后，预算审计员才启动 |
| **条件路由** | `add_conditional_edges` + `Literal["revise", "__end__"]` | 预算充足 → 结束；超支且未达上限 → 修订循环 |
| **状态管理** | `AgentState(TypedDict)` + `add_messages` reducer | 全局共享状态，消息追加而非覆盖 |
| **ReAct 循环** | `model.bind_tools(tools)` + `ToolMessage` | 每个 Agent 内部由 LLM 自主决策工具调用，6 轮迭代上限 |

---

## 四大智能体

| Agent | 角色 | 数据源 | 工具数 | 核心工具 |
|-------|------|--------|--------|----------|
| **行程规划师** | 设计每日活动路线，优化景点顺序 | 高德地图 POI 搜索 | 5 | `search_attractions`, `get_city_highlights`, `optimize_route`, `get_attraction_details`, `search_restaurants` |
| **住宿协调员** | 按预算推荐酒店，计算住宿费用 | 高德地图 POI 搜索 | 4 | `search_hotels`, `recommend_hotels_by_budget`, `calculate_accommodation_cost`, `get_hotel_details` |
| **餐饮规划员** | 搜索特色餐厅，制定每日餐饮计划 | 美团开放平台 | 5 | `search_restaurants_by_city`, `search_local_cuisine`, `calculate_food_cost`, `recommend_dining_plan`, `get_restaurant_detail` |
| **预算审计员** | 汇总费用、检查预算、生成报告 | Qwen LLM + 规则引擎 | 5 | `calculate_total_cost`, `check_budget`, `suggest_savings`, `generate_budget_report`, `estimate_food_cost` |

### ReAct Agent 内部机制

每个 Agent 节点都运行标准的 **ReAct (Reasoning + Acting)** 循环，而非手动调用工具:

```python
# 核心: LLM 绑定工具 → 自主决策 → 执行 → 反馈 → 循环
model_with_tools = model.bind_tools(tools)    # 工具绑定到 LLM
tool_map = {t.name: t for t in tools}

for iteration in range(max_iterations):
    response = model_with_tools.invoke(messages)  # LLM 决定调用哪个工具
    tool_calls = response.tool_calls

    if not tool_calls:
        return response.content   # LLM 认为可以给出最终答案

    for tc in tool_calls:
        result = tool_map[tc["name"]].invoke(tc["args"])   # 执行工具
        messages.append(ToolMessage(content=result, ...))   # 结果返回 LLM
```

LLM 在循环中看到工具执行结果后，可以继续调用更多工具（如先搜索景点、再获取详情、最后优化路线），直到它认为信息足够给出最终答案。

---

## 五大 AI Agent 模块

| 模块 | 核心类 | 职责 |
|------|--------|------|
| **规划模块** | `TaskDecomposer`, `PlanGenerator` | 自然语言请求分解为原子子任务，生成带依赖关系的结构化执行计划，LLM 智能分解 + 拓扑排序兜底 |
| **记忆模块** | `ConversationMemory`, `UserProfile`, `MemoryStore` | 三层记忆体系：短期滑动窗口对话记忆 + 长期用户画像持久化 + 情景旅行方案复用 |
| **工具调用模块** | `ToolRegistry`, `bind_tools` | 19 个工具集中注册管理，按 Agent 分域，`bind_tools` 绑定到 LLM 实现 function-calling |
| **行动执行模块** | `TravelGraphBuilder`, `run_react_agent` | LangGraph `StateGraph` 编排四个 ReAct Agent，`Send` API 并行 fan-out，条件边实现修订循环 |
| **结果评估模块** | `PlanEvaluator`, `ConstraintValidator` | 5 维度质量评分（预算效率/行程可行性/兴趣覆盖/地理连贯性/约束满足），6 项硬性约束校验 |

---

## 项目结构

```
intelligent-travel-planner/
├── modules/                     # 五大 AI Agent 核心模块
│   ├── planning.py              # 规划模块 — TaskDecomposer + PlanGenerator
│   ├── memory.py                # 记忆模块 — ConversationMemory + UserProfile + MemoryStore
│   ├── tools.py                 # 工具调用模块 — ToolRegistry (19 tools, 4 agent domains)
│   ├── execution.py             # 行动执行模块 — run_react_agent + TravelGraphBuilder (StateGraph)
│   └── evaluation.py            # 结果评估模块 — PlanEvaluator + ConstraintValidator
├── agents/                      # Agent 层
│   ├── base.py                  # Agent 基类 + 4 个系统提示词
│   ├── itinerary/               # 行程规划师 (景点搜索、路线优化) → 高德API
│   ├── accommodation/           # 住宿协调员 (酒店搜索、费用计算) → 高德API
│   ├── food/                    # 餐饮规划员 (餐厅搜索、餐饮计划) → 美团API
│   └── budget/                  # 预算审计员 (费用汇总、预算检查)
├── unified_coordinator.py       # 统一协调器 — 整合五大模块 + LangGraph 编排
├── utils/
│   ├── llm.py                   # Qwen LLM 封装 (通义千问 via DashScope)
│   ├── intent_parser.py         # 基于 LLM 的意图解析器
│   ├── amap_api.py              # 高德地图 Web 服务 API
│   ├── meituan_api.py           # 美团开放平台 API (含 5 城市参考数据降级)
│   └── logger.py                # 日志模块
├── data/
│   ├── models.py                # Pydantic v2 数据模型
│   └── mock_data.py             # 离线参考数据 (覆盖 10+ 城市)
├── config/
│   └── settings.py              # 环境变量配置 (pydantic-settings)
├── main.py                      # CLI 入口
├── unified_app.py               # Gradio Web 界面 (聊天 + 表单双模式)
└── pyproject.toml               # 项目配置 (uv 依赖管理)
```

---

## 快速开始

### 1. 安装

```bash
cd intelligent-travel-planner
uv sync
```

### 2. 配置

编辑 `.env` 文件：

```env
# 通义千问 (必填 — ReAct 推理引擎)
DASHSCOPE_API_KEY=your_key_here
QWEN_MODEL=qwen-plus

# 高德地图 (必填 — 景点/酒店 POI 搜索)
AMAP_API_KEY=your_amap_key_here

# 美团开放平台 (可选 — 未配置时自动降级到内置参考数据)
MEITUAN_API_KEY=your_meituan_key_here
```

**无 API Key 也能运行**: 系统内置 `MockChatModel` 模拟 LLM 响应，各 API 模块内置覆盖 5-10 个城市的离线参考数据。未配置任何 API Key 时，系统自动降级，完整流程仍可跑通。

### 3. 运行

```bash
# 统一模式 CLI (LangGraph 编排四个 ReAct Agent)
python main.py --unified

# 交互式 CLI
python main.py --unified -i

# Web 界面 (Gradio)
python unified_app.py
```

---

## 使用示例

### 代码调用

```python
from datetime import date, timedelta
from data.models import TravelRequest
from unified_coordinator import unified_coordinator

request = TravelRequest(
    destination="成都",
    origin="上海",
    start_date=date.today() + timedelta(days=14),
    end_date=date.today() + timedelta(days=16),
    traveler_count=2,
    budget=6000.0,
    preferences={
        "interests": ["美食", "自然风光"],
        "preference_level": "舒适型",
    },
)

# LangGraph 编排执行: itinerary → [accommodation ‖ food] → budget → evaluate
result = unified_coordinator.plan_trip(request)

# 查看各 Agent 的 ReAct 输出
print(result.itinerary["final_response"])    # 行程规划师
print(result.accommodation["final_response"]) # 住宿协调员
print(result.food["final_response"])          # 餐饮规划员
print(result.budget_report)                   # 预算审计员

# 质量评估
if result.evaluation:
    print(f"评分: {result.evaluation.overall_score}/100 ({result.evaluation.grade})")
    print(f"约束: {len(result.evaluation.passed_constraints)} 通过, "
          f"{len(result.evaluation.failed_constraints)} 失败")

# 执行追踪
for log_entry in result.execution_log:
    print(f"  {log_entry}")
```

### 实际运行输出

```
============================================================
  统一旅行规划系统 (LangGraph + ReAct Agent)
  目的地: 成都 | 3天 | 2人 | ¥6000.0
============================================================

LangGraph 工作流启动 (ReAct Agent 模式):
  START → itinerary → [accommodation ‖ food] → budget
  → evaluate → conditional(OK→END / 超支→revise→budget)

============================================================
  规划完成 (LangGraph + ReAct)
  总费用: ¥2520 | 预算: 充足
  质量评分: 55.3/100 (D)
  修订次数: 0
============================================================

执行追踪:
  [记忆模块] 用户画像加载 (历史: 4 次)
  [规划模块] 5 个子任务, 3 个层级
  [ReAct] 行程规划师: 成都博物馆 → 人民公园 → 宽窄巷子 → ...
  [ReAct] 住宿协调员: 四川锦江宾馆(4.7分) | 望江宾馆(4.8分) | ...
  [ReAct] 餐饮规划员: 陈麻婆豆腐 | 龙抄手 | 大龙燚火锅 | ...
  [ReAct] 预算审计员: ¥2520/¥6000, 结余¥3480, 预算健康
  [评估模块] 55.3/100 (D), 5 通过 / 1 失败
```

---

## 设计亮点

### 1. LangGraph 原生编排，真正并行

`itinerary` 节点完成后通过 `Send` API 将状态分发给 `accommodation` 和 `food`，两个 Agent 在 LangGraph 运行时中并发执行。不是 `asyncio.gather()`，不是线程池，而是 LangGraph 原生的图并行语义。`budget` 节点在两个分支都完成后自动汇聚。

```python
def _fanout_after_itinerary(self, state: AgentState) -> list[Send]:
    return [
        Send("accommodation", state),  # 并行分支 1
        Send("food", state),           # 并行分支 2
    ]
```

### 2. ReAct Agent，LLM 自主决策

每个 Agent 通过 `model.bind_tools(tools)` 绑定 4-5 个工具，LLM 在循环中自行决定调用哪些工具、何时调用、何时给出最终答案。例如餐饮规划员会自动先调用 `search_local_cuisine` 了解当地特色，再调用 `recommend_dining_plan` 制定计划，最后调用 `calculate_food_cost` 汇总费用 —— 这个顺序是 LLM 自己推理出来的，不是代码预设的。

### 3. 预算修订闭环

`add_conditional_edges` 实现条件路由: 超支时自动进入 `revise` 节点（降住宿 → 减景点），然后回到 `budget` 重新审计。最多 3 次迭代，每次修订结果实时反映在共享状态中。

### 4. API → 离线参考数据三级降级

高德/美团 API 可用 → 实时 POI 数据。不可用 → 内置覆盖 5-10 个城市的参考数据（基于真实餐厅/酒店信息）。LLM 不可用 → `MockChatModel` 模拟响应。系统始终可运行，不会因缺少 API Key 而崩溃。

### 5. 三层记忆体系

短期滑动窗口对话记忆（自动摘要压缩） + 长期用户画像 JSON 持久化（跨会话累积偏好） + 情景旅行方案存储复用。

### 6. 五维质量量化

每个方案输出 5 维评分（预算效率 / 行程可行性 / 兴趣覆盖 / 地理连贯性 / 约束满足）+ 字母评级（A-F）+ 具体改进建议。

---

## 技术栈

| 层 | 技术 |
|----|------|
| Agent 框架 | LangChain (tool definition, message types) + LangGraph (StateGraph, Send, conditional edges) |
| LLM | Qwen-Plus (通义千问) via DashScope |
| 外部 API | 高德地图 Web API (景点/酒店 POI) + 美团开放平台 (餐厅搜索) |
| 数据校验 | Pydantic v2 |
| Web 界面 | Gradio (聊天 + 表单双模式) |
| 依赖管理 | uv |
| 测试 | pytest |

---

## 扩展方向

- **天气 Agent**: 接入高德天气 API，根据天气动态调整行程
- **RAG 知识增强**: 引入旅游攻略/游记向量库，为 LLM 提供领域知识
- **方案导出**: 支持导出 PDF / Markdown 旅行方案
- **多语言**: 支持英文界面与境外目的地

---

LangChain · LangGraph · Qwen (通义千问) · 高德地图 API · 美团开放平台 · Gradio · Pydantic · pytest · uv
