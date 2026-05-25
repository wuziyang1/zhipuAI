"""
检查 train_sharegpt.json 前 N 条数据与 hjy_all.json 的分布（难度、题型、知识点等）
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRAIN_PATH = PROJECT_ROOT / "data" / "train_sharegpt.json"
HJY_PATH = PROJECT_ROOT / "data" / "hjy_all.json"
NUM_RECORDS = 50

# 难度文本 -> 1-5 星映射（与 Planner 逻辑对齐）
DIFFICULTY_TO_STAR = {
    "容易": 1,
    "较易": 2,
    "中等": 3,
    "较难": 4,
    "困难": 5,
    "难": 5,
}


def iter_json_array(path: Path):
    """流式解析 JSON 数组，避免一次性加载大文件"""
    decoder = json.JSONDecoder()
    with open(path, "r", encoding="utf-8") as f:
        ch = f.read(1)
        while ch and ch.isspace():
            ch = f.read(1)
        if ch != "[":
            raise ValueError("期望 JSON 数组")

        buf = ""
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            buf += chunk
            while True:
                buf = buf.lstrip(" \t\n\r,")
                if not buf:
                    break
                if buf[0] == "]":
                    return
                try:
                    obj, idx = decoder.raw_decode(buf)
                    yield obj
                    buf = buf[idx:]
                except json.JSONDecodeError:
                    break

        buf = buf.lstrip(" \t\n\r,")
        while buf and buf[0] != "]":
            try:
                obj, idx = decoder.raw_decode(buf)
                yield obj
                buf = buf[idx:].lstrip(" \t\n\r,")
            except json.JSONDecodeError:
                break


def load_hjy_index(target_ids: set) -> dict:
    """从 hjy_all.json 提取目标 id 的元数据"""
    found = {}
    print(f"正在从 hjy_all.json 检索 {len(target_ids)} 个 id ...")
    for i, item in enumerate(iter_json_array(HJY_PATH)):
        qid = item.get("id")
        if qid in target_ids:
            found[qid] = item
            if len(found) == len(target_ids):
                print(f"  已找齐，扫描了 {i + 1} 条 hjy 记录")
                break
        if (i + 1) % 5000 == 0:
            print(f"  已扫描 {i + 1} 条 hjy，命中 {len(found)}/{len(target_ids)}")
    return found


def infer_difficulty_from_gpt(gpt_text: str) -> int | None:
    """从 ShareGPT 解析文本中启发式提取难度（备用）"""
    patterns = [
        r"难度等级[：:]\s*(\d)",
        r"(\d)\s*星",
        r"难度[：:]\s*([一二三四五])",
    ]
    cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
    for p in patterns:
        m = re.search(p, gpt_text)
        if m:
            v = m.group(1)
            return int(v) if v.isdigit() else cn_map.get(v)
    # 关键词
    if "压轴" in gpt_text or "困难" in gpt_text:
        return 5
    if "基础" in gpt_text and "简单" in gpt_text:
        return 1
    return None


def chi_square_uniformity(counts: Counter, label: str) -> dict:
    """简单均匀性检验（卡方，类别数>=2）"""
    n = sum(counts.values())
    k = len(counts)
    if n == 0 or k < 2:
        return {"label": label, "uniform": None, "note": "样本不足"}

    expected = n / k
    chi2 = sum((c - expected) ** 2 / expected for c in counts.values())
    # 粗略阈值：df=k-1，α=0.05 时 χ²≈3.84(k=2)~9.49(k=5)
    thresholds = {2: 5.99, 3: 7.81, 4: 9.49, 5: 11.07, 6: 12.59}
    threshold = thresholds.get(k, 3.84 + (k - 1) * 1.5)
    return {
        "label": label,
        "chi2": round(chi2, 2),
        "df": k - 1,
        "threshold_approx": threshold,
        "likely_uniform": chi2 < threshold,
        "max_pct": round(max(counts.values()) / n * 100, 1),
        "min_pct": round(min(counts.values()) / n * 100, 1),
    }


def print_bar(counter: Counter, total: int, width: int = 30):
    for key, cnt in counter.most_common():
        pct = cnt / total * 100
        bar_len = int(pct / 100 * width)
        bar = "#" * bar_len + "-" * (width - bar_len)
        print(f"  {str(key):12} {cnt:3} ({pct:5.1f}%) {bar}")


def main():
    print("=" * 60)
    print(f"前 {NUM_RECORDS} 条训练数据分布检查")
    print("=" * 60)

    with open(TRAIN_PATH, encoding="utf-8") as f:
        train = json.load(f)
    subset = train[:NUM_RECORDS]
    target_ids = {r.get("id") for r in subset if r.get("id")}

    hjy_map = load_hjy_index(target_ids)
    missing = target_ids - set(hjy_map.keys())
    if missing:
        print(f"\n警告: {len(missing)} 条在 hjy_all.json 中未找到")

    rows = []
    for idx, rec in enumerate(subset, 1):
        qid = rec.get("id", f"idx_{idx}")
        hjy = hjy_map.get(qid, {})

        preset_diff = hjy.get("presetDifficulty", "未知")
        star = DIFFICULTY_TO_STAR.get(preset_diff)

        gpt = ""
        for msg in rec.get("conversations", []):
            if msg.get("from") == "gpt":
                gpt = msg.get("value", "")
                break
        inferred_star = infer_difficulty_from_gpt(gpt) if star is None else star

        kp_train = rec.get("knowledgePoints") or []
        kp_hjy = [k.get("knowName", "") for k in hjy.get("knowledgePoints", []) if k.get("knowName")]

        rows.append({
            "idx": idx,
            "id": qid,
            "preset_difficulty": preset_diff,
            "star": star or inferred_star,
            "ques_type": hjy.get("quesType") or hjy.get("busiType") or "未知",
            "year": hjy.get("year"),
            "kp_count": len(kp_hjy) or len(kp_train),
            "kp_top": (kp_hjy[0] if kp_hjy else (kp_train[0] if kp_train else "未知"))[:30],
        })

    # ---- 统计 ----
    diff_counter = Counter(r["preset_difficulty"] for r in rows)
    star_counter = Counter(r["star"] for r in rows if r["star"])
    type_counter = Counter(r["ques_type"] for r in rows)
    year_counter = Counter(r["year"] for r in rows if r["year"])
    kp_bucket = Counter(
        "1个" if r["kp_count"] <= 1 else ("2-3个" if r["kp_count"] <= 3 else "4+个")
        for r in rows
    )

    n = len(rows)
    print(f"\n【基本信息】共 {n} 条，hjy 匹配 {n - len(missing)}/{n}")
    print(f"数据来源: {TRAIN_PATH.name} + {HJY_PATH.name}")

    print("\n【预设难度 presetDifficulty】")
    print_bar(diff_counter, n)

    print("\n【难度星级 (映射到 Planner 1-5 星)】")
    print_bar(star_counter, n or 1)

    print("\n【题型 quesType】")
    print_bar(type_counter, n)

    print("\n【年份 year】")
    print_bar(year_counter, n or 1)

    print("\n【知识点数量】")
    print_bar(kp_bucket, n)

    # 均匀性检验
    print("\n【均匀性检验（卡方近似）】")
    for test in [
        chi_square_uniformity(diff_counter, "预设难度"),
        chi_square_uniformity(star_counter, "难度星级"),
        chi_square_uniformity(type_counter, "题型"),
    ]:
        if test.get("likely_uniform") is None:
            print(f"  {test['label']}: {test.get('note')}")
        else:
            status = "较均匀" if test["likely_uniform"] else "不均匀"
            print(
                f"  {test['label']}: chi2={test['chi2']} (df={test['df']}), "
                f"占比 {test['min_pct']}%~{test['max_pct']}% -> {status}"
            )

    # 理想分布建议（50条 / 5档难度 ≈ 每档10条）
    print("\n【与理想分布对比（50条建议每难度档 10 条）】")
    ideal_per_star = NUM_RECORDS // 5
    for star in range(1, 6):
        cnt = star_counter.get(star, 0)
        delta = cnt - ideal_per_star
        flag = "OK" if abs(delta) <= 3 else ("偏多" if delta > 0 else "偏少")
        print(f"  {star}星: 实际 {cnt:2}，理想 {ideal_per_star}，偏差 {delta:+d} [{flag}]")

    # 详细列表（前10 + 异常）
    print("\n【前 10 条明细】")
    print(f"{'#':>3} {'难度':8} {'星级':4} {'题型':8} {'知识点数':6} 知识点/题干摘要")
    print("-" * 70)
    for r in rows[:10]:
        print(
            f"{r['idx']:3} {r['preset_difficulty']:8} "
            f"{str(r['star'] or '?'):4} {r['ques_type']:8} "
            f"{r['kp_count']:6} {r['kp_top']}"
        )

    # 保存报告
    report_path = PROJECT_ROOT / "src" / "multi_agent_pipeline" / "output" / "first50_distribution_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "num_records": NUM_RECORDS,
        "hjy_matched": n - len(missing),
        "hjy_missing_ids": list(missing),
        "preset_difficulty": dict(diff_counter),
        "star_distribution": {str(k): v for k, v in sorted(star_counter.items())},
        "ques_type": dict(type_counter),
        "year": dict(year_counter),
        "knowledge_point_count_bucket": dict(kp_bucket),
        "uniformity_tests": [
            chi_square_uniformity(diff_counter, "preset_difficulty"),
            chi_square_uniformity(star_counter, "star"),
            chi_square_uniformity(type_counter, "ques_type"),
        ],
        "rows": rows,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {report_path}")

    # 结论
    print("\n" + "=" * 60)
    print("【结论与建议】")
    if len(missing) > 0:
        print(f"- 有 {len(missing)} 条未在 hjy 中匹配，难度统计可能不完整")
    max_star = max(star_counter.values()) if star_counter else 0
    min_star = min(star_counter.values()) if star_counter else 0
    if star_counter and (max_star - min_star) > NUM_RECORDS * 0.3:
        print("- 难度星级分布不均匀，roll 50 条时建议按难度分层抽样而非顺序取前 50")
    else:
        print("- 难度星级分布相对可接受，但仍建议分层抽样")
    if diff_counter.most_common(1)[0][1] > n * 0.4:
        top = diff_counter.most_common(1)[0]
        print(f"- 预设难度「{top[0]}」占比过高 ({top[1]}/{n})，前 50 条不代表全量")
    print("- 若跑 Pipeline：将 NUM_RECORDS=50，并考虑按难度/题型 shuffle 后抽样")
    print("=" * 60)


if __name__ == "__main__":
    main()
