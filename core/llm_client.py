"""
LLM 客户端 — OpenAI 兼容 SDK 轻量封装

支持 function-calling 和结构化 JSON 输出，用于多智能体分析流水线。
"""

import json
import os
from typing import Any, Optional

from openai import OpenAI
from pydantic import BaseModel

# 从 .env 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass


class LLMClient:
    """OpenAI 兼容的 LLM 客户端封装"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("AI_ANALYST_MODEL", "deepseek-v4-pro")
        self.temperature = temperature
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=120.0,  # 120s 超时，防止无限等待
        )

    def chat(
        self,
        messages: list[dict],
        stream: bool = False,
        max_retries: int = 2,
        **kwargs,
    ):
        """发送对话，返回 (content, usage)。自动重试 transient errors。"""
        params = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            **kwargs,
        }
        if self.temperature is not None:
            params["temperature"] = self.temperature

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                if stream:
                    return self._client.chat.completions.create(**params)

                response = self._client.chat.completions.create(**params)
                choice = response.choices[0]
                content = choice.message.content or ""
                usage = response.usage
                return content, usage
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    import time
                    time.sleep(2 ** attempt)  # 1s, 2s backoff
                    continue
        raise last_error

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        stream: bool = False,
        **kwargs,
    ):
        """带 function-calling 的对话，返回 (content, tool_calls, usage) 或 generator"""
        params = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "stream": stream,
            **kwargs,
        }
        if self.temperature is not None:
            params["temperature"] = self.temperature

        if stream:
            return self._client.chat.completions.create(**params)

        response = self._client.chat.completions.create(**params)
        choice = response.choices[0]
        msg = choice.message
        content = msg.content or ""
        tool_calls = []

        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })

        return content, tool_calls, response.usage

    def structured_output(
        self,
        messages: list[dict],
        schema: type[BaseModel],
        **kwargs,
    ) -> tuple[Any, Any]:
        """要求 LLM 输出结构化 JSON，解析为 Pydantic model"""
        schema_json = schema.model_json_schema()
        schema_name = schema.__name__

        # 将 schema 注入 prompt
        system_prompt = (
            f"你必须严格按照以下 JSON Schema 输出结果，不要输出任何其他内容。\n\n"
            f"```json\n{json.dumps(schema_json, ensure_ascii=False, indent=2)}\n```\n\n"
            f"只输出 JSON，不要包含 markdown 代码块标记。"
        )

        # 在 messages 中注入 schema 要求
        modified = list(messages)
        if modified and modified[0].get("role") == "system":
            modified[0]["content"] += "\n\n" + system_prompt
        else:
            modified.insert(0, {"role": "system", "content": system_prompt})

        content, usage = self.chat(modified, **kwargs)

        # 尝试多种方式提取 JSON
        # 1. 直接解析
        try:
            data = json.loads(content)
            return schema.model_validate(data), usage
        except (json.JSONDecodeError, Exception):
            pass

        # 2. 提取 ```json ... ``` 块
        import re
        m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                return schema.model_validate(data), usage
            except Exception:
                pass

        # 3. 提取首个 JSON 对象
        m2 = re.search(r'\{.*\}', content, re.DOTALL)
        if m2:
            try:
                data = json.loads(m2.group(0))
                return schema.model_validate(data), usage
            except Exception:
                pass

        # 解析失败，作为纯文本返回
        return content, usage


# --- 全局客户端实例 ---
_llm: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
