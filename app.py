
import streamlit as st
from collections import Counter
from falkordb import FalkorDB
from src.csv_loader import parse_transactions, load_transactions_into_graph
from streamlit_agraph import agraph, Node, Edge, Config
from src.risk_score import calculate_risk_scores

st.set_page_config(
    page_title="GraphSleuth",
    layout="wide",
)

st.title(" GraphSleuth")
st.caption("Graph-powered fraud investigation | Synthetic demo data")
st.header("Upload Transaction Data")

st.caption(
    "Upload a CSV to replace the current graph and analyze its transaction network."
)

uploaded_file = st.file_uploader(
    "Choose a transaction CSV",
    type=["csv"],
    help=(
        "Required columns: transaction_id, source_account, "
        "target_account, amount, timestamp"
    ),
)

if uploaded_file is not None:
    if st.button("Load CSV and Analyze", type="primary"):
        try:
            transactions = parse_transactions(uploaded_file.getvalue())

            db = FalkorDB(host="localhost", port=6379)
            graph = db.select_graph("graphsleuth")

            load_transactions_into_graph(graph, transactions)

            st.session_state["csv_loaded_this_session"] = True
            st.session_state["show_agent_results"] = False
            st.session_state["agent_focus_account"] = None
            st.session_state["run_recommended_investigation"] = False
            st.session_state.pop("investigation_account", None)

            st.success(
                f"Loaded {len(transactions)} transactions into FalkorDB."
            )
            st.rerun()

        except ValueError as exc:
            st.error(f"CSV validation failed: {exc}")
        except Exception as exc:
            st.error(
                "Could not load the CSV. Check that FalkorDB is running. "
                f"Details: {exc}"
            )
if "csv_loaded_this_session" not in st.session_state:
    st.session_state["csv_loaded_this_session"] = False
@st.cache_resource
def get_graph():
    db = FalkorDB(host="localhost", port=6379)
    return db.select_graph("graphsleuth")


# Preserve agent results across Streamlit reruns.
if "show_agent_results" not in st.session_state:
    st.session_state["show_agent_results"] = False

if "agent_focus_account" not in st.session_state:
    st.session_state["agent_focus_account"] = None

if "run_recommended_investigation" not in st.session_state:
    st.session_state["run_recommended_investigation"] = False


def get_chronological_paths(graph, min_hops=2, max_hops=4):
    """Find chronological multi-hop transaction paths."""
    result = graph.query(
        f"""
        MATCH p = (source:Account)-[:TRANSFER*{min_hops}..{max_hops}]->
                  (destination:Account)
        WITH p, [r IN relationships(p) | r.timestamp] AS times
        WHERE ALL(
            i IN range(0, size(times) - 2)
            WHERE times[i] <= times[i + 1]
        )
        RETURN [n IN nodes(p) | n.account_id] AS accounts,
               [r IN relationships(p) | r.amount] AS amounts,
               times,
               length(p) AS hops
        ORDER BY hops DESC
        LIMIT 20
        """
    )
    return result.result_set


def count_paths(graph, blocked_account=None):
    """Count chronological paths, optionally excluding an account."""
    query = """
        MATCH p = (s:Account)-[:TRANSFER*2..4]->(d:Account)
        WITH p, [r IN relationships(p) | r.timestamp] AS times
        WHERE ALL(
            i IN range(0, size(times) - 2)
            WHERE times[i] <= times[i + 1]
        )
    """
    params = {}

    if blocked_account is not None:
        query += """
            AND NONE(
                n IN nodes(p)
                WHERE n.account_id = $blocked
            )
        """
        params["blocked"] = blocked_account

    query += " RETURN count(p) AS total"
    result = graph.query(query, params)
    return result.result_set[0][0]


def get_affected_paths(graph, blocked_account):
    """Return chronological paths that contain an account."""
    result = graph.query(
        """
        MATCH p = (s:Account)-[:TRANSFER*2..4]->(d:Account)
        WITH p, [r IN relationships(p) | r.timestamp] AS times
        WHERE ALL(
            i IN range(0, size(times) - 2)
            WHERE times[i] <= times[i + 1]
        )
        AND ANY(
            n IN nodes(p)
            WHERE n.account_id = $blocked
        )
        RETURN [n IN nodes(p) | n.account_id] AS accounts
        LIMIT 20
        """,
        {"blocked": blocked_account},
    )
    return result.result_set


def render_account_investigation(graph, account):
    """Show paths, evidence and the transaction network."""
    paths = graph.query(
        """
        MATCH p = (start:Account {account_id: $account})
                   -[:TRANSFER*1..4]->(destination:Account)
        WITH p, [r IN relationships(p) | r.timestamp] AS times
        WHERE ALL(
            i IN range(0, size(times) - 2)
            WHERE times[i] <= times[i + 1]
        )
        RETURN [n IN nodes(p) | n.account_id] AS accounts,
               [r IN relationships(p) | r.amount] AS amounts,
               times,
               length(p) AS hops
        ORDER BY hops ASC
        LIMIT 20
        """,
        {"account": account},
    ).result_set

    st.subheader(f"Investigation results: {account}")

    if not paths:
        st.info("No chronological outgoing paths found for this account.")
    else:
        for row in paths:
            accounts, amounts, times, hops = row

            with st.container(border=True):
                st.markdown(" → ".join(accounts))

                col1, col2 = st.columns(2)
                col1.metric("Hops", hops)
                col2.metric(
                    "Sum of transfer amounts",
                    f"{sum(amounts):,.2f}",
                )

                st.caption("Transfers along this path")
                for i, amount in enumerate(amounts):
                    st.write(
                        f"**{accounts[i]} → {accounts[i + 1]}**"
                        f" · Amount: {amount:,.2f}"
                        f" · Time: {times[i]}"
                    )

        st.subheader("Evidence summary")
        st.write(f"- Chronological paths shown: **{len(paths)}**.")
        st.write(
            f"- Longest returned path: **{max(row[3] for row in paths)} hops**."
        )
        unique_accounts = {
            account_id for row in paths for account_id in row[0]
        }
        st.write(
            f"- Accounts appearing in these paths: **{len(unique_accounts)}**."
        )

    st.caption(
        "Graph connectivity and timing are investigation leads, "
        "not proof of fraud."
    )

    st.subheader("Transaction network")

    graph_data = graph.query(
        """
        MATCH (a:Account)-[t:TRANSFER]->(b:Account)
        RETURN a.account_id AS source,
               b.account_id AS target,
               t.transaction_id AS transaction_id,
               t.amount AS amount
        """
    )

    nodes_by_id = {}
    edges = []

    # Highlight edges belonging to paths affected by the simulated block.
    simulated_block_account = st.session_state.get("simulated_block_account")
    disrupted_edges = set()
    if simulated_block_account:
        for path_row in get_affected_paths(graph, simulated_block_account):
            accounts_in_path = path_row[0]
            disrupted_edges.update(
                (accounts_in_path[i], accounts_in_path[i + 1])
                for i in range(len(accounts_in_path) - 1)
            )

    for source, target, tx_id, amount in graph_data.result_set:
        for account_id in (source, target):
            if account_id not in nodes_by_id:
                nodes_by_id[account_id] = Node(
                    id=account_id,
                    label=account_id,
                    size=25,
                    color="#3B82F6",
                )

        edge_color = (
            "#EF4444"
            if simulated_block_account and (source, target) in disrupted_edges
            else "#9CA3AF"
        )
        edges.append(
            Edge(
                source=source,
                target=target,
                label=f"{tx_id}: {amount:g}",
                title=f"Transaction amount: {amount:g}",
                width=4 if amount > 90000 else 1,
                color=edge_color,
                directed=True,
            )
        )

    agraph(
        nodes=list(nodes_by_id.values()),
        edges=edges,
        config=Config(
            width=900,
            height=550,
            directed=True,
            physics=True,
            hierarchical=False,
        ),
    )


if not st.session_state["csv_loaded_this_session"]:
    st.info(
        "Upload a transaction CSV and click "
        "'Load CSV and Analyze' to begin your investigation."
    )
    st.stop()

try:
    # Connect only after a CSV has been loaded in this session.
    graph = get_graph()
    # Dashboard summary
    summary = graph.query(
        """
        MATCH (a:Account)
        WITH count(a) AS accounts
        MATCH ()-[t:TRANSFER]->()
        RETURN accounts, count(t) AS transfers
        """
    ).result_set[0]

    col1, col2 = st.columns(2)
    col1.metric("Accounts", summary[0])
    col2.metric("Transfers", summary[1])


    # Explainable risk ranking
    st.divider()
    st.subheader("Explainable Account Risk Ranking")
    st.caption(
        "Transparent heuristic scores based on graph evidence. "
        "Scores are not fraud probabilities or proof of wrongdoing."
    )

    with st.spinner("Calculating account risk scores..."):
        risk_results = calculate_risk_scores(graph)

    if risk_results:
        risk_table = [
            {
                "Account": item["account"],
                "Risk score": f'{item["score"]}/100',
                "Evidence": (
                    " · ".join(
                        reason.replace(
                            "Appears in many multi-hop paths", "Flow-through"
                        )
                        .replace(
                            "Receives and forwards funds", "Flow-through"
                        )
                        .replace(
                            "Large outgoing transfer total", "High out-flow"
                        )
                        .replace(
                            "High transaction activity", "High activity"
                        )
                        for reason in item["reasons"]
                    )
                    if item["reasons"]
                    else "No indicators"
                ),
            }
            for item in risk_results
        ]

        st.dataframe(
            risk_table,
            use_container_width=True,
            hide_index=True,
            height=min(420, 38 + 36 * len(risk_table)),
            column_config={
                "Account": st.column_config.TextColumn(
                    "Account",
                    width="small",
                ),
                "Risk score": st.column_config.TextColumn(
                    "Risk score",
                    width="small",
                ),
                "Evidence": st.column_config.TextColumn(
                    "Evidence",
                    width="large",
                ),
            },
        )

        with st.expander("View full risk-score explanations"):
            for item in risk_results:
                st.markdown(
                    f"**{item['account']} — {item['score']}/100**"
                )

                if item["reasons"]:
                    for reason in item["reasons"]:
                        st.write(f"- {reason}")
                else:
                    st.write("- No elevated graph indicators")

                st.caption(
                    f"Incoming: {item['incoming_total']:,.2f} · "
                    f"Outgoing: {item['outgoing_total']:,.2f} · "
                    f"Candidate paths: {item['candidate_paths']}"
                )
    else:
        st.info("No accounts are available to score.")


    account_rows = graph.query(
        """
        MATCH (a:Account)
        RETURN a.account_id AS account
        ORDER BY account
        """
    ).result_set

    account_ids = [row[0] for row in account_rows]

    if not account_ids:
        st.warning("No accounts found. Load the synthetic dataset first.")
        st.stop()

    # Intervention simulator
    st.divider()
    st.subheader("Intervention Simulator")
    st.write(
        "Simulate blocking an account to see affected transaction paths."
    )

    simulation_account = st.selectbox(
        "Account to simulate blocking",
        options=account_ids,
        key="simulation_account",
    )

    alternatives = [
        account for account in account_ids
        if account != simulation_account
    ]
    default_alternative = (
        "A301" if "A301" in alternatives else alternatives[0]
    )

    alternative_account = st.selectbox(
        "Compare with blocking another account",
        options=alternatives,
        index=alternatives.index(default_alternative),
        key="alternative_account",
    )

    if st.button("Simulate intervention", type="primary"):
        st.session_state["simulated_block_account"] = simulation_account
        baseline = count_paths(graph)
        results = []

        for account in (simulation_account, alternative_account):
            remaining = count_paths(graph, account)
            results.append({
                "Account blocked": account,
                "Paths before": baseline,
                "Paths remaining": remaining,
                "Paths disrupted": baseline - remaining,
            })

        st.subheader("Simulation results")
        st.dataframe(results, use_container_width=True)

        st.subheader("Paths affected by each intervention")
        for account in (simulation_account, alternative_account):
            affected = get_affected_paths(graph, account)
            with st.expander(
                f"Paths involving {account} ({len(affected)} shown)"
            ):
                if not affected:
                    st.write("No affected chronological paths found.")
                else:
                    for path_row in affected:
                        st.write(" → ".join(path_row[0]))

        best = max(results, key=lambda item: item["Paths disrupted"])
        st.subheader("Intervention analysis")
        st.success(
            f"Highest path disruption in this comparison: "
            f"{best['Account blocked']} "
            f"({best['Paths disrupted']} paths disrupted)"
        )
        st.write(
            f"**{best['Account blocked']}** disrupts "
            f"{best['Paths disrupted']} of {best['Paths before']} "
            "chronological paths in this comparison."
        )
        st.caption(
            "A disrupted path is one that would no longer exist if the "
            "account were excluded. It does not measure money recovered or lost."
        )
        st.info(
            "Simulation only: no graph data is changed. Graph connectivity "
            "is an investigative signal, not proof of fraud."
        )

    # Agent investigation
    st.divider()
    st.subheader("Agent Investigation")
    st.write(
        "Discover transaction flows, rank accounts for follow-up, "
        "and review the evidence behind the recommendation."
    )

    if st.button(
        "Run Agent Investigation",
        type="primary",
        key="run_agent_investigation",
    ):
        st.session_state["show_agent_results"] = True
        st.session_state["agent_focus_account"] = None

    if st.session_state["show_agent_results"]:
        with st.spinner("Investigating transaction flows..."):
            candidate_paths = get_chronological_paths(graph)

        st.subheader("Agent Findings")

        if not candidate_paths:
            st.info("No chronological multi-hop paths found.")
        else:
            intermediate_frequency = Counter()
            for accounts, amounts, times, hops in candidate_paths:
                intermediate_frequency.update(accounts[1:-1])

            if not intermediate_frequency:
                st.info(
                    "Paths were found, but none had an intermediate account "
                    "to prioritize."
                )
            else:
                ranked_accounts = intermediate_frequency.most_common(3)
                focus_account, appearances = ranked_accounts[0]
                st.session_state["agent_focus_account"] = focus_account

                st.caption(
                    f"Ranking based on {len(candidate_paths)} chronological "
                    "candidate paths (maximum 20 returned)."
                )

                st.subheader("Accounts worth reviewing")
                for rank, (account, count) in enumerate(
                    ranked_accounts, start=1
                ):
                    st.write(
                        f"**{rank}. {account}** — intermediate in "
                        f"{count} candidate paths."
                    )
                st.caption(
                    "This ranking reflects repeated involvement in paths, "
                    "not a fraud probability."
                )

                st.metric("Candidate paths examined", len(candidate_paths))
                st.write(
                    f"**Why {focus_account}?** It appears as an intermediate "
                    f"account in {appearances} candidate paths."
                )

                with st.expander("View candidate transaction paths"):
                    for accounts, amounts, times, hops in candidate_paths:
                        st.write(" → ".join(accounts))
                        st.caption(f"{hops} hops · Amounts: {amounts}")

                incoming_result = graph.query(
                    """
                    MATCH (:Account)-[t:TRANSFER]->(
                        a:Account {account_id: $account}
                    )
                    RETURN coalesce(sum(t.amount), 0)
                    """,
                    {"account": focus_account},
                )
                incoming_total = incoming_result.result_set[0][0] or 0

                outgoing_result = graph.query(
                    """
                    MATCH (a:Account {account_id: $account})
                          -[t:TRANSFER]->(:Account)
                    RETURN coalesce(sum(t.amount), 0)
                    """,
                    {"account": focus_account},
                )
                outgoing_total = outgoing_result.result_set[0][0] or 0

                col1, col2, col3 = st.columns(3)
                col1.metric("Incoming total", f"{incoming_total:,.2f}")
                col2.metric("Outgoing total", f"{outgoing_total:,.2f}")
                col3.metric(
                    "Outgoing − incoming",
                    f"{outgoing_total - incoming_total:,.2f}",
                )

                st.write("**Connected transfers**")
                connected = graph.query(
                    """
                    MATCH (source:Account)-[t:TRANSFER]->(target:Account)
                    WHERE source.account_id = $account
                       OR target.account_id = $account
                    RETURN source.account_id,
                           target.account_id,
                           t.amount,
                           t.timestamp,
                           t.transaction_id
                    ORDER BY t.timestamp
                    """,
                    {"account": focus_account},
                )

                for source, target, amount, timestamp, tx_id in (
                    connected.result_set
                ):
                    st.write(
                        f"{source} → {target} | {amount:,.2f} | "
                        f"{timestamp} | {tx_id}"
                    )

                if st.button(
                    f"Investigate recommended account: {focus_account}",
                    key="investigate_recommended_account",
                ):
                    st.session_state["investigation_account"] = focus_account
                    st.session_state["run_recommended_investigation"] = True
                    st.rerun()

                st.warning(
                    "These are investigation leads, not proof of fraud. "
                    "Review the evidence before making any decision."
                )

    # Account investigation
    st.divider()
    st.subheader("Investigate an account")

    default_selected = st.session_state.get(
        "investigation_account",
        account_ids[0],
    )
    if default_selected not in account_ids:
        default_selected = account_ids[0]

    selected = st.selectbox(
        "Choose an account to investigate",
        options=account_ids,
        index=account_ids.index(default_selected),
        key="investigation_account",
    )

    manual_investigation = st.button("Investigate", type="primary")
    recommended_investigation = st.session_state.pop(
        "run_recommended_investigation",
        False,
    )

    if manual_investigation or recommended_investigation:
        render_account_investigation(graph, selected)

except Exception as exc:
    st.error(f"Could not query FalkorDB: {exc}")
    st.caption(
        "Check that the graphsleuth-db Docker container is running "
        "and that the risk-scoring module is available."
    )
