"""
绘制 10 只强势股 K 线图（近90个交易日）
数据源: mootdx 通达信 (TCP，不封IP)
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from mootdx.quotes import Quotes

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

STOCKS = [
    ("600516", "方大炭素", "石墨电极龙头+电池材料+核电石墨"),
    ("688268", "华特气体", "电子特气+氦气+光刻气+国产替代"),
    ("002156", "通富微电", "CPO封装+AMD产业链+存储芯片封测"),
    ("600487", "亨通光电", "多芯光纤+CPO+一季报增长"),
    ("301366", "一博科技", "AI PCB+光模块+英伟达合作+签单增长"),
    ("603236", "移远通信", "卫星通信+物联网模组+人形机器人"),
    ("600688", "上海石化", "T1000级高性能碳纤维+石油化工+央企"),
    ("600121", "郑州煤电", "煤炭+机器人+算力中心+郑州国资"),
    ("002965", "祥鑫科技", "液冷服务器+人形机器人+汽车零部件"),
    ("688655", "迅捷兴", "800G光模块+PCB+定增AI服务器"),
]

OUTPUT_DIR = r"c:\Users\DELL\Desktop\ai_a_stock\charts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

client = Quotes.factory(market='std')

fig, axes = plt.subplots(5, 2, figsize=(22, 28))
fig.suptitle("今日强势股 · 近90日K线图（数据源：通达信 mootdx）", fontsize=18, fontweight='bold', y=0.995)

for idx, (code, name, reason) in enumerate(STOCKS):
    row, col = idx // 2, idx % 2
    ax = axes[row, col]
    
    print(f"正在获取 {code} {name} ...")
    
    # 市场: 0=深圳, 1=上海
    market = 1 if code.startswith("6") else 0
    try:
        bars = client.bars(symbol=code, category=4, offset=90)
        if bars is None or len(bars) == 0:
            ax.text(0.5, 0.5, f"{code} {name}\n无K线数据", transform=ax.transAxes,
                    ha='center', va='center', fontsize=11, color='gray')
            ax.set_title(f"{name} ({code})")
            continue
        
        df = pd.DataFrame(bars)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
        df = df.rename(columns={
            'open': 'Open', 'close': 'Close', 'high': 'High', 'low': 'Low', 'vol': 'Volume'
        })
        
        # 计算均线
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA10'] = df['Close'].rolling(10).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        
        # 在 subplot 的 ax 上绘制
        mpf.plot(df, type='candle', style='charles',
                 mav=(5, 10, 20),
                 volume=False,
                 ylabel='',
                 ax=ax,
                 show_nontrading=False,
                 datetime_format='%m/%d')
        
        # 计算涨跌幅
        if len(df) >= 2:
            first_close = df['Close'].iloc[0]
            last_close = df['Close'].iloc[-1]
            chg = (last_close - first_close) / first_close * 100
            color = 'red' if chg >= 0 else 'green'
        else:
            chg = 0
            color = 'black'
        
        title = f"{name} ({code})  区间涨跌: {chg:+.1f}%"
        ax.set_title(title, fontsize=12, fontweight='bold', color=color)
        ax.set_ylabel('')
        
        # 在右上角加题材标签
        ax.text(0.99, 0.97, reason, transform=ax.transAxes,
                ha='right', va='top', fontsize=8, color='gray',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.8))
        
    except Exception as e:
        ax.text(0.5, 0.5, f"{code} {name}\n错误: {str(e)[:50]}", transform=ax.transAxes,
                ha='center', va='center', fontsize=10, color='red')
        ax.set_title(f"{name} ({code})")
        print(f"  {code} 获取失败: {e}")

plt.tight_layout(rect=[0, 0, 1, 0.99])
output_path = os.path.join(OUTPUT_DIR, "强势股K线图_20260603.png")
fig.savefig(output_path, dpi=150, bbox_inches='tight')
plt.close(fig)
print(f"\n✅ 图表已保存至: {output_path}")
