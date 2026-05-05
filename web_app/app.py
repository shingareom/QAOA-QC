import os
import sys
import io
import base64
import random
import networkx as nx
import matplotlib
matplotlib.use('Agg') # Ensure no display issues
import matplotlib.pyplot as plt

from flask import Flask, render_template, request, jsonify

# Add parent directory to path to import qaoa_social_network
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import qaoa_social_network as qsn

app = Flask(__name__)

def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches="tight")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return encoded

def generate_random_network(num_nodes, edge_prob=0.4):
    G = nx.erdos_renyi_graph(n=num_nodes, p=edge_prob, seed=None)
    # Ensure graph is connected, if not add edges
    if not nx.is_connected(G):
        components = list(nx.connected_components(G))
        for i in range(len(components)-1):
            u = list(components[i])[0]
            v = list(components[i+1])[0]
            G.add_edge(u, v)
    
    users = {}
    names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Heidi", "Ivan", "Judy", "Mallory", "Niaj", "Olivia", "Peggy", "Sybil"]
    for i in G.nodes():
        name = names[i] if i < len(names) else f"User{i}"
        users[i] = name
        G.nodes[i]['name'] = name
        
    for u, v in G.edges():
        G[u][v]['weight'] = round(random.uniform(0.5, 3.0), 1)
        
    return G, users

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run_simulation', methods=['POST'])
def run_simulation():
    data = request.json
    num_nodes = int(data.get('num_nodes', 5))
    p_layers = int(data.get('p_layers', 1))
    
    if not (3 <= num_nodes <= 15):
        return jsonify({"error": "Number of nodes must be between 3 and 15"}), 400
        
    G, users = generate_random_network(num_nodes)
    
    # Run QAOA
    best_bs, best_cut, counts, history, qc = qsn.run_qaoa(
        G, p=p_layers, shots=1024, max_iter=100, verbose=False
    )
    
    # Generate figures
    fig_graph = qsn.plot_social_network(G, best_bs, users, title_suffix="")
    fig_prob = qsn.plot_probability_distribution(counts, G, 1024, 10, title_suffix="")
    fig_circ = qsn.plot_circuit(qc, title_suffix="")
    fig_conv = qsn.plot_convergence(history, title_suffix="")
    
    img_graph = fig_to_base64(fig_graph)
    img_prob = fig_to_base64(fig_prob)
    img_circ = fig_to_base64(fig_circ)
    img_conv = fig_to_base64(fig_conv)
    
    group_a = [users[i] for i, b in enumerate(best_bs) if b == "0"]
    group_b = [users[i] for i, b in enumerate(best_bs) if b == "1"]
    
    return jsonify({
        "best_bitstring": best_bs,
        "best_cut": best_cut,
        "group_a": group_a,
        "group_b": group_b,
        "images": {
            "graph": img_graph,
            "probability": img_prob,
            "circuit": img_circ,
            "convergence": img_conv
        }
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
