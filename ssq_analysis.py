# -*- coding: utf-8 -*-
"""
双色球历史数据统计分析 + 预测公式推导 + 回归测试
"""
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime

# ===================== 1. 加载数据 =====================
def load_data(csv_path):
    data = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            issue = row['期号']
            reds = [int(row[f'红球{i}']) for i in range(1, 7)]
            blue = int(row['蓝球'])
            data.append({'issue': issue, 'reds': sorted(reds), 'blue': blue})
    return data

data = load_data(r'c:\Users\DELL\Desktop\ai_a_stock\ssq_history_utf8.csv')
total = len(data)
print(f"加载 {total} 期数据")

# ===================== 2. 基础频率统计 =====================
red_counter = Counter()
blue_counter = Counter()
for d in data:
    for r in d['reds']:
        red_counter[r] += 1
    blue_counter[d['blue']] += 1

# 红球理论期望 = total * 6 / 33
red_expected = total * 6 / 33
print(f"\n红球理论期望出现次数: {red_expected:.1f}")

print("\n=== 红球频率排名 (Top 10 热号) ===")
for num, cnt in red_counter.most_common(10):
    freq = cnt / total * 100
    print(f"  红球 {num:02d}: {cnt}次 ({freq:.2f}%)")

print("\n=== 红球频率排名 (Bottom 10 冷号) ===")
for num, cnt in red_counter.most_common()[-10:]:
    freq = cnt / total * 100
    print(f"  红球 {num:02d}: {cnt}次 ({freq:.2f}%)")

# 蓝球理论期望 = total / 16
blue_expected = total / 16
print(f"\n蓝球理论期望出现次数: {blue_expected:.1f}")

print("\n=== 蓝球频率排名 ===")
for num, cnt in blue_counter.most_common():
    freq = cnt / total * 100
    bar = '█' * int(freq * 2)
    print(f"  蓝球 {num:02d}: {cnt}次 ({freq:5.2f}%) {bar}")

# ===================== 3. 奇偶比分析 =====================
odd_even_ratio = Counter()
for d in data:
    odd_count = sum(1 for r in d['reds'] if r % 2 == 1)
    even_count = 6 - odd_count
    odd_even_ratio[f"{odd_count}:{even_count}"] += 1

print("\n=== 红球奇偶比分布 ===")
for ratio, cnt in sorted(odd_even_ratio.items(), key=lambda x: int(x[0][0]), reverse=True):
    freq = cnt / total * 100
    bar = '█' * int(freq)
    print(f"  {ratio}: {cnt}次 ({freq:.1f}%) {bar}")

# ===================== 4. 和值分析 =====================
sums = [sum(d['reds']) for d in data]
min_sum, max_sum = min(sums), max(sums)
avg_sum = sum(sums) / len(sums)

# 和值区间分布
sum_ranges = Counter()
for s in sums:
    if s < 60:
        sum_ranges['<60 (小)'] += 1
    elif s < 80:
        sum_ranges['60-79'] += 1
    elif s < 100:
        sum_ranges['80-99'] += 1
    elif s < 120:
        sum_ranges['100-119'] += 1
    elif s < 140:
        sum_ranges['120-139'] += 1
    else:
        sum_ranges['>=140 (大)'] += 1

print(f"\n=== 红球和值统计 ===")
print(f"  最小值: {min_sum}, 最大值: {max_sum}, 平均值: {avg_sum:.1f}")
for rng, cnt in sorted(sum_ranges.items()):
    freq = cnt / total * 100
    bar = '█' * int(freq)
    print(f"  {rng:>15s}: {cnt}次 ({freq:.1f}%) {bar}")

# ===================== 5. 区间分布 (1-11, 12-22, 23-33) =====================
zone_counter = Counter()
for d in data:
    z1 = sum(1 for r in d['reds'] if 1 <= r <= 11)
    z2 = sum(1 for r in d['reds'] if 12 <= r <= 22)
    z3 = sum(1 for r in d['reds'] if 23 <= r <= 33)
    zone_counter[f"{z1}-{z2}-{z3}"] += 1

print("\n=== 区间分布 Top 10 (1-11区 / 12-22区 / 23-33区) ===")
for pattern, cnt in zone_counter.most_common(10):
    freq = cnt / total * 100
    print(f"  {pattern}: {cnt}次 ({freq:.1f}%)")

# ===================== 6. 连号分析 =====================
consecutive_counter = Counter()
for d in data:
    reds = d['reds']
    consec = 0
    for i in range(len(reds) - 1):
        if reds[i+1] - reds[i] == 1:
            consec += 1
    consecutive_counter[consec] += 1

print("\n=== 连号个数分布 ===")
for cnt_num in sorted(consecutive_counter.keys()):
    cnt_val = consecutive_counter[cnt_num]
    freq = cnt_val / total * 100
    print(f"  {cnt_num}组连号: {cnt_val}次 ({freq:.1f}%)")

# ===================== 7. 缺失分析（冷号遗漏期数）=====================
print("\n=== 红球当前遗漏期数 ===")
missing_reds = {i: 0 for i in range(1, 34)}
for d in reversed(data):
    found = False
    for r in d['reds']:
        if missing_reds[r] == 0:
            missing_reds[r] = 0  # just appeared
    for num in range(1, 34):
        if num not in d['reds']:
            missing_reds[num] += 1
    # Count from latest backwards isn't right, let me fix
    
# Better approach: find last appearance
last_appear_red = {}
last_appear_blue = {}
for i, d in enumerate(data):
    for r in d['reds']:
        last_appear_red[r] = i
    last_appear_blue[d['blue']] = i

current_missing_red = {num: total - 1 - idx for num, idx in last_appear_red.items()}
current_missing_blue = {num: total - 1 - idx for num, idx in last_appear_blue.items()}

print("  红球遗漏 Top 5 (最冷):")
for num, miss in sorted(current_missing_red.items(), key=lambda x: x[1], reverse=True)[:5]:
    print(f"    红球 {num:02d}: 遗漏 {miss} 期")

print("  蓝球当前遗漏:")
for num in range(1, 17):
    miss = current_missing_blue.get(num, total)
    bar = '█' * min(miss, 40)
    print(f"    蓝球 {num:02d}: 遗漏 {miss:4d} 期 {bar}")

# ===================== 8. 预测公式推导 =====================
print("\n" + "="*60)
print("       预测公式推导")
print("="*60)

# 公式1: 频率权重法 (基于历史频率)
# P(球x) = freq(x) / total * (6/33 修正)
print("\n【公式1: 频率权重预测法】")
print("  Score_red(x) = (freq(x) - freq_min) / (freq_max - freq_min)")
print("  依据: 历史出现频率越高的球，下期出现概率越大（热号追踪）")
red_scores_freq = {}
freq_max = max(red_counter.values())
freq_min = min(red_counter.values())
for num in range(1, 34):
    score = (red_counter[num] - freq_min) / (freq_max - freq_min) if freq_max != freq_min else 0
    red_scores_freq[num] = score

top_reds_freq = sorted(red_scores_freq.items(), key=lambda x: x[1], reverse=True)[:6]
print(f"  预测红球: {[x[0] for x in top_reds_freq]}")

# 公式2: 遗漏回补法 (冷号反弹)
print("\n【公式2: 遗漏回补预测法】")
print("  Score_cold(x) = missing(x) / max_missing")
print("  依据: 长期未出的球，下一期出现概率增大（冷号回补）")

red_scores_cold = {}
max_miss_red = max(current_missing_red.values()) if current_missing_red else 1
for num in range(1, 34):
    score = current_missing_red.get(num, 0) / max_miss_red
    red_scores_cold[num] = score

top_reds_cold = sorted(red_scores_cold.items(), key=lambda x: x[1], reverse=True)[:6]
print(f"  预测红球: {[x[0] for x in top_reds_cold]}")

# 公式3: 综合加权公式
print("\n【公式3: 综合加权预测法 (推荐)】")
print("  Score(x) = w1 * Score_freq(x) + w2 * Score_cold(x) + w3 * Score_zone(x)")
print("  权重: w1=0.4 (历史频率), w2=0.4 (遗漏回补), w3=0.2 (区间平衡)")

# 区间平衡得分
zone_balance = {1: 0, 2: 0, 3: 0}
for d in data[-30:]:
    for r in d['reds']:
        if r <= 11:
            zone_balance[1] += 1
        elif r <= 22:
            zone_balance[2] += 1
        else:
            zone_balance[3] += 1
# 需要补充的区间 (缺的得分高)
zone_total = sum(zone_balance.values())
zone_scores = {1: 1 - zone_balance[1]/zone_total, 2: 1 - zone_balance[2]/zone_total, 3: 1 - zone_balance[3]/zone_total}

red_scores_combined = {}
for num in range(1, 34):
    zone = 1 if num <= 11 else (2 if num <= 22 else 3)
    score = (0.4 * red_scores_freq[num] + 
             0.4 * red_scores_cold[num] + 
             0.2 * zone_scores[zone])
    red_scores_combined[num] = score

top_reds_combined = sorted(red_scores_combined.items(), key=lambda x: x[1], reverse=True)[:6]
print(f"  预测红球: {sorted([x[0] for x in top_reds_combined])}")

# 蓝球公式
print("\n【蓝球预测公式】")
print("  Score_blue(x) = 0.5 * freq_score(x) + 0.5 * cold_score(x)")

blue_scores = {}
blue_freq_max = max(blue_counter.values())
blue_freq_min = min(blue_counter.values())
max_miss_blue = max(current_missing_blue.values()) if current_missing_blue else 1

for num in range(1, 17):
    freq_score = (blue_counter[num] - blue_freq_min) / (blue_freq_max - blue_freq_min) if blue_freq_max != blue_freq_min else 0
    cold_score = current_missing_blue.get(num, 0) / max_miss_blue
    blue_scores[num] = 0.5 * freq_score + 0.5 * cold_score

top_blues = sorted(blue_scores.items(), key=lambda x: x[1], reverse=True)[:3]
print(f"  预测蓝球 Top3: {[x[0] for x in top_blues]}")

# ===================== 9. 回归测试 =====================
print("\n" + "="*60)
print("       回归测试 (Backtesting)")
print("="*60)

# 留出最近100期作为测试集
TEST_SIZE = 100
train_data = data[:-TEST_SIZE]
test_data = data[-TEST_SIZE:]

# 在训练集上计算频率
train_red_counter = Counter()
train_blue_counter = Counter()
for d in train_data:
    for r in d['reds']:
        train_red_counter[r] += 1
    train_blue_counter[d['blue']] += 1

def predict_top_reds(train_set, top_n=6):
    """基于训练集的频率预测"""
    counter = Counter()
    for d in train_set:
        for r in d['reds']:
            counter[r] += 1
    return [x[0] for x in counter.most_common(top_n)]

def predict_blue(train_set, top_n=1):
    counter = Counter()
    for d in train_set:
        counter[d['blue']] += 1
    return [x[0] for x in counter.most_common(top_n)]

def predict_cold_reds(train_set, top_n=6):
    """基于遗漏预测"""
    last_appear = {}
    for i, d in enumerate(train_set):
        for r in d['reds']:
            last_appear[r] = i
    total = len(train_set)
    missing = {num: total - 1 - last_appear.get(num, -1) for num in range(1, 34)}
    return [x[0] for x in sorted(missing.items(), key=lambda x: x[1], reverse=True)[:top_n]]

def predict_cold_blue(train_set, top_n=1):
    last_appear = {}
    for i, d in enumerate(train_set):
        last_appear[d['blue']] = i
    total = len(train_set)
    missing = {num: total - 1 - last_appear.get(num, -1) for num in range(1, 17)}
    return [x[0] for x in sorted(missing.items(), key=lambda x: x[1], reverse=True)[:top_n]]

def predict_combined_reds(train_set, top_n=6):
    """综合预测"""
    counter = Counter()
    for d in train_set:
        for r in d['reds']:
            counter[r] += 1
    
    last_appear = {}
    for i, d in enumerate(train_set):
        for r in d['reds']:
            last_appear[r] = i
    total = len(train_set)
    missing = {num: total - 1 - last_appear.get(num, -1) for num in range(1, 34)}
    
    freq_max = max(counter.values())
    freq_min = min(counter.values())
    miss_max = max(missing.values())
    
    scores = {}
    for num in range(1, 34):
        f_score = (counter[num] - freq_min) / (freq_max - freq_min) if freq_max != freq_min else 0
        m_score = missing[num] / miss_max if miss_max > 0 else 0
        scores[num] = 0.5 * f_score + 0.5 * m_score
    
    return [x[0] for x in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]]

def predict_combined_blue(train_set, top_n=1):
    counter = Counter()
    for d in train_set:
        counter[d['blue']] += 1
    
    last_appear = {}
    for i, d in enumerate(train_set):
        last_appear[d['blue']] = i
    total = len(train_set)
    missing = {num: total - 1 - last_appear.get(num, -1) for num in range(1, 17)}
    
    freq_max = max(counter.values())
    freq_min = min(counter.values())
    miss_max = max(missing.values())
    
    scores = {}
    for num in range(1, 17):
        f_score = (counter[num] - freq_min) / (freq_max - freq_min) if freq_max != freq_min else 0
        m_score = missing[num] / miss_max if miss_max > 0 else 0
        scores[num] = 0.5 * f_score + 0.5 * m_score
    
    return [x[0] for x in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]]

# 滑动窗口回归测试
print(f"\n测试集: 最近 {TEST_SIZE} 期")
print(f"训练集: 前 {len(train_data)} 期")
print("\n--- 滑动窗口回归测试 (每次用前N期预测下一期) ---")

models = {
    "频率法(热号)": (predict_top_reds, predict_blue),
    "遗漏法(冷号)": (predict_cold_reds, predict_cold_blue),
    "综合法(热+冷)": (predict_combined_reds, predict_combined_blue),
}

results = {}
for model_name, (red_fn, blue_fn) in models.items():
    red_hits_total = 0
    blue_hits = 0
    red_hit_counts = []
    
    for i in range(len(test_data)):
        # 用测试集之前的全部数据 + 测试集中已"发生"的数据作为训练集
        current_train = data[:-(TEST_SIZE - i)]
        pred_reds = set(red_fn(current_train, 6))
        pred_blues = set(blue_fn(current_train, 1))
        
        actual_reds = set(test_data[i]['reds'])
        actual_blue = test_data[i]['blue']
        
        red_hit = len(pred_reds & actual_reds)
        blue_hit = 1 if actual_blue in pred_blues else 0
        
        red_hits_total += red_hit
        blue_hits += blue_hit
        red_hit_counts.append(red_hit)
    
    avg_red_hit = red_hits_total / len(test_data)
    blue_acc = blue_hits / len(test_data) * 100
    
    # 红球命中分布
    red_hit_dist = Counter(red_hit_counts)
    
    results[model_name] = {
        'avg_red_hit': avg_red_hit,
        'blue_acc': blue_acc,
        'red_hit_dist': red_hit_dist,
        'red_hits_total': red_hits_total,
        'blue_hits': blue_hits,
    }

for model_name, r in results.items():
    print(f"\n{'='*40}")
    print(f"  {model_name}")
    print(f"{'='*40}")
    print(f"  红球平均命中: {r['avg_red_hit']:.2f} / 6  ({r['avg_red_hit']/6*100:.1f}%)")
    print(f"  蓝球准确率: {r['blue_acc']:.1f}% ({r['blue_hits']}/{TEST_SIZE})")
    print(f"  红球命中分布:")
    for hit_num in sorted(r['red_hit_dist'].keys()):
        cnt = r['red_hit_dist'][hit_num]
        bar = '█' * cnt
        print(f"    命中 {hit_num} 个: {cnt:3d} 期 ({cnt/TEST_SIZE*100:5.1f}%) {bar}")

# ===================== 10. 随机基准对比 =====================
print(f"\n{'='*40}")
print("  随机选号基准 (理论值)")
print(f"{'='*40}")
# 从33个红球选6个, 预测6个, 期望命中数
# 超几何分布: E(hits) = 6 * 6 / 33 = 1.09
import random
random.seed(42)
rand_red_hits = []
rand_blue_hits = 0
for i in range(1000):
    pred = set(random.sample(range(1, 34), 6))
    # 用实际开奖数据
    if i < len(test_data):
        actual = set(test_data[i]['reds'])
        rand_red_hits.append(len(pred & actual))
        if random.randint(1, 16) == test_data[i]['blue']:
            rand_blue_hits += 1

print(f"  随机红球期望命中: {6*6/33:.2f} / 6")
print(f"  随机蓝球期望准确率: {1/16*100:.2f}%")
print(f"  模拟随机红球平均命中: {sum(rand_red_hits)/len(rand_red_hits):.2f} / 6")
print(f"  模拟随机蓝球准确率: {rand_blue_hits/min(len(test_data),1000)*100:.1f}%")

# ===================== 11. 最优公式总结 =====================
print("\n" + "="*60)
print("       最终推荐预测公式")
print("="*60)

best_model = max(results.items(), key=lambda x: x[1]['avg_red_hit'] + x[1]['blue_acc']/100)
print(f"""
基于回归测试结果，最优模型为: **{best_model[0]}**

### 红球预测公式:

Score_red(x) = 0.5 × FreqScore(x) + 0.5 × ColdScore(x)

其中:
- FreqScore(x) = (freq(x) - freq_min) / (freq_max - freq_min)
  freq(x): 球x在历史所有期数中出现的次数
- ColdScore(x) = missing(x) / max_missing
  missing(x): 球x自上次出现后遗漏的期数

选取 Score 最高的 6 个红球作为预测结果。

### 蓝球预测公式:

Score_blue(x) = 0.5 × FreqScore(x) + 0.5 × ColdScore(x)

选取 Score 最高的 1 个蓝球作为预测结果。

### 回归测试表现:
- 红球平均命中: {best_model[1]['avg_red_hit']:.2f} / 6 (vs 随机 {6*6/33:.2f})
- 蓝球准确率: {best_model[1]['blue_acc']:.1f}% (vs 随机 {1/16*100:.1f}%)
""")

# ===================== 12. 下一次预测 =====================
print("="*60)
print("       基于全部数据 → 下期预测 (2026063)")
print("="*60)

# 基于全部数据的综合预测
next_reds = predict_combined_reds(data, 12)
next_blue = predict_combined_blue(data, 3)

print(f"\n  推荐红球 (Top 12, 从中选6): {sorted(next_reds)}")
print(f"  推荐蓝球 (Top 3): {next_blue}")

print("\n  综合得分 Top 6 红球:")
all_scores = {}
all_counter = Counter()
for d in data:
    for r in d['reds']:
        all_counter[r] += 1

all_last = {}
for i, d in enumerate(data):
    for r in d['reds']:
        all_last[r] = i

all_missing = {num: total - 1 - all_last.get(num, -1) for num in range(1, 34)}
freq_max_all = max(all_counter.values())
freq_min_all = min(all_counter.values())
miss_max_all = max(all_missing.values())

for num in range(1, 34):
    f = (all_counter[num] - freq_min_all) / (freq_max_all - freq_min_all)
    m = all_missing[num] / miss_max_all
    all_scores[num] = 0.5 * f + 0.5 * m

for num, score in sorted(all_scores.items(), key=lambda x: x[1], reverse=True)[:6]:
    freq = all_counter[num]
    miss = all_missing[num]
    print(f"    红球 {num:02d}: 得分 {score:.4f} (出现{freq}次, 遗漏{miss}期)")

# ===================== 保存报告 =====================
report_path = r'c:\Users\DELL\Desktop\ai_a_stock\ssq_analysis_report.md'
with open(report_path, 'w', encoding='utf-8') as f:
    f.write("# 双色球历史数据分析报告\n\n")
    f.write(f"**数据范围**: 2003001 ~ 2026062 共 {total} 期\n\n")
    f.write("---\n\n")
    
    f.write("## 一、红球频率分析\n\n")
    f.write("| 排名 | 号码 | 出现次数 | 频率 | 类型 |\n")
    f.write("|------|------|----------|------|------|\n")
    sorted_reds = sorted(red_counter.items(), key=lambda x: x[1], reverse=True)
    for rank, (num, cnt) in enumerate(sorted_reds, 1):
        freq = cnt / total * 100
        ftype = "热号" if cnt >= red_expected else "冷号"
        f.write(f"| {rank} | {num:02d} | {cnt} | {freq:.2f}% | {ftype} |\n")
    
    f.write("\n## 二、蓝球频率分析\n\n")
    f.write("| 号码 | 出现次数 | 频率 |\n")
    f.write("|------|----------|------|\n")
    for num in range(1, 17):
        cnt = blue_counter[num]
        freq = cnt / total * 100
        f.write(f"| {num:02d} | {cnt} | {freq:.2f}% |\n")
    
    f.write("\n## 三、奇偶比分析\n\n")
    f.write("| 奇偶比 | 次数 | 占比 |\n")
    f.write("|--------|------|------|\n")
    for ratio, cnt in sorted(odd_even_ratio.items(), key=lambda x: x[1], reverse=True):
        f.write(f"| {ratio} | {cnt} | {cnt/total*100:.1f}% |\n")
    
    f.write("\n## 四、和值统计\n\n")
    f.write(f"- 最小值: {min_sum}\n")
    f.write(f"- 最大值: {max_sum}\n")
    f.write(f"- 平均值: {avg_sum:.1f}\n")
    f.write(f"- 标准差: {math.sqrt(sum((s-avg_sum)**2 for s in sums)/len(sums)):.1f}\n\n")
    
    f.write("\n## 五、预测公式\n\n")
    f.write("### 红球综合得分公式\n\n")
    f.write("```\n")
    f.write("Score(x) = 0.5 × (freq(x) - freq_min) / (freq_max - freq_min)\n")
    f.write("         + 0.5 × missing(x) / max_missing\n")
    f.write("```\n\n")
    f.write("### 蓝球综合得分公式\n\n")
    f.write("```\n")
    f.write("Score(x) = 0.5 × (freq(x) - freq_min) / (freq_max - freq_min)\n")
    f.write("         + 0.5 × missing(x) / max_missing\n")
    f.write("```\n\n")
    
    f.write("\n## 六、回归测试结果\n\n")
    f.write(f"测试集: 最近 {TEST_SIZE} 期\n\n")
    f.write("| 模型 | 红球平均命中 | 蓝球准确率 |\n")
    f.write("|------|-------------|------------|\n")
    for model_name, r in results.items():
        f.write(f"| {model_name} | {r['avg_red_hit']:.2f}/6 ({r['avg_red_hit']/6*100:.1f}%) | {r['blue_acc']:.1f}% |\n")
    f.write(f"| 随机基准 | {6*6/33:.2f}/6 (18.2%) | {1/16*100:.1f}% |\n")
    
    f.write("\n## 七、下期预测 (2026063)\n\n")
    f.write(f"**推荐红球**: {sorted(next_reds[:6])}\n\n")
    f.write(f"**推荐蓝球**: {next_blue[:1]}\n\n")

print(f"\n\n分析报告已保存至: {report_path}")
print("完成!")
