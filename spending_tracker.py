"""
Capital One Spending Tracker — CSV Upload Edition
---------------------------------------------------
No API keys or third-party accounts needed.

How to get your Capital One CSV:
  1. Log in at capitalone.com
  2. Go to your account > Transaction History
  3. Click "Download" and choose CSV
  4. Upload the file here

Run:
  pip install -r requirements.txt
  python spending_tracker.py
  Open http://localhost:5000
"""

import csv
import io
from collections import defaultdict
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Capital One CSV columns (case-insensitive matching below)
COL_DATE = "transaction date"
COL_DESC = "description"
COL_CATEGORY = "category"
COL_DEBIT = "debit"
COL_CREDIT = "credit"
COL_CARD = "card no."


def parse_capital_one_csv(text: str) -> list[dict]:
    """Parse a Capital One transaction CSV into a list of transaction dicts."""
    reader = csv.DictReader(io.StringIO(text))

    # Normalize header names to lowercase
    rows = []
    for row in reader:
        normalized = {k.strip().lower(): v.strip() for k, v in row.items()}
        rows.append(normalized)

    transactions = []
    for row in rows:
        # Skip credits/refunds (Debit is blank, Credit has a value)
        debit_str = row.get(COL_DEBIT, "").replace("$", "").replace(",", "").strip()
        credit_str = row.get(COL_CREDIT, "").replace("$", "").replace(",", "").strip()

        try:
            amount = float(debit_str) if debit_str else 0.0
        except ValueError:
            amount = 0.0

        try:
            credit = float(credit_str) if credit_str else 0.0
        except ValueError:
            credit = 0.0

        # Skip credits/refunds; include only debits
        if amount <= 0:
            continue

        transactions.append({
            "date": row.get(COL_DATE, ""),
            "name": row.get(COL_DESC, ""),
            "category": row.get(COL_CATEGORY, "Uncategorized") or "Uncategorized",
            "amount": round(amount, 2),
            "credit": round(credit, 2),
            "card": row.get(COL_CARD, ""),
        })

    return transactions


def build_summary(transactions: list[dict]) -> dict:
    by_category: dict[str, float] = defaultdict(float)
    by_date: dict[str, float] = defaultdict(float)
    total = 0.0

    for t in transactions:
        by_category[t["category"]] += t["amount"]
        by_date[t["date"]] += t["amount"]
        total += t["amount"]

    # Sort dates chronologically, categories by spend descending
    sorted_dates = dict(sorted(by_date.items()))
    sorted_cats = dict(sorted(by_category.items(), key=lambda x: -x[1]))

    return {
        "total": round(total, 2),
        "by_category": {k: round(v, 2) for k, v in sorted_cats.items()},
        "by_date": {k: round(v, 2) for k, v in sorted_dates.items()},
        "transactions": sorted(transactions, key=lambda x: x["date"], reverse=True),
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    """Accept a Capital One CSV file and return spending data."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    if not f.filename.lower().endswith(".csv"):
        return jsonify({"error": "Please upload a .csv file"}), 400

    try:
        text = f.read().decode("utf-8-sig")  # utf-8-sig strips BOM if present
    except UnicodeDecodeError:
        try:
            f.seek(0)
            text = f.read().decode("latin-1")
        except Exception as e:
            return jsonify({"error": f"Could not read file: {e}"}), 400

    try:
        transactions = parse_capital_one_csv(text)
    except Exception as e:
        return jsonify({"error": f"Parse error: {e}"}), 400

    if not transactions:
        return jsonify({"error": "No debit transactions found. Make sure this is a Capital One CSV."}), 400

    return jsonify(build_summary(transactions))


if __name__ == "__main__":
    import os
    os.makedirs("templates", exist_ok=True)
    print("Starting Capital One Spending Tracker on http://localhost:5000")
    app.run(debug=True, port=5000)
