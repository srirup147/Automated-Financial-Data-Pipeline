import yfinance as yf
import pandas as pd
from yahooquery import Ticker
import requests
from bs4 import BeautifulSoup

# ------------------
# Primary: Yahooquery
# ------------------
def get_ratios_yq(ticker):
    try:
        t = Ticker(ticker)
        key_stats = t.key_metrics.get(ticker, {})
        if key_stats:
            ratios = {
                "ROE": key_stats.get("returnOnEquity", None),
                "ROCE": key_stats.get("returnOnCapitalEmployed", None),
                "Debt/Equity": key_stats.get("totalDebt/Equity", None)
            }
            ratios = {k: round(v,3) for k,v in ratios.items() if v is not None}
            if ratios:
                return ratios
    except Exception as e:
        print("Yahooquery error:", e)
    return None

# ------------------
# Fallback: Moneycontrol Scraping
# ------------------
def get_moneycontrol_ratios(stock_url):
    try:
        response = requests.get(stock_url, headers={'User-Agent': 'Mozilla/5.0'})
        tables = pd.read_html(response.text)
        key_ratios = tables[0]
        return key_ratios.to_dict(orient="records")[:5]
    except Exception as e:
        print("Moneycontrol scrape error:", e)
    return None

# ------------------
# Unified Interface
# ------------------
def compute_ratios(ticker, fallback_url=None):
    ratios = get_ratios_yq(ticker)
    if ratios:
        return ratios
    elif fallback_url:
        return {"Moneycontrol_Ratios": get_moneycontrol_ratios(fallback_url)}
    else:
        return {"Info": "Ratios not available for this ticker"}

# ------------------
# Stock Data
# ------------------
def get_stock_data(ticker, period="1y"):
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    return hist

def get_financials(ticker):
    stock = yf.Ticker(ticker)
    balance_sheet = stock.balance_sheet
    income_stmt = stock.financials
    return balance_sheet, income_stmt
