"""今日强势股筛选 + 多因子评分推荐"""
import pandas as pd
import requests
import time
from datetime import date
from mootdx.quotes import Quotes

d = date.today().strftime("%Y-%m-%d")
print(f"=== 今日({d})强势股拉取 ===")

url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{d}/orderby/date/orderway/desc/charset/GBK/"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
df = pd.DataFrame(r.json().get("data") or [])

if df.empty:
    print("今天暂无数据")
    exit()

print(f"当日强势股: {len(df)} 只\n")

# 检查列名
if "zhangfu" not in df.columns or "huanshou" not in df.columns:
    print("列名不匹配:", list(df.columns))
    exit()

df["zhangfu"] = df["zhangfu"].astype(float)
df["huanshou"] = df["huanshou"].astype(float)

# 筛选：涨幅3-8%（非涨停有空间）+ 换手3-25%（活跃）
mask = (df["zhangfu"] >= 3) & (df["zhangfu"] <= 8) & (df["huanshou"] >= 3) & (df["huanshou"] <= 25)
candidates = df[mask].copy()
print(f"初步筛选: {len(candidates)} 只 (涨幅3-8%, 换手3-25%)")

if len(candidates) == 0:
    print("无候选，扩大筛选范围...")
    mask2 = (df["zhangfu"] >= 1) & (df["zhangfu"] <= 9) & (df["huanshou"] >= 1)
    candidates = df[mask2].copy()
    print(f"放宽筛选: {len(candidates)} 只")

top = candidates.head(10)
print(f"\n{'代码':<8}{'名称':<10}{'涨幅%':<8}{'换手%':<8}{'题材归因'}")
print("-" * 80)
codes = []
for _, row in top.iterrows():
    code = str(row["code"]).zfill(6)
    name = str(row.get("name", ""))
    zf = row["zhangfu"]
    hs = row["huanshou"]
    reason = str(row.get("reason", ""))
    print(f"{code:<8}{name:<10}{zf:<8.1f}{hs:<8.1f}{reason}")
    codes.append(code)

# 保存候选
with open("candidates.txt", "w") as f:
    for _, row in top.iterrows():
        code = str(row["code"]).zfill(6)
        name = str(row.get("name", ""))
        reason = str(row.get("reason", ""))
        f.write(f"{code}|{name}|{reason}\n")

print(f"\n✅ 已保存 {len(codes)} 只候选到 candidates.txt")
print(f"候选代码: {codes}")
