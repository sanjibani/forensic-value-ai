import json
from pathlib import Path

TICKERS_FILE = Path("data/tickers.json")

new_tickers = [
    {"ticker": "SAKUMA", "name": "Sakuma Exports Ltd"},
    {"ticker": "MENONBE", "name": "Menon Bearings Ltd"},
    {"ticker": "ASIANENE", "name": "Asian Energy Services Ltd"},
    {"ticker": "ORIENTBELL", "name": "Orient Bell Ltd"},
    {"ticker": "ARMANFIN", "name": "Arman Financial Services Ltd"},
    {"ticker": "PLASTIBLEN", "name": "Plastiblends India Ltd"},
    {"ticker": "NGLFINE", "name": "NGL Fine-Chem Ltd"},
    {"ticker": "GOCLCORP", "name": "GOCL Corporation Ltd"},
    {"ticker": "HINDCOMPOS", "name": "Hindustan Composites Ltd"},
    {"ticker": "NCLIND", "name": "NCL Industries Ltd"},
    {"ticker": "TBZ", "name": "Tribhovandas Bhimji Zaveri Ltd"},
    {"ticker": "EXPLEOSOL", "name": "Expleo Solutions Ltd"},
    {"ticker": "GEPIL", "name": "GE Power India Ltd"},
    {"ticker": "KICL", "name": "Kalyani Investment Company Ltd"},
    {"ticker": "WHEELS", "name": "Wheels India Ltd"},
]

def add_tickers():
    if not TICKERS_FILE.exists():
        print(f"Error: {TICKERS_FILE} not found.")
        return

    with open(TICKERS_FILE, "r") as f:
        existing = json.load(f)

    existing_tickers = {t["ticker"] for t in existing}
    added_count = 0

    for t in new_tickers:
        if t["ticker"] not in existing_tickers:
            existing.append(t)
            existing_tickers.add(t["ticker"])
            added_count += 1
            print(f"Added {t['ticker']}")

    if added_count > 0:
        with open(TICKERS_FILE, "w") as f:
            json.dump(existing, f, indent=4)
        print(f"\nSuccessfully added {added_count} Nano Cap tickers.")
    else:
        print("\nNo new tickers added (all duplicates).")

if __name__ == "__main__":
    add_tickers()
