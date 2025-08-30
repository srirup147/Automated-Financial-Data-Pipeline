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
        net_income = income_stmt.loc["Net Income"].iloc[0]
        equity = balance_sheet.loc["Total Stockholder Equity"].iloc[0]
        ebit = income_stmt.loc["Ebit"].iloc[0]
        total_assets = balance_sheet.loc["Total Assets"].iloc[0]
        total_liabilities = balance_sheet.loc["Total Liab"].iloc[0]

        ratios["ROE"] = round(net_income / equity, 3)
        ratios["ROCE"] = round(ebit / (total_assets - total_liabilities), 3)
        ratios["Debt/Equity"] = round(total_liabilities / equity, 3)
    except Exception:
        pass
    return ratios
