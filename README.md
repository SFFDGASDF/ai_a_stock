# 🐂 AI A-Stock 短线量化分析系统 V4

基于 Python 的 A 股 T+1 隔日交易选股系统。内置**四策略体系** + 统一回测框架 + 全市场扫描 + 市场情绪检测 + 真实RPS + 基本面过滤。

---

## 📦 环境依赖

```bash
pip install pandas numpy stockstats mootdx requests
```

| 库 | 用途 |
|---|---|
| `mootdx` (tdxpy) | 通达信 TCP 行情数据（实时行情 + K线） |
| `stockstats` | 技术指标计算（RSI / MACD / KDJ / BOLL） |
| `pandas` | 数据处理 |
| `requests` | HTTP API（东财/腾讯/同花顺） |

---

## 🗂️ 项目结构

```
ai_a_stock/
├── strategies/                        # V4 策略（核心）
│   ├── momentum_v4.py                 # 动量策略：追今日涨幅3-7%的强势股
│   ├── oversold_v4.py                 # 超跌反弹：抄今日大跌2-8%的反弹
│   ├── volume_price_resonance_v4.py   # 量价共振：放量+主力流入+趋势三确认
│   └── breakout_strategy.py           # 均线突破：放量突破MA20/MA60启动信号
│
├── stock_utils.py                     # 公共模块（行情/指标/换手/资金/情绪/基本面/RPS）
│
├── backtest/
│   └── backtest_framework.py          # 统一回测框架（滚动窗口+胜率+盈亏比+IC分析）
│
├── tools/                             # 辅助工具
│   ├── draw_kline.py                  # K线图生成
│   ├── draw_kline_interactive.py      # 交互式K线图（Plotly）
│   ├── ths_hot.py                     # 同花顺当日强势股列表
│   ├── pick_stock.py                  # 今日强势股筛选
│   └── deep_compare.py                # 候选股深度对比分析
│
├── legacy/                            # V3 策略（参考保留）
│   ├── momentum_v3.py
│   ├── oversold_v3.py
│   ├── enhanced_score.py
│   ├── score_stocks.py
│   └── backtest_score.py
│
├── .claude/skills/a-stock-data/       # Claude Code Skill
├── charts/                            # K线图输出
└── README.md
```

---

## 🚀 快速开始

### 动量策略 V4（追强势股）
```bash
python strategies/momentum_v4.py
```
- 全市场扫描今日涨幅 3-7% 的股票
- 13因子评分：均线排列 + RSI + MACD + 量能 + 真实RPS + 行业动量 + 基本面
- 市场情绪 Gate（炸板率>35% 直接退出）
- 输出 TOP15 + ATR止损 + 最终推荐

### 超跌反弹 V4（抄底）
```bash
python strategies/oversold_v4.py
```
- 全市场扫描今日跌幅 2-8% 的股票
- 11因子评分：超跌深度 + 下影线 + 均线支撑 + RSI超卖 + 低位放量
- 跌停>50家自动退出（恐慌不抄底）

### 量价共振 V4（三维确认）
```bash
python strategies/volume_price_resonance_v4.py
```
- 量价配合 + 主力资金流入 + 趋势向上 三重共振
- 高位放量危险检测（BOLL>85%+量比>1.5）

### 均线突破 V1（启动信号）
```bash
python strategies/breakout_strategy.py
```
- 放量突破 MA20/MA60 的启动信号捕捉
- 9因子评分：突破强度 + 量能确认 + 资金共振 + RPS

### 回测验证
```bash
python backtest/backtest_framework.py
```
- 滚动窗口回测 + 信号vs噪声对比 + 分数段细分 + Spearman秩相关

---

## 🛡️ V4 核心能力

### 市场情绪 Gate（策略启动前检测）
| 指标 | 阈值 | 动作 |
|------|------|------|
| 炸板率 | > 35% | 动量/量价/突破 直接退出 |
| 跌停家数 | > 50 | 超跌策略退出 |
| 市场温度 | < 25 | 动量策略退出 |
| 涨停家数 | < 20 | 动量策略警告 |

### 基本面过滤（全策略通用）
| 条件 | 动作 |
|------|------|
| PE < 0 或 PE > 200 | 排除 |
| PB > 10 | 排除 |
| 市值 < 20亿 / < 30亿 | 排除 |

### 真实 RPS
- 基于全市场20日涨幅排名百分位
- RPS ≥ 85: +8分 | RPS < 30: -6分

### ATR 动态止损
- 止损距离 = 1.5 × ATR14，限幅 2%-5%

### 安全门
各策略最终推荐前通过多重安全检查（量比/RSI/乖离/连涨/连阴/上影线/RPS），不通过则拒绝推荐。

---

## 📊 V4 策略对比

| 策略 | 选股逻辑 | 评分因子 | 适合行情 |
|------|---------|---------|---------|
| 动量 V4 | 涨幅3-7%强势追涨 | 13因子 | 强势/偏强 |
| 超跌 V4 | 跌幅2-8%抄底反弹 | 11因子 | 震荡/偏弱 |
| 量价共振 V4 | 放量+主力流+趋势 | 10因子 | 偏强/震荡 |
| 均线突破 V1 | 突破MA20/MA60+放量 | 9因子 | 偏强 |

---

## 📝 数据源

| 数据 | 来源 |
|------|------|
| 实时行情 + K线 | 通达信（mootdx TCP） |
| 换手率 + 大单净量 + 量比 | 东方财富 push2his API |
| PE/PB/市值 | 东方财富 push2his API |
| 市场情绪（涨停/炸板） | 东方财富 clist API |
| 行业板块排名 | 东方财富 push2 API |
| 股票名称 | 腾讯行情 API |
| 强势股列表 | 同花顺接口 |

---

## ⚠️ 免责声明

- 本工具仅供技术学习与研究参考，**不构成任何投资建议**
- 股票投资有风险，入市需谨慎
- 历史回测数据不代表未来表现
- 策略基于纯技术面分析，不含消息面/政策面因子
- 使用者需自行承担交易风险

---

## 📋 更新日志

### V4.0 — 全面升级
- 新增市场情绪 Gate（涨停/跌停/炸板率/市场温度）
- 新增真实 RPS（全市场排名百分位）
- 新增基本面过滤（PE/PB/市值）
- 新增行业动量排名
- 新增均线突破策略
- 新增统一回测框架
- 修复 get_extra_data_batch API（多页拉取+日缓存）
- 所有策略升级多因子评分体系
- 项目结构重组（strategies/core/backtest/tools/legacy）

### V3.0 — 策略升级
- 动量策略 V3 + 超跌策略 V3 + 量价共振策略
- stock_utils.py 公共模块（换手率/资金流向/技术指标/量价背离/ATR止损）
- 大盘环境检测（涨跌比统计）

### V2.0 — 安全版
- 安全惩罚系统 + 风险标签 + 安全门机制

### V1.0 — 初始版本
- 动量策略 + 超跌反弹 + 多因子评分 + K线可视化
