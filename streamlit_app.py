import os
from datetime import datetime, timezone
from itertools import product

import ccxt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ============================================================
# NEXUS — PROFESSIONAL PAPER TRADING & RESEARCH TERMINAL
# Simulation only. No real order execution.
# ============================================================

st.set_page_config(
    page_title="NEXUS | Trading Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------- DESIGN -----------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root {
  --bg:#080D16; --panel:#101A2A; --panel2:#142238; --line:#263951;
  --text:#EAF1FA; --muted:#8FA2BA; --green:#35D6A2; --red:#FF647C;
  --blue:#78A6FF; --gold:#E9BE72; --purple:#B39AFF;
}
html, body, [class*="css"] {font-family:'DM Sans',sans-serif;}
.stApp {background:radial-gradient(ellipse at 80% -10%,#1B3150 0%,transparent 36%),var(--bg);color:var(--text);}
header[data-testid="stHeader"] {background:rgba(8,13,22,.72);}
.block-container {max-width:1580px;padding-top:1.35rem;padding-bottom:3rem;}
h1,h2,h3 {font-family:'Space Grotesk',sans-serif!important;color:var(--text)!important;letter-spacing:-.6px;}
h1 {font-size:2.15rem!important;}
[data-testid="stSidebar"] {background:#0A1220;border-right:1px solid var(--line);}
[data-testid="stMetric"] {background:linear-gradient(145deg,#172840,#101A2A);border:1px solid var(--line);padding:17px 18px;border-radius:15px;}
[data-testid="stMetricLabel"] {color:var(--muted)!important;font-size:.76rem;}
[data-testid="stMetricValue"] {font-family:'Space Grotesk',sans-serif;color:var(--text)!important;}
[data-testid="stMetricDelta"] {font-family:'DM Mono',monospace;}
.stButton>button,.stDownloadButton>button {border:1px solid #38516F;border-radius:10px;background:#192B43;color:#F4F7FC;font-weight:650;min-height:2.55rem;}
.stButton>button:hover,.stDownloadButton>button:hover {border-color:var(--blue);background:#223B5B;color:white;}
button[kind="primary"] {background:linear-gradient(100deg,#2866C7,#397DE0)!important;border:0!important;}
div[data-baseweb="select"]>div,.stTextInput input,.stNumberInput input,.stTextArea textarea {background:#111E30;border-color:#344A65;color:white;border-radius:9px;}
[data-testid="stDataFrame"] {border:1px solid var(--line);border-radius:12px;}
hr {border-color:var(--line);}
.nx-brand {font:700 25px 'Space Grotesk';letter-spacing:2px;color:#F5F8FF;}
.nx-sub {font:500 9px 'DM Mono';letter-spacing:2.4px;color:#8FA2BA;margin-top:-3px;}
.eyebrow {font:600 10px 'DM Mono';letter-spacing:2px;color:#91A5C0;text-transform:uppercase;margin-bottom:8px;}
.panel {background:linear-gradient(145deg,#14243A,#101A2A);border:1px solid #2A405C;border-radius:15px;padding:17px 19px;margin-bottom:10px;}
.panel-title {font:600 11px 'DM Mono';letter-spacing:1.5px;color:#91A5C0;text-transform:uppercase;margin-bottom:8px;}
.big-number {font:600 25px 'Space Grotesk';color:#F1F6FD;}
.muted {font-size:12px;color:#8FA2BA;}
.pill {display:inline-block;border:1px solid #314965;background:#14243A;padding:5px 9px;border-radius:20px;font:500 10px 'DM Mono';color:#B7C9DF;}
div[data-testid="stChatMessage"] {background:#111E30;border:1px solid #293F5B;border-radius:13px;padding:12px;}
.stTabs [data-baseweb="tab-list"] {gap:7px;background:#0E1928;padding:6px;border:1px solid #263951;border-radius:12px;}
.stTabs [data-baseweb="tab"] {border-radius:8px;color:#9FB0C5;}
.stTabs [aria-selected="true"] {background:#203753;color:white;}
</style>
""", unsafe_allow_html=True)


# ----------------------------- STATE -----------------------------

DEFAULTS = {
    "starting_balance": 1000.0,
    "cash": 1000.0 / 11.5,
    "risk": 20,
    "fee": 0.4,
    "refresh": 60,
    "timeframe": "1h",
    "auto_trade": False,
    "currency_rate": 11.5,
    "positions": {"BTC": {"qty": 0.0, "cost": 0.0}, "ETH": {"qty": 0.0, "cost": 0.0}},
    "trades": [],
    "processed": {},
    "history": [],
    "chat": [],
    "last_backtest": None,
    "last_optimization": None,
    "last_comparison": None,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value

exchange = ccxt.kraken({"enableRateLimit": True, "timeout": 20000})


# ----------------------------- INDICATORS -----------------------------

def add_indicators(source, fast=20, slow=50):
    df = source.copy()
    close = df["close"]
    df["EMA20"] = close.ewm(span=20, adjust=False).mean()
    df["EMA50"] = close.ewm(span=50, adjust=False).mean()
    df["EMA_FAST"] = close.ewm(span=fast, adjust=False).mean()
    df["EMA_SLOW"] = close.ewm(span=slow, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["RSI"] = 100 - 100 / (1 + rs)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]

    mid = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std()
    df["BB_MID"] = mid
    df["BB_UPPER"] = mid + 2 * std
    df["BB_LOWER"] = mid - 2 * std
    df["BB_WIDTH"] = (df["BB_UPPER"] - df["BB_LOWER"]) / mid.replace(0, float("nan"))

    prev_close = close.shift(1)
    true_range = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs()
    ], axis=1).max(axis=1)
    df["ATR"] = true_range.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    df["ATR_PCT"] = df["ATR"] / close * 100
    return df


def signal_for(row, strategy="NEXUS Multi-Factor", params=None):
    params = params or {}
    required = ["RSI", "EMA_FAST", "EMA_SLOW", "MACD", "MACD_SIGNAL",
                "BB_UPPER", "BB_LOWER", "ATR"]
    if any(pd.isna(row.get(k)) for k in required):
        return "HOLD"

    rsi = float(row["RSI"])
    trend_up = row["EMA_FAST"] > row["EMA_SLOW"]
    trend_down = row["EMA_FAST"] < row["EMA_SLOW"]
    macd_up = row["MACD"] > row["MACD_SIGNAL"]
    macd_down = row["MACD"] < row["MACD_SIGNAL"]

    if strategy == "NEXUS Baseline":
        if row["EMA20"] > row["EMA50"] and 50 < rsi < 68:
            return "BUY"
        if row["EMA20"] < row["EMA50"] or rsi > 75:
            return "SELL"
        return "HOLD"

    if strategy == "EMA Crossover":
        return "BUY" if trend_up else "SELL" if trend_down else "HOLD"

    if strategy == "RSI Reversal":
        if rsi < params.get("rsi_buy", 30):
            return "BUY"
        if rsi > params.get("rsi_sell", 70):
            return "SELL"
        return "HOLD"

    if strategy == "Bollinger Reversal":
        if row["close"] < row["BB_LOWER"] and rsi < 40:
            return "BUY"
        if row["close"] > row["BB_UPPER"] and rsi > 60:
            return "SELL"
        return "HOLD"

    if strategy == "MACD Trend":
        if trend_up and macd_up and rsi > 48:
            return "BUY"
        if trend_down and macd_down:
            return "SELL"
        return "HOLD"

    # Multi-factor: require trend + momentum confirmation; avoid chasing extremes.
    buy_rsi = params.get("rsi_buy", 48)
    sell_rsi = params.get("rsi_sell", 72)
    if trend_up and macd_up and buy_rsi <= rsi <= 68:
        return "BUY"
    if trend_down and (macd_down or rsi >= sell_rsi):
        return "SELL"
    return "HOLD"


def analyze(symbol, timeframe):
    candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=180)
    if not candles:
        raise ValueError("No market data returned.")
    df = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "volume"])
    df = df.iloc[:-1].copy()  # exclude the still-forming candle
    if len(df) < 80:
        raise ValueError("Not enough completed candles.")
    df = add_indicators(df)
    last = df.iloc[-1]
    previous = df.iloc[-25]["close"]
    return {
        "price": float(last["close"]),
        "rsi": float(last["RSI"]) if pd.notna(last["RSI"]) else 50.0,
        "signal": signal_for(last, "NEXUS Multi-Factor"),
        "change": float((last["close"] / previous - 1) * 100),
        "candle": int(last["time"]),
        "history": df
    }


# ----------------------------- HISTORICAL DATA -----------------------------

@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(symbol, timeframe, limit):
    client = ccxt.kraken({"enableRateLimit": True, "timeout": 25000})
    candles = client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not candles:
        raise ValueError("Kraken returned no historical candles.")
    df = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "volume"])
    df = df.iloc[:-1].copy()
    df["Date"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = add_indicators(df).reset_index(drop=True)
    if len(df) < 100:
        raise ValueError("Not enough historical data. Try another timeframe or candle count.")
    return df


# ----------------------------- BACKTEST ENGINE -----------------------------

def run_backtest(df, starting_balance, position_pct, fee_pct, strategy,
                 params=None, stop_loss=0, take_profit=0, max_dd=0,
                 trailing_stop=0):
    """Close-based signals execute at next open. Intrabar exits use conservative stop-first ordering."""
    params = params or {}
    fee = fee_pct / 100
    cash = float(starting_balance)
    qty = 0.0
    entry_cost = entry_price = high_water = 0.0
    entry_date = None
    trades, points = [], []
    peak_equity = float(starting_balance)
    halted = False
    warmup = min(80, max(30, len(df) // 5))
    points.append({"Date": df.iloc[warmup]["Date"], "Equity": cash})

    for i in range(warmup, len(df) - 1):
        signal_row = df.iloc[i]
        candle = df.iloc[i + 1]
        op, hi, lo, cl = map(float, [candle["open"], candle["high"], candle["low"], candle["close"]])
        date = candle["Date"]
        exit_price, exit_reason = None, None

        if qty > 0:
            high_water = max(high_water, hi)
            stop_candidates = []
            if stop_loss > 0:
                stop_candidates.append((entry_price * (1 - stop_loss / 100), "Stop-loss"))
            if trailing_stop > 0:
                stop_candidates.append((high_water * (1 - trailing_stop / 100), "Trailing stop"))
            active_stop = max([x[0] for x in stop_candidates], default=None)
            target = entry_price * (1 + take_profit / 100) if take_profit > 0 else None
            # Gap-through stop fills at the open; otherwise at stop level.
            if active_stop is not None and lo <= active_stop:
                exit_price = min(op, active_stop) if op < active_stop else active_stop
                exit_reason = "Stop / trailing stop"
            elif target is not None and hi >= target:
                exit_price, exit_reason = max(op, target), "Take-profit"

        def close_position(price, reason, trade_date):
            nonlocal cash, qty, entry_cost, entry_price, entry_date, high_water
            proceeds = qty * price * (1 - fee)
            pnl = proceeds - entry_cost
            trades.append({
                "Entry Date": entry_date, "Exit Date": trade_date,
                "Exit Reason": reason, "Entry Price": entry_price,
                "Exit Price": price, "Entry Cost": entry_cost,
                "Exit Value": proceeds, "Profit": pnl,
                "Return %": pnl / entry_cost * 100 if entry_cost else 0
            })
            cash += proceeds
            qty, entry_cost, entry_price, high_water, entry_date = 0.0, 0.0, 0.0, 0.0, None

        if exit_price is not None and qty > 0:
            close_position(float(exit_price), exit_reason, date)

        equity_before_signal = cash + qty * cl
        peak_equity = max(peak_equity, equity_before_signal)
        dd = (equity_before_signal / peak_equity - 1) * 100 if peak_equity else 0
        if max_dd > 0 and dd <= -max_dd and not halted:
            if qty > 0:
                close_position(cl, "Account drawdown stop", date)
            halted = True

        if not halted:
            signal = signal_for(signal_row, strategy, params)
            if signal == "SELL" and qty > 0:
                close_position(op, "Strategy exit", date)
            elif signal == "BUY" and qty == 0 and cash > 1:
                allocation = cash * position_pct / 100
                qty = allocation * (1 - fee) / op
                entry_cost, entry_price, entry_date, high_water = allocation, op, date, op
                cash -= allocation

        equity = cash + qty * cl
        peak_equity = max(peak_equity, equity)
        points.append({"Date": date, "Equity": equity})

    last = df.iloc[-1]
    if qty > 0:
        close_position(float(last["close"]), "End of test", last["Date"])
    final_equity = cash
    if points:
        points[-1]["Equity"] = final_equity
    equity_df = pd.DataFrame(points)

    first_exec = min(warmup + 1, len(df) - 1)
    buy_price = float(df.iloc[first_exec]["open"])
    end_price = float(df.iloc[-1]["close"])
    buy_qty = starting_balance * (1 - fee) / buy_price
    buy_hold_value = buy_qty * end_price * (1 - fee)

    total_return = (final_equity / starting_balance - 1) * 100
    buy_hold_return = (buy_hold_value / starting_balance - 1) * 100
    running_peak = equity_df["Equity"].cummax()
    drawdown = (equity_df["Equity"] / running_peak - 1) * 100
    max_drawdown = float(drawdown.min()) if len(drawdown) else 0.0
    wins = [t for t in trades if t["Profit"] > 0]
    losses = [t for t in trades if t["Profit"] < 0]
    gross_profit = sum(t["Profit"] for t in wins)
    gross_loss = abs(sum(t["Profit"] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0)
    metrics = {
        "final_equity": final_equity,
        "total_return": total_return,
        "buy_hold_value": buy_hold_value,
        "buy_hold_return": buy_hold_return,
        "trades": len(trades),
        "win_rate": len(wins) / len(trades) * 100 if trades else 0.0,
        "max_drawdown": max_drawdown,
        "profit_factor": profit_factor,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
    }
    return metrics, equity_df, trades


def score_metrics(metrics):
    """Risk-aware ranking: reward return, penalize drawdown and tiny samples."""
    ret = metrics["total_return"]
    dd = abs(metrics["max_drawdown"])
    trades = metrics["trades"]
    pf = min(metrics["profit_factor"], 3) if metrics["profit_factor"] != float("inf") else 3
    sample_penalty = 8 if trades < 5 else 3 if trades < 10 else 0
    return ret - 0.65 * dd + min(pf, 3) * 1.5 - sample_penalty


def optimize_strategy(df, balance, position, fee, sl, tp, max_dd, trailing):
    """Small, transparent grid search on training data; evaluate the winner on a later holdout."""
    split = int(len(df) * 0.70)
    warmup_overlap = 90
    train = df.iloc[:split].reset_index(drop=True)
    test_start = max(0, split - warmup_overlap)
    test = df.iloc[test_start:].reset_index(drop=True)

    candidates = []
    grid = product(
        [10, 20, 30],       # fast EMA
        [40, 50, 80],       # slow EMA
        [45, 50, 55],       # RSI lower boundary
        [68, 72, 76],       # RSI exit boundary
        [0, 1],             # MACD confirmation on/off
    )
    for fast, slow, rsi_buy, rsi_sell, macd_filter in grid:
        if fast >= slow or rsi_buy >= rsi_sell:
            continue
        params = {
            "fast": fast, "slow": slow,
            "rsi_buy": rsi_buy, "rsi_sell": rsi_sell,
            "macd_filter": bool(macd_filter)
        }
        train_ind = add_indicators(train, fast, slow)
        # Candidate signal uses the same common engine; MACD is always part of multi-factor logic.
        metrics, _, _ = run_backtest(
            train_ind, balance, position, fee, "NEXUS Multi-Factor",
            params, sl, tp, max_dd, trailing
        )
        candidates.append({
            **params,
            "Training Return %": metrics["total_return"],
            "Training Max DD %": metrics["max_drawdown"],
            "Training Trades": metrics["trades"],
            "Training Win Rate %": metrics["win_rate"],
            "Robust Score": score_metrics(metrics),
        })

    ranking = pd.DataFrame(candidates).sort_values(
        ["Robust Score", "Training Return %"], ascending=False
    ).reset_index(drop=True)
    best = ranking.iloc[0]
    best_params = {
        "fast": int(best["fast"]), "slow": int(best["slow"]),
        "rsi_buy": int(best["rsi_buy"]), "rsi_sell": int(best["rsi_sell"]),
        "macd_filter": bool(best["macd_filter"])
    }
    test_ind = add_indicators(test, best_params["fast"], best_params["slow"])
    test_metrics, test_equity, test_trades = run_backtest(
        test_ind, balance, position, fee, "NEXUS Multi-Factor",
        best_params, sl, tp, max_dd, trailing
    )
    return ranking, best_params, test_metrics, test_equity, test_trades, split


# ----------------------------- PAPER ACCOUNT -----------------------------

def execute_paper_trade(coin, data):
    if not st.session_state.auto_trade:
        return
    candle_id = data["candle"]
    if st.session_state.processed.get(coin) == candle_id:
        return
    st.session_state.processed[coin] = candle_id
    pos = st.session_state.positions[coin]
    price = data["price"]
    fee = st.session_state.fee / 100
    signal = data["signal"]

    if signal == "BUY" and pos["qty"] == 0:
        amount = st.session_state.cash * st.session_state.risk / 100
        if amount < 5:
            return
        qty = amount * (1 - fee) / price
        st.session_state.cash -= amount
        pos["qty"], pos["cost"] = qty, amount
        st.session_state.trades.append({
            "Time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "Asset": coin, "Action": "BUY",
            "Price EUR": round(price, 2), "Amount EUR": round(amount, 2)
        })
    elif signal == "SELL" and pos["qty"] > 0:
        proceeds = pos["qty"] * price * (1 - fee)
        st.session_state.cash += proceeds
        st.session_state.trades.append({
            "Time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "Asset": coin, "Action": "SELL",
            "Price EUR": round(price, 2), "Amount EUR": round(proceeds, 2)
        })
        pos["qty"], pos["cost"] = 0.0, 0.0


# ----------------------------- CHARTS -----------------------------

def chart_layout(fig, height=400):
    fig.update_layout(
        height=height, template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=28, b=10),
        font=dict(color="#AFC0D5"),
        legend=dict(orientation="h", y=1.08),
        hovermode="x unified",
    )
    return fig


def market_chart(data):
    df = data["history"].tail(120).copy()
    dates = pd.to_datetime(df["time"], unit="ms", utc=True)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=dates, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name="Price", increasing_line_color="#35D6A2", decreasing_line_color="#FF647C"
    ))
    fig.add_trace(go.Scatter(x=dates, y=df["EMA20"], name="EMA 20", line=dict(color="#78A6FF", width=1.4)))
    fig.add_trace(go.Scatter(x=dates, y=df["EMA50"], name="EMA 50", line=dict(color="#B39AFF", width=1.4)))
    return chart_layout(fig, 470)


def equity_chart(eq, label="Strategy"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=eq["Date"], y=eq["Equity"], name=label,
        line=dict(color="#35D6A2", width=2.5), fill="tozeroy"
    ))
    return chart_layout(fig, 380)


def metric_report(metrics):
    a, b, c, d = st.columns(4)
    a.metric("Final equity", f'{metrics["final_equity"]:,.2f} EUR', f'{metrics["total_return"]:+.2f}%')
    b.metric("Strategy return", f'{metrics["total_return"]:+.2f}%')
    c.metric("Buy & hold", f'{metrics["buy_hold_return"]:+.2f}%')
    d.metric("Closed trades", metrics["trades"])
    e, f, g = st.columns(3)
    e.metric("Win rate", f'{metrics["win_rate"]:.1f}%')
    f.metric("Max drawdown", f'{metrics["max_drawdown"]:.2f}%')
    pf = "∞" if metrics["profit_factor"] == float("inf") else f'{metrics["profit_factor"]:.2f}'
    g.metric("Profit factor", pf)


# ----------------------------- SIDEBAR / DATA -----------------------------

st.sidebar.markdown('<div class="nx-brand">◈ NEXUS</div><div class="nx-sub">TRADING INTELLIGENCE TERMINAL</div>', unsafe_allow_html=True)
st.sidebar.divider()
pages = ["Command Center", "Markets", "Portfolio", "Strategy Studio", "Backtest & AI", "Trade Journal", "AI Copilot", "Settings"]
page = st.sidebar.radio("NAVIGATION", pages, label_visibility="visible")
st.sidebar.divider()
st.sidebar.markdown("#### SIMULATION ACCOUNT")
st.sidebar.metric("Starting capital", f'{st.session_state.starting_balance:,.0f} SEK')
st.sidebar.markdown('<span class="pill">● PAPER MODE</span>', unsafe_allow_html=True)
st.sidebar.caption("Kraken public market data · No real orders")
st.sidebar.divider()
st.sidebar.markdown("#### QUICK CONTROLS")
st.sidebar.caption(f'Timeframe: {st.session_state.timeframe}')
st.sidebar.caption(f'Auto paper trading: {"ON" if st.session_state.auto_trade else "OFF"}')

st_autorefresh(interval=int(st.session_state.refresh) * 1000, key="nexus_refresh")
results, errors = {}, []
for coin in ["BTC", "ETH"]:
    try:
        info = analyze(coin + "/EUR", st.session_state.timeframe)
        results[coin] = info
        execute_paper_trade(coin, info)
    except Exception as exc:
        errors.append(f"{coin}: {exc}")

portfolio_value, profit = 0.0, 0.0
if results:
    marked_positions = sum(
        st.session_state.positions[c]["qty"] * results[c]["price"]
        for c in results
    )
    total_eur = st.session_state.cash + marked_positions
    portfolio_value = total_eur * st.session_state.currency_rate
    profit = portfolio_value - st.session_state.starting_balance
    st.session_state.history.append({"Time": datetime.now(), "Value": portfolio_value})
    st.session_state.history = st.session_state.history[-600:]


# ----------------------------- HEADER -----------------------------

st.markdown('<div class="eyebrow">NEXUS / DIGITAL ASSET RESEARCH</div>', unsafe_allow_html=True)
header_left, header_right = st.columns([3, 1])
with header_left:
    st.title(page)
    st.caption("Market intelligence · Quantitative research · Paper execution")
with header_right:
    st.markdown('<div style="text-align:right;padding-top:18px"><span class="pill">● SYSTEM ONLINE</span></div>', unsafe_allow_html=True)
if errors:
    st.warning("Market data issue: " + " | ".join(errors))


# ============================================================
# COMMAND CENTER
# ============================================================

if page == "Command Center":
    if results:
        st.markdown("### Account overview")
        a, b, c, d = st.columns(4)
        a.metric("Net liquidation value", f"{portfolio_value:,.2f} SEK")
        b.metric("Unrealized + realized P/L", f"{profit:+,.2f} SEK")
        c.metric("Available cash", f'{st.session_state.cash * 11.5:,.2f} SEK')
        d.metric("Active positions", sum(p["qty"] > 0 for p in st.session_state.positions.values()))

        left, right = st.columns([1.65, 1])
        with left:
            st.markdown("### Portfolio trajectory")
            if st.session_state.history:
                hist = pd.DataFrame(st.session_state.history).set_index("Time")
                fig = go.Figure(go.Scatter(
                    x=hist.index, y=hist["Value"], mode="lines",
                    line=dict(color="#35D6A2", width=2.5), fill="tozeroy", name="Equity"
                ))
                st.plotly_chart(chart_layout(fig, 330), use_container_width=True)
        with right:
            st.markdown("### Market pulse")
            for coin, data in results.items():
                signal_color = "#35D6A2" if data["signal"] == "BUY" else "#FF647C" if data["signal"] == "SELL" else "#E9BE72"
                st.markdown(
                    f'<div class="panel"><div class="panel-title">{coin} / EUR</div>'
                    f'<div class="big-number">€{data["price"]:,.2f}</div>'
                    f'<div style="color:{signal_color};font-weight:700;margin-top:5px">{data["signal"]}</div>'
                    f'<div class="muted">RSI {data["rsi"]:.1f} · Change {data["change"]:+.2f}%</div></div>',
                    unsafe_allow_html=True
                )
        st.markdown("### Market watch")
        watch = pd.DataFrame([{
            "Asset": c, "Last price (EUR)": round(d["price"], 2),
            "Change (sample)": f'{d["change"]:+.2f}%', "RSI": round(d["rsi"], 1),
            "Signal": d["signal"]
        } for c, d in results.items()])
        st.dataframe(watch, use_container_width=True, hide_index=True)
    else:
        st.info("Waiting for market data from Kraken.")


# ============================================================
# MARKETS
# ============================================================

elif page == "Markets":
    if results:
        selected = st.selectbox("Select instrument", list(results.keys()))
        data = results[selected]
        a, b, c, d = st.columns(4)
        a.metric("Last price", f'€{data["price"]:,.2f}')
        b.metric("Sample change", f'{data["change"]:+.2f}%')
        c.metric("RSI (14)", f'{data["rsi"]:.1f}')
        d.metric("Model signal", data["signal"])
        st.markdown("### Price action")
        st.plotly_chart(market_chart(data), use_container_width=True)
        df = data["history"]
        st.markdown("### Indicator monitor")
        latest = df.iloc[-1]
        indicators = pd.DataFrame([
            {"Indicator": "EMA 20", "Value": f'{latest["EMA20"]:.2f}', "Reading": "Short-term trend"},
            {"Indicator": "EMA 50", "Value": f'{latest["EMA50"]:.2f}', "Reading": "Medium-term trend"},
            {"Indicator": "MACD", "Value": f'{latest["MACD"]:.4f}', "Reading": "Momentum"},
            {"Indicator": "MACD signal", "Value": f'{latest["MACD_SIGNAL"]:.4f}', "Reading": "Momentum trigger"},
            {"Indicator": "Bollinger upper", "Value": f'{latest["BB_UPPER"]:.2f}', "Reading": "Upper volatility band"},
            {"Indicator": "Bollinger lower", "Value": f'{latest["BB_LOWER"]:.2f}', "Reading": "Lower volatility band"},
            {"Indicator": "ATR", "Value": f'{latest["ATR"]:.2f}', "Reading": "Average true range"},
            {"Indicator": "ATR %", "Value": f'{latest["ATR_PCT"]:.2f}%', "Reading": "Volatility relative to price"},
        ])
        st.dataframe(indicators, use_container_width=True, hide_index=True)
        st.caption("Sample change is measured across the available recent candles, not an exact 24-hour return.")
    else:
        st.error("No market data available.")


# ============================================================
# PORTFOLIO
# ============================================================

elif page == "Portfolio":
    if results:
        a, b, c = st.columns(3)
        a.metric("Portfolio value", f"{portfolio_value:,.2f} SEK")
        b.metric("Total P/L", f"{profit:+,.2f} SEK")
        c.metric("Cash", f'{st.session_state.cash * 11.5:,.2f} SEK')
        holdings = []
        labels, values = ["Cash"], [st.session_state.cash]
        for coin, pos in st.session_state.positions.items():
            price = results.get(coin, {}).get("price", 0.0)
            value = pos["qty"] * price
            holdings.append({
                "Asset": coin, "Quantity": round(pos["qty"], 8),
                "Entry allocation (EUR)": round(pos["cost"], 2),
                "Market value (EUR)": round(value, 2)
            })
            labels.append(coin)
            values.append(value)
        left, right = st.columns([1.2, 1])
        with left:
            st.markdown("### Holdings")
            st.dataframe(pd.DataFrame(holdings), use_container_width=True, hide_index=True)
        with right:
            st.markdown("### Capital allocation")
            pie = go.Figure(go.Pie(labels=labels, values=values, hole=.68))
            st.plotly_chart(chart_layout(pie, 330), use_container_width=True)
    else:
        st.info("Waiting for current prices.")


# ============================================================
# STRATEGY STUDIO
# ============================================================

elif page == "Strategy Studio":
    st.markdown("### Quantitative strategy workspace")
    st.write("Inspect the rules and indicators that power the NEXUS research engine.")
    st.markdown("""
    - **Trend:** EMA fast/slow relationship
    - **Momentum:** RSI and MACD confirmation
    - **Volatility:** Bollinger Bands and ATR
    - **Risk:** fixed stop, take-profit, trailing stop and account drawdown guard
    """)
    if results:
        selected = st.selectbox("Instrument", list(results.keys()))
        df = results[selected]["history"]
        latest = df.iloc[-1]
        a, b, c, d = st.columns(4)
        a.metric("RSI", f'{latest["RSI"]:.1f}')
        b.metric("MACD histogram", f'{latest["MACD_HIST"]:.4f}')
        c.metric("Bollinger width", f'{latest["BB_WIDTH"] * 100:.2f}%')
        d.metric("ATR", f'{latest["ATR"]:.2f}')
        st.markdown("### Recent indicator readings")
        st.dataframe(
            df.tail(30)[["close", "EMA20", "EMA50", "RSI", "MACD", "MACD_SIGNAL", "BB_UPPER", "BB_LOWER", "ATR"]],
            use_container_width=True
        )
    st.warning("Indicators describe historical price behaviour. They do not predict prices or guarantee profitable trades.")


# ============================================================
# BACKTEST & AI
# ============================================================

elif page == "Backtest & AI":
    st.markdown("### Research, compare and optimize")
    st.caption("All simulations are isolated from the paper account. No live orders are sent.")
    with st.container(border=True):
        st.markdown("#### Test configuration")
        x1, x2, x3 = st.columns(3)
        with x1:
            asset = st.selectbox("Market", ["BTC/EUR", "ETH/EUR"], key="research_asset")
        with x2:
            tf = st.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=1, key="research_tf")
        with x3:
            candles = st.selectbox("Candles", [150, 250, 500, 720], index=2, key="research_candles")
        x4, x5, x6 = st.columns(3)
        with x4:
            balance = st.number_input("Starting balance (EUR)", 100.0, 1000000.0, 1000.0, 100.0, key="research_balance")
        with x5:
            position = st.slider("Position size (%)", 5, 100, 20, 5, key="research_position")
        with x6:
            fee = st.number_input("Fee per order (%)", 0.0, 2.0, 0.4, 0.05, key="research_fee")
        st.markdown("#### Risk controls")
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            sl = st.slider("Stop-loss (%)", 0.0, 20.0, 5.0, 0.5, key="research_sl")
        with r2:
            tp = st.slider("Take-profit (%)", 0.0, 40.0, 10.0, 0.5, key="research_tp")
        with r3:
            trailing = st.slider("Trailing stop (%)", 0.0, 20.0, 0.0, 0.5, key="research_trailing")
        with r4:
            maxdd = st.slider("Max account drawdown (%)", 0.0, 50.0, 15.0, 1.0, key="research_maxdd")
        st.caption("Set a risk control to 0 to disable it. Stop-loss is checked before take-profit if both are touched in the same candle.")
        btn1, btn2 = st.columns(2)
        with btn1:
            compare = st.button("Run strategy comparison", type="primary", use_container_width=True)
        with btn2:
            optimize = st.button("Run robust optimizer", use_container_width=True)

    if compare or optimize:
        try:
            with st.spinner("Fetching Kraken candles and running research..."):
                hist = fetch_history(asset, tf, candles)
                if compare:
                    specs = [
                        ("NEXUS Baseline", {}),
                        ("EMA Crossover", {}),
                        ("RSI Reversal", {"rsi_buy": 30, "rsi_sell": 70}),
                        ("Bollinger Reversal", {}),
                        ("MACD Trend", {}),
                        ("NEXUS Multi-Factor", {"fast": 20, "slow": 50, "rsi_buy": 48, "rsi_sell": 72}),
                    ]
                    rows = []
                    base_detail = None
                    for name, params in specs:
                        ind = add_indicators(hist, params.get("fast", 20), params.get("slow", 50))
                        m, eq, tr = run_backtest(ind, balance, position, fee, name, params, sl, tp, maxdd, trailing)
                        rows.append({"Strategy": name, **m, "Robust score": score_metrics(m)})
                        if name == "NEXUS Multi-Factor":
                            base_detail = (m, eq, tr)
                    st.session_state.last_comparison = {
                        "asset": asset, "timeframe": tf, "candles": len(hist), "rows": rows
                    }
                    if base_detail:
                        m, eq, tr = base_detail
                        st.session_state.last_backtest = {
                            "asset": asset, "timeframe": tf, "candles": len(hist),
                            "metrics": m, "equity": eq, "trades": tr,
                            "start": balance, "strategy": "NEXUS Multi-Factor"
                        }
                if optimize:
                    ranking, params, metrics, eq, trades, split = optimize_strategy(
                        hist, balance, position, fee, sl, tp, maxdd, trailing
                    )
                    st.session_state.last_optimization = {
                        "asset": asset, "timeframe": tf, "candles": len(hist),
                        "ranking": ranking, "params": params, "metrics": metrics,
                        "equity": eq, "trades": trades, "start": balance,
                        "train_candles": split, "test_candles": len(hist) - split
                    }
        except Exception as exc:
            st.error(f"Research run failed: {exc}")

    comparison = st.session_state.get("last_comparison")
    if comparison:
        st.divider()
        st.markdown("### Strategy leaderboard")
        st.caption(f'{comparison["asset"]} · {comparison["timeframe"]} · {comparison["candles"]} completed candles')
        comp_df = pd.DataFrame(comparison["rows"])
        display = comp_df[[
            "Strategy", "final_equity", "total_return", "buy_hold_return",
            "trades", "win_rate", "max_drawdown", "profit_factor", "Robust score"
        ]].rename(columns={
            "final_equity": "Final EUR", "total_return": "Return %",
            "buy_hold_return": "Buy & hold %", "trades": "Trades",
            "win_rate": "Win rate %", "max_drawdown": "Max DD %",
            "profit_factor": "Profit factor"
        })
        st.dataframe(display, use_container_width=True, hide_index=True)
        best = comp_df.sort_values("Robust score", ascending=False).iloc[0]
        st.info(f'Highest risk-adjusted research score: {best["Strategy"]}. Score is a ranking aid, not a forecast.')

    baseline = st.session_state.get("last_backtest")
    if baseline:
        st.divider()
        st.markdown("### Detailed simulation")
        st.caption(f'{baseline["asset"]} · {baseline["timeframe"]} · {baseline["candles"]} candles')
        metric_report(baseline["metrics"])
        st.plotly_chart(equity_chart(baseline["equity"], baseline["strategy"]), use_container_width=True)
        if baseline["trades"]:
            trade_df = pd.DataFrame(baseline["trades"])
            st.dataframe(trade_df, use_container_width=True, hide_index=True)
            st.download_button("Export strategy trades", trade_df.to_csv(index=False), "nexus_strategy_trades.csv", "text/csv")

    optimized = st.session_state.get("last_optimization")
    if optimized:
        st.divider()
        st.markdown("### Robust optimizer — holdout report")
        st.caption(
            f'Optimizer trained on {optimized["train_candles"]} candles; '
            f'holdout period contains {optimized["test_candles"]} candles.'
        )
        p = optimized["params"]
        st.markdown(
            f'<span class="pill">EMA {p["fast"]}/{p["slow"]}</span> '
            f'<span class="pill">RSI buy ≥ {p["rsi_buy"]}</span> '
            f'<span class="pill">RSI exit ≥ {p["rsi_sell"]}</span>',
            unsafe_allow_html=True
        )
        metric_report(optimized["metrics"])
        st.plotly_chart(equity_chart(optimized["equity"], "Optimized holdout"), use_container_width=True)
        st.markdown("#### Top training candidates")
        st.dataframe(optimized["ranking"].head(20), use_container_width=True, hide_index=True)
        if optimized["trades"]:
            test_trades = pd.DataFrame(optimized["trades"])
            st.dataframe(test_trades, use_container_width=True, hide_index=True)
            st.download_button("Export holdout trades", test_trades.to_csv(index=False), "nexus_holdout_trades.csv", "text/csv")
        st.warning("The holdout period is more useful than the training ranking, but one holdout is not proof of future performance. Repeat across markets, timeframes and different date ranges.")

    st.caption("Models omit or simplify spread, slippage, liquidity, latency and exchange outages. Historical simulation is not a promise of future returns.")


# ============================================================
# TRADE JOURNAL
# ============================================================

elif page == "Trade Journal":
    trades = st.session_state.trades
    a, b, c = st.columns(3)
    a.metric("Total simulated orders", len(trades))
    b.metric("Buy orders", sum(t["Action"] == "BUY" for t in trades))
    c.metric("Sell orders", sum(t["Action"] == "SELL" for t in trades))
    if trades:
        journal = pd.DataFrame(trades)
        st.dataframe(journal, use_container_width=True, hide_index=True)
        st.download_button("Export journal CSV", journal.to_csv(index=False), "nexus_paper_journal.csv", "text/csv")
    else:
        st.info("No paper trades yet.")
    st.caption("Journal is currently held in the active app session and may reset when the app restarts.")


# ============================================================
# AI COPILOT
# ============================================================

elif page == "AI Copilot":
    st.markdown("### NEXUS intelligence assistant")
    st.caption("Ask about indicators, strategy behaviour, risk controls or your simulation results.")
    api_key = os.getenv("OPENAI_API_KEY", "")
    try:
        api_key = st.secrets.get("OPENAI_API_KEY", api_key)
    except Exception:
        pass
    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    prompt = st.chat_input("Ask NEXUS...")
    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        market_context = "\n".join(
            f'{coin}: €{d["price"]:.2f}, RSI {d["rsi"]:.1f}, signal {d["signal"]}'
            for coin, d in results.items()
        )
        bt = st.session_state.get("last_backtest")
        opt = st.session_state.get("last_optimization")
        bt_context = ""
        if bt:
            m = bt["metrics"]
            bt_context = f'Last strategy simulation: return {m["total_return"]:.2f}%, max drawdown {m["max_drawdown"]:.2f}%, trades {m["trades"]}.'
        opt_context = ""
        if opt:
            m = opt["metrics"]
            opt_context = f'Optimizer holdout: return {m["total_return"]:.2f}%, max drawdown {m["max_drawdown"]:.2f}%, params {opt["params"]}.'
        system = f"""
You are NEXUS AI, a clear educational crypto research assistant.
Live market snapshot: {market_context}
Paper portfolio: {portfolio_value:.2f} SEK; simulated P/L: {profit:.2f} SEK.
{bt_context}
{opt_context}
Explain uncertainty, fees, slippage, overfitting and drawdown when relevant.
Never promise returns, invent market facts, or tell the user to risk real money.
This application is paper-trading simulation only, not personalized financial advice.
"""
        answer = ""
        with st.chat_message("assistant"):
            if api_key:
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=api_key)
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "system", "content": system}, *st.session_state.chat[-10:]],
                        temperature=0.3,
                    )
                    answer = response.choices[0].message.content or "No response was generated."
                except Exception as exc:
                    answer = f"AI connection failed: {exc}"
            else:
                q = prompt.lower()
                if "macd" in q:
                    answer = "MACD compares two exponential moving averages and a signal line. It is a momentum indicator; crossovers can lag and produce false signals in sideways markets."
                elif "bollinger" in q:
                    answer = "Bollinger Bands show a moving average with volatility bands. Touching a band is not automatically a buy or sell signal; price can ride a band during a strong trend."
                elif "atr" in q or "trailing" in q:
                    answer = "ATR estimates recent price range, not direction. It can help size volatility-based stops, but a stop can fill worse than expected during fast markets."
                elif "optimi" in q or "overfit" in q:
                    answer = "The optimizer ranks a grid on a training segment, then evaluates the selected parameters on a later holdout segment. If the holdout is weak, the strategy has not demonstrated robust performance. Try other markets and date ranges."
                elif "minus" in q or "förlust" in q or "backtest" in q:
                    answer = "Check return against buy-and-hold, drawdown, fees, number of trades and the holdout result. A tiny sample can be misleading. A negative test is useful information: it shows the rules need more research."
                elif "risk" in q or "stop" in q:
                    answer = "Stop-loss, take-profit, trailing stop and maximum drawdown rules can structure a simulation, but gaps, spread, slippage and outages mean they cannot guarantee a maximum loss."
                elif "portfolio" in q or "saldo" in q or "balance" in q:
                    answer = f"Your simulated portfolio is currently worth {portfolio_value:.2f} SEK, with simulated P/L of {profit:+.2f} SEK."
                else:
                    answer = "I can explain RSI, EMA, MACD, Bollinger Bands, ATR, stop-loss, trailing stops, drawdown, optimization and backtest results. Configure OPENAI_API_KEY in Streamlit Secrets to enable the full AI model."
            st.markdown(answer)
        st.session_state.chat.append({"role": "assistant", "content": answer})


# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":
    st.markdown("### Terminal configuration")
    st.markdown("#### Paper trading")
    st.session_state.risk = st.slider("Position size (% of available cash)", 5, 50, int(st.session_state.risk), 5)
    st.session_state.fee = st.slider("Simulated fee (%)", 0.0, 1.0, float(st.session_state.fee), 0.05)
    st.session_state.timeframe = st.selectbox(
        "Market timeframe", ["15m", "1h", "4h", "1d"],
        index=["15m", "1h", "4h", "1d"].index(st.session_state.timeframe)
    )
    st.session_state.refresh = st.select_slider(
        "Dashboard refresh", options=[30, 60, 120, 300], value=int(st.session_state.refresh)
    )
    st.divider()
    st.markdown("#### Automation")
    st.session_state.auto_trade = st.toggle("Enable automatic paper trading", value=st.session_state.auto_trade)
    st.caption("This only simulates trades using public market data. It never sends real orders.")
    st.divider()
    st.markdown("#### Account")
    st.write(f'Starting balance: {st.session_state.starting_balance:.2f} SEK')
    st.write("Display conversion: 1 EUR = 11.5 SEK (fixed estimate, not a live FX rate).")
    st.divider()
    st.markdown("#### AI connection")
    st.write("Optional: add OPENAI_API_KEY in Streamlit Cloud → App settings → Secrets.")
    st.code('OPENAI_API_KEY = "your-api-key"', language="toml")
    st.warning("Never put your API key in GitHub or directly in this Python file.")
    st.divider()
    st.markdown("#### Reset simulation")
    if st.button("Reset virtual account and journal"):
        st.session_state.cash = st.session_state.starting_balance / st.session_state.currency_rate
        st.session_state.positions = {"BTC": {"qty": 0.0, "cost": 0.0}, "ETH": {"qty": 0.0, "cost": 0.0}}
        st.session_state.trades = []
        st.session_state.processed = {}
        st.session_state.history = []
        st.success("Virtual account reset.")


# ----------------------------- FOOTER -----------------------------

st.divider()
st.markdown(
    '<div style="text-align:center;color:#7589A4;font:500 10px DM Mono;letter-spacing:2px;">'
    '◈ NEXUS INTELLIGENCE TERMINAL · PAPER TRADING ONLY · HISTORICAL RESULTS ARE NOT PREDICTIONS'
    '</div>',
    unsafe_allow_html=True,
)
