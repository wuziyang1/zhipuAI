# 数学题目诊断系统

基于LLM的数学题目学生解答诊断系统，用于自动评估学生解答的正确性并给出诊断建议。

## 项目结构

```
src/
├── gen_error/
│   └── generate_error_data.py      # 生成学生解答数据（含错误和正确）
├── diagnosisv/
│   ├── generate_diagnosis.py       # V1: 验证版（模型可见正确解析）
│   ├── generate_diagnosisv2.py     # V2: 真实场景版（模型需自己解题）
│   └── generate_diagnosisv3.py     # V3: 完全自主版（模型自判知识点）
└── visualize_data.py               # 可视化诊断结果

data/
└── train_sharegpt.json             # 原始训练数据

output/
├── error_solutions/                # 学生解答数据
│   └── error_solutionsv2.json
├── diagnosis/                      # 诊断结果
│   ├── diagnosis_v1.json
│   ├── diagnosis_v2.json
│   └── diagnosis_v3.json
└── view_html/                      # 可视化HTML
    └── visualization_v3.html
```

## 使用流程

### 1. 生成学生解答数据

```bash
python src/gen_error/generate_error_data.py
```

**功能：**
- 读取训练集中的数学题目
- 使用LLM生成模拟学生的解答
- 按照配置比例生成错误/正确解答（默认7:3）

**配置参数：**
- `NUM_RECORDS`: 处理的题目数量
- `ERROR_RATIO`: 错误解答比例（0.7 = 70%错误）
- `TEMPERATURE`: 生成随机性（0-1）

**输出：** `output/error_solutions/error_solutionsv2.json`

### 2. 生成诊断评价（选择一个版本）

#### V1版本 - 验证版（推荐用于baseline）

```bash
python src/diagnosisv/generate_diagnosis.py
```

**特点：**
- 模型能看到正确解析和知识点
- 用于验证模型的诊断能力
- 诊断准确率最高

#### V2版本 - 真实场景版

```bash
python src/diagnosisv/generate_diagnosisv2.py
```

**特点：**
- 模型看不到正确解析，需要自己解题
- 模型能看到题目涉及的知识点作为提示
- 诊断结果不直接告诉学生答案
- 更符合实际教学场景

#### V3版本 - 完全自主版（推荐用于实际应用）

```bash
python src/diagnosisv/generate_diagnosisv3.py
```

**特点：**
- 模型完全自主，连知识点都要自己判断
- 自动评估诊断准确性（diagnosis_correct字段）
- 最接近实际应用场景
- 可用于发现模型的误判模式

**配置参数：**
- `NUM_RECORDS`: 处理的记录数量（None=全部）
- `TEMPERATURE`: 生成随机性
- `MAX_OUTPUT_TOKENS`: 最大输出长度

**输出：** `output/diagnosis/diagnosis_v{1,2,3}.json`

### 3. 可视化诊断结果

```bash
python src/visualize_data.py
```

**功能：**
- 生成HTML可视化页面
- 支持Markdown和LaTeX渲染
- 自动处理大数据集（超过10条随机抽样）
- 显示诊断准确性标注（V3版本）

**配置参数：**
- `INPUT_FILE`: 输入的诊断结果文件
- `MAX_DISPLAY_RECORDS`: 最多展示的记录数
- `RANDOM_SEED`: 随机种子（可固定抽样结果）
- `AUTO_OPEN_BROWSER`: 是否自动打开浏览器

**输出：** `output/view_html/visualization_v3.html`

## 三个版本的对比

| 特性 | V1 验证版 | V2 真实场景版 | V3 完全自主版 |
|------|----------|--------------|--------------|
| 模型可见正确解析 | ✅ | ❌ | ❌ |
| 模型可见知识点 | ✅ | ✅ | ❌ |
| 模型需自己解题 | ❌ | ✅ | ✅ |
| 模型需自判知识点 | ❌ | ❌ | ✅ |
| 诊断准确率统计 | ❌ | ❌ | ✅ |
| 适用场景 | 能力验证 | 教学辅助 | 实际应用 |

## 数据字段说明

### 学生解答数据（error_solutionsv2.json）

```json
{
  "id": "题目ID",
  "question": "题目内容",
  "correct_solution": "正确解析",
  "knowledge_points": ["知识点1", "知识点2"],
  "student_solution": "学生的解答",
  "is_correct": true/false  // 仅用于验证，V3输出时会移除
}
```

### 诊断结果数据（diagnosis_v3.json）

```json
{
  "id": "题目ID",
  "question": "题目内容",
  "correct_solution": "正确解析",
  "knowledge_points": ["知识点1", "知识点2"],
  "student_solution": "学生的解答",
  "diagnosis": "诊断评价内容（包含诊断过程、结果、建议等）",
  "diagnosis_correct": true/false/null  // V3特有：模型诊断是否准确
}
```

## 环境配置

需要在 `.env` 文件中配置：

```env
Gemini_API_KEY=your_api_key
Gemini_BASE_URL=your_base_url
Gemini_MODEL_NAME=your_model_name
```

## 依赖安装

```bash
pip install google-genai python-dotenv
```

## 使用建议

1. **数据准备阶段**：先用小数据集（10-20条）测试流程
2. **模型验证**：运行V1版本建立baseline
3. **效果对比**：依次运行V2、V3，对比诊断效果
4. **准确率分析**：使用V3的 `diagnosis_correct` 字段分析误判模式
5. **Prompt优化**：根据误判case优化各版本的prompt
6. **规模化测试**：扩大数据集规模（100-1000条）进行全面评估

## 后续优化方向

- [ ] 扩大测试数据集规模
- [ ] 分析不同题型、知识点的诊断准确率
- [ ] 优化prompt提升诊断准确性
- [ ] 细化错误类型分类
- [ ] 建立知识点图谱
- [ ] 开发Web界面或API服务
