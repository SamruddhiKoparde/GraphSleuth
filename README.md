# 🔎 GraphSleuth

**Graph-powered fraud investigation with interactive path analysis and intervention simulation.**

GraphSleuth is a prototype that helps investigators explore suspicious transaction flows using a graph database. It identifies chronological transaction paths, summarizes connected accounts, and simulates how excluding an account affects those paths.

## Features

- **Transaction network:** Explore accounts and transfers in an interactive graph.
- **Chronological path investigation:** Trace multi-hop transaction paths and their amounts and timestamps.
- **Evidence summary:** Review path counts, path lengths, and connected accounts.
- **Intervention simulator:** Compare two account-exclusion scenarios and count paths disrupted.
- **Explainable results:** Display the evidence behind each comparison.
- **Read-only simulation:** Simulated interventions do not delete or modify database records.

## Technology

- Python
- Streamlit
- FalkorDB and Cypher
- `streamlit-agraph` for network visualization
- Synthetic transaction data

## Requirements

- Python installed
- Docker Desktop installed and running
- FalkorDB running locally

## Setup

### 1. Start FalkorDB

```bash
docker run -d --name graphsleuth-db -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest
```

If the container already exists, start it with:

```bash
docker start graphsleuth-db
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install falkordb streamlit streamlit-agraph
```

### 4. Load the synthetic transactions

```bash
python src/load_data.py
```

**Note:** The loader clears the existing graph before reloading the sample data.

### 5. Launch GraphSleuth

```bash
python -m streamlit run app.py
```

Open the local URL printed in your terminal, usually `http://localhost:8501`.

## How to demo

1. Show the account and transfer counts.
2. Investigate an account such as `A101`.
3. Review its chronological transaction paths and evidence summary.
4. Explore the transaction network.
5. Compare two accounts in the Intervention Simulator.
6. Expand the affected-path sections and explain the difference between the scenarios.

## Graph model

- `(:Account {account_id})` represents an account.
- `(:Account)-[:TRANSFER {transaction_id, amount, timestamp}]->(:Account)` represents a transaction between accounts.

The prototype examines directed paths of two to four transfers for intervention comparisons and checks timestamp ordering.

## Limitations and responsible use

Graph connectivity and chronological paths are investigative leads, not proof of fraud. The intervention simulator counts graph paths that would disappear under a hypothetical account exclusion; it does not estimate recovered funds, financial losses, or real-world outcomes.

The current prototype uses synthetic data and rule-based graph queries. It does not make real account-blocking decisions.

## AI assistance disclosure

Disclose the AI tools used during development and describe which parts were AI-assisted, in accordance with the hackathon rules. Verify and understand the submitted code before presenting it.

## Project status

Hackathon prototype — under active development.
