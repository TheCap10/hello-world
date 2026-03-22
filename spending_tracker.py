"""
Capital One Spending Tracker via Plaid
---------------------------------------
Setup:
  1. Sign up at https://dashboard.plaid.com and get PLAID_CLIENT_ID + PLAID_SECRET
  2. Copy .env.example to .env and fill in your credentials
  3. pip install -r requirements.txt
  4. python spending_tracker.py
  5. Open http://localhost:5000 and click "Connect Capital One"
"""

import os
import json
from datetime import date, timedelta
from collections import defaultdict

from flask import Flask, request, jsonify, render_template, session
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid import ApiClient, Configuration, Environment
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# ── Plaid client setup ────────────────────────────────────────────────────────

PLAID_ENV = os.environ.get("PLAID_ENV", "sandbox")  # sandbox | development | production
ENV_MAP = {
    "sandbox": Environment.Sandbox,
    "development": Environment.Development,
    "production": Environment.Production,
}

configuration = Configuration(
    host=ENV_MAP.get(PLAID_ENV, Environment.Sandbox),
    api_key={
        "clientId": os.environ.get("PLAID_CLIENT_ID", ""),
        "secret": os.environ.get("PLAID_SECRET", ""),
    },
)
api_client = ApiClient(configuration)
plaid_client = plaid_api.PlaidApi(api_client)

# In-memory token store (use a DB in production)
_access_tokens: list[str] = []


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    connected = bool(_access_tokens)
    return render_template("index.html", connected=connected)


@app.route("/api/create_link_token", methods=["POST"])
def create_link_token():
    """Step 1: create a Plaid Link token for the frontend to open."""
    try:
        req = LinkTokenCreateRequest(
            products=[Products("transactions")],
            client_name="Capital One Spending Tracker",
            country_codes=[CountryCode("US")],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id="local-user"),
        )
        response = plaid_client.link_token_create(req)
        return jsonify({"link_token": response["link_token"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/exchange_token", methods=["POST"])
def exchange_token():
    """Step 2: exchange the public token from Plaid Link for an access token."""
    public_token = request.json.get("public_token")
    if not public_token:
        return jsonify({"error": "missing public_token"}), 400
    try:
        req = ItemPublicTokenExchangeRequest(public_token=public_token)
        response = plaid_client.item_public_token_exchange(req)
        _access_tokens.append(response["access_token"])
        return jsonify({"status": "connected"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/transactions")
def get_transactions():
    """Return transactions + spending summary for the past N days."""
    if not _access_tokens:
        return jsonify({"error": "not connected"}), 401

    days = int(request.args.get("days", 30))
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    all_transactions = []
    for token in _access_tokens:
        try:
            options = TransactionsGetRequestOptions(count=500, offset=0)
            req = TransactionsGetRequest(
                access_token=token,
                start_date=start_date,
                end_date=end_date,
                options=options,
            )
            resp = plaid_client.transactions_get(req)
            all_transactions.extend(resp["transactions"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Build summary
    by_category: dict[str, float] = defaultdict(float)
    by_date: dict[str, float] = defaultdict(float)
    total = 0.0
    transactions_out = []

    for txn in all_transactions:
        amount = float(txn["amount"])
        # Plaid: positive = money leaving account, negative = credit/refund
        if amount <= 0:
            continue
        category = (txn.get("category") or ["Uncategorized"])[0]
        txn_date = str(txn["date"])
        by_category[category] += amount
        by_date[txn_date] += amount
        total += amount
        transactions_out.append({
            "date": txn_date,
            "name": txn["name"],
            "amount": round(amount, 2),
            "category": category,
        })

    transactions_out.sort(key=lambda x: x["date"], reverse=True)

    return jsonify({
        "total": round(total, 2),
        "days": days,
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: -x[1])},
        "by_date": dict(sorted(by_date.items())),
        "transactions": transactions_out,
    })


if __name__ == "__main__":
    os.makedirs("templates", exist_ok=True)
    print("Starting Capital One Spending Tracker on http://localhost:5000")
    app.run(debug=True, port=5000)
