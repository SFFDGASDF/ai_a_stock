"""精选超跌反弹 — 长下影+支撑+放量+低RSI"""
import logging; logging.getLogger('tdxpy').setLevel(logging.CRITICAL)
from mootdx.quotes import Quotes
from stockstats import StockDataFrame
import pandas as pd, time, requests

client = Quotes.factory(market='std')
UA = 'Mozilla/5.0'

# 获取股票列表
stocks_sh = client.stocks(market=1)
stocks_sz = client.stocks(market=0)
df_all = pd.concat([stocks_sh, stocks_sz], ignore_index=True)

codes_list = []
for _, s in df_all.iterrows():
    code = str(s.get('code', ''))
    name = str(s.get('name', ''))
    if (len(code)==6 and code[:3] in ('600','601','603','605','000','002','003','300')
        and code[:3]!='301'
        and not name.startswith(('ST','st','*ST','N','C'))):
        codes_list.append(code)

# 行情扫描
print('扫描大跌候选...')
candidates = []
for i in range(0, len(codes_list), 80):
    batch = codes_list[i:i+80]
    try:
        quotes = client.quotes(symbol=batch)
        if quotes is None or len(quotes)==0: continue
        for _, q in quotes.iterrows():
            code = str(q.get('code','')).zfill(6)
            price = float(q.get('price',0) or 0)
            prev = float(q.get('last_close',0) or 0)
            open_p = float(q.get('open',0) or 0)
            high = float(q.get('high',0) or 0)
            low = float(q.get('low',0) or 0)
            amount = float(q.get('amount',0) or 0)
            if price<=0 or prev<=0: continue
            chg = (price/prev-1)*100
            if chg>-2 or chg<-8: continue
            if amount<30000000: continue
            if price<3: continue
            ls = (min(price,open_p)-low)/open_p*100
            amp = (high/low-1)*100
            candidates.append({'code':code,'price':price,'prev':prev,'open':open_p,
                'high':high,'low':low,'chg':chg,'amount':amount,'ls':ls,'amp':amp})
    except: pass
    time.sleep(0.1)

# 按下影排序取60
candidates.sort(key=lambda x: x['ls']*2 - abs(x['chg'])/5, reverse=True)
candidates = candidates[:60]
print(f'候选: {len(candidates)} 只, 深度分析...')

results = []
for c in candidates:
    code = c['code']
    try:
        bars = client.bars(symbol=code, category=4, offset=120)
        if bars is None or len(bars)<30: continue
        df = bars.copy()
        close = df['close'].astype(float)
        vol_s = df['vol'].astype(float)
        cur = float(close.iloc[-1])
        ma5 = float(close.rolling(5).mean().iloc[-1])
        ma10 = float(close.rolling(10).mean().iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma60 = float(close.rolling(60).mean().iloc[-1]) if len(close)>=60 else 0
        v_today = float(vol_s.iloc[-1])
        v_5avg = float(vol_s.iloc[-6:-1].mean())
        vr = v_today/v_5avg if v_5avg>0 else 1
        chg_3d = (cur/float(close.iloc[-4])-1)*100 if len(close)>=4 else 0
        chg_5d = (cur/float(close.iloc[-6])-1)*100 if len(close)>=6 else 0

        stock = StockDataFrame.retype(df)
        try: rsi6 = float(stock['rsi_6'].dropna().iloc[-1])
        except: rsi6=50
        try: rsi14 = float(stock['rsi_14'].dropna().iloc[-1])
        except: rsi14=50
        try: dif=float(stock['macd'].dropna().iloc[-1]); dea=float(stock['macds'].dropna().iloc[-1]); macdh=float(stock['macdh'].dropna().iloc[-1])
        except: dif=dea=macdh=0
        try: kdj_j=float(stock['kdjj'].dropna().iloc[-1])
        except: kdj_j=50
        try:
            boll_u=float(stock['boll_ub'].dropna().iloc[-1]); boll_l=float(stock['boll_lb'].dropna().iloc[-1])
            boll_pos=(cur-boll_l)/(boll_u-boll_l)*100
        except: boll_pos=50

        sup_dist = 99; sup_name = '无'
        for label, ma in [('MA20',ma20),('MA60',ma60),('MA10',ma10)]:
            if ma>0:
                d = (cur/ma-1)*100
                if 0<d<sup_dist: sup_dist=d; sup_name=label

        down_days=0
        for d in range(1,min(10,len(close))):
            if float(close.iloc[-d])<float(close.iloc[-d-1]): down_days+=1
            else: break

        dev = (cur/ma20-1)*100 if ma20>0 else 0

        score = 0
        score += min(30, c['ls']*8)
        score += max(0, 20 - abs(sup_dist)*3) if sup_dist<99 else 0
        if 1.0<=vr<=2.5: score+=15
        elif 0.7<=vr<1.0: score+=8
        if rsi6<30: score+=12
        elif rsi6<40: score+=8
        if dif>dea: score+=8
        if boll_pos<30: score+=8
        elif boll_pos<50: score+=4
        score -= min(5, c['amp']-6) if c['amp']>6 else 0
        if vr<0.3: score-=15
        elif vr<0.5: score-=8
        if dev>20: score-=10
        if down_days>=4: score-=8
        elif down_days>=3: score-=4

        name = ''
        results.append({
            'code':code,'name':name,'price':cur,'chg':c['chg'],
            'ls':c['ls'],'amp':c['amp'],'amount':c['amount'],
            'rsi6':rsi6,'rsi14':rsi14,'dif':dif,'dea':dea,'macdh':macdh,
            'kdj_j':kdj_j,'vr':vr,'chg_3d':chg_3d,'chg_5d':chg_5d,
            'ma5':ma5,'ma10':ma10,'ma20':ma20,'ma60':ma60,
            'boll_pos':boll_pos,'dev':dev,'sup':sup_name,'sup_dist':sup_dist,
            'down_days':down_days,'score':score,
        })
    except: pass
    time.sleep(0.2)

# 补名称
needs = [r for r in results if not r['name']]
if needs:
    try:
        url = 'https://qt.gtimg.cn/q='+','.join(
            ['sh'+r['code'] if r['code'][0]=='6' else 'sz'+r['code'] for r in needs])
        resp = requests.get(url, headers={'User-Agent': UA}, timeout=10)
        text = resp.content.decode('gbk')
        for r in needs:
            prefix = 'sh' if r['code'][0]=='6' else 'sz'
            for line in text.split('\n'):
                if f'v_{prefix}{r["code"]}' in line:
                    parts = line.split('~')
                    if len(parts)>1: r['name']=parts[1]
    except: pass

results.sort(key=lambda x: x['score'], reverse=True)

print()
print('='*80)
print('  🎯 精选超跌反弹 (长下影+支撑+放量+低RSI)')
print('='*80)

for i,r in enumerate(results[:10]):
    name_str = r['name'] or f'({r["code"]})'
    barl = max(0,int(r['score']/5)); bar_chars = '▓'*barl+'░'*(15-barl)
    w=[]
    if r['vr']<0.3: w.append('⚠️无量')
    elif r['vr']<0.5: w.append('⚠️缩量')
    if r['down_days']>=4: w.append(f'🔴连阴{r["down_days"]}天')
    elif r['down_days']>=3: w.append(f'⚠️连阴{r["down_days"]}天')
    if r['dev']>20: w.append('🔴乖离大')
    if r['rsi6']>60: w.append('⚠️RSI偏高')
    tag = '🟢' if r['score']>=55 and not w else ('🟡' if r['score']>=40 else '🔴')
    print(f'\n  #{i+1} {name_str}({r["code"]})  ¥{r["price"]:.2f}  {r["chg"]:+.1f}%  评分{r["score"]}  {tag}')
    print(f'  [{bar_chars}]')
    print(f'  下影:{r["ls"]:.1f}% | 支撑:{r["sup"]}(距{r["sup_dist"]:.1f}%) | BOLL:{r["boll_pos"]:.0f}% | 量比:{r["vr"]:.1f}x')
    print(f'  RSI6:{r["rsi6"]:.0f} KDJ-J:{r["kdj_j"]:.0f} | 连阴:{r["down_days"]}天 | 5日:{r["chg_5d"]:+.1f}%')
    print(f'  MA5:¥{r["ma5"]:.2f} MA10:¥{r["ma10"]:.2f} MA20:¥{r["ma20"]:.2f}')
    macd_tag = '✅多头' if r['dif']>r['dea'] else '⚠️空头'
    risk_str = ('风险:'+' '.join(w)) if w else '✅无风险'
    print(f'  MACD DIF:{r["dif"]:.3f} DEA:{r["dea"]:.3f} {macd_tag} | {risk_str}')

# 安检
print(f'\n{"="*80}')
print(f'  🏁 通过安检 (得分≥50 + vr≥0.4 + 不连阴 + 不乖离)')
print(f'{"="*80}')

good = [r for r in results
        if r['score']>=45
        and r['vr']>=0.4
        and r['down_days']<4
        and r.get('dev',0)<=18]

if not good:
    print('\n  ❌ 无。市场太弱，今天不适合超跌反弹。')
else:
    for r in good[:3]:
        n = r['name'] or r['code']
        print(f'\n  ✅ {n}({r["code"]}) ¥{r["price"]:.2f} 今日{r["chg"]:+.1f}%  评分{r["score"]}')
        print(f'     下影{r["ls"]:.1f}% 支撑{r["sup"]}({r["sup_dist"]:.1f}%)  量比{r["vr"]:.1f}x')
        print(f'     买入: 尾盘 ¥{r["price"]:.2f} | 目标: ¥{r["price"]*1.04:.2f}(+4%)~¥{r["price"]*1.05:.2f}(+5%)')
        print(f'     止损: ¥{r["price"]*0.97:.2f}(-3%) | 仓位: ≤ 15%')
