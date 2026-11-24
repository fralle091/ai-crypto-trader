
import os
from datetime import datetime

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
    --bg: #080C14;
    --panel: #101827;
    --panel2: #141F30;
    --border: #233149;
    --text: #EDF3FC;
    --muted: #8B9BB2;
    --green: #25D6A2;
    --red: #FF6178;
    --blue: #6C9BFF;
    --purple: #A78BFA;
}

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background:
        radial-gradient(ellipse at 75% 0%, #15233a 0%, transparent 35%),
        var(--bg);
    color: var(--text);
}

header[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    max-width: 1500px;
    padding-top: 2rem;
    padding-bottom: 4rem;
}

h1, h2, h3 {
    font-family: 'Space Grotesk', sans-serif !important;
    color: var(--text) !important;
    letter-spacing: -0.5px;
}

p, label, span {
    color: inherit;
}

[data-testid="stSidebar"] {
    background: #0B1220;
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] h1 {
    font-family: 'Space Grotesk', sans-serif !important;
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #16243A, #101827);
    border: 1px solid var(--border);
    padding: 20px;
    border-radius: 16px;
}

[data-testid="stMetricLabel"] {
    color: var(--muted) !important;
    font-size: 0.8rem;
}

[data-testid="stMetricValue"] {
    color: var(--text) !important;
    font-family: 'Space Grotesk', sans-serif;
}

[data-testid="stMetricDelta"] {
    font-size: 0.8rem;
}

.stButton > button {
    border-radius: 10px;
    border: 1px solid #344967;
    background: #17243A;
    color: white;
    font-weight: 600;
    transition: 0.2s;
}

.stButton > button:hover {
    border-color: #6C9BFF;
    background: #203453;
    color: white;
}

div[data-baseweb="select"] > div,
.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
    background: #111D2E;
    border-color: #34445D;
    color: white;
    border-radius: 10px;
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: 12px;
}

hr {
    border-color: var(--border);
}

.nexus-brand {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 25px;
    font-weight: 700;
    letter-spacing: 2px;
    color: white;
}

.nexus-sub {
    color: #8193AC;
    font-size: 10px;
    letter-spacing: 2px;
}

.section-label {
    color: #8193AC;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    margin-bottom: 8px;
}

.panel {
    background: linear-gradient(145deg, #142137, #101827);
    border: 1px solid #263750;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 12px;
}

.status-dot {
    color: #25D6A2;
    font-weight: 700;
}

.small-muted {
    color: #8B9BB2;
    font-size: 12px;
}

div[data-testid="stChatMessage"] {
    background: #111D2E;
    border: 1px solid #263750;
    border-radius: 14px;
    padding: 12px;
}

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
    "currency_rate": 11.5
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.markdown(
    '<div class="nexus-brand">◈ NEXUS</div>'
    '<div class="nexus-sub">AI TRADING TERMINAL</div>',
    unsafe_allow_html=True
)

st.sidebar.divider()

pages = [
    "Overview",
    "Markets",
    "Portfolio",
    "Strategy Lab",
    "Trade Journal",
    "AI Copilot",
    "Settings"
]

page = st.sidebar.radio(
    "WORKSPACE",
    pages,
    label_visibility="visible"
)

st.sidebar.divider()

st.sidebar.markdown("### ACCOUNT")

st.sidebar.metric(
    "Virtual starting balance",
    f"{st.session_state.starting_balance:,.0f} SEK"
)

st.sidebar.markdown(
    '<p class="small-muted">● PAPER TRADING ACTIVE</p>',
    unsafe_allow_html=True
)

st.sidebar.divider()

st.sidebar.markdown("### SYSTEM")

st.sidebar.caption("Exchange: Kraken")
st.sidebar.caption("Markets: BTC / ETH")
st.sidebar.caption("Mode: Simulation only")

# =====================================================
# MARKET DATA
# =====================================================

exchange = ccxt.kraken({
    "enableRateLimit": True,
    "timeout": 15000
})

def analyze(symbol, timeframe):
    candles = exchange.fetch_ohlcv(
        symbol,
        timeframe=timeframe,
        limit=150
    )

    df = pd.DataFrame(
        candles,
        columns=[
            "time", "open", "high",
            "low", "close", "volume"
        ]
    )

    # Use completed candles only
    df = df.iloc[:-1].copy()

    if len(df) < 55:
        raise ValueError("Not enough candle data")

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

    rsi = (
        float(last["RSI"])
        if pd.notna(last["RSI"])
        else 50.0
    )

    if last["EMA20"] > last["EMA50"] and 50 < rsi < 68:
        signal = "BUY"
    elif last["EMA20"] < last["EMA50"] or rsi > 75:
        signal = "SELL"
    else:
        signal = "HOLD"

    previous = df.iloc[-25]["close"]

    change = (
        (last["close"] / previous) - 1
    ) * 100

    return {
        "price": float(last["close"]),
        "rsi": rsi,
        "signal": signal,
        "change": float(change),
        "candle": int(last["time"]),
        "history": df
    }


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
    signal = data["signal"]
    price = data["price"]

    fee = st.session_state.fee / 100

    if signal == "BUY" and position["qty"] == 0:
        amount = (
            st.session_state.cash *
            st.session_state.risk / 100
        )

        if amount < 5:
            return

        quantity = amount * (1 - fee) / price

        st.session_state.cash -= amount
        position["qty"] = quantity
        position["cost"] = amount

        st.session_state.trades.append({
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Asset": coin,
            "Action": "BUY",
            "Price EUR": round(price, 2),
            "Amount EUR": round(amount, 2)
        })

    elif signal == "SELL" and position["qty"] > 0:
        proceeds = position["qty"] * price * (1 - fee)

        st.session_state.cash += proceeds

        st.session_state.trades.append({
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Asset": coin,
            "Action": "SELL",
            "Price EUR": round(price, 2),
            "Amount EUR": round(proceeds, 2)
        })

        position["qty"] = 0.0
        position["cost"] = 0.0


# =====================================================
# LOAD DATA
# =====================================================

st_autorefresh(
    interval=st.session_state.refresh * 1000,
    key="nexus_refresh"
)

results = {}
errors = []

for coin in ["BTC", "ETH"]:
    try:
        data = analyze(
            coin + "/EUR",
            st.session_state.timeframe
        )
        results[coin] = data
        execute_paper_trade(coin, data)
    except Exception as error:
        errors.append(f"{coin}: {error}")

# =====================================================
# CALCULATE PORTFOLIO
# =====================================================

portfolio_value = 0.0

if results:
    position_value = sum(
        st.session_state.positions[coin]["qty"] *
        data["price"]
        for coin, data in results.items()
    )

    equity = st.session_state.cash + position_value

    portfolio_value = (
        equity * st.session_state.currency_rate
    )

    profit = (
        portfolio_value -
        st.session_state.starting_balance
    )

    st.session_state.history.append({
        "Time": datetime.now(),
        "Value": portfolio_value
    })

    st.session_state.history = (
        st.session_state.history[-500:]
    )
else:
    profit = 0.0

# =====================================================
# REUSABLE CHART
# =====================================================

def create_market_chart(data):
    df = data["history"].tail(100).copy()

    df["Date"] = pd.to_datetime(
        df["time"], unit="ms"
    )

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["Date"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Market",
        increasing_line_color="#25D6A2",
        decreasing_line_color="#FF6178"
    ))

    fig.add_trace(go.Scatter(
        x=df["Date"],
        y=df["EMA20"],
        name="EMA 20",
        line=dict(color="#6C9BFF", width=1.5)
    ))

    fig.add_trace(go.Scatter(
        x=df["Date"],
        y=df["EMA50"],
        name="EMA 50",
        line=dict(color="#A78BFA", width=1.5)
    ))

    fig.update_layout(
        height=450,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.08),
        font=dict(color="#B8C7DC")
    )

    return fig


# =====================================================
# HEADER
# =====================================================

st.markdown(
    '<div class="section-label">NEXUS / TRADING WORKSPACE</div>',
    unsafe_allow_html=True
)

st.title(page)

st.caption(
    "Advanced market intelligence and portfolio analytics"
)

if errors:
    st.warning("Market data warning: " + "; ".join(errors))


# =====================================================
# OVERVIEW
# =====================================================

if page == "Overview":

    st.markdown("### Performance Overview")

    if results:

        a, b, c, d = st.columns(4)

        a.metric(
            "Portfolio Value",
            f"{portfolio_value:,.2f} SEK"
        )

        b.metric(
            "Total P/L",
            f"{profit:+,.2f} SEK"
        )

        c.metric(
            "Available Cash",
            f"{st.session_state.cash * 11.5:,.2f} SEK"
        )

        d.metric(
            "Open Positions",
            sum(
                1 for p in st.session_state.positions.values()
                if p["qty"] > 0
            )
        )

        st.divider()

        left, right = st.columns([1.6, 1])

        with left:
            st.markdown("### Portfolio Performance")

            if st.session_state.history:
                history = pd.DataFrame(
                    st.session_state.history
                ).set_index("Time")

                fig = go.Figure()

                fig.add_trace(go.Scatter(
                    x=history.index,
                    y=history["Value"],
                    mode="lines",
                    fill="tozeroy",
                    line=dict(
                        color="#25D6A2",
                        width=3
                    ),
                    name="Portfolio"
                ))

                fig.update_layout(
                    height=330,
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=5, r=5, t=20, b=5)
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

        with right:
            st.markdown("### Market Signals")

            for coin, data in results.items():

                st.markdown(
                    f'<div class="panel">'
                    f'<b>{coin}</b><br>'
                    f'<span class="small-muted">Price</span>'
                    f'<h3>{data["price"]:,.2f} EUR</h3>'
                    f'<span class="small-muted">Signal</span>'
                    f'<h3>{data["signal"]}</h3>'
                    f'<span class="small-muted">RSI: {data["rsi"]:.1f}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        st.divider()

        st.markdown("### Market Snapshot")

        market_rows = []

        for coin, data in results.items():
            market_rows.append({
                "Asset": coin,
                "Price EUR": round(data["price"], 2),
                "Change": f'{data["change"]:+.2f}%',
                "RSI": round(data["rsi"], 1),
                "Signal": data["signal"]
            })

        st.dataframe(
            pd.DataFrame(market_rows),
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("Waiting for market data.")


# =====================================================
# MARKETS
# =====================================================

elif page == "Markets":

    st.markdown("### Live Market Analysis")

    if results:

        selected = st.selectbox(
            "Choose market",
            list(results.keys())
        )

        data = results[selected]

        a, b, c = st.columns(3)

        a.metric(
            "Market Price",
            f'{data["price"]:,.2f} EUR'
        )

        b.metric(
            "Price Change",
            f'{data["change"]:+.2f}%'
        )

        c.metric(
            "RSI",
            f'{data["rsi"]:.2f}'
        )

        st.markdown("### Price Chart")

        st.plotly_chart(
            create_market_chart(data),
            use_container_width=True
        )

        st.markdown("### Technical Indicators")

        st.write(
            f'EMA20: {data["history"].iloc[-1]["EMA20"]:.2f} EUR'
        )

        st.write(
            f'EMA50: {data["history"].iloc[-1]["EMA50"]:.2f} EUR'
        )

        st.write(
            f'RSI: {data["rsi"]:.2f}'
        )

        st.info(
            f'Current strategy signal: {data["signal"]}'
        )

    else:
        st.error("No market data available.")


# =====================================================
# PORTFOLIO
# =====================================================

elif page == "Portfolio":

    st.markdown("### Account Analytics")

    if results:

        a, b, c = st.columns(3)

        a.metric(
            "Portfolio",
            f"{portfolio_value:,.2f} SEK"
        )

        b.metric(
            "Profit / Loss",
            f"{profit:+,.2f} SEK"
        )

        c.metric(
            "Cash",
            f"{st.session_state.cash * 11.5:,.2f} SEK"
        )

        st.divider()

        rows = []

        for coin, position in st.session_state.positions.items():

            price = results.get(
                coin, {}
            ).get("price", 0)

            value = position["qty"] * price

            rows.append({
                "Asset": coin,
                "Quantity": round(position["qty"], 8),
                "Average Cost EUR": round(position["cost"], 2),
                "Market Value EUR": round(value, 2)
            })

        st.markdown("### Holdings")

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("### Allocation")

        labels = ["Cash"]
        values = [st.session_state.cash]

        for coin, position in st.session_state.positions.items():
            labels.append(coin)
            values.append(position["qty"] * results[coin]["price"])

        fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=0.65
        ))

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            height=350
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    else:
        st.info("Waiting for market prices.")


# =====================================================
# STRATEGY LAB
# =====================================================

elif page == "Strategy Lab":

    st.markdown("### Strategy Research")

    st.write(
        "Explore the indicators used by the current strategy."
    )

    st.markdown("### Strategy Rules")

    st.markdown("""
    **BUY**
    - EMA20 is above EMA50
    - RSI is between 50 and 68

    **SELL**
    - EMA20 is below EMA50
    - Or RSI is above 75

    **HOLD**
    - Neither condition is met
    """)

    st.divider()

    if results:

        selected = st.selectbox(
            "Choose asset for analysis",
            list(results.keys())
        )

        data = results[selected]

        df = data["history"]

        a, b, c = st.columns(3)

        a.metric(
            "Current RSI",
            f'{data["rsi"]:.2f}'
        )

        b.metric(
            "EMA20",
            f'{df.iloc[-1]["EMA20"]:.2f}'
        )

        c.metric(
            "EMA50",
            f'{df.iloc[-1]["EMA50"]:.2f}'
        )

        st.markdown("### Recent Indicator Values")

        display = df.tail(20)[
            ["close", "EMA20", "EMA50", "RSI"]
        ].copy()

        st.dataframe(
            display,
            use_container_width=True
        )

        st.warning(
            "Signals are rule-based and are not guaranteed "
            "to predict future prices."
        )


# =====================================================
# TRADE JOURNAL
# =====================================================

elif page == "Trade Journal":

    st.markdown("### Trading Activity")

    trades = st.session_state.trades

    a, b, c = st.columns(3)

    a.metric("Total Trades", len(trades))

    b.metric(
        "Buy Orders",
        sum(t["Action"] == "BUY" for t in trades)
    )

    c.metric(
        "Sell Orders",
        sum(t["Action"] == "SELL" for t in trades)
    )

    st.divider()

    if trades:

        st.dataframe(
            pd.DataFrame(trades),
            use_container_width=True,
            hide_index=True
        )

        csv = pd.DataFrame(trades).to_csv(index=False)

        st.download_button(
            "Download Trade History CSV",
            csv,
            file_name="nexus_trade_history.csv",
            mime="text/csv"
        )

    else:
        st.info("No simulated trades yet.")

    st.caption(
        "Trade history is currently stored in the active app session."
    )


# =====================================================
# AI COPILOT
# =====================================================

elif page == "AI Copilot":

    st.markdown("### ◈ NEXUS AI Copilot")

    st.write(
        "Ask questions about your portfolio, trading indicators "
        "and the market."
    )

    st.info(
        "The AI assistant uses live dashboard information when available. "
        "It is an educational assistant, not financial advice."
    )

    # API KEY: set OPENAI_API_KEY in Streamlit secrets
    api_key = os.getenv("OPENAI_API_KEY", "")

    try:
        api_key = st.secrets.get("OPENAI_API_KEY", api_key)
    except Exception:
        pass

    for message in st.session_state.chat:

        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input(
        "Ask NEXUS anything..."
    )

    if prompt:

        st.session_state.chat.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        market_context = ""

        if results:
            market_context = "\n".join([
                (
                    f'{coin}: price {data["price"]:.2f} EUR, '
                    f'RSI {data["rsi"]:.1f}, '
                    f'signal {data["signal"]}'
                )
                for coin, data in results.items()
            ])

        context = f"""
        You are NEXUS AI, an educational crypto market assistant.

        Current market information:
        {market_context}

        Portfolio value: {portfolio_value:.2f} SEK
        Cash: {st.session_state.cash:.2f} EUR
        Profit/loss: {profit:.2f} SEK

        Explain concepts clearly.
        Do not promise profits.
        Do not invent market data.
        Do not tell the user that a signal guarantees a price movement.
        This is a paper trading simulation.
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
                            {
                                "role": "system",
                                "content": context
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        temperature=0.4
                    )

                    answer = response.choices[0].message.content

                except Exception as error:
                    answer = (
                        "I could not connect to the AI service. "
                        f"Technical error: {error}"
                    )

            else:

                lower = prompt.lower()

                if "rsi" in lower:
                    answer = (
                        "RSI measures momentum. Values above 70 are "
                        "often considered overbought, while values below "
                        "30 are often considered oversold. These are "
                        "guidelines, not guaranteed reversal signals."
                    )

                elif "ema" in lower:
                    answer = (
                        "EMA is an exponential moving average. EMA20 "
                        "reacts faster to price changes than EMA50. "
                        "Traders sometimes compare them to study trends."
                    )

                elif "portfolio" in lower or "balance" in lower:
                    answer = (
                        f"Your current simulated portfolio is worth "
                        f"{portfolio_value:.2f} SEK. Your simulated "
                        f"profit/loss is {profit:+.2f} SEK."
                    )

                elif "signal" in lower or "buy" in lower:
                    answer = (
                        "The current system uses EMA20, EMA50 and RSI. "
                        "BUY requires EMA20 above EMA50 and RSI between "
                        "50 and 68. SELL is triggered when EMA20 is "
                        "below EMA50 or RSI exceeds 75."
                    )

                else:
                    answer = (
                        "I am currently in basic assistant mode. "
                        "I can explain RSI, EMA, signals and your "
                        "simulated portfolio. Add an OpenAI API key "
                        "in Streamlit Secrets to activate full AI chat."
                    )

            st.markdown(answer)

        st.session_state.chat.append({
            "role": "assistant",
            "content": answer
        })


# =====================================================
# SETTINGS
# =====================================================

elif page == "Settings":

    st.markdown("### System Configuration")

    st.markdown("#### Trading Settings")

    st.session_state.risk = st.slider(
        "Position size (% of available cash)",
        min_value=5,
        max_value=50,
        value=st.session_state.risk,
        step=5
    )

    st.session_state.fee = st.slider(
        "Simulated trading fee (%)",
        min_value=0.0,
        max_value=1.0,
        value=float(st.session_state.fee),
        step=0.05
    )

    st.session_state.timeframe = st.selectbox(
        "Market timeframe",
        ["15m", "1h", "4h", "1d"],
        index=["15m", "1h", "4h", "1d"].index(
            st.session_state.timeframe
        )
    )

    st.session_state.refresh = st.select_slider(
        "Dashboard refresh interval",
        options=[30, 60, 120, 300],
        value=st.session_state.refresh
    )

    st.divider()

    st.markdown("#### Automation")

    st.session_state.auto_trade = st.toggle(
        "Enable automatic paper trading",
        value=st.session_state.auto_trade
    )

    st.caption(
        "When enabled, the strategy can simulate trades "
        "on completed candles. It never places real orders."
    )

    st.divider()

    st.markdown("#### Account")

    st.write(
        f'Starting balance: {st.session_state.starting_balance:.2f} SEK'
    )

    st.write(
        "Currency conversion: 1 EUR = 11.5 SEK (fixed estimate)"
    )

    st.divider()

    st.markdown("#### AI Configuration")

    st.write(
        "To activate full AI chat, configure OPENAI_API_KEY "
        "in Streamlit Cloud → App settings → Secrets."
    )

    st.code(
        'OPENAI_API_KEY = "your-api-key"',
        language="toml"
    )

    st.warning(
        "Never publish your API key in GitHub or in your Python code."
    )

    st.divider()

    st.markdown("#### Reset Virtual Account")

    if st.button(
        "Reset account and trading history",
        type="secondary"
    ):

        st.session_state.cash = (
            st.session_state.starting_balance / 11.5
        )

        st.session_state.positions = {
            "BTC": {"qty": 0.0, "cost": 0.0},
            "ETH": {"qty": 0.0, "cost": 0.0}
        }

        st.session_state.trades = []
        st.session_state.processed = {}
        st.session_state.history = []

        st.success("Virtual account reset.")


# =====================================================
# FOOTER
# =====================================================

st.divider()

st.markdown(
    '<div style="text-align:center;color:#71839B;'
    'font-size:11px;letter-spacing:2px;">'
    '◈ NEXUS TRADING TERMINAL · PAPER TRADING ONLY'
    '</div>',
    unsafe_allow_html=True
)
