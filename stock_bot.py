import os
import json
from pathlib import Path
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

import pandas as pd
import yfinance as yf

yf.enable_debug_mode()


EMAIL_ADDRESS = "lamisyjtang@gmail.com"
EMAIL_TO = "lamisyjtang@gmail.com"
EMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

BASE_DIR = Path(__file__).resolve().parent
HISTORY_PATH = BASE_DIR / "history.json"


PORTFOLIO = {
    "2330.TW": {
        "name": "台積電",
        "sector": "AI 科技",
        "type": "position",
        "trades": [
            {"price": 1450.0, "amount": 144805.0},
            {"price": 1425.0, "amount": 57000.0},
        ]
    },
    "00878.TW": {
        "name": "00878 國泰永續高股息",
        "sector": "高股息 ETF",
        "type": "watch"
    },
    "00757.TW": {
        "name": "00757 全球電動車",
        "sector": "主題 ETF",
        "type": "watch"
    },
    "VOO": {
        "name": "VOO S&P500",
        "sector": "美股 大盤",
        "type": "watch"
    },
    "QQQ": {
        "name": "QQQ 科技 ETF",
        "sector": "美股 科技",
        "type": "watch"
    },
    "GOOGL": {
        "name": "Alphabet A",
        "sector": "美股 科技",
        "type": "watch"
    },
    "NVDA": {
        "name": "NVIDIA",
        "sector": "美股 AI",
        "type": "watch"
    },
    "AVGO": {
        "name": "Broadcom",
        "sector": "美股 半導體",
        "type": "watch"
    },
    "AMD": {
        "name": "AMD",
        "sector": "美股 半導體",
        "type": "watch"
    },
    "0050.TW": {
        "name": "0050 元大台灣50",
        "sector": "台股 ETF",
        "type": "watch"
    }
}


RULES = {
    "2330.TW": {
        "dip_buy": [0.10, 0.20],
        "take_profit": [0.30, 0.50],
        "dip_combo": {
            "drop_from_year_high": 0.15,
            "below_sma200": 0.05,
            "rsi14_below": 35
        }
    },
    "00878.TW": {
        "observe": 0.10,
        "dip_buy": [0.15, 0.20]
    },
    "00757.TW": {
        "observe": 0.15,
        "dip_buy": [0.25, 0.35]
    },
    "VOO": {
        "observe": 0.10,
        "dip_buy": [0.20, 0.30],
        "price_band": [550, 580]
    },
    "QQQ": {
        "observe": 0.15,
        "dip_buy": [0.25, 0.35],
        "price_band": [450, 600]
    },
    "GOOGL": {"price_band": [250, 300]},
    "NVDA": {"price_band": [150, 180]},
    "AVGO": {"price_band": [250, 300]},
    "AMD": {"price_band": [150, 190]},
    "0050.TW": {"price_band": [75, 75]},
}


def log(message):
    print(f"[{datetime.now().strftime('%Y/%m/%d %H:%M:%S')}] {message}")


def safe_float(value):
    try:
        if value is None:
            return None
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def extract_single_series(data, field_name):
    if data is None or data.empty:
        return None

    try:
        if field_name not in data.columns:
            return None
        result = data[field_name]
    except Exception:
        return None

    if isinstance(result, pd.DataFrame):
        if result.shape[1] == 0:
            return None
        result = result.iloc[:, 0]

    if not isinstance(result, pd.Series):
        return None

    result = pd.to_numeric(result, errors="coerce").dropna()
    if result.empty:
        return None

    return result


def download_price_data(ticker, period, interval="1d"):
    try:
        log(f"{ticker} 開始下載 period={period} interval={interval}")
        tk = yf.Ticker(ticker)
        data = tk.history(
            period=period,
            interval=interval,
            auto_adjust=False,
            timeout=20,
            raise_errors=True
        )

        if data is None or data.empty:
            log(f"{ticker} 無資料")
            return None

        log(f"{ticker} 下載成功 rows={len(data)}")
        return data

    except Exception as e:
        log(f"{ticker} 下載失敗: {repr(e)}")
        return None


def get_latest_price(ticker):
    data = download_price_data(ticker, period="10d", interval="1d")
    if data is None:
        return None

    close_series = extract_single_series(data, "Close")
    if close_series is None or close_series.empty:
        log(f"{ticker} Close 欄位無有效資料")
        return None

    latest_price = safe_float(close_series.iloc[-1])
    log(f"{ticker} 最新價格 {latest_price}")
    return latest_price


def get_year_high(ticker):
    data = download_price_data(ticker, period="1y", interval="1d")
    if data is None:
        return None

    high_series = extract_single_series(data, "High")
    if high_series is None or high_series.empty:
        log(f"{ticker} High 欄位無有效資料")
        return None

    year_high = safe_float(high_series.max())
    log(f"{ticker} 近一年高點 {year_high}")
    return year_high


def get_daily_history_data(ticker, period="2y"):
    return download_price_data(ticker, period=period, interval="1d")


def compute_sma(close_series, window):
    if close_series is None or len(close_series) < window:
        return None
    return safe_float(close_series.tail(window).mean())


def compute_rsi(close_series, period=14):
    if close_series is None or len(close_series) < period + 1:
        return None

    delta = close_series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    last_gain = safe_float(avg_gain.iloc[-1])
    last_loss = safe_float(avg_loss.iloc[-1])

    if last_gain is None or last_loss is None:
        return None

    if last_loss == 0:
        return 100.0

    rs = last_gain / last_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return safe_float(rsi)


def calc_position_from_trades(trades):
    total_amount = 0.0
    total_shares = 0.0

    for t in trades:
        price = safe_float(t.get("price"))
        amount = safe_float(t.get("amount"))

        if price is None or amount is None or price <= 0:
            continue

        total_amount += amount
        total_shares += amount / price

    avg_cost = (total_amount / total_shares) if total_shares > 0 else None
    return total_shares, avg_cost, total_amount


def load_history():
    if not HISTORY_PATH.exists():
        return {}

    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception as e:
        log(f"讀取 history.json 失敗: {repr(e)}")
        return {}


def save_history(history):
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"寫入 history.json 失敗: {repr(e)}")


def update_history_for_today(history, ticker, today_key, flags, details):
    if ticker not in history:
        history[ticker] = {}

    existing = history[ticker].get(today_key, {})
    existing_flags = existing.get("flags", {})
    existing_details = existing.get("details", {})

    merged_flags = {**existing_flags, **flags}
    merged_details = {**existing_details, **details}

    history[ticker][today_key] = {
        "flags": merged_flags,
        "details": merged_details
    }

    keys_sorted = sorted(history[ticker].keys(), reverse=True)
    for k in keys_sorted[120:]:
        del history[ticker][k]


def three_day_streak(history, ticker, flag_key):
    items = history.get(ticker, {})
    if not items:
        return False

    keys_sorted = sorted(items.keys(), reverse=True)
    last_three = keys_sorted[:3]

    if len(last_three) < 3:
        return False

    for k in last_three:
        if not items[k].get("flags", {}).get(flag_key, False):
            return False

    return True


def last_flag_value(history, ticker, flag_key):
    items = history.get(ticker, {})
    if not items:
        return None

    keys_sorted = sorted(items.keys(), reverse=True)
    if not keys_sorted:
        return None

    last_key = keys_sorted[0]
    return bool(items[last_key].get("flags", {}).get(flag_key, False))


def send_email(subject, body):
    if not EMAIL_APP_PASSWORD:
        raise RuntimeError("找不到環境變數 GMAIL_APP_PASSWORD")

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_TO

    log("開始寄信")

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        smtp.send_message(msg)

    log("寄信成功")


def check_all():
    now = datetime.now()
    today_key = now.strftime("%Y-%m-%d")
    history = load_history()

    summary_lines = []
    alert_lines = []

    total_value = 0.0
    total_cost = 0.0
    success_count = 0

    summary_lines.append(f"檢查時間：{now.strftime('%Y/%m/%d %H:%M:%S')}")
    summary_lines.append("")

    for ticker, info in PORTFOLIO.items():
        try:
            name = info.get("name", ticker)
            sector = info.get("sector", "")
            ptype = info.get("type", "watch")
            rules = RULES.get(ticker, {})
            trades = info.get("trades")

            log(f"開始處理 {ticker}")

            if trades:
                shares, cost, _ = calc_position_from_trades(trades)
            else:
                shares = 0.0
                cost = None

            price = get_latest_price(ticker)
            if price is None:
                summary_lines.append(f"{name}（{ticker}）無法取得價格")
                summary_lines.append("")
                continue

            success_count += 1

            line = f"{name}（{ticker}）"
            if sector:
                line += f"\n  產業 類型：{sector}"
            line += f"\n  現價：{price:.2f}"

            price_band = rules.get("price_band")
            if price_band:
                low = safe_float(price_band[0])
                high = safe_float(price_band[1])

                if low is not None and high is not None:
                    in_band = low <= price <= high
                    prev_in_band = last_flag_value(history, ticker, "price_band")

                    update_history_for_today(
                        history,
                        ticker,
                        today_key,
                        {"price_band": bool(in_band)},
                        {"price": price, "low": low, "high": high}
                    )

                    line += f"\n  你的到價區間：{low:.2f} 到 {high:.2f}"
                    line += "\n  今日是否進入：" + ("是" if in_band else "否")

                    if in_band and not prev_in_band:
                        alert_lines.append(
                            f"【{name} 到價提醒】\n"
                            f"目前價格 {price:.2f}\n"
                            f"已進入你設定的區間 {low:.2f} 到 {high:.2f}\n"
                            f"提醒：分批規劃比一次買滿更穩"
                        )

            if ptype == "position" and cost is not None and shares > 0:
                position_value = price * shares
                position_cost = cost * shares
                position_pnl = position_value - position_cost
                gain_percent = (price - cost) / cost if cost > 0 else 0.0

                total_value += position_value
                total_cost += position_cost

                line += (
                    f"\n  加權成本：{cost:.2f}"
                    f"\n  推算股數：{shares:.4f}"
                    f"\n  持股市值：約 {position_value:.0f} 元"
                    f"\n  未實現損益：約 {position_pnl:.0f} 元"
                    f"\n  報酬率：約 {(gain_percent * 100):.2f}％"
                )

                combo = rules.get("dip_combo")
                if combo:
                    daily = get_daily_history_data(ticker, period="2y")
                    if daily is not None:
                        close_series = extract_single_series(daily, "Close")
                        high_series = extract_single_series(daily, "High")

                        if close_series is not None and high_series is not None:
                            high_1y_series = high_series.tail(252)
                            high_1y = safe_float(high_1y_series.max()) if not high_1y_series.empty else None
                            sma200 = compute_sma(close_series, 200)
                            rsi14 = compute_rsi(close_series, 14)

                            drop_from_high = None
                            if high_1y is not None and high_1y > 0:
                                drop_from_high = (high_1y - price) / high_1y

                            below_sma200 = None
                            if sma200 is not None and sma200 > 0:
                                below_sma200 = (sma200 - price) / sma200

                            flag_combo_today = True

                            if drop_from_high is None or drop_from_high < float(combo["drop_from_year_high"]):
                                flag_combo_today = False
                            if below_sma200 is None or below_sma200 < float(combo["below_sma200"]):
                                flag_combo_today = False
                            if rsi14 is None or rsi14 > float(combo["rsi14_below"]):
                                flag_combo_today = False

                            update_history_for_today(
                                history,
                                ticker,
                                today_key,
                                {"dip_combo": bool(flag_combo_today)},
                                {
                                    "drop_from_high": drop_from_high,
                                    "below_sma200": below_sma200,
                                    "rsi14": rsi14
                                }
                            )

                            streak3 = three_day_streak(history, ticker, "dip_combo")

                            line += "\n  低點三條件"
                            if drop_from_high is not None:
                                line += f"\n    近一年高點回檔：{drop_from_high * 100:.2f}％"
                            else:
                                line += "\n    近一年高點回檔：無資料"

                            if below_sma200 is not None:
                                line += f"\n    低於 200 日均線：{below_sma200 * 100:.2f}％"
                            else:
                                line += "\n    低於 200 日均線：無資料"

                            if rsi14 is not None:
                                line += f"\n    RSI14：{rsi14:.2f}"
                            else:
                                line += "\n    RSI14：無資料"

                            line += "\n  今日是否符合：" + ("是" if flag_combo_today else "否")
                            line += "\n  近三天連續符合：" + ("是" if streak3 else "否")

                            if streak3:
                                alert_lines.append(
                                    "【台積電 低點三條件 連三天符合】\n"
                                    "建議你檢查基本面與倉位配置，再決定是否分批加碼"
                                )

                if "dip_buy" in rules:
                    dip1, dip2 = rules["dip_buy"]

                    if gain_percent <= -dip1:
                        alert_lines.append(
                            f"【台積電跌到觀察區】\n"
                            f"跌幅已超過 {dip1 * 100:.0f}％\n"
                            f"現價：{price:.2f} 成本：{cost:.2f}"
                        )

                    if gain_percent <= -dip2:
                        alert_lines.append(
                            f"【台積電跌到加碼區】\n"
                            f"跌幅已超過 {dip2 * 100:.0f}％\n"
                            f"現價：{price:.2f} 成本：{cost:.2f}"
                        )

                if "take_profit" in rules:
                    tp1, tp2 = rules["take_profit"]

                    if gain_percent >= tp1:
                        alert_lines.append(
                            f"【台積電可考慮減碼】\n"
                            f"已漲超過 {tp1 * 100:.0f}％\n"
                            f"現價：{price:.2f} 成本：{cost:.2f}"
                        )

                    if gain_percent >= tp2:
                        alert_lines.append(
                            f"【台積電大幅獲利提醒】\n"
                            f"已漲超過 {tp2 * 100:.0f}％\n"
                            f"現價：{price:.2f} 成本：{cost:.2f}"
                        )

            else:
                year_high = get_year_high(ticker)
                if year_high is not None and year_high > 0:
                    drop_from_high = (year_high - price) / year_high

                    line += f"\n  近一年高點：約 {year_high:.2f}"
                    line += f"\n  距離高點回檔：約 {drop_from_high * 100:.2f}％"

                    observe = rules.get("observe")
                    dip_buy = rules.get("dip_buy")

                    if observe is not None and drop_from_high >= observe:
                        alert_lines.append(
                            f"【{name} 進入觀察區】\n"
                            f"從一年高點回檔 {drop_from_high * 100:.1f}％\n"
                            f"現價：{price:.2f}"
                        )

                    if dip_buy is not None:
                        d1, d2 = dip_buy

                        if drop_from_high >= d1:
                            alert_lines.append(
                                f"【{name} 可考慮分批佈局】\n"
                                f"跌幅已達 {d1 * 100:.0f}％\n"
                                f"現價：{price:.2f}"
                            )

                        if drop_from_high >= d2:
                            alert_lines.append(
                                f"【{name} 已到便宜區】\n"
                                f"跌幅已達 {d2 * 100:.0f}％\n"
                                f"現價：{price:.2f}"
                            )

            summary_lines.append(line)
            summary_lines.append("")
            log(f"完成處理 {ticker}")

        except Exception as e:
            log(f"{ticker} 處理失敗: {repr(e)}")
            summary_lines.append(f"{info.get('name', ticker)}（{ticker}）處理失敗：{repr(e)}")
            summary_lines.append("")

    if success_count == 0:
        raise RuntimeError("所有 ticker 都抓不到資料，這次不寄送報告，請檢查 yfinance 或 Yahoo 限流問題")

    if total_cost > 0:
        total_gain = total_value - total_cost
        total_return = total_gain / total_cost

        summary_lines.append("總體部位")
        summary_lines.append(f"投入成本：約 {total_cost:.0f} 元")
        summary_lines.append(f"目前市值：約 {total_value:.0f} 元")
        summary_lines.append(f"總未實現損益：約 {total_gain:.0f} 元")
        summary_lines.append(f"總報酬率：約 {total_return * 100:.2f}％")
    else:
        summary_lines.append("目前尚未設定任何持股成本與股數，無法計算總損益。")

    summary_lines.append("")

    if alert_lines:
        summary_lines.append("今日提醒")
        summary_lines.extend(alert_lines)
    else:
        summary_lines.append("今日尚未觸發任何買點或賣點條件。")

    subject = "每日股票摘要與提醒"
    body = "\n".join(summary_lines)

    save_history(history)
    send_email(subject, body)
    log("全部完成")


if __name__ == "__main__":
    check_all()
