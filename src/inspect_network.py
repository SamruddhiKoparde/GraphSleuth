
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("graphsleuth")

result = graph.query("""
MATCH (a:Account)
OPTIONAL MATCH (a)-[out:TRANSFER]->()
WITH a, count(out) AS outgoing
OPTIONAL MATCH ()-[inc:TRANSFER]->(a)
RETURN a.account_id AS account,
       outgoing,
       count(inc) AS incoming
ORDER BY outgoing DESC, incoming DESC, account
""")

print("Account | Outgoing | Incoming")
for row in result.result_set:
    print(f"{row[0]} | {row[1]} | {row[2]}")
