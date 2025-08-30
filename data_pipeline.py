# data_pipeline.py
import yfinance as yf
from yahooquery import Ticker
import pandas as pd
import requests
from bs4 import BeautifulSoup
import numpy as np
import math
import warnings
warnings.filterwarnings("ignore")

# -----------------------
# Helpers
# -----------------------
def _to_num(x):
    """Try to coerce various formats to float. Accepts '15', '15%', '0.15', '1,234'"""
    if x is None:
        return None
    try:
        # direct numeric
        if isinstance(x, (int, float, np.floating, np.integer)):
            return float(x)
        s = str(x).strip().replace(",", "")
        if s == "" or s.lower() in ["nan", "n/a", "-", "--"]:
            return None
        # percent string '15%'
        if s.endswith("%"):
            v = float(s[:-1])
            return v / 100.0 if abs(v) > 1e-9 else 0.0
        # sometimes values come as strings with brackets or text - keep digits & dot & minus
        cleaned = "".join(ch for ch in s if ch.isdigit() or ch in ".-")
        if cleaned == "" or cleaned in [".", "-", "-."]:
            return None
        v = float(cleaned)
        return v
    except Exception:
        return None

def normalize_metric(value, metric_name):
    """Normalize representation for metrics where we expect percentage-like numbers (ROE/ROCE/growth)
       Returns float in decimal for percentage metrics (e.g., 0.15 = 15%)."""
    v = _to_num(value)
    if v is None:
        return None
    # For ROE/ROCE/Growth: if value looks > 1 assume it's expressed as percentage (15 -> 15%)
    if metric_name in ["ROE", "ROCE", "Revenue Growth (YoY)"]:
        if v > 1.0:
            return v / 100.0
        return v
    # For Debt/Equity & other ratios, keep as-is
    return v

# -----------------------
# Primary: yahooquery key_metrics
# -----------------------
def get_ratios_yq(ticker):
    try:
        t = Ticker(ticker)
        # key_metrics sometimes returns dict keyed by ticker, sometimes DataFrame-like
        raw = None
        try:
            raw = t.key_metrics.get(ticker) if isinstance(t.key_metrics, dict) else t.key_metrics
        except Exception:
            raw = t.key_metrics

        # if raw is a pandas DataFrame, convert to dictionary of latest column
        km = {}
        if isinstance(raw, pd.DataFrame):
            # take first (most recent) column if numeric columns exist
            try:
                col = raw.columns[0]
                km = raw[col].to_dict()
            except Exception:
                km = raw.to_dict()
        elif isinstance(raw, dict):
            km = raw
        else:
            km = dict(raw) if raw is not None else {}

        # common key names to look for (lowercased)
        lower_km = {str(k).lower(): v for k, v in km.items()}

        def pick(keys):
            for k in keys:
                if k.lower() in lower_km:
                    return lower_km[k.lower()]
            return None

        candidates = {
            "ROE": ["returnonequity", "returnoninvestedcapital", "returnOnEquity", "returnOnAssets"],
            "ROCE": ["returnoncapitalemployed", "returnoncapital", "returnOnCapitalEmployed"],
            "Debt/Equity": ["debttoequity", "totaldebttoequity", "totalDebt/equity", "totaldebt/equity", "totalDebtToEquity"],
            "P/E": ["peRatio", "priceEarningsRatio", "peRatio"],
            "P/B": ["pbRatio", "priceToBook"],
            "EV/EBITDA": ["enterprisevalueoverebitda", "evToEbitda", "enterpriseValueOverEbitda"]
        }

        ratios = {}
        for name, keys in candidates.items():
            val = pick(keys)
            if val is not None:
                ratios[name] = normalize_metric(val, name)

        # if any ratios found return them
        if ratios:
            return ratios

    except Exception as e:
        print("get_ratios_yq error:", e)
    return None

# -----------------------
# Fallback: compute from yfinance financials (Net income / Equity etc.)
# -----------------------
def compute_from_yfinance(ticker):
    try:
        yf_t = yf.Ticker(ticker)
        fin = yf_t.financials    # income statement
        bs = yf_t.balance_sheet  # balance sheet

        if (fin is None or fin.empty) or (bs is None or bs.empty):
            return None

        # helper to find a row by keyword in df index
        def find_value(df, keywords):
            if df is None or df.empty:
                return None
            for idx in df.index:
                low = str(idx).lower()
                for k in keywords:
                    if k.lower() in low:
                        try:
                            return _to_num(df.loc[idx].iloc[0])
                        except Exception:
                            pass
            return None

        net_income = find_value(fin, ["net income", "netincome", "net income applicable"])
        equity = find_value(bs, ["total stockholder equity", "total shareholders' equity", "total equity", "total stockholder equity"])
        total_assets = find_value(bs, ["total assets"])
        total_liab = find_value(bs, ["total liab", "total liabilities"])
        ebit = find_value(fin, ["ebit", "operating income", "operatingincome"])

        ratios = {}
        if net_income is not None and equity is not None and equity != 0:
            ratios["ROE"] = normalize_metric(net_income / equity, "ROE")
        if ebit is not None and total_assets is not None and total_liab is not None:
            capital_employed = total_assets - (total_liab if total_liab is not None else 0)
            if capital_employed and capital_employed != 0:
                ratios["ROCE"] = normalize_metric(ebit / capital_employed, "ROCE")
        if total_liab is not None and equity is not None and equity != 0:
            ratios["Debt/Equity"] = normalize_metric(total_liab / equity, "Debt/Equity")

        # P/E and P/B via yfinance quick info
        try:
            info = yf_t.info
            pe = _to_num(info.get("trailingPE") or info.get("regularMarketPrice") / info.get("epsTrailingTwelveMonths") if info.get("epsTrailingTwelveMonths") else None)
            pb = _to_num(info.get("priceToBook"))
            if pe is not None:
                ratios.setdefault("P/E", normalize_metric(pe, "P/E"))
            if pb is not None:
                ratios.setdefault("P/B", normalize_metric(pb, "P/B"))
        except Exception:
            pass

        return ratios if ratios else None
    except Exception as e:
        print("compute_from_yfinance error:", e)
    return None

# -----------------------
# Fallback: Moneycontrol scraping (works for Indian stocks with ratios page)
# Example URL: https://www.moneycontrol.com/financials/tcs-ratiosVI/TCS
# -----------------------
def get_moneycontrol_ratios(stock_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(stock_url, headers=headers, timeout=10)
        tables = pd.read_html(resp.text)
        # heuristics: find a table that contains common ratio strings like 'Return on Equity' or 'Debt to Equity'
        for tbl in tables:
            cols = " ".join(map(str, tbl.columns)).lower()
            text = " ".join(tbl.astype(str).values.flatten()).lower()
            if "return on equity" in cols or "return on equity" in text or "debt to equity" in text:
                # convert to dict and map known names
                rows = tbl.astype(str).to_dict(orient="records")
                mapped = {}
                for r in rows:
                    # many moneycontrol tables have first column as ratio name, second as value
                    # try to parse each row
                    if len(r) >= 2:
                        keys = list(r.keys())
                        name = str(r[keys[0]]).strip().lower()
                        val = r[keys[1]]
                        if "return on equity" in name:
                            mapped["ROE"] = normalize_metric(val, "ROE")
                        if "return on capital employed" in name or "roce" in name:
                            mapped["ROCE"] = normalize_metric(val, "ROCE")
                        if "debt to equity" in name or "debt/equity" in name:
                            mapped["Debt/Equity"] = normalize_metric(val, "Debt/Equity")
                if mapped:
                    return mapped
        # if not matched, try the first table and try to extract numeric-looking fields as fallback
        if tables:
            tbl = tables[0]
            for col in tbl.columns:
                try:
                    tbl[col] = tbl[col].apply(lambda x: _to_num(x) if pd.notna(x) else None)
                except Exception:
                    pass
            # try find columns by names
            return None
    except Exception as e:
        print("get_moneycontrol_ratios error:", e)
    return None

# -----------------------
# Unified compute_ratios
# -----------------------
def compute_ratios(ticker, fallback_url=None):
    # 1) try yahooquery key metrics
    try:
        ratios = get_ratios_yq(ticker)
        if ratios:
            return ratios
    except Exception as e:
        print("yq step error:", e)

    # 2) try compute from yfinance financials
    try:
        ratios = compute_from_yfinance(ticker)
        if ratios:
            return ratios
    except Exception as e:
        print("yf step error:", e)

    # 3) try Moneycontrol fallback (if provided)
    if fallback_url:
        try:
            ratios = get_moneycontrol_ratios(fallback_url)
            if ratios:
                return ratios
        except Exception as e:
            print("moneycontrol step error:", e)

    return {"Info": "Ratios not available for this ticker"}

# -----------------------
# Growth: revenue YoY using yahooquery/yfinance best-effort
# -----------------------
def compute_growth(ticker):
    # try yahooquery first
    try:
        t = Ticker(ticker)
        # try income_statement with annual frequency
        try:
            inc = t.income_statement(frequency='a')
            # if inc is dict keyed by ticker
            if isinstance(inc, dict) and ticker in inc:
                df = pd.DataFrame(inc[ticker])
            elif isinstance(inc, pd.DataFrame):
                df = inc
            else:
                df = None
        except Exception:
            df = None

        if df is not None and not df.empty:
            # try to find total revenue row
            for idx in df.index:
                if 'total revenue' in str(idx).lower() or 'totalrevenue' in str(idx).lower() or 'total revenue' in str(idx).lower():
                    vals = df.loc[idx].dropna().astype(float).values
                    if len(vals) >= 2:
                        # compute YoY of last two
                        last, prev = vals[0], vals[1]
                        if prev != 0:
                            return {"Revenue Growth (YoY)": round((last - prev) / abs(prev), 4)}
        # fallback yfinance
        yf_t = yf.Ticker(ticker)
        fin = yf_t.financials
        if fin is not None and not fin.empty:
            # find revenue row
            for idx in fin.index:
                if 'total revenue' in str(idx).lower() or 'totalrevenue' in str(idx).lower() or 'revenue' in str(idx).lower():
                    vals = fin.loc[idx].dropna().astype(float).values
                    if len(vals) >= 2:
                        last, prev = vals[0], vals[1]
                        if prev != 0:
                            return {"Revenue Growth (YoY)": round((last - prev) / abs(prev), 4)}
    except Exception as e:
        print("compute_growth error:", e)

    return {"Info": "Growth data not available"}

# -----------------------
# Screening
# -----------------------
def screen_stocks(tickers, criteria={"ROE": 0.15, "Debt/Equity": 1.0}, fallback_url_map=None):
    """
    tickers: list of strings
    criteria: dict where keys are metric names and values are thresholds (ROE/ROCE expect decimal e.g., 0.15)
    fallback_url_map: optional dict mapping ticker -> moneycontrol url if needed
    """
    rows = []
    for tkr in tickers:
        fb_url = (fallback_url_map.get(tkr) if fallback_url_map else None)
        ratios = compute_ratios(tkr, fb_url)
        # ensure ratios is dict
        if not isinstance(ratios, dict):
            ratios = {"Info": "Ratios fetch failed"}

        # normalize metric values for comparison
        reasons = []
        passed = True
        normalized = {}
        for metric, threshold in criteria.items():
            raw_val = ratios.get(metric)
            val = normalize_metric(raw_val, metric)
            normalized[metric] = val
            if val is None:
                reasons.append(f"{metric}: Missing")
                passed = False
                continue
            # rule checks
            if metric in ["ROE", "ROCE", "Revenue Growth (YoY)"]:
                if val < threshold:
                    reasons.append(f"{metric}: {val} < {threshold}")
                    passed = False
            elif metric == "Debt/Equity":
                if val > threshold:
                    reasons.append(f"{metric}: {val} > {threshold}")
                    passed = False
            else:
                # default: require equality/threshold not enforced
                pass

        status = "PASS" if passed else "FAIL"
        row = {"Ticker": tkr, **{k: (v if v is not None else "") for k, v in normalized.items()},
               "Status": status, "Reason": "; ".join(reasons)}
        # add the original ratio fields too (for display)
        for k, v in ratios.items():
            if k not in row:
                row[k] = v
        rows.append(row)

    return pd.DataFrame(rows)
