"""行动执行模块 —— LangGraph 多智能体编排与并行执行。

基于 LangGraph StateGraph 实现：
- 声明式工作流定义（节点 + 边 + 条件分支）
- 并行执行独立智能体（住宿、交通可并发）
- 状态管理与上下文传递
- 预算修订循环（最多 3 次迭代）
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TypedDict

from utils.logger import get_logger

logger = get_logger(__name__)


class ExecutionPhase(str, Enum):
    """执行阶段枚举。"""

    INIT = "init"
    PLANNING = "planning"  # 任务分解
    ITINERARY = "itinerary"  # 行程规划
    ACCOMMODATION = "accommodation"  # 住宿安排
    TRANSPORTATION = "transportation"  # 交通规划
    FOOD = "food"  # 餐饮推荐
    BUDGET_AUDIT = "budget_audit"  # 预算审计
    EVALUATION = "evaluation"  # 结果评估
    REVISION = "revision"  # 修订循环
    COMPLETE = "complete"  # 执行完成
    FAILED = "failed"  # 执行失败


@dataclass
class WorkflowNode:
    """工作流节点 —— 表示编排图中的一个执行步骤。"""

    node_id: str
    name: str
    phase: ExecutionPhase
    agent: str  # 负责执行的智能体
    handler: Optional[Callable] = None  # 执行函数
    depends_on: list[str] = field(default_factory=list)  # 依赖的 node_id
    can_parallel: bool = False  # 是否可与同级节点并行
    retry_on_fail: bool = True  # 失败时是否重试
    timeout: float = 60.0  # 超时时间（秒）


class ExecutionState(TypedDict, total=False):
    """执行状态 —— 在工作流节点间传递的上下文。

    使用 TypedDict 以兼容 LangGraph StateGraph。
    """

    # 输入
    destination: str
    origin: str
    days: int
    traveler_count: int
    budget: float
    preference_level: str
    spend_all_budget: bool
    special_requests: str

    # 中间结果
    itinerary_plan: dict
    accommodation_plan: dict
    transportation_plan: dict
    food_plan: dict
    budget_analysis: dict

    # 控制流
    current_phase: str
    revision_count: int
    max_revisions: int
    is_within_budget: bool
    errors: list[str]

    # 最终输出
    total_cost: float
    final_result: dict


class AgentOrchestrator:
    """基于 LangGraph 的多智能体编排器。

    将硬编码的顺序管道替换为声明式工作流图：
    - 节点 = 智能体执行步骤
    - 边 = 执行顺序 + 条件分支
    - 支持并行节点（住宿/交通/餐饮可并发）

    工作流拓扑：
    ```
    [INIT] → [ITINERARY] → [ACCOMMODATION] ─┬─→ [BUDGET_AUDIT] → [EVALUATION]
                            [TRANSPORTATION] ─┤                        │
                            [FOOD] ───────────┘              ┌─ OK? ──┘
                                                              │ NO
                                                              └→ [REVISION] → [BUDGET_AUDIT]
                                                                 (max 3 iterations)
    ```
    """

    def __init__(self) -> None:
        self.nodes: dict[str, WorkflowNode] = {}
        self.state: ExecutionState = ExecutionState()
        self._handlers: dict[str, Callable] = {}
        self._build_workflow()

    def _build_workflow(self) -> None:
        """构建工作流节点图。"""
        self.nodes = {
            "init": WorkflowNode(
                node_id="init",
                name="初始化",
                phase=ExecutionPhase.INIT,
                agent="orchestrator",
                depends_on=[],
            ),
            "itinerary": WorkflowNode(
                node_id="itinerary",
                name="行程规划",
                phase=ExecutionPhase.ITINERARY,
                agent="itinerary",
                depends_on=["init"],
            ),
            "accommodation": WorkflowNode(
                node_id="accommodation",
                name="住宿安排",
                phase=ExecutionPhase.ACCOMMODATION,
                agent="accommodation",
                depends_on=["itinerary"],
                can_parallel=True,
            ),
            "transportation": WorkflowNode(
                node_id="transportation",
                name="交通规划",
                phase=ExecutionPhase.TRANSPORTATION,
                agent="transportation",
                depends_on=["itinerary"],
                can_parallel=True,
            ),
            "food": WorkflowNode(
                node_id="food",
                name="餐饮推荐",
                phase=ExecutionPhase.FOOD,
                agent="budget",
                depends_on=["itinerary"],
                can_parallel=True,
            ),
            "budget_audit": WorkflowNode(
                node_id="budget_audit",
                name="预算审计",
                phase=ExecutionPhase.BUDGET_AUDIT,
                agent="budget",
                depends_on=["accommodation", "transportation", "food"],
            ),
            "evaluation": WorkflowNode(
                node_id="evaluation",
                name="结果评估",
                phase=ExecutionPhase.EVALUATION,
                agent="evaluator",
                depends_on=["budget_audit"],
            ),
            "revision": WorkflowNode(
                node_id="revision",
                name="方案修订",
                phase=ExecutionPhase.REVISION,
                agent="orchestrator",
                depends_on=["evaluation"],
                retry_on_fail=False,
            ),
        }

    def register_handler(self, node_id: str, handler: Callable) -> None:
        """注册节点的执行处理器。"""
        self._handlers[node_id] = handler

    def get_execution_order(self) -> list[list[str]]:
        """获取拓扑排序后的执行顺序（支持并行层级）。

        Returns:
            嵌套列表，外层为执行层级，内层为可并行的节点ID。
        """
        # 计算每个节点的层级深度
        def get_depth(node_id: str, visited: set | None = None) -> int:
            if visited is None:
                visited = set()
            if node_id in visited:
                return 0
            visited.add(node_id)
            node = self.nodes.get(node_id)
            if not node or not node.depends_on:
                return 1
            return 1 + max(get_depth(dep, visited) for dep in node.depends_on)

        # 按层级分组
        levels: dict[int, list[str]] = {}
        for nid in self.nodes:
            depth = get_depth(nid, set())
            levels.setdefault(depth, []).append(nid)

        return [levels[k] for k in sorted(levels.keys())]

    def should_continue(self, state: ExecutionState) -> str:
        """条件边：评估后决定继续还是修订。"""
        if state.get("is_within_budget", True):
            return "complete"

        revision_count = state.get("revision_count", 0)
        max_revisions = state.get("max_revisions", 3)

        if revision_count < max_revisions:
            logger.info(f"预算不足，进入修订循环 ({revision_count + 1}/{max_revisions})")
            return "revision"
        else:
            logger.info(f"已达到最大修订次数 ({max_revisions})，终止修订")
            return "complete"

    def get_parallel_groups(self) -> list[list[str]]:
        """获取可并行执行的节点组。"""
        groups: list[list[str]] = []
        execution_order = self.get_execution_order()

        for level in execution_order:
            parallel_group = []
            for nid in level:
                node = self.nodes.get(nid)
                if node and node.can_parallel:
                    parallel_group.append(nid)
            if parallel_group:
                groups.append(parallel_group)

        return groups

    def execute_phase(
        self,
        phase: ExecutionPhase,
        state: ExecutionState,
        agent_handlers: dict[str, Callable],
    ) -> ExecutionState:
        """执行单个阶段，委托给对应的智能体处理器。

        Args:
            phase: 当前执行阶段
            state: 当前执行状态
            agent_handlers: agent_name → handler 函数映射

        Returns:
            更新后的执行状态
        """
        # 找到属于此阶段的所有节点
        phase_nodes = [
            n for n in self.nodes.values()
            if n.phase == phase
        ]

        for node in phase_nodes:
            if node.agent not in agent_handlers:
                logger.warning(f"阶段 {phase.value} 没有注册处理器 (agent={node.agent})")
                continue

            try:
                handler = agent_handlers[node.agent]
                result = handler(state)
                self._merge_result(state, node.node_id, result)
                logger.info(f"阶段完成: {node.name}")

            except Exception as e:
                logger.error(f"阶段执行失败 [{node.name}]: {e}")
                if node.retry_on_fail:
                    state.setdefault("errors", []).append(f"{node.name}: {str(e)}")
                else:
                    raise

        return state

    def _merge_result(self, state: ExecutionState, node_id: str, result: dict) -> None:
        """将节点执行结果合并到状态中。"""
        key_mapping = {
            "itinerary": "itinerary_plan",
            "accommodation": "accommodation_plan",
            "transportation": "transportation_plan",
            "food": "food_plan",
            "budget_audit": "budget_analysis",
            "evaluation": "evaluation_result",
        }

        state_key = key_mapping.get(node_id, node_id)
        if isinstance(result, dict):
            state[state_key] = result  # type: ignore[literal-required]


def build_execution_state(
    destination: str,
    origin: str,
    days: int,
    traveler_count: int,
    budget: float,
    preference_level: str = "舒适型",
    spend_all_budget: bool = False,
    special_requests: str = "",
) -> ExecutionState:
    """构建初始执行状态。"""
    return ExecutionState(
        destination=destination,
        origin=origin,
        days=days,
        traveler_count=traveler_count,
        budget=budget,
        preference_level=preference_level,
        spend_all_budget=spend_all_budget,
        special_requests=special_requests,
        # 中间结果（空）
        itinerary_plan={},
        accommodation_plan={},
        transportation_plan={},
        food_plan={},
        budget_analysis={},
        # 控制流
        current_phase=ExecutionPhase.INIT.value,
        revision_count=0,
        max_revisions=3,
        is_within_budget=True,
        errors=[],
        # 最终输出
        total_cost=0.0,
        final_result={},
    )
