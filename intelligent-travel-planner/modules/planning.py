"""规划模块 —— 任务分解与执行计划生成。

负责将用户的自然语言旅行请求分解为原子化的子任务，
并生成带依赖关系的结构化执行计划，驱动后续智能体协同。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from utils.llm import qwen_brain
from utils.logger import get_logger

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskDependency(str, Enum):
    SEQUENTIAL = "sequential"  # 必须在上一任务完成后执行
    PARALLEL = "parallel"  # 可与同级任务并行执行


@dataclass
class SubTask:
    """原子子任务 —— 规划模块的最小执行单元。"""

    task_id: str
    name: str
    description: str
    agent: str  # 负责执行的智能体名称
    dependencies: list[str] = field(default_factory=list)  # 依赖的前置 task_id
    dependency_type: TaskDependency = TaskDependency.SEQUENTIAL
    tools_required: list[str] = field(default_factory=list)  # 需要的工具列表
    expected_output: str = ""  # 期望输出描述
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[dict] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2


@dataclass
class ExecutionPlan:
    """执行计划 —— 规划模块的顶层输出，驱动整个编排流程。"""

    destination: str
    days: int
    traveler_count: int
    budget: float
    preference_level: str
    tasks: list[SubTask] = field(default_factory=list)
    execution_order: list[list[str]] = field(default_factory=list)  # 按层级排列的 task_id
    metadata: dict = field(default_factory=dict)


class TaskDecomposer:
    """基于 LLM 的旅行任务分解器。

    将用户的自然语言请求拆解为结构化的子任务列表，
    识别任务间的依赖关系（串行/并行）。
    """

    DECOMPOSE_PROMPT = """你是一个旅行规划任务分解专家。请将用户的旅行规划请求拆解为独立的子任务。

对于每个子任务，请确定：
1. task_id: 唯一标识符
2. name: 任务名称
3. description: 任务描述
4. agent: 负责的智能体（itinerary/accommodation/transportation/budget）
5. dependencies: 依赖的前置任务ID列表
6. dependency_type: sequential（串行依赖）或 parallel（可并行）

旅行规划的标准子任务流程：
- 行程规划（itinerary）总是第一步
- 住宿安排（accommodation）和交通规划（transportation）可在行程确定后并行
- 预算审计（budget）必须在住宿和交通都完成后进行
- 如果预算不足，可能需要回到住宿或行程进行修订

请以JSON格式返回任务列表：
```json
{
    "tasks": [
        {
            "task_id": "task_1",
            "name": "搜索景点与生成行程",
            "description": "搜索目的地热门景点，生成每日行程安排",
            "agent": "itinerary",
            "dependencies": [],
            "dependency_type": "sequential",
            "tools_required": ["search_attractions", "get_attraction_details", "optimize_route", "get_city_highlights"],
            "expected_output": "每日行程安排与景点列表"
        },
        ...
    ],
    "parallel_groups": [["task_2", "task_3"]]
}
```"""

    def __init__(self) -> None:
        self._cache: dict[str, ExecutionPlan] = {}

    def decompose(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        preference_level: str = "舒适型",
        special_requests: str = "",
    ) -> ExecutionPlan:
        """分解用户旅行请求为子任务列表。"""
        logger.info(f"分解任务: {destination} {days}天 {traveler_count}人 {budget}元 [{preference_level}]")

        if qwen_brain.is_available():
            plan = self._llm_decompose(
                destination, days, traveler_count, budget,
                preference_level, special_requests,
            )
        else:
            plan = self._rule_decompose(
                destination, days, traveler_count, budget, preference_level,
            )

        logger.info(f"生成 {len(plan.tasks)} 个子任务, {len(plan.execution_order)} 个执行层级")
        return plan

    def _llm_decompose(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        preference_level: str,
        special_requests: str,
    ) -> ExecutionPlan:
        """使用 LLM 进行智能任务分解。"""
        prompt = f"""请为以下旅行请求分解子任务：

目的地: {destination}
天数: {days}天
人数: {traveler_count}人
预算: {budget}元
消费档次: {preference_level}
特殊要求: {special_requests or '无'}"""

        result = qwen_brain.parse_json_response(prompt, self.DECOMPOSE_PROMPT)
        if not result or "tasks" not in result:
            logger.warning("LLM 任务分解失败，使用规则兜底")
            return self._rule_decompose(destination, days, traveler_count, budget, preference_level)

        tasks = []
        for t in result.get("tasks", []):
            tasks.append(SubTask(
                task_id=t.get("task_id", f"task_{len(tasks)+1}"),
                name=t.get("name", "未命名任务"),
                description=t.get("description", ""),
                agent=t.get("agent", "itinerary"),
                dependencies=t.get("dependencies", []),
                dependency_type=TaskDependency(t.get("dependency_type", "sequential")),
                tools_required=t.get("tools_required", []),
                expected_output=t.get("expected_output", ""),
            ))

        parallel_groups = result.get("parallel_groups", [])
        execution_order = self._build_execution_order(tasks, parallel_groups)

        return ExecutionPlan(
            destination=destination,
            days=days,
            traveler_count=traveler_count,
            budget=budget,
            preference_level=preference_level,
            tasks=tasks,
            execution_order=execution_order,
            metadata={"source": "llm"},
        )

    def _rule_decompose(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        preference_level: str,
    ) -> ExecutionPlan:
        """规则驱动的任务分解（LLM 不可用时的兜底方案）。"""
        tasks = [
            SubTask(
                task_id="task_itinerary",
                name="搜索景点与生成行程",
                description=f"搜索{destination}热门景点，生成{days}天每日行程安排",
                agent="itinerary",
                dependencies=[],
                dependency_type=TaskDependency.SEQUENTIAL,
                tools_required=["search_attractions", "get_attraction_details", "optimize_route", "get_city_highlights"],
                expected_output="每日行程安排与景点列表",
            ),
            SubTask(
                task_id="task_accommodation",
                name="搜索酒店与住宿安排",
                description=f"搜索{destination}酒店，按{preference_level}档位匹配住宿",
                agent="accommodation",
                dependencies=["task_itinerary"],
                dependency_type=TaskDependency.PARALLEL,
                tools_required=["search_hotels", "get_hotel_details", "calculate_accommodation_cost", "recommend_hotels_by_budget"],
                expected_output="酒店推荐列表与住宿费用",
            ),
            SubTask(
                task_id="task_transportation",
                name="规划往返与当地交通",
                description="规划往返交通方式与当地交通方案",
                agent="transportation",
                dependencies=["task_itinerary"],
                dependency_type=TaskDependency.PARALLEL,
                tools_required=["search_flights", "search_trains", "estimate_local_transport", "compare_transport_options", "get_round_trip_cost"],
                expected_output="交通方案与费用估算",
            ),
            SubTask(
                task_id="task_food",
                name="搜索餐饮推荐",
                description=f"搜索{destination}特色餐厅与美食推荐",
                agent="budget",
                dependencies=["task_itinerary"],
                dependency_type=TaskDependency.PARALLEL,
                tools_required=["estimate_food_cost"],
                expected_output="餐厅推荐与餐饮预算",
            ),
            SubTask(
                task_id="task_budget_audit",
                name="预算审计与优化",
                description="汇总全量成本，校验预算边界，必要时触发修订",
                agent="budget",
                dependencies=["task_accommodation", "task_transportation", "task_food"],
                dependency_type=TaskDependency.SEQUENTIAL,
                tools_required=["calculate_total_cost", "check_budget", "suggest_savings", "generate_budget_report"],
                expected_output="预算审计报告与优化建议",
            ),
            SubTask(
                task_id="task_evaluation",
                name="结果评估与质量检查",
                description="对旅行方案进行多维度质量评估",
                agent="evaluator",
                dependencies=["task_budget_audit"],
                dependency_type=TaskDependency.SEQUENTIAL,
                tools_required=[],
                expected_output="质量评估报告",
            ),
        ]

        # 构建执行层级：同一层级的任务可并行
        execution_order = [
            ["task_itinerary"],  # 第1层：行程规划（先行）
            ["task_accommodation", "task_transportation", "task_food"],  # 第2层：并行
            ["task_budget_audit"],  # 第3层：预算审计
            ["task_evaluation"],  # 第4层：质量评估
        ]

        return ExecutionPlan(
            destination=destination,
            days=days,
            traveler_count=traveler_count,
            budget=budget,
            preference_level=preference_level,
            tasks=tasks,
            execution_order=execution_order,
            metadata={"source": "rule"},
        )

    def _build_execution_order(
        self,
        tasks: list[SubTask],
        parallel_groups: list[list[str]],
    ) -> list[list[str]]:
        """根据依赖关系和并行组构建执行顺序。"""
        if parallel_groups:
            return parallel_groups

        # 拓扑排序：按依赖层级分组
        task_map = {t.task_id: t for t in tasks}
        levels: list[list[str]] = []
        remaining = set(task_map.keys())

        while remaining:
            current_level = []
            for tid in list(remaining):
                task = task_map[tid]
                if all(dep not in remaining for dep in task.dependencies):
                    current_level.append(tid)
            if not current_level:
                # 循环依赖或所有任务已处理
                current_level = list(remaining)
            for tid in current_level:
                remaining.discard(tid)
            levels.append(current_level)

        return levels


class PlanGenerator:
    """执行计划生成器 —— 将分解后的任务组装为可执行的 ExecutionPlan。"""

    def __init__(self, decomposer: TaskDecomposer | None = None) -> None:
        self.decomposer = decomposer or TaskDecomposer()

    def generate(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        preference_level: str = "舒适型",
        special_requests: str = "",
    ) -> ExecutionPlan:
        """生成完整的执行计划。"""
        plan = self.decomposer.decompose(
            destination=destination,
            days=days,
            traveler_count=traveler_count,
            budget=budget,
            preference_level=preference_level,
            special_requests=special_requests,
        )
        self._validate_plan(plan)
        return plan

    def revise(
        self,
        plan: ExecutionPlan,
        failed_task_id: str,
        reason: str,
    ) -> ExecutionPlan:
        """根据失败的任务修订执行计划。"""
        logger.info(f"修订计划: 任务 {failed_task_id} 失败, 原因: {reason}")
        for task in plan.tasks:
            if task.task_id == failed_task_id:
                task.status = TaskStatus.FAILED
                task.error = reason
                if task.retry_count < task.max_retries:
                    task.status = TaskStatus.PENDING
                    task.retry_count += 1
                    logger.info(f"任务 {failed_task_id} 将重试 ({task.retry_count}/{task.max_retries})")
        return plan

    @staticmethod
    def _validate_plan(plan: ExecutionPlan) -> None:
        """验证执行计划的完整性和无环性，自动修复不匹配的执行顺序。"""
        task_ids = {t.task_id for t in plan.tasks}

        # 检查所有依赖引用的任务是否存在
        for task in plan.tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    raise ValueError(f"任务 {task.task_id} 依赖不存在的任务 {dep}")

        # 检查执行顺序涵盖所有任务
        ordered_ids = set()
        for level in plan.execution_order:
            ordered_ids.update(level)
        if ordered_ids != task_ids:
            # 自动重建执行顺序（按拓扑排序）
            logger.info("执行顺序与任务列表不匹配，自动重建拓扑排序")
            task_map = {t.task_id: t for t in plan.tasks}
            levels: list[list[str]] = []
            remaining = set(task_map.keys())
            while remaining:
                current_level = []
                for tid in list(remaining):
                    task = task_map[tid]
                    if all(dep not in remaining for dep in task.dependencies):
                        current_level.append(tid)
                if not current_level:
                    current_level = list(remaining)
                for tid in current_level:
                    remaining.discard(tid)
                levels.append(current_level)
            plan.execution_order = levels

        logger.info(f"计划验证通过: {len(plan.tasks)} 个任务, {len(plan.execution_order)} 个层级")
