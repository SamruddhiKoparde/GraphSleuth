
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("graphsleuth")

result = graph.query("RETURN 'GraphSleuth connected!' AS message")
print(result.result_set[0][0])
