# ============================================================
# Bank Nifty ATM Straddle - Daily Auto Paper-Trading Tracker
# ============================================================
# STRATEGY BEING TRACKED:
# Entry: ~3:15 PM, buy ATM Call (CE) + ATM Put (PE)
# SL: 50 points per leg | Target: 150 points per leg
# Exit: next day (checked against your logged snapshots)
#
# HOW THIS WORKS:
# - Run this ONCE a day around 3:15 PM in Google Colab.
# - Each run does TWO things automatically:
#     1) Checks YESTERDAY's open trade against TODAY's price
#        -> marks it as Target Hit / SL Hit / Closed at current price
#     2) Logs a fresh NEW entry for today at today's ATM CE/PE price
# - Over time, banknifty_paper_trades.csv builds up a full
#   day-by-day trade history with automatic P&L per leg.
#
# IMPORTANT HONEST LIMITATION:
# Since this only takes ONE snapshot per day (whenever you run it,
# e.g. 3:15 PM), it can only tell whether SL/Target was hit
# BETWEEN two snapshots -- not the exact intraday moment. If price
# touched your SL and recovered before the next day's 3:15 PM
# snapshot, this script will NOT catch that -- it will just see
# wherever the price ended up at the next snapshot. For more
# accuracy, run this script MORE OFTEN during the day (e.g. every
# hour) -- the code works the same either way, it just compares
# against whatever the most recent OPEN trade is.
# ============================================================

import requests
import pandas as pd
from datetime import datetime
import os

LOG_FILE = "banknifty_paper_trades.csv"
SL = 50
TARGET = 150

def fetch_banknifty_option_chain():
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=BANKNIFTY"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/115.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers, timeout=10)
    response = session.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()

def get_atm_ce_pe(data):
    spot = data["records"]["underlyingValue"]
    expiry = data["records"]["expiryDates"][0]
    atm_strike = round(spot / 100) * 100
    ce_price, pe_price = None, None
    for item in data["records"]["data"]:
        if item.get("expiryDate") == expiry and item.get("strikePrice") == atm_strike:
            if "CE" in item:
                ce_price = item["CE"]["lastPrice"]
            if "PE" in item:
                pe_price = item["PE"]["lastPrice"]
    return spot, atm_strike, expiry, ce_price, pe_price

def load_log():
    if os.path.isfile(LOG_FILE):
        return pd.read_csv(LOG_FILE)
    return pd.DataFrame(columns=[
        "entry_date", "entry_time", "spot_entry", "strike", "expiry",
        "ce_entry", "pe_entry",
        "status", "exit_date", "exit_time", "spot_exit",
        "ce_exit", "pe_exit", "ce_pnl", "pe_pnl", "total_pnl"
    ])

def save_log(df):
    df.to_csv(LOG_FILE, index=False)

def close_open_trades(df, current_ce, current_pe, spot, now):
    """Check any OPEN trade against today's price and close it out."""
    open_mask = df["status"] == "OPEN"
    if open_mask.sum() == 0:
        print("No open trade to evaluate today.")
        return df

    for idx in df[open_mask].index:
        ce_entry = df.at[idx, "ce_entry"]
        pe_entry = df.at[idx, "pe_entry"]

        ce_move = current_ce - ce_entry
        pe_move = current_pe - pe_entry

        if ce_move >= TARGET:
            ce_pnl = TARGET
        elif ce_move <= -SL:
            ce_pnl = -SL
        else:
            ce_pnl = ce_move

        if pe_move >= TARGET:
            pe_pnl = TARGET
        elif pe_move <= -SL:
            pe_pnl = -SL
        else:
            pe_pnl = pe_move

        df.at[idx, "status"] = "CLOSED"
        df.at[idx, "exit_date"] = now.strftime("%d-%b-%Y")
        df.at[idx, "exit_time"] = now.strftime("%H:%M:%S")
        df.at[idx, "spot_exit"] = spot
        df.at[idx, "ce_exit"] = current_ce
        df.at[idx, "pe_exit"] = current_pe
        df.at[idx, "ce_pnl"] = round(ce_pnl, 1)
        df.at[idx, "pe_pnl"] = round(pe_pnl, 1)
        df.at[idx, "total_pnl"] = round(ce_pnl + pe_pnl, 1)

        print(f"Closed trade from {df.at[idx,'entry_date']}: "
              f"CE P&L={ce_pnl:.1f}, PE P&L={pe_pnl:.1f}, "
              f"Total={ce_pnl+pe_pnl:.1f} points")
    return df

def log_new_entry(df, spot, strike, expiry, ce, pe, now):
    new_row = {
        "entry_date": now.strftime("%d-%b-%Y"),
        "entry_time": now.strftime("%H:%M:%S"),
        "spot_entry": spot,
        "strike": strike,
        "expiry": expiry,
        "ce_entry": ce,
        "pe_entry": pe,
        "status": "OPEN",
        "exit_date": "", "exit_time": "", "spot_exit": "",
        "ce_exit": "", "pe_exit": "", "ce_pnl": "", "pe_pnl": "", "total_pnl": "",
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    print(f"\nNew entry logged for {new_row['entry_date']}: "
          f"Strike={strike}, CE={ce}, PE={pe}")
    return df

def run_daily():
    now = datetime.now()
    data = fetch_banknifty_option_chain()
    spot, strike, expiry, ce, pe = get_atm_ce_pe(data)

    df = load_log()
    df = close_open_trades(df, ce, pe, spot, now)
    df = log_new_entry(df, spot, strike, expiry, ce, pe, now)
    save_log(df)

    # Summary of all CLOSED trades so far
    closed = df[df["status"] == "CLOSED"]
    if len(closed) > 0:
        total_pnl = closed["total_pnl"].astype(float).sum()
        wins = (closed["total_pnl"].astype(float) > 0).sum()
        print(f"\n--- Overall Summary ({len(closed)} closed trades) ---")
        print(f"Total P&L: {total_pnl:.1f} points")
        print(f"Win days: {wins}/{len(closed)} ({wins/len(closed)*100:.1f}%)")
    else:
        print("\nNo closed trades yet -- check back after tomorrow's run.")

# Run it
run_daily()
