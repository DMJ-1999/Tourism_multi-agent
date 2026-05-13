"""结果评估模块 —— 多因子质量评分与约束校验。

对旅行规划方案进行多维度评估：
1. 预算效率：费用是否在预算范围内，利用率如何
2. 行程可行性：每日活动量是否合理，时间是否冲突
3. 兴趣覆盖：用户兴趣偏好是否被充分覆盖
4. 地理连贯性：景点间距离是否合理，路线是否顺畅
5. 约束满足：各类硬性约束是否全部通过
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from utils.llm import qwen_brain
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EvaluationReport:
    """评估报告 —— 多维度质量评分的结构化输出。"""

    # 综合评分
    overall_score: float = 0.0  # 0-100
    grade: str = "C"  # A/B/C/D/F

    # 各维度评分（0-100）
    budget_efficiency: float = 0.0
    schedule_feasibility: float = 0.0
    interest_coverage: float = 0.0
    geographic_coherence: float = 0.0
    constraint_satisfaction: float = 0.0

    # 详情
    issues: list[str] = field(default_factory=list)  # 发现的问题
    suggestions: list[str] = field(default_factory=list)  # 改进建议
    passed_constraints: list[str] = field(default_factory=list)  # 通过的约束
    failed_constraints: list[str] = field(default_factory=list)  # 未通过的约束

    # 元数据
    evaluator_version: str = "1.0"
    evaluation_timestamp: str = ""


class ConstraintValidator:
    """约束校验器 —— 验证旅行方案是否满足各类硬性约束。"""

    def validate(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        total_cost: float,
        itinerary: dict,
        accommodation: dict,
    ) -> tuple[list[str], list[str]]:
        """执行全量约束校验。

        Returns:
            (passed_constraints, failed_constraints) 元组
        """
        passed: list[str] = []
        failed: list[str] = []

        # 约束1: 预算边界
        if total_cost <= budget:
            passed.append(f"预算约束: 总费用 ¥{total_cost:.0f} ≤ 预算 ¥{budget:.0f}")
        else:
            failed.append(f"预算约束: 超支 ¥{total_cost - budget:.0f}")

        # 约束2: 住宿晚数合理性
        nights = max(1, days - 1)
        accommodation_cost = accommodation.get("estimated_cost", 0)
        if accommodation_cost > 0:
            passed.append(f"住宿约束: {nights}晚住宿已安排")
        else:
            failed.append("住宿约束: 未安排住宿")

        # 约束3: 每日行程非空
        itinerary_text = itinerary.get("plan", "")
        if itinerary_text and len(itinerary_text) > 50:
            passed.append("行程约束: 包含每日行程安排")
        else:
            failed.append("行程约束: 行程内容不足")

        # 约束4: 天数合理性
        if 1 <= days <= 30:
            passed.append(f"天数约束: {days}天在合理范围")
        else:
            failed.append(f"天数约束: {days}天超出合理范围")

        # 约束5: 人数合理性
        if traveler_count >= 1:
            passed.append(f"人数约束: {traveler_count}人")
        else:
            failed.append("人数约束: 人数无效")

        # 约束6: 目的地有效性
        valid_cities = [
            "北京", "上海", "杭州", "成都", "西安",
            "南京", "苏州", "重庆", "广州", "深圳",
        ]
        if destination in valid_cities:
            passed.append(f"目的地约束: {destination}受支持")
        else:
            # 不是硬错误，但标记
            passed.append(f"目的地约束: {destination}（不在预定义城市列表中，但仍继续）")

        logger.info(f"约束校验: {len(passed)} 通过, {len(failed)} 失败")
        return passed, failed


class PlanEvaluator:
    """方案评估器 —— 多因子质量评分。"""

    # 维度权重
    WEIGHTS = {
        "budget_efficiency": 0.30,
        "schedule_feasibility": 0.25,
        "interest_coverage": 0.20,
        "geographic_coherence": 0.10,
        "constraint_satisfaction": 0.15,
    }

    EVALUATION_PROMPT = """你是一位旅行方案质量评估专家。请根据以下维度对旅行方案进行评分（每项0-100分）：

1. 预算效率 (budget_efficiency): 费用是否合理利用了预算？是否在预算范围内？
2. 行程可行性 (schedule_feasibility): 每日活动量是否合理？时间安排是否可行？
3. 兴趣覆盖 (interest_coverage): 景点是否覆盖了用户的兴趣偏好？
4. 地理连贯性 (geographic_coherence): 景点之间的地理位置是否合理？路线是否顺畅？
5. 约束满足 (constraint_satisfaction): 各类硬性约束是否被满足？

请以JSON格式返回：
```json
{
    "budget_efficiency": 85,
    "schedule_feasibility": 80,
    "interest_coverage": 75,
    "geographic_coherence": 70,
    "constraint_satisfaction": 90,
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"]
}
```"""

    def __init__(self, validator: Optional[ConstraintValidator] = None) -> None:
        self.validator = validator or ConstraintValidator()

    def evaluate(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        total_cost: float,
        itinerary: dict,
        accommodation: dict,
        preferences: Optional[dict] = None,
    ) -> EvaluationReport:
        """执行完整的多维度评估。"""
        logger.info(f"开始评估: {destination} {days}天 {traveler_count}人 {budget}元")

        # 1. 约束校验
        passed, failed = self.validator.validate(
            destination=destination,
            days=days,
            traveler_count=traveler_count,
            budget=budget,
            total_cost=total_cost,
            itinerary=itinerary,
            accommodation=accommodation,
        )

        # 2. 规则评分
        scores = self._rule_based_scoring(
            budget=budget,
            total_cost=total_cost,
            days=days,
            failed_count=len(failed),
            itinerary=itinerary,
            preferences=preferences,
        )

        # 3. LLM 增强评估（如果可用）
        if qwen_brain.is_available():
            llm_scores = self._llm_evaluate(
                destination=destination,
                days=days,
                traveler_count=traveler_count,
                budget=budget,
                total_cost=total_cost,
                itinerary=itinerary,
                accommodation=accommodation,
                preferences=preferences,
            )
            # 融合 LLM 评分与规则评分（加权平均）
            if llm_scores:
                for key in scores:
                    if key in llm_scores:
                        scores[key] = scores[key] * 0.3 + llm_scores[key] * 0.7

        # 4. 计算综合评分
        overall = sum(
            scores.get(dim, 0) * weight
            for dim, weight in self.WEIGHTS.items()
        )

        # 5. 评级
        grade = self._score_to_grade(overall)

        issues = []
        suggestions = []

        # 预算问题
        if total_cost > budget:
            issues.append(f"费用超出预算 ¥{total_cost - budget:.0f}")
            suggestions.append("建议调整住宿档次或减少付费景点")
        elif total_cost < budget * 0.6:
            issues.append(f"预算利用率不足 {total_cost / budget * 100:.0f}%")
            suggestions.append("剩余预算可用于升级住宿或增加特色体验")

        # 天数问题
        if days < 2:
            issues.append("旅行天数较少，行程可能过于紧凑")

        # 约束问题
        if failed:
            issues.extend(failed)
            suggestions.append("请检查并修复未通过的约束项")

        from datetime import datetime

        report = EvaluationReport(
            overall_score=round(overall, 1),
            grade=grade,
            budget_efficiency=round(scores.get("budget_efficiency", 0), 1),
            schedule_feasibility=round(scores.get("schedule_feasibility", 0), 1),
            interest_coverage=round(scores.get("interest_coverage", 0), 1),
            geographic_coherence=round(scores.get("geographic_coherence", 0), 1),
            constraint_satisfaction=round(scores.get("constraint_satisfaction", 0), 1),
            issues=issues,
            suggestions=suggestions,
            passed_constraints=passed,
            failed_constraints=failed,
            evaluation_timestamp=datetime.now().isoformat(),
        )

        logger.info(f"评估完成: 综合 {report.overall_score}/100 ({report.grade})")
        return report

    def _rule_based_scoring(
        self,
        budget: float,
        total_cost: float,
        days: int,
        failed_count: int,
        itinerary: dict,
        preferences: Optional[dict] = None,
    ) -> dict[str, float]:
        """规则驱动的评分（LLM 不可用时的兜底方案）。"""
        # 预算效率：越接近预算越好（不超支的前提下）
        if total_cost <= 0:
            budget_score = 50.0
        elif total_cost <= budget:
            ratio = total_cost / budget
            if 0.80 <= ratio <= 0.95:
                budget_score = 90.0
            elif 0.60 <= ratio < 0.80:
                budget_score = 75.0
            elif ratio < 0.60:
                budget_score = 60.0
            else:
                budget_score = 85.0
        else:
            overspend_ratio = (total_cost - budget) / budget
            budget_score = max(0, 80.0 - overspend_ratio * 100)

        # 行程可行性：按天数和内容量评估
        itinerary_text = itinerary.get("plan", "")
        if len(itinerary_text) > 200:
            schedule_score = 80.0
        elif len(itinerary_text) > 50:
            schedule_score = 60.0
        else:
            schedule_score = 30.0

        # 约束满足
        constraint_score = max(0, 100.0 - failed_count * 20.0)

        # 兴趣覆盖（基于偏好）
        if preferences and preferences.get("interests"):
            interest_score = 70.0  # 有偏好但无法精确计算覆盖度
        else:
            interest_score = 60.0  # 无偏好则为中性

        # 地理连贯性（无法精确计算，给基准分）
        geo_score = 65.0

        return {
            "budget_efficiency": budget_score,
            "schedule_feasibility": schedule_score,
            "interest_coverage": interest_score,
            "geographic_coherence": geo_score,
            "constraint_satisfaction": constraint_score,
        }

    def _llm_evaluate(
        self,
        destination: str,
        days: int,
        traveler_count: int,
        budget: float,
        total_cost: float,
        itinerary: dict,
        accommodation: dict,
        preferences: Optional[dict] = None,
    ) -> Optional[dict[str, float]]:
        """使用 LLM 进行智能评估。"""
        prompt = f"""请评估以下旅行方案：

目的地: {destination}
天数: {days}天
人数: {traveler_count}人
预算: ¥{budget}
总费用: ¥{total_cost}

行程概要: {itinerary.get('plan', '暂无')[:500]}
住宿概要: {accommodation.get('plan', '暂无')[:200]}
用户偏好: {preferences or '无特别偏好'}"""

        result = qwen_brain.parse_json_response(prompt, self.EVALUATION_PROMPT)
        if not result:
            return None

        try:
            return {
                "budget_efficiency": float(result.get("budget_efficiency", 0)),
                "schedule_feasibility": float(result.get("schedule_feasibility", 0)),
                "interest_coverage": float(result.get("interest_coverage", 0)),
                "geographic_coherence": float(result.get("geographic_coherence", 0)),
                "constraint_satisfaction": float(result.get("constraint_satisfaction", 0)),
            }
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _score_to_grade(score: float) -> str:
        """百分制分数转字母评级。"""
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"


class FeedbackIntegrator:
    """用户反馈集成器 —— 收集用户反馈并用于改进后续方案。"""

    def __init__(self) -> None:
        self.feedback_history: list[dict] = []

    def collect_feedback(
        self,
        plan_id: str,
        rating: float,  # 1-5 星级
        comments: str = "",
        liked_aspects: Optional[list[str]] = None,
        disliked_aspects: Optional[list[str]] = None,
    ) -> dict:
        """收集用户对旅行方案的反馈。"""
        feedback = {
            "plan_id": plan_id,
            "rating": rating,
            "comments": comments,
            "liked_aspects": liked_aspects or [],
            "disliked_aspects": disliked_aspects or [],
        }
        self.feedback_history.append(feedback)
        logger.info(f"用户反馈收集: 评分 {rating}/5, {len(self.feedback_history)} 条历史")

        # 提取可操作的改进点
        improvements = self._extract_improvements(feedback)
        feedback["suggested_improvements"] = improvements

        return feedback

    def _extract_improvements(self, feedback: dict) -> list[str]:
        """从反馈中提取改进建议。"""
        improvements: list[str] = []

        disliked = feedback.get("disliked_aspects", [])
        mapping = {
            "酒店": "下次优先考虑高评分酒店，提前查看真实住客评价",
            "行程": "下次可增加自由活动时间，减少景点密度",
            "餐饮": "下次可提供更多本地特色小吃推荐",
            "交通": "下次可提供更详细的当地交通攻略",
            "预算": "下次可提供多档位预算方案供选择",
        }
        for aspect in disliked:
            for keyword, suggestion in mapping.items():
                if keyword in aspect:
                    improvements.append(suggestion)

        return improvements

    def get_preference_adjustments(self) -> dict[str, Any]:
        """根据历史反馈生成偏好调整建议。"""
        if not self.feedback_history:
            return {}

        avg_rating = sum(f["rating"] for f in self.feedback_history) / len(self.feedback_history)

        adjustments: dict[str, Any] = {
            "average_rating": round(avg_rating, 1),
            "total_feedbacks": len(self.feedback_history),
        }

        if avg_rating < 3.5:
            adjustments["suggestion"] = "整体满意度偏低，建议调整默认偏好为更保守的方案"

        return adjustments
