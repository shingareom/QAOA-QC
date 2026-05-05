import os
import sys
import io
import base64
import random
import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from flask import Flask, render_template, request, jsonify

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import qaoa_social_network as qsn

app = Flask(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches="tight")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return encoded


def generate_random_network(num_nodes, edge_prob=0.4):
    G = nx.erdos_renyi_graph(n=num_nodes, p=edge_prob)
    if not nx.is_connected(G):
        components = list(nx.connected_components(G))
        for i in range(len(components) - 1):
            u = list(components[i])[0]
            v = list(components[i + 1])[0]
            G.add_edge(u, v)

    names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace",
             "Heidi", "Ivan", "Judy", "Mallory", "Niaj", "Olivia", "Peggy", "Sybil"]
    users = {}
    rng = random.Random()
    for i in G.nodes():
        name = names[i] if i < len(names) else f"User{i}"
        users[i] = name
        G.nodes[i]['name'] = name
    for u, v in G.edges():
        G[u][v]['weight'] = round(rng.uniform(0.5, 3.0), 1)
    return G, users


def parse_custom_network(text):
    """Parse a network.txt-style text block from the frontend textarea."""
    section = None
    name_to_idx = {}
    users = {}
    edges_raw = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.upper() == '[NODES]':
            section = 'nodes'
            continue
        if line.upper() == '[EDGES]':
            section = 'edges'
            continue

        if section == 'nodes':
            name = line.split()[0]
            idx = len(name_to_idx)
            name_to_idx[name] = idx
            users[idx] = name
        elif section == 'edges':
            parts = line.split()
            if len(parts) < 2:
                continue
            node_a, node_b = parts[0], parts[1]
            weight = float(parts[2]) if len(parts) >= 3 else 1.0
            if node_a in name_to_idx and node_b in name_to_idx:
                edges_raw.append((name_to_idx[node_a], name_to_idx[node_b], weight))

    if not users:
        raise ValueError("No nodes found. Add a [NODES] section.")
    if not edges_raw:
        raise ValueError("No edges found. Add an [EDGES] section.")
    if not (3 <= len(users) <= 15):
        raise ValueError(f"Node count must be 3–15 (got {len(users)}).")

    G = nx.Graph()
    for idx, name in users.items():
        G.add_node(idx, name=name)
    for u, v, w in edges_raw:
        G.add_edge(u, v, weight=w)
    return G, users


def build_graph_json(G, best_bitstring, users):
    nodes = [
        {"id": n, "name": users.get(n, str(n)), "group": int(best_bitstring[n])}
        for n in G.nodes()
    ]
    edges = [
        {
            "source":  u,
            "target":  v,
            "weight":  round(data.get("weight", 1.0), 1),
            "is_cut":  best_bitstring[u] != best_bitstring[v],
        }
        for u, v, data in G.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


def build_counts_json(counts, G, shots, top_k):
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [
        {
            "bitstring":   bs,
            "probability": round(cnt / shots, 4),
            "cut_value":   qsn.compute_maxcut_value(bs, G),
        }
        for bs, cnt in sorted_counts
    ]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run_simulation', methods=['POST'])
def run_simulation():
    data = request.get_json(force=True)
    if data is None:
        return jsonify({"error": "Invalid JSON body"}), 400

    try:
        num_nodes    = int(data.get('num_nodes', 6))
        p_layers     = int(data.get('p_layers', 1))
        shots        = int(data.get('shots', 1024))
        max_iter     = int(data.get('max_iter', 100))
        top_k        = int(data.get('top_k', 10))
        network_mode = str(data.get('network_mode', 'random'))
        custom_text  = str(data.get('custom_network', ''))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid parameter types"}), 400

    if not (3 <= num_nodes <= 15):
        return jsonify({"error": "Number of nodes must be between 3 and 15"}), 400
    if not (1 <= p_layers <= 3):
        return jsonify({"error": "QAOA layers must be 1, 2, or 3"}), 400
    if shots not in (512, 1024, 2048, 4096):
        return jsonify({"error": "Shots must be 512, 1024, 2048, or 4096"}), 400
    if not (50 <= max_iter <= 300):
        return jsonify({"error": "max_iter must be between 50 and 300"}), 400
    if not (5 <= top_k <= 16):
        return jsonify({"error": "top_k must be between 5 and 16"}), 400

    try:
        if network_mode == 'custom' and custom_text.strip():
            G, users = parse_custom_network(custom_text)
        else:
            G, users = generate_random_network(num_nodes)

        best_bs, best_cut, counts, history, qc = qsn.run_qaoa(
            G, p=p_layers, shots=shots, max_iter=max_iter, verbose=False
        )

        fig_circ    = qsn.plot_circuit(qc, title_suffix="")
        circuit_img = fig_to_base64(fig_circ)

        return jsonify({
            "best_bitstring": best_bs,
            "best_cut":       best_cut,
            "group_a":        [users[i] for i, b in enumerate(best_bs) if b == "0"],
            "group_b":        [users[i] for i, b in enumerate(best_bs) if b == "1"],
            "graph_data":     build_graph_json(G, best_bs, users),
            "counts_data":    build_counts_json(counts, G, shots, top_k),
            "history":        history,
            "circuit_img":    circuit_img,
            "meta": {
                "nodes":      G.number_of_nodes(),
                "edges":      G.number_of_edges(),
                "p":          p_layers,
                "shots":      shots,
                "iterations": len(history),
            },
        })

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Simulation error: {str(exc)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
