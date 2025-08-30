import streamlit as st
import pandas as pd
import plotly.graph_objs as go
import plotly.express as px
from data_pipeline import fetch_stock_data, get_financials, compute_ratios, compute_growth, screen_stocks
from transcript_analysis import scrape_transcript, analyze_sentiment

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Financial Analysis Dashboard", layout="wide")
st.title("📊 Automated Financial Data Pipeline")

# ---------- USER INPUT ----------
col1, col2 = st.columns([2, 3])
with col1:
    ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, INFY.NS)", "AAPL")
    fallback_url = st.text_input("Optional: Moneycontrol Ratios URL", "")

# ---------- STOCK PRICE ----------
df = fetch_stock_data(ticker, period="5y", interval="1d")
if not df.empty:
    st.subheader(f"📈 {ticker} - 5 Year Candlestick Chart")
    fig = go.Figure(data=[go.Candlestick(
        x=df['Date'],
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close']
    )])
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        title=f"{ticker} Stock Price (5Y)"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No stock price data available.")

# ---------- RATIOS ----------
st.subheader("📌 Key Financial Ratios")
ratios = compute_ratios(ticker, fallback_url)
if ratios and isinstance(ratios, dict):
    col1, col2, col3 = st.columns(3)
    for i, (metric, value) in enumerate(ratios.items()):
        if i % 3 == 0:
            col1.metric(metric, value)
        elif i % 3 == 1:
            col2.metric(metric, value)
        else:
            col3.metric(metric, value)
else:
    st.warning("No ratios available.")

# ---------- GROWTH ----------
st.subheader("📈 Growth Metrics")
growth = compute_growth(ticker)
if growth:
    growth_df = pd.DataFrame(list(growth.items()), columns=["Metric", "Value"])
    st.dataframe(growth_df.set_index("Metric"))
else:
    st.warning("No growth data available.")

# ---------- FINANCIAL STATEMENTS ----------
with st.expander("📑 Show Raw Financial Statements"):
    try:
        bs, inc = get_financials(ticker)
        st.write("Balance Sheet", bs if bs is not None else "No data")
        st.write("Income Statement", inc if inc is not None else "No data")
    except Exception as e:
        st.error(f"Could not fetch financials: {e}")

# ---------- EARNINGS TRANSCRIPT ----------
with st.expander("🎤 Earnings Transcript Analysis"):
    url = st.text_input("Enter Transcript URL")
    if url:
        text = scrape_transcript(url)
        if text:
            sentiment = analyze_sentiment(text)
            overall = "Positive" if sentiment["compound"] > 0.05 else "Negative" if sentiment["compound"] < -0.05 else "Neutral"
            
            st.metric("Overall Sentiment", overall, f"{sentiment['compound']:.2f}")

            # Sentiment breakdown chart
            sent_df = pd.DataFrame({
                "Sentiment": ["Negative", "Neutral", "Positive"],
                "Score": [sentiment["neg"], sentiment["neu"], sentiment["pos"]]
            })
            fig = px.bar(
                sent_df, x="Sentiment", y="Score", color="Sentiment", text="Score",
                color_discrete_map={"Negative": "red", "Neutral": "steelblue", "Positive": "green"},
                width=500, height=300
            )
            fig.update_traces(marker_line_width=1.2, marker_line_color="black",
                              width=0.3, texttemplate='%{text:.2f}', textposition="outside")
            fig.update_layout(template="plotly_white", yaxis=dict(range=[0, 1], title="Proportion"), xaxis=dict(title=""), showlegend=False)
            st.plotly_chart(fig, use_container_width=False)
        else:
            st.warning("Transcript could not be extracted.")

# ---------- SCREENING TOOL ----------
st.markdown("---")
st.subheader("📌 Stock Screening Tool")

tickers_input = st.text_area("Enter tickers (comma-separated)", "AAPL,MSFT,GOOG,INFY.NS,TCS.NS")
roe_thresh = st.number_input("ROE threshold (%)", min_value=0.0, max_value=100.0, value=15.0, step=0.5)
de_thresh = st.number_input("Debt/Equity threshold", min_value=0.0, max_value=10.0, value=1.0, step=0.1)
criteria = {"ROE": roe_thresh / 100.0, "Debt/Equity": de_thresh}

if st.button("Run Screening"):
    tickers = [t.strip() for t in tickers_input.split(",") if t.strip()]
    df_screen = screen_stocks(tickers, criteria=criteria)
    if not df_screen.empty:
        st.dataframe(df_screen.reset_index(drop=True), use_container_width=True)
    else:
        st.warning("No stocks matched criteria.")
