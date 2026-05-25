"""
模型名称规范化与 API 路由
"""

from typing import Dict, Literal, Optional

ApiBackend = Literal['gemini', 'openai']

# glm.ai 网关 OpenRouter 渠道使用短名，不是 OpenRouter 原生 z-ai/glm-5.1
DEFAULT_MODEL_ALIASES: Dict[str, str] = {
    'openrouter:z-ai/glm-5.1': 'openrouter:glm-5.1',
    'z-ai/glm-5.1': 'openrouter:glm-5.1',
    'glm-5.1': 'openrouter:glm-5.1',
}


def normalize_model_name(
    model_name: str,
    aliases: Optional[Dict[str, str]] = None,
) -> str:
    """将常见写法统一为网关可识别的模型名"""
    aliases = aliases or DEFAULT_MODEL_ALIASES
    name = model_name.strip()
    return aliases.get(name, name)


def detect_api_backend(model_name: str) -> ApiBackend:
    """
    选择 API 协议：
    - openrouter:* 走 OpenAI Chat Completions（glm.ai 网关 /v1/chat/completions）
    - 其余走 Gemini generateContent
    """
    if model_name.startswith('openrouter:'):
        return 'openai'
    return 'gemini'


def format_gemini_model_name(model_name: str) -> str:
    if model_name.startswith('models/'):
        return model_name
    return f'models/{model_name}'


def channel_error_hint(model_name: str, backend: ApiBackend) -> str:
    if backend == 'openai':
        return (
            f'OpenRouter 模型请求失败 (model={model_name})\n'
            '  - 确认 .env 中 EVAL_MODEL_NAME=openrouter:glm-5.1\n'
            '  - 确认 glm.ai 账户已开通 OpenRouter 渠道且有余额\n'
            '  - 网关地址应为 https://api-gateway.glm.ai'
        )
    return (
        f'Gemini 模型请求失败 (model={model_name})\n'
        '  - 确认模型名正确，如 gemini-3-pro-preview\n'
        '  - OpenRouter 模型请使用 openrouter:glm-5.1，不要用 Gemini SDK 路径'
    )
