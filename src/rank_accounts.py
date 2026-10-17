
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("graphsleuth")

result = graph.query("""
MATCH (a:Account)
OPTIONAL MATCH (a)-[out:TRANSFER]->()
WITH a, count(out) AS outgoing
OPTIONAL MATCH ()-[inc:TRANSFER]->(a)
WITH a, outgoing, count(inc) AS incoming
RETURN a.account_id AS account,
       incoming,
       outgoing,
       incoming + outgoing AS total_activity,
       CASE
           WHEN incoming > 0 AND outgoing > 0
           THEN 'Receives and forwards'
           ELSE 'Other activity'
       END AS pattern
ORDER BY total_activity DESC, account
""")

print("Account | In | Out | Total | Pattern")
for row in result.result_set:
    print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}")
