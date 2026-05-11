# 智能旅行规划系统 (Intelligent Travel Planner)

基于LangChain多智能体架构的智能旅行规划系统，使用**高德地图API**获取真实景点/酒店/餐厅数据，通过多Agent协作实现个性化的旅行规划服务。

## 功能特点

- **多智能体协作**: 4个专业Agent协同工作
  - 🗺️ 行程规划师 — 高德地图API搜索景点，生成每日行程
  - 🏨 住宿协调员 — 高德地图API搜索酒店，推荐住宿方案
  - 🍜 餐饮推荐 — 高德地图API搜索餐厅，推荐当地美食
  - 💰 预算审计员 — 计算总费用，智能优化预算分配

- **真实数据驱动**: 通过高德地图Web服务API获取实时POI数据
  - 景点搜索：风景名胜、博物馆、古迹等真实POI
  - 酒店搜索：酒店、宾馆、民宿等真实房源
  - 餐厅搜索：中餐厅、火锅、小吃等餐饮POI
- **智能意图解析**: 基于Qwen LLM理解自然语言，支持多轮对话上下文
- **预算智能优化**: 用户要求"花光预算"时，自动升级住宿/餐饮档次

## 项目结构

```
intelligent-travel-planner/
├── config/                 # 配置管理
│   └── settings.py         # API密钥、模型参数 (从.env加载)
├── data/                   # 数据层
│   ├── models.py           # Pydantic数据模型定义
│   └── mock_data.py        # 离线参考数据（API不可用时的降级方案）
├── agents/                 # Agent层
│   ├── base.py             # Agent基类和系统提示词
│   ├── itinerary/          # 行程规划师（景点搜索、路线优化）
│   ├── accommodation/      # 住宿协调员（酒店搜索、费用计算）
│   ├── transportation/     # 交通调度员（航班/火车参考价格）
│   └── budget/             # 预算审计员（费用汇总、预算检查）
├── orchestration/          # 编排层
│   └── coordinator.py      # 多Agent协作协调器
├── utils/                  # 工具层
│   ├── amap_api.py         # 高德地图Web服务API封装
│   ├── llm.py              # Qwen LLM (通义千问) 封装
│   ├── intent_parser.py    # 基于LLM的意图解析器
│   └── logger.py           # 日志配置
├── tests/                  # 测试
│   └── test_workflow.py    # 单元测试和集成测试
├── main.py                 # 命令行入口
├── web_app.py              # Web界面入口 (Gradio表单+对话双模式)
├── simple_app.py           # 四Agent协作界面 (Gradio对话模式)
├── simple_coordinator.py   # 四Agent协作协调器 (高德API直连)
└── pyproject.toml          # 项目配置
```

## 快速开始

### 1. 安装依赖

```bash
cd intelligent-travel-planner
pip install -e .
```

或使用uv:

```bash
uv sync
```

### 2. 配置API密钥

复制环境变量示例文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入API密钥：

```bash
# 通义千问API密钥 (可选，未配置时使用规则解析)
DASHSCOPE_API_KEY=your_api_key_here

# 高德地图Web服务API密钥 (必填，用于景点/酒店/餐厅搜索)
AMAP_API_KEY=your_amap_key_here
```

获取API密钥：
- 通义千问：[阿里云DashScope控制台](https://dashscope.console.aliyun.com/)
- 高德地图：[高德开放平台](https://lbs.amap.com/)

### 3. 运行程序

```bash
# Web界面模式 — 对话+表单双模式 (推荐)
python web_app.py

# 四Agent协作界面 — 带上下文记忆的对话模式
python simple_app.py

# 命令行默认模式
python main.py

# 命令行交互式模式
python main.py -i
```

Web界面启动后，在浏览器中打开终端显示的地址（默认 http://localhost:8099）即可使用。

## 使用示例

### 代码调用

```python
from datetime import date
from data.models import TravelRequest
from orchestration.coordinator import coordinator

# 创建旅行请求
request = TravelRequest(
    destination="北京",
    origin="上海",
    start_date=date(2025, 6, 15),
    end_date=date(2025, 6, 18),
    traveler_count=2,
    budget=5000.0,
    preferences={
        "interests": ["历史文化", "美食"],
    },
)

# 执行规划
result = coordinator.plan_trip(request)

# 输出结果
print(f"总费用: ¥{result.total_cost}")
print(f"预算状态: {'充足' if result.is_within_budget else '超支'}")
```

### 输出示例

```
📋 旅行规划报告 - 北京
============================================================

📍 目的地: 北京
📅 行程天数: 4天
👥 旅行人数: 2人
💰 预算: ¥5000

------------------------------------------------------------
📊 费用明细
------------------------------------------------------------
  🎫 门票费用: ¥240
  🏨 住宿费用: ¥1200
  🚄 交通费用: ¥1000
  🍜 餐饮费用: ¥1600
  📦 其他费用: ¥200

  💵 总费用: ¥4240
  ✅ 预算充足，剩余 ¥760

------------------------------------------------------------
💡 旅行贴士
------------------------------------------------------------
  1. 出发前请检查北京的天气预报，准备合适的衣物。
  2. 故宫门票建议提前10天网上预约。
  ...
```

## 数据来源

| 数据类型 | 数据源 | 说明 |
|---------|--------|------|
| 景点信息 | **高德地图POI搜索** | 实时搜索风景名胜、博物馆、古迹等 |
| 酒店信息 | **高德地图POI搜索** | 实时搜索酒店、宾馆、民宿等 |
| 餐饮信息 | **高德地图POI搜索** | 实时搜索餐厅、火锅、小吃等 |
| 交通参考价 | 离线参考数据 | 航班/火车实时票价需付费API授权，使用基于真实票价的参考数据 |
| 当地交通 | 各城市实际价格 | 基于各城市真实地铁/公交/出租车起步价 |

> **降级策略**: 当高德API不可用（无网络或Key失效）时，自动降级到离线参考数据，确保系统仍可运行。

## Agent说明

### 1. 行程规划师 (Itinerary Planner)

**职责**: 根据目的地、天数、兴趣偏好设计每日活动路线

**数据来源**: 高德地图API → 离线参考数据

**工具**:
- `search_attractions` — 搜索城市景点（高德API优先）
- `get_attraction_details` — 获取景点详情（高德API优先）
- `optimize_route` — 优化游览路线
- `get_city_highlights` — 获取城市旅行亮点

### 2. 住宿协调员 (Accommodation Agent)

**职责**: 根据预算、位置推荐酒店

**数据来源**: 高德地图API → 离线参考数据

**工具**:
- `search_hotels` — 搜索酒店（高德API优先）
- `get_hotel_details` — 获取酒店详情（高德API优先）
- `calculate_accommodation_cost` — 计算住宿费用
- `recommend_hotels_by_budget` — 根据预算推荐酒店

### 3. 交通调度员 (Transportation Agent)

**职责**: 规划往返交通和当地交通方案

**数据来源**: 离线参考数据（实时12306/航班数据需付费API授权）

**工具**:
- `search_flights` — 搜索航班参考价格
- `search_trains` — 搜索火车参考价格
- `estimate_local_transport` — 估算当地交通费用（基于各城市真实价格）
- `compare_transport_options` — 比较交通方式

### 4. 预算审计员 (Budget Auditor)

**职责**: 汇总费用、检查预算、提供优化建议

**工具**:
- `calculate_total_cost` — 计算总费用
- `check_budget` — 检查预算状态
- `suggest_savings` — 提供节省建议
- `estimate_food_cost` — 估算餐饮费用
- `generate_budget_report` — 生成完整预算报告

## 工作流程

```
用户请求 → 意图解析器(LLM) → 行程规划师(高德API) → 住宿协调员(高德API)
                                                          ↓
                                                    餐饮推荐(高德API)
                                                          ↓
                                                    预算审计员(Qwen LLM)
                                                          ↓
                                              ┌───────────┴───────────┐
                                              │    预算是否充足？      │
                                              └───────────┬───────────┘
                                                    │           │
                                                   NO          YES
                                                    │           │
                                          LLM智能调整方案    输出结果
```

## 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_workflow.py -v
```

## 扩展方向

1. **接入实时交通数据**: 集成12306和航班数据API，获取实时票价和余票
2. **添加天气Agent**: 使用高德天气API提供目的地天气和出行建议
3. **行程持久化**: 支持保存、分享和导出旅行计划（PDF/JSON）
4. **多语言支持**: 为境外旅行提供多语言界面
5. **移动端适配**: 将Gradio界面适配为移动端友好的布局

## 技术栈

- **LangChain**: Agent框架和LLM抽象
- **LangGraph**: 工作流编排
- **通义千问 (Qwen)**: 大语言模型（自然语言理解 + 预算智能优化）
- **高德地图API**: 实时POI数据（景点/酒店/餐厅搜索）
- **Gradio**: Web交互界面
- **Pydantic**: 数据验证和模型定义
- **pytest**: 测试框架

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

---

**系统要求**:
1. 配置高德地图API密钥（必填，获取真实数据）
2. 配置通义千问API密钥（可选，未配置时使用规则解析）
