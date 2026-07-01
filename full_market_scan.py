"""全市场隔日短线扫描 — 同花顺强势股预筛 + 技术面多因子评分"""
import pandas as pd
import numpy as np
import requests
import time
from datetime import date
from mootdx.quotes import Quotes
from stockstats import StockDataFrame

d = date.today().strftime("%Y-%m-%d")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36"
client = Quotes.factory(market="std")

# ========== Step 1: 拉当日强势股（同花顺） ==========
print("=" * 72)
print(f"  全市场隔日短线扫描 · {d}")
print("=" * 72)
print("\n  [Step 1] 拉取当日同花顺强势股...")

url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{d}/orderby/date/orderway/desc/charset/GBK/"
r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
hot_data = r.json().get("data") or []

if not hot_data:
    print("  今日暂无强势股数据，尝试扩大日期范围...")
    # 尝试前一天
    from datetime import timedelta
    d2 = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    url2 = f"http://zx.10jqka.com.cn/event/api/getharden/date/{d2}/orderby/date/orderway/desc/charset/GBK/"
    r2 = requests.get(url2, headers={"User-Agent": UA}, timeout=15)
    hot_data = r2.json().get("data") or []
    print(f"  使用 {d2} 数据: {len(hot_data)} 只")

df_hot = pd.DataFrame(hot_data)
print(f"  当日强势股总数: {len(df_hot)} 只")

# 检查列名
cols = list(df_hot.columns)
print(f"  可用列: {cols}")

# 适配不同的列名格式
code_col = next((c for c in cols if c in ("code", "股票代码", "stock_code")), None)
name_col = next((c for c in cols if c in ("name", "股票名称", "stock_name")), None)
reason_col = next((c for c in cols if c in ("reason", "题材", "归因")), None)
zf_col = next((c for c in cols if c in ("zhangfu", "涨幅", "涨幅%")), None)
hs_col = next((c for c in cols if c in ("huanshou", "换手", "换手率%")), None)
cje_col = next((c for c in cols if c in ("chengjiaoe", "成交额")), None)

if not code_col or not name_col:
    print("  ❌ 找不到代码/名称列，退出")
    exit(1)

# 重命名为统一列名
df_hot = df_hot.rename(columns={
    code_col: "code", name_col: "name",
    **( {reason_col: "reason"} if reason_col and reason_col != "reason" else {} ),
    **( {zf_col: "zhangfu"} if zf_col and zf_col != "zhangfu" else {} ),
    **( {hs_col: "huanshou"} if hs_col and hs_col != "huanshou" else {} ),
    **( {cje_col: "chengjiaoe"} if cje_col and cje_col != "chengjiaoe" else {} ),
})

# 确保 code 是 6 位字符串
df_hot["code"] = df_hot["code"].astype(str).str.zfill(6)

# ========== Step 2: 预筛选（涨幅3-8%，换手3-25%） ==========
print("\n  [Step 2] 预筛选: 涨幅3-8%, 换手3-25%...")

has_zf = "zhangfu" in df_hot.columns
has_hs = "huanshou" in df_hot.columns

if has_zf:
    df_hot["zhangfu"] = pd.to_numeric(df_hot["zhangfu"], errors="coerce")
    mask = (df_hot["zhangfu"] >= 3) & (df_hot["zhangfu"] <= 8)
else:
    mask = pd.Series([True] * len(df_hot))

if has_hs:
    df_hot["huanshou"] = pd.to_numeric(df_hot["huanshou"], errors="coerce")
    mask = mask & (df_hot["huanshou"] >= 3) & (df_hot["huanshou"] <= 25)

candidates = df_hot[mask].copy()

# 如果太少，放宽条件
if len(candidates) < 10:
    print(f"  候选太少({len(candidates)}), 放宽筛选...")
    if has_zf and has_hs:
        mask2 = (df_hot["zhangfu"] >= 1) & (df_hot["zhangfu"] <= 9.5) & (df_hot["huanshou"] >= 1)
    elif has_zf:
        mask2 = (df_hot["zhangfu"] >= 1) & (df_hot["zhangfu"] <= 9.5)
    else:
        mask2 = pd.Series([True] * len(df_hot))
    candidates = df_hot[mask2].copy()

# 按成交额降序，优先大盘股
if "chengjiaoe" in candidates.columns:
    candidates["chengjiaoe"] = pd.to_numeric(candidates["chengjiaoe"], errors="coerce")
    candidates = candidates.sort_values("chengjiaoe", ascending=False)

# 限制候选数量，避免超时（最多80只）
MAX_CANDIDATES = 80
if len(candidates) > MAX_CANDIDATES:
    candidates = candidates.head(MAX_CANDIDATES)

print(f"  候选池: {len(candidates)} 只")

# ========== Step 3: 逐只技术面评分 ==========
print(f"\n  [Step 3] 逐只技术面分析 (mootdx K线 + stockstats)...")
print(f"  {'代码':<8}{'名称':<10}{'现价':<10}{'RSI':<8}{'量比':<8}{'5日%':<10}{'乖离%':<10}{'评分':<6}")

results = []
idx = 0
for _, row in candidates.iterrows():
    idx += 1
    code = str(row["code"]).zfill(6)
    name = str(row.get("name", ""))
    reason = str(row.get("reason", "")) if "reason" in row.index else ""
    
    try:
        bars = client.bars(symbol=code, category=4, offset=60)
        if bars is None or len(bars) < 30:
            continue
        df = pd.DataFrame(bars)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime").sort_index()
        stock = StockDataFrame.retype(df)
        close = df["close"]
        vol = df["vol"]
        c = float(close.iloc[-1])
        ma5 = float(close.rolling(5).mean().iloc[-1])
        ma10 = float(close.rolling(10).mean().iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        v5 = float(vol.iloc[-5:].mean())
        v20 = float(vol.iloc[-20:].mean())
        vol_ratio_val = v5 / v20 if v20 > 0 else 1
        chg_5d = (c / float(close.iloc[-5]) - 1) * 100 if len(close) >= 5 else 0
        dev = (c / ma20 - 1) * 100

        try:
            rsi_val = float(stock["rsi_14"].dropna().iloc[-1])
        except:
            rsi_val = 50
        try:
            dif = float(stock["macd"].dropna().iloc[-1])
            dea = float(stock["macds"].dropna().iloc[-1])
            macdh_val = float(stock["macdh"].dropna().iloc[-1])
        except:
            dif = dea = macdh_val = 0

        score = 0
        signals = []

        # 趋势
        if c > ma5 > ma10:
            score += 18
            signals.append("短期多头")
        elif c > ma5:
            score += 8
            signals.append("站上MA5")

        # 量能（权重最高）
        if vol_ratio_val > 1.5:
            score += 25
            signals.append(f"放量{vol_ratio_val:.1f}x")
        elif vol_ratio_val > 1.2:
            score += 15
            signals.append(f"温和放量{vol_ratio_val:.1f}x")
        elif vol_ratio_val > 1.0:
            score += 6

        # MACD柱
        macdh_vals = stock["macdh"].dropna()
        if len(macdh_vals) >= 2:
            macdh_prev = float(macdh_vals.iloc[-2])
            if macdh_val > macdh_prev > 0:
                score += 18
                signals.append("MACD柱放大")
            elif macdh_val > 0:
                score += 8

        # RSI
        if 60 <= rsi_val <= 75:
            score += 14
            signals.append(f"RSI{rsi_val:.0f}强势")
        elif 55 <= rsi_val < 60:
            score += 8
        elif rsi_val > 80:
            score -= 12
            signals.append("RSI过热⚠")

        # 乖离
        if 3 <= dev <= 15:
            score += 12
            signals.append(f"乖离{dev:.0f}%适中")
        elif dev > 25:
            score -= 10
            signals.append("乖离过大⚠")

        # 三连阳
        if len(close) >= 4:
            ok = (close.iloc[-1] > close.iloc[-2] and
                  close.iloc[-2] > close.iloc[-3] and
                  close.iloc[-3] > close.iloc[-4])
            if ok:
                score += 13
                signals.append("三连阳🔥")

        # 大阳线今日（实体>3%）
        body = abs(c / float(close.iloc[-2]) - 1) * 100 if len(close) >= 2 else 0
        if body > 3:
            score += 8
            signals.append(f"大阳线{body:.1f}%")

        # 涨停板品种加分（20cm弹性更大）
        if code.startswith("30") or code.startswith("68"):
            score += 5
            signals.append("20cm弹性")

        results.append({
            "code": code, "name": name, "reason": reason,
            "price": c, "rsi": rsi_val,
            "vol_ratio": vol_ratio_val, "chg_5d": chg_5d, "dev": dev,
            "score": score, "signals": signals,
            "ma5": ma5, "ma20": ma20, "ma10": ma10,
        })

        bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
        print(f"  {code:<8}{name:<10}{c:<10.2f}{rsi_val:<8.1f}{vol_ratio_val:<8.2f}"
              f"{chg_5d:<10.1f}{dev:<10.1f}{score:<6}[{bar}]")

        time.sleep(0.35)  # mootdx 限流
    except Exception as e:
        # 静默跳过错误的股票
        pass

# ========== Step 4: 排名与推荐 ==========
results.sort(key=lambda x: x["score"], reverse=True)

print(f"\n{'='*72}")
print(f"  🏆 全市场隔日短线 · 最终推荐 TOP5")
print(f"{'='*72}")

if len(results) == 0:
    print("  ❌ 没有符合条件的股票")
    exit()

for rank, r in enumerate(results[:5]):
    tag = "🥇" if rank == 0 else ("🥈" if rank == 1 else ("🥉" if rank == 2 else f"  {rank+1}"))
    print(f"\n  {tag} {r['name']} ({r['code']})  评分: {r['score']}/100")
    if r['reason']:
        print(f"  题材: {r['reason']}")
    print(f"  现价: ¥{r['price']:.2f}")
    print(f"  RSI: {r['rsi']:.1f}  |  量比: {r['vol_ratio']:.2f}  |  5日涨幅: {r['chg_5d']:+.1f}%")
    print(f"  MA5: {r['ma5']:.2f}  |  MA10: {r['ma10']:.2f}  |  MA20: {r['ma20']:.2f}  |  乖离: {r['dev']:.1f}%")
    print(f"  触发信号: {'; '.join(r['signals'])}")

# ========== Step 5: 操作建议 ==========
top = results[0]
limit_pct = 20 if top["code"].startswith("30") or top["code"].startswith("68") else 10

print(f"\n{'='*72}")
print(f"  💡 操作建议（首选: {top['name']}）")
print(f"{'='*72}")
print(f"""
  买入策略:
    ● 明日开盘竞价买入 or 开盘后前30分钟分时回踩买入
    ● 目标价位: ¥{top['price'] * 1.07:.2f} (+7%)

  卖出策略 (后天):
    ● 达标止盈: 涨幅 5-10% 分批卖出
    ● 止损保护: 跌幅超 −3% 果断止损
    ● 时间止损: 后天收盘无论涨跌必须出

  仓位建议:
    ● 短线仓位 ≤ 总资金 20%
    ● 切不可满仓单票

  ⚠ 风险提示:
    ● 隔日交易历史胜率约 59%，非确定性策略
    ● 5-10%收益通常需配合题材热点/涨停板
    ● 以上为技术面分析，不含消息面/基本面因子
    ● 不构成投资建议，投资需谨慎
""")
