"""基于LLM的智能意图解析器 - 支持对话上下文记忆"""

import json
from datetime import date, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from utils.llm import qwen_brain


@dataclass
class ParsedIntent:
    """解析后的用户意图"""
    destination: str = "北京"
    origin: str = "北京"
    days: int = 3
    traveler_count: int = 1
    budget: float = 5000.0
    spend_all_budget: bool = False  # 是否要花光预算
    preference_level: str = "舒适型"  # 经济型/舒适型/高档型/豪华型
    special_requests: str = ""  # 特殊要求
    target_remaining: float = 0.0  # 用户希望剩余多少元（0表示不限制）
    confidence: float = 0.0  # 解析置信度


@dataclass
class ConversationContext:
    """对话上下文"""
    last_intent: Optional[ParsedIntent] = None
    last_result: Optional[Dict[str, Any]] = None
    history: List[str] = field(default_factory=list)


class IntentParser:
    """使用LLM智能解析用户意图 - 支持上下文记忆"""

    SYSTEM_PROMPT = """你是一个旅行规划助手，负责解析用户的旅行需求。

你会收到用户的输入和对话历史。请根据上下文理解用户的意图。

如果用户的新输入是对之前请求的修改或补充（如"花掉全部预算"、"升级酒店档次"、"剩余1000元"），请保留之前的信息并更新相关字段。

如果用户提出全新的请求，则解析新的完整信息。

请从用户输入中提取以下信息，以JSON格式返回：

1. destination: 目的地城市
2. origin: 出发城市（如果用户未说明，默认与目的地相同）
3. days: 旅行天数
4. traveler_count: 旅行人数
5. budget: 预算金额（元）
6. spend_all_budget: 用户是否希望花光全部预算（布尔值）
7. preference_level: 消费档次偏好（经济型/舒适型/高档型/豪华型）
8. special_requests: 用户的其他特殊要求
9. target_remaining: 用户希望剩余多少钱（数字，如"剩余1000元"则填1000；没有提到则不填）

注意：
- 仔细理解用户意图，如"把预算花完"、"全花掉"、"不差钱"、"花光预算"等表达都表示spend_all_budget为true
- 如果用户说"剩余1000元"、"留1000块"等，表示希望最终剩余约该金额，budget应保持原值，target_remaining设为对应数字
- 如果用户只是说"花掉全部预算"而没有其他信息，应该保留对话历史中的目的地、天数、人数、预算等信息
- 如果用户提到"穷游"、"省钱"等，preference_level应为"经济型"
- 如果用户提到"豪华"、"高端"、"享受"等，preference_level应为"高档型"或"豪华型"
- 默认为"舒适型"

返回格式示例：
```json
{
    "destination": "北京",
    "origin": "上海",
    "days": 4,
    "traveler_count": 2,
    "budget": 8000,
    "spend_all_budget": true,
    "preference_level": "舒适型",
    "special_requests": "想体验当地特色美食",
    "target_remaining": 0
}
```"""

    FALLBACK_CITIES = ["北京", "上海", "杭州", "成都", "西安", "南京", "苏州", "重庆", "广州", "深圳"]

    def __init__(self):
        self.context = ConversationContext()

    def parse(self, user_input: str) -> ParsedIntent:
        """解析用户输入，支持上下文"""
        print(f"\n[意图解析] 用户输入: {user_input}")

        # 添加到历史
        self.context.history.append(user_input)

        # 首先尝试LLM解析（带上下文）
        if qwen_brain.is_available():
            result = self._parse_with_llm_and_context(user_input)
            if result and result.confidence > 0.5:
                # 更新上下文
                self.context.last_intent = result
                print(f"[LLM解析成功] {result}")
                return result

        # 降级到规则解析
        print("[意图解析] 使用规则解析（LLM不可用或置信度过低）")
        result = self._parse_with_rules(user_input)
        self.context.last_intent = result
        return result

    def _parse_with_llm_and_context(self, user_input: str) -> Optional[ParsedIntent]:
        """使用LLM和上下文解析意图"""
        # 构建包含上下文的提示
        context_info = ""
        if self.context.last_intent:
            last = self.context.last_intent
            context_info = f"""
[之前的对话信息]
- 目的地: {last.destination}
- 天数: {last.days}天
- 人数: {last.traveler_count}人
- 预算: {last.budget}元
- 是否花光预算: {last.spend_all_budget}
- 消费档次: {last.preference_level}
"""

        prompt = f"""{context_info}
[当前用户输入]
{user_input}

请根据上下文解析用户当前的意图。如果用户只是说"花掉全部预算"等补充说明，请保留之前的信息并更新相关字段。"""

        response_json = qwen_brain.parse_json_response(prompt, self.SYSTEM_PROMPT)
        if not response_json:
            # 如果LLM解析失败，尝试结合上下文的默认值
            if self.context.last_intent:
                # 检查是否是修改请求
                if self._is_modification_request(user_input):
                    return self._apply_modification(self.context.last_intent, user_input)
            return None

        try:
            # 如果新解析结果缺少关键信息，从上下文补充
            last = self.context.last_intent

            destination = response_json.get("destination")
            if not destination or destination == "北京":
                # 检查用户输入是否只包含修改意图
                if last and self._is_modification_request(user_input):
                    destination = last.destination

            target_remaining = float(response_json.get("target_remaining", 0) or 0)
            # 如果LLM返回了target_remaining，调整budget为目标花费
            adjusted_budget = float(response_json.get("budget", last.budget if last else 5000))
            spend_all = bool(response_json.get("spend_all_budget", False))
            if target_remaining > 0:
                adjusted_budget = max(0, adjusted_budget - target_remaining)
                spend_all = True
                print(f"[LLM] 检测到剩余{target_remaining}元 -> 目标花费{adjusted_budget}元")

            return ParsedIntent(
                destination=destination or (last.destination if last else "北京"),
                origin=response_json.get("origin", destination or (last.origin if last else "北京")),
                days=int(response_json.get("days", last.days if last else 3)),
                traveler_count=int(response_json.get("traveler_count", last.traveler_count if last else 1)),
                budget=adjusted_budget,
                spend_all_budget=spend_all,
                preference_level=response_json.get("preference_level", last.preference_level if last else "舒适型"),
                special_requests=response_json.get("special_requests", ""),
                target_remaining=target_remaining,
                confidence=0.9,
            )
        except Exception as e:
            print(f"[错误] LLM解析结果格式错误: {e}")
            return None

    def _is_modification_request(self, user_input: str) -> bool:
        """检测是否是修改请求（而非全新请求）"""
        modification_keywords = [
            "花掉", "花光", "全部花完", "预算花完", "把预算",
            "升级", "降级", "换", "改",
            "不够", "太多", "加", "减",
            "剩余", "留", "省", "只用",
        ]
        return any(kw in user_input for kw in modification_keywords)

    def _apply_modification(self, last_intent: ParsedIntent, user_input: str) -> ParsedIntent:
        """应用修改到上一个意图"""
        import re

        result = ParsedIntent(
            destination=last_intent.destination,
            origin=last_intent.origin,
            days=last_intent.days,
            traveler_count=last_intent.traveler_count,
            budget=last_intent.budget,
            spend_all_budget=last_intent.spend_all_budget,
            preference_level=last_intent.preference_level,
            special_requests=last_intent.special_requests,
            confidence=0.8,
        )

        # 检测"剩余XXX元"模式：用户希望保留指定金额，其余花掉
        remain_match = re.search(r'剩余\s*(\d+)\s*[元块]?', user_input)
        if remain_match:
            remain_amount = float(remain_match.group(1))
            result.target_remaining = remain_amount
            # 将预算调整为 原预算 - 希望剩余 = 目标花费
            result.budget = max(0, last_intent.budget - remain_amount)
            result.spend_all_budget = True
            print(f"[修改] 剩余{remain_amount}元 -> 目标花费{result.budget}元，花光模式开启")

        # 检测花光预算意图
        spend_keywords = ["花掉", "花光", "全部花完", "预算花完", "把预算花完"]
        if any(kw in user_input for kw in spend_keywords):
            result.spend_all_budget = True

        # 检测升级/降级
        if any(k in user_input for k in ["升级", "高档", "豪华"]):
            result.preference_level = "豪华型"
        elif any(k in user_input for k in ["降级", "经济", "省钱", "便宜"]):
            result.preference_level = "经济型"

        return result

    def update_result(self, result: Dict[str, Any]):
        """更新对话结果"""
        self.context.last_result = result

    def reset(self):
        """重置对话上下文"""
        self.context = ConversationContext()

    def _parse_with_rules(self, user_input: str) -> ParsedIntent:
        """规则解析（降级方案）"""
        import re

        destination = "北京"
        traveler_count = 1
        budget = 5000.0
        days = 3
        spend_all = False
        preference_level = "舒适型"
        target_remaining = 0.0

        # 提取城市
        for city in self.FALLBACK_CITIES:
            if city in user_input:
                destination = city
                break

        # 提取人数
        num_match = re.search(r'(\d+)\s*[个]?[人位]', user_input)
        if num_match:
            traveler_count = int(num_match.group(1))

        # 提取预算
        budget_match = re.search(r'预算\s*[为约]?(\d+)', user_input)
        if budget_match:
            budget = float(budget_match.group(1))

        # 提取天数
        days_match = re.search(r'(\d+)\s*[日天]', user_input)
        if days_match:
            days = int(days_match.group(1))

        # 检测"剩余XXX元"模式
        remain_match = re.search(r'剩余\s*(\d+)\s*[元块]?', user_input)
        if remain_match:
            remain_amount = float(remain_match.group(1))
            target_remaining = remain_amount
            if self.context.last_intent:
                budget = max(0, self.context.last_intent.budget - remain_amount)
            spend_all = True

        # 检测花光预算意图
        spend_keywords = [
            "花光", "全部花掉", "清空预算", "花完预算", "全部花完",
            "用完预算", "把预算花完", "把预算全部花掉", "花完", "用光预算",
            "预算全部花完", "预算花完", "尽量多花", "不差钱", "全花掉"
        ]
        for keyword in spend_keywords:
            if keyword in user_input:
                spend_all = True
                break

        # 检测消费档次
        if any(k in user_input for k in ["穷游", "省钱", "经济", "便宜"]):
            preference_level = "经济型"
        elif any(k in user_input for k in ["豪华", "高端", "奢侈", "享受"]):
            preference_level = "豪华型"
        elif any(k in user_input for k in ["高档", "品质"]):
            preference_level = "高档型"

        return ParsedIntent(
            destination=destination,
            origin=destination,
            days=days,
            traveler_count=traveler_count,
            budget=budget,
            spend_all_budget=spend_all,
            preference_level=preference_level,
            special_requests="",
            target_remaining=target_remaining,
            confidence=0.5,  # 规则解析置信度较低
        )


# 全局实例
intent_parser = IntentParser()
