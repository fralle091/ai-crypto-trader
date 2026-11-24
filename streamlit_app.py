
import streamlit as st
import ccxt
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(

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
    max-width: 1250px;
    padding-top: 2rem;
}

h1, h2, h3 {
    color: #F8FAFC !important;
    font-weight: 700 !important;
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #142236, #101927);
    border: 1px solid #26364B;
    padding: 20px;
    border-radius: 14px;
}

[data-testid="stMetricLabel"] {
    color: #94A3B8 !important;
}

[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #26364B;
    border-radius: 12px;
}

hr {
    border-color: #26364B;
}

.stCaption {
    color: #94A3B8;
}

</style>
""", unsafe_allow_html=True)

)

START_SEK = 1000
EUR_SEK = 11.5
FEE = 0.004

st.title("🤖 MY AI TRADER")
st.caption("Automated Crypto Paper Trading")

st_autorefresh(interval=60000, key="refresh")

exchange = ccxt.kraken({
    "enableRateLimit": True
})

# Create virtual account
if "cash" not in st.session_state:
    st.session_state.cash = START_SEK / EUR_SEK
    st.session_state.positions = {
        "BTC": {"qty": 0.0, "cost": 0.0},
        "ETH": {"qty": 0.0, "cost": 0.0}
    }
    st.session_state.trades = []
    st.session_state.processed = {}

# Market analysis
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

    if last["EMA20"] > last["EMA50"] and 50 < last["RSI"] < 68:
        signal = "BUY"
    elif last["EMA20"] < last["EMA50"] or last["RSI"] > 75:
        signal = "SELL"
    else:
        signal = "HOLD"

    return {
        "price": float(last["close"]),
        "rsi": float(last["RSI"]),
        "signal": signal,
        "candle": int(last["time"])
    }

# Automatic simulated trading
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

# Load market data
results = {}
errors = []

for coin in ["BTC", "ETH"]:
    try:
        data = analyze(coin + "/EUR")
        results[coin] = data
        paper_trade(coin, data)
    except Exception as error:
        errors.append(f"{coin}: {error}")

if errors:
    st.warning("Market data error: " + "; ".join(errors))

if results:
    position_value = sum(
        st.session_state.positions[coin]["qty"] * data["price"]
        for coin, data in results.items()
    )

    equity = st.session_state.cash + position_value
    total_sek = equity * EUR_SEK

    st.divider()
    st.subheader("Portfolio")

    a, b, c = st.columns(3)

    a.metric("Portfolio value", f"{total_sek:.2f} SEK")
    b.metric("Available cash", f"{st.session_state.cash * EUR_SEK:.2f} SEK")
    c.metric("Profit / Loss", f"{total_sek - START_SEK:+.2f} SEK")

    st.divider()
    st.subheader("Market analysis")

    for coin, data in results.items():
        st.markdown(f"### {coin}")

        a, b, c = st.columns(3)
        a.metric("Price", f"{data['price']:.2f} EUR")
        b.metric("RSI", f"{data['rsi']:.2f}")
        c.metric("Signal", data["signal"])

    st.divider()
    st.subheader("Positions")

    for coin, position in st.session_state.positions.items():
        st.write(
            f"**{coin}:** {position['qty']:.8f} coins"
        )

    st.divider()
    st.subheader("Trade history")

    if st.session_state.trades:
        st.dataframe(
            pd.DataFrame(st.session_state.trades),
            use_container_width=True
        )
    else:
        st.info("No trades yet. Bot is analyzing the market.")

else:
    st.error("Could not retrieve market data.")

st.caption("Simulation only • No real money or orders involved")
