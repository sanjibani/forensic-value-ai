import json
from pathlib import Path

TICKERS_FILE = Path("data/tickers.json")

# The list we just added
nano_caps = [
    "SAKUMA", "MENONBE", "ASIANENE", "ORIENTBELL", "ARMANFIN",
    "PLASTIBLEN", "NGLFINE", "GOCLCORP", "HINDCOMPOS", "NCLIND",
    "TBZ", "EXPLEOSOL", "GEPIL", "KICL", "WHEELS"
]

def prioritize():
    if not TICKERS_FILE.exists():
        return

    with open(TICKERS_FILE, "r") as f:
        existing = json.load(f)

    # Separate nano caps from others
    nano_objs = []
    others = []

    for t in existing:
        if t["ticker"] in nano_caps:
            nano_objs.append(t)
        else:
            others.append(t)

    # Verify we found them
    print(f"Found {len(nano_objs)} Nano Cap tickers to prioritize.")

    # Combine: Nano Caps first, then others
    new_list = nano_objs + others

    with open(TICKERS_FILE, "w") as f:
        json.dump(new_list, f, indent=4)
    
    print("Reordered tickers.json: Nano Caps are now at the top.")

if __name__ == "__main__":
    prioritize()
