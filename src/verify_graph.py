
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("graphsleuth")

result = graph.query("""
MATCH (a:Account)
WITH count(a) AS accounts
MATCH ()-[t:TRANSFER]->()
RETURN accounts, count(t) AS transfers
""")

print(f"Accounts: {result.result_set[0][0]}")
print(f"Transfers: {result.result_set[0][1]}")
