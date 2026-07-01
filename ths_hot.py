import requests
import pandas as pd
from datetime import date

d = date.today().strftime("%Y-%m-%d")
url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{d}/orderby/date/orderway/desc/charset/GBK/"
r = requests.get(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36"
}, timeout=10)
data = r.json()
rows = data.get("data") or []
df = pd.DataFrame(rows)

if df.empty:
    print("今天没有强势股数据")
else:
    # 检查实际列名
    print(f"=== 今日强势股 ({d}) 共 {len(df)} 只 ===")
    print(f"列名: {list(df.columns)}\n")
    
    # 找出可用列并显示
    display_cols = []
    name_map = {
        "name": "名称", "code": "代码", "reason": "题材归因",
        "close": "收盘价", "zhangdie": "涨跌额", "zhangfu": "涨幅%",
        "huanshou": "换手率%", "chengjiaoe": "成交额",
        "chengjiaoliang": "成交量", "ddejingliang": "大单净量",
        "market": "市场",
    }
    
    # 先重命名存在的列
    existing_rename = {k: v for k, v in name_map.items() if k in df.columns}
    df = df.rename(columns=existing_rename)
    
    # 选择要显示的列
    wanted = ["代码", "名称", "涨幅%", "换手率%", "成交额", "大单净量", "题材归因"]
    available = [c for c in wanted if c in df.columns]
    
    pd.set_option('display.max_rows', 80)
    pd.set_option('display.max_columns', 20)
    pd.set_option('display.width', 300)
    pd.set_option('display.max_colwidth', 60)
    pd.set_option('display.colheader_justify', 'left')
    
    if available:
        print(df[available].to_string())
    
    # 统计题材
    if "题材归因" in df.columns:
        reasons = df["题材归因"].dropna()
        print(f"\n--- 题材统计 ---")
        all_tags = []
        for r in reasons:
            all_tags.extend([t.strip() for t in str(r).split("+")])
        from collections import Counter
        tag_count = Counter(all_tags)
        print("热门题材 TOP15:")
        for tag, cnt in tag_count.most_common(15):
            print(f"  {tag}: {cnt}只")
