# app.py
import os
print("CWD:", os.getcwd())
print("Files:", os.listdir("."))

import streamlit as st
from data_pipeline import (
    get_stock_data,
    get_financials,
    compute_ratios,
    compute_growth,
    screen_stocks
)
from transcript_analysis import scrape_transcript, analyze_sentiment
import pandas as pd

st.set_page_config(page_title="Automated Financial Data Pipeline", layout="wide")
st.title("Automated Financial Data Pipeline")

ticker = st.text_input("Enter Stock Ticker (e.g., TCS.NS, INFY.NS, AAPL)", "AAPL")
fallback_url = st.text_input("(Optional) Moneycontrol Ratios URL for the above ticker",
                             "https://www.moneycontrol.com/financials/tcs-ratiosVI/TCS")

if st.button("Fetch Data"):
    hist = get_stock_data(ticker)
    if hist is not None and not hist.empty:
        st.subheader("Stock Price (Last 1 Year)")
        st.line_chart(hist["Close"])
    else:
        st.warning("No stock price data found for this ticker.")

    st.subheader("Financial Ratios")
    ratios = compute_ratios(ticker, fallback_url)
    st.json(ratios)

    st.subheader("Growth Metrics")
    growth = compute_growth(ticker)
    st.json(growth)

    with st.expander("Show Raw Financial Statements (from yfinance)"):
        try:
            bs, inc = get_financials(ticker)
            st.write("Balance Sheet:", bs if bs is not None else "No data")
            st.write("Income Statement:", inc if inc is not None else "No data")
        except Exception as e:
            st.write("Could not fetch raw financials:", e)

    url = st.text_input("Enter Earnings Transcript URL to analyze (optional)")
    if url:
        text = scrape_transcript(url)
        if text:
            sentiment = analyze_sentiment(text)
            st.subheader("Earnings Transcript Sentiment")
            st.write(sentiment)
        else:
            st.warning("Transcript text could not be extracted.")

st.markdown("---")
st.subheader("Stock Screening Tool")

tickers_input = st.text_area("Enter tickers (comma-separated)", "AAPL,MSFT,GOOG,INFY.NS,TCS.NS")
# small UI to let user change thresholds quickly
col1, col2 = st.columns(2)
with col1:
    roe_thresh = st.number_input("ROE threshold (%)", min_value=0.0, max_value=100.0, value=15.0, step=0.5)
with col2:
    de_thresh = st.number_input("Debt/Equity threshold", min_value=0.0, max_value=10.0, value=1.0, step=0.1)

# convert ROE% to decimal
criteria = {"ROE": roe_thresh / 100.0, "Debt/Equity": de_thresh}

# Optional: allow entering fallback URLs for specific tickers (format: TICKER|URL per line)
fallback_text = st.text_area("Optional fallback mapping (one per line, format: TICKER|URL)", "")

def parse_fallback_map(text):
    mapping = {}
    for line in text.splitlines():
        if "|" in line:
            t, u = line.split("|", 1)
            mapping[t.strip()] = u.strip()
    return mapping

fallback_map = parse_fallback_map(fallback_text)

if st.button("Run Screening"):
    tickers = [t.strip() for t in tickers_input.split(",") if t.strip()]
    if not tickers:
        st.warning("Please enter at least one ticker.")
    else:
        df = screen_stocks(tickers, criteria=criteria, fallback_url_map=fallback_map)
        if df.empty:
            st.warning("No data returned for the tickers.")
        else:
            # show PASS rows first
            if "Status" in df.columns:
                df_pass = df[df["Status"] == "PASS"]
                df_fail = df[df["Status"] != "PASS"]
                st.write(f"Matched: {len(df_pass)}  |  Failed: {len(df_fail)}")
                if not df_pass.empty:
                    st.subheader("✅ Passed Stocks")
                    st.dataframe(df_pass.reset_index(drop=True))
                if not df_fail.empty:
                    st.subheader("❌ Failed Stocks (with reasons)")
                    st.dataframe(df_fail.reset_index(drop=True))
            else:
                st.dataframe(df)
