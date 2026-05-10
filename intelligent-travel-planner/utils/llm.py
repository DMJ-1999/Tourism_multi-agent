"""Qwen LLM封装模块 - 作为智能体的大脑"""

import os
from typing import Optional, Dict, Any
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config.settings import settings


class QwenBrain:
    """Qwen LLM大脑 - 为智能体提供自然语言理解能力"""

    _instance: Optional['QwenBrain'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.api_key = settings.dashscope_api_key or os.getenv("DASHSCOPE_API_KEY")

        if not self.api_key:
            print("[警告] 未配置DASHSCOPE_API_KEY，将使用模拟模式")
            self.model = None
            self._initialized = True
            return

        try:
            self.model = ChatTongyi(
                model=settings.qwen_model,
                dashscope_api_key=self.api_key,
                temperature=settings.qwen_temperature,
                max_tokens=settings.qwen_max_tokens,
            )
            print(f"[Qwen] 初始化成功，使用模型: {settings.qwen_model}")
        except Exception as e:
            print(f"[错误] Qwen初始化失败: {e}")
            self.model = None

        self._initialized = True

    def is_available(self) -> bool:
        """检查LLM是否可用"""
        return self.model is not None

    def chat(self, prompt: str, system_prompt: str = None) -> str:
        """简单对话接口"""
        if not self.is_available():
            return ""

        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            response = self.model.invoke(messages)
            return response.content
        except Exception as e:
            print(f"[错误] LLM调用失败: {e}")
            return ""

    def parse_json_response(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        """解析JSON格式的响应"""
        import json
        import re

        response = self.chat(prompt, system_prompt)
        if not response:
            return {}

        try:
            # 尝试提取JSON块
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            # 移除控制字符
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[错误] JSON解析失败: {e}")
            print(f"[原始响应] {response[:500]}...")
            return {}


# 全局单例
qwen_brain = QwenBrain()
