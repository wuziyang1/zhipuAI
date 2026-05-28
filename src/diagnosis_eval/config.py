"""
诊断能力评测配置
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ==================== 数据配置 ====================
# 测试集 raw_data.json 路径（相对于项目根目录）
INPUT_RAW_DATA = 'src/multi_agent_pipeline/output/2026-05-25_21-27-11/raw_data.json'

# 只评测通过质量审核的案例（gold 标签更可靠）
USE_PASSED_CASES_ONLY = True

# 限制评测样本数（None = 全部）
MAX_SAMPLES = None

# ==================== 模型配置 ====================
API_KEY = os.getenv('EVAL_API_KEY') or os.getenv('Gemini_API_KEY')
BASE_URL = os.getenv('EVAL_BASE_URL') or os.getenv('Gemini_BASE_URL')
MODEL_NAME = os.getenv('EVAL_MODEL_NAME', 'openrouter:glm-5.1')

# glm.ai 网关 OpenRouter 模型请用 openrouter:glm-5.1（走 /v1/chat/completions）
# 不要用 openrouter:z-ai/glm-5.1，斜杠会导致 Gemini 路径 404

TEMPERATURE = 0.3
MAX_OUTPUT_TOKENS = 8192
API_MAX_RETRIES = 3
API_RETRY_DELAY = 2

# ==================== 输出配置 ====================
OUTPUT_DIR = 'src/diagnosis_eval/output'

# 是否缓存模型预测（避免重复调用 API）
ENABLE_CACHE = True
CACHE_DIR = 'src/diagnosis_eval/output/.cache'

# 请求间隔（秒），避免触发限流
REQUEST_INTERVAL = 1.0
