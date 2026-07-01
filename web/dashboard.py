"""
A股策略可视化仪表盘 v3 — 综合选股 + 进度动画 + 协调UI
"""
import json, sys, os, time, threading, queue, re, itertools, io, base64
from flask import Flask, Response, render_template_string, jsonify, request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core.db_manager as db_manager
import core.scheduler as bg_scheduler
from core.config import FLASK_HOST, FLASK_PORT

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRATEGIES_DIR = os.path.join(BASE_DIR, "strategies")

STRATEGIES = {
    "momentum":    {"name": "动量策略", "file": "momentum_v4.py",    "icon": "\U0001f680", "color": "#ff6b6b"},
    "oversold":    {"name": "超跌反弹", "file": "oversold_v4.py",    "icon": "\U0001f4c9", "color": "#48dbfb"},
    "volume_price":{"name": "量价共振", "file": "volume_price_resonance_v4.py", "icon": "\U0001f4ca", "color": "#feca57"},
    "breakout":    {"name": "均线突破", "file": "breakout_strategy.py","icon": "\U0001f53a", "color": "#00d2a0"},
}

ALL_ORDER = ["momentum", "oversold", "volume_price", "breakout"]
_run_status = {}
_run_lock = threading.Lock()


def parse_strategy_output(lines):
    result = {"market_env": "", "sentiment": "", "stocks": [], "recommendation": None}
    stock_re = re.compile(r"#(\d+)\s+(.+?)\((\d{6})\)\s+([\d.]+)\s+今日([+-][\d.]+)%\s+评分(\d+)")

    for line in lines:
        ls = line.strip()
        if not ls: continue
        if "大盘:" in ls and "情绪:" in ls: result["market_env"] = ls
        if "涨停" in ls and ("炸板率" in ls or "温度" in ls): result["sentiment"] = ls
        if "最终推荐:" in ls:
            m = re.search(r"最终推荐:\s*(.+?)\((\d{6})\)\s*(\d+)/100", ls)
            if m: result["recommendation"] = {"name": m.group(1), "code": m.group(2), "score": int(m.group(3))}
        if result["recommendation"]:
            rc = result["recommendation"]
            for pat, key in [(r"现价:\s*([\d.]+)","price"),(r"今日涨幅:\s*([+-][\d.]+)%","chg"),
                             (r"今日跌幅:\s*([-][\d.]+)%","chg"),
                             (r"换手率:\s*([\d.]+)%","turnover"),(r"RPS20:\s*([\d.]+)","rps20"),
                             (r"PE:\s*([\d.]+)","pe")]:
                m = re.search(pat, ls)
                if m: rc[key] = float(m.group(1))
            m = re.search(r"目标:\s*([\d.]+).*?([\d.]+)", ls)
            if m: rc["target_low"] = float(m.group(1)); rc["target_high"] = float(m.group(2))
            m = re.search(r"止损:\s*([\d.]+)", ls)
            if m: rc["stop_price"] = float(m.group(1))

        sm = stock_re.match(ls)
        if sm:
            result["stocks"].append({"rank":int(sm.group(1)),"name":sm.group(2).strip(),
                "code":sm.group(3),"price":float(sm.group(4)),"chg":float(sm.group(5)),
                "score":int(sm.group(6)),"source":""})
        elif result["stocks"] and any(kw in ls for kw in ["RSI","量比","换手","RPS","PE","BOLL","大单","涨停基因","乖离","下影","MA5","MA20","MACD"]):
            last = result["stocks"][-1]
            for pat, key in [(r"RSI6=([\d.]+)","rsi6"),(r"RSI14=([\d.]+)","rsi14"),
                             (r"量比=([\d.]+)x","volume_ratio"),(r"换手=([\d.]+)%","turnover"),
                             (r"RPS20=([\d.]+)","rps20"),(r"乖离=([\d.]+)%","deviation"),
                             (r"涨停基因=(\d+)次","limit_up_count"),(r"PE=([\d.]+)","pe"),
                             (r"BOLL=([\d.]+)%","boll_pos")]:
                m2 = re.search(pat, ls)
                if m2: last[key] = float(m2.group(1))
            m3 = re.search(r"大单=(\d+)万", ls)
            if m3: last["main_net"] = float(m3.group(1))
    return result


def _save_run_to_db(strategy_key, result):
    """将策略运行结果保存到数据库"""
    try:
        info = STRATEGIES[strategy_key]
        stocks = result.get("stocks", [])
        rec = result.get("recommendation")
        if rec and rec.get("code"):
            # 在 stocks 中标记推荐股
            for s in stocks:
                if s.get("code") == rec.get("code"):
                    s["is_recommendation"] = True
        run_id = db_manager.save_strategy_run(
            strategy_key, info["name"], result,
            sentiment=None, env_data=None
        )
        if run_id and stocks:
            db_manager.save_stock_picks(run_id, strategy_key, stocks)
            print(f"[DB] 已保存 {strategy_key}: run_id={run_id}, stocks={len(stocks)}", flush=True)
    except Exception as e:
        print(f"[DB] 保存失败 {strategy_key}: {e}", flush=True)


class _LineWriter:
    """自定义stdout，将每行输出放入队列实现实时流式传输"""
    def __init__(self, q):
        self.q = q
        self._buf = ""
    def write(self, s):
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self.q.put(line)
    def flush(self):
        if self._buf:
            self.q.put(self._buf)
            self._buf = ""


def run_strategy_stream(strategy_key):
    info = STRATEGIES[strategy_key]
    script = os.path.join(STRATEGIES_DIR, info["file"])
    with _run_lock: _run_status[strategy_key] = {"running":True,"progress":0,"done":False}
    def emit(etype,**kw): return f"data: {json.dumps(dict(type=etype,**kw),ensure_ascii=False)}\n\n"
    try:
        q = queue.Queue()
        writer = _LineWriter(q)
        error_occurred = {"flag": False, "msg": ""}

        def _run_script():
            old_stdout = sys.stdout
            old_cwd = os.getcwd()
            sys.stdout = writer
            os.chdir(BASE_DIR)
            try:
                with open(script, "r", encoding="utf-8") as sf:
                    code = compile(sf.read(), script, "exec")
                exec(code, {"__name__": "__main__", "__file__": script})
            except Exception as e:
                import traceback
                error_occurred["flag"] = True
                error_occurred["msg"] = str(e)
                traceback.print_exc()
            finally:
                sys.stdout = old_stdout
                os.chdir(old_cwd)
                writer.flush()
                q.put(None)

        t = threading.Thread(target=_run_script, daemon=True)
        t.start()

        all_lines = []; last_p = 0
        while True:
            try:
                line = q.get(timeout=0.2)
            except queue.Empty:
                if not t.is_alive():
                    try: line = q.get_nowait()
                    except queue.Empty: break
                continue
            if line is None:
                break
            if error_occurred["flag"]:
                yield emit("error", msg=error_occurred["msg"])
                break
            all_lines.append(line)
            progress = last_p
            if "[0/7]" in line: progress = 5
            elif "[1/7]" in line: progress = 10
            elif "[2/7]" in line: progress = 20
            elif "[3/7]" in line: progress = 30
            elif "[4/7]" in line: progress = 45
            elif "[5/7]" in line: progress = 60
            elif "[6/7]" in line: progress = 80
            elif "[7/7]" in line: progress = 90
            elif "最终推荐" in line: progress = 95
            elif "以上为技术面分析" in line: progress = 100
            if progress > last_p: last_p = progress
            with _run_lock: _run_status[strategy_key] = {"running":True,"progress":progress,"done":False}
            yield emit("log", line=line, progress=progress)

        t.join(timeout=5)
        if error_occurred["flag"]:
            with _run_lock: _run_status[strategy_key] = {"running":False,"progress":0,"done":True,"error":error_occurred["msg"]}
            yield emit("error", msg=error_occurred["msg"])
        else:
            result = parse_strategy_output(all_lines)
            with _run_lock: _run_status[strategy_key] = {"running":False,"progress":100,"done":True,"result":result}
            # 异步保存到数据库
            threading.Thread(target=_save_run_to_db, args=(strategy_key, result), daemon=True).start()
            yield emit("done", result=result)
    except Exception as e:
        import traceback; traceback.print_exc()
        yield emit("error", msg=str(e))
        with _run_lock: _run_status[strategy_key] = {"running":False,"progress":0,"done":True,"error":str(e)}


@app.route("/")
def index():
    template_path = os.path.join(BASE_DIR, "web", "templates", "dashboard.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    return render_template_string(html, strategies=STRATEGIES, all_order=ALL_ORDER)


@app.route("/api/run/<strategy_key>")
def api_run(strategy_key):
    if strategy_key not in STRATEGIES: return jsonify({"error":"unknown"}), 404
    return Response(run_strategy_stream(strategy_key), mimetype="text/event-stream; charset=utf-8",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})


@app.route("/api/run-all")
def api_run_all():
    """综合选股: 顺序运行全部4个策略, 合并结果"""
    def generate():
        merged = {"stocks": [], "recommendations": [], "market_env": "", "sentiment": "", "total": 4, "done_count": 0}
        yield f"data: {json.dumps({'type':'all_start','total':4},ensure_ascii=False)}\n\n"
        for idx, key in enumerate(ALL_ORDER):
            info = STRATEGIES[key]
            yield f"data: {json.dumps({'type':'strategy_start','key':key,'name':info['name'],'icon':info['icon'],'color':info['color'],'idx':idx+1,'total':4},ensure_ascii=False)}\n\n"
            for chunk in run_strategy_stream(key):
                if chunk.startswith("data: "):
                    try:
                        data = json.loads(chunk[6:])
                        if data.get("type") == "log":
                            yield f"data: {json.dumps({'type':'all_log','key':key,'line':data['line'],'progress':data['progress']},ensure_ascii=False)}\n\n"
                        elif data.get("type") == "done":
                            r = data.get("result", {})
                            merged["market_env"] = r.get("market_env") or merged["market_env"]
                            merged["sentiment"] = r.get("sentiment") or merged["sentiment"]
                            # 标记来源并合并
                            for s in r.get("stocks", []):
                                s["source"] = info["icon"] + " " + info["name"]
                            merged["stocks"].extend(r.get("stocks", []))
                            if r.get("recommendation"):
                                r["recommendation"]["source_key"] = key
                                r["recommendation"]["source_name"] = info["name"]
                                r["recommendation"]["source_icon"] = info["icon"]
                                merged["recommendations"].append(r["recommendation"])
                            merged["done_count"] = idx + 1
                            yield f"data: {json.dumps({'type':'strategy_done','key':key,'done_count':idx+1,'total':4,'result':r},ensure_ascii=False)}\n\n"
                    except: pass
        # 去重、排序合并结果
        seen = set()
        uniq_stocks = []
        for s in merged["stocks"]:
            if s["code"] not in seen:
                seen.add(s["code"])
                uniq_stocks.append(s)
        uniq_stocks.sort(key=lambda x: x["score"], reverse=True)
        merged["stocks"] = uniq_stocks[:60]
        merged["recommendations"].sort(key=lambda x: x["score"], reverse=True)
        merged["all_done"] = True
        yield f"data: {json.dumps({'type':'all_done','result':merged},ensure_ascii=False)}\n\n"
    return Response(generate(), mimetype="text/event-stream; charset=utf-8",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})


@app.route("/api/chart/<code>")
def api_chart(code):
    """股票快照行情图: K线(60日) + 均线 + 成交量, 返回base64 PNG"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.font_manager as fm
        # 中文字体: 必须在 import pyplot 之前设置，清除缓存确保生效
        try: fm._load_fontmanager(try_read_cache=False)
        except: pass
        font_paths = [
            'C:/Windows/Fonts/msyh.ttc',   # 微软雅黑
            'C:/Windows/Fonts/simsun.ttc',  # 宋体
            'C:/Windows/Fonts/simhei.ttf',  # 黑体
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                fm.fontManager.addfont(fp)
                break
        # 使用英文标签, 避免中文字体缺失导致缺字
        matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans']
        matplotlib.rcParams['axes.unicode_minus'] = False

        import matplotlib.pyplot as plt
        import mplfinance as mpf
        import pandas as pd
        from mootdx.quotes import Quotes
        from core.stock_utils import calc_technical_indicators
        client = Quotes.factory(market='std')

        bars = client.bars(symbol=code, category=4, offset=70)
        if bars is None or len(bars) < 20:
            return jsonify({"error": "K线数据不足"}), 404

        df = pd.DataFrame(bars)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime').sort_index()
        df = df.rename(columns={'open':'Open','close':'Close','high':'High','low':'Low','vol':'Volume'})

        ind = calc_technical_indicators(bars)
        name = code  # 使用代码作为fallback
        try:
            from core.stock_utils import get_name_batch
            nm = get_name_batch([code])
            if nm: name = nm.get(code, code)
        except: pass

        chg_str = ""
        if len(df) >= 2:
            chg = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100
            chg_str = f"{chg:+.1f}%"

        colors = mpf.make_marketcolors(up='#ef4444',down='#22c55e',edge='inherit',wick='inherit',volume={'up':'#ef4444','down':'#22c55e'},alpha=0.8)
        style = mpf.make_mpf_style(marketcolors=colors,gridcolor='#e5e7eb',facecolor='#fafafa',figcolor='#fafafa')

        apds = [
            mpf.make_addplot(df['Volume'],type='bar',width=0.7,alpha=0.35,color='#9ca3af',panel=1,secondary_y=False),
        ]
        fig, axes = mpf.plot(df, type='candle', style=style, mav=(5,10,20),
                 volume=False, addplot=apds, panel_ratios=(3,1), figsize=(10,5.5),
                 title=f"\n{code}  Price:{ind['cur']:.2f}  Chg:{chg_str}  RSI14:{ind['rsi14']:.0f}  Vol:{ind.get('vr',1):.1f}x",
                 returnfig=True, warn_too_much_data=200)

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        return jsonify({"image": "data:image/png;base64," + img_b64, "name": name, "code": code})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/kline/<code>")
def api_kline(code):
    """交互式K线数据: 返回 JSON 格式 OHLC + 均线 + MACD + RSI
    支持 period 参数: minute(分时) | day(日K) | week(周K) | month(月K)
    """
    try:
        period = request.args.get("period", "day")
        category_map = {"minute": 0, "day": 4, "week": 5, "month": 6}
        category = category_map.get(period, 4)
        offset_map = {"minute": 240, "day": 120, "week": 80, "month": 60}
        offset = offset_map.get(period, 120)

        from mootdx.quotes import Quotes
        import pandas as pd
        import numpy as np

        client = Quotes.factory(market='std')
        bars = client.bars(symbol=code, category=category, offset=offset)

        if bars is None or len(bars) < 10:
            return jsonify({"error": "K线数据不足"}), 404

        df = pd.DataFrame(bars)
        # mootdx 返回的 bars 可能 datetime 同时是 index 和列，需要修复歧义
        try:
            dup_cols = set(df.index.names) & set(df.columns)
            for col in dup_cols:
                if col and col != '':
                    df = df.drop(columns=[col])
        except:
            pass
        # 确保 datetime 不是索引
        if df.index.name == 'datetime' or 'datetime' in (df.index.names or []):
            df = df.reset_index()
        # 确保有 datetime 列
        if 'datetime' not in df.columns:
            for col in df.columns:
                if 'datetime' in str(col).lower() or 'date' in str(col).lower():
                    df = df.rename(columns={col: 'datetime'})
                    break
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.sort_values('datetime')

        # 分时数据字段可能不同
        if period == "minute":
            # 分时: 直接用 price/vol
            prices = df['price'].astype(float).tolist()
            vols = df['vol'].astype(float).tolist()
            dates = df['datetime'].astype(str).tolist()
            last_price = float(prices[-1]) if prices else 0
            prev_close = float(bars.iloc[0].get('last_close', last_price)) if len(bars) > 0 else last_price
            chg_pct = round((last_price / prev_close - 1) * 100, 2) if prev_close > 0 else 0

            result = {
                "code": code, "period": "minute",
                "dates": dates, "prices": prices, "volumes": vols,
                "last_price": last_price, "prev_close": prev_close,
                "chg_pct": chg_pct,
            }
        else:
            # K线数据
            o = df['open'].astype(float)
            h = df['high'].astype(float)
            l = df['low'].astype(float)
            c = df['close'].astype(float)
            v = df['vol'].astype(float)
            dates = df['datetime'].astype(str).tolist()

            # 均线
            ma5 = c.rolling(5).mean().round(2).tolist()
            ma10 = c.rolling(10).mean().round(2).tolist()
            ma20 = c.rolling(20).mean().round(2).tolist()
            ma60 = c.rolling(60).mean().round(2).tolist()

            # MACD
            ema12 = c.ewm(span=12).mean()
            ema26 = c.ewm(span=26).mean()
            dif = (ema12 - ema26).round(3).tolist()
            dea = dif.copy()
            for i in range(9, len(dea)):
                dea[i] = round(sum(dif[i-8:i+1]) / 9, 3)
            macd_hist = [(dif[i] - dea[i]) * 2 for i in range(len(dif))]
            macd_hist = [round(x, 3) for x in macd_hist]

            # RSI14
            delta = c.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta).where(delta < 0, 0.0)
            avg_gain = gain.rolling(14).mean()
            avg_loss = loss.rolling(14).mean()
            rs = avg_gain / avg_loss.replace(0, 1e-9)
            rsi14 = (100 - (100 / (1 + rs))).round(1).tolist()

            # KDJ
            low_n = l.rolling(9).min()
            high_n = h.rolling(9).max()
            rsv = ((c - low_n) / (high_n - low_n).replace(0, 1)).clip(0, 1) * 100
            k_val = rsv.ewm(com=2).mean().round(1).tolist()
            d_val = pd.Series(k_val).ewm(com=2).mean().round(1).tolist()
            j_val = [round(3 * k_val[i] - 2 * d_val[i], 1) for i in range(len(k_val))]

            last_price = float(c.iloc[-1])
            prev_close = float(c.iloc[-2]) if len(c) >= 2 else last_price
            chg_pct = round((last_price / prev_close - 1) * 100, 2) if prev_close > 0 else 0

            result = {
                "code": code, "period": period,
                "dates": dates,
                "open": o.tolist(), "high": h.tolist(),
                "low": l.tolist(), "close": c.tolist(),
                "volume": v.tolist(),
                "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
                "dif": dif, "dea": dea, "macd_hist": macd_hist,
                "rsi14": rsi14,
                "k": k_val, "d": d_val, "j": j_val,
                "last_price": last_price, "prev_close": prev_close,
                "chg_pct": chg_pct,
            }

        # 获取股票名称
        try:
            from core.stock_utils import get_name_batch
            nm = get_name_batch([code])
            result["name"] = nm.get(code, code) if nm else code
        except:
            result["name"] = code

        return jsonify(result)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
#  绩效 & 优化 API
# ============================================================

@app.route("/api/performance")
def api_performance():
    """获取各策略的绩效概览"""
    try:
        stats = db_manager.get_strategy_stats()
        runs = db_manager.get_run_summary()
        return jsonify({"stats": stats, "runs": runs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/performance/<strategy_key>")
def api_performance_strategy(strategy_key):
    """获取单策略绩效详情"""
    try:
        if strategy_key not in STRATEGIES and strategy_key != "all":
            return jsonify({"error": "unknown strategy"}), 404
        stats = db_manager.get_strategy_stats(strategy_key)
        recent = db_manager.get_recent_performance(strategy_key, limit=30)
        return jsonify({"stats": stats, "recent": recent})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/factors/<strategy_key>")
def api_factors(strategy_key):
    """获取因子IC分析"""
    try:
        if strategy_key not in STRATEGIES:
            return jsonify({"error": "unknown strategy"}), 404
        ic_analysis = db_manager.get_ic_analysis(strategy_key)
        weights = db_manager.get_factor_weights(strategy_key)
        return jsonify({"ic_analysis": ic_analysis, "weights": weights})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/optimize/<strategy_key>")
def api_optimize(strategy_key):
    """触发策略优化"""
    try:
        if strategy_key not in STRATEGIES:
            return jsonify({"error": "unknown strategy"}), 404
        import core.strategy_optimizer as strategy_optimizer
        result = strategy_optimizer.optimize_strategy(strategy_key)
        return jsonify(result)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/optimize-all")
def api_optimize_all():
    """触发全部策略优化"""
    try:
        import core.strategy_optimizer as strategy_optimizer
        results = {}
        for key in ALL_ORDER:
            try:
                results[key] = strategy_optimizer.optimize_strategy(key)
            except Exception as e:
                results[key] = {"error": str(e)}
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/optimization-history")
def api_optimization_history():
    """获取优化历史"""
    try:
        history = db_manager.get_optimization_history()
        return jsonify({"history": history})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scheduler/status")
def api_scheduler_status():
    """调度器状态"""
    return jsonify(bg_scheduler.get_scheduler().get_status())


@app.route("/api/scheduler/check-now")
def api_scheduler_check_now():
    """手动触发绩效检查"""
    return jsonify(bg_scheduler.get_scheduler().trigger_check_now())


@app.route("/api/scheduler/optimize-now")
def api_scheduler_optimize_now():
    """手动触发优化"""
    return jsonify(bg_scheduler.get_scheduler().trigger_optimize_now())


if __name__ == "__main__":
    print("\n  A股策略可视化仪表盘 v3")
    print("  ========================")
    print("  综合选股 · 四策略一键运行")
    print(f"  访问: http://{FLASK_HOST}:{FLASK_PORT}")
    print("  策略进化引擎已就绪: 数据库 + 绩效追踪 + 自动优化\n")
    bg_scheduler.start_scheduler()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True)
