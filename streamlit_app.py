import os
from datetime import datetime
from itertools import product

import ccxt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# =====================================================
# CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="NEXUS | AI Trading Terminal",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# PREMIUM DESIGN
# =====================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root {
    --bg:#080C14; --panel:#101827; --border:#233149; --text:#EDF3FC;
    --muted:#8B9BB2; --green:#25D6A2; --red:#FF6178; --blue:#6C9BFF;
    --purple:#A78BFA;
}
html,body,[class*="css"] {font-family:'DM Sans',sans-serif;}
.stApp {background:radial-gradient(ellipse at 75% 0%,#15233a 0%,transparent 35%),var(--bg);color:var(--text);}
header[data-testid="stHeader"] {background:transparent;}
.block-container {max-width:1500px;padding-top:2rem;padding-bottom:4rem;}
h1,h2,h3 {font-family:'Space Grotesk',sans-serif!important;color:var(--text)!important;letter-spacing:-.5px;}
[data-testid="stSidebar"] {background:#0B1220;border-right:1px solid var(--border);}
[data-testid="stMetric"] {background:linear-gradient(145deg,#16243A,#101827);border:1px solid var(--border);padding:20px;border-radius:16px;}
[data-testid="stMetricLabel"] {color:var(--muted)!important;font-size:.8rem;}
[data-testid="stMetricValue"] {color:var(--text)!important;font-family:'Space Grotesk',sans-serif;}
.stButton>button {border-radius:10px;border:1px solid #344967;background:#17243A;color:white;font-weight:600;}
.stButton>button:hover {border-color:#6C9BFF;background:#203453;color:white;}
div[data-baseweb="select"]>div,.stTextInput input,.stNumberInput input,.stTextArea textarea {background:#111D2E;border-color:#34445D;color:white;border-radius:10px;}
[data-testid="stDataFrame"] {border:1px solid var(--border);border-radius:12px;}
hr {border-color:var(--border);}
.nexus-brand {font-family:'Space Grotesk',sans-serif;font-size:25px;font-weight:700;letter-spacing:2px;color:white;}
.nexus-sub {color:#8193AC;font-size:10px;letter-spacing:2px;}
.section-label {color:#8193AC;font-size:11px;font-weight:700;letter-spacing:2px;margin-bottom:8px;}
.panel {background:linear-gradient(145deg,#142137,#101827);border:1px solid #263750;border-radius:16px;padding:20px;margin-bottom:12px;}
.small-muted {color:#8B9BB2;font-size:12px;}
div[data-testid="stChatMessage"] {background:#111D2E;border:1px solid #263750;border-radius:14px;padding:12px;}
</style>
""", unsafe_allow_html=True)


# =====================================================
# DEFAULT SETTINGS
# =====================================================

DEFAULTS = {
    "starting_balance": 1000.0,
    "risk": 20,
    "fee": 0.4,
    "refresh": 60,
    "timeframe": "1h",
    "auto_trade": False,
    "cash": 1000.0 / 11.5,
    "positions": {
        "BTC": {"qty": 0.0, "cost": 0.0},
        "ETH": {"qty": 0.0, "cost": 0.0}
    },
    "trades": [],
    "processed": {},
    "history": [],
    "chat": [],
    "currency_rate": 11.5,
    "last_backtest": None,
    "last_optimization": None
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

exchange = ccxt.kraken({"enableRateLimit": True, "timeout": 15000})


# =====================================================
# INDICATORS AND SIGNALS
# =====================================================

def add_indicators(df, fast=20, slow=50):
    df = df.copy()
    df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["EMA_FAST"] = df["close"].ewm(span=fast, adjust=False).mean()
    df["EMA_SLOW"] = df["close"].ewm(span=slow, adjust=False).mean()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


def get_signal(row):
    rsi = row["RSI"]
    if pd.isna(rsi):
        return "HOLD"
    if row["EMA20"] > row["EMA50"] and 50 < rsi < 68:
        return "BUY"
    if row["EMA20"] < row["EMA50"] or rsi > 75:
        return "SELL"
    return "HOLD"


def strategy_signal(row, strategy, params):
    rsi = row["RSI"]
    if pd.isna(rsi):
        return "HOLD"

    if strategy == "NEXUS Baseline":
        return get_signal(row)

    if strategy == "EMA Crossover":
        fast = row["EMA_FAST"]
        slow = row["EMA_SLOW"]
        if fast > slow:
            return "BUY"
        if fast < slow:
            return "SELL"
        return "HOLD"

    if strategy == "RSI Reversal":
        if rsi < params.get("rsi_buy", 30):
            return "BUY"
        if rsi > params.get("rsi_sell", 70):
            return "SELL"
        return "HOLD"

    # Tuned EMA + RSI strategy
    if row["EMA_FAST"] > row["EMA_SLOW"] and rsi >= params["rsi_buy"] and rsi <= params["rsi_buy_max"]:
        return "BUY"
    if row["EMA_FAST"] < row["EMA_SLOW"] or rsi >= params["rsi_sell"]:
        return "SELL"
    return "HOLD"


def analyze(symbol, timeframe):
    candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=150)
    df = pd.DataFrame(candles, columns=["time","open","high","low","close","volume"])
    df = df.iloc[:-1].copy()
    if len(df) < 55:
        raise ValueError("Not enough candle data")
    df = add_indicators(df)
    last = df.iloc[-1]
    rsi = float(last["RSI"]) if pd.notna(last["RSI"]) else 50.0
    change = ((last["close"] / df.iloc[-25]["close"]) - 1) * 100
    return {
        "price": float(last["close"]), "rsi": rsi,
        "signal": get_signal(last), "change": float(change),
        "candle": int(last["time"]), "history": df
    }


# =====================================================
# HISTORICAL DATA AND BACKTEST ENGINE
# =====================================================

@st.cache_data(ttl=300)
def fetch_backtest_data(symbol, timeframe, limit):
    client = ccxt.kraken({"enableRateLimit": True, "timeout": 20000})
    candles = client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not candles:
        raise ValueError("Kraken returned no historical data.")
    df = pd.DataFrame(candles, columns=["time","open","high","low","close","volume"])
    df = df.iloc[:-1].copy()
    df = add_indicators(df)
    df["Date"] = pd.to_datetime(df["time"], unit="ms")
    if len(df) < 80:
        raise ValueError("Not enough historical candles. Try a larger candle count or timeframe.")
    return df.reset_index(drop=True)


def run_backtest(df, starting_balance, position_size, fee_percent,
                 strategy="NEXUS Baseline", params=None,
                 stop_loss=0, take_profit=0, max_drawdown=0):
    """Signals use candle close; orders execute no earlier than next candle open."""
    params = params or {}
    fee = fee_percent / 100
    cash = float(starting_balance)
    qty = 0.0
    entry_cost = 0.0
    entry_price = 0.0
    entry_date = None
    trades = []
    points = []
    peak = float(starting_balance)
    halted = False
    first = min(60, max(1, len(df)//4))
    points.append({"Date": df.iloc[first]["Date"], "Equity": cash})

    for i in range(first, len(df)-1):
        signal_row = df.iloc[i]
        candle = df.iloc[i+1]
        open_price = float(candle["open"])
        close_price = float(candle["close"])
        low_price = float(candle["low"])
        high_price = float(candle["high"])
        date = candle["Date"]

        # Risk controls are evaluated against the next candle's range.
        if qty > 0:
            stop_price = entry_price * (1 - stop_loss/100) if stop_loss > 0 else None
            target_price = entry_price * (1 + take_profit/100) if take_profit > 0 else None
            exit_price = None
            exit_reason = None

            # Conservative assumption: if both levels are touched, stop loss wins.
            if stop_price is not None and low_price <= stop_price:
                exit_price, exit_reason = stop_price, "Stop-loss"
            elif target_price is not None and high_price >= target_price:
                exit_price, exit_reason = target_price, "Take-profit"

            if exit_price is not None:
                proceeds = qty * exit_price * (1-fee)
                pnl = proceeds - entry_cost
                trades.append({
                    "Entry Date": entry_date, "Exit Date": date,
                    "Action": exit_reason, "Entry Price": entry_price,
                    "Exit Price": exit_price, "Entry Cost": entry_cost,
                    "Exit Value": proceeds, "Profit": pnl,
                    "Return %": pnl/entry_cost*100 if entry_cost else 0
                })
                cash += proceeds
                qty, entry_cost, entry_price, entry_date = 0.0, 0.0, 0.0, None

        # Portfolio-level drawdown protection. Once triggered, trading stops.
        current_equity = cash + qty * close_price
        peak = max(peak, current_equity)
        dd = (current_equity / peak - 1) * 100 if peak else 0
        if max_drawdown > 0 and dd <= -max_drawdown and not halted:
            if qty > 0:
                proceeds = qty * close_price * (1-fee)
                pnl = proceeds - entry_cost
                trades.append({
                    "Entry Date": entry_date, "Exit Date": date,
                    "Action": "Max drawdown stop", "Entry Price": entry_price,
                    "Exit Price": close_price, "Entry Cost": entry_cost,
                    "Exit Value": proceeds, "Profit": pnl,
                    "Return %": pnl/entry_cost*100 if entry_cost else 0
                })
                cash += proceeds
                qty, entry_cost, entry_price, entry_date = 0.0, 0.0, 0.0, None
            halted = True

        signal = strategy_signal(signal_row, strategy, params)
        if not halted:
            if signal == "SELL" and qty > 0:
                proceeds = qty * open_price * (1-fee)
                pnl = proceeds - entry_cost
                trades.append({
                    "Entry Date": entry_date, "Exit Date": date,
                    "Action": "Signal sell", "Entry Price": entry_price,
                    "Exit Price": open_price, "Entry Cost": entry_cost,
                    "Exit Value": proceeds, "Profit": pnl,
                    "Return %": pnl/entry_cost*100 if entry_cost else 0
                })
                cash += proceeds
                qty, entry_cost, entry_price, entry_date = 0.0, 0.0, 0.0, None
            elif signal == "BUY" and qty == 0 and cash > 0:
                amount = cash * position_size / 100
                if amount > 0:
                    qty = amount * (1-fee) / open_price
                    entry_cost = amount
                    entry_price = open_price
                    entry_date = date
                    cash -= amount

        equity = cash + qty * close_price
        peak = max(peak, equity)
        points.append({"Date": date, "Equity": equity})

    # Close any remaining position at the last close.
    last = df.iloc[-1]
    if qty > 0:
        proceeds = qty * float(last["close"]) * (1-fee)
        pnl = proceeds - entry_cost
        trades.append({
            "Entry Date": entry_date, "Exit Date": last["Date"],
            "Action": "End of test", "Entry Price": entry_price,
            "Exit Price": float(last["close"]), "Entry Cost": entry_cost,
            "Exit Value": proceeds, "Profit": pnl,
            "Return %": pnl/entry_cost*100 if entry_cost else 0
        })
        cash += proceeds
        qty = 0.0

    final_equity = cash
    if points:
        points[-1]["Equity"] = final_equity
    equity_df = pd.DataFrame(points)
    if equity_df.empty:
        equity_df = pd.DataFrame([{"Date": last["Date"], "Equity": final_equity}])

    start_price = float(df.iloc[first+1]["open"])
    end_price = float(df.iloc[-1]["close"])
    buy_qty = starting_balance * (1-fee) / start_price
    buy_hold_value = buy_qty * end_price * (1-fee)
    total_return = (final_equity/starting_balance - 1)*100
    buy_hold_return = (buy_hold_value/starting_balance - 1)*100

    running_peak = equity_df["Equity"].cummax()
    drawdown = (equity_df["Equity"]/running_peak - 1)*100
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    winners = [t for t in trades if t["Profit"] > 0]
    losers = [t for t in trades if t["Profit"] < 0]
    gross_profit = sum(t["Profit"] for t in winners)
    gross_loss = abs(sum(t["Profit"] for t in losers))
    pf = gross_profit/gross_loss if gross_loss else (float("inf") if gross_profit else 0.0)

    metrics = {
        "final_equity": final_equity, "total_return": total_return,
        "buy_hold_value": buy_hold_value, "buy_hold_return": buy_hold_return,
        "trades": len(trades),
        "win_rate": len(winners)/len(trades)*100 if trades else 0,
        "max_drawdown": max_dd, "profit_factor": pf
    }
    return metrics, equity_df, trades


def optimize_strategy(df, starting_balance, position_size, fee,
                      stop_loss, take_profit, max_drawdown):
    """Search a small parameter grid on training data only."""
    split = int(len(df) * 0.70)
    train = df.iloc[:split].reset_index(drop=True)
    test = df.iloc[split-60:].reset_index(drop=True)  # indicator warm-up overlap
    candidates = []

    grid = product(
        [10, 20, 30],       # fast EMA
        [40, 50, 80],       # slow EMA
        [45, 50, 55],       # RSI lower bound
        [62, 68, 72]        # RSI sell threshold
    )
    for fast, slow, buy_rsi, sell_rsi in grid:
        if fast >= slow or buy_rsi >= sell_rsi:
            continue
        candidate_params = {
            "fast": fast, "slow": slow,
            "rsi_buy": buy_rsi, "rsi_buy_max": min(68, buy_rsi+13),
            "rsi_sell": sell_rsi
        }
        candidate_df = add_indicators(train, fast, slow)
        m, _, _ = run_backtest(
            candidate_df, starting_balance, position_size, fee,
            "Optimized EMA + RSI", candidate_params,
            stop_loss, take_profit, max_drawdown
        )
        candidates.append({
            **candidate_params,
            "Training Return %": m["total_return"],
            "Training Max DD %": m["max_drawdown"],
            "Training Trades": m["trades"]
        })

    ranking = pd.DataFrame(candidates)
    if ranking.empty:
        raise ValueError("No valid parameter combinations were found.")
    # Penalize parameter sets that barely trade; rank by return with drawdown tie-break.
    ranking = ranking.sort_values(
        ["Training Return %", "Training Max DD %"],
        ascending=[False, False]
    ).reset_index(drop=True)
    best = ranking.iloc[0].to_dict()
    best_params = {
        "fast": int(best["fast"]), "slow": int(best["slow"]),
        "rsi_buy": int(best["rsi_buy"]),
        "rsi_buy_max": int(best["rsi_buy_max"]),
        "rsi_sell": int(best["rsi_sell"])
    }
    test_df = add_indicators(test, best_params["fast"], best_params["slow"])
    test_metrics, test_equity, test_trades = run_backtest(
        test_df, starting_balance, position_size, fee,
        "Optimized EMA + RSI", best_params,
        stop_loss, take_profit, max_drawdown
    )
    return ranking, best_params, test_metrics, test_equity, test_trades, split


# =====================================================
# PAPER TRADING ENGINE
# =====================================================

def execute_paper_trade(coin, data):
    if not st.session_state.auto_trade:
        return
    candle = data["candle"]
    if st.session_state.processed.get(coin) == candle:
        return
    st.session_state.processed[coin] = candle
    position = st.session_state.positions[coin]
    signal, price = data["signal"], data["price"]
    fee = st.session_state.fee/100

    if signal == "BUY" and position["qty"] == 0:
        amount = st.session_state.cash * st.session_state.risk/100
        if amount < 5:
            return
        quantity = amount*(1-fee)/price
        st.session_state.cash -= amount
        position["qty"], position["cost"] = quantity, amount
        st.session_state.trades.append({
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Asset": coin, "Action": "BUY",
            "Price EUR": round(price, 2), "Amount EUR": round(amount, 2)
        })
    elif signal == "SELL" and position["qty"] > 0:
        proceeds = position["qty"]*price*(1-fee)
        st.session_state.cash += proceeds
        st.session_state.trades.append({
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Asset": coin, "Action": "SELL",
            "Price EUR": round(price, 2), "Amount EUR": round(proceeds, 2)
        })
        position["qty"], position["cost"] = 0.0, 0.0


# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.markdown(
    '<div class="nexus-brand">◈ NEXUS</div><div class="nexus-sub">AI TRADING TERMINAL</div>',
    unsafe_allow_html=True
)
st.sidebar.divider()
pages = ["Overview","Markets","Portfolio","Strategy Lab","Backtesting",
         "Trade Journal","AI Copilot","Settings"]
page = st.sidebar.radio("WORKSPACE", pages)
st.sidebar.divider()
st.sidebar.markdown("### ACCOUNT")
st.sidebar.metric("Virtual starting balance", f'{st.session_state.starting_balance:,.0f} SEK')
st.sidebar.markdown('<p class="small-muted">● PAPER TRADING ACTIVE</p>', unsafe_allow_html=True)
st.sidebar.divider()
st.sidebar.markdown("### SYSTEM")
st.sidebar.caption("Exchange: Kraken")
st.sidebar.caption("Markets: BTC / ETH")
st.sidebar.caption("Mode: Simulation only")


# =====================================================
# LOAD LIVE MARKET DATA
# =====================================================

st_autorefresh(interval=st.session_state.refresh*1000, key="nexus_refresh")
results, errors = {}, []
for coin in ["BTC", "ETH"]:
    try:
        data = analyze(coin+"/EUR", st.session_state.timeframe)
        results[coin] = data
        execute_paper_trade(coin, data)
    except Exception as error:
        errors.append(f"{coin}: {error}")

portfolio_value, profit = 0.0, 0.0
if results:
    position_value = sum(
        st.session_state.positions[c]["qty"]*d["price"] for c,d in results.items()
    )
    equity = st.session_state.cash + position_value
    portfolio_value = equity*st.session_state.currency_rate
    profit = portfolio_value-st.session_state.starting_balance
    st.session_state.history.append({"Time":datetime.now(),"Value":portfolio_value})
    st.session_state.history = st.session_state.history[-500:]


# =====================================================
# CHART HELPERS
# =====================================================

def create_market_chart(data):
    df = data["history"].tail(100).copy()
    df["Date"] = pd.to_datetime(df["time"], unit="ms")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df["Date"], open=df["open"], high=df["high"], low=df["low"],
        close=df["close"], name="Market",
        increasing_line_color="#25D6A2", decreasing_line_color="#FF6178"
    ))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["EMA20"], name="EMA 20",
                             line=dict(color="#6C9BFF",width=1.5)))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["EMA50"], name="EMA 50",
                             line=dict(color="#A78BFA",width=1.5)))
    fig.update_layout(
        height=450, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10,r=10,t=30,b=10),
        xaxis_rangeslider_visible=False, legend=dict(orientation="h",y=1.08),
        font=dict(color="#B8C7DC")
    )
    return fig


def metrics_row(metrics):
    a,b,c,d = st.columns(4)
    a.metric("Final balance", f'{metrics["final_equity"]:,.2f} EUR', f'{metrics["total_return"]:+.2f}%')
    b.metric("Strategy return", f'{metrics["total_return"]:+.2f}%')
    c.metric("Buy & hold", f'{metrics["buy_hold_return"]:+.2f}%')
    d.metric("Closed trades", metrics["trades"])
    e,f,g = st.columns(3)
    e.metric("Win rate", f'{metrics["win_rate"]:.1f}%')
    f.metric("Max drawdown", f'{metrics["max_drawdown"]:.2f}%')
    pf = "∞" if metrics["profit_factor"] == float("inf") else f'{metrics["profit_factor"]:.2f}'
    g.metric("Profit factor", pf)


def show_equity_chart(equity_df, starting_balance, label="Strategy"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity_df["Date"], y=equity_df["Equity"], mode="lines",
        name=label, line=dict(color="#25D6A2",width=3), fill="tozeroy"
    ))
    fig.add_hline(y=starting_balance,line_dash="dash",line_color="#8B9BB2",
                  annotation_text="Starting balance")
    fig.update_layout(
        height=390,template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=10,r=10,t=25,b=10),
        xaxis_title="Date",yaxis_title="Account value (EUR)"
    )
    st.plotly_chart(fig,use_container_width=True)


# =====================================================
# HEADER
# =====================================================

st.markdown('<div class="section-label">NEXUS / TRADING WORKSPACE</div>', unsafe_allow_html=True)
st.title(page)
st.caption("Advanced market intelligence and portfolio analytics")
if errors:
    st.warning("Market data warning: "+"; ".join(errors))


# =====================================================
# OVERVIEW
# =====================================================

if page == "Overview":
    st.markdown("### Performance Overview")
    if results:
        a,b,c,d = st.columns(4)
        a.metric("Portfolio Value",f"{portfolio_value:,.2f} SEK")
        b.metric("Total P/L",f"{profit:+,.2f} SEK")
        c.metric("Available Cash",f'{st.session_state.cash*11.5:,.2f} SEK')
        d.metric("Open Positions",sum(1 for p in st.session_state.positions.values() if p["qty"]>0))
        st.divider()
        left,right = st.columns([1.6,1])
        with left:
            st.markdown("### Portfolio Performance")
            if st.session_state.history:
                h = pd.DataFrame(st.session_state.history).set_index("Time")
                fig = go.Figure(go.Scatter(
                    x=h.index,y=h["Value"],mode="lines",fill="tozeroy",
                    line=dict(color="#25D6A2",width=3),name="Portfolio"
                ))
                fig.update_layout(height=330,template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=5,r=5,t=20,b=5))
                st.plotly_chart(fig,use_container_width=True)
        with right:
            st.markdown("### Market Signals")
            for coin,data in results.items():
                st.markdown(
                    f'<div class="panel"><b>{coin}</b><br><span class="small-muted">Price</span>'
                    f'<h3>{data["price"]:,.2f} EUR</h3><span class="small-muted">Signal</span>'
                    f'<h3>{data["signal"]}</h3><span class="small-muted">RSI: {data["rsi"]:.1f}</span></div>',
                    unsafe_allow_html=True
                )
        st.divider()
        st.markdown("### Market Snapshot")
        rows=[{"Asset":c,"Price EUR":round(d["price"],2),"Change":f'{d["change"]:+.2f}%',
               "RSI":round(d["rsi"],1),"Signal":d["signal"]} for c,d in results.items()]
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    else:
        st.info("Waiting for market data.")


# =====================================================
# MARKETS
# =====================================================

elif page == "Markets":
    st.markdown("### Live Market Analysis")
    if results:
        selected=st.selectbox("Choose market",list(results.keys()))
        data=results[selected]
        a,b,c=st.columns(3)
        a.metric("Market Price",f'{data["price"]:,.2f} EUR')
        b.metric("Price Change",f'{data["change"]:+.2f}%')
        c.metric("RSI",f'{data["rsi"]:.2f}')
        st.markdown("### Price Chart")
        st.plotly_chart(create_market_chart(data),use_container_width=True)
        st.markdown("### Technical Indicators")
        st.write(f'EMA20: {data["history"].iloc[-1]["EMA20"]:.2f} EUR')
        st.write(f'EMA50: {data["history"].iloc[-1]["EMA50"]:.2f} EUR')
        st.write(f'RSI: {data["rsi"]:.2f}')
        st.info(f'Current strategy signal: {data["signal"]}')
    else:
        st.error("No market data available.")


# =====================================================
# PORTFOLIO
# =====================================================

elif page == "Portfolio":
    st.markdown("### Account Analytics")
    if results:
        a,b,c=st.columns(3)
        a.metric("Portfolio",f"{portfolio_value:,.2f} SEK")
        b.metric("Profit / Loss",f"{profit:+,.2f} SEK")
        c.metric("Cash",f'{st.session_state.cash*11.5:,.2f} SEK')
        st.divider()
        rows=[]
        for coin,pos in st.session_state.positions.items():
            price=results.get(coin,{}).get("price",0)
            rows.append({"Asset":coin,"Quantity":round(pos["qty"],8),
                         "Average Cost EUR":round(pos["cost"],2),
                         "Market Value EUR":round(pos["qty"]*price,2)})
        st.markdown("### Holdings")
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        st.markdown("### Allocation")
        labels=["Cash"]; values=[st.session_state.cash]
        for coin,pos in st.session_state.positions.items():
            labels.append(coin)
            values.append(pos["qty"]*results.get(coin,{}).get("price",0))
        fig=go.Figure(go.Pie(labels=labels,values=values,hole=.65))
        fig.update_layout(template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",height=350)
        st.plotly_chart(fig,use_container_width=True)
    else:
        st.info("Waiting for market prices.")


# =====================================================
# STRATEGY LAB
# =====================================================

elif page == "Strategy Lab":
    st.markdown("### Strategy Research")
    st.write("Compare the logic behind the available rule-based strategies.")
    st.markdown("""
    **NEXUS Baseline:** EMA20 above EMA50 and RSI 50–68 to buy; EMA20 below EMA50 or RSI above 75 to sell.

    **EMA Crossover:** Buys when the fast EMA is above the slow EMA and sells when it is below.

    **RSI Reversal:** Buys when RSI is low and sells when RSI is high.

    **Optimized EMA + RSI:** Uses parameter values selected from historical training data. It must still be checked on unseen data.
    """)
    if results:
        selected=st.selectbox("Choose asset for indicator analysis",list(results.keys()))
        data=results[selected]; df=data["history"]
        a,b,c=st.columns(3)
        a.metric("Current RSI",f'{data["rsi"]:.2f}')
        b.metric("EMA20",f'{df.iloc[-1]["EMA20"]:.2f}')
        c.metric("EMA50",f'{df.iloc[-1]["EMA50"]:.2f}')
        st.markdown("### Recent Indicator Values")
        st.dataframe(df.tail(20)[["close","EMA20","EMA50","RSI"]],use_container_width=True)
    st.warning("Signals are mathematical rules, not reliable predictions. A strategy can lose money.")


# =====================================================
# BACKTESTING + OPTIMIZATION + RISK CONTROLS
# =====================================================

elif page == "Backtesting":
    st.markdown("### NEXUS Strategy Lab")
    st.write("Run historical simulations, compare strategies, optimize parameters and test risk controls.")
    st.info("All results are simulations only. They do not change your paper account or place real orders.")

    with st.container(border=True):
        st.markdown("#### Market and account")
        c1,c2,c3=st.columns(3)
        with c1:
            asset=st.selectbox("Market",["BTC/EUR","ETH/EUR"],key="bt_asset")
        with c2:
            timeframe=st.selectbox("Timeframe",["15m","1h","4h","1d"],index=1,key="bt_tf")
        with c3:
            candle_count=st.selectbox("Historical candles",[150,250,500,720],index=2,key="bt_count")
        c4,c5,c6=st.columns(3)
        with c4:
            balance=st.number_input("Starting balance (EUR)",100.0,1000000.0,1000.0,100.0,key="bt_balance")
        with c5:
            position=st.slider("Position size (% of cash)",5,100,20,5,key="bt_position")
        with c6:
            fee=st.number_input("Fee per order (%)",0.0,2.0,0.4,0.05,key="bt_fee")

        st.markdown("#### Risk management")
        r1,r2,r3=st.columns(3)
        with r1:
            sl=st.slider("Stop-loss (%)",0.0,20.0,5.0,0.5,key="bt_sl")
        with r2:
            tp=st.slider("Take-profit (%)",0.0,50.0,10.0,0.5,key="bt_tp")
        with r3:
            max_dd=st.slider("Maximum account drawdown (%)",0.0,50.0,15.0,1.0,key="bt_maxdd")
        st.caption("Set a risk control to 0% to disable it. If stop-loss and take-profit are both touched in one candle, the simulation assumes the stop-loss happened first.")

        run_col,opt_col=st.columns(2)
        with run_col:
            run_all=st.button("Run strategy comparison",type="primary",use_container_width=True)
        with opt_col:
            run_opt=st.button("Optimize strategy automatically",use_container_width=True)

    if run_all or run_opt:
        try:
            with st.spinner("Loading Kraken history and running simulations..."):
                hist=fetch_backtest_data(asset,timeframe,candle_count)
                if run_all:
                    comparison_results=[]
                    strategy_specs=[
                        ("NEXUS Baseline",{}),
                        ("EMA Crossover",{}),
                        ("RSI Reversal",{"rsi_buy":30,"rsi_sell":70})
                    ]
                    for name,params in strategy_specs:
                        # EMA fast/slow columns used by the crossover strategy.
                        strat_df=add_indicators(hist,20,50)
                        m,eq,tr=run_backtest(strat_df,balance,position,fee,name,params,sl,tp,max_dd)
                        comparison_results.append({"Strategy":name,**m})
                    st.session_state["last_comparison"]={
                        "asset":asset,"timeframe":timeframe,"candles":len(hist),
                        "rows":comparison_results
                    }
                    # Save baseline details for chart and journal.
                    base_df=add_indicators(hist,20,50)
                    m,eq,tr=run_backtest(base_df,balance,position,fee,"NEXUS Baseline",{},sl,tp,max_dd)
                    st.session_state["last_backtest"]={
                        "asset":asset,"timeframe":timeframe,"candles":len(hist),
                        "metrics":m,"equity":eq,"trades":tr,"start":balance,
                        "strategy":"NEXUS Baseline"
                    }
                if run_opt:
                    ranking,best_params,test_metrics,test_equity,test_trades,split=optimize_strategy(
                        hist,balance,position,fee,sl,tp,max_dd
                    )
                    st.session_state["last_optimization"]={
                        "asset":asset,"timeframe":timeframe,"candles":len(hist),
                        "ranking":ranking,"params":best_params,
                        "metrics":test_metrics,"equity":test_equity,
                        "trades":test_trades,"start":balance,
                        "train_candles":split,
                        "test_candles":len(hist)-split
                    }
        except Exception as error:
            st.error(f"Simulation failed: {error}")

    if st.session_state.get("last_comparison"):
        comp=st.session_state["last_comparison"]
        st.divider()
        st.markdown("### Strategy comparison")
        st.caption(f'{comp["asset"]} · {comp["timeframe"]} · {comp["candles"]} candles')
        comp_df=pd.DataFrame(comp["rows"])
        st.dataframe(
            comp_df[["Strategy","final_equity","total_return","buy_hold_return",
                     "trades","win_rate","max_drawdown","profit_factor"]].rename(columns={
                "final_equity":"Final EUR","total_return":"Return %",
                "buy_hold_return":"Buy & Hold %","trades":"Trades",
                "win_rate":"Win Rate %","max_drawdown":"Max DD %",
                "profit_factor":"Profit Factor"
            }),
            use_container_width=True,hide_index=True
        )
        best_row=comp_df.sort_values("total_return",ascending=False).iloc[0]
        st.caption(f'Highest historical return in this comparison: {best_row["Strategy"]} ({best_row["total_return"]:+.2f}%). This does not mean it will perform best in the future.')

    if st.session_state.get("last_backtest"):
        res=st.session_state["last_backtest"]
        st.divider()
        st.markdown("### Baseline detailed report")
        st.caption(f'{res["asset"]} · {res["timeframe"]} · {res["candles"]} candles')
        metrics_row(res["metrics"])
        show_equity_chart(res["equity"],res["start"],"NEXUS Baseline")
        if res["trades"]:
            st.markdown("#### Trade log")
            trade_df=pd.DataFrame(res["trades"])
            st.dataframe(trade_df,use_container_width=True,hide_index=True)
            st.download_button("Download baseline trades CSV",trade_df.to_csv(index=False),
                               "nexus_baseline_trades.csv","text/csv")

    if st.session_state.get("last_optimization"):
        opt=st.session_state["last_optimization"]
        st.divider()
        st.markdown("### Automatic optimization")
        st.caption(
            f'Parameters selected using {opt["train_candles"]} training candles. '
            f'Results below use a separate later period of {opt["test_candles"]} candles.'
        )
        p=opt["params"]
        st.write(
            f'**Selected settings:** EMA {p["fast"]}/{p["slow"]} · '
            f'RSI buy {p["rsi_buy"]}–{p["rsi_buy_max"]} · RSI sell {p["rsi_sell"]}'
        )
        st.markdown("#### Out-of-sample results")
        metrics_row(opt["metrics"])
        show_equity_chart(opt["equity"],opt["start"],"Optimized strategy — test period")
        st.markdown("#### Best parameter combinations (training period)")
        st.dataframe(opt["ranking"].head(15),use_container_width=True,hide_index=True)
        if opt["trades"]:
            opt_trades=pd.DataFrame(opt["trades"])
            st.dataframe(opt_trades,use_container_width=True,hide_index=True)
            st.download_button("Download optimized test trades CSV",opt_trades.to_csv(index=False),
                               "nexus_optimized_test_trades.csv","text/csv")
        st.warning("Optimization can overfit historical data. Treat the separate test-period result as more informative than the training ranking, and test on other markets and timeframes too.")

    st.caption("Backtests omit some real-world effects such as spread, slippage, outages and changing liquidity. Historical performance does not predict future returns.")


# =====================================================
# TRADE JOURNAL
# =====================================================

elif page == "Trade Journal":
    st.markdown("### Trading Activity")
    trades=st.session_state.trades
    a,b,c=st.columns(3)
    a.metric("Total Trades",len(trades))
    b.metric("Buy Orders",sum(t["Action"]=="BUY" for t in trades))
    c.metric("Sell Orders",sum(t["Action"]=="SELL" for t in trades))
    st.divider()
    if trades:
        trade_df=pd.DataFrame(trades)
        st.dataframe(trade_df,use_container_width=True,hide_index=True)
        st.download_button("Download Trade History CSV",trade_df.to_csv(index=False),
                           "nexus_trade_history.csv","text/csv")
    else:
        st.info("No simulated trades yet.")
    st.caption("Trade history is stored in the active app session and may reset when the app restarts.")


# =====================================================
# AI COPILOT
# =====================================================

elif page == "AI Copilot":
    st.markdown("### ◈ NEXUS AI Copilot")
    st.write("Ask about your portfolio, indicators, backtests, strategy settings or risk controls.")
    st.info("Educational assistant only. It does not provide personalized financial advice.")
    api_key=os.getenv("OPENAI_API_KEY","")
    try:
        api_key=st.secrets.get("OPENAI_API_KEY",api_key)
    except Exception:
        pass

    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt=st.chat_input("Ask NEXUS anything...")
    if prompt:
        st.session_state.chat.append({"role":"user","content":prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        bt_context=""
        if st.session_state.get("last_backtest"):
            bm=st.session_state["last_backtest"]["metrics"]
            bt_context=f'Last baseline backtest return: {bm["total_return"]:.2f}%, max drawdown: {bm["max_drawdown"]:.2f}%, trades: {bm["trades"]}.'
        opt_context=""
        if st.session_state.get("last_optimization"):
            om=st.session_state["last_optimization"]["metrics"]
            op=st.session_state["last_optimization"]["params"]
            opt_context=f'Optimized out-of-sample return: {om["total_return"]:.2f}%, parameters: {op}.'
        market_context="\n".join(
            f'{coin}: {d["price"]:.2f} EUR, RSI {d["rsi"]:.1f}, signal {d["signal"]}'
            for coin,d in results.items()
        )
        system_context=f"""
You are NEXUS AI, an educational crypto market and backtesting assistant.
Live market context: {market_context}
Paper portfolio value: {portfolio_value:.2f} SEK; P/L: {profit:.2f} SEK.
{bt_context}
{opt_context}
Explain in clear, concise language. Never promise profit or claim signals guarantee price movement.
Explain backtest limitations, overfitting, fees, slippage and risk when relevant.
This app is simulation only. Do not tell the user to risk real money.
"""
        answer=""
        with st.chat_message("assistant"):
            if api_key:
                try:
                    from openai import OpenAI
                    client=OpenAI(api_key=api_key)
                    response=client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role":"system","content":system_context},
                            *st.session_state.chat[-10:]
                        ],
                        temperature=.35
                    )
                    answer=response.choices[0].message.content or "I could not generate a response."
                except Exception as error:
                    answer=f"AI connection failed: {error}"
            else:
                low=prompt.lower()
                if "backtest" in low or "minus" in low or "förlust" in low or "resultat" in low:
                    answer="A negative backtest means the tested rules lost value over that historical sample. Check the comparison against buy-and-hold, fees, number of trades and maximum drawdown. Automatic optimization can also overfit, so the separate test period matters more than the training result."
                elif "risk" in low or "stop" in low or "loss" in low:
                    answer="Stop-loss limits the loss on an individual position, take-profit closes after a target gain, and maximum drawdown can stop the strategy after an account-level decline. These controls reduce some risks but cannot guarantee a maximum loss, especially when prices gap or data is incomplete."
                elif "optimer" in low or "optimize" in low or "bäst" in low:
                    answer="The optimizer searches combinations of EMA and RSI settings on the training section, then tests the selected settings on a later section. Prefer settings that remain reasonably stable across several assets and timeframes rather than choosing only the highest return."
                elif "rsi" in low:
                    answer="RSI measures momentum. Values near 70 or above are often called overbought and values near 30 or below oversold, but strong trends can stay extreme for a long time."
                elif "ema" in low:
                    answer="EMA is an exponential moving average. A shorter EMA reacts faster to recent prices; comparing a fast and slow EMA can help describe trend direction, but it can produce false signals in sideways markets."
                elif "portfolio" in low or "balance" in low:
                    answer=f"Your simulated portfolio is worth {portfolio_value:.2f} SEK with simulated P/L of {profit:+.2f} SEK."
                else:
                    answer="I can explain RSI, EMA, strategy comparison, parameter optimization, stop-loss, take-profit, drawdown and backtest results. Add OPENAI_API_KEY in Streamlit Secrets to enable full AI chat."
            st.markdown(answer)
        st.session_state.chat.append({"role":"assistant","content":answer})


# =====================================================
# SETTINGS
# =====================================================

elif page == "Settings":
    st.markdown("### System Configuration")
    st.markdown("#### Trading Settings")
    st.session_state.risk=st.slider("Position size (% of available cash)",5,50,
                                    st.session_state.risk,5)
    st.session_state.fee=st.slider("Simulated trading fee (%)",0.0,1.0,
                                   float(st.session_state.fee),.05)
    st.session_state.timeframe=st.selectbox(
        "Market timeframe",["15m","1h","4h","1d"],
        index=["15m","1h","4h","1d"].index(st.session_state.timeframe)
    )
    st.session_state.refresh=st.select_slider(
        "Dashboard refresh interval",options=[30,60,120,300],
        value=st.session_state.refresh
    )
    st.divider()
    st.markdown("#### Automation")
    st.session_state.auto_trade=st.toggle(
        "Enable automatic paper trading",value=st.session_state.auto_trade
    )
    st.caption("When enabled, the strategy can simulate trades on completed candles. It never places real orders.")
    st.divider()
    st.markdown("#### Account")
    st.write(f'Starting balance: {st.session_state.starting_balance:.2f} SEK')
    st.write("Currency conversion: 1 EUR = 11.5 SEK (fixed estimate)")
    st.divider()
    st.markdown("#### AI Configuration")
    st.write("To activate full AI chat, configure OPENAI_API_KEY in Streamlit Cloud → App settings → Secrets.")
    st.code('OPENAI_API_KEY = "your-api-key"',language="toml")
    st.warning("Never publish your API key in GitHub or in your Python code.")
    st.divider()
    st.markdown("#### Reset Virtual Account")
    if st.button("Reset account and trading history"):
        st.session_state.cash=st.session_state.starting_balance/11.5
        st.session_state.positions={"BTC":{"qty":0.0,"cost":0.0},"ETH":{"qty":0.0,"cost":0.0}}
        st.session_state.trades=[]
        st.session_state.processed={}
        st.session_state.history=[]
        st.success("Virtual account reset.")


# =====================================================
# FOOTER
# =====================================================

st.divider()
st.markdown(
    '<div style="text-align:center;color:#71839B;font-size:11px;letter-spacing:2px;">'
    '◈ NEXUS TRADING TERMINAL · PAPER TRADING ONLY</div>',
    unsafe_allow_html=True
)
