"""
module3 配置：读取 .env 并构建 Agent 所需的 config dict
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

# zhipuAIWeb 子项目根目录（server/module3 -> server -> zhipuAIWeb）
ZHIPUAI_WEB_ROOT = Path(__file__).resolve().parents[2]
# zhipuAI  monorepo 根目录
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODULE3_DIR = Path(__file__).resolve().parent

# 先加载仓库根 .env，再用 zhipuAIWeb/.env 覆盖（子项目优先）
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(ZHIPUAI_WEB_ROOT / ".env", override=True)

API_KEY = os.getenv("Gemini_API_KEY")
BASE_URL = os.getenv("Gemini_BASE_URL")
MODEL_NAME = os.getenv("Gemini_MODEL_NAME")

PIPELINE_DIR = PROJECT_ROOT / "src" / "multi_agent_pipeline"
SRC_DIR = PROJECT_ROOT / "src"


def ensure_pipeline_imports() -> None:
    pipeline_path = str(PIPELINE_DIR)
    src_path = str(SRC_DIR)
    if pipeline_path not in sys.path:
        sys.path.insert(0, pipeline_path)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def is_model_configured() -> bool:
    return bool(API_KEY and BASE_URL and MODEL_NAME)


def build_agent_config() -> Dict[str, Any]:
    """构建与 multi_agent_pipeline 兼容的 Agent 配置字典"""
    ensure_pipeline_imports()
    import config as pipeline_config  # noqa: pipeline config module

    config_dict = {
        key: getattr(pipeline_config, key)
        for key in dir(pipeline_config)
        if not key.startswith("_") and key.isupper()
    }

    # Web 服务层覆盖
    config_dict.update({
        "API_KEY": API_KEY,
        "BASE_URL": BASE_URL,
        "MODEL_NAME": MODEL_NAME,
        "ENABLE_CACHE": False,
        "VERBOSE": False,
        "LOG_LEVEL": "WARNING",
        "CACHE_DIR": str(MODULE3_DIR / ".cache"),
    })

    return config_dict
