# 📊 Automated Financial Data Pipeline

This project is a deployment-ready tool for **automated financial analysis**.

### Features
- Fetch stock price data and financial statements (via yfinance)
- Compute key ratios: ROE, ROCE, Debt/Equity
- Scrape earnings transcripts from web pages
- Run NLP sentiment analysis on management commentary
- Interactive dashboard built with **Streamlit**
- Deployable on **Streamlit Cloud**

### Run Locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

### Deployment
- Push this repo to GitHub
- Deploy on [Streamlit Cloud](https://streamlit.io/cloud)
- Select `app.py` as the entry file
