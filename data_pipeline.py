import yfinance as yf
import pandas as pd
from yahooquery import Ticker
import requests

# ------------------
# Stock Price Fetcher
# ------------------
def fetch_stock_data(ticker, period="1y", interval="1d"):
    """
    Fetch stock price history using yfinance.
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df is None or df.empty:
            return pd.DataFrame()
        df.reset_index(inplace=True)
        return df
    except Exception as e:
        return pd.DataFrame({"Error": [str(e)]})

# ------------------
# Financials
# ------------------
def get_financials(ticker):
    """
    Fetch balance sheet & income statement using yfinance.
    """
    try:
        stock = yf.Ticker(ticker)
        balance_sheet = stock.balance_sheet
        income_stmt = stock.financials
        return balance_sheet, income_stmt
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

# ------------------
# Ratios (Yahooquery + fallback)
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
            ratios = {k: round(v, 3) for k, v in ratios.items() if v is not None}
            if ratios:
                return ratios
    except Exception as e:
        print("Yahooquery error:", e)
    return None

def compute_ratios(ticker):
    ratios = get_ratios_yq(ticker)
    if ratios:
        return ratios
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
            growth["Revenue Growth (YoY)"] = round(
                (fin.iloc[-1, 0] - fin.iloc[-2, 0]) / fin.iloc[-2, 0] * 100, 2
            )
        return growth
    except Exception as e:
        print("Growth calc error:", e)
        return {"Info": "Growth data not available"}

# ------------------
# Stock Screening
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

            # Rule: want high for ROE/ROCE
            if metric in ["ROE", "ROCE"]:
                if value < threshold:
                    reasons.append(f"{metric}: {value} < {threshold}")
                    passed = False
            # Rule: want low for Debt/Equity
            elif metric == "Debt/Equity":
                if value > threshold:
                    reasons.append(f"{metric}: {value} > {threshold}")
                    passed = False

        if passed:
            results.append({"Ticker": tkr, **ratios, "Status": "PASS"})
        else:
            results.append({"Ticker": tkr, **ratios, "Status": "FAIL", "Reason": "; ".join(reasons)})

    return pd.DataFrame(results)
