"""
多智能体Pipeline配置文件
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ==================== API配置 ====================
API_KEY = os.getenv("Gemini_API_KEY")
BASE_URL = os.getenv("Gemini_BASE_URL")
MODEL_NAME = os.getenv("Gemini_MODEL_NAME")

# ==================== 数据处理配置 ====================
# 输入输出路径
INPUT_TRAIN_DATA = 'data/train_sharegpt.json'
OUTPUT_DIR = 'src/multi_agent_pipeline/output'

# 处理数量
NUM_RECORDS = 50  # 处理的题目数量（None表示全部）

# 分层抽样（按 hjy_all.json 的 presetDifficulty 均衡抽题）
STRATIFIED_SAMPLING = True
HJY_METADATA_FILE = 'data/hjy_all.json'
HJY_DIFFICULTY_CACHE = 'data/hjy_difficulty_index.json'
STRATIFIED_DIFFICULTY_LEVELS = ['容易', '较易', '中等', '较难', '困难']
SAMPLING_RANDOM_SEED = 42

# ==================== 学生智能体配置 ====================
STUDENT_LEVELS = [
    {
        'name': 'excellent',
        'description': '优秀学生',
        'correct_rate': 0.95,  # 正确率95%
        'temperature': 0.3,
        'characteristics': '基础扎实，思路清晰，计算准确'
    },
    {
        'name': 'average',
        'description': '中等学生',
        'correct_rate': 0.70,  # 正确率70%
        'temperature': 0.6,
        'characteristics': '基础一般，偶尔粗心，部分知识点不牢固'
    },
    {
        'name': 'weak',
        'description': '薄弱学生',
        'correct_rate': 0.50,  # 正确率50%
        'temperature': 0.8,
        'characteristics': '基础薄弱，容易混淆概念，计算经常出错'
    }
]

# 每道题生成的学生解答数量（从上面的水平中随机选择）
NUM_STUDENTS_PER_QUESTION = 3

# ==================== 质量控制配置 ====================
# 质量阈值（0-100分）
QUALITY_THRESHOLD = 70  # 低于此分数的诊断会被拒绝

# 最大重试次数
MAX_RETRY_ATTEMPTS = 2  # 诊断质量不合格时的最大重试次数

# 质量评分权重
QUALITY_WEIGHTS = {
    'completeness': 0.3,      # 完整性（是否包含所有必需部分）
    'accuracy': 0.4,          # 准确性（诊断是否正确）
    'clarity': 0.2,           # 清晰度（表达是否清楚）
    'usefulness': 0.1         # 实用性（建议是否有帮助）
}

# ==================== 模型参数配置 ====================
# 各智能体的温度参数
AGENT_TEMPERATURES = {
    'analyzer': 0.2,      # 题目分析需要准确
    'teacher': 0.3,       # 教师诊断需要专业
    'reviewer': 0.1,      # 质量审核需要严格
    'integrator': 0.0     # 数据整合需要确定
}

# 最大输出token数
MAX_OUTPUT_TOKENS = 8192

# API调用重试配置
API_MAX_RETRIES = 3
API_RETRY_DELAY = 2  # 秒

# ==================== 输出配置 ====================
# 是否保存中间结果
SAVE_INTERMEDIATE_RESULTS = True

# 是否保存被拒绝的案例
SAVE_REJECTED_CASES = True

# 训练数据增量写入：每累积 N 条写入一次文件
INCREMENTAL_FLUSH_SIZE = 5

# 输出文件名
OUTPUT_FILES = {
    'raw_data': 'raw_data.json',              # 原始数据（包含所有中间结果）
    'training_data': 'training_data.json',    # 最终训练数据（ShareGPT格式）
    'quality_report': 'quality_report.json',  # 质量报告
    'rejected_cases': 'rejected_cases.json'   # 被拒绝的案例
}

# ==================== 输出配置 ====================
# 是否显示详细进度
VERBOSE = True

# 控制台输出级别：DEBUG, INFO, WARNING, ERROR
LOG_LEVEL = 'INFO'

# 是否启用并行处理（实验性功能）True
ENABLE_PARALLEL = False

# 并行工作线程数
PARALLEL_WORKERS = 3

# 是否启用缓存（避免重复API调用）
ENABLE_CACHE = True

# 缓存目录
CACHE_DIR = 'src/multi_agent_pipeline/output/.cache'
