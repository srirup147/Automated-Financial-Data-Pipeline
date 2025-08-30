import streamlit as st
from data_pipeline import get_stock_data, get_financials, compute_ratios
from transcript_analysis import scrape_transcript, analyze_sentiment

st.set_page_config(page_title="Automated Financial Data Pipeline", layout="wide")
st.title("📊 Automated Financial Data Pipeline")

ticker = st.text_input("Enter Stock Ticker (e.g., TCS.NS, INFY.NS, AAPL)", "AAPL")
fallback_url = st.text_input("(Optional) Enter Moneycontrol Ratios URL for Indian stocks",
                             "https://www.moneycontrol.com/financials/tcs-ratiosVI/TCS")

if st.button("Fetch Data"):
    # Stock Prices
    hist = get_stock_data(ticker)
    if not hist.empty:
        st.subheader("Stock Price (Last 1 Year)")
        st.line_chart(hist["Close"])
    else:
        st.warning("No stock price data found.")

    # Financial Ratios
    st.subheader("Financial Ratios")
    ratios = compute_ratios(ticker, fallback_url)
    st.json(ratios)

    # Financial Statements (Optional)
    with st.expander("Show Raw Financial Statements"):
        balance_sheet, income_stmt = get_financials(ticker)
        st.write("**Balance Sheet**", balance_sheet)
        st.write("**Income Statement**", income_stmt)

    # Transcript Analysis
    url = st.text_input("Enter Earnings Transcript URL (e.g., Moneycontrol result page)")
    if url:
        text = scrape_transcript(url)
        if text:
            sentiment = analyze_sentiment(text)
            st.subheader("Earnings Transcript Sentiment")
            st.write(sentiment)
        else:
            st.warning("Transcript text could not be extracted.")

