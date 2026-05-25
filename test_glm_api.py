"""测试 GLM API 调用"""
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv('EVAL_API_KEY')
base_url = os.getenv('EVAL_BASE_URL')

print(f"API Key: {api_key[:20]}...")
print(f"Base URL: {base_url}")

client = genai.Client(
    api_key=api_key,
    http_options=genai.types.HttpOptions(base_url=base_url)
)

# 测试不同的模型名称格式
test_models = [
    'openrouter:z-ai/glm-5.1',
    'models/openrouter:z-ai/glm-5.1',
    'z-ai/glm-5.1',
    'glm-5.1',
]

for model_name in test_models:
    print(f"\n{'='*60}")
    print(f"测试模型名: {model_name}")
    print(f"{'='*60}")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=genai.types.Content(
                parts=[genai.types.Part(text="你好，请回复'收到'")]
            ),
            config=genai.types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=100,
            )
        )
        print(f"✓ 成功! 响应: {response.text[:100]}")
        break
    except Exception as e:
        print(f"✗ 失败: {str(e)[:200]}")
