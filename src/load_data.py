
import csv
from pathlib import Path

from falkordb import FalkorDB

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "transactions.csv"

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("graphsleuth")

with CSV_PATH.open("r", newline="", encoding="utf-8") as file:
    transactions = list(csv.DictReader(file))
    print("CSV file:", CSV_PATH)
    print("CSV columns:", list(transactions[0].keys()) if transactions else "No rows")

# Reset this demo graph so repeated runs don't duplicate transactions.
graph.query("MATCH (n) DETACH DELETE n")

for tx in transactions:
    amount = float(tx["amount"])
    transaction_id = tx["transaction_id"]
    timestamp = tx["timestamp"]
    source = tx["source_account"]
    target = tx["target_account"]

    graph.query(
        """
        MERGE (s:Account {account_id: $source})
        MERGE (t:Account {account_id: $target})
        CREATE (s)-[:TRANSFER {
            transaction_id: $transaction_id,
            amount: $amount,
            timestamp: $timestamp
        }]->(t)
        """,
        params={
            "source": source,
            "target": target,
            "transaction_id": transaction_id,
            "amount": amount,
            "timestamp": timestamp,
        },
    )

print(f"Loaded {len(transactions)} transactions into FalkorDB.")
