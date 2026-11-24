
import streamlit as st
import ccxt
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# PAGE CONFIG
st.set_page_config(
    page_title="MY AI TRADER",
    page_icon="🤖",
    layout="wide"
)

# DESIGN
st.markdown("""
<style>
.stApp {
    background: #080D17;
    color: #F1F5F9;
}
header[data-testid="stHeader"] {
    background: transparent;
}
.block-container {
    max-width: 1350px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}
h1, h2, h3 {
    color: #F8FAFC !important;
}
[data-testid="stMetric"] {
    background: linear-gradient(145deg, #142236, #101927);
    border: 1px solid #26364B;
    padding: 18px;
    border-radius: 14px;
}
[data-testid="stMetricLabel"] {
    color: #94A3B8 !important;
}
[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] {
    background: #0D1726;
}
[data-testid="stDataFrame"] {
    border: 1px solid #26364B;
    border-radius: 12px;
}
hr {
    border-color: #26364B;
}
</style>
""", unsafe_allow_html=True)

# SETTINGS
START_SEK = 1000
EUR_SEK = 11.5
FEE = 0.004

# SESSION STATE
if "cash" not in st.session_state:
    st.session_state.cash = START_SEK / EUR_SEK
    st.session_state.positions = {
        "BTC": {"qty": 0.0, "cost": 0.0},
        "ETH": {"qty": 0.0, "cost": 0.0}
    }
    st.session_state.trades = []
    st.session_state.processed = {}
    st.session_state.portfolio_history = []

# SIDEBAR
st.sidebar.title("🤖 MY AI TRADER")
st.sidebar.caption("PROFESSIONAL TRADING TERMINAL")
st.sidebar.divider()

page = st.sidebar.radio(
    "NAVIGATION",
    ["Dashboard", "Portfolio", "Settings"]
)

st.sidebar.divider()
st.sidebar.metric("Starting Balance", "1 000 SEK")
st.sidebar.caption("PAPER TRADING MODE")
st.sidebar.caption("Market data: Kraken")

# AUTO REFRESH
st_autorefresh(interval=60000, key="refresh")

# EXCHANGE
exchange = ccxt.kraken({
    "enableRateLimit": True
})

# MARKET ANALYSIS
def analyze(symbol):
    candles = exchange.fetch_ohlcv(
        symbol,
        timeframe="1h",
        limit=100
    )

    df = pd.DataFrame(
        candles,
        columns=[
            "time", "open", "high",
            "low", "close", "volume"
        ]
    )

    df = df.iloc[:-1].copy()

    if len(df) < 50:
        raise ValueError("Not enough market data")

    df["EMA20"] = df["close"].ewm(
        span=20, adjust=False
    ).mean()

    df["EMA50"] = df["close"].ewm(
        span=50, adjust=False
    ).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1/14, adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/14, adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["RSI"] = 100 - (100 / (1 + rs))

    last = df.iloc[-1]
    rsi = float(last["RSI"]) if pd.notna(last["RSI"]) else 50.0

    if last["EMA20"] > last["EMA50"] and 50 < rsi < 68:
        signal = "BUY"
    elif last["EMA20"] < last["EMA50"] or rsi > 75:
        signal = "SELL"
    else:
        signal = "HOLD"

    change = (
        (last["close"] / df.iloc[-25]["close"]) - 1
    ) * 100

    return {
        "price": float(last["close"]),
        "rsi": rsi,
        "signal": signal,
        "candle": int(last["time"]),
        "change": float(change),
        "history": df.tail(40)
    }

# PAPER TRADING
def paper_trade(coin, data):
    signal = data["signal"]
    price = data["price"]
    candle = data["candle"]

    if st.session_state.processed.get(coin) == candle:
        return

    st.session_state.processed[coin] = candle
    position = st.session_state.positions[coin]

    if signal == "BUY" and position["qty"] == 0:
        amount = st.session_state.cash * 0.20

        if amount < 5:
            return

        quantity = amount * (1 - FEE) / price

        st.session_state.cash -= amount
        position["qty"] = quantity
        position["cost"] = amount

        st.session_state.trades.append({
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Coin": coin,
            "Action": "BUY",
            "Price EUR": round(price, 2),
            "Amount EUR": round(amount, 2)
        })

    elif signal == "SELL" and position["qty"] > 0:
        proceeds = position["qty"] * price * (1 - FEE)

        st.session_state.cash += proceeds

        st.session_state.trades.append({
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Coin": coin,
            "Action": "SELL",
            "Price EUR": round(price, 2),
            "Amount EUR": round(proceeds, 2)
        })

        position["qty"] = 0.0
        position["cost"] = 0.0

# GET MARKET DATA
results = {}
errors = []

for coin in ["BTC", "ETH"]:
    try:
        data = analyze(coin + "/EUR")
        results[coin] = data
        paper_trade(coin, data)
    except Exception as error:
        errors.append(f"{coin}: {error}")

# PORTFOLIO VALUE
if results:
    position_value = sum(
        st.session_state.positions[coin]["qty"] * data["price"]
        for coin, data in results.items()
    )

    equity = st.session_state.cash + position_value
    total_sek = equity * EUR_SEK
    profit = total_sek - START_SEK

    st.session_state.portfolio_history.append({
        "Time": datetime.now(),
        "Value": total_sek
    })

    # Keep history manageable
    st.session_state.portfolio_history = (
        st.session_state.portfolio_history[-500:]
    )

# HEADER
st.title("🤖 MY AI TRADER")

if page == "Dashboard":

    st.caption("MARKET INTELLIGENCE · LIVE PAPER TRADING")
    st.divider()

    if errors:
        st.warning("Market data issue: " + "; ".join(errors))

    if results:
        # TOP METRICS
        st.subheader("Portfolio Overview")

        a, b, c = st.columns(3)

        a.metric(
            "Portfolio Value",
            f"{total_sek:,.2f} SEK"
        )

        b.metric(
            "Available Cash",
            f"{st.session_state.cash * EUR_SEK:,.2f} SEK"
        )

        c.metric(
            "Total Profit / Loss",
            f"{profit:+,.2f} SEK"
        )

        st.divider()

        # MARKET WATCH
        st.subheader("📊 Market Watch")

        for coin, data in results.items():
            st.markdown(f"### {coin}")

            a, b, c = st.columns(3)

            a.metric(
                "Price",
                f"{data['price']:,.2f} EUR"
            )

            b.metric(
                "24h Approx. Change",
                f"{data['change']:+.2f}%"
            )

            c.metric(
                "Trading Signal",
                data["signal"]
            )

        st.divider()

        # CHARTS
        st.subheader("📈 Market Charts")

        selected_coin = st.selectbox(
            "Select market",
            list(results.keys())
        )

        chart_data = results[selected_coin]["history"].copy()
        chart_data["time"] = pd.to_datetime(
            chart_data["time"], unit="ms"
        )
        chart_data = chart_data.set_index("time")

        st.line_chart(
            chart_data[["close", "EMA20", "EMA50"]],
            height=350
        )

        st.caption(
            "Close = market price · EMA20 and EMA50 = moving averages"
        )

    else:
        st.error("Could not retrieve market data. Please try again.")

elif page == "Portfolio":

    st.caption("YOUR VIRTUAL ACCOUNT")
    st.divider()

    if results:
        st.metric(
            "Total Portfolio Value",
            f"{total_sek:,.2f} SEK"
        )

        st.metric(
            "Profit / Loss",
            f"{profit:+,.2f} SEK"
        )

        st.subheader("Open Positions")

        rows = []

        for coin, position in st.session_state.positions.items():
            price = results.get(coin, {}).get("price", 0)

            rows.append({
                "Asset": coin,
                "Quantity": round(position["qty"], 8),
                "Current Value (EUR)": round(
                    position["qty"] * price, 2
                )
            })

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Portfolio Development")

        if st.session_state.portfolio_history:
            history = pd.DataFrame(
                st.session_state.portfolio_history
            ).set_index("Time")

            st.line_chart(history, height=300)

    st.divider()
    st.subheader("Trade History")

    if st.session_state.trades:
        st.dataframe(
            pd.DataFrame(st.session_state.trades),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No trades have been made yet.")

elif page == "Settings":

    st.caption("BOT CONFIGURATION")
    st.divider()

    st.subheader("Trading Settings")

    st.write("**Trading mode:** Paper Trading")
    st.write("**Exchange:** Kraken")
    st.write("**Markets:** BTC/EUR and ETH/EUR")
    st.write("**Timeframe:** 1 hour")
    st.write("**Strategy:** EMA20 + EMA50 + RSI")
    st.write("**Position size:** 20% of available cash")
    st.write("**Simulated trading fee:** 0.4%")

    st.divider()

    st.subheader("About the Strategy")

    st.write(
        "The bot analyzes moving averages and RSI "
        "to generate BUY, SELL and HOLD signals."
    )

    st.warning(
        "This is a rule-based paper trading system. "
        "It does not use real money or place real orders."
    )

    st.divider()

    st.subheader("Account Information")
    st.write(f"Starting balance: {START_SEK} SEK")
    st.write("Currency conversion: 1 EUR = 11.5 SEK")

# FOOTER
st.divider()

st.caption(
    "MY AI TRADER  |  PAPER TRADING ONLY  |  "
    "Market data provided by Kraken"
)
