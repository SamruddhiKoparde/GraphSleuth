
import csv
from datetime import datetime
from io import StringIO


REQUIRED_COLUMNS = {
    "transaction_id",
    "source_account",
    "target_account",
    "amount",
    "timestamp",
}


def parse_transactions(file_bytes):
    """Validate an uploaded CSV and return normalized transaction rows."""
    try:
        content = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("The CSV must use UTF-8 encoding.") from exc

    reader = csv.DictReader(StringIO(content))

    if not reader.fieldnames:
        raise ValueError("The CSV is empty or has no header row.")

    # Ignore surrounding spaces in column names.
    reader.fieldnames = [name.strip() for name in reader.fieldnames]

    missing = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(sorted(missing))
        )

    transactions = []
    seen_ids = set()

    for line_number, row in enumerate(reader, start=2):
        # Ignore completely blank lines.
        if not row or all(
            value is None or not value.strip()
            for value in row.values()
        ):
            continue

        transaction_id = (row.get("transaction_id") or "").strip()
        source = (row.get("source_account") or "").strip()
        target = (row.get("target_account") or "").strip()
        amount_text = (row.get("amount") or "").strip()
        timestamp = (row.get("timestamp") or "").strip()

        if not all([transaction_id, source, target, amount_text, timestamp]):
            raise ValueError(
                f"Row {line_number}: all required values must be filled in."
            )

        if transaction_id in seen_ids:
            raise ValueError(
                f"Row {line_number}: duplicate transaction ID "
                f"'{transaction_id}'."
            )
        seen_ids.add(transaction_id)

        if source == target:
            raise ValueError(
                f"Row {line_number}: source and target accounts must differ."
            )

        try:
            amount = float(amount_text)
        except ValueError as exc:
            raise ValueError(
                f"Row {line_number}: amount must be a number."
            ) from exc

        if amount <= 0:
            raise ValueError(
                f"Row {line_number}: amount must be greater than zero."
            )

        try:
            # Accept ISO timestamps, including a trailing Z.
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"Row {line_number}: timestamp must be a valid ISO timestamp."
            ) from exc

        transactions.append({
            "transaction_id": transaction_id,
            "source_account": source,
            "target_account": target,
            "amount": amount,
            "timestamp": timestamp,
        })

    if not transactions:
        raise ValueError("The CSV contains no transaction rows.")

    return transactions


def load_transactions_into_graph(graph, transactions):
    """Replace graph contents with validated transaction rows."""
    # This is destructive to the selected demo graph, so call only
    # after the uploaded CSV has passed validation.
    graph.query("MATCH (n) DETACH DELETE n")

    for tx in transactions:
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
            {
                "source": tx["source_account"],
                "target": tx["target_account"],
                "transaction_id": tx["transaction_id"],
                "amount": tx["amount"],
                "timestamp": tx["timestamp"],
            },
        )
