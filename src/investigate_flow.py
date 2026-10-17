
from collections import Counter
from falkordb import FalkorDB

# Connect to FalkorDB
db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("graphsleuth")

# Step 1: Find chronological multi-hop transaction flows
result = graph.query("""
    MATCH p = (source:Account)-[:TRANSFER*2..4]->(destination:Account)
    WITH p,
         [r IN relationships(p) | r.amount] AS amounts,
         [r IN relationships(p) | r.timestamp] AS times
    WHERE ALL(amount IN amounts WHERE amount IS NOT NULL)
      AND ALL(
          i IN range(0, size(times) - 2)
          WHERE times[i] <= times[i + 1]
      )
    RETURN [n IN nodes(p) | n.account_id] AS accounts,
           amounts,
           times,
           length(p) AS hops
    ORDER BY hops DESC
    LIMIT 20
""")

paths = result.result_set

print("GRAPHSLEUTH: EVIDENCE-DRIVEN INVESTIGATION")
print("=" * 48)

if not paths:
    print("No chronological multi-hop flows found.")
    print("Agent decision: inspect individual transfers next.")

else:
    print(f"Candidate flows found: {len(paths)}")

    # Step 2: Summarize the observed paths
    account_frequency = Counter()

    for row in paths:
        accounts, amounts, times, hops = row
        print(f"\nPath: {' -> '.join(accounts)}")
        print(f"Amounts: {amounts}")
        print(f"Times: {times}")
        print(f"Hops: {hops}")

        # Count accounts appearing in the candidate flows
        account_frequency.update(accounts)

    # Step 3: Choose a follow-up investigation from the evidence
    # Exclude the endpoints when possible, to focus on intermediaries.
    intermediate_frequency = Counter()

    for row in paths:
        accounts = row[0]
        intermediate_frequency.update(accounts[1:-1])

    print("\n" + "=" * 48)
    print("AGENT DECISION")

    if intermediate_frequency:
        focus_account, appearances = (
            intermediate_frequency.most_common(1)[0]
        )

        print(
            f"Selected {focus_account}: it appears as an "
            f"intermediate account in {appearances} candidate paths."
        )
        print(
            "Reason: repeated appearances make this account "
            "useful to inspect next."
        )

    else:
        # If there are no intermediate accounts, inspect the
        # starting account of the longest candidate flow.
        longest_path = max(paths, key=lambda row: row[3])
        focus_account = longest_path[0][0]

        print(
            f"Selected {focus_account} from the longest "
            "candidate flow."
        )
        print(
            "Reason: inspect its connected transfers to gather "
            "more evidence."
        )

    # Step 4: Follow up with a targeted query for that account
    follow_up = graph.query("""
        MATCH (a:Account)-[t:TRANSFER]->(b:Account)
        WHERE a.account_id = $account
           OR b.account_id = $account
        RETURN a.account_id AS source,
               b.account_id AS target,
               t.amount AS amount,
               t.timestamp AS timestamp,
               t.transaction_id AS transaction_id
        ORDER BY timestamp
        LIMIT 20
    """, {"account": focus_account})

    print(f"\nFOLLOW-UP: Transfers connected to {focus_account}")
    
    flow_result = graph.query("""
        MATCH (source:Account)-[t:TRANSFER]->(target:Account)
        WHERE target.account_id = $account
        RETURN sum(t.amount) AS incoming_total
    """, {"account": focus_account})

    incoming_total = flow_result.result_set[0][0] or 0

    outgoing_result = graph.query("""
        MATCH (source:Account)-[t:TRANSFER]->(target:Account)
        WHERE source.account_id = $account
        RETURN sum(t.amount) AS outgoing_total
    """, {"account": focus_account})

    outgoing_total = outgoing_result.result_set[0][0] or 0

    print(f"Incoming transfer total: {incoming_total:.2f}")
    print(f"Outgoing transfer total: {outgoing_total:.2f}")
    print(
        "Outgoing minus incoming: "
        f"{outgoing_total - incoming_total:.2f}"
    )
    print(
        "Note: these totals cover all recorded transfers for this "
        "account, not just the candidate paths above."
    )


    if not follow_up.result_set:
        print("No connected transfers returned.")

    else:
        for row in follow_up.result_set:
            source, target, amount, timestamp, tx_id = row
            print(
                f"{source} -> {target} | "
                f"{amount} | {timestamp} | {tx_id}"
            )

    print("\nAGENT SUMMARY")
    print(
        f"{focus_account} received {incoming_total:.2f} "
        f"and sent {outgoing_total:.2f}."
    )
    print(
        f"The recorded net flow (outgoing minus incoming) "
        f"is {outgoing_total - incoming_total:.2f}."
    )
    print(
        "Next step: review the connected transactions and "
        "the upstream and downstream accounts."
    )
    print("\nInvestigation status: candidate evidence only.")
    print("Graph patterns are leads, not proof of fraud.")
