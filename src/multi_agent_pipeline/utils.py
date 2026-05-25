"""
工具函数
"""

import json
import os
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator

# 与 hjy presetDifficulty / Planner 星级对齐
STRATIFIED_DIFFICULTY_LEVELS = ['容易', '较易', '中等', '较难', '困难']
DIFFICULTY_TO_STAR = {
    '容易': 1, '较易': 2, '中等': 3, '较难': 4, '困难': 5, '难': 5,
}


def _resolve_project_path(file_path: str) -> str:
    """将相对路径解析为基于项目根目录的绝对路径"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    if os.path.isabs(file_path):
        return file_path
    return os.path.join(project_root, file_path)


class IncrementalJsonWriter:
    """JSON 数组增量写入器：每累积 flush_every 条新数据落盘一次"""

    def __init__(self, file_path: str, flush_every: int = 5, indent: int = 2):
        self.file_path = _resolve_project_path(file_path)
        self.flush_every = flush_every
        self.indent = indent
        self._buffer: List[Any] = []
        self._last_flushed_count = 0

        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self._write_to_disk()

    def add_items(self, items: List[Any]) -> int:
        """追加数据，每满 flush_every 条写入一次。返回本次触发的写入次数。"""
        if not items:
            return 0

        flush_count = 0
        for item in items:
            self._buffer.append(item)
            if len(self._buffer) % self.flush_every == 0:
                self._write_to_disk()
                self._last_flushed_count = len(self._buffer)
                flush_count += 1
        return flush_count

    def finalize(self) -> None:
        """写入剩余未满阈值的数据"""
        if len(self._buffer) > self._last_flushed_count:
            self._write_to_disk()
            self._last_flushed_count = len(self._buffer)

    @property
    def total_count(self) -> int:
        return len(self._buffer)

    def _write_to_disk(self) -> None:
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self._buffer, f, ensure_ascii=False, indent=self.indent)
        print(f"[已写入] {len(self._buffer)} 条 -> {self.file_path}")


class TrainingDataWriters:
    """训练数据双文件（完整版 + 纯净版）增量写入"""

    def __init__(
        self,
        run_output_dir: str,
        training_filename: str,
        flush_every: int = 5,
    ):
        training_path = os.path.join(run_output_dir, training_filename)
        minimal_path = os.path.join(run_output_dir, 'training_data_minimal.json')

        self.full_writer = IncrementalJsonWriter(training_path, flush_every=flush_every)
        self.minimal_writer = IncrementalJsonWriter(minimal_path, flush_every=flush_every)

    def add(self, items: List[Dict[str, Any]]) -> None:
        if not items:
            return
        self.full_writer.add_items(items)
        self.minimal_writer.add_items(generate_minimal_training_data(items))

    def finalize(self) -> None:
        self.full_writer.finalize()
        self.minimal_writer.finalize()


def build_overall_statistics(
    all_results: List[Dict[str, Any]],
    all_training_data: List[Dict[str, Any]],
    all_passed_cases: List[Dict[str, Any]],
    all_rejected_cases: List[Dict[str, Any]],
    total_questions: int,
) -> Dict[str, Any]:
    """根据逐题处理结果汇总统计信息"""
    total_passed = len(all_passed_cases)
    total_rejected = len(all_rejected_cases)
    quality_scores = [
        r['statistics'].get('avg_quality_score', 0)
        for r in all_results
        if r.get('statistics')
    ]

    return {
        'total_questions': total_questions,
        'total_training_samples': len(all_training_data),
        'avg_samples_per_question': len(all_training_data) / total_questions if total_questions else 0,
        'overall_avg_quality': sum(quality_scores) / len(quality_scores) if quality_scores else 0,
        'total_student_cases': sum(len(r['student_cases']) for r in all_results),
        'total_passed_cases': total_passed,
        'total_rejected_cases': total_rejected,
        'pass_rate': total_passed / (total_passed + total_rejected) * 100
        if (total_passed + total_rejected) > 0 else 0,
    }


def iter_json_array(path: str) -> Iterator[Dict[str, Any]]:
    """流式解析 JSON 数组（用于大文件 hjy_all.json）"""
    decoder = json.JSONDecoder()
    with open(path, 'r', encoding='utf-8') as f:
        ch = f.read(1)
        while ch and ch.isspace():
            ch = f.read(1)
        if ch != '[':
            raise ValueError(f'期望 JSON 数组: {path}')

        buf = ''
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            buf += chunk
            while True:
                buf = buf.lstrip(' \t\n\r,')
                if not buf:
                    break
                if buf[0] == ']':
                    return
                try:
                    obj, idx = decoder.raw_decode(buf)
                    yield obj
                    buf = buf[idx:]
                except json.JSONDecodeError:
                    break

        buf = buf.lstrip(' \t\n\r,')
        while buf and buf[0] != ']':
            try:
                obj, idx = decoder.raw_decode(buf)
                yield obj
                buf = buf[idx:].lstrip(' \t\n\r,')
            except json.JSONDecodeError:
                break


def _parse_sharegpt_record(record: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """从 ShareGPT 记录提取题目字段"""
    conversations = record.get('conversations', [])
    question = ''
    correct_solution = ''
    for msg in conversations:
        if msg['from'] == 'human':
            question = msg['value']
        elif msg['from'] == 'gpt':
            correct_solution = msg['value']

    return {
        'id': record.get('id', f'question_{idx + 1}'),
        'question': question,
        'correct_solution': correct_solution,
        'knowledge_points': record.get('knowledgePoints', []),
    }


def build_hjy_difficulty_index(
    train_ids: set,
    hjy_path: str,
    cache_path: str,
    force_rebuild: bool = False,
) -> Dict[str, str]:
    """
    构建 train id -> presetDifficulty 索引（带本地缓存）
    """
    hjy_full = _resolve_project_path(hjy_path)
    cache_full = _resolve_project_path(cache_path)
    train_ids = set(train_ids)

    if not force_rebuild and os.path.exists(cache_full):
        with open(cache_full, 'r', encoding='utf-8') as f:
            cached = json.load(f)
        if train_ids.issubset(cached.keys()):
            print(f'[分层抽样] 使用难度索引缓存: {cache_path}')
            return {k: cached[k] for k in train_ids}

    print(f'[分层抽样] 正在从 {hjy_path} 构建难度索引（约需 1-2 分钟）...')
    index = {}
    for i, item in enumerate(iter_json_array(hjy_full)):
        qid = item.get('id')
        if qid in train_ids:
            index[qid] = item.get('presetDifficulty') or '未知'
            if len(index) == len(train_ids):
                print(f'  索引完成，扫描 {i + 1} 条 hjy 记录')
                break
        if (i + 1) % 10000 == 0:
            print(f'  已扫描 {i + 1} 条 hjy，命中 {len(index)}/{len(train_ids)}')

    missing = train_ids - set(index.keys())
    if missing:
        print(f'[分层抽样] 警告: {len(missing)} 条在 hjy 中无难度元数据，将归入「未知」')

    os.makedirs(os.path.dirname(cache_full), exist_ok=True)
    with open(cache_full, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False)
    print(f'[分层抽样] 难度索引已缓存: {cache_path} ({len(index)} 条)')

    return index


def _allocate_stratum_quotas(
    total: int,
    levels: List[str],
    pool_sizes: Dict[str, int],
) -> Dict[str, int]:
    """在各难度层之间分配抽样配额（不超过各层容量）"""
    active = [lv for lv in levels if pool_sizes.get(lv, 0) > 0]
    if not active:
        return {}

    n = len(active)
    base, rem = divmod(total, n)
    quotas = {}
    for i, lv in enumerate(active):
        want = base + (1 if i < rem else 0)
        quotas[lv] = min(want, pool_sizes[lv])

    assigned = sum(quotas.values())
    # 配额不足时，从仍有剩余的层补齐
    while assigned < total:
        progressed = False
        for lv in active:
            if quotas[lv] < pool_sizes[lv]:
                quotas[lv] += 1
                assigned += 1
                progressed = True
                if assigned >= total:
                    break
        if not progressed:
            break

    return quotas


def stratified_sample_questions(
    questions: List[Dict[str, Any]],
    difficulty_index: Dict[str, str],
    num_records: int,
    levels: Optional[List[str]] = None,
    random_seed: int = 42,
) -> List[Dict[str, Any]]:
    """按 presetDifficulty 分层抽样"""
    levels = levels or STRATIFIED_DIFFICULTY_LEVELS
    rng = random.Random(random_seed)

    buckets: Dict[str, List[Dict[str, Any]]] = {lv: [] for lv in levels}
    unclassified: List[Dict[str, Any]] = []

    for q in questions:
        diff = difficulty_index.get(q['id'], '未知')
        if diff in levels:
            buckets[diff].append(q)
        else:
            unclassified.append(q)

    active_levels = [lv for lv in levels if buckets[lv]]
    pool_sizes = {lv: len(buckets[lv]) for lv in active_levels}
    quotas = _allocate_stratum_quotas(num_records, active_levels, pool_sizes)

    selected = []
    print('[分层抽样] 各难度配额与抽样结果:')
    for lv in active_levels:
        pool = buckets[lv][:]
        rng.shuffle(pool)
        take = quotas.get(lv, 0)
        picked = pool[:take]
        selected.extend(picked)
        star = DIFFICULTY_TO_STAR.get(lv, '?')
        print(
            f'  {lv}({star}星): 池={len(pool):5} 配额={take:3} 实抽={len(picked):3}'
        )

    if unclassified:
        print(f'  [未分类] hjy 无难度元数据: {len(unclassified)} 条（仅用于补齐）')

    # 若总量仍不足，从未选中题目 / 未分类题目中补齐
    if len(selected) < num_records:
        selected_ids = {q['id'] for q in selected}
        remainder = [q for q in questions if q['id'] not in selected_ids]
        rng.shuffle(remainder)
        need = num_records - len(selected)
        extra = remainder[:need]
        selected.extend(extra)
        print(f'  [补齐] 补充 {len(extra)} 条')

    rng.shuffle(selected)
    return selected[:num_records]


def load_training_data(
    file_path: str,
    num_records: int = None,
    stratified: bool = False,
    hjy_metadata_file: str = 'data/hjy_all.json',
    hjy_cache_file: str = 'data/hjy_difficulty_index.json',
    stratified_levels: Optional[List[str]] = None,
    random_seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    加载训练数据

    Args:
        file_path: 数据文件路径（相对于项目根目录）
        num_records: 加载的记录数量（None表示全部）
        stratified: 是否按 hjy 难度分层抽样
        hjy_metadata_file: hjy 元数据文件路径
        hjy_cache_file: 难度索引缓存路径
        stratified_levels: 参与分层的难度档位
        random_seed: 随机种子（保证可复现）

    Returns:
        题目列表
    """
    full_path = _resolve_project_path(file_path)

    print(f'正在加载数据: {file_path}')
    print(f'完整路径: {full_path}')

    with open(full_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    questions = [_parse_sharegpt_record(record, idx) for idx, record in enumerate(data)]
    print(f'数据集共 {len(questions)} 条')

    if num_records is None or num_records >= len(questions):
        print(f'成功加载全部 {len(questions)} 条题目')
        return questions

    if stratified:
        levels = stratified_levels or STRATIFIED_DIFFICULTY_LEVELS
        train_ids = {q['id'] for q in questions}
        difficulty_index = build_hjy_difficulty_index(
            train_ids, hjy_metadata_file, hjy_cache_file
        )
        questions = stratified_sample_questions(
            questions,
            difficulty_index,
            num_records,
            levels=levels,
            random_seed=random_seed,
        )
        dist = Counter(difficulty_index.get(q['id'], '未知') for q in questions)
        print('[分层抽样] 最终难度分布:')
        for lv, cnt in dist.most_common():
            print(f'  {lv}: {cnt}')
    else:
        questions = questions[:num_records]
        print(f'顺序截取前 {num_records} 条')

    print(f'成功加载 {len(questions)} 条题目')
    return questions


def save_json(data: Any, file_path: str, indent: int = 2):
    """
    保存JSON文件
    
    Args:
        data: 要保存的数据
        file_path: 文件路径（相对于项目根目录）
        indent: 缩进空格数
    """
    full_path = _resolve_project_path(file_path)
    
    # 确保目录存在
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    
    print(f"[已保存] {file_path}")


def generate_quality_report(results: Dict[str, Any], output_path: str):
    """
    生成质量报告
    
    Args:
        results: Pipeline处理结果
        output_path: 输出路径
    """
    statistics = results['overall_statistics']
    all_results = results['all_results']
    
    report = {
        'summary': {
            '总题目数': statistics['total_questions'],
            '总学生案例数': statistics['total_student_cases'],
            '通过审核数': statistics['total_passed_cases'],
            '被拒绝数': statistics['total_rejected_cases'],
            '通过率': f"{statistics['pass_rate']:.1f}%",
            '最终训练数据': statistics['total_training_samples'],
            '平均质量分': f"{statistics['overall_avg_quality']:.1f}"
        },
        'per_question_details': []
    }
    
    # 每个题目的详细信息
    for result in all_results:
        detail = {
            'question_id': result['question_id'],
            'question_preview': result['question'][:100] + '...',
            'difficulty': result['analysis'].get('difficulty', 'N/A'),
            'knowledge_points': result['analysis'].get('knowledge_points', []),
            'student_cases_count': len(result['student_cases']),
            'passed_count': len(result['passed_cases']),
            'rejected_count': len(result['rejected_cases']),
            'avg_quality_score': result['statistics'].get('avg_quality_score', 0)
        }
        report['per_question_details'].append(detail)
    
    save_json(report, output_path)


def generate_minimal_training_data(training_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    生成纯净版训练数据（移除元数据）
    
    Args:
        training_data: 完整的训练数据
    
    Returns:
        纯净版训练数据（只保留conversations）
    """
    minimal_data = []
    
    for item in training_data:
        minimal_item = {
            'conversations': item['conversations']
        }
        minimal_data.append(minimal_item)
    
    return minimal_data


def print_sample_data(training_data: List[Dict[str, Any]], num_samples: int = 1):
    """
    打印示例数据
    
    Args:
        training_data: 训练数据
        num_samples: 打印的示例数量
    """
    print(f"\n{'='*60}")
    print(f"示例数据（前{num_samples}条）")
    print(f"{'='*60}")
    
    for idx, item in enumerate(training_data[:num_samples], 1):
        print(f"\n--- 示例 {idx} ---")
        
        conversations = item.get('conversations', [])
        
        for msg in conversations:
            role = msg['from']
            content = msg['value']
            
            # 截断显示
            if len(content) > 200:
                content = content[:200] + '...'
            
            print(f"\n[{role.upper()}]")
            print(content)
        
        # 显示元数据
        metadata = item.get('_metadata', {})
        if metadata:
            print(f"\n[元数据]")
            print(f"  知识点: {', '.join(metadata.get('knowledge_points', []))}")
            print(f"  学生水平: {metadata.get('student_level', 'N/A')}")
            print(f"  质量分: {metadata.get('quality_score', 'N/A')}")
    
    print(f"\n{'='*60}\n")
