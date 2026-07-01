"""
交互式 K 线图 - 10 只强势股（近90个交易日）
数据源: mootdx 通达信
输出: 可缩放、悬停查看详情的交互式 HTML 图表

依赖: pip install plotly mootdx pandas
"""
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from mootdx.quotes import Quotes

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

fig = make_subplots(
    rows=5, cols=2,
    specs=[[{"secondary_y": True}, {"secondary_y": True}]] * 5,
    vertical_spacing=0.06,
    horizontal_spacing=0.06,
)

for idx, (code, name, reason) in enumerate(STOCKS):
    row, col = idx // 2 + 1, idx % 2 + 1
    print(f"正在获取 {code} {name} ...")

    try:
        bars = client.bars(symbol=code, category=4, offset=90)
        if bars is None or len(bars) == 0:
            print(f"  ⚠ {code} {name}: 无K线数据")
            continue

        df = pd.DataFrame(bars)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime').sort_index()

        # 计算均线
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()

        # 构建悬停提示文本
        hover_texts = []
        for dt, row_data in df.iterrows():
            dt_str = dt.strftime('%Y-%m-%d')
            hover_texts.append(
                f"<b>{name}</b><br>"
                f"日期: {dt_str}<br>"
                f"开: {row_data['open']:.2f}  "
                f"高: {row_data['high']:.2f}<br>"
                f"低: {row_data['low']:.2f}  "
                f"收: {row_data['close']:.2f}<br>"
                f"量: {row_data.get('vol', 0):.0f}"
            )

        # === K线 ===
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name=name,
            showlegend=False,
            increasing=dict(line=dict(color='#ef4444'), fillcolor='#ef4444'),
            decreasing=dict(line=dict(color='#22c55e'), fillcolor='#22c55e'),
            hovertext=hover_texts,
            hoverinfo='text',
        ), row=row, col=col)

        # === MA5 ===
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MA5'],
            mode='lines', line=dict(width=1.2, color='#f59e0b'),
            name='MA5', showlegend=False, hoverinfo='skip',
        ), row=row, col=col)

        # === MA10 ===
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MA10'],
            mode='lines', line=dict(width=1.2, color='#3b82f6'),
            name='MA10', showlegend=False, hoverinfo='skip',
        ), row=row, col=col)

        # === MA20 ===
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MA20'],
            mode='lines', line=dict(width=1.2, color='#a855f7'),
            name='MA20', showlegend=False, hoverinfo='skip',
        ), row=row, col=col)

        # === 成交量柱状图（secondary_y，显示在下方）===
        vol_colors = []
        for _, r in df.iterrows():
            vol_colors.append('#ef4444' if r['close'] >= r['open'] else '#22c55e')

        fig.add_trace(go.Bar(
            x=df.index, y=df['vol'],
            name='成交量',
            showlegend=False,
            marker=dict(color=vol_colors, opacity=0.35),
            hoverinfo='skip',
        ), row=row, col=col, secondary_y=True)

        # 计算区间涨跌幅
        chg_str = ""
        if len(df) >= 2:
            chg = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100
            sign = '+' if chg >= 0 else ''
            clr = '#ef4444' if chg >= 0 else '#22c55e'
            chg_str = f" <span style='color:{clr}'>区间: {sign}{chg:.1f}%</span>"

        # 每张子图标题
        title_html = (
            f"<b>{name}</b> ({code}){chg_str}<br>"
            f"<sup style='color:#6b7280'>{reason}</sup>"
        )

        # xref: 第一个子图用 'x domain'，其余用 'x2 domain' 等
        xref = 'x domain' if idx == 0 else f'x{idx+1} domain'
        yref = 'y domain' if idx == 0 else f'y{idx+1} domain'
        fig.add_annotation(
            xref=xref, yref=yref,
            x=0.5, y=1.02,
            text=title_html,
            showarrow=False,
            font=dict(size=11),
        )

    except Exception as e:
        print(f"  ✗ {code} {name} 获取失败: {e}")

# === 全局布局 ===
fig.update_layout(
    title=dict(
        text="<b>强势股 · 近90日交互式K线图</b><br>"
             "<sup>数据源：通达信 mootdx  |  悬停查看详情  |  滚轮缩放  |  拖拽平移</sup>",
        font=dict(size=18),
        x=0.5,
    ),
    height=1500,
    hovermode='x unified',
    template='plotly_white',
    margin=dict(t=80, b=30, l=40, r=40),
)

# 隐藏所有子图的 rangeslider，设置成交量 Y 轴范围
for i in range(1, 11):
    r, c = (i-1)//2+1, (i-1)%2+1
    fig.update_xaxes(rangeslider_visible=False, row=r, col=c)
    # 主 Y 轴（价格）
    fig.update_yaxes(title_text="", row=r, col=c, secondary_y=False)
    # 次 Y 轴（成交量）- 占下方约 1/3，且不显示刻度
    fig.update_yaxes(
        title_text="", showticklabels=False,
        row=r, col=c, secondary_y=True,
        rangemode='tozero',
    )

# 在最底部添加图例
fig.add_annotation(
    xref='paper', yref='paper',
    x=0.99, y=0.01,
    text="<span style='color:#f59e0b'>── MA5</span>  "
         "<span style='color:#3b82f6'>── MA10</span>  "
         "<span style='color:#a855f7'>── MA20</span>  "
         "<span style='color:#ef4444'>▊</span><span style='color:#22c55e'>▊</span> 成交量",
    showarrow=False,
    font=dict(size=11),
    bgcolor='rgba(255,255,255,0.8)',
    bordercolor='#ccc',
    borderwidth=1,
    borderpad=4,
)

output_path = os.path.join(OUTPUT_DIR, "强势股K线图_交互式_20260603.html")
fig.write_html(output_path, include_plotlyjs='cdn')
print(f"\n✅ 交互式图表已保存至: {output_path}")
print(f"   用浏览器打开即可交互查看（缩放/平移/悬停详情）")
