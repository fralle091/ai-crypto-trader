
import os
from datetime import datetime, timezone
from itertools import product

import ccxt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ============================================================
# NEXUS — PREMIUM DIGITAL ASSET TERMINAL
# Paper trading only. No real orders.
# ============================================================

st.set_page_config(
    page_title="NEXUS | Intelligence Terminal",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------- DESIGN SYSTEM -------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
    --bg:#070B12;
    --surface:#0D1420;
    --surface2:#111C2B;
    --surface3:#172538;
    --border:#202F43;
    --text:#EDF3FC;
    --muted:#8192A9;
    --green:#36D6A0;
    --red:#FF657A;
    --blue:#6FA7FF;
    --purple:#AD91FF;
}

html, body, [class*="css"] {
    font-family:'DM Sans',sans-serif;
}

.stApp {
    background:
        radial-gradient(ellipse at 75% 0%, rgba(38,82,130,.17), transparent 35%),
        var(--bg);
    color:var(--text);
}

.block-container {
    max-width:1700px;
    padding-top:1.5rem;
    padding-bottom:3rem;
}

h1,h2,h3 {
    font-family:'Space Grotesk',sans-serif !important;
    color:var(--text) !important;
    letter-spacing:-.7px;
}

h1 {font-size:2.2rem !important;}
h2 {font-size:1.55rem !important;}
h3 {font-size:1.1rem !important;}

[data-testid="stSidebar"] {
    background:#090F19;
    border-right:1px solid var(--border);
}

[data-testid="stSidebar"] > div:first-child {
    padding-top:1.3rem;
}

[data-testid="stMetric"] {
    background:linear-gradient(145deg,#142237,#0D1725);
    border:1px solid #263A53;
    padding:18px;
    border-radius:13px;
}

[data-testid="stMetricLabel"] {
    color:var(--muted) !important;
    font-size:.75rem;
}

[data-testid="stMetricValue"] {
    color:var(--text) !important;
    font-family:'Space Grotesk',sans-serif;
}

[data-testid="stMetricDelta"] {
    font-family:'DM Mono',monospace;
}

.stButton>button,
.stDownloadButton>button {
    background:#17283D;
    color:#EDF3FC;
    border:1px solid #304762;
    border-radius:9px;
    min-height:2.6rem;
    font-weight:650;
    transition:.2s;
}

.stButton>button:hover,
.stDownloadButton>button:hover {
    background:#223B59;
    border-color:#6FA7FF;
    color:white;
}

button[kind="primary"] {
    background:linear-gradient(100deg,#2466C7,#4388EC) !important;
    border:0 !important;
}

div[data-baseweb="select"]>div,
.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
    background:#111D2C;
    border-color:#2C4059;
    color:white;
    border-radius:9px;
}

[data-testid="stDataFrame"] {
    border:1px solid var(--border);
    border-radius:11px;
}

hr {
    border-color:var(--border);
}

.nx-logo {
    font-family:'Space Grotesk',sans-serif;
    font-size:29px;
    font-weight:700;
    letter-spacing:3px;
    color:#F4F8FF;
}

.nx-subtitle {
    font-family:'DM Mono',monospace;
    font-size:9px;
    letter-spacing:2px;
    color:#8094AE;
    margin-top:-5px;
}

.eyebrow {
    font-family:'DM Mono',monospace;
    color:#7F9BBC;
    font-size:10px;
    letter-spacing:2px;
    text-transform:uppercase;
    margin-bottom:8px;
}

.panel {
    background:linear-gradient(145deg,#14243A,#0D1725);
    border:1px solid #263B55;
    border-radius:14px;
    padding:19px;
    margin-bottom:12px;
}

.panel-label {
    color:#8DA3BF;
    font-family:'DM Mono',monospace;
    font-size:10px;
    letter-spacing:1.6px;
    text-transform:uppercase;
}

.panel-value {
    color:#F1F6FD;
    font-family:'Space Grotesk',sans-serif;
    font-size:27px;
    font-weight:600;
    margin-top:8px;
}

.panel-note {
    color:#8FA2BA;
    font-size:11px;
    margin-top:5px;
}

.status {
    display:inline-block;
    padding:6px 11px;
    border-radius:30px;
    background:#102D29;
    color:#49D9A8;
    border:1px solid #245448;
    font-family:'DM Mono',monospace;
    font-size:10px;
    letter-spacing:1px;
}

.tag {
    display:inline-block;
    padding:5px 9px;
    border:1px solid #304760;
    background:#14243A;
    border-radius:30px;
    color:#B8CBE1;
    font-family:'DM Mono',monospace;
    font-size:10px;
}

div[data-testid="stChatMessage"] {
    background:#111D2C;
    border:1px solid #293D55;
    border-radius:12px;
}

.stTabs [data-baseweb="tab-list"] {
    gap:8px;
    background:#0D1725;
    border:1px solid #26384E;
    padding:6px;
    border-radius:11px;
}

.stTabs [data-baseweb="tab"] {
    color:#9EB0C6;
    border-radius:8px;
}

.stTabs [aria-selected="true"] {
    background:#203854;
    color:white;
}

[data-testid="stExpander"] {
    border:1px solid var(--border);
    border-radius:10px;
}

footer {visibility:hidden;}
</style>
""", unsafe_allow_html=True)


# ------------------------- SESSION STATE -------------------------

DEFAULTS = {
    "cash": 1000 / 11.5,
    "starting_balance": 1000.0,
    "currency_rate": 11.5,
    "position_size": 20,
    "fee": 0.4,
    "timeframe": "1h",
    "refresh": 60,
    "auto_trade": False,
    "positions": {
        "BTC": {"qty": 0.0, "cost": 0.0},
        "ETH": {"qty": 0.0, "cost": 0.0}
    },
    "trades": [],
    "processed": {},
    "history": [],
    "chat": [],
    "comparison": None,
    "backtest": None,
    "optimization": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value


# ------------------------- MARKET CONNECTION -------------------------

@st.cache_resource
def get_exchange():
    return ccxt.kraken({
        "enableRateLimit": True,
        "timeout": 20000
    })


exchange = get_exchange()


# ------------------------- INDICATORS -------------------------

def add_indicators(df, fast=20, slow=50):
    df = df.copy()
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

    mid = close.rolling(20).mean()
    std = close.rolling(20).std()

    df["BB_MID"] = mid
    df["BB_UPPER"] = mid + 2 * std
    df["BB_LOWER"] = mid - 2 * std

    previous = close.shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous).abs(),
        (df["low"] - previous).abs()
    ], axis=1).max(axis=1)

    df["ATR"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    df["ATR_PCT"] = df["ATR"] / close * 100

    return df


# ------------------------- STRATEGY ENGINE -------------------------

STRATEGIES = [
    "NEXUS Multi-Factor",
    "NEXUS Baseline",
    "EMA Crossover",
    "RSI Reversal",
    "Bollinger Reversal",
    "MACD Trend"
]


def get_signal(row, strategy="NEXUS Multi-Factor", params=None):
    params = params or {}

    required = [
        "RSI", "EMA_FAST", "EMA_SLOW",
        "MACD", "MACD_SIGNAL", "BB_UPPER", "BB_LOWER"
    ]

    if any(pd.isna(row.get(x)) for x in required):
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
        if trend_up:
            return "BUY"
        if trend_down:
            return "SELL"
        return "HOLD"

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

    buy_rsi = params.get("rsi_buy", 48)
    sell_rsi = params.get("rsi_sell", 72)
    macd_filter = params.get("macd_filter", True)

    if trend_up and buy_rsi <= rsi <= 68 and (macd_up or not macd_filter):
        return "BUY"

    if trend_down and (macd_down or rsi >= sell_rsi):
        return "SELL"

    return "HOLD"


# ------------------------- LIVE DATA -------------------------

def get_market_data(symbol, timeframe):
    candles = exchange.fetch_ohlcv(
        symbol,
        timeframe=timeframe,
        limit=180
    )

    if not candles:
        raise ValueError("No market data returned")

    df = pd.DataFrame(
        candles,
        columns=["time", "open", "high", "low", "close", "volume"]
    )

    # Ignore unfinished candle
    df = df.iloc[:-1].copy()

    if len(df) < 80:
        raise ValueError("Not enough completed candles")

    df = add_indicators(df)
    last = df.iloc[-1]

    return {
        "price": float(last["close"]),
        "rsi": float(last["RSI"]) if pd.notna(last["RSI"]) else 50,
        "signal": get_signal(last),
        "change": float((last["close"] / df.iloc[-25]["close"] - 1) * 100),
        "candle": int(last["time"]),
        "history": df
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(symbol, timeframe, limit):
    client = ccxt.kraken({
        "enableRateLimit": True,
        "timeout": 25000
    })

    candles = client.fetch_ohlcv(
        symbol,
        timeframe=timeframe,
        limit=limit
    )

    df = pd.DataFrame(
        candles,
        columns=["time", "open", "high", "low", "close", "volume"]
    )

    df = df.iloc[:-1].copy()
    df["Date"] = pd.to_datetime(df["time"], unit="ms", utc=True)

    df = add_indicators(df).reset_index(drop=True)

    if len(df) < 100:
        raise ValueError("Not enough historical data")

    return df


# ------------------------- PAPER TRADING -------------------------

def paper_trade(coin, data):
    if not st.session_state.auto_trade:
        return

    candle = data["candle"]

    if st.session_state.processed.get(coin) == candle:
        return

    st.session_state.processed[coin] = candle

    pos = st.session_state.positions[coin]
    price = data["price"]
    fee = st.session_state.fee / 100

    if data["signal"] == "BUY" and pos["qty"] == 0:
        amount = st.session_state.cash * st.session_state.position_size / 100

        if amount < 5:
            return

        qty = amount * (1 - fee) / price
        st.session_state.cash -= amount

        pos["qty"] = qty
        pos["cost"] = amount

        st.session_state.trades.append({
            "Time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "Asset": coin,
            "Action": "BUY",
            "Price EUR": round(price, 2),
            "Amount EUR": round(amount, 2)
        })

    elif data["signal"] == "SELL" and pos["qty"] > 0:
        proceeds = pos["qty"] * price * (1 - fee)
        st.session_state.cash += proceeds

        st.session_state.trades.append({
            "Time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "Asset": coin,
            "Action": "SELL",
            "Price EUR": round(price, 2),
            "Amount EUR": round(proceeds, 2)
        })

        pos["qty"] = 0.0
        pos["cost"] = 0.0


# ------------------------- BACKTEST ENGINE -------------------------

def run_backtest(
    df, balance, position, fee, strategy,
    params=None, stop_loss=0, take_profit=0,
    max_dd=0, trailing_stop=0
):
    params = params or {}
    fee_rate = fee / 100

    cash = float(balance)
    qty = 0.0
    entry_price = 0.0
    entry_cost = 0.0
    high_water = 0.0
    trades = []
    points = []

    peak = float(balance)
    halted = False

    warmup = min(80, max(30, len(df) // 5))
    points.append({
        "Date": df.iloc[warmup]["Date"],
        "Equity": cash
    })

    def close_position(price, reason, date):
        nonlocal cash, qty, entry_price, entry_cost, high_water

        proceeds = qty * price * (1 - fee_rate)
        pnl = proceeds - entry_cost

        trades.append({
            "Exit Date": date,
            "Exit Reason": reason,
            "Entry Price": entry_price,
            "Exit Price": price,
            "Profit": pnl,
            "Return %": pnl / entry_cost * 100 if entry_cost else 0
        })

        cash += proceeds
        qty = 0.0
        entry_price = 0.0
        entry_cost = 0.0
        high_water = 0.0

    for i in range(warmup, len(df) - 1):
        signal_row = df.iloc[i]
        candle = df.iloc[i + 1]

        op = float(candle["open"])
        hi = float(candle["high"])
        lo = float(candle["low"])
        cl = float(candle["close"])
        date = candle["Date"]

        exit_price = None
        exit_reason = None

        if qty > 0:
            stop_candidates = []

            if stop_loss > 0:
                stop_candidates.append(
                    (entry_price * (1 - stop_loss / 100), "Stop-loss")
                )

            if trailing_stop > 0 and high_water > 0:
                stop_candidates.append(
                    (high_water * (1 - trailing_stop / 100), "Trailing stop")
                )

            active_stop = max(
                [x[0] for x in stop_candidates],
                default=None
            )

            target = (
                entry_price * (1 + take_profit / 100)
                if take_profit > 0 else None
            )

            if active_stop is not None and lo <= active_stop:
                exit_price = min(op, active_stop)
                exit_reason = "Stop-loss"

            elif target is not None and hi >= target:
                exit_price = max(op, target)
                exit_reason = "Take-profit"

        if exit_price is not None and qty > 0:
            close_position(exit_price, exit_reason, date)

        equity = cash + qty * cl
        peak = max(peak, equity)

        drawdown = (equity / peak - 1) * 100 if peak else 0

        if max_dd > 0 and drawdown <= -max_dd and not halted:
            if qty > 0:
                close_position(cl, "Drawdown limit", date)
            halted = True

        if not halted:
            signal = get_signal(signal_row, strategy, params)

            if signal == "SELL" and qty > 0:
                close_position(op, "Strategy exit", date)

            elif signal == "BUY" and qty == 0 and cash > 1:
                allocation = cash * position / 100
                qty = allocation * (1 - fee_rate) / op
                entry_cost = allocation
                entry_price = op
                high_water = op
                cash -= allocation

        if qty > 0:
            high_water = max(high_water, hi)

        equity = cash + qty * cl
        points.append({"Date": date, "Equity": equity})

    last = df.iloc[-1]

    if qty > 0:
        close_position(float(last["close"]), "End of test", last["Date"])

    final_equity = cash

    if points:
        points[-1]["Equity"] = final_equity

    equity_df = pd.DataFrame(points)

    total_return = (final_equity / balance - 1) * 100

    wins = [t for t in trades if t["Profit"] > 0]
    losses = [t for t in trades if t["Profit"] < 0]

    gross_profit = sum(t["Profit"] for t in wins)
    gross_loss = abs(sum(t["Profit"] for t in losses))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else (float("inf") if gross_profit > 0 else 0)
    )

    running_peak = equity_df["Equity"].cummax()
    dd = (equity_df["Equity"] / running_peak - 1) * 100

    metrics = {
        "final_equity": final_equity,
        "total_return": total_return,
        "trades": len(trades),
        "win_rate": len(wins) / len(trades) * 100 if trades else 0,
        "max_drawdown": float(dd.min()) if len(dd) else 0,
        "profit_factor": profit_factor
    }

    return metrics, equity_df, trades


def score_metrics(m):
    pf = min(m["profit_factor"], 3) if m["profit_factor"] != float("inf") else 3
    penalty = 8 if m["trades"] < 5 else 3 if m["trades"] < 10 else 0

    return (
        m["total_return"]
        - abs(m["max_drawdown"]) * .65
        + pf * 1.5
        - penalty
    )


def optimize_strategy(df, balance, position, fee, sl, tp, maxdd, trailing):
    split = int(len(df) * .7)

    train = df.iloc[:split].reset_index(drop=True)
    test = df.iloc[max(0, split - 90):].reset_index(drop=True)

    candidates = []

    for fast, slow, rsi_buy, rsi_sell, macd_filter in product(
        [10, 20, 30],
        [40, 50, 80],
        [45, 50, 55],
        [68, 72, 76],
        [True, False]
    ):
        if fast >= slow or rsi_buy >= rsi_sell:
            continue

        params = {
            "fast": fast,
            "slow": slow,
            "rsi_buy": rsi_buy,
            "rsi_sell": rsi_sell,
            "macd_filter": macd_filter
        }

        train_ind = add_indicators(train, fast, slow)

        metrics, _, _ = run_backtest(
            train_ind, balance, position, fee,
            "NEXUS Multi-Factor", params,
            sl, tp, maxdd, trailing
        )

        candidates.append({
            **params,
            "Training Return %": metrics["total_return"],
            "Training Drawdown %": metrics["max_drawdown"],
            "Training Trades": metrics["trades"],
            "Score": score_metrics(metrics)
        })

    ranking = pd.DataFrame(candidates).sort_values(
        "Score", ascending=False
    ).reset_index(drop=True)

    best = ranking.iloc[0]

    params = {
        "fast": int(best["fast"]),
        "slow": int(best["slow"]),
        "rsi_buy": int(best["rsi_buy"]),
        "rsi_sell": int(best["rsi_sell"]),
        "macd_filter": bool(best["macd_filter"])
    }

    test_ind = add_indicators(test, params["fast"], params["slow"])

    metrics, equity, trades = run_backtest(
        test_ind, balance, position, fee,
        "NEXUS Multi-Factor", params,
        sl, tp, maxdd, trailing
    )

    return ranking, params, metrics, equity, trades, split


# ------------------------- CHARTS -------------------------

def chart_style(fig, height=400):
    fig.update_layout(
        height=height,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=35, b=10),
        font=dict(color="#9FB1C8"),
        legend=dict(orientation="h", y=1.08),
        hovermode="x unified",
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="rgba(130,155,185,.10)")
    )
    return fig


def price_chart(data):
    df = data["history"].tail(120)
    dates = pd.to_datetime(df["time"], unit="ms", utc=True)

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=dates,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Price",
        increasing_line_color="#36D6A0",
        decreasing_line_color="#FF657A"
    ))

    fig.add_trace(go.Scatter(
        x=dates, y=df["EMA20"],
        name="EMA 20",
        line=dict(color="#6FA7FF", width=1.5)
    ))

    fig.add_trace(go.Scatter(
        x=dates, y=df["EMA50"],
        name="EMA 50",
        line=dict(color="#AD91FF", width=1.5)
    ))

    return chart_style(fig, 480)


def equity_chart(eq):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=eq["Date"],
        y=eq["Equity"],
        name="Equity",
        line=dict(color="#36D6A0", width=2.5),
        fill="tozeroy"
    ))

    return chart_style(fig, 370)


def show_metrics(metrics):
    a, b, c, d = st.columns(4)

    a.metric(
        "Final equity",
        f'{metrics["final_equity"]:,.2f} EUR'
    )

    b.metric(
        "Total return",
        f'{metrics["total_return"]:+.2f}%'
    )

    c.metric(
        "Win rate",
        f'{metrics["win_rate"]:.1f}%'
    )

    d.metric(
        "Maximum drawdown",
        f'{metrics["max_drawdown"]:.2f}%'
    )


# ------------------------- NAVIGATION -------------------------

PAGES = [
    "Overview",
    "Trading Terminal",
    "Markets",
    "Portfolio",
    "Strategy Lab",
    "Backtesting",
    "Trade Journal",
    "AI Copilot",
    "Settings"
]

st.sidebar.markdown(
    '<div class="nx-logo">◈ NEXUS</div>'
    '<div class="nx-subtitle">INTELLIGENCE TERMINAL</div>',
    unsafe_allow_html=True
)

st.sidebar.divider()

page = st.sidebar.radio(
    "WORKSPACE",
    PAGES,
    label_visibility="visible"
)

st.sidebar.divider()

st.sidebar.markdown("#### ACCOUNT")

st.sidebar.metric(
    "Starting capital",
    f'{st.session_state.starting_balance:,.0f} SEK'
)

st.sidebar.markdown(
    '<span class="status">● PAPER MODE ACTIVE</span>',
    unsafe_allow_html=True
)

st.sidebar.caption("Public Kraken market data · Simulation only")

st.sidebar.divider()

st.sidebar.markdown("#### SYSTEM")

st.sidebar.caption(f'Timeframe: {st.session_state.timeframe}')
st.sidebar.caption(
    f'Auto trading: {"ON" if st.session_state.auto_trade else "OFF"}'
)

if st.sidebar.button("Refresh market data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()


# ------------------------- FETCH LIVE DATA -------------------------

st_autorefresh(
    interval=int(st.session_state.refresh) * 1000,
    key="nexus_refresh"
)

results = {}
errors = []

for coin in ["BTC", "ETH"]:
    try:
        data = get_market_data(
            coin + "/EUR",
            st.session_state.timeframe
        )
        results[coin] = data
        paper_trade(coin, data)

    except Exception as exc:
        errors.append(f"{coin}: {exc}")


portfolio_value = 0.0
profit = 0.0

if results:
    holdings_value = sum(
        st.session_state.positions[c]["qty"] * results[c]["price"]
        for c in results
    )

    total_eur = st.session_state.cash + holdings_value

    portfolio_value = total_eur * st.session_state.currency_rate
    profit = portfolio_value - st.session_state.starting_balance

    st.session_state.history.append({
        "Time": datetime.now(),
        "Value": portfolio_value
    })

    st.session_state.history = st.session_state.history[-500:]


# ------------------------- GLOBAL HEADER -------------------------

st.markdown(
    '<div class="eyebrow">NEXUS / DIGITAL ASSET INTELLIGENCE</div>',
    unsafe_allow_html=True
)

head1, head2 = st.columns([4, 1])

with head1:
    st.title(page)
    st.caption("Market intelligence · Quantitative research · Portfolio analytics")

with head2:
    st.markdown(
        '<div style="text-align:right;padding-top:20px">'
        '<span class="status">● SYSTEM ONLINE</span></div>',
        unsafe_allow_html=True
    )

if errors:
    st.warning("Market data issue: " + " | ".join(errors))

st.divider()


# ============================================================
# OVERVIEW
# ============================================================

if page == "Overview":

    st.markdown("### Command center")

    if results:

        a, b, c, d = st.columns(4)

        a.metric(
            "Portfolio value",
            f"{portfolio_value:,.2f} SEK"
        )

        b.metric(
            "Total simulated P/L",
            f"{profit:+,.2f} SEK",
            f"{profit / st.session_state.starting_balance * 100:+.2f}%"
        )

        c.metric(
            "Available cash",
            f'{st.session_state.cash * 11.5:,.2f} SEK'
        )

        d.metric(
            "Open positions",
            sum(
                p["qty"] > 0
                for p in st.session_state.positions.values()
            )
        )

        st.markdown("### Market intelligence")

        left, right = st.columns([1.7, 1])

        with left:
            st.markdown("#### Portfolio performance")

            if len(st.session_state.history) > 1:
                hist = pd.DataFrame(st.session_state.history)

                fig = go.Figure()

                fig.add_trace(go.Scatter(
                    x=hist["Time"],
                    y=hist["Value"],
                    line=dict(color="#36D6A0", width=2.5),
                    fill="tozeroy",
                    name="Portfolio"
                ))

                st.plotly_chart(
                    chart_style(fig, 350),
                    use_container_width=True
                )

            else:
                st.info("Portfolio history will appear as data is collected.")

        with right:
            st.markdown("#### Live market pulse")

            for coin, data in results.items():

                color = (
                    "#36D6A0" if data["signal"] == "BUY"
                    else "#FF657A" if data["signal"] == "SELL"
                    else "#E9BE72"
                )

                st.markdown(
                    f'<div class="panel">'
                    f'<div class="panel-label">{coin} / EUR</div>'
                    f'<div class="panel-value">€{data["price"]:,.2f}</div>'
                    f'<div style="color:{color};font-weight:700">'
                    f'{data["signal"]}</div>'
                    f'<div class="panel-note">'
                    f'RSI {data["rsi"]:.1f} · Change {data["change"]:+.2f}%'
                    f'</div></div>',
                    unsafe_allow_html=True
                )

        st.markdown("### Market overview")

        market_table = pd.DataFrame([
            {
                "Asset": coin,
                "Price EUR": round(data["price"], 2),
                "Change": f'{data["change"]:+.2f}%',
                "RSI": round(data["rsi"], 1),
                "Signal": data["signal"]
            }
            for coin, data in results.items()
        ])

        st.dataframe(
            market_table,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("Waiting for Kraken market data.")


# ============================================================
# TRADING TERMINAL
# ============================================================

elif page == "Trading Terminal":

    if results:

        coin = st.selectbox(
            "Trading instrument",
            list(results.keys())
        )

        data = results[coin]

        a, b, c, d = st.columns(4)

        a.metric("Last price", f'€{data["price"]:,.2f}')
        b.metric("Market change", f'{data["change"]:+.2f}%')
        c.metric("RSI", f'{data["rsi"]:.1f}')
        d.metric("Signal", data["signal"])

        st.markdown("### Advanced price chart")

        st.plotly_chart(
            price_chart(data),
            use_container_width=True
        )

        tabs = st.tabs([
            "Technical indicators",
            "Market information",
            "Trading rules"
        ])

        with tabs[0]:

            df = data["history"]
            latest = df.iloc[-1]

            indicator_data = pd.DataFrame([
                {"Indicator": "EMA 20", "Value": latest["EMA20"]},
                {"Indicator": "EMA 50", "Value": latest["EMA50"]},
                {"Indicator": "RSI", "Value": latest["RSI"]},
                {"Indicator": "MACD", "Value": latest["MACD"]},
                {"Indicator": "MACD Signal", "Value": latest["MACD_SIGNAL"]},
                {"Indicator": "ATR", "Value": latest["ATR"]},
                {"Indicator": "Bollinger Upper", "Value": latest["BB_UPPER"]},
                {"Indicator": "Bollinger Lower", "Value": latest["BB_LOWER"]}
            ])

            st.dataframe(
                indicator_data.round(4),
                use_container_width=True,
                hide_index=True
            )

        with tabs[1]:

            st.write(f"Instrument: {coin}/EUR")
            st.write(f"Timeframe: {st.session_state.timeframe}")
            st.write("Exchange: Kraken")
            st.write("Data type: Public OHLCV market data")
            st.write("Execution: Paper trading only")

        with tabs[2]:

            st.write("The NEXUS Multi-Factor model combines trend and momentum.")
            st.write("EMA measures trend direction.")
            st.write("RSI measures momentum.")
            st.write("MACD provides momentum confirmation.")
            st.warning("Signals are experimental research outputs, not forecasts.")

    else:
        st.error("Market data unavailable.")


# ============================================================
# MARKETS
# ============================================================

elif page == "Markets":

    st.markdown("### Digital asset market monitor")

    if results:

        for coin, data in results.items():

            with st.container(border=True):

                left, mid, right = st.columns([2, 2, 1])

                left.markdown(f"#### {coin} / EUR")
                left.metric("Price", f'€{data["price"]:,.2f}')

                mid.metric(
                    "Recent change",
                    f'{data["change"]:+.2f}%'
                )

                right.metric("RSI", f'{data["rsi"]:.1f}')

                st.plotly_chart(
                    price_chart(data),
                    use_container_width=True
                )

    else:
        st.info("Waiting for market data.")


# ============================================================
# PORTFOLIO
# ============================================================

elif page == "Portfolio":

    if results:

        st.markdown("### Portfolio overview")

        a, b, c = st.columns(3)

        a.metric("Net asset value", f"{portfolio_value:,.2f} SEK")
        b.metric("Profit / loss", f"{profit:+,.2f} SEK")
        c.metric("Cash available", f'{st.session_state.cash * 11.5:,.2f} SEK')

        holdings = []
        labels = ["Cash"]
        values = [st.session_state.cash]

        for coin, pos in st.session_state.positions.items():

            price = results.get(coin, {}).get("price", 0)
            value = pos["qty"] * price

            holdings.append({
                "Asset": coin,
                "Quantity": round(pos["qty"], 8),
                "Entry cost EUR": round(pos["cost"], 2),
                "Market value EUR": round(value, 2)
            })

            labels.append(coin)
            values.append(value)

        left, right = st.columns([1.3, 1])

        with left:
            st.markdown("#### Asset holdings")

            st.dataframe(
                pd.DataFrame(holdings),
                use_container_width=True,
                hide_index=True
            )

        with right:
            st.markdown("#### Capital allocation")

            fig = go.Figure(go.Pie(
                labels=labels,
                values=values,
                hole=.68
            ))

            st.plotly_chart(
                chart_style(fig, 330),
                use_container_width=True
            )

        st.markdown("#### Portfolio history")

        if len(st.session_state.history) > 1:

            hist = pd.DataFrame(st.session_state.history)

            fig = go.Figure(go.Scatter(
                x=hist["Time"],
                y=hist["Value"],
                line=dict(color="#36D6A0", width=2),
                fill="tozeroy"
            ))

            st.plotly_chart(
                chart_style(fig, 330),
                use_container_width=True
            )

    else:
        st.info("Waiting for current prices.")


# ============================================================
# STRATEGY LAB
# ============================================================

elif page == "Strategy Lab":

    st.markdown("### Quantitative research workspace")

    st.write(
        "Explore the indicators and strategies used by the NEXUS research engine."
    )

    strategy = st.selectbox(
        "Strategy",
        STRATEGIES
    )

    st.markdown("#### Strategy description")

    descriptions = {
        "NEXUS Multi-Factor": "Combines EMA trend, RSI momentum and MACD confirmation.",
        "NEXUS Baseline": "Uses EMA 20/50 and RSI conditions.",
        "EMA Crossover": "Uses fast and slow EMA trend direction.",
        "RSI Reversal": "Looks for RSI overbought and oversold conditions.",
        "Bollinger Reversal": "Uses Bollinger Bands and RSI.",
        "MACD Trend": "Combines EMA trend with MACD momentum."
    }

    st.info(descriptions[strategy])

    if results:

        coin = st.selectbox(
            "Asset analysis",
            list(results.keys()),
            key="strategy_coin"
        )

        df = results[coin]["history"]
        latest = df.iloc[-1]

        a, b, c, d = st.columns(4)

        a.metric("RSI", f'{latest["RSI"]:.1f}')
        b.metric("MACD", f'{latest["MACD"]:.4f}')
        c.metric("ATR", f'{latest["ATR"]:.2f}')
        d.metric("Bollinger width", f'{(latest["BB_UPPER"] - latest["BB_LOWER"]) / latest["BB_MID"] * 100:.2f}%')

        st.markdown("#### Recent indicator history")

        st.dataframe(
            df.tail(30)[[
                "close", "EMA20", "EMA50", "RSI",
                "MACD", "MACD_SIGNAL", "ATR"
            ]].round(4),
            use_container_width=True
        )

    st.warning(
        "Historical indicators can produce false signals. "
        "No strategy is guaranteed to be profitable."
    )


# ============================================================
# BACKTESTING
# ============================================================

elif page == "Backtesting":

    st.markdown("### Strategy research and optimization")

    st.caption(
        "Historical simulations are separate from your paper portfolio."
    )

    with st.container(border=True):

        st.markdown("#### Test configuration")

        a, b, c = st.columns(3)

        with a:
            asset = st.selectbox(
                "Market",
                ["BTC/EUR", "ETH/EUR"],
                key="bt_asset"
            )

        with b:
            timeframe = st.selectbox(
                "Timeframe",
                ["15m", "1h", "4h", "1d"],
                index=1,
                key="bt_tf"
            )

        with c:
            candles = st.selectbox(
                "Historical candles",
                [150, 250, 500, 720],
                index=2,
                key="bt_candles"
            )

        a, b, c = st.columns(3)

        with a:
            balance = st.number_input(
                "Starting balance EUR",
                min_value=100.0,
                max_value=1000000.0,
                value=1000.0,
                step=100.0
            )

        with b:
            position = st.slider(
                "Position size %",
                5, 100, 20, 5
            )

        with c:
            fee = st.number_input(
                "Fee per order %",
                0.0, 2.0, 0.4, 0.05
            )

        st.markdown("#### Risk management")

        a, b, c, d = st.columns(4)

        with a:
            sl = st.slider("Stop-loss %", 0.0, 20.0, 5.0, .5)

        with b:
            tp = st.slider("Take-profit %", 0.0, 40.0, 10.0, .5)

        with c:
            trailing = st.slider("Trailing stop %", 0.0, 20.0, 0.0, .5)

        with d:
            maxdd = st.slider("Maximum drawdown %", 0.0, 50.0, 15.0, 1.0)

        st.caption("Set a risk control to zero to disable it.")

        a, b = st.columns(2)

        with a:
            run_compare = st.button(
                "Run strategy comparison",
                type="primary",
                use_container_width=True
            )

        with b:
            run_optimizer = st.button(
                "Run AI parameter optimizer",
                use_container_width=True
            )

    if run_compare or run_optimizer:

        try:

            with st.spinner("Downloading market history and running simulations..."):

                hist = fetch_history(asset, timeframe, candles)

                if run_compare:

                    specs = [
                        ("NEXUS Multi-Factor", {}),
                        ("NEXUS Baseline", {}),
                        ("EMA Crossover", {}),
                        ("RSI Reversal", {"rsi_buy": 30, "rsi_sell": 70}),
                        ("Bollinger Reversal", {}),
                        ("MACD Trend", {})
                    ]

                    rows = []

                    for name, params in specs:

                        ind = add_indicators(
                            hist,
                            params.get("fast", 20),
                            params.get("slow", 50)
                        )

                        metrics, equity, trades = run_backtest(
                            ind, balance, position, fee,
                            name, params, sl, tp, maxdd, trailing
                        )

                        rows.append({
                            "Strategy": name,
                            **metrics,
                            "Score": score_metrics(metrics)
                        })

                        if name == "NEXUS Multi-Factor":

                            st.session_state.backtest = {
                                "metrics": metrics,
                                "equity": equity,
                                "trades": trades,
                                "asset": asset,
                                "timeframe": timeframe
                            }

                    st.session_state.comparison = rows

                if run_optimizer:

                    ranking, params, metrics, equity, trades, split = optimize_strategy(
                        hist, balance, position, fee,
                        sl, tp, maxdd, trailing
                    )

                    st.session_state.optimization = {
                        "ranking": ranking,
                        "params": params,
                        "metrics": metrics,
                        "equity": equity,
                        "trades": trades,
                        "train": split,
                        "test": len(hist) - split,
                        "asset": asset,
                        "timeframe": timeframe
                    }

        except Exception as exc:
            st.error(f"Research error: {exc}")

    comparison = st.session_state.comparison

    if comparison:

        st.divider()
        st.markdown("### Strategy leaderboard")

        comp = pd.DataFrame(comparison)

        display = comp[[
            "Strategy", "final_equity", "total_return",
            "trades", "win_rate", "max_drawdown",
            "profit_factor", "Score"
        ]].rename(columns={
            "final_equity": "Final EUR",
            "total_return": "Return %",
            "trades": "Trades",
            "win_rate": "Win rate %",
            "max_drawdown": "Max drawdown %",
            "profit_factor": "Profit factor"
        })

        st.dataframe(
            display.round(3),
            use_container_width=True,
            hide_index=True
        )

        best = comp.sort_values("Score", ascending=False).iloc[0]

        st.info(
            f'Highest research score: {best["Strategy"]}. '
            "This is a historical ranking, not a prediction."
        )

    bt = st.session_state.backtest

    if bt:

        st.divider()
        st.markdown("### Detailed backtest")

        show_metrics(bt["metrics"])

        st.plotly_chart(
            equity_chart(bt["equity"]),
            use_container_width=True
        )

        if bt["trades"]:

            trades_df = pd.DataFrame(bt["trades"])

            st.dataframe(
                trades_df,
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                "Download backtest trades",
                trades_df.to_csv(index=False),
                "nexus_backtest.csv",
                "text/csv"
            )

    opt = st.session_state.optimization

    if opt:

        st.divider()
        st.markdown("### Optimizer holdout results")

        st.caption(
            f'Training: {opt["train"]} candles · '
            f'Test: {opt["test"]} candles'
        )

        p = opt["params"]

        st.markdown(
            f'<span class="tag">EMA {p["fast"]}/{p["slow"]}</span> '
            f'<span class="tag">RSI buy {p["rsi_buy"]}</span> '
            f'<span class="tag">RSI exit {p["rsi_sell"]}</span>',
            unsafe_allow_html=True
        )

        show_metrics(opt["metrics"])

        st.plotly_chart(
            equity_chart(opt["equity"]),
            use_container_width=True
        )

        st.markdown("#### Highest-ranked training parameters")

        st.dataframe(
            opt["ranking"].head(20),
            use_container_width=True,
            hide_index=True
        )

        st.warning(
            "A holdout result is not proof of future performance. "
            "Test different periods and markets before drawing conclusions."
        )

    st.caption(
        "Simulations simplify spread, slippage, liquidity, latency and outages. "
        "Historical performance does not guarantee future results."
    )


# ============================================================
# TRADE JOURNAL
# ============================================================

elif page == "Trade Journal":

    st.markdown("### Paper trading activity")

    trades = st.session_state.trades

    a, b, c = st.columns(3)

    a.metric("Total orders", len(trades))
    b.metric("Buy orders", sum(t["Action"] == "BUY" for t in trades))
    c.metric("Sell orders", sum(t["Action"] == "SELL" for t in trades))

    if trades:

        journal = pd.DataFrame(trades)

        st.dataframe(
            journal,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "Export journal",
            journal.to_csv(index=False),
            "nexus_trade_journal.csv",
            "text/csv"
        )

    else:
        st.info("Your paper trading journal is empty.")

    st.caption("The journal is stored in the current app session and may reset on restart.")


# ============================================================
# AI COPILOT
# ============================================================

elif page == "AI Copilot":

    st.markdown("### NEXUS Intelligence")

    st.caption(
        "Ask questions about technical indicators, strategies, "
        "risk management and your simulations."
    )

    api_key = os.getenv("OPENAI_API_KEY", "")

    try:
        api_key = st.secrets.get("OPENAI_API_KEY", api_key)
    except Exception:
        pass

    for message in st.session_state.chat:

        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask NEXUS anything...")

    if prompt:

        st.session_state.chat.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        market_context = "\n".join([
            f'{coin}: EUR {d["price"]:.2f}, RSI {d["rsi"]:.1f}, signal {d["signal"]}'
            for coin, d in results.items()
        ])

        system = f"""
You are NEXUS AI, an advanced educational crypto research assistant.

Current market data:
{market_context}

Simulated portfolio value: {portfolio_value:.2f} SEK.
Simulated profit/loss: {profit:.2f} SEK.

Explain technical indicators clearly.
Be honest about uncertainty.
Discuss fees, slippage, drawdown and overfitting when relevant.
Never promise profits or invent market facts.
Never encourage the user to risk real money.
This app is paper trading only.
"""

        answer = ""

        with st.chat_message("assistant"):

            if api_key:

                try:

                    from openai import OpenAI

                    client = OpenAI(api_key=api_key)

                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system},
                            *st.session_state.chat[-10:]
                        ],
                        temperature=.3
                    )

                    answer = (
                        response.choices[0].message.content
                        or "No response generated."
                    )

                except Exception as exc:
                    answer = f"AI connection failed: {exc}"

            else:

                q = prompt.lower()

                if "rsi" in q:
                    answer = "RSI measures momentum on a scale from 0 to 100. Values above 70 are often considered overbought and below 30 oversold. These levels are not automatic trading signals."

                elif "macd" in q:
                    answer = "MACD compares two exponential moving averages and a signal line. It can help identify momentum changes, but it can lag and produce false signals."

                elif "ema" in q:
                    answer = "EMA is an exponential moving average. A faster EMA reacts more quickly to price changes than a slower EMA. Crossovers can help describe trends."

                elif "bollinger" in q:
                    answer = "Bollinger Bands measure volatility around a moving average. Price touching a band does not automatically mean it will reverse."

                elif "risk" in q or "stop" in q:
                    answer = "Stop-loss and position sizing can structure risk in a simulation. Real execution can differ because of gaps, fees, spread and slippage."

                elif "portfolio" in q or "balance" in q:
                    answer = f"Your simulated portfolio is currently worth {portfolio_value:.2f} SEK. Simulated P/L: {profit:+.2f} SEK."

                elif "backtest" in q or "optimization" in q:
                    answer = "Backtesting evaluates historical rules. Compare results with buy-and-hold, drawdown, trade count and a separate test period. Good historical results do not guarantee future performance."

                else:
                    answer = "I can explain RSI, EMA, MACD, Bollinger Bands, ATR, backtesting, optimization and risk management. Add OPENAI_API_KEY in Streamlit Secrets to enable the full AI model."

            st.markdown(answer)

        st.session_state.chat.append({
            "role": "assistant",
            "content": answer
        })


# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":

    st.markdown("### Terminal configuration")

    st.markdown("#### Paper account")

    st.session_state.position_size = st.slider(
        "Position size (% of available cash)",
        5, 50,
        int(st.session_state.position_size),
        5
    )

    st.session_state.fee = st.slider(
        "Simulated transaction fee (%)",
        0.0, 1.0,
        float(st.session_state.fee),
        .05
    )

    st.divider()

    st.markdown("#### Market data")

    st.session_state.timeframe = st.selectbox(
        "Default timeframe",
        ["15m", "1h", "4h", "1d"],
        index=["15m", "1h", "4h", "1d"].index(
            st.session_state.timeframe
        )
    )

    st.session_state.refresh = st.select_slider(
        "Dashboard refresh interval",
        options=[30, 60, 120, 300],
        value=int(st.session_state.refresh)
    )

    st.divider()

    st.markdown("#### Automation")

    st.session_state.auto_trade = st.toggle(
        "Enable automatic paper trading",
        value=st.session_state.auto_trade
    )

    st.caption(
        "This only simulates trades. It never sends real exchange orders."
    )

    st.divider()

    st.markdown("#### AI connection")

    st.write(
        "Optional: add an OpenAI API key in Streamlit Cloud → "
        "App settings → Secrets."
    )

    st.code(
        'OPENAI_API_KEY = "your-api-key"',
        language="toml"
    )

    st.warning(
        "Never publish your API key in GitHub or put it directly in this file."
    )

    st.divider()

    st.markdown("#### Account information")

    st.write(
        f'Starting balance: {st.session_state.starting_balance:.2f} SEK'
    )

    st.write(
        "Display conversion: 1 EUR = 11.5 SEK. "
        "This is a fixed estimate, not a live exchange rate."
    )

    st.divider()

    st.markdown("#### Reset simulation")

    if st.button(
        "Reset virtual account",
        type="primary"
    ):

        st.session_state.cash = (
            st.session_state.starting_balance
            / st.session_state.currency_rate
        )

        st.session_state.positions = {
            "BTC": {"qty": 0.0, "cost": 0.0},
            "ETH": {"qty": 0.0, "cost": 0.0}
        }

        st.session_state.trades = []
        st.session_state.processed = {}
        st.session_state.history = []

        st.success("Virtual account reset.")


# ------------------------- FOOTER -------------------------

st.divider()

st.markdown(
    '<div style="text-align:center;color:#637A96;'
    'font-family:DM Mono,monospace;font-size:10px;'
    'letter-spacing:2px;padding:15px">'
    '◈ NEXUS INTELLIGENCE TERMINAL · PAPER TRADING ONLY'
    '<br>HISTORICAL RESULTS ARE NOT PREDICTIONS'
    '</div>',
    unsafe_allow_html=True
)
