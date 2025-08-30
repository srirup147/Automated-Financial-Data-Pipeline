import yfinance as yf
import pandas as pd

def get_stock_data(ticker, period="1y"):
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    return hist

def get_financials(ticker):
    stock = yf.Ticker(ticker)
    balance_sheet = stock.balance_sheet
    income_stmt = stock.financials
    return balance_sheet, income_stmt

def compute_ratios(income_stmt, balance_sheet):
    ratios = {}
    try:
        income_stmt.index = income_stmt.index.str.lower()
        balance_sheet.index = balance_sheet.index.str.lower()
        net_income = income_stmt.loc["net income", :].iloc[0] if "net income" in income_stmt.index else None
        equity = balance_sheet.loc["total stockholder equity", :].iloc[0] if "total stockholder equity" in balance_sheet.index else None
        ebit = income_stmt.loc["ebit", :].iloc[0] if "ebit" in income_stmt.index else None
        total_assets = balance_sheet.loc["total assets", :].iloc[0] if "total assets" in balance_sheet.index else None
        total_liabilities = balance_sheet.loc["total liab", :].iloc[0] if "total liab" in balance_sheet.index else None
        if net_income and equity:
            ratios["ROE"] = round(net_income / equity, 3)
        if ebit and total_assets and total_liabilities:
            ratios["ROCE"] = round(ebit / (total_assets - total_liabilities), 3)
        if total_liabilities and equity:
            ratios["Debt/Equity"] = round(total_liabilities / equity, 3)

    except Exception as e:
        print("Error computing ratios:", e)

    return ratios if ratios else {"Info": "Ratios not available for this ticker"}

