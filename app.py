import os
import streamlit as st
import pandas as pd
import plotly.graph_objs as go

from data_pipeline import (
    fetch_stock_data as get_stock_data,
    get_financials,
    compute_ratios,
    compute_growth,
    screen_stocks
)
from transcript_analysis import scrape_transcript, analyze_sentiment

# ------------------ Streamlit Page Config ------------------
st.set_page_config(page_title="Automated Financial Data Pipeline", layout="wide")
st.title("Automated Financial Data Pipeline")

# ------------------ Inputs ------------------
ticker = st.text_input("Enter Stock Ticker (e.g., TCS.NS, INFY.NS)", "AAPL")
fallback_url = st.text_input(
    "(Optional) Moneycontrol Ratios URL for the above ticker",
    "https://www.moneycontrol.com/financials/tcs-ratiosVI/TCS"
)


# ------------------ Stock Price Section ------------------
st.subheader("Stock Price History")

period_choice = st.selectbox("Select Time Period", ["1y","3y", "5y", "max"], index=1)
df = get_stock_data(ticker, period=period_choice, interval="1d")

if not df.empty:
    fig = go.Figure(data=[go.Candlestick(
        x=df['Date'],
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Candlestick'
    )])
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        title=f"{ticker} Stock Price ({period_choice.upper()})"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No stock price data available.")
    
# ------------------ Financial Ratios ------------------
st.subheader("Financial Ratios")

try:
    ratios = compute_ratios(ticker, fallback_url)
    if ratios:
        st.table(pd.DataFrame(ratios.items(), columns=["Metric", "Value"]))
    else:
        st.warning("No ratios available.")
except Exception as e:
    st.error(f"Error fetching ratios: {e}")


# ------------------ Growth Metrics ------------------
st.subheader("Growth Metrics")
try:
    growth = compute_growth(ticker)
    if growth:
        st.table(pd.DataFrame(growth.items(), columns=["Metric", "Value"]))
    else:
        st.warning("No growth metrics available.")
except Exception as e:
    st.error(f"Error fetching growth metrics: {e}")

# ------------------ Raw Financial Statements ------------------
with st.expander("Show Raw Financial Statements (from yfinance)"):
    try:
        bs, inc = get_financials(ticker)
        st.write("**Balance Sheet**")
        st.dataframe(bs if bs is not None else "No data")
        st.write("**Income Statement**")
        st.dataframe(inc if inc is not None else "No data")
    except Exception as e:
        st.write("Could not fetch raw financials:", e)

# ------------------ Transcript Analysis ------------------
st.subheader("Earnings Transcript Analysis")
url = st.text_input("Enter Earnings Transcript URL to analyze (optional)")
if url:
    text = scrape_transcript(url)
    if text:
        sentiment = analyze_sentiment(text)
        st.write("**Transcript Sentiment**")
        st.json(sentiment)
    else:
        st.warning("Transcript text could not be extracted.")

# ------------------ Stock Screening Tool ------------------
st.markdown("---")
st.subheader("Stock Screening Tool")

tickers_input = st.text_area("Enter tickers (comma-separated)", "AAPL,MSFT,GOOG,INFY.NS,TCS.NS")
col1, col2 = st.columns(2)
with col1:
    roe_thresh = st.number_input("ROE threshold (%)", min_value=0.0, max_value=100.0, value=15.0, step=0.5)
with col2:
    de_thresh = st.number_input("Debt/Equity threshold", min_value=0.0, max_value=10.0, value=1.0, step=0.1)

criteria = {"ROE": roe_thresh / 100.0, "Debt/Equity": de_thresh}

if st.button("Run Screening"):
    tickers = [t.strip() for t in tickers_input.split(",") if t.strip()]
    if not tickers:
        st.warning("Please enter at least one ticker.")
    else:
        df_screen = screen_stocks(tickers, criteria=criteria)
        if df_screen.empty:
            st.warning("No data returned for the tickers.")
        else:
            if "Status" in df_screen.columns:
                df_pass = df_screen[df_screen["Status"] == "PASS"]
                df_fail = df_screen[df_screen["Status"] != "PASS"]

                st.write(f"Matched: {len(df_pass)}  |  Failed: {len(df_fail)}")

                if not df_pass.empty:
                    st.subheader("Passed Stocks")
                    st.dataframe(df_pass.reset_index(drop=True))
                if not df_fail.empty:
                    st.subheader("Failed Stocks (with reasons)")
                    st.dataframe(df_fail.reset_index(drop=True))
            else:
                st.dataframe(df_screen)

