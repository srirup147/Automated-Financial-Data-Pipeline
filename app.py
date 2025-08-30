import streamlit as st
import matplotlib.pyplot as plt
from data_pipeline import get_stock_data, get_financials, compute_ratios
from transcript_analysis import scrape_transcript, analyze_sentiment

st.title("📊 Automated Financial Data Pipeline")
ticker = st.text_input("Enter Stock Ticker (e.g., TCS.NS, INFY.NS)", "TCS.NS")

if st.button("Fetch Data"):
    hist = get_stock_data(ticker)
    st.line_chart(hist["Close"])

    balance_sheet, income_stmt = get_financials(ticker)
    ratios = compute_ratios(income_stmt, balance_sheet)
    st.write("**Financial Ratios**", ratios)

    url = st.text_input("Enter Earnings Transcript URL")
    if url:
        text = scrape_transcript(url)
        sentiment = analyze_sentiment(text)
        st.write("**Sentiment Analysis**:", sentiment)
