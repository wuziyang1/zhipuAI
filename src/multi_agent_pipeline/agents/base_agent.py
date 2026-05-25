"""
智能体基类
提供通用的API调用、重试、缓存等功能
"""

import time
import json
import hashlib
import os
from google import genai
from typing import Optional, Dict, Any


class BaseAgent:
    """智能体基类"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        初始化智能体
        
        Args:
            name: 智能体名称
            config: 配置字典
        """
        self.name = name
        self.config = config
        
        # 初始化API客户端
        self.client = genai.Client(
            api_key=config['API_KEY'],
            http_options=genai.types.HttpOptions(
                base_url=config['BASE_URL']
            )
        )
        
        # 缓存配置
        self.enable_cache = config.get('ENABLE_CACHE', False)
        self.cache_dir = config.get('CACHE_DIR', '.cache')
        if self.enable_cache:
            os.makedirs(self.cache_dir, exist_ok=True)
        
    def _get_cache_key(self, prompt: str, temperature: float) -> str:
        """生成缓存键"""
        content = f"{self.name}:{prompt}:{temperature}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """从缓存读取"""
        if not self.enable_cache:
            return None
        
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('response')
            except Exception:
                return None
        return None
    
    def _save_to_cache(self, cache_key: str, response: str):
        """保存到缓存"""
        if not self.enable_cache:
            return
        
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'response': response}, f, ensure_ascii=False)
        except Exception:
            pass
    
    def call_llm(self, prompt: str, temperature: float = 0.3, 
                 max_retries: Optional[int] = None) -> Optional[str]:
        """
        调用LLM API（带重试和缓存）
        
        Args:
            prompt: 提示词
            temperature: 温度参数
            max_retries: 最大重试次数
        
        Returns:
            LLM响应文本，失败返回None
        """
        # 检查缓存
        cache_key = self._get_cache_key(prompt, temperature)
        cached_response = self._get_from_cache(cache_key)
        if cached_response:
            if self.config.get('VERBOSE'):
                print(f"  [{self.name}] 使用缓存结果")
            return cached_response
        
        # 设置重试次数
        if max_retries is None:
            max_retries = self.config.get('API_MAX_RETRIES', 3)
        
        retry_delay = self.config.get('API_RETRY_DELAY', 2)
        
        # 确保模型名称有正确的前缀
        model_name = self.config['MODEL_NAME']
        if not model_name.startswith('models/'):
            model_name = f'models/{model_name}'
        
        # 重试循环
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=genai.types.Content(
                        parts=[genai.types.Part(text=prompt)]
                    ),
                    config=genai.types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=self.config.get('MAX_OUTPUT_TOKENS', 8192)
                    )
                )
                
                result = response.text
                
                # 保存到缓存
                self._save_to_cache(cache_key, result)
                
                return result
                
            except Exception as e:
                error_msg = str(e)[:100]
                if attempt < max_retries - 1:
                    if self.config.get('VERBOSE'):
                        print(f"  [{self.name}] API调用失败 (尝试 {attempt+1}/{max_retries}): {error_msg}")
                        print(f"  [{self.name}] 等待 {retry_delay ** attempt} 秒后重试...")
                    time.sleep(retry_delay ** attempt)  # 指数退避
                else:
                    if self.config.get('VERBOSE'):
                        print(f"  [{self.name}] API调用失败，已达最大重试次数: {error_msg}")
                    return None
        
        return None
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理输入数据（子类需要实现）
        
        Args:
            input_data: 输入数据字典
        
        Returns:
            输出数据字典
        """
        raise NotImplementedError("子类必须实现process方法")
    
    def log(self, message: str, level: str = 'INFO'):
        """
        记录日志（控制台输出）
        
        Args:
            message: 日志消息
            level: 日志级别
        """
        log_level = self.config.get('LOG_LEVEL', 'INFO')
        levels = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3}
        
        if levels.get(level, 1) >= levels.get(log_level, 1):
            print(f"[{level}] [{self.name}] {message}")
