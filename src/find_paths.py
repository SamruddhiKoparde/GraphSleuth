
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("graphsleuth")

result = graph.query("""
MATCH p = (source:Account)-[:TRANSFER*2..4]->(destination:Account)
WHERE source <> destination
RETURN [node IN nodes(p) | node.account_id] AS accounts,
       length(p) AS hops
ORDER BY hops ASC
LIMIT 20
""")

print("Multi-hop transfer paths:")
for row in result.result_set:
    print(f"{row[1]} hops: {' -> '.join(row[0])}")

print(f"\nPaths found: {len(result.result_set)}")
