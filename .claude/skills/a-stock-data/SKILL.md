---
name: a-stock-data
description: A股全栈数据工具包 — 覆盖行情(mootdx+腾讯+百度K线)、研报(东财+同花顺+iwencai)、信号(同花顺热点+北向+龙虎榜+解禁+行业)、资金面(融资融券+大宗交易+股东户数+分红+资金流分钟级+资金流120日)、新闻(东财个股+全球资讯)、基础数据(mootdx财务/F10+东财+新浪三表)、公告(巨潮)、推荐与预测(多因子评分+技术指标RSI/MACD/BOLL/KDJ+趋势预测+智能选股)八层数据源，内嵌全部调用代码，自包含零依赖外部文件。优先用通达信(mootdx)/腾讯(不封IP)，东财接口已内置限流防封。适用于个股估值、研报检索、题材归因、龙虎榜跟踪、解禁预警、行业轮动、融资融券跟踪、筹码分析、产业链调研、批量筛选、智能推荐、趋势预测等场景。
origin: custom
version: 3.3.0
---

> 📦 项目主页：https://github.com/simonlin1212/a-stock-data — 更新、反馈、支持作者
> 
> 作者：Simon 林 · 抖音「Simon林」· 公众号「硅基世纪」

# A股全栈数据工具包 V3.3.0

八层数据架构，29+ 个端点实测可用（2026-06 验证；财联社快讯已下线，详见 §5.2），覆盖主板/中小板/科创板/ST。

> **V3.3（推荐与预测）：** 新增 Layer 8「推荐与预测层」—— 多因子智能评分系统（技术面40%+资金面30%+信号面20%+基本面10%），支持技术指标分析（RSI/MACD/BOLL/KDJ/均线交叉）、量价关系研判、短期/中期/长期趋势预测、批量选股推荐排名。全部基于 stockstats + mootdx，零额外依赖。

> **V3.2.1（Bug 修复）：** 修复两个内嵌函数的解析逻辑（预先存在，非 V3.2 引入）——
> - **§5.1 东财个股新闻**：东财实际返回里 `result.cmsArticleWebOld` 直接就是文章列表，旧写法对 list 调 `.get("list")` 触发 AttributeError / 返回空 → 改为遍历 `cmsArticleWebOld` 列表本身。
> - **§6.4 新浪财报三表**：新浪实际结构是 `result.data.report_list`（按报告期为键的 dict，每期 `data` 才是行项列表），旧写法取 `result.data.{lrb}` 永久返回空 → 改为遍历 `report_list` 期次、从每期 `data` 按 `item_title` 提取。
> - 两函数均用茅台 600519 公开 API（零 key）实测返回非空、字段正确。
>
> **V3.2（防封 + 失效修复）：**
> - **数据源优先级 + 东财防封**：明确「通达信(mootdx)/腾讯不封IP 优先用，东财仅用于其独有数据」原则；新增统一节流入口 `em_get()`，所有东财接口内置串行限流（间隔≥1s+随机抖动）+ 会话复用，AI 抄代码即自带防封。详见「数据源优先级 & 东财防封」章节。
> - **财联社快讯下线（#14）**：`cls.cn` 旧 API 全面 404，标注弃用并改用东财全球资讯。
>
> **V3.1 修复：** 替换 4 个失效接口（百度 PAE 资金流→东财 push2、大宗交易 RPT 报表名更新、机构席位改用 BUY/SELL 明细筛选）+ 修复东财全球资讯 req_trace 参数 + 修复巨潮公告 orgId 格式。
>
> **V3.0 Breaking Change**：彻底移除 akshare 依赖，所有数据源改为直连 HTTP API（零第三方数据依赖，仅 mootdx 保留 TCP）。

**使用方式：** 将本文件放入 `~/.claude/skills/a-stock-data/SKILL.md`，Claude Code 会自动识别并在 A 股相关对话中激活。

```
行情层（实时，不封IP）
├── mootdx        → K线 + 五档盘口 + 逐笔成交 (TCP 7709)
├── 腾讯财经 API   → PE/PB/市值/换手率/涨跌停/指数/ETF (HTTP)
└── 百度股市通     → K线带MA5/10/20 (V3.0 新增，HTTP)

研报层
├── 东财 reportapi → 研报列表 + PDF下载 + 评级 + 三年EPS
├── 同花顺 THS     → 一致预期EPS (直连 basic.10jqka.com.cn)
└── iwencai        → NL语义搜索研报 (唯一能力，需X-Claw)

信号层
├── 同花顺热点     → 当日强势股 + 题材归因 reason tags (零鉴权 73ms)
├── 同花顺北向     → hgt/sgt 分钟资金流向 + 本地自缓存历史
├── 百度股市通     → 概念板块归属 (HTTP)
├── 东财 push2     → 个股资金流向 分钟级 (V3.1 替换百度PAE)
├── 龙虎榜席位     → 上榜记录 + 买卖席位 TOP5 + 机构动向 (datacenter-web)
├── 全市场龙虎榜   → 每日全市场上榜股票 + 净买额排名 (datacenter-web)
├── 限售解禁日历   → 历史解禁 + 未来90天待解禁 (datacenter-web)
└── 行业板块排名   → 东财行业涨跌/上涨下跌家数 (V3.0 替换同花顺)

资金面 / 筹码层
├── 融资融券明细   → 日级融资余额/买入/偿还 + 融券 (datacenter-web)
├── 大宗交易       → 成交价/量 + 买卖方营业部 (datacenter-web)
├── 股东户数变化   → 季度股东户数 + 环比变化 (datacenter-web)
├── 分红送转       → 历史每股派息/送股/转增 (datacenter-web)
└── 个股资金流120日 → 主力/大单/中单/小单 日级净流入 (push2his)

新闻层
├── 东财个股新闻   → 个股相关新闻 (search-api-web JSONP)
├── 财联社快讯     → ⚠️ 已下线 (cls.cn 迁 Next.js，旧API 404)
└── 东财全球资讯   → 7×24 财经快讯 (np-weblist，财联社替代)

基础数据层
├── mootdx finance → 季报快照 (37字段, EPS/ROE/净利)
├── mootdx F10     → 公司资料 (9大类文本)
├── 东财个股信息   → 行业/总股本/流通股/市值/上市日期 (push2)
└── 新浪财报三表   → 资产负债表/利润表/现金流量表 (quotes.sina.cn)

公告层
├── 巨潮 cninfo    → 公告全文检索+下载 (cninfo.com.cn)
└── mootdx F10     → 最新公告摘要

推荐与预测层（V3.3 新增）
├── 技术面评分     → RSI/MACD/BOLL/KDJ/均线 (stockstats + mootdx)
├── 资金面评分     → 主力净流入/北向加仓/龙虎榜/融资变化
├── 信号面评分     → 强势股归因/题材热度/行业排名
├── 基本面评分     → PE消化/PEG/一致预期增速
├── 综合推荐       → 加权多因子评分 → 买入/观望/回避
└── 趋势预测       → 短/中/长期方向 + 均线交叉 + 量价配合 + 背离
```

## 数据源优先级 & 东财防封（重要，先读）

### 优先级原则：能用通达信/腾讯，就别用东财

| 优先级 | 数据源 | 协议 | 封 IP 风险 | 覆盖 |
|--------|--------|------|-----------|------|
| **1（首选）** | **mootdx（通达信）** | TCP 7709 二进制 | **不封 IP** | K线、五档盘口、逐笔成交、财务快照、F10 |
| **2** | **腾讯财经** | HTTP GBK | **不封 IP** | 实时价、PE/PB/市值/换手率/涨跌停、指数、ETF |
| **3** | 新浪 / 巨潮 / 同花顺 | HTTP | 低 | 财报三表、公告、一致预期/热点 |
| **4（仅独有数据才用）** | **东财 eastmoney** | HTTP | **有风控，会封 IP** | 见下 |

**凡是行情 / K线 / 实时价 / 市值 / 财务三表能从 mootdx 或腾讯拿到的，一律走它们**——TCP 协议和腾讯接口实测不封 IP，可放心高频调用。

### 东财只用于它「独有、别处拿不到」的数据

下列数据**只有东财有**，通达信/腾讯/新浪都没有，必须用东财（但要限流）：

> 龙虎榜席位 · 全市场龙虎榜 · 限售解禁日历 · 融资融券 · 大宗交易 · 股东户数 · 分红送转 · 个股资金流向（分钟/日级）· 行业板块排名 · 研报列表/PDF · 个股新闻 · 全球资讯

### 东财风控阈值（社区实测，2026-05）

| 行为 | 触发封禁的阈值 | 风险 |
|------|---------------|------|
| 每秒请求数 | > 5 次/秒 | 高 |
| 单 IP 并发连接 | ≥ 10 | 高 |
| 1 分钟请求总数 | ≥ 200 次 | 中高 |
| 5 分钟请求总数 | ≥ 300 次 | 触发封禁 |
| User-Agent | 空 UA / 无浏览器特征 | 中 |

被封表现：连续请求后 `403` / `429` / 连接超时 / 返回空数据。临时封禁通常几分钟到几小时。

### 防封铁律（调用东财时必须遵守）

1. **串行，不并发**——绝不对东财开多线程/协程并发请求
2. **每次间隔 ≥ 1 秒 + 随机抖动**（QPS ≤ 2），批量筛选时调大到 1.5~2 秒
3. **复用 HTTP 会话**（Keep-Alive），不要每次新建连接
4. **带正常 UA + Referer**（本 SKILL 各端点已配好）
5. **批量场景每只股票之间 sleep**——AI 跑批量循环（如筛选 100 只股逐个拉龙虎榜/资金流）是被封的头号元凶

### 已内置限流：所有东财请求走 `em_get()`

本 SKILL 提供统一的节流入口 `em_get()`（定义见下方「东财数据中心统一查询（共用 helper）」），它自动做到：串行限流（最小间隔 `EM_MIN_INTERVAL=1.0s` + 随机抖动）+ 复用 `EM_SESSION`（Keep-Alive）+ 默认 UA。**所有 `eastmoney.com` 端点的代码块都已改用 `em_get` 而非裸 `requests.get`**，AI 直接抄代码即自带防封。批量任务把 `EM_MIN_INTERVAL` 调大即可进一步降速。

> 注：`em_get` / `EM_SESSION` / `EM_MIN_INTERVAL` 是所有东财代码块共用的前置定义，使用任一东财端点前需先执行「共用 helper」代码块。

---

## When to Activate

- 用户要查 A 股个股估值（一致预期 / PE / PEG / PE消化）
- 用户要拉实时行情（价格 / 五档盘口 / K线 / 涨跌停价）
- 用户要搜研报（按主题 / 按标的 / 按行业 / 下载PDF）
- 用户要看**当日强势股 / 题材归因 / 概念热点**
- 用户要看**北向资金动向**（沪股通/深股通分钟流向）
- 用户要看**概念板块归属**（行业/概念/地域）
- 用户要看**个股资金流向**（主力/散户/超大单/大单分钟级）
- 用户要看**龙虎榜席位**（营业部 + 机构买卖）
- 用户要看**全市场龙虎榜**（当日所有上榜股票 + 净买额排名）
- 用户要看**限售解禁日历**（历史解禁 + 未来待解禁）
- 用户要做**行业横向对比**（涨跌排名 / 资金流入 / 领涨股）
- 用户要看**融资融券 / 两融数据**（融资余额 + 融券余额）
- 用户要看**大宗交易**（成交价/量 + 买卖方营业部）
- 用户要看**股东户数变化**（筹码集中度）
- 用户要看**分红送转历史**（每股派息 + 送股 + 转增）
- 用户要看**指数/ETF行情**（上证指数 / 沪深300 / 创业板指 / ETF）
- 用户要看新闻资讯（个股新闻 / 财联社快讯 / 全球资讯）
- 用户要查公告（巨潮公告全文）
- 用户要做产业链调研 / 批量横向对比
- **用户要股票推荐/智能选股（多因子评分 / 技术面筛选 / 资金面筛选）**
- **用户要趋势预测（短期/中期/长期方向 / 均线交叉 / 量价配合 / RSI/MACD/BOLL/KDJ）**
- **用户要技术分析（金叉死叉 / 超买超卖 / 底背离顶背离 / 布林带突破）**
- **用户要评分排名（综合评分排序 / 按行业筛选 / 按题材筛选）**
- 关键词：估值、一致预期、机构预测、市盈率、PEG、市值、研报、产业链、行业研究、K线、盘口、公告、新闻、**强势股、题材、热点、概念归因、北向资金、沪股通、深股通、概念板块、资金流向、主力、龙虎榜、席位、营业部、全市场龙虎榜、净买入、解禁、限售、行业对比、行业轮动、融资融券、两融、大宗交易、股东户数、筹码集中、分红、派息、送股、指数、ETF**、**推荐、预测、选股、评分、技术指标、RSI、MACD、BOLL、布林带、KDJ、金叉、死叉、超买、超卖、背离、趋势、多头、空头、突破、回踩**

---

## Prerequisites

```bash
pip install mootdx requests pandas stockstats
```

| 依赖 | 版本要求 | 用途 |
|------|---------|------|
| mootdx | >= 0.10 | TCP行情+财务+F10（唯一非HTTP依赖） |
| requests | any | 所有HTTP API直连 |
| pandas | any | 数据处理+HTML表格解析 |
| stockstats | any | 技术指标计算（RSI/MACD/BOLL等） |

> **V3.0 架构：** 除 mootdx（TCP 二进制协议）外，所有数据源均为直连 HTTP API，零第三方数据封装依赖。每个端点的底层 URL/参数完全暴露，方便调试和定制。

### iwencai API Key（仅语义搜索需要）

```bash
# 环境变量方式
export IWENCAI_API_KEY="your_key_here"
export IWENCAI_BASE_URL="https://openapi.iwencai.com"

# 申请地址: https://www.iwencai.com/skillhub
# 注册后安装 SkillHub CLI，再安装 report-search 技能即可获得 Key
```

其他数据源（mootdx / 腾讯 / 东财 / 同花顺 / 百度股市通 / 新浪 / 巨潮）全部免费，无需 key。

### 市场前缀规则（全局通用）

```python
def get_prefix(code: str) -> str:
    """6位代码 → 市场前缀"""
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith("8"):
        return "bj"
    else:
        return "sz"
```

### Ticker 格式归一化

所有接口统一支持多种输入格式，内部归一化为纯 6 位数字：

| 输入 | 归一化结果 |
|------|-----------|
| `688017` | `688017` |
| `SH688017` / `sh688017` | `688017` |
| `688017.SH` / `688017.sh` | `688017` |
| `SZ000001` | `000001` |
| `BJ832000` | `832000` |

### 东财数据中心统一查询（共用 helper）

龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用同一 base URL：

```python
import time
import random
import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# ── 东财防封：全局节流 + 会话复用 ────────────────────────────────────
# 东财系 HTTP 接口（push2 / datacenter / reportapi / search / np-weblist）有风控：
#   每秒 >5 次 / 单 IP 并发 ≥10 / 1 分钟 ≥200 次  →  临时封 IP。
# 所有 eastmoney.com 请求一律走 em_get()：串行限流（最小间隔 + 随机抖动）+ 复用
# Keep-Alive 会话，批量调用时自动降速，避免被封。详见「数据源优先级 & 东财防封」章节。
EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_MIN_INTERVAL = 1.0          # 两次东财请求最小间隔(秒)；批量筛选建议调大到 1.5~2
_em_last_call = [0.0]          # 模块级上次请求时间戳

def em_get(url: str, params: dict | None = None, headers: dict | None = None,
           timeout: int = 15, **kwargs):
    """东财统一请求入口：自动节流 + 复用 session + 默认 UA。
    所有 eastmoney.com 接口都应通过它请求，避免高频被封 IP。"""
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
    finally:
        _em_last_call[0] = time.time()

def eastmoney_datacenter(report_name: str, columns: str = "ALL",
                          filter_str: str = "", page_size: int = 50,
                          sort_columns: str = "", sort_types: str = "-1") -> list[dict]:
    """东财数据中心统一查询 — 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用（已内置限流）"""
    params = {
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    r = em_get(DATACENTER_URL, params=params, timeout=15)
    d = r.json()
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []
```

---

## Layer 1: 行情层（实时，不封IP）

### 1.1 mootdx — K线 + 五档盘口 + 逐笔成交

TCP 二进制协议，连通达信服务器(7709)，无需注册，不封IP。

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market='std')

# === K线数据 ===
# market: 0=深圳, 1=上海
# category: 4=日线, 5=周线, 6=月线, 7=1分钟, 8=5分钟, 9=15分钟, 10=30分钟, 11=60分钟
klines = client.bars(symbol='688017', category=4, offset=10)
# 返回: open, close, high, low, vol, amount, datetime

# === 实时报价 ===
quotes = client.quotes(symbol=['688017', '300476'])
# 返回 46 个字段:
#   price(现价), open, high, low, last_close(昨收)
#   bid1~bid5, ask1~ask5, bid_vol1~bid_vol5, ask_vol1~ask_vol5
#   vol(成交量), amount(成交额), servertime

# === 逐笔成交（非交易时间返回空）===
trades = client.transaction(symbol='688017', date='20260502')
# 返回: time, price, vol, num, buyorsell(0买/1卖/2中性)
```

**mootdx 不提供 PE / PB / 市值 / 换手率 / 涨跌停价** — 这些走腾讯财经。

### 1.2 腾讯财经 API — PE/PB/市值/换手率/涨跌停/指数/ETF

HTTP GET，GBK 编码，`~` 分隔 88 个字段，不封IP。

```python
import urllib.request

def tencent_quote(codes: list[str]) -> dict[str, dict]:
    """
    批量拉取腾讯财经实时行情。
    codes: ["688017", "300476", "002463"]
    也支持指数: ["000001", "000300", "399006"]
    也支持ETF: ["510050", "510300"]
    返回: {code: {name, price, pe_ttm, pb, mcap, ...}}
    """
    prefixed = []
    for c in codes:
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name":         vals[1],
            "price":        float(vals[3]) if vals[3] else 0,
            "last_close":   float(vals[4]) if vals[4] else 0,
            "open":         float(vals[5]) if vals[5] else 0,
            "change_amt":   float(vals[31]) if vals[31] else 0,
            "change_pct":   float(vals[32]) if vals[32] else 0,
            "high":         float(vals[33]) if vals[33] else 0,
            "low":          float(vals[34]) if vals[34] else 0,
            "amount_wan":   float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm":       float(vals[39]) if vals[39] else 0,
            "amplitude_pct":float(vals[43]) if vals[43] else 0,
            "mcap_yi":      float(vals[44]) if vals[44] else 0,
            "float_mcap_yi":float(vals[45]) if vals[45] else 0,
            "pb":           float(vals[46]) if vals[46] else 0,
            "limit_up":     float(vals[47]) if vals[47] else 0,
            "limit_down":   float(vals[48]) if vals[48] else 0,
            "vol_ratio":    float(vals[49]) if vals[49] else 0,
            "pe_static":    float(vals[52]) if vals[52] else 0,
        }
    return result

# 用法: 个股
quotes = tencent_quote(["688017", "300476", "002463"])
for code, q in quotes.items():
    print(f"{q['name']}({code}): {q['price']}元 PE={q['pe_ttm']} PB={q['pb']} 市值={q['mcap_yi']}亿")

# 用法: 指数 — sh000001=上证指数, sh000300=沪深300, sz399006=创业板指
index_quotes = tencent_quote(["000001", "000300", "399006"])

# 用法: ETF — sh510050=上证50ETF, sh510300=沪深300ETF
etf_quotes = tencent_quote(["510050", "510300"])
```

#### 腾讯财经字段索引速查（实测校准 2026-05-03）

| 索引 | 含义 | 示例 |
|------|------|------|
| 1 | 名称 | 绿的谐波 |
| 3 | 当前价 | 224.12 |
| 4 | 昨收 | 215.01 |
| 5 | 今开 | 214.10 |
| 9-18 | 买一~买五(价+量) | |
| 19-28 | 卖一~卖五(价+量) | |
| 31 | 涨跌额 | 9.11 |
| 32 | 涨跌幅% | 4.24 |
| 33 | 最高 | 229.62 |
| 34 | 最低 | 214.10 |
| 37 | 成交额(万) | 187040 |
| 38 | 换手率% | 4.55 |
| **39** | **PE(TTM)** | 300.45 |
| **43** | **振幅%（不是PB！）** | 7.22 |
| **44** | **总市值(亿)** | 410.88 |
| **45** | **流通市值(亿)** | 410.88 |
| **46** | **PB(市净率)** | 11.51 |
| **47** | **涨停价** | 258.01 |
| **48** | **跌停价** | 172.01 |
| 49 | 量比 | 1.20 |
| **52** | **PE(静)** | 314.76 |

> **踩坑提醒：** 网上很多教程把索引 43 写成 PB，实测是振幅%。PB 在索引 46。

### 1.3 百度股市通 K线 — 带MA5/MA10/MA20（V3.0 新增）

**核心价值：** 返回时自带均线数据，无需本地计算。

```python
import requests

def baidu_kline_with_ma(code: str, start_time: str = "") -> dict:
    """百度股市通K线 — 独有能力: 返回时自带 ma5/ma10/ma20 均价"""
    url = "https://finance.pae.baidu.com/selfselect/getstockquotation"
    params = {
        "all": "1", "isIndex": "false", "isBk": "false", "isBlock": "false",
        "isFutures": "false", "isStock": "true", "newFormat": "1",
        "group": "quotation_kline_ab", "finClientType": "pc",
        "code": code, "start_time": start_time, "ktype": "1",
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/vnd.finance-web.v1+json",
        "Origin": "https://gushitong.baidu.com",
        "Referer": "https://gushitong.baidu.com/",
    }
    r = requests.get(url, params=params, headers=headers, timeout=10)
    d = r.json()
    result = d.get("Result", {})
    md = result.get("newMarketData", {})
    keys = md.get("keys", [])  # includes: ma5avgprice, ma10avgprice, ma20avgprice
    rows = md.get("marketData", "").split(";")
    return {"keys": keys, "rows": rows}

# 用法
data = baidu_kline_with_ma("600519")
print("字段:", data["keys"][:10])
print("最近5根K线:", data["rows"][-5:])
# keys 包含: time, open, close, high, low, volume, amount, ma5avgprice, ma10avgprice, ma20avgprice 等
```

---

## Layer 2: 研报层

### 2.1 东财研报 API — 研报列表 + PDF下载（主力）

A级接口（公开JSON API），reportapi.eastmoney.com，免费无key。

```python
import requests
import re
import time
from pathlib import Path

REPORT_API = "https://reportapi.eastmoney.com/report/list"
PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def eastmoney_reports(code: str, max_pages: int = 5) -> list[dict]:
    """拉取指定股票的研报列表"""
    all_records = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*", "pageSize": "100", "industry": "*",
            "rating": "*", "ratingChange": "*",
            "beginTime": "2000-01-01", "endTime": "2030-01-01",
            "pageNo": str(page), "fields": "", "qType": "0",
            "orgCode": "", "code": code, "rcode": "",
            "p": str(page), "pageNum": str(page), "pageNumber": str(page),
        }
        r = em_get(REPORT_API, params=params,
                   headers={"Referer": "https://data.eastmoney.com/"}, timeout=30)  # 已内置限流
        d = r.json()
        rows = d.get("data") or []
        if not rows:
            break
        all_records.extend(rows)
        if page >= (d.get("TotalPage", 1) or 1):
            break
    return all_records

def download_pdf(record: dict, target_dir: str = "./reports") -> str | None:
    """下载单份研报PDF，返回保存路径或None"""
    info_code = record.get("infoCode", "")
    if not info_code:
        return None
    date = (record.get("publishDate") or "")[:10]
    org = record.get("orgSName") or "未知"
    title = re.sub(r'[\\/:*?"<>|]', "_", record.get("title", ""))[:80]
    fname = f"{date}_{org}_{title}.pdf"
    target = Path(target_dir) / fname
    if target.exists():
        return str(target)
    url = PDF_TPL.format(info_code=info_code)
    r = em_get(url, headers={"Referer": "https://data.eastmoney.com/"}, timeout=60)
    if r.status_code == 200 and len(r.content) >= 1024:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(r.content)
        return str(target)
    return None

# 用法
reports = eastmoney_reports("688017")
print(f"共 {len(reports)} 篇研报")
for r in reports[:5]:
    print(f"  {r.get('publishDate','')[:10]} | {r.get('orgSName')} | {r.get('title','')[:60]}")
```

#### 研报 record 关键字段

| 字段 | 含义 |
|------|------|
| title | 研报标题 |
| publishDate | 发布日期 |
| orgSName | 机构简称 |
| infoCode | 用于拼 PDF URL |
| predictThisYearEps | 今年EPS预测 |
| predictNextYearEps | 明年EPS预测 |
| predictNextTwoYearEps | 后年EPS预测 |
| emRatingName | 评级(买入/增持/...) |
| indvInduName | 行业分类 |

### 2.2 同花顺一致预期EPS（直连 basic.10jqka.com.cn）

```python
import requests
import pandas as pd
from io import StringIO

def ths_eps_forecast(code: str) -> pd.DataFrame:
    """
    同花顺机构一致预期EPS。
    直连 basic.10jqka.com.cn，解析HTML表格。
    返回 DataFrame: 年度, 预测机构数, 最小值, 均值, 最大值
    "均值" = 机构一致预期EPS
    """
    url = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://basic.10jqka.com.cn/",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.encoding = "gbk"
    dfs = pd.read_html(StringIO(r.text))
    # 找含"每股收益"的表格
    for df in dfs:
        cols = [str(c) for c in df.columns]
        if any("每股收益" in c or "均值" in c for c in cols):
            return df
    # fallback: 返回第一个表
    return dfs[0] if dfs else pd.DataFrame()

# 用法
df = ths_eps_forecast("688017")
print(df)
# "预测机构数" < 3 的要谨慎
```

### 2.3 iwencai — NL语义搜索研报（唯一能力）

需要 API Key + X-Claw Headers（SkillHub 2.0 强制要求）。

```python
import os
import json
import secrets
import requests

IWENCAI_BASE = os.environ.get("IWENCAI_BASE_URL", "https://openapi.iwencai.com")
IWENCAI_KEY = os.environ.get("IWENCAI_API_KEY", "")

def _claw_headers(call_type: str = "normal") -> dict:
    """SkillHub 2.0 必须的 X-Claw 鉴权头"""
    return {
        "X-Claw-Call-Type": call_type,
        "X-Claw-Skill-Id": "report-search",
        "X-Claw-Skill-Version": "2.0.0",
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": secrets.token_hex(32),
    }

def iwencai_search(query: str, channel: str = "report", size: int = 50) -> list[dict]:
    """
    iwencai 语义搜索。
    channel: "report"(研报) / "announcement"(公告) / "news"(新闻)
    size: 默认10, 实测可调到50（隐藏参数）
    """
    headers = {
        "Authorization": f"Bearer {IWENCAI_KEY}",
        "Content-Type": "application/json",
        **_claw_headers(),
    }
    payload = {
        "channels": [channel],
        "app_id": "AIME_SKILL",
        "query": query,
        "size": size,
    }
    r = requests.post(
        f"{IWENCAI_BASE}/v1/comprehensive/search",
        json=payload, headers=headers, timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"iwencai HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("status_code", 0) != 0:
        raise RuntimeError(f"iwencai error: {data.get('status_msg', '')}")
    return data.get("data") or []

def iwencai_query(query: str, page: int = 1, limit: int = 50) -> list[dict]:
    """
    iwencai NL数据查询（结构化字段）。
    例: "贵州茅台 ROE" → DataFrame-like rows
    """
    headers = {
        "Authorization": f"Bearer {IWENCAI_KEY}",
        "Content-Type": "application/json",
        **_claw_headers(),
    }
    payload = {
        "query": query,
        "page": str(page),
        "limit": str(limit),
        "is_cache": "1",
        "expand_index": "true",
    }
    r = requests.post(
        f"{IWENCAI_BASE}/v1/query2data",
        json=payload, headers=headers, timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"iwencai HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("status_code", 0) != 0:
        raise RuntimeError(f"iwencai error: {data.get('status_msg', '')}")
    return data.get("datas") or []

def dedup_articles(articles: list[dict]) -> list[dict]:
    """同一uid仅保留score最高的段落"""
    best = {}
    for a in articles:
        uid = a.get("uid", "") or f"{a.get('title','')}|{a.get('publish_date','')}"
        score = float(a.get("score", 0))
        if uid not in best or score > float(best[uid].get("score", 0)):
            best[uid] = a
    return sorted(best.values(), key=lambda x: x.get("publish_date", ""), reverse=True)

# 用法: NL语义搜索研报
articles = iwencai_search("人形机器人 行星滚柱丝杠 2026", channel="report", size=50)
articles = dedup_articles(articles)
for a in articles[:5]:
    extra = a.get("extra") or {}
    if isinstance(extra, str):
        extra = json.loads(extra)
    print(f"{a.get('publish_date','')[:10]} | {extra.get('organization','')} | {a.get('title','')[:60]}")
```

**iwencai 的唯一价值：** NL 主题搜索。"人形机器人 行星滚柱丝杠" 这种跨主题检索只有 iwencai 能做。按标的搜研报走东财 reportapi 更稳定。

---

## Layer 3: 信号层

### 3.1 同花顺热点 — 当日强势股 + 题材归因 reason tags（独家）

**核心价值：** 不只告诉你"哪些走强"，还告诉你**"为什么走强"** —— 同花顺编辑部人工运营的题材标签。

```python
import requests
import pandas as pd

def ths_hot_reason(date: str = None) -> pd.DataFrame:
    """
    同花顺当日强势股归因。
    date: 'YYYY-MM-DD' 格式，None=今天
    返回 DataFrame，含每只股票的题材标签 (reason)。

    实测: 73ms 拿到 ~125 只 + 完整字段
    """
    from datetime import date as _date
    if date is None:
        date = _date.today().strftime("%Y-%m-%d")

    url = (
        f"http://zx.10jqka.com.cn/event/api/getharden/"
        f"date/{date}/orderby/date/orderway/desc/charset/GBK/"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "Chrome/117.0.0.0 Safari/537.36"
        )
    }
    r = requests.get(url, headers=headers, timeout=10)
    data = r.json()
    if data.get("errocode", 0) != 0:
        raise RuntimeError(f"同花顺热点错误: {data.get('errormsg', '')}")

    rows = data.get("data") or []
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # 字段重命名（中文友好）
    rename_map = {
        "name": "名称", "code": "代码", "reason": "题材归因",
        "close": "收盘价", "zhangdie": "涨跌额", "zhangfu": "涨幅%",
        "huanshou": "换手率%", "chengjiaoe": "成交额",
        "chengjiaoliang": "成交量", "ddejingliang": "大单净量",
        "market": "市场",
    }
    df = df.rename(columns=rename_map)
    return df

# 用法
df = ths_hot_reason("2026-05-09")
print(f"当日强势股: {len(df)} 只")
print(df[["代码", "名称", "涨幅%", "题材归因"]].head(10))
```

#### 同花顺热点字段速查

| 原字段 | 中文 | 说明 |
|---|---|---|
| code | 代码 | 6 位股票代码 |
| name | 名称 | 简称 |
| **reason** | **题材归因** | **核心字段，人工运营 tags，如"算力租赁+Token工厂+AI政务"** |
| zhangfu | 涨幅% | 当日涨幅 |
| huanshou | 换手率% | 当日换手 |
| chengjiaoe | 成交额 | 元 |
| chengjiaoliang | 成交量 | 股 |
| ddejingliang | 大单净量 | 主力净流入指标 |
| close | 收盘价 | 元 |
| zhangdie | 涨跌额 | 元 |
| market | 市场 | 沪/深/北 |

### 3.2 同花顺北向资金 — hsgtApi 实时分钟流向 + 本地自缓存历史

> **已知行业性问题：** eastmoney 全系北向数据自 2024-08 后净买额字段返回 NaN/0，属上游断供。已改为**本地 CSV 自缓存模式**——每次拉实时数据后自动写入本地 CSV，历史越跑越丰富。

```python
import requests
import pandas as pd
from pathlib import Path

HSGT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "Chrome/117.0.0.0 Safari/537.36"
    ),
    "Host": "data.hexin.cn",
    "Referer": "https://data.hexin.cn/",
}

def hsgt_realtime() -> pd.DataFrame:
    """
    沪深股通当日实时分钟流向（含集合竞价 09:10–15:00，262 个时间点）。
    返回字段: time, hgt(沪股通累计净买入), sgt(深股通累计净买入)
    单位: 亿元
    """
    url = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
    r = requests.get(url, headers=HSGT_HEADERS, timeout=10)
    d = r.json()
    times = d.get("time", [])
    hgt = d.get("hgt", [])
    sgt = d.get("sgt", [])

    n = len(times)
    return pd.DataFrame({
        "time": times,
        "hgt_yi": hgt[:n] + [None] * (n - len(hgt)),
        "sgt_yi": sgt[:n] + [None] * (n - len(sgt)),
    })

# === 自缓存辅助函数 ===

def _northbound_cache_path() -> Path:
    """北向资金本地 CSV 缓存路径"""
    p = Path.home() / ".tradingagents" / "cache" / "northbound_daily.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def _save_northbound_snapshot(date: str, hgt: float, sgt: float):
    """写入/更新当天北向收盘数据到 CSV"""
    path = _northbound_cache_path()
    rows = {}
    if path.exists():
        for line in path.read_text().strip().split("\n")[1:]:
            parts = line.split(",")
            if len(parts) == 3:
                rows[parts[0]] = line
    rows[date] = f"{date},{hgt},{sgt}"
    with open(path, "w") as f:
        f.write("date,hgt,sgt\n")
        for d in sorted(rows.keys()):
            f.write(rows[d] + "\n")

def _load_northbound_history(n: int = 20) -> pd.DataFrame:
    """读取最近 N 天北向历史"""
    path = _northbound_cache_path()
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df.tail(n)

# 用法 1: 实时分钟流向
df = hsgt_realtime()
print(f"分钟点数: {len(df)}")
print(df.tail(5))

# 用法 2: 自动缓存今日收盘数据
if not df.empty:
    last = df.dropna().iloc[-1]
    _save_northbound_snapshot("2026-05-17", last["hgt_yi"], last["sgt_yi"])

# 用法 3: 读取历史
hist = _load_northbound_history(20)
print(hist)
```

### 3.3 百度股市通 — 概念板块归属

**核心价值：** 一次调用拿到个股所属的行业（申万一级/二级）、概念（多个）、地域三维分类，含当日涨跌幅。

```python
import requests

_BAIDU_PAE_HEADERS = {
    "Host": "finance.pae.baidu.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0",
    "Accept": "application/vnd.finance-web.v1+json",
    "Origin": "https://gushitong.baidu.com",
    "Referer": "https://gushitong.baidu.com/",
}

def baidu_concept_blocks(code: str) -> dict:
    """
    百度股市通概念板块归属。
    返回: {industry: [...], concept: [...], region: [...], concept_tags: [...]}
    """
    url = (
        f"https://finance.pae.baidu.com/api/getrelatedblock"
        f"?code={code}&market=ab"
        f"&typeCode=all&finClientType=pc"
    )
    r = requests.get(url, headers=_BAIDU_PAE_HEADERS, timeout=10)
    d = r.json()
    if str(d.get("ResultCode", -1)) != "0":
        raise RuntimeError(f"百度PAE错误: {d}")

    result = {"industry": [], "concept": [], "region": [], "concept_tags": []}
    for block in d.get("Result", []):
        block_type = block.get("type", "")
        for item in block.get("list", []):
            entry = {
                "name": item.get("name", ""),
                "change_pct": item.get("increase", ""),
                "desc": item.get("desc", ""),
            }
            if "行业" in block_type:
                result["industry"].append(entry)
            elif "概念" in block_type:
                result["concept"].append(entry)
                result["concept_tags"].append(entry["name"])
            elif "地域" in block_type:
                result["region"].append(entry)
    return result

# 用法
blocks = baidu_concept_blocks("688017")
print("行业:", [b["name"] for b in blocks["industry"]])
print("概念:", blocks["concept_tags"])
print("地域:", [b["name"] for b in blocks["region"]])
```

> **踩坑：** `ResultCode` 返回类型不稳定——有时 int `0`，有时 string `"0"`。必须用 `str()` 统一比较。

### 3.4 东财 push2 — 个股资金流向（分钟级）

盘中实时分钟级资金流（主力/大单/中单/小单/超大单净流入）。

> **V3.1 替换说明：** 百度 PAE `fundflow` 和 `fundsortlist` 接口已于 2026-05 下线（返回 null），改用东财 push2 资金流 API。日级资金流见 Layer 4.5 `stock_fund_flow_120d()`。

```python
import requests

def eastmoney_fund_flow_minute(code: str) -> list[dict]:
    """
    个股资金流向（分钟级，当日盘中）。
    code: 6位股票代码
    返回: [{time, main_net, small_net, mid_net, large_net, super_net}, ...]
    单位: 元
    """
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
    params = {
        "secid": secid, "klt": 1,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    headers = {
        "User-Agent": UA,
        "Referer": "https://quote.eastmoney.com/",
        "Origin": "https://quote.eastmoney.com",
    }
    try:
        r = em_get(url, params=params, headers=headers, timeout=10)
        d = r.json()
    except Exception as e:
        print(f"[WARN] push2 资金流请求失败: {e}")
        return []

    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append({
                "time": parts[0],
                "main_net": float(parts[1]),
                "small_net": float(parts[2]),
                "mid_net": float(parts[3]),
                "large_net": float(parts[4]),
                "super_net": float(parts[5]),
            })
    return rows

# 用法: 分钟级实时资金流
realtime = eastmoney_fund_flow_minute("000858")
if realtime:
    last = realtime[-1]
    signal = "bullish" if last["main_net"] > 0 else "bearish"
    print(f"主力净流入: {last['main_net']:.0f}元 → {signal}")
    # 统计全天主力净流入
    total = sum(r["main_net"] for r in realtime)
    print(f"全天主力累计: {total/1e4:.0f}万元")
```

> **注意：** push2 资金流金额单位是**元**（非万元），使用时注意换算。`klt=1` 分钟级，`klt=101` 日级。

### 3.5 龙虎榜席位 — 个股上榜记录 + 买卖席位 TOP5 + 机构动向

直连东财 datacenter API，不依赖第三方封装。

```python
import requests
from datetime import datetime, timedelta

def dragon_tiger_board(code: str, trade_date: str, look_back: int = 30) -> dict:
    """
    龙虎榜数据聚合。
    trade_date: YYYY-MM-DD
    look_back: 回看天数
    返回: {records: [...], seats: {buy: [...], sell: [...]}, institution: {...}}
    """
    start = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=look_back)
    start_str = start.strftime("%Y-%m-%d")

    # 1. 上榜记录
    records = []
    data = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{start_str}')(TRADE_DATE<='{trade_date}')(SECURITY_CODE=\"{code}\")",
        page_size=50,
        sort_columns="TRADE_DATE", sort_types="-1",
    )
    for row in data:
        records.append({
            "date": str(row.get("TRADE_DATE", ""))[:10],
            "reason": row.get("EXPLANATION", ""),
            "net_buy": round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 1),
            "turnover": round(float(row.get("TURNOVERRATE") or 0), 2),
        })

    # 2. 最近上榜的买卖席位
    seats = {"buy": [], "sell": []}
    if records:
        latest_date = records[0]["date"]
        # 买入席位
        buy_data = eastmoney_datacenter(
            "RPT_BILLBOARD_DAILYDETAILSBUY",
            filter_str=f"(TRADE_DATE='{latest_date}')(SECURITY_CODE=\"{code}\")",
            page_size=10,
            sort_columns="BUY", sort_types="-1",
        )
        for row in buy_data[:5]:
            seats["buy"].append({
                "name": row.get("OPERATEDEPT_NAME", ""),
                "buy_amt": round((row.get("BUY") or 0) / 10000, 1),
                "sell_amt": round((row.get("SELL") or 0) / 10000, 1),
                "net": round((row.get("NET") or 0) / 10000, 1),
            })
        # 卖出席位
        sell_data = eastmoney_datacenter(
            "RPT_BILLBOARD_DAILYDETAILSSELL",
            filter_str=f"(TRADE_DATE='{latest_date}')(SECURITY_CODE=\"{code}\")",
            page_size=10,
            sort_columns="SELL", sort_types="-1",
        )
        for row in sell_data[:5]:
            seats["sell"].append({
                "name": row.get("OPERATEDEPT_NAME", ""),
                "buy_amt": round((row.get("BUY") or 0) / 10000, 1),
                "sell_amt": round((row.get("SELL") or 0) / 10000, 1),
                "net": round((row.get("NET") or 0) / 10000, 1),
            })

    # 3. 机构买卖统计（从买卖席位明细中筛选 OPERATEDEPT_CODE="0" 即机构专用席位）
    institution = {"buy_amt": 0, "sell_amt": 0, "net_amt": 0}
    for detail_data, side in [(buy_data, "buy"), (sell_data, "sell")]:
        for row in detail_data:
            if str(row.get("OPERATEDEPT_CODE", "")) == "0":
                amt = (row.get("BUY") or 0) if side == "buy" else (row.get("SELL") or 0)
                if side == "buy":
                    institution["buy_amt"] += amt
                else:
                    institution["sell_amt"] += amt
    institution["buy_amt"] = round(institution["buy_amt"] / 10000, 1)
    institution["sell_amt"] = round(institution["sell_amt"] / 10000, 1)
    institution["net_amt"] = round(institution["buy_amt"] - institution["sell_amt"], 1)

    return {"records": records, "seats": seats, "institution": institution}

# 用法
data = dragon_tiger_board("002475", "2026-05-17")
print(f"近30日上榜 {len(data['records'])} 次")
for r in data["records"]:
    print(f"  {r['date']}: {r['reason']}")
if data["seats"]["buy"]:
    print("买入席位 TOP5:")
    for s in data["seats"]["buy"]:
        print(f"  {s['name']}: 买{s['buy_amt']}万 卖{s['sell_amt']}万 净{s['net']}万")
```

> **ST 股注意：** 5% 涨跌停更容易触发龙虎榜（"连续三日偏离值累计达12%"），科创板 20% 涨跌停则较少触发。

### 3.6 限售解禁日历 — 历史解禁 + 未来 90 天待解禁

```python
from datetime import datetime, timedelta

def lockup_expiry(code: str, trade_date: str, forward_days: int = 90) -> dict:
    """
    限售解禁日历。
    返回: {history: [...], upcoming: [...]}
    """
    # 1. 历史解禁记录
    history_data = eastmoney_datacenter(
        "RPT_LIFT_STAGE",
        filter_str=f"(SECURITY_CODE=\"{code}\")",
        page_size=15,
        sort_columns="FREE_DATE", sort_types="-1",
    )
    history = []
    for row in history_data:
        history.append({
            "date": str(row.get("FREE_DATE", ""))[:10],
            "type": row.get("LIMITED_STOCK_TYPE", ""),
            "shares": row.get("FREE_SHARES_NUM", 0),
            "ratio": row.get("FREE_RATIO", 0),
        })

    # 2. 未来待解禁
    end_date = datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=forward_days)
    end_str = end_date.strftime("%Y-%m-%d")
    upcoming_data = eastmoney_datacenter(
        "RPT_LIFT_STAGE",
        filter_str=f"(SECURITY_CODE=\"{code}\")(FREE_DATE>='{trade_date}')(FREE_DATE<='{end_str}')",
        page_size=20,
        sort_columns="FREE_DATE", sort_types="1",
    )
    upcoming = []
    for row in upcoming_data:
        upcoming.append({
            "date": str(row.get("FREE_DATE", ""))[:10],
            "type": row.get("LIMITED_STOCK_TYPE", ""),
            "shares": row.get("FREE_SHARES_NUM", 0),
            "ratio": row.get("FREE_RATIO", 0),
        })

    return {"history": history, "upcoming": upcoming}

# 用法
data = lockup_expiry("002475", "2026-05-17")
print(f"历史解禁 {len(data['history'])} 批")
for h in data["history"][:5]:
    print(f"  {h['date']}: {h['type']} 数量={h['shares']}")
if data["upcoming"]:
    print(f"未来90天待解禁 {len(data['upcoming'])} 批")
else:
    print("未来90天无待解禁")
```

**限售股类型参考：**
- 首发原股东限售股份（IPO 后 1-3 年）
- 首发机构配售股份（IPO 战略配售）
- 定向增发机构配售股份（6-18 个月）
- 股权激励限售股份

### 3.7 行业板块排名（V3.0 改用东财 — 同花顺加了反爬401）

东财行业板块涨跌幅排名，一次调用看全市场行业轮动。

```python
import requests

def industry_comparison(top_n: int = 20) -> dict:
    """
    全行业涨跌幅排名（东财行业板块，~100 个行业）。
    返回: {top: [...], bottom: [...], total: int}
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "fltt": "2", "invt": "2",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
    }
    headers = {"User-Agent": UA}
    r = em_get(url, params=params, headers=headers, timeout=15)
    d = r.json()
    items = d.get("data", {}).get("diff", [])
    if not items:
        return {"top": [], "bottom": [], "total": 0}

    rows = []
    for i, item in enumerate(items):
        rows.append({
            "rank": i + 1,
            "name": item.get("f14", ""),
            "change_pct": item.get("f3", 0),
            "code": item.get("f12", ""),
            "up_count": item.get("f104", 0),
            "down_count": item.get("f105", 0),
            "leader": item.get("f140", ""),
            "leader_change": item.get("f136", 0),
        })

    return {
        "top": rows[:top_n],
        "bottom": rows[-top_n:],
        "total": len(rows),
    }

# 用法
data = industry_comparison(20)
print(f"共 {data['total']} 个行业")
print("\nTOP 10 涨幅:")
for r in data["top"][:10]:
    print(f"  {r['rank']}. {r['name']}: {r['change_pct']}% 涨{r['up_count']}跌{r['down_count']} 领涨{r['leader']}")
print("\nBOTTOM 5 跌幅:")
for r in data["bottom"][-5:]:
    print(f"  {r['rank']}. {r['name']}: {r['change_pct']}%")
```

### 3.8 全市场龙虎榜

每日全市场龙虎榜汇总——当日所有触发龙虎榜的股票 + 上榜原因 + 买卖净额 + 换手率。

```python
from datetime import datetime

def daily_dragon_tiger(trade_date: str = None, min_net_buy: float = None) -> dict:
    """
    全市场龙虎榜。
    trade_date: YYYY-MM-DD（默认当日）
    min_net_buy: 净买入下限（万元），None 不过滤
    返回: {date, total_records, stocks: [{code, name, reason, close, change_pct,
           net_buy_wan, buy_wan, sell_wan, turnover_pct}]}
    """
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    data = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
        page_size=500,
        sort_columns="BILLBOARD_NET_AMT", sort_types="-1",
    )
    if not data:
        return {"date": trade_date, "total_records": 0, "stocks": [],
                "note": "无数据（非交易日或盘后未更新）"}

    actual_date = str(data[0].get("TRADE_DATE", ""))[:10] if data else trade_date
    stocks = []
    for row in data:
        net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
        if min_net_buy is not None and net_buy < min_net_buy:
            continue
        stocks.append({
            "code": row.get("SECURITY_CODE", ""),
            "name": row.get("SECURITY_NAME_ABBR", ""),
            "reason": row.get("EXPLANATION", ""),
            "close": row.get("CLOSE_PRICE") or 0,
            "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
            "net_buy_wan": round(net_buy, 1),
            "buy_wan": round((row.get("BILLBOARD_BUY_AMT") or 0) / 10000, 1),
            "sell_wan": round((row.get("BILLBOARD_SELL_AMT") or 0) / 10000, 1),
            "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
        })
    return {"date": actual_date, "total_records": len(stocks), "stocks": stocks}

# 用法
data = daily_dragon_tiger("2026-05-16")
print(f"{data['date']} 龙虎榜共 {data['total_records']} 条记录")
for s in data["stocks"][:10]:
    print(f"  {s['code']} {s['name']}: {s['reason']} | 净买{s['net_buy_wan']}万 涨跌{s['change_pct']}%")

# 只看净买入 > 5000 万的
data = daily_dragon_tiger("2026-05-16", min_net_buy=5000)
print(f"\n净买入 > 5000万: {data['total_records']} 条")
```

### 3.9 信号层组合用法：题材热度 + 资金验证

```python
# 拉当日强势股 reason
df_hot = ths_hot_reason()

# 词频统计 reason 列里的题材关键词
from collections import Counter
all_tags = []
for r in df_hot["题材归因"].dropna():
    tags = [t.strip() for t in str(r).split("+") if t.strip()]
    all_tags.extend(tags)

cnt = Counter(all_tags)
print("当日 TOP 10 题材热度:")
for tag, n in cnt.most_common(10):
    print(f"  {tag}: {n} 只")

# 同时拉北向当日流向，看资金流方向是否对应题材
df_north = hsgt_realtime()
hgt_close = df_north["hgt_yi"].dropna().iloc[-1] if not df_north.empty else 0
sgt_close = df_north["sgt_yi"].dropna().iloc[-1] if not df_north.empty else 0
print(f"\n北向收盘累计: 沪股通 {hgt_close} 亿 / 深股通 {sgt_close} 亿")

# V3.0: 叠加行业对比，看哪些行业资金在流入
comp = industry_comparison(10)
print("\n行业涨幅 TOP 5:")
for r in comp["top"][:5]:
    print(f"  {r['name']}: {r['change_pct']}% 涨{r['up_count']}跌{r['down_count']}")
```

---

## Layer 4: 资金面 / 筹码层（V3.0 新增）

### 4.1 融资融券明细

```python
def margin_trading(code: str, page_size: int = 30) -> list[dict]:
    """
    融资融券明细（日级）。
    返回: [{date, rzye(融资余额), rzmre(融资买入), rqye(融券余额), ...}]
    """
    data = eastmoney_datacenter(
        "RPTA_WEB_RZRQ_GGMX",
        filter_str=f'(SCODE="{code}")',
        page_size=page_size,
        sort_columns="DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        rows.append({
            "date": str(row.get("DATE", ""))[:10],
            "rzye": row.get("RZYE", 0),       # 融资余额(元)
            "rzmre": row.get("RZMRE", 0),      # 融资买入额
            "rzche": row.get("RZCHE", 0),      # 融资偿还额
            "rqye": row.get("RQYE", 0),        # 融券余额(元)
            "rqmcl": row.get("RQMCL", 0),      # 融券卖出量
            "rqchl": row.get("RQCHL", 0),      # 融券偿还量
            "rzrqye": row.get("RZRQYE", 0),    # 融资融券余额合计
        })
    return rows

# 用法
data = margin_trading("600519")
for d in data[:5]:
    print(f"{d['date']}: 融资余额={d['rzye']/1e8:.2f}亿 融券余额={d['rqye']/1e8:.2f}亿")
```

### 4.2 大宗交易

```python
def block_trade(code: str, page_size: int = 20) -> list[dict]:
    """
    大宗交易记录。
    返回: [{date, price, vol, amount, buyer, seller, premium_pct}]
    """
    data = eastmoney_datacenter(
        "RPT_DATA_BLOCKTRADE",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="TRADE_DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        close = row.get("CLOSE_PRICE") or 0
        deal_price = row.get("DEAL_PRICE") or 0
        premium = ((deal_price / close - 1) * 100) if close else 0
        rows.append({
            "date": str(row.get("TRADE_DATE", ""))[:10],
            "price": deal_price,
            "close": close,
            "premium_pct": round(premium, 2),
            "vol": row.get("DEAL_VOLUME", 0),
            "amount": row.get("DEAL_AMT", 0),
            "buyer": row.get("BUYER_NAME", ""),
            "seller": row.get("SELLER_NAME", ""),
        })
    return rows

# 用法
data = block_trade("600519")
for d in data[:5]:
    print(f"{d['date']}: 价格={d['price']} 溢价={d['premium_pct']}% 买方={d['buyer']}")
```

### 4.3 股东户数变化

```python
def holder_num_change(code: str, page_size: int = 10) -> list[dict]:
    """
    股东户数变化（季度级）。
    返回: [{date, holder_num, change_num, change_ratio, avg_shares}]
    """
    data = eastmoney_datacenter(
        "RPT_HOLDERNUMLATEST",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="END_DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        rows.append({
            "date": str(row.get("END_DATE", ""))[:10],
            "holder_num": row.get("HOLDER_NUM", 0),
            "change_num": row.get("HOLDER_NUM_CHANGE", 0),
            "change_ratio": row.get("HOLDER_NUM_RATIO", 0),  # 环比%
            "avg_shares": row.get("AVG_FREE_SHARES", 0),     # 户均持股
        })
    return rows

# 用法
data = holder_num_change("600519")
for d in data[:5]:
    print(f"{d['date']}: 股东数={d['holder_num']} 变化={d['change_ratio']}% 户均={d['avg_shares']}")
# 股东户数持续减少 = 筹码集中 = 主力吸筹信号
```

### 4.4 分红送转历史

```python
def dividend_history(code: str, page_size: int = 20) -> list[dict]:
    """
    分红送转历史。
    返回: [{date, bonus_rmb(每股派息), transfer_ratio(转增比例), bonus_ratio(送股比例)}]
    """
    data = eastmoney_datacenter(
        "RPT_SHAREBONUS_DET",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="EX_DIVIDEND_DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        rows.append({
            "date": str(row.get("EX_DIVIDEND_DATE", ""))[:10],
            "bonus_rmb": row.get("PRETAX_BONUS_RMB", 0),    # 每股派息(税前)
            "transfer_ratio": row.get("TRANSFER_RATIO", 0),  # 每10股转增
            "bonus_ratio": row.get("BONUS_RATIO", 0),        # 每10股送股
            "plan": row.get("ASSIGN_PROGRESS", ""),           # 进度
        })
    return rows

# 用法
data = dividend_history("600519")
for d in data[:5]:
    print(f"{d['date']}: 每股派息={d['bonus_rmb']}元 转增={d['transfer_ratio']} 送={d['bonus_ratio']}")
```

### 4.5 个股资金流（120日，日级）

```python
import requests

def stock_fund_flow_120d(code: str) -> list[dict]:
    """
    个股资金流（日级，最近120个交易日）。
    返回: [{date, main_net(主力净流入), small_net, mid_net, large_net, super_net}]
    单位: 元
    """
    market_code = 1 if code.startswith("6") else 0
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": f"{market_code}.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": "120",
    }
    headers = {
        "User-Agent": UA,
        "Referer": "https://quote.eastmoney.com/",
        "Origin": "https://quote.eastmoney.com",
    }
    try:
        r = em_get(url, params=params, headers=headers, timeout=15)
        d = r.json()
    except Exception as e:
        print(f"[WARN] push2 资金流请求失败: {e}")
        return []
    klines = d.get("data", {}).get("klines", [])

    rows = []
    for line in klines:
        parts = line.split(",")
        if len(parts) >= 7:
            rows.append({
                "date": parts[0],
                "main_net": float(parts[1]) if parts[1] != "-" else 0,
                "small_net": float(parts[2]) if parts[2] != "-" else 0,
                "mid_net": float(parts[3]) if parts[3] != "-" else 0,
                "large_net": float(parts[4]) if parts[4] != "-" else 0,
                "super_net": float(parts[5]) if parts[5] != "-" else 0,
            })
    return rows

# 用法
data = stock_fund_flow_120d("600519")
for d in data[-5:]:
    print(f"{d['date']}: 主力净流入={d['main_net']/1e4:.0f}万 超大单={d['super_net']/1e4:.0f}万")

# 统计近20日主力净流入
recent_20 = data[-20:]
total_main = sum(d["main_net"] for d in recent_20)
print(f"\n近20日主力累计净流入: {total_main/1e8:.2f}亿")
```

---

## Layer 5: 新闻层

### 5.1 东财个股新闻（直连 search-api-web）

```python
import requests
import re
import json

def eastmoney_stock_news(code: str, page_size: int = 20) -> list[dict]:
    """
    东财个股新闻（JSONP 接口）。
    返回: [{title, content, time, source, url}]
    """
    # 构造 JSONP 参数
    cb = "jQuery_news"
    url = "https://search-api-web.eastmoney.com/search/jsonp"
    inner_params = json.dumps({
        "uid": "",
        "keyword": code,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {"cmsArticleWebOld": {"searchScope": "default", "sort": "default",
                  "pageIndex": 1, "pageSize": page_size, "preTag": "", "postTag": ""}},
    }, separators=(',', ':'))
    params = {"cb": cb, "param": inner_params}
    headers = {"User-Agent": UA, "Referer": "https://so.eastmoney.com/"}
    r = em_get(url, params=params, headers=headers, timeout=15)

    # 解析 JSONP
    text = r.text
    json_str = text[text.index("(") + 1 : text.rindex(")")]
    d = json.loads(json_str)

    rows = []
    # 东财实际返回里 result.cmsArticleWebOld 直接就是文章列表（非 {list:[...]} 嵌套）
    articles = d.get("result", {}).get("cmsArticleWebOld", []) or []
    for a in articles:
        rows.append({
            "title": re.sub(r'<[^>]+>', '', a.get("title", "")),
            "content": re.sub(r'<[^>]+>', '', a.get("content", ""))[:200],
            "time": a.get("date", ""),
            "source": a.get("mediaName", ""),
            "url": a.get("url", ""),
        })
    return rows

# 用法
news = eastmoney_stock_news("688017")
for n in news[:5]:
    print(f"  {n['time']} | {n['source']} | {n['title']}")
```

### 5.2 财联社快讯（直连 cls.cn）— ⚠️ 已下线，改用 §5.3

> **⚠️ 2026-05 已失效（#14）：** 财联社网站迁移到 Next.js 架构，旧版公开接口
> `cls.cn/nodeapi/telegraphList` 全面下线（返回 404），新版 API 需签名认证，无法
> 公开 HTTP 调用。**全市场实时快讯请改用 §5.3「东财全球资讯」**（7×24 滚动，免费无 key）。
> 下面代码仅作历史参考，已不可用。

```python
import requests

def cls_telegraph(page_size: int = 50) -> list[dict]:
    """
    财联社电报（全市场实时快讯）。
    返回: [{title, content, time}]
    """
    url = "https://www.cls.cn/nodeapi/telegraphList"
    params = {"rn": str(page_size), "page": "1"}
    headers = {"User-Agent": UA, "Referer": "https://www.cls.cn/"}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    d = r.json()

    rows = []
    for item in d.get("data", {}).get("roll_data", []):
        rows.append({
            "title": item.get("title", "") or item.get("brief", ""),
            "content": item.get("content", "") or item.get("brief", ""),
            "time": item.get("ctime", ""),
        })
    return rows

# 用法
news = cls_telegraph()
for n in news[:10]:
    print(f"  {n['time']} | {n['title'][:60]}")
```

### 5.3 东财全球资讯（7x24）

```python
import requests

import uuid

def eastmoney_global_news(page_size: int = 50) -> list[dict]:
    """
    东方财富全球财经资讯（7x24 滚动）。
    返回: [{title, summary, time}]
    """
    url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
    params = {
        "client": "web", "biz": "web_724",
        "fastColumn": "102", "sortEnd": "",
        "pageSize": str(page_size),
        "req_trace": str(uuid.uuid4()),
    }
    headers = {"User-Agent": UA, "Referer": "https://kuaixun.eastmoney.com/"}
    r = em_get(url, params=params, headers=headers, timeout=10)
    d = r.json()

    rows = []
    for item in d.get("data", {}).get("fastNewsList", []):
        rows.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", "")[:200],
            "time": item.get("showTime", ""),
        })
    return rows

# 用法
news = eastmoney_global_news()
for n in news[:10]:
    print(f"  {n['time']} | {n['title']}")
```

---

## Layer 6: 基础数据层

### 6.1 mootdx 财务快照（37字段季报数据）

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market='std')

# market: 0=深圳, 1=上海
fin = client.finance(symbol='688017')
# 返回 37 个字段的季报快照:
#   liutongguben(流通股本), zongguben(总股本)
#   eps(每股收益), bvps(每股净资产), roe(净资产收益率%)
#   profit(净利润), income(主营收入)
#   meigujingzichan(每股净资产), meigugongjijin(每股公积金)
#   meiguweifeipeili(每股未分配利润)
#   等37个季报财务字段
```

### 6.2 mootdx F10（公司文本资料）

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market='std')

# 9 大类文本数据:
categories = [
    "最新提示", "公司概况", "财务分析",
    "股东研究", "股本结构", "资本运作",
    "业内点评", "行业分析", "公司大事",
]
for cat in categories:
    text = client.F10(symbol='688017', name=cat)
    print(f"=== {cat} ===")
    print(text[:200] if text else "(空)")
```

> **优化提示：** "股东研究" 中的【4.股东变化】章节含大量历史十大股东列表，实测 16000+ chars。建议只保留最新一期（-70% token）。

### 6.3 东财个股基本面（直连 push2 API）

```python
import requests

def eastmoney_stock_info(code: str) -> dict:
    """
    东财个股基本面信息。
    返回: {code, name, industry, total_shares, float_shares, mcap, float_mcap, list_date}
    """
    market_code = 1 if code.startswith("6") else 0
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "fltt": "2", "invt": "2",
        "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
        "secid": f"{market_code}.{code}",
    }
    headers = {"User-Agent": UA}
    r = em_get(url, params=params, headers=headers, timeout=10)
    d = r.json().get("data", {})
    return {
        "code": d.get("f57", ""),
        "name": d.get("f58", ""),
        "industry": d.get("f127", ""),
        "total_shares": d.get("f84", 0),     # 总股本(股)
        "float_shares": d.get("f85", 0),     # 流通股(股)
        "mcap": d.get("f116", 0),            # 总市值(元)
        "float_mcap": d.get("f117", 0),      # 流通市值(元)
        "list_date": str(d.get("f189", "")), # 上市日期 YYYYMMDD
        "price": d.get("f43", 0),
    }

# 用法
info = eastmoney_stock_info("688017")
print(f"{info['name']}({info['code']}): 行业={info['industry']} 总市值={info['mcap']/1e8:.0f}亿 上市={info['list_date']}")
```

### 6.4 新浪财报三表（资产负债表/利润表/现金流量表）

```python
import requests

def sina_financial_report(code: str, report_type: str = "lrb", num: int = 8) -> list[dict]:
    """
    新浪财报三表。
    code: 6位代码
    report_type: "fzb"(资产负债表) / "lrb"(利润表) / "llb"(现金流量表)
    num: 取最近 N 期（默认 8 期）
    返回: 按报告期倒序的记录列表，每期一条 dict：
          {"报告期": "2026-03-31", "<科目>": "<值>", "<科目>_同比": <同比>, ...}
          （item_value 为新浪原始字符串数值，仅在有同比时附 "_同比" 键）
    """
    prefix = "sh" if code.startswith("6") else "sz"
    paper_code = f"{prefix}{code}"
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
    params = {
        "paperCode": paper_code,
        "source": report_type,
        "type": "0",
        "page": "1",
        "num": str(num),
    }
    headers = {"User-Agent": UA}
    r = requests.get(url, params=params, headers=headers, timeout=15)
    # 新浪实际结构: result.data.report_list 是「按报告期(如 '20260331')为键」的 dict,
    # 每期对象的 data 字段才是行项列表 [{item_title, item_value, item_tongbi}]。
    report_list = r.json().get("result", {}).get("data", {}).get("report_list", {}) or {}

    rows = []
    for period in sorted(report_list.keys(), reverse=True)[:num]:
        obj = report_list[period]
        rec = {"报告期": f"{period[:4]}-{period[4:6]}-{period[6:8]}"}
        for it in obj.get("data", []) or []:
            title = it.get("item_title", "")
            if not title or it.get("item_value") is None:
                continue
            rec[title] = it.get("item_value")
            tongbi = it.get("item_tongbi")
            if tongbi not in (None, ""):
                rec[title + "_同比"] = tongbi
        rows.append(rec)
    return rows

# 用法: 利润表
lrb = sina_financial_report("600519", "lrb")
for item in lrb[:3]:
    print(f"报告期: {item.get('报告期', '')} 净利润: {item.get('净利润', '')}")

# 用法: 资产负债表
fzb = sina_financial_report("600519", "fzb")

# 用法: 现金流量表
llb = sina_financial_report("600519", "llb")
```

---

## Layer 7: 公告层

### 7.1 巨潮公告（直连 cninfo.com.cn）

```python
import requests
from datetime import datetime

def _cninfo_ts_to_date(ts):
    """巨潮 announcementTime 返回 Unix 毫秒整数，需转换为日期字符串。"""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
    return str(ts)[:10] if ts else ""

def cninfo_announcements(code: str, page_size: int = 30) -> list[dict]:
    """
    巨潮公告全文检索。
    返回: [{title, type, date, url}]
    """
    url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    # 构造 orgId（巨潮 2026 新格式）
    if code.startswith("6"):
        org_id = f"gssh0{code}"
    elif code.startswith("8") or code.startswith("4"):
        org_id = f"gsbj0{code}"
    else:
        org_id = f"gssz0{code}"

    payload = {
        "stock": f"{code},{org_id}",
        "tabName": "fulltext",
        "pageSize": str(page_size),
        "pageNum": "1",
        "column": "",
        "category": "",
        "plate": "",
        "seDate": "",
        "searchkey": "",
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.cninfo.com.cn/new/disclosure",
        "Origin": "https://www.cninfo.com.cn",
    }
    r = requests.post(url, data=payload, headers=headers, timeout=15)
    d = r.json()

    rows = []
    for item in d.get("announcements", []) or []:
        rows.append({
            "title": item.get("announcementTitle", ""),
            "type": item.get("announcementTypeName", ""),
            "date": _cninfo_ts_to_date(item.get("announcementTime")),
            "url": f"https://www.cninfo.com.cn/new/disclosure/detail?annoId={item.get('announcementId', '')}",
        })
    return rows

# 用法
anns = cninfo_announcements("688017")
for a in anns[:10]:
    print(f"  {a['date']} | {a['type']} | {a['title']}")
```

### 7.2 mootdx F10 公告摘要

```python
from mootdx.quotes import Quotes
client = Quotes.factory(market='std')
text = client.F10(symbol='688017', name='最新提示')
# 包含最近的公告/分红/股东大会决议等摘要
```

---

## Layer 8: 推荐与预测层（V3.3 新增）

多因子智能评分系统，综合技术面、资金面、信号面、基本面四大维度生成推荐建议，支持个股趋势预测和批量选股排名。

### 8.0 前置依赖 — 技术指标计算（共用 helper）

```python
import pandas as pd
import numpy as np
from mootdx.quotes import Quotes
from stockstats import StockDataFrame

client = Quotes.factory(market='std')

# ── 技术指标计算器（stockstats 封装）───────────────────────────────────
# stockstats 基于 pandas DataFrame，自动计算 RSI/MACD/BOLL/KDJ 等 30+ 指标
# 用法: stock = StockDataFrame.retype(df) 后即可访问 stock['rsi_14'] 等

def calc_technical_indicators(code: str, offset: int = 120) -> dict:
    """
    计算单只股票的全部技术指标。
    返回 dict: 含 RSI/MACD/BOLL/KDJ/均线 等最新值及历史序列。
    """
    bars = client.bars(symbol=code, category=4, offset=offset)
    if bars is None or len(bars) < 30:
        return {}
    df = pd.DataFrame(bars)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime').sort_index()
    
    # 用 stockstats 计算全部指标
    stock = StockDataFrame.retype(df)
    
    # 提取最新值
    last = {
        'code': code,
        'close': float(df['close'].iloc[-1]),
        'volume': float(df['vol'].iloc[-1]),
        
        # RSI
        'rsi_6': float(stock['rsi_6'].dropna().iloc[-1]) if len(stock['rsi_6'].dropna()) > 0 else None,
        'rsi_14': float(stock['rsi_14'].dropna().iloc[-1]) if len(stock['rsi_14'].dropna()) > 0 else None,
        
        # MACD
        'macd': float(stock['macd'].dropna().iloc[-1]) if len(stock['macd'].dropna()) > 0 else None,
        'macds': float(stock['macds'].dropna().iloc[-1]) if len(stock['macds'].dropna()) > 0 else None,
        'macdh': float(stock['macdh'].dropna().iloc[-1]) if len(stock['macdh'].dropna()) > 0 else None,
        
        # BOLL
        'boll': float(stock['boll'].dropna().iloc[-1]) if len(stock['boll'].dropna()) > 0 else None,
        'boll_ub': float(stock['boll_ub'].dropna().iloc[-1]) if len(stock['boll_ub'].dropna()) > 0 else None,
        'boll_lb': float(stock['boll_lb'].dropna().iloc[-1]) if len(stock['boll_lb'].dropna()) > 0 else None,
        
        # KDJ
        'kdjk': float(stock['kdjk'].dropna().iloc[-1]) if len(stock['kdjk'].dropna()) > 0 else None,
        'kdjd': float(stock['kdjd'].dropna().iloc[-1]) if len(stock['kdjd'].dropna()) > 0 else None,
        'kdjj': float(stock['kdjj'].dropna().iloc[-1]) if len(stock['kdjj'].dropna()) > 0 else None,
        
        # 均线
        'ma5': float(df['close'].rolling(5).mean().iloc[-1]),
        'ma10': float(df['close'].rolling(10).mean().iloc[-1]),
        'ma20': float(df['close'].rolling(20).mean().iloc[-1]),
        'ma60': float(df['close'].rolling(60).mean().iloc[-1]) if len(df) >= 60 else None,
        
        # 量比
        'vr': float(stock['vr'].dropna().iloc[-1]) if len(stock['vr'].dropna()) > 0 else None,
        'vr_6': float(stock['vr_6'].dropna().iloc[-1]) if len(stock['vr_6'].dropna()) > 0 else None,
    }
    
    # 保存完整序列用于趋势判断
    last['_df'] = df
    last['_stock'] = stock
    return last
```

### 8.1 技术面评分（权重 40%）

RSI位置 + MACD方向 + 均线排列 + 布林带位置 + KDJ信号综合评分，0-100 分。

```python
def technical_score(code: str) -> dict:
    """
    技术面综合评分 (0-100分)。
    评分维度:
      - RSI (0-25分): 30-70 为健康区，<20 超卖加分，>80 超买扣分
      - MACD (0-20分): DIF>DEA 且 MACD柱>0 加分，金叉额外加分
      - 均线排列 (0-25分): 多头排列(MA5>MA10>MA20>MA60)满分，空头排列低分
      - 布林带 (0-15分): 中轨上方加分，突破上轨/下轨做信号判断
      - KDJ (0-15分): K>D 多头，J<0 超卖反转信号
    返回: {score, level, details, signals}
    """
    ind = calc_technical_indicators(code)
    if not ind:
        return {'score': 0, 'level': '数据不足', 'details': {}, 'signals': []}
    
    score = 0
    signals = []
    details = {}
    close = ind['close']
    
    # ── RSI (0-25) ──
    rsi14 = ind.get('rsi_14')
    rsi_sub = 0
    if rsi14 is not None:
        if 30 <= rsi14 <= 70:
            rsi_sub = 20  # 健康区间
        elif rsi14 < 20:
            rsi_sub = 25  # 极度超卖，反弹概率高
            signals.append('RSI极度超卖(<20) → 反弹信号')
        elif rsi14 < 30:
            rsi_sub = 18
            signals.append('RSI超卖(<30) → 关注反弹')
        elif rsi14 > 80:
            rsi_sub = 5   # 极度超买
            signals.append('RSI极度超买(>80) → 回调风险')
        elif rsi14 > 70:
            rsi_sub = 10
            signals.append('RSI超买(>70) → 注意风险')
        else:
            rsi_sub = 15
    details['rsi14'] = round(rsi14, 1) if rsi14 else None
    details['rsi_score'] = rsi_sub
    score += rsi_sub
    
    # ── MACD (0-20) ──
    macd = ind.get('macd')
    macds = ind.get('macds')
    macdh = ind.get('macdh')
    macd_sub = 0
    if macd is not None and macds is not None and macdh is not None:
        # 检查近3日是否金叉
        df = ind['_df']
        stock = ind['_stock']
        macd_series = stock['macd'].dropna()
        macds_series = stock['macds'].dropna()
        if len(macd_series) >= 3 and len(macds_series) >= 3:
            # 金叉: 前一日 DIF<=DEA 且 当日 DIF>DEA
            prev_dif = macd_series.iloc[-2]
            prev_dea = macds_series.iloc[-2]
            if prev_dif <= prev_dea and macd > macds:
                signals.append('MACD金叉 ✓')
                macd_sub = 20
            elif macd > macds and macdh > 0:
                macd_sub = 15
            elif macd > macds:
                macd_sub = 10
            elif macdh < 0:
                macd_sub = 3
            else:
                macd_sub = 6
            if prev_dif > prev_dea and macd <= macds:
                signals.append('MACD死叉 ✗')
                macd_sub = max(0, macd_sub - 10)
    details['macd_dif'] = round(macd, 4) if macd else None
    details['macd_dea'] = round(macds, 4) if macds else None
    details['macd_score'] = macd_sub
    score += macd_sub
    
    # ── 均线排列 (0-25) ──
    ma5 = ind.get('ma5')
    ma10 = ind.get('ma10')
    ma20 = ind.get('ma20')
    ma60 = ind.get('ma60')
    ma_sub = 0
    if ma5 and ma10 and ma20:
        if ma60 and ma5 > ma10 > ma20 > ma60:
            ma_sub = 25  # 完美多头排列
            signals.append('均线多头排列(MA5>MA10>MA20>MA60) ✓')
        elif ma5 > ma10 > ma20:
            ma_sub = 20
            signals.append('短中期均线多头 ✓')
        elif ma5 > ma10:
            ma_sub = 12
        elif ma5 < ma10 < ma20:
            ma_sub = 3   # 空头排列
            if ma60 and ma5 < ma60:
                signals.append('均线空头排列 ✗')
        elif close > ma20:
            ma_sub = 8  # 价格在20日线上方
        else:
            ma_sub = 5
        # 价格站上所有均线加分
        above_all = [close > m for m in [ma5, ma10, ma20] if m]
        if all(above_all):
            ma_sub = min(25, ma_sub + 3)
            signals.append('股价站上所有短期均线 ✓')
    details['ma5'] = round(ma5, 2) if ma5 else None
    details['ma20'] = round(ma20, 2) if ma20 else None
    details['ma_score'] = ma_sub
    score += ma_sub
    
    # ── 布林带 (0-15) ──
    boll_mid = ind.get('boll')
    boll_ub = ind.get('boll_ub')
    boll_lb = ind.get('boll_lb')
    boll_sub = 0
    if boll_mid and boll_ub and boll_lb:
        boll_width = (boll_ub - boll_lb) / boll_mid  # 带宽
        if close > boll_mid:
            boll_sub = 12
        else:
            boll_sub = 6
        if boll_width < 0.1:
            signals.append('布林带收窄 → 变盘信号')
            boll_sub += 3
        if close > boll_ub:
            signals.append('股价突破布林上轨 → 强势但需防回调')
        elif close < boll_lb:
            signals.append('股价跌破布林下轨 → 超跌反弹概率高')
            boll_sub = min(15, boll_sub + 3)
    details['boll_mid'] = round(boll_mid, 2) if boll_mid else None
    details['boll_score'] = boll_sub
    score += boll_sub
    
    # ── KDJ (0-15) ──
    k = ind.get('kdjk')
    d = ind.get('kdjd')
    j = ind.get('kdjj')
    kdj_sub = 0
    if k is not None and d is not None and j is not None:
        if k > d:
            kdj_sub = 10
        if j < 0:
            kdj_sub = 15  # J值负值，超卖反转
            signals.append('KDJ J值<0 → 超卖底部信号')
        elif j > 100:
            kdj_sub = max(0, kdj_sub - 5)
            signals.append('KDJ J值>100 → 超买顶部信号')
        if k > 80 and d > 80:
            kdj_sub = max(0, kdj_sub - 3)
    details['kdj_k'] = round(k, 1) if k else None
    details['kdj_d'] = round(d, 1) if d else None
    details['kdj_j'] = round(j, 1) if j else None
    details['kdj_score'] = kdj_sub
    score += kdj_sub
    
    # ── 评级 ──
    if score >= 80:
        level = '强烈推荐'
    elif score >= 65:
        level = '推荐'
    elif score >= 50:
        level = '中性偏多'
    elif score >= 35:
        level = '中性偏空'
    elif score >= 20:
        level = '回避'
    else:
        level = '强烈回避'
    
    return {
        'score': score,
        'level': level,
        'details': details,
        'signals': signals,
    }
```

### 8.2 资金面评分（权重 30%）

主力资金流向 + 北向资金 + 融资融券 + 龙虎榜净买，0-100 分。

```python
import time

def capital_flow_score(code: str) -> dict:
    """
    资金面评分 (0-100分)，基于东财 push2his 120日资金流。
    - 近5日/20日主力净流入趋势
    - 超大单占比
    - 连续流入天数
    返回: {score, level, details, signals}
    """
    try:
        flow = stock_fund_flow_120d(code)
    except Exception:
        return {'score': 25, 'level': '数据不足', 'details': {}, 'signals': []}
    
    if not flow or len(flow) < 5:
        return {'score': 25, 'level': '数据不足', 'details': {}, 'signals': []}
    
    score = 25  # 基础分
    signals = []
    details = {}
    
    # 近5日主力净流入
    recent_5 = flow[-5:]
    main_5d = sum(d['main_net'] for d in recent_5)
    details['main_5d_wan'] = round(main_5d / 10000, 1)
    if main_5d > 1e8:
        score += 20
        signals.append('近5日主力大幅流入')
    elif main_5d > 0:
        score += 12
    elif main_5d < -5e7:
        score -= 10
        signals.append('近5日主力持续流出')
    
    # 近20日主力净流入
    recent_20 = flow[-20:]
    main_20d = sum(d['main_net'] for d in recent_20)
    details['main_20d_wan'] = round(main_20d / 10000, 1)
    if main_20d > 2e8:
        score += 25
        signals.append('近20日主力大幅建仓')
    elif main_20d > 5e7:
        score += 15
    elif main_20d < -1e8:
        score -= 15
        signals.append('近20日主力持续出货')
    
    # 超大单占比
    super_5d = sum(d['super_net'] for d in recent_5)
    if main_5d > 0 and super_5d > 0:
        ratio = super_5d / main_5d if main_5d else 0
        details['super_ratio'] = round(ratio, 2)
        if ratio > 0.5:
            score += 10
            signals.append('超大单主导流入 → 机构行为特征')
    
    # 连续流入天数
    consecutive = 0
    for d in reversed(flow):
        if d['main_net'] > 0:
            consecutive += 1
        else:
            break
    details['consecutive_days'] = consecutive
    if consecutive >= 5:
        score += 15
        signals.append(f'主力连续流入{consecutive}天')
    elif consecutive >= 3:
        score += 8
    
    # 北向资金（如果缓存有数据）
    try:
        north_df = _load_northbound_history(5)
        if not north_df.empty:
            north_recent = north_df.tail(3)
            north_sum = north_recent['hgt'].sum() + north_recent['sgt'].sum()
            if north_sum > 0:
                score += 5
                signals.append('北向资金近期净流入')
    except Exception:
        pass
    
    score = max(0, min(100, score))
    
    if score >= 75:
        level = '资金面强势'
    elif score >= 55:
        level = '资金面偏多'
    elif score >= 40:
        level = '资金面中性'
    elif score >= 25:
        level = '资金面偏空'
    else:
        level = '资金面弱势'
    
    return {'score': score, 'level': level, 'details': details, 'signals': signals}
```

### 8.3 信号面评分（权重 20%）

同花顺强势股归因 + 题材热度 + 行业排名，0-100 分。

```python
def signal_score(code: str, ths_df: pd.DataFrame | None = None) -> dict:
    """
    信号面评分 (0-100分)。
    - 是否在当日强势股名单中
    - 题材标签数量和质量
    - 所在行业当日涨幅排名
    返回: {score, level, details, signals}
    """
    score = 30  # 基础分（不在强势股名单也能有基础分）
    signals = []
    details = {}
    
    # 拉当日强势股
    if ths_df is None:
        try:
            ths_df = ths_hot_reason()
        except Exception:
            ths_df = pd.DataFrame()
    
    # 检查是否在强势股名单
    if not ths_df.empty and '代码' in ths_df.columns:
        code_in_df = ths_df[ths_df['代码'].astype(str).str.zfill(6) == str(code).zfill(6)]
        if not code_in_df.empty:
            row = code_in_df.iloc[0]
            zhangfu = float(row.get('涨幅%', 0))
            reason = str(row.get('题材归因', ''))
            tags = [t.strip() for t in reason.split('+') if t.strip()]
            details['in_hot_list'] = True
            details['change_pct'] = zhangfu
            details['tags'] = tags
            
            # 涨停直接高分
            if zhangfu >= 9.5:
                score += 40
                signals.append('当日涨停 ✓')
            elif zhangfu >= 5:
                score += 25
            elif zhangfu >= 3:
                score += 15
            elif zhangfu > 0:
                score += 8
            else:
                score -= 5
            
            # 题材丰富度
            tag_count = len(tags)
            details['tag_count'] = tag_count
            if tag_count >= 3:
                score += 15
                signals.append(f'多题材共振({tag_count}个标签)')
            elif tag_count >= 2:
                score += 8
            
            # 题材热度
            try:
                all_tags = []
                for r in ths_df['题材归因'].dropna():
                    all_tags.extend([t.strip() for t in str(r).split('+')])
                from collections import Counter
                tag_cnt = Counter(all_tags)
                tag_heat = sum(tag_cnt.get(t, 0) for t in tags)
                details['tag_heat'] = tag_heat
                if tag_heat > 10:
                    score += 10
                    signals.append('所属题材市场热度高')
            except Exception:
                pass
        else:
            details['in_hot_list'] = False
            signals.append('未入选当日强势股')
    
    # 行业排名（取东财行业板块）
    try:
        comp = industry_comparison(50)
        info = eastmoney_stock_info(code)
        industry_name = info.get('industry', '')
        details['industry'] = industry_name
        for r in comp['top']:
            if r['name'] == industry_name:
                score += 10
                signals.append(f'所属行业涨幅居前(第{r["rank"]}名)')
                break
    except Exception:
        pass
    
    score = max(0, min(100, score))
    
    if score >= 70:
        level = '信号强烈'
    elif score >= 50:
        level = '信号偏多'
    elif score >= 35:
        level = '信号中性'
    else:
        level = '信号偏弱'
    
    return {'score': score, 'level': level, 'details': details, 'signals': signals}
```

### 8.4 基本面评分（权重 10%）

PE消化时间 + PEG + 一致预期增速，0-100 分。

```python
def fundamental_score(code: str) -> dict:
    """
    基本面评分 (0-100分)，基于估值消化 + 增长质量。
    """
    score = 50
    signals = []
    details = {}
    
    try:
        val = full_valuation(code)
        
        # PEG 评分
        peg = val.get('peg')
        details['peg'] = peg
        if peg is not None and peg != float('inf'):
            if peg < 0.5:
                score += 25
                signals.append('PEG<0.5 → 极度低估')
            elif peg < 1.0:
                score += 15
                signals.append('PEG<1 → 低估')
            elif peg < 1.5:
                score += 5
            elif peg > 3:
                score -= 15
                signals.append('PEG>3 → 估值偏高')
        
        # PE消化时间
        digest = val.get('digest_years', 99)
        details['digest_years'] = digest
        if digest <= 1:
            score += 15
            signals.append(f'PE消化仅需{digest}年 → 估值合理')
        elif digest <= 3:
            score += 5
        elif digest > 5:
            score -= 10
            signals.append(f'PE消化需{digest}年 → 估值偏贵')
        
        # CAGR 增速
        cagr = val.get('cagr_pct')
        details['cagr_pct'] = cagr
        if cagr is not None:
            if cagr > 50:
                score += 10
                signals.append(f'一致预期增速>{cagr}% → 高增长')
            elif cagr > 30:
                score += 5
            elif cagr < 10:
                score -= 5
        
        # 机构覆盖
        ac = val.get('analyst_count', 0)
        details['analyst_count'] = ac
        if ac >= 10:
            score += 5
    except Exception:
        pass
    
    score = max(0, min(100, score))
    
    if score >= 70:
        level = '基本面优秀'
    elif score >= 55:
        level = '基本面良好'
    elif score >= 40:
        level = '基本面一般'
    else:
        level = '基本面较差'
    
    return {'score': score, 'level': level, 'details': details, 'signals': signals}
```

### 8.5 综合推荐评分

四因子加权汇总，输出「买入/观望/回避」三级建议。

```python
def comprehensive_recommendation(code: str, verbose: bool = True) -> dict:
    """
    综合多因子推荐评分。
    权重: 技术面40% + 资金面30% + 信号面20% + 基本面10%
    返回: {overall_score, recommendation, breakdown, all_signals}
    """
    print(f"\n{'='*60}")
    print(f"  综合评估: {code}")
    print(f"{'='*60}")
    
    # 各维度评分
    tech = technical_score(code)
    time.sleep(0.3)
    capital = capital_flow_score(code)
    time.sleep(0.3)
    signal_s = signal_score(code)
    time.sleep(0.3)
    funda = fundamental_score(code)
    
    # 加权汇总
    overall = (
        tech['score'] * 0.40 +
        capital['score'] * 0.30 +
        signal_s['score'] * 0.20 +
        funda['score'] * 0.10
    )
    
    # 推荐等级
    if overall >= 75:
        recommendation = '🟢 买入'
        action = '推荐买入 — 技术面+资金面+信号面共振'
    elif overall >= 60:
        recommendation = '🟡 关注'
        action = '可关注，等待更好买点或加仓信号'
    elif overall >= 45:
        recommendation = '⚪ 观望'
        action = '暂时观望，信号不明确'
    elif overall >= 30:
        recommendation = '🟠 减仓'
        action = '建议减仓或规避'
    else:
        recommendation = '🔴 回避'
        action = '强烈建议回避 — 多维度偏空'
    
    # 收集所有信号
    all_signals = []
    for cat, result in [('技术面', tech), ('资金面', capital), ('信号面', signal_s), ('基本面', funda)]:
        for s in result.get('signals', []):
            all_signals.append(f'[{cat}] {s}')
    
    result = {
        'code': code,
        'overall_score': round(overall, 1),
        'recommendation': recommendation,
        'action': action,
        'breakdown': {
            '技术面(40%)': {'score': tech['score'], 'level': tech['level']},
            '资金面(30%)': {'score': capital['score'], 'level': capital['level']},
            '信号面(20%)': {'score': signal_s['score'], 'level': signal_s['level']},
            '基本面(10%)': {'score': funda['score'], 'level': funda['level']},
        },
        'all_signals': all_signals,
    }
    
    if verbose:
        print(f"\n  综合评分: {overall:.1f}/100 → {recommendation}")
        print(f"  建议: {action}")
        print(f"\n  维度分解:")
        for dim, info in result['breakdown'].items():
            bar = '█' * (info['score'] // 5) + '░' * (20 - info['score'] // 5)
            print(f"    {dim}: [{bar}] {info['score']}/100 ({info['level']})")
        if all_signals:
            print(f"\n  关键信号:")
            for s in all_signals[:10]:
                print(f"    • {s}")
    
    return result

# 用法
rec = comprehensive_recommendation("688017")
print(f"\n结论: {rec['recommendation']} | 评分: {rec['overall_score']}/100")
```

### 8.6 趋势预测

基于均线交叉、MACD方向、量价配合，输出短期(1-5天)/中期(1-4周)/长期(1-3月)趋势判断。

```python
def trend_prediction(code: str) -> dict:
    """
    个股趋势预测 — 短期/中期/长期三维度方向判断。
    返回: {short_term, mid_term, long_term, confidence, key_levels, risk_flags}
    """
    bars = client.bars(symbol=code, category=4, offset=250)
    if bars is None or len(bars) < 60:
        return {'error': '数据不足，需要≥60个交易日'}
    
    df = pd.DataFrame(bars)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime').sort_index()
    stock = StockDataFrame.retype(df)
    close = df['close']
    vol = df['vol']
    
    last_close = float(close.iloc[-1])
    
    # ── 趋势判断辅助函数 ──
    def trend_from_ma(close_series):
        """基于均线排列判断趋势"""
        ma5 = close_series.rolling(5).mean().iloc[-1]
        ma10 = close_series.rolling(10).mean().iloc[-1]
        ma20 = close_series.rolling(20).mean().iloc[-1]
        ma60 = close_series.rolling(60).mean().iloc[-1] if len(close_series) >= 60 else None
        last = close_series.iloc[-1]
        
        if ma60 and last > ma5 > ma10 > ma20 > ma60:
            return '强势上涨', 90
        elif last > ma5 > ma10 > ma20:
            return '上涨', 75
        elif last > ma20:
            return '偏多震荡', 55
        elif ma60 and last < ma5 < ma10 < ma20 < ma60:
            return '强势下跌', 10
        elif last < ma5 < ma10 < ma20:
            return '下跌', 25
        elif last < ma20:
            return '偏空震荡', 40
        else:
            return '横盘整理', 50
    
    # ── 短期趋势 (近10日) ──
    short_close = close.iloc[-15:]
    short_vol = vol.iloc[-15:]
    short_trend, short_conf = trend_from_ma(short_close)
    
    # 量价配合检查
    price_up = short_close.iloc[-1] > short_close.iloc[-6]
    vol_up = short_vol.iloc[-5:].mean() > short_vol.iloc[-10:-5].mean() if len(short_vol) >= 10 else False
    if price_up and vol_up:
        short_conf = min(100, short_conf + 10)  # 价涨量增
    elif price_up and not vol_up:
        short_conf = max(0, short_conf - 15)    # 价涨量缩 → 背离
    
    # ── 中期趋势 (近30-60日) ──
    mid_close = close.iloc[-60:]
    mid_trend, mid_conf = trend_from_ma(mid_close)
    mid_vol = vol.iloc[-60:]
    mid_vol_ma20 = mid_vol.rolling(20).mean()
    if len(mid_vol_ma20.dropna()) >= 2:
        if mid_vol_ma20.iloc[-1] > mid_vol_ma20.iloc[-2] * 1.2:
            mid_conf = min(100, mid_conf + 5)  # 放量
    
    # ── 长期趋势 (近120日) ──
    long_close = close.iloc[-120:] if len(close) >= 120 else close
    long_trend, long_conf = trend_from_ma(long_close)
    
    # ── MACD 方向辅助 ──
    macd_series = stock['macd'].dropna()
    macds_series = stock['macds'].dropna()
    macdh_series = stock['macdh'].dropna()
    
    macd_signal = ''
    if len(macdh_series) >= 5:
        # MACD柱趋势
        recent_macdh = macdh_series.iloc[-5:]
        if all(recent_macdh.diff().dropna() > 0):
            macd_signal = 'MACD柱连续放大 → 动能增强'
            short_conf = min(100, short_conf + 8)
        elif all(recent_macdh.diff().dropna() < 0):
            macd_signal = 'MACD柱连续缩小 → 动能减弱'
            short_conf = max(0, short_conf - 8)
        
        # 顶背离/底背离检测
        if len(close) >= 30 and len(macdh_series) >= 30:
            recent_price = close.iloc[-20:]
            recent_macd = macdh_series.iloc[-20:]
            price_high = recent_price.idxmax()
            macd_high = recent_macd.idxmax()
            # 价格新高但MACD柱未新高 → 顶背离
            if price_high > macd_high and recent_price.max() > close.iloc[-30:-10].max():
                macd_signal += '; ⚠ 顶背离信号'
                short_conf = max(0, short_conf - 10)
    
    # ── 关键价位 ──
    high_20 = float(close.iloc[-20:].max())
    low_20 = float(close.iloc[-20:].min())
    high_60 = float(close.iloc[-60:].max()) if len(close) >= 60 else high_20
    low_60 = float(close.iloc[-60:].min()) if len(close) >= 60 else low_20
    ma20_val = float(close.rolling(20).mean().iloc[-1])
    ma60_val = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else None
    
    key_levels = {
        'resistance': round(high_20, 2),
        'resistance_strong': round(high_60, 2),
        'support': round(low_20, 2),
        'support_strong': round(low_60, 2),
        'ma20': round(ma20_val, 2),
        'ma60': round(ma60_val, 2) if ma60_val else None,
    }
    
    # ── 风险标记 ──
    risk_flags = []
    rsi14 = float(stock['rsi_14'].dropna().iloc[-1]) if len(stock['rsi_14'].dropna()) > 0 else None
    if rsi14 and rsi14 > 80:
        risk_flags.append(f'RSI={rsi14:.1f} 严重超买')
    if rsi14 and rsi14 < 20:
        risk_flags.append(f'RSI={rsi14:.1f} 严重超卖')
    
    # 量价背离
    if len(close) >= 20:
        pct_chg_20 = (close.iloc[-1] / close.iloc[-20] - 1) * 100
        vol_ratio = vol.iloc[-5:].mean() / (vol.iloc[-20:].mean() + 1)
        if pct_chg_20 > 10 and vol_ratio < 0.7:
            risk_flags.append('近20日价涨量缩 → 量价背离')
    
    # 距压力位/支撑位距离
    dist_to_resist = (high_20 / last_close - 1) * 100
    dist_to_support = (last_close / low_20 - 1) * 100
    if dist_to_resist < 3:
        risk_flags.append(f'距压力位{high_20}仅{dist_to_resist:.1f}%')
    if dist_to_support < 3:
        risk_flags.append(f'距支撑位{low_20}仅{dist_to_support:.1f}%')
    
    return {
        'code': code,
        'price': last_close,
        'short_term': {'trend': short_trend, 'confidence': short_conf, 'horizon': '1-5个交易日'},
        'mid_term': {'trend': mid_trend, 'confidence': mid_conf, 'horizon': '1-4周'},
        'long_term': {'trend': long_trend, 'confidence': long_conf, 'horizon': '1-3个月'},
        'macd_signal': macd_signal,
        'key_levels': key_levels,
        'risk_flags': risk_flags,
    }

# 用法
pred = trend_prediction("688017")
print(f"当前价: {pred['price']}")
print(f"短期({pred['short_term']['horizon']}): {pred['short_term']['trend']} (置信度{pred['short_term']['confidence']}%)")
print(f"中期({pred['mid_term']['horizon']}): {pred['mid_term']['trend']} (置信度{pred['mid_term']['confidence']}%)")
print(f"长期({pred['long_term']['horizon']}): {pred['long_term']['trend']} (置信度{pred['long_term']['confidence']}%)")
print(f"MACD: {pred['macd_signal']}")
print(f"压力位: {pred['key_levels']['resistance']} / 强压力: {pred['key_levels']['resistance_strong']}")
print(f"支撑位: {pred['key_levels']['support']} / 强支撑: {pred['key_levels']['support_strong']}")
if pred['risk_flags']:
    print(f"风险提示: {'; '.join(pred['risk_flags'])}")
```

### 8.7 批量推荐排名

对候选股票池批量打分排序，输出综合推荐排名表。

```python
def batch_recommend(codes: list[str], top_n: int = 20, min_score: float = 50) -> list[dict]:
    """
    批量多因子评分排名。
    codes: 候选股票代码列表
    top_n: 返回前 N 名
    min_score: 最低入围分数
    
    注意: 东财批量请求需限流，自动 sleep 1.5s/只
    """
    results = []
    for i, code in enumerate(codes):
        try:
            print(f"[{i+1}/{len(codes)}] 评估 {code} ...")
            rec = comprehensive_recommendation(code, verbose=False)
            results.append(rec)
            if i < len(codes) - 1:
                time.sleep(1.5)  # 东财防封
        except Exception as e:
            print(f"  ✗ {code} 评估失败: {e}")
    
    # 按综合评分排序
    results.sort(key=lambda x: x['overall_score'], reverse=True)
    
    # 过滤 + 截断
    filtered = [r for r in results if r['overall_score'] >= min_score][:top_n]
    
    print(f"\n{'='*80}")
    print(f"  综合推荐排名 TOP{len(filtered)}")
    print(f"{'='*80}")
    print(f"{'排名':<6}{'代码':<10}{'评分':<8}{'建议':<12}{'技术':<6}{'资金':<6}{'信号':<6}{'基本':<6}")
    print(f"{'-'*60}")
    for i, r in enumerate(filtered):
        bd = r['breakdown']
        print(f"{i+1:<6}{r['code']:<10}{r['overall_score']:<8}{r['recommendation']:<12}"
              f"{bd['技术面(40%)']['score']:<6}{bd['资金面(30%)']['score']:<6}"
              f"{bd['信号面(20%)']['score']:<6}{bd['基本面(10%)']['score']:<6}")
    
    return filtered

# 用法: 对同花顺当日强势股 TOP30 做综合排序
# df_hot = ths_hot_reason()
# top_codes = df_hot['代码'].head(30).tolist()
# ranked = batch_recommend(top_codes, top_n=15, min_score=55)
```

## 估值计算公式

### 前向PE

```python
def forward_pe(price: float, eps_forecast: float) -> float:
    """前向PE = 当前股价 / 未来年度一致预期EPS"""
    if eps_forecast <= 0:
        return float("inf")
    return price / eps_forecast
```

### PE消化时间

```python
import math

def pe_digestion(current_pe: float, cagr: float, target_pe: float = 30) -> float:
    """
    当前PE消化到目标PE需要多少年。
    target_pe 固定30x（A股成长股合理估值锚点）。
    cagr: 用 下一年EPS / 当年EPS - 1
    """
    if current_pe <= target_pe:
        return 0.0
    if cagr <= 0:
        return float("inf")
    return math.log(current_pe / target_pe) / math.log(1 + cagr)
```

### PEG

```python
def calc_peg(pe: float, cagr: float) -> float:
    """
    PEG = 前向PE / (CAGR * 100)
    PEG < 1   → 便宜
    PEG 1-1.5 → 合理
    PEG > 1.5 → 贵
    """
    if cagr <= 0:
        return float("inf")
    return pe / (cagr * 100)
```

### 投资框架速查

```
壁垒 → 增速 → PE消化 → PEG校验

1. 有壁垒吗？(tech_moat / capacity_moat) → 没有则排除
2. 增速多少？(CAGR > 30% 才有意义)
3. PE多久消化到30x？(< 2年合理, > 4年太贵)
4. PEG多少？(< 1 便宜, 1-1.5 合理, > 1.5 贵)

30x PE 锚点: A股成长股的合理估值重力线，所有行业统一用30x。
期权定价例外: PEG > 3 但壁垒极深时，本质是看涨期权，不适用PEG框架。
```

---

## 完整调研流程

### 流程 A: 单票完整估值（30秒）

```python
import requests
import urllib.request
import math
import pandas as pd

def full_valuation(code: str) -> dict:
    """单票完整估值分析"""
    # 1. 腾讯实时行情
    prefix = "sh" if code.startswith(("6","9")) else ("bj" if code.startswith("8") else "sz")
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")
    vals = data.split('"')[1].split("~")
    price = float(vals[3])
    mcap = float(vals[44])
    pe_ttm = float(vals[39]) if vals[39] else 0
    pb = float(vals[46]) if vals[46] else 0

    # 2. 机构一致预期（直连同花顺）
    df = ths_eps_forecast(code)
    eps_cur = eps_next = None
    analyst_count = 0
    if not df.empty and len(df.columns) >= 3:
        # 解析表格（列结构因页面可能变化，取前两行数据行）
        try:
            for i, row in df.iterrows():
                if i == 0:
                    eps_cur = float(row.iloc[2]) if pd.notna(row.iloc[2]) else None
                    analyst_count = int(row.iloc[1]) if pd.notna(row.iloc[1]) else 0
                elif i == 1:
                    eps_next = float(row.iloc[2]) if pd.notna(row.iloc[2]) else None
        except (ValueError, IndexError):
            pass

    # 3. 估值指标
    pe_fwd = price / eps_cur if eps_cur else float("inf")
    cagr = (eps_next / eps_cur - 1) if (eps_cur and eps_next) else 0
    peg = pe_fwd / (cagr * 100) if cagr > 0 else float("inf")
    digest = (
        math.log(pe_fwd / 30) / math.log(1 + cagr)
        if pe_fwd > 30 and cagr > 0 else 0
    )

    return {
        "name": vals[1],
        "price": price,
        "mcap_yi": mcap,
        "pe_ttm": pe_ttm,
        "pb": pb,
        "eps_cur": eps_cur,
        "eps_next": eps_next,
        "pe_fwd": round(pe_fwd, 1) if eps_cur else None,
        "cagr_pct": round(cagr * 100, 0) if cagr else None,
        "peg": round(peg, 2) if peg != float("inf") else None,
        "digest_years": round(digest, 1),
        "analyst_count": analyst_count,
    }

# 用法
result = full_valuation("688017")
print(result)
```

### 流程 B: 批量估值对比

```python
stocks = ["688017", "300308", "300476", "002463"]
for code in stocks:
    try:
        r = full_valuation(code)
        print(f"{r['name']}({code}): PE_fwd={r['pe_fwd']}x PEG={r['peg']} 消化={r['digest_years']}年 覆盖={r['analyst_count']}家")
    except Exception as e:
        print(f"{code}: 失败 - {e}")
```

### 流程 C: 主题研报批量检索

```python
# Step 1: iwencai 多 query 语义搜索
queries = [
    "人形机器人产业链深度 2026",
    "人形机器人减速器 丝杠",
    "特斯拉Optimus 国产供应链",
]
seen_uids = set()
all_articles = []
for q in queries:
    arts = iwencai_search(q, channel="report", size=50)
    for a in arts:
        uid = a.get("uid", "")
        if uid not in seen_uids:
            seen_uids.add(uid)
            all_articles.append(a)
print(f"共 {len(all_articles)} 篇去重后研报")

# Step 2: 东财补充同标的研报 + PDF
for a in all_articles[:10]:
    stocks = a.get("stock_infos") or []
    for s in stocks:
        stock_code = s.get("code", "")
        if stock_code:
            em = eastmoney_reports(stock_code, max_pages=1)
            print(f"  {stock_code}: 东财 {len(em)} 篇")
```

### 流程 D: 新标的快速调研（V3.0 增强版）

```python
code = "688017"

# 1. 有无机构覆盖？
forecast = ths_eps_forecast(code)
print(f"机构覆盖: {'有' if not forecast.empty else '无'}")

# 2. 实时估值
quotes = tencent_quote([code])
q = quotes[code]
print(f"PE={q['pe_ttm']} PB={q['pb']} 市值={q['mcap_yi']}亿")

# 3. PE消化 → 用 full_valuation()
# 4. PEG校验

# 5. 概念板块归属
blocks = baidu_concept_blocks(code)
print(f"概念: {', '.join(blocks['concept_tags'][:10])}")

# 6. 资金流向（百度分钟级）
flow = baidu_fund_flow_history(code)
if flow:
    recent = flow[0]
    print(f"最近主力净流入: {recent['mainIn']}万")

# 7. 资金流向（东财120日）
flow_120 = stock_fund_flow_120d(code)
if flow_120:
    total = sum(d["main_net"] for d in flow_120[-20:])
    print(f"近20日主力累计净流入: {total/1e8:.2f}亿")

# 8. 龙虎榜
dtb = dragon_tiger_board(code, "2026-05-17")
print(f"近30日上龙虎榜: {len(dtb['records'])} 次")

# 9. 解禁预警
lockup = lockup_expiry(code, "2026-05-17")
print(f"未来90天待解禁: {len(lockup['upcoming'])} 批")

# 10. 融资融券
margin = margin_trading(code, page_size=5)
if margin:
    print(f"最新融资余额: {margin[0]['rzye']/1e8:.2f}亿")

# 11. 股东户数
holders = holder_num_change(code)
if holders:
    print(f"最新股东数: {holders[0]['holder_num']} 环比{holders[0]['change_ratio']}%")
```

### 流程 E: 智能选股推荐（V3.3 新增）

综合多因子评分批量选股，输出排序推荐列表。

```python
# ── 场景1: 从当日强势股中筛选 ──
print("Step 1: 拉取当日强势股名单...")
df_hot = ths_hot_reason()
print(f"  当日强势股: {len(df_hot)} 只")

# 选出涨幅 3%-8%（非涨停板仍有空间）+ 换手率 3%-20%（活跃但不过度）
candidates = df_hot[
    (df_hot['涨幅%'].astype(float) >= 3) &
    (df_hot['涨幅%'].astype(float) <= 8) &
    (df_hot['换手率%'].astype(float) >= 3) &
    (df_hot['换手率%'].astype(float) <= 20)
]
print(f"  初步筛选: {len(candidates)} 只")

# 对候选股做多因子评分
codes = candidates['代码'].head(20).tolist()
ranked = batch_recommend(codes, top_n=10, min_score=55)

# ── 场景2: 自定义股票池对比 ──
my_watchlist = ["688017", "300476", "002463", "300308", "600519"]
print("\n自定义股票池综合评分:")
results = []
for code in my_watchlist:
    name = tencent_quote([code]).get(code, {}).get('name', code)
    try:
        rec = comprehensive_recommendation(code, verbose=False)
        results.append({'name': name, **rec})
    except Exception as e:
        print(f"  {code} {name}: 失败 - {e}")

results.sort(key=lambda x: x['overall_score'], reverse=True)
for i, r in enumerate(results):
    print(f"  {i+1}. {r['name']}({r['code']}): {r['overall_score']}分 → {r['recommendation']}")

# ── 场景3: 按题材关键词筛选强势股 ──
keyword = "人形机器人"
df_target = df_hot[df_hot['题材归因'].str.contains(keyword, na=False)]
print(f"\n'{keyword}'题材强势股: {len(df_target)} 只")
target_codes = df_target['代码'].head(10).tolist()
if target_codes:
    ranked = batch_recommend(target_codes, top_n=5)
```

### 流程 F: 趋势预测 + 操作建议（V3.3 新增）

结合趋势预测和技术面评分，输出可操作的建议。

```python
def full_prediction_report(code: str) -> dict:
    """完整趋势预测报告 — 含操作建议"""
    # 1. 基本信息
    quotes = tencent_quote([code])
    q = quotes.get(code, {})
    name = q.get('name', code)
    price = q.get('price', 0)
    
    print(f"\n{'='*60}")
    print(f"  {name}({code}) 趋势预测报告")
    print(f"  当前价: {price}元  PE(TTM): {q.get('pe_ttm', 'N/A')}  市值: {q.get('mcap_yi', 'N/A')}亿")
    print(f"{'='*60}")
    
    # 2. 趋势预测
    pred = trend_prediction(code)
    if 'error' in pred:
        print(f"  ✗ {pred['error']}")
        return pred
    
    print(f"\n  📊 趋势研判:")
    st = pred['short_term']
    mt = pred['mid_term']
    lt = pred['long_term']
    
    def trend_icon(trend):
        if '上涨' in trend: return '📈'
        elif '下跌' in trend: return '📉'
        else: return '📊'
    
    print(f"    短期({st['horizon']}): {trend_icon(st['trend'])} {st['trend']} (置信度{st['confidence']}%)")
    print(f"    中期({mt['horizon']}): {trend_icon(mt['trend'])} {mt['trend']} (置信度{mt['confidence']}%)")
    print(f"    长期({lt['horizon']}): {trend_icon(lt['trend'])} {lt['trend']} (置信度{lt['confidence']}%)")
    
    if pred['macd_signal']:
        print(f"\n  🔧 MACD: {pred['macd_signal']}")
    
    # 3. 关键价位
    kl = pred['key_levels']
    print(f"\n  🎯 关键价位:")
    print(f"    压力位: {kl['resistance']} (近20日高) / {kl['resistance_strong']} (近60日高)")
    print(f"    支撑位: {kl['support']} (近20日低) / {kl['support_strong']} (近60日低)")
    print(f"    MA20: {kl['ma20']}" + (f"  MA60: {kl['ma60']}" if kl.get('ma60') else ""))
    
    # 4. 风险提示
    if pred['risk_flags']:
        print(f"\n  ⚠ 风险提示:")
        for flag in pred['risk_flags']:
            print(f"    • {flag}")
    
    # 5. 综合推荐
    rec = comprehensive_recommendation(code, verbose=True)
    
    # 6. 操作建议
    print(f"\n  📋 操作建议:")
    if st['trend'] in ('强势上涨', '上涨') and rec['overall_score'] >= 60:
        print(f"    ✅ 短期趋势向好，综合评分{rec['overall_score']}分，可考虑介入")
        if kl['support'] > 0:
            print(f"    💡 理想买点: 回踩 {kl['support']} 附近（近20日支撑）")
        if kl['resistance'] > 0:
            print(f"    🎯 第一目标: {kl['resistance']}")
    elif st['trend'] in ('强势下跌', '下跌') and rec['overall_score'] < 45:
        print(f"    ❌ 短期趋势偏空，综合评分{rec['overall_score']}分，建议观望或减仓")
    else:
        print(f"    ⚡ 趋势不明确，综合评分{rec['overall_score']}分，等待方向确认")
    
    return {**pred, 'recommendation': rec}

# 用法
report = full_prediction_report("688017")
```

---

## 数据源优先级

| 优先级 | 数据源 | 用途 | 可靠性 | 封IP风险 |
|--------|--------|------|--------|---------|
| 1 | **mootdx** (TCP) | K线+五档盘口+逐笔成交+财务快照+F10 | 极稳定 | 极低 |
| 2 | **腾讯财经** (HTTP) | 实时PE/PB/市值/换手率/涨跌停/指数/ETF | 稳定 | 低 |
| 3 | **东财 datacenter** (HTTP) | 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红/个股信息 | 稳定 | 低 |
| 4 | **东财 push2/push2his** (HTTP) | 行业板块/个股资金流分钟级+120日 | 稳定 | 低 |
| 5 | **iwencai** (OpenAPI) | NL主题搜索研报(唯一能力) | 需X-Claw Header | 低 |
| 6 | **东财 reportapi/PDF** (HTTP) | 完整研报图表、评级 | 稳定 | 低 |
| 7 | **同花顺热点** (HTTP) | 当日强势股+题材归因 reason tags | 稳定 73ms | 极低（零鉴权） |
| 8 | **同花顺 hsgtApi** (HTTP) | 北向资金分钟级+自缓存历史 | 稳定 | 极低（零鉴权） |
| 9 | **百度股市通** (HTTP) | 概念板块+K线带MA | 稳定 | 极低（零鉴权） |
| 10 | **新浪财经** (HTTP) | 资产负债表/利润表/现金流量表 | 稳定 | 低 |
| 11 | **同花顺 basic** (HTTP) | 一致预期EPS | 稳定(需UA) | 低 |
| 12 | **财联社** (HTTP) | 全市场实时电报 | 稳定 | 低 |
| 13 | **巨潮 cninfo** (HTTP) | 公告全文检索+下载 | 稳定 | 低 |

**原则：** 行情走 mootdx+腾讯（不封IP），研报走东财+iwencai，资金面走东财 datacenter+push2，**信号层走同花顺+百度+东财直连接口**。全部直连 HTTP，零第三方数据封装依赖。

---

## FAQ

### Q: mootdx 和腾讯有什么区别？
A: 互补关系。mootdx = 交易层（价格+盘口+K线），腾讯 = 估值层（PE/PB/市值/换手率/涨跌停价）。两者都不封IP。

### Q: V3.0 为什么移除 akshare？
A: akshare 本质是对东财/同花顺/新浪等公开 API 的封装，中间层增加了故障点（版本兼容 bug、pandas 3.0 ArrowInvalid 等）。V3.0 直连底层 HTTP API，零中间依赖，更稳定可控。

### Q: iwencai 返回 401
A: 检查两点：(1) API Key 是否有效 (2) 是否携带了 X-Claw-* Headers。SkillHub 2.0 后必须带 X-Claw Headers，否则一律 401。

### Q: 同花顺一致预期 ths_eps_forecast 返回空
A: 该股票无机构覆盖。小盘/次新/ST 股常见。可 fallback 到东财 reportapi 里的 predictThisYearEps 字段。

### Q: 东财 PDF 下载 403
A: 必须带 `Referer: https://data.eastmoney.com/` header。

### Q: 腾讯 API 返回乱码
A: 编码是 GBK，必须 `decode("gbk")`。

### Q: 腾讯 API 字段 43 是 PB 吗？
A: **不是！** 43=振幅%，46=PB。网上很多教程写错了，这里是实测校准结果。

### Q: iwencai search 返回条数太少
A: `size` 参数默认 10，调到 50。隐藏参数，文档未写明但实测可用。

### Q: 哪些数据源需要 API Key？
A: 只有 iwencai 需要。mootdx / 腾讯 / 东财 / 同花顺 / 百度股市通 / 新浪 / 巨潮 / 财联社全部免费无 key。

### Q: 同花顺热点接口需要 cookie 吗？
A: **不需要**。仅 User-Agent 即可，零鉴权 73ms 拿到 ~125 只当日强势股。但**不要去打 search.10jqka.com.cn 的 iwencai NL 选股接口** —— 那个有 hexin-v cookie JS 签名鉴权，跟热点接口完全两码事。

### Q: 百度股市通 ResultCode 有时是 0 有时是 "0"？
A: 已知坑。`ResultCode` 返回类型不稳定——有时 int，有时 string。代码里必须用 `str(d.get("ResultCode", -1)) != "0"` 统一比较。

### Q: 北向资金历史数据为什么只有最近几天？
A: 本地自缓存模式。eastmoney 全系北向数据自 2024-08 起断供（净买额字段返回 NaN/0）。每次调用实时 API 后自动写入本地 CSV，历史越跑越丰富。

### Q: 行业板块为什么从同花顺换成东财？
A: 同花顺 `stock_board_industry_summary_ths` 接口 2026 年初加了反爬 401（需要登录态）。东财 push2 行业板块数据（`m:90+t:2`）是完美替代，零鉴权且字段更丰富。

### Q: 在海外服务器跑，mootdx 接口超时？
A: mootdx 走 TCP 直连通达信行情服务器，需国内 IP 才稳定。海外环境建议走代理。腾讯财经和百度股市通不受影响。

### Q: 不用 Claude Code，能用吗？
A: 能。SKILL.md 本质是 Markdown + 内嵌 Python 代码。Codex、OpenClaw 或任何 AI 编程助手都能读取。你也可以直接把 Python 代码段复制出来在自己的脚本里跑。

---

## 安装说明

```bash
# 1. 创建 skill 目录
mkdir -p ~/.claude/skills/a-stock-data

# 2. 将本文件复制为 SKILL.md
cp SKILL.md ~/.claude/skills/a-stock-data/SKILL.md

# 3. 安装 Python 依赖
pip install mootdx requests pandas stockstats

# 4. (可选) 配置 iwencai API Key
export IWENCAI_API_KEY="your_key_here"

# 5. 启动 Claude Code，说"查一下688017的估值"即可自动激活
```

---

> 📦 https://github.com/simonlin1212/a-stock-data — Star ⭐ 是最好的支持
