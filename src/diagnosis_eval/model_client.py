"""
模型调用客户端（自动选择 Gemini / OpenAI 协议）
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from model_utils import (
    channel_error_hint,
    detect_api_backend,
    format_gemini_model_name,
    normalize_model_name,
)


class ModelClient:
    """被测模型 API 客户端"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        raw_name = config['MODEL_NAME']
        self.resolved_model_name = normalize_model_name(raw_name)
        self.backend = detect_api_backend(self.resolved_model_name)
        self.base_url = config['BASE_URL'].rstrip('/')
        self.api_key = config['API_KEY']
        self._genai = None
        self._gemini_client = None

        if self.backend == 'gemini':
            from google import genai
            self._genai = genai
            self._gemini_client = genai.Client(
                api_key=self.api_key,
                http_options=genai.types.HttpOptions(base_url=self.base_url)
            )

        self.enable_cache = config.get('ENABLE_CACHE', True)
        self.cache_dir = config.get('CACHE_DIR', '.cache')
        if self.enable_cache:
            os.makedirs(self._resolve_path(self.cache_dir), exist_ok=True)

        if raw_name != self.resolved_model_name:
            print(f"[ModelClient] 模型名已规范化: {raw_name} -> {self.resolved_model_name}")
        print(f"[ModelClient] API 协议: {self.backend} | 模型: {self.resolved_model_name}")

    @staticmethod
    def _resolve_path(relative_path: str) -> str:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(root, relative_path)

    def _cache_key(self, prompt: str) -> str:
        content = f"{self.backend}:{self.resolved_model_name}:{prompt}"
        return hashlib.md5(content.encode()).hexdigest()

    def _read_cache(self, key: str) -> Optional[str]:
        if not self.enable_cache:
            return None
        path = os.path.join(self._resolve_path(self.cache_dir), f"{key}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f).get('response')
        return None

    def _write_cache(self, key: str, response: str):
        if not self.enable_cache:
            return
        path = os.path.join(self._resolve_path(self.cache_dir), f"{key}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'response': response}, f, ensure_ascii=False)

    def _generate_openai(self, prompt: str) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            'model': self.resolved_model_name,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': self.config.get('TEMPERATURE', 0.3),
            'max_tokens': self.config.get('MAX_OUTPUT_TOKENS', 8192),
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            method='POST',
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            },
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode('utf-8'))

        message = body['choices'][0]['message']
        content = message.get('content')
        if content:
            return content

        # GLM 5.1 等推理模型可能把内容放在 reasoning 字段
        reasoning = message.get('reasoning')
        if reasoning:
            return reasoning

        raise ValueError(f'响应无 content/reasoning 字段: {json.dumps(message, ensure_ascii=False)[:200]}')

    def _generate_gemini(self, prompt: str) -> str:
        model_name = format_gemini_model_name(self.resolved_model_name)
        response = self._gemini_client.models.generate_content(
            model=model_name,
            contents=self._genai.types.Content(
                parts=[self._genai.types.Part(text=prompt)]
            ),
            config=self._genai.types.GenerateContentConfig(
                temperature=self.config.get('TEMPERATURE', 0.3),
                max_output_tokens=self.config.get('MAX_OUTPUT_TOKENS', 8192),
            )
        )
        return response.text

    def generate(self, prompt: str) -> Optional[str]:
        cache_key = self._cache_key(prompt)
        cached = self._read_cache(cache_key)
        if cached:
            print("  [ModelClient] 使用缓存")
            return cached

        max_retries = self.config.get('API_MAX_RETRIES', 3)
        retry_delay = self.config.get('API_RETRY_DELAY', 2)

        for attempt in range(max_retries):
            try:
                if self.backend == 'openai':
                    result = self._generate_openai(prompt)
                else:
                    result = self._generate_gemini(prompt)

                self._write_cache(cache_key, result)
                return result

            except Exception as e:
                err = str(e)
                retryable = any(x in err for x in ('503', '502', '429', '500', 'No available channel'))

                if attempt < max_retries - 1 and retryable:
                    wait = retry_delay ** attempt
                    print(f"  [ModelClient] API 失败 ({attempt + 1}/{max_retries}): {err[:120]}")
                    print(f"  [ModelClient] 等待 {wait}s 后重试...")
                    time.sleep(wait)
                else:
                    print(f"  [ModelClient] API 最终失败: {err[:200]}")
                    print(channel_error_hint(self.resolved_model_name, self.backend))
                    return None

        return None
