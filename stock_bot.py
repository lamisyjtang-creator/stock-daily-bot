import os
import json
import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from datetime import datetime


EMAIL_ADDRESS = "lamisyjtang@gmail.com"
EMAIL_TO = "lamisyjtang@gmail.com"

# 請在系統環境變數設定 GMAIL_APP_PASSWORD
# Mac 終端機範例
# export GMAIL_APP_PASSWORD="qhcv olwf qllw lrha"
EMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


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

    # 新增到價提醒標的
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

    # 新增你指定的到價區間
    "GOOGL": {"price_band": [250, 300]},
    "NVDA": {"price_band": [150, 180]},
    "AVGO": {"price_band": [250, 300]},
    "AMD": {"price_band": [150, 190]},
    "0050.TW": {"price_band": [75, 75]},
}


HISTORY_PATH = os.path.expanduser("~/stock_bot/history.json")


def send_email(subject, body):
    if not EMAIL_APP_PASSWORD:
        raise RuntimeError("找不到環境變數 GMAIL_APP_PASSWORD，請先設定後再執行")

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_TO

    try:
        print("sending email")
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        print("email sent")
    except Exception as e:
        print("email failed")
        print(repr(e))
        raise


def get_latest_price(ticker):
    data = yf.download(
        ticker,
        period="10d",
        interval="1d",
        progress=False,
        auto_adjust=False
    )
    if data is None or data.empty:
        return None

    close_series = data.get("Close")
    if close_series is None:
        return None

    close_series = close_series.dropna()
    if close_series.empty:
        return None

    return float(close_series.iloc[-1])


def get_year_high(ticker):
    data = yf.download(
        ticker,
        period="1y",
        interval="1d",
        progress=False,
        auto_adjust=False
    )
    if data is None or data.empty:
        return None

    high_series = data.get("High")
    if high_series is None:
        return None

    high_series = high_series.dropna()
    if high_series.empty:
        return None

    return float(high_series.max())


def get_daily_history_data(ticker, period="2y"):
    data = yf.download(
        ticker,
        period=period,
        interval="1d",
        progress=False,
        auto_adjust=False
    )
    if data is None or data.empty:
        return None
    return data


def compute_sma(close_series, window):
    if close_series is None or len(close_series) < window:
        return None
    return float(close_series.tail(window).mean())


def compute_rsi(close_series, period=14):
    if close_series is None or len(close_series) < period + 1:
        return None

    delta = close_series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    last_gain = avg_gain.iloc[-1]
    last_loss = avg_loss.iloc[-1]

    if float(last_loss) == 0.0:
        return 100.0

    rs = float(last_gain) / float(last_loss)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return float(rsi)


def calc_position_from_trades(trades):
    total_amount = 0.0
    total_shares = 0.0

    for t in trades:
        price = float(t["price"])
        amount = float(t["amount"])
        if price <= 0:
            continue
        total_amount += amount
        total_shares += amount / price

    avg_cost = (total_amount / total_shares) if total_shares > 0 else None
    return total_shares, avg_cost, total_amount


def load_history():
    if not os.path.exists(HISTORY_PATH):
        return {}
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(history):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def update_history_for_today(history, ticker, today_key, flags, details):
    if ticker not in history:
        history[ticker] = {}

    history[ticker][today_key] = {
        "flags": flags,
        "details": details
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
    last_key = keys_sorted[0]
    return bool(items[last_key].get("flags", {}).get(flag_key, False))


def check_all():
    now = datetime.now()
    today_key = now.strftime("%Y-%m-%d")
    history = load_history()

    summary_lines = []
    alert_lines = []

    total_value = 0.0
    total_cost = 0.0

    summary_lines.append(f"檢查時間：{now.strftime('%Y/%m/%d %H:%M:%S')}")
    summary_lines.append("")

    for ticker, info in PORTFOLIO.items():
        name = info.get("name", ticker)
        sector = info.get("sector", "")
        ptype = info.get("type", "watch")
        rules = RULES.get(ticker, {})

        trades = info.get("trades")
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

        line = f"{name}（{ticker}）"
        if sector:
            line += f"\n  產業 類型：{sector}"
        line += f"\n  現價：{price:.2f}"

        # 到價區間提醒，採用進入區間才提醒一次的邏輯
        price_band = rules.get("price_band")
        if price_band:
            low = float(price_band[0])
            high = float(price_band[1])
            in_band = (price >= low) and (price <= high)

            prev_in_band = last_flag_value(history, ticker, "price_band")
            flags_for_band = {"price_band": bool(in_band)}
            details_for_band = {"price": price, "low": low, "high": high}
            update_history_for_today(history, ticker, today_key, flags_for_band, details_for_band)

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
            gain_percent = (price - cost) / cost

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
                    close_series = daily["Close"].dropna()

                    high_1y_series = daily.tail(252)["High"].dropna()
                    high_1y = float(high_1y_series.max()) if not high_1y_series.empty else None

                    sma200 = compute_sma(close_series, 200)
                    rsi14 = compute_rsi(close_series, 14)

                    drop_from_high = None
                    if high_1y is not None and high_1y > 0:
                        drop_from_high = float((high_1y - price) / high_1y)

                    below_sma200 = None
                    if sma200 is not None and float(sma200) > 0:
                        below_sma200 = float((float(sma200) - price) / float(sma200))

                    flag_combo_today = True

                    if drop_from_high is None or drop_from_high < float(combo["drop_from_year_high"]):
                        flag_combo_today = False
                    if below_sma200 is None or below_sma200 < float(combo["below_sma200"]):
                        flag_combo_today = False
                    if rsi14 is None or float(rsi14) > float(combo["rsi14_below"]):
                        flag_combo_today = False

                    flags = {"dip_combo": bool(flag_combo_today)}
                    details = {
                        "drop_from_high": drop_from_high,
                        "below_sma200": below_sma200,
                        "rsi14": rsi14
                    }

                    update_history_for_today(history, ticker, today_key, flags, details)
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
                        line += f"\n    RSI14：{float(rsi14):.2f}"
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
    print("done")


if __name__ == "__main__":
    check_all()
