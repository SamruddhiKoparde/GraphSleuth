# GraphSleuth

GraphSleuth is a graph-based transaction investigation tool built with Python, Streamlit, and FalkorDB. It was developed for the WeMakeDevs x FalkorDB Graph Hacks, Track 01: Agents That Act on Connected Data.

The project explores how graph databases can help investigators understand transaction flows, identify accounts that may need further review, and examine relationships between connected accounts.

## What it does

- **Account risk ranking:** Assigns heuristic risk scores to accounts and displays the graph evidence behind each score.
- **Agent investigation:** Finds chronological multi-hop transaction paths and ranks accounts based on how frequently they appear as intermediate accounts.
- **Intervention simulation:** Compares how excluding different accounts affects the number of chronological transaction paths.
- **Account investigation:** Displays outgoing transaction paths, transfer amounts, timestamps, and connected accounts.
- **Network visualization:** Shows accounts and transfers as an interactive directed graph.
- **CSV upload:** Validates transaction data and loads it into FalkorDB for analysis.

## How it works

Transaction records are loaded into FalkorDB as a graph. Each account is represented by an `Account` node, and each transfer is represented by a directed `TRANSFER` relationship.

A transfer stores its transaction ID, amount, and timestamp. The application uses Cypher queries to explore connections and find chronological paths containing two to four transfers.

The risk-ranking module uses graph-derived indicators, such as repeated involvement in multi-hop paths, receiving and forwarding funds, large outgoing transfer totals, and transaction activity. The agent investigation uses path frequency to recommend accounts for further review.

The intervention simulator compares the number of paths found in the original graph with the number remaining when a selected account is excluded from the query. This is a simulation; it does not actually block an account or change the graph.

## Technologies

- Python
- FalkorDB
- Cypher
- Streamlit
- streamlit-agraph

## Project structure

```text
GraphSleuth/
├── app.py
├── README.md
├── requirements.txt
├── test_connection.py
├── data/
│   ├── transactions.csv
│   └── Demo.csv
└── src/
    ├── csv_loader.py
    ├── find_paths.py
    ├── inspect_network.py
    ├── investigate_flow.py
    ├── load_data.py
    ├── rank_accounts.py
    ├── risk_score.py
    └── verify_graph.py
```

## Requirements

- Python 3.11 or newer
- Docker Desktop
- Git

FalkorDB must be running locally for the application to work.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/SamruddhiKoparde/GraphSleuth
cd GraphSleuth
```

### 2. Create a virtual environment

On Windows PowerShell, run:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install the dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Start FalkorDB

If you have not created the container yet, run:

```powershell
docker run -d --name graphsleuth-db -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest
```

If the container already exists, start it with:

```powershell
docker start graphsleuth-db
```

The application connects to FalkorDB at `localhost:6379` and uses the `graphsleuth` graph.

### 5. Run the application

From the project directory, run:

```powershell
python -m streamlit run app.py
```

Open the local URL displayed in the terminal.

### 6. Load transaction data

Upload `data/transactions.csv` in the dashboard and click **Load CSV and Analyze**. Once the data is loaded, you can explore the risk ranking, run the agent investigation, simulate interventions, and investigate individual accounts.

You can also upload `data/Demo.csv` to try the application with a smaller dataset.

Or you can also upload the CSV file you want to check, before analyzing do check if the expected columns are proper and are in below given format.

Uploading a CSV replaces the current graph data.

## CSV format

The uploaded file must contain these columns:

| Column | Description |
| `transaction_id` | Transaction identifier |
| `source_account` | Account sending the transfer |
| `target_account` | Account receiving the transfer |
| `amount` | Transfer amount |
| `timestamp` | Transaction timestamp |

Example:

```csv
transaction_id,source_account,target_account,amount,timestamp
T001,A101,A201,950,2026-10-15T09:00:00
T002,A101,A202,970,2026-10-15T09:04:00
T003,A201,A301,900,2026-10-15T09:10:00
```

The CSV validation and graph-loading code is in `src/csv_loader.py`.

## Sample data

The repository includes three synthetic datasets:

- `data/transactions.csv` contains the main example transaction network.
- `data/Demo.csv` contains a smaller dataset for testing.
- `data/test.csv` contains another dataset for testing.

These datasets are for demonstration purposes and do not contain real banking records.

### Evidence-Driven Investigation

**File:** `src/investigate_flow.py`

**Purpose:** Identify candidate transaction flows, select an account for further investigation, and retrieve supporting transaction evidence using FalkorDB.

**Graph query - chronological multi-hop paths:**

```cypher
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
```

This query discovers directed paths containing 2–4 transfers. It checks that amounts are present and timestamps are in non-decreasing order, then returns account IDs, amounts, timestamps, and path lengths.

**Graph algorithms and application logic:**

- Counts how frequently accounts appear as intermediate nodes in candidate paths.
- Selects the most frequently recurring intermediate account for further investigation.
- If no intermediate account exists, selects the starting account from the longest candidate path.
- Retrieves connected transfers and calculates total incoming and outgoing amounts for the selected account.

**Investigation output:** The application reports the selected account, the reason for selection, connected transaction evidence, and net flow calculated as outgoing minus incoming.

## Limitations

GraphSleuth is a hackathon prototype. Its risk scores are based on heuristics and are not calibrated probabilities of fraud. A connected transaction path does not establish wrongdoing, and the results may require further investigation.

The application limits the number of paths returned for analysis. It also expects a locally accessible FalkorDB instance and does not implement production-grade authentication or multi-user data isolation.

The intervention simulator is hypothetical and does not execute real account-blocking actions. All findings should be reviewed independently before any consequential decisions are made.

## Hackathon

Event: WeMakeDevs x FalkorDB Graph Hacks

Track: Track 01 - Agents That Act on Connected Data

Repository: https://github.com/SamruddhiKoparde/GraphSleuth 

Demo video: https://youtu.be/5x-QltCpvt4?si=jb6pVaostrHq-c4g

## AI assistance

AI assistance was used during development for coding guidance, debugging, and documentation. The implementation was tested and refined during development.

The current investigation agent uses deterministic graph queries and Python-based heuristic ranking. It does not call an external large language model API.

## License

No license has been added to the repository yet. Add a license file if you decide to distribute the project under an open-source license.
