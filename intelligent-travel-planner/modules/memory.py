"""记忆模块 —— 多轮对话记忆与用户画像持久化。

提供三层记忆能力：
1. 短期记忆：当前会话的对话历史（滑动窗口）
2. 长期记忆：用户偏好画像（JSON 文件持久化）
3. 情景记忆：历史旅行方案摘要（支持检索复用）
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.llm import qwen_brain
from utils.logger import get_logger

logger = get_logger(__name__)

# 默认记忆存储路径
DEFAULT_MEMORY_DIR = Path(__file__).parent.parent / "data" / "memory"


@dataclass
class UserProfile:
    """用户偏好画像 —— 跨会话持久化的用户旅行偏好。"""

    user_id: str = "default"
    # 偏好统计
    preferred_destinations: list[str] = field(default_factory=list)  # 偏好的目的地
    interest_categories: list[str] = field(default_factory=list)  # 兴趣类别（历史文化/自然风光/美食购物等）
    budget_preference: str = "舒适型"  # 消费档位偏好
    avg_group_size: float = 1.0  # 平均同行人数
    avg_trip_days: int = 3  # 平均旅行天数
    avg_budget: float = 5000.0  # 平均预算
    # 行为记录
    total_trips_planned: int = 0
    last_destination: str = ""
    last_updated: str = ""
    # 隐式偏好标签
    preferred_tags: list[str] = field(default_factory=list)  # 偏好的景点标签

    def update_from_request(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        preference_level: str,
        interests: Optional[list[str]] = None,
    ) -> None:
        """从新的旅行请求更新用户画像。"""
        self.total_trips_planned += 1

        # 移动平均更新偏好
        if destination not in self.preferred_destinations:
            self.preferred_destinations.append(destination)
        if len(self.preferred_destinations) > 10:
            self.preferred_destinations = self.preferred_destinations[-10:]

        if interests:
            for cat in interests:
                if cat not in self.interest_categories:
                    self.interest_categories.append(cat)

        self.avg_group_size = (self.avg_group_size * (self.total_trips_planned - 1) + traveler_count) / self.total_trips_planned
        self.avg_trip_days = int((self.avg_trip_days * (self.total_trips_planned - 1) + days) / self.total_trips_planned)
        self.avg_budget = (self.avg_budget * (self.total_trips_planned - 1) + budget) / self.total_trips_planned
        self.budget_preference = preference_level
        self.last_destination = destination
        self.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class ConversationTurn:
    """单轮对话记录。"""

    role: str  # "user" 或 "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)


class ConversationMemory:
    """短期对话记忆 —— 带滑动窗口的多轮对话管理。

    特性：
    - 滑动窗口：保留最近 N 轮对话，超出部分自动压缩为摘要
    - 上下文注入：将历史摘要注入后续 LLM 调用
    - 意图追踪：关联用户意图与系统响应
    """

    def __init__(self, max_turns: int = 20, summary_trigger: int = 10) -> None:
        self.turns: list[ConversationTurn] = []
        self.max_turns = max_turns
        self.summary_trigger = summary_trigger
        self._summary: str = ""

    def add_user_message(self, content: str, metadata: Optional[dict] = None) -> None:
        """添加用户消息到记忆。"""
        self.turns.append(ConversationTurn(
            role="user",
            content=content,
            metadata=metadata or {},
        ))
        self._maybe_compress()

    def add_assistant_message(self, content: str, metadata: Optional[dict] = None) -> None:
        """添加助手响应到记忆。"""
        self.turns.append(ConversationTurn(
            role="assistant",
            content=content,
            metadata=metadata or {},
        ))
        self._maybe_compress()

    def get_context(self, last_n: int = 6) -> str:
        """获取当前对话上下文（用于 LLM 注入）。"""
        if not self.turns and not self._summary:
            return ""

        parts: list[str] = []

        # 先添加历史摘要
        if self._summary:
            parts.append(f"[历史对话摘要]\n{self._summary}")

        # 再添加最近 N 轮
        recent = self.turns[-last_n:] if last_n > 0 else self.turns
        if recent:
            parts.append("[最近对话]")
            for turn in recent:
                label = "用户" if turn.role == "user" else "助手"
                parts.append(f"{label}: {turn.content}")

        return "\n\n".join(parts)

    def get_history_messages(self, last_n: int = 6) -> list[dict]:
        """获取最近 N 轮对话（用于 LangChain 消息列表）。"""
        recent = self.turns[-last_n:] if last_n > 0 else self.turns
        return [{"role": t.role, "content": t.content} for t in recent]

    def get_last_user_message(self) -> Optional[str]:
        """获取最近一条用户消息。"""
        for turn in reversed(self.turns):
            if turn.role == "user":
                return turn.content
        return None

    def get_last_assistant_message(self) -> Optional[str]:
        """获取最近一条助手响应。"""
        for turn in reversed(self.turns):
            if turn.role == "assistant":
                return turn.content
        return None

    def clear(self) -> None:
        """清空所有对话记忆。"""
        self.turns.clear()
        self._summary = ""

    def reset_context(self) -> None:
        """重置上下文（保留对话历史但清除摘要）。"""
        self._summary = ""

    def _maybe_compress(self) -> None:
        """当对话轮数超过阈值时，自动压缩早期对话为摘要。"""
        if len(self.turns) <= self.summary_trigger:
            return

        # 取最早的几轮压缩
        old_turns = self.turns[:-self.max_turns] if len(self.turns) > self.max_turns else []
        if len(old_turns) < 2:
            return

        new_summary = self._generate_summary(old_turns)
        if new_summary:
            self._summary = new_summary
            self.turns = self.turns[-self.max_turns:]

    def _generate_summary(self, turns: list[ConversationTurn]) -> str:
        """使用 LLM 生成对话摘要。"""
        if not qwen_brain.is_available():
            # 简单拼接作为降级摘要
            return "；".join([f"{t.role}: {t.content[:100]}" for t in turns[-4:]])

        dialogue = "\n".join([f"{'用户' if t.role == 'user' else '助手'}: {t.content[:200]}" for t in turns])
        prompt = f"请用2-3句话总结以下旅行规划对话的核心内容：\n\n{dialogue}"
        summary = qwen_brain.chat(prompt)
        return summary if summary else ""


class MemoryStore:
    """记忆持久化存储 —— 用户画像与对话历史的文件存储。"""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self.storage_dir = storage_dir or DEFAULT_MEMORY_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    # ========= 用户画像 =========

    def load_profile(self, user_id: str = "default") -> UserProfile:
        """加载用户画像。"""
        filepath = self.storage_dir / f"profile_{user_id}.json"
        if not filepath.exists():
            return UserProfile(user_id=user_id)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return UserProfile(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"用户画像加载失败: {e}，使用默认画像")
            return UserProfile(user_id=user_id)

    def save_profile(self, profile: UserProfile) -> None:
        """保存用户画像。"""
        filepath = self.storage_dir / f"profile_{profile.user_id}.json"
        try:
            data = {
                "user_id": profile.user_id,
                "preferred_destinations": profile.preferred_destinations,
                "interest_categories": profile.interest_categories,
                "budget_preference": profile.budget_preference,
                "avg_group_size": profile.avg_group_size,
                "avg_trip_days": profile.avg_trip_days,
                "avg_budget": profile.avg_budget,
                "total_trips_planned": profile.total_trips_planned,
                "last_destination": profile.last_destination,
                "last_updated": profile.last_updated,
                "preferred_tags": profile.preferred_tags,
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"用户画像已保存: {filepath}")
        except OSError as e:
            logger.error(f"用户画像保存失败: {e}")

    # ========= 对话历史 =========

    def save_conversation(
        self,
        memory: ConversationMemory,
        session_id: str = "latest",
    ) -> None:
        """保存对话历史。"""
        filepath = self.storage_dir / f"conversation_{session_id}.json"
        try:
            data = {
                "session_id": session_id,
                "summary": memory._summary,
                "turns": [
                    {
                        "role": t.role,
                        "content": t.content,
                        "timestamp": t.timestamp,
                        "metadata": t.metadata,
                    }
                    for t in memory.turns
                ],
                "saved_at": datetime.now().isoformat(),
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error(f"对话历史保存失败: {e}")

    def load_conversation(self, session_id: str = "latest") -> Optional[ConversationMemory]:
        """加载对话历史。"""
        filepath = self.storage_dir / f"conversation_{session_id}.json"
        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            memory = ConversationMemory()
            memory._summary = data.get("summary", "")
            for t in data.get("turns", []):
                memory.turns.append(ConversationTurn(
                    role=t["role"],
                    content=t["content"],
                    timestamp=t.get("timestamp", ""),
                    metadata=t.get("metadata", {}),
                ))
            return memory
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"对话历史加载失败: {e}")
            return None

    # ========= 旅行方案记录 =========

    def save_trip_record(self, trip_data: dict, trip_id: Optional[str] = None) -> str:
        """保存旅行方案记录（情景记忆）。"""
        trip_id = trip_id or f"trip_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        filepath = self.storage_dir / f"trips/{trip_id}.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        trip_data["trip_id"] = trip_id
        trip_data["created_at"] = datetime.now().isoformat()
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(trip_data, f, ensure_ascii=False, indent=2)
            logger.info(f"旅行方案已保存: {trip_id}")
        except OSError as e:
            logger.error(f"旅行方案保存失败: {e}")
        return trip_id

    def list_trip_records(self, limit: int = 10) -> list[dict]:
        """列出最近的旅行方案记录。"""
        trips_dir = self.storage_dir / "trips"
        if not trips_dir.exists():
            return []

        records = []
        for f in sorted(trips_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:limit]:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    records.append(json.load(fp))
            except (json.JSONDecodeError, OSError):
                continue
        return records
