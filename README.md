# 智能旅行规划系统 (Intelligent Travel Planner)

基于LangChain多智能体架构的智能旅行规划系统，使用阿里通义千问Qwen作为LLM，通过多Agent协作实现个性化的旅行规划服务。

## 功能特点

- **多智能体协作**: 4个专业Agent协同工作
  - 🗺️ 行程规划师 - 设计每日活动路线
  - 🏨 住宿协调员 - 推荐合适的酒店
  - 🚄 交通调度员 - 规划往返和当地交通
  - 💰 预算审计员 - 汇总费用并检查预算

- **国内LLM支持**: 使用阿里通义千问Qwen模型
- **模拟数据**: 预置北京、上海、杭州、成都、西安等城市数据
- **预算优化**: 自动检查预算并提供节省建议

## 项目结构

```
intelligent-travel-planner/
├── config/                 # 配置管理
│   └── settings.py         # API密钥、模型参数
├── data/                   # 数据层
│   ├── models.py           # 数据模型定义
│   └── mock_data.py        # 模拟数据
├── agents/                 # Agent层
│   ├── base.py             # Agent基类
│   ├── itinerary/          # 行程规划师
│   ├── accommodation/      # 住宿协调员
│   ├── transportation/     # 交通调度员
│   └── budget/             # 预算审计员
├── orchestration/          # 编排层
│   ├── state.py            # 状态定义
│   └── coordinator.py      # 主协调器
├── utils/                  # 工具函数
├── tests/                  # 测试
├── main.py                 # 命令行入口
├── web_app.py              # Web界面入口
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

编辑 `.env` 文件，填入你的通义千问API密钥：

```bash
DASHSCOPE_API_KEY=your_api_key_here
```

获取API密钥：访问 [阿里云DashScope控制台](https://dashscope.console.aliyun.com/)

### 3. 运行程序

```bash
# Web界面模式（推荐）
python web_app.py

# 命令行默认模式
python main.py

# 命令行交互式模式
python main.py -i
```

Web界面启动后，在浏览器中打开 http://localhost:7860 即可使用。

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

## Agent说明

### 1. 行程规划师 (Itinerary Planner)

**职责**: 根据目的地、天数、兴趣偏好设计每日活动路线

**工具**:
- `search_attractions` - 搜索景点
- `get_attraction_details` - 获取景点详情
- `optimize_route` - 优化游览路线

### 2. 住宿协调员 (Accommodation Agent)

**职责**: 根据预算、位置推荐酒店

**工具**:
- `search_hotels` - 搜索酒店
- `get_hotel_details` - 获取酒店详情
- `calculate_accommodation_cost` - 计算住宿费用

### 3. 交通调度员 (Transportation Agent)

**职责**: 规划往返交通和当地交通

**工具**:
- `search_flights` - 搜索航班
- `search_trains` - 搜索火车
- `estimate_local_transport` - 估算当地交通费用
- `compare_transport_options` - 比较交通方式

### 4. 预算审计员 (Budget Auditor)

**职责**: 汇总费用、检查预算、提供建议

**工具**:
- `calculate_total_cost` - 计算总费用
- `check_budget` - 检查预算
- `suggest_savings` - 提供节省建议

## 工作流程

```
用户请求 → 行程规划师 → 住宿协调员 → 交通调度员 → 预算审计员
                                                          ↓
                                              ┌───────────┴───────────┐
                                              │    预算是否充足？      │
                                              └───────────┬───────────┘
                                                    │           │
                                                   NO          YES
                                                    │           │
                                              调整并重新规划    输出结果
```

## 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_workflow.py -v
```

## 扩展方向

1. **添加更多城市数据**: 扩展模拟数据覆盖更多目的地
2. **接入真实API**: 集成高德地图、携程、12306等API
3. **添加本地向导Agent**: 提供季节活动、支付提示等
4. **Web界面**: 使用Streamlit或Gradio构建Web应用
5. **行程保存**: 支持保存和分享旅行计划

## 技术栈

- **LangChain**: Agent框架
- **LangGraph**: 工作流编排
- **通义千问 (Qwen)**: 大语言模型
- **Gradio**: Web交互界面
- **Pydantic**: 数据验证
- **pytest**: 测试框架

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

---

**注意**: 本项目使用模拟数据进行演示，实际使用时需要：
1. 配置通义千问API密钥
2. 可选：接入真实的旅行API服务
