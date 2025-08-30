import yfinance as yf
import pandas as pd
from yahooquery import Ticker
import requests

# ------------------
# Stock Price Fetcher
# ------------------
def fetch_stock_data(ticker, period="5y", interval="1d"):
    """
    Fetch stock price history using yfinance (default 5 years daily data).
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
from yahooquery import Ticker
import pandas as pd, requests

def get_ratios_yq(ticker):
    try:
        t = Ticker(ticker)

        # Yahoo Finance data
        fin = t.financial_data.get(ticker, {})
        summary = t.summary_detail.get(ticker, {})
        stats = t.key_stats.get(ticker, {})

        ratios = {
            "ROE": fin.get("returnOnEquity"),
            "EPS": stats.get("trailingEps"),
            "P/E": stats.get("trailingPE"),
            "Dividend Yield": summary.get("dividendYield"),
        }

        # Try to compute ROCE = EBIT / (Total Assets - Current Liabilities)
        try:
            fin_stmt = t.all_financial_data(ticker)
            ebit = fin_stmt.loc[(ticker, slice(None)), "EBIT"].iloc[0]
            total_assets = fin_stmt.loc[(ticker, slice(None)), "TotalAssets"].iloc[0]
            curr_liab = fin_stmt.loc[(ticker, slice(None)), "CurrentLiabilities"].iloc[0]
            roce = ebit / (total_assets - curr_liab)
            ratios["ROCE"] = round(roce, 3)
        except Exception as e:
            print("ROCE calc failed:", e)

        # Round numbers
        ratios = {k: round(v, 3) for k, v in ratios.items() if v is not None}
        if ratios:
            return ratios
    except Exception as e:
        print("Yahooquery error:", e)
    return None


def compute_ratios(ticker, fallback_url=None):
    ratios = get_ratios_yq(ticker)
    if ratios:
        # If Industry P/E is missing, try fallback
        if fallback_url:
            try:
                tables = pd.read_html(
                    requests.get(fallback_url, headers={'User-Agent':'Mozilla/5.0'}).text
                )
                for table in tables:
                    if "Industry P/E" in table.to_string():
                        ind_pe = table.iloc[:,1].astype(str).str.extract(r"([\d\.]+)").dropna().values[0][0]
                        ratios["Industry P/E"] = float(ind_pe)
                        break
            except Exception as e:
                ratios["Industry P/E"] = f"Error: {e}"
        return ratios
    elif fallback_url:
        try:
            tables = pd.read_html(
                requests.get(fallback_url, headers={'User-Agent':'Mozilla/5.0'}).text
            )
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
