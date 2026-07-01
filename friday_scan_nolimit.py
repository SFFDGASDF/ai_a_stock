"""周五买入→周一卖出 — 排除涨停板，只扫可买入强势股"""
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

print("=" * 72)
print(f"  周五买→周一卖 · 排除涨停板 · {d}")
print("=" * 72)

# === Step 1: 拉同花顺强势股 ===
print("\n  [1/4] 拉取同花顺强势股...")
url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{d}/orderby/date/orderway/desc/charset/GBK/"
r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
hot_data = r.json().get("data") or []
df_hot = pd.DataFrame(hot_data)
print(f"  全部强势股: {len(df_hot)} 只")

# === Step 2: 用腾讯行情获取实时涨跌幅，排除涨停 ===
print("  [2/4] 腾讯行情批量过滤涨停板...")

codes_all = df_hot["code"].astype(str).str.zfill(6).tolist()
# 分批次查询腾讯行情（每批最多50只）
valid_candidates = []

for batch_start in range(0, len(codes_all), 50):
    batch = codes_all[batch_start:batch_start + 50]
    # 构建腾讯行情请求
    symbols = []
    for c in batch:
        prefix = "sh" if c.startswith("6") else "sz"
        symbols.append(f"{prefix}{c}")
    
    try:
        qt_url = f"https://qt.gtimg.cn/q={','.join(symbols)}"
        resp = requests.get(qt_url, headers={"User-Agent": UA}, timeout=15)
        # 编码可能有问题，尝试多种
        try:
            text = resp.content.decode("gbk")
        except:
            text = resp.content.decode("utf-8", errors="replace")
        
        lines = text.strip().split("\n")
        for line in lines:
            if not line.strip() or "=" not in line:
                continue
            try:
                # 解析: v_sh600516="1~方大炭素~600516~..."
                var_name = line.split("=")[0].strip()
                data_str = line.split('="')[1].rstrip('";\n')
                parts = data_str.split("~")
                
                if len(parts) < 35:
                    continue
                
                name = parts[1]
                price = float(parts[3]) if parts[3] else 0
                prev_close = float(parts[4]) if parts[4] else 0
                chg_pct = float(parts[32]) if parts[32] else 0
                high = float(parts[33]) if parts[33] else 0
                low = float(parts[34]) if parts[34] else 0
                
                # 判断涨停板
                code_from_qt = parts[2]
                is_20cm = code_from_qt.startswith("30") or code_from_qt.startswith("68")
                limit_pct = 20 if is_20cm else 10
                
                # 接近涨停(>9.5%)就算涨停板
                is_limit_up = chg_pct >= (limit_pct - 0.5)
                
                # 排除：涨停板、涨幅<2%（太弱）、跌幅>2%
                if not is_limit_up and 2 <= chg_pct <= 8.5 and price > 0:
                    valid_candidates.append({
                        "code": code_from_qt,
                        "name": name,
                        "price": price,
                        "chg_pct": chg_pct,
                        "prev_close": prev_close,
                        "high": high,
                        "low": low,
                    })
            except:
                continue
        time.sleep(0.3)
    except Exception as e:
        print(f"    批量查询失败: {e}")
        continue

print(f"  非涨停 + 涨幅2-8.5%: {len(valid_candidates)} 只")

if len(valid_candidates) == 0:
    # 放宽条件
    print("  候选太少，放宽至涨幅1-9.5%...")
    for batch_start in range(0, len(codes_all), 50):
        batch = codes_all[batch_start:batch_start + 50]
        symbols = []
        for c in batch:
            prefix = "sh" if c.startswith("6") else "sz"
            symbols.append(f"{prefix}{c}")
        try:
            qt_url = f"https://qt.gtimg.cn/q={','.join(symbols)}"
            resp = requests.get(qt_url, headers={"User-Agent": UA}, timeout=15)
            try:
                text = resp.content.decode("gbk")
            except:
                text = resp.content.decode("utf-8", errors="replace")
            lines = text.strip().split("\n")
            for line in lines:
                if not line.strip() or "=" not in line:
                    continue
                try:
                    var_name = line.split("=")[0].strip()
                    data_str = line.split('="')[1].rstrip('";\n')
                    parts = data_str.split("~")
                    if len(parts) < 35: continue
                    code_from_qt = parts[2]
                    price = float(parts[3]) if parts[3] else 0
                    chg_pct = float(parts[32]) if parts[32] else 0
                    is_20cm = code_from_qt.startswith("30") or code_from_qt.startswith("68")
                    limit_pct = 20 if is_20cm else 10
                    is_limit_up = chg_pct >= (limit_pct - 0.5)
                    if not is_limit_up and 1 <= chg_pct <= 9.5 and price > 0:
                        valid_candidates.append({
                            "code": code_from_qt,
                            "name": parts[1],
                            "price": price,
                            "chg_pct": chg_pct,
                            "prev_close": float(parts[4]) if parts[4] else 0,
                        })
                except: continue
            time.sleep(0.3)
        except: continue
    print(f"  放宽后候选: {len(valid_candidates)} 只")

if len(valid_candidates) == 0:
    print("\n  ❌ 今日没有符合条件的非涨停强势股（全部涨停或涨幅不足）")
    exit()

# 去重
seen = set()
uniq = []
for c in valid_candidates:
    if c["code"] not in seen:
        seen.add(c["code"])
        uniq.append(c)
valid_candidates = uniq

# 限制数量
if len(valid_candidates) > 60:
    valid_candidates = valid_candidates[:60]

print(f"  去重后: {len(valid_candidates)} 只")

# === Step 3: 逐只深度技术面分析 ===
print(f"\n  [3/4] 逐只技术面分析 ({len(valid_candidates)} 只)...")

results = []
for idx, cand in enumerate(valid_candidates):
    code = cand["code"]
    name = cand["name"]
    chg_today = cand["chg_pct"]
    rt_price = cand["price"]
    
    try:
        bars = client.bars(symbol=code, category=4, offset=120)
        if bars is None or len(bars) < 60:
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
        ma60 = float(close.rolling(60).mean().iloc[-1])
        
        v5 = float(vol.iloc[-5:].mean())
        v20 = float(vol.iloc[-20:].mean())
        vol_ratio = v5 / v20 if v20 > 0 else 1
        
        chg_5d = (c / float(close.iloc[-5]) - 1) * 100
        chg_10d = (c / float(close.iloc[-10]) - 1) * 100 if len(close) >= 10 else 0
        dev = (c / ma20 - 1) * 100
        
        try: rsi14 = float(stock["rsi_14"].dropna().iloc[-1])
        except: rsi14 = 50
        try: rsi6 = float(stock["rsi_6"].dropna().iloc[-1])
        except: rsi6 = rsi14
        try:
            dif = float(stock["macd"].dropna().iloc[-1])
            dea = float(stock["macds"].dropna().iloc[-1])
            macdh = float(stock["macdh"].dropna().iloc[-1])
            macdh_prev = float(stock["macdh"].dropna().iloc[-2])
        except: dif=dea=macdh=macdh_prev=0
        try:
            k = float(stock["kdjk"].dropna().iloc[-1])
            j = float(stock["kdjj"].dropna().iloc[-1])
        except: k=j=50
        
        # 均线多头?
        ma_bull = c > ma5 > ma10 > ma20
        ma_strong = c > ma5 > ma10
        
        # === 精密评分 ===
        score = 0
        
        # 均线 (25)
        if ma_bull and ma60 and ma20 > ma60:
            score += 25
        elif ma_bull:
            score += 22
        elif ma_strong:
            score += 15
        elif c > ma5:
            score += 8
        
        # RSI (20)
        if 55 <= rsi14 <= 68:
            score += 20
        elif 50 <= rsi14 < 55:
            score += 15
        elif 68 < rsi14 <= 75:
            score += 12
        elif rsi14 > 75:
            score += 5
        else:
            score += 8
        
        # MACD (15)
        if dif > dea > 0 and macdh > macdh_prev:
            score += 15
        elif dif > dea > 0:
            score += 12
        elif dif > dea:
            score += 8
        elif dif > 0:
            score += 5
        
        # 量能 (15)
        if vol_ratio > 1.5:
            score += 15
        elif vol_ratio > 1.3:
            score += 12
        elif vol_ratio > 1.1:
            score += 8
        elif vol_ratio > 0.9:
            score += 5
        
        # 乖离 (10)
        if 3 <= dev <= 15:
            score += 10
        elif 0 <= dev < 3:
            score += 7
        elif 15 < dev <= 20:
            score += 5
        elif dev > 25:
            score += 1
        
        # 位置分 (5) - 今日涨幅不宜过大
        if 2 <= chg_today <= 5:
            score += 5
        elif 5 < chg_today <= 8.5:
            score += 3
        elif chg_today < 2:
            score += 1
        
        # 风险扣分
        if j > 100:
            score -= 5
        if rsi6 > 80:
            score -= 3
        
        signals = []
        if ma_bull: signals.append("均线完美多头")
        elif ma_strong: signals.append("站上MA5/MA10")
        if dif > dea > 0: signals.append("MACD多头")
        if vol_ratio > 1.3: signals.append(f"放量{vol_ratio:.1f}x")
        if 3 <= dev <= 15: signals.append(f"乖离{dev:.0f}%适中")
        if 55 <= rsi14 <= 68: signals.append(f"RSI{rsi14:.0f}最佳")
        
        results.append({
            "code": code, "name": name, "price": rt_price,
            "chg_today": chg_today, "rsi14": rsi14, "rsi6": rsi6,
            "vol_ratio": vol_ratio, "chg_5d": chg_5d, "chg_10d": chg_10d,
            "dev": dev, "score": max(0, score), "signals": signals,
            "ma5": ma5, "ma20": ma20, "ma60": ma60,
            "dif": dif, "dea": dea, "macdh": macdh,
            "k": k, "j": j, "ma_bull": ma_bull,
        })
        
        time.sleep(0.35)
    except Exception as e:
        pass

results.sort(key=lambda x: x["score"], reverse=True)
print(f"  有效分析: {len(results)} 只")

# === Step 4: 输出 ===
print(f"\n{'='*72}")
print(f"  🏆 可买入强势股 TOP10（非涨停）")
print(f"{'='*72}")
print(f"  {'代码':<10}{'名称':<10}{'现价':<10}{'涨%':<7}{'RSI':<7}{'量比':<7}{'乖离':<7}{'评分':<6}")
print(f"  {'─'*65}")

for rank, r in enumerate(results[:10]):
    bar = "█" * int(r["score"] / 5) + "░" * (20 - int(r["score"] / 5))
    print(f"  {r['code']:<10}{r['name']:<10}{r['price']:<10.2f}{r['chg_today']:<7.1f}"
          f"{r['rsi14']:<7.1f}{r['vol_ratio']:<7.2f}{r['dev']:<7.1f}{r['score']:<6}[{bar}]")
    print(f"    → {', '.join(r['signals'])}  "
          f"DIF={r['dif']:.3f} MACD柱={r['macdh']:.3f} KDJ-J={r['j']:.1f}")

# === 最终推荐 ===
if len(results) == 0:
    print("\n  ❌ 没有符合条件的股票")
    exit()

top = results[0]
print(f"\n{'='*72}")
print(f"  🎯 周五买→周一卖 · 最终推荐")
print(f"{'='*72}")

print(f"""
  首选: {top['name']} ({top['code']})
  现价: ¥{top['price']:.2f}    今日涨幅: {top['chg_today']:+.1f}%
  评分: {top['score']}/100
  信号: {'; '.join(top['signals'])}

  技术面详情:
    RSI(14)={top['rsi14']:.1f}  RSI(6)={top['rsi6']:.1f}
    MACD DIF={top['dif']:.3f}  DEA={top['dea']:.3f}  柱={top['macdh']:.3f}
    KDJ K={top['k']:.1f}  J={top['j']:.1f}
    均线: MA5={top['ma5']:.2f}  MA20={top['ma20']:.2f}  MA60={top['ma60']:.2f}
    量比: {top['vol_ratio']:.2f}x  乖离: {top['dev']:.1f}%
    5日涨幅: {top['chg_5d']:+.1f}%  10日涨幅: {top['chg_10d']:+.1f}%

  买入: 今日尾盘或盘中回踩MA5(¥{top['ma5']:.2f})介入
  目标: ¥{top['price']*1.07:.2f}(+7%) ~ ¥{top['price']*1.10:.2f}(+10%)
  止损: ¥{top['price']*0.97:.2f}(-3%)
  卖出: 周一收盘前必须出清
  仓位: ≤ 总资金 20%
""")

if len(results) >= 2:
    r2 = results[1]
    print(f"  备选: {r2['name']}({r2['code']})  ¥{r2['price']:.2f}  今日{r2['chg_today']:+.1f}%  评分{r2['score']}")
    print(f"  信号: {'; '.join(r2['signals'])}")

print(f"""
  ⚠ 周末持仓风险: 政策/外盘/消息面
  ⚠ 以上为技术面分析，不构成投资建议
""")
