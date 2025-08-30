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

def compute_ratios(ticker, fallback_url=None):
    ratios = get_ratios_yq(ticker)
    if ratios:
        return ratios
    elif fallback_url:
        try:
            import pandas as pd, requests
            tables = pd.read_html(requests.get(fallback_url, headers={'User-Agent':'Mozilla/5.0'}).text)
            key_ratios = tables[0]
            return {"Moneycontrol_Ratios": key_ratios.to_dict(orient="records")[:5]}
        except Exception as e:
            return {"Error": f"Moneycontrol scrape failed: {str(e)}"}
    else:
        return {"Info": "Ratios not available for this ticker"}
# ------------------
# Growth Metrics
# ------------------
def compute_growth(ticker):
    """
    Compute YoY growth for key metrics using yahooquery.
    Returns Revenue, Net Income, EPS, Free Cash Flow growth.
    """
    try:
        t = Ticker(ticker)
        fin = t.all_financial_data().reset_index()

        if fin.empty:
            return {"Info": "No financial data available"}

        # Pivot for easier access
        fin_pivot = fin.pivot(index="asOfDate", columns="periodType", values="TotalRevenue").sort_index()
        ni_pivot = fin.pivot(index="asOfDate", columns="periodType", values="NetIncome").sort_index()
        eps_pivot = fin.pivot(index="asOfDate", columns="periodType", values="DilutedEPS").sort_index()
        fcf_pivot = fin.pivot(index="asOfDate", columns="periodType", values="FreeCashFlow").sort_index()

        growth = {}

        def calc_growth(df, label):
            if not df.empty and df.shape[0] > 1:
                prev, curr = df.iloc[-2, 0], df.iloc[-1, 0]
                if prev and prev != 0:
                    growth[label] = round((curr - prev) / prev * 100, 2)

        # Compute growth for different metrics
        calc_growth(fin_pivot, "Revenue Growth (YoY)")
        calc_growth(ni_pivot, "Net Income Growth (YoY)")
        calc_growth(eps_pivot, "EPS Growth (YoY)")
        calc_growth(fcf_pivot, "Free Cash Flow Growth (YoY)")

        if not growth:
            return {"Info": "Growth data not available"}
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
