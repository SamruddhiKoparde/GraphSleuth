
from falkordb import FalkorDB


def calculate_risk_scores(graph):
    """Calculate transparent heuristic scores for every account."""
    accounts = graph.query("""
        MATCH (a:Account)
        RETURN a.account_id
        ORDER BY a.account_id
    """).result_set

    results = []

    for (account,) in accounts:
        incoming = graph.query("""
            MATCH (:Account)-[t:TRANSFER]->(
                a:Account {account_id: $account}
            )
            RETURN count(t), coalesce(sum(t.amount), 0)
        """, {"account": account}).result_set[0]

        outgoing = graph.query("""
            MATCH (a:Account {account_id: $account})
                  -[t:TRANSFER]->(:Account)
            RETURN count(t), coalesce(sum(t.amount), 0)
        """, {"account": account}).result_set[0]

        path_count = graph.query("""
            MATCH p = (s:Account)-[:TRANSFER*2..4]->(d:Account)
            WHERE ANY(
                n IN nodes(p)
                WHERE n.account_id = $account
            )
            RETURN count(p)
        """, {"account": account}).result_set[0][0]

        score = 0
        reasons = []

        if path_count >= 5:
            score += 40
            reasons.append("Appears in many multi-hop paths")

        if incoming[0] > 0 and outgoing[0] > 0:
            score += 30
            reasons.append("Receives and forwards funds")

        if outgoing[1] >= 1500:
            score += 20
            reasons.append("Large outgoing transfer total")

        if incoming[0] + outgoing[0] >= 3:
            score += 10
            reasons.append("High transaction activity")

        results.append({
            "account": account,
            "score": score,
            "reasons": reasons,
            "incoming_total": incoming[1],
            "outgoing_total": outgoing[1],
            "candidate_paths": path_count,
        })

    return sorted(
        results,
        key=lambda item: item["score"],
        reverse=True,
    )


if __name__ == "__main__":
    db = FalkorDB(host="localhost", port=6379)
    graph = db.select_graph("graphsleuth")

    for item in calculate_risk_scores(graph):
        print(f"\n{item['account']}: {item['score']}/100")
        for reason in item["reasons"]:
            print(f" - {reason}")
        if not item["reasons"]:
            print(" - No elevated graph indicators")
