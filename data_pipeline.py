import yfinance as yf
import pandas as pd
from yahooquery import Ticker
import requests
from bs4 import BeautifulSoup

# ------------------
# Primary: Yahooquery Ratios
# ------------------
def get_ratios_yq(ticker):
    try:
        t = Ticker(ticker)
        key_stats = t.key_metrics.get(ticker, {})
        if key_stats:
            ratios = {
                "ROE": key_stats.get("returnOnEquity", None),
                "ROCE": key_stats.get("returnOnCapitalEmployed", None),
                "Debt/Equity": key_stats.get("totalDebt/Equity", None),
                "P/E": key_stats.get("peRatio", None),
                "P/B": key_stats.get("pbRatio", None),
                "EV/EBITDA": key_stats.get("enterpriseValueOverEBITDA", None),
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
# Growth Metrics
# ------------------
def compute_growth(ticker):
    try:
        t = Ticker(ticker)
        fin = t.all_financial_data().reset_index()
        fin = fin.pivot(index="asOfDate", columns="periodType", values="TotalRevenue").sort_index()
        
        growth = {}
        if not fin.empty and fin.shape[0] > 1:
            growth["Revenue Growth (YoY)"] = round((fin.iloc[-1,0] - fin.iloc[-2,0]) / fin.iloc[-2,0] * 100, 2)
        return growth
    except Exception as e:
        print("Growth calc error:", e)
        return {"Info": "Growth data not available"}

# ------------------
# Screening Filters
# ------------------
def screen_stocks(tickers, criteria={"ROE": 0.15, "Debt/Equity": 1.0}):
    results = []
    for tkr in tickers:
        ratios = get_ratios_yq(tkr)
        if not ratios:
            continue

        passed = True
        reasons = []
        for metric, threshold in criteria.items():
            value = ratios.get(metric, None)
            if value is None:
                reasons.append(f"{metric}: Missing")
                passed = False
                continue

            # Rule: if metric is ROE/ROCE → want HIGH
            if metric in ["ROE", "ROCE"]:
                if value < threshold:
                    reasons.append(f"{metric}: {value} < {threshold}")
                    passed = False
            # Rule: if metric is Debt/Equity → want LOW
            elif metric == "Debt/Equity":
                if value > threshold:
                    reasons.append(f"{metric}: {value} > {threshold}")

        if passed:
            results.append({"Ticker": tkr, **ratios, "Status": "PASS"})
        else:
            results.append({"Ticker": tkr, **ratios, "Status": "FAIL", "Reason": "; ".join(reasons)})

    return pd.DataFrame(results)



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
