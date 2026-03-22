"""
============================================================
  QAOA for Social Media Network Analysis (Max-Cut Problem)
  Implemented using Qiskit
============================================================
  Authors : Rohit Rao, Viraj Nalbalwar, Shreesh Kolhatkar, Om Shingare
  Purpose : Partition a social network into influencers vs followers
            by solving Max-Cut via the Quantum Approximate
            Optimization Algorithm (QAOA).
============================================================
"""

# ── Standard library ──────────────────────────────────────
import warnings
warnings.filterwarnings("ignore")
import os

# ── Third-party ───────────────────────────────────────────
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

# ── Qiskit ────────────────────────────────────────────────
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter, ParameterVector
from qiskit_aer import AerSimulator
from scipy.optimize import minimize

# ══════════════════════════════════════════════════════════
#  1.  CONFIG FILE LOADERS
# ══════════════════════════════════════════════════════════

def load_network(filepath: str = "network.txt"):
    """
    Parse network.txt and return a NetworkX graph + users dict.

    File format:
        [NODES]
        Alice
        Bob
        ...

        [EDGES]
        Alice  Bob  3
        ...
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"  ✗ Could not find '{filepath}'.\n"
            f"    Make sure it is in the same folder as this script."
        )

    section = None
    name_to_idx = {}
    users       = {}
    edges       = []

    with open(filepath, "r") as f:
        for raw_line in f:
            line = raw_line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            # Section headers
            if line.upper() == "[NODES]":
                section = "nodes"
                continue
            if line.upper() == "[EDGES]":
                section = "edges"
                continue

            if section == "nodes":
                name = line.split()[0]          # first token only (safety)
                idx  = len(name_to_idx)
                name_to_idx[name] = idx
                users[idx]        = name

            elif section == "edges":
                parts = line.split()
                if len(parts) < 2:
                    print(f"  ⚠ Skipping malformed edge line: '{line}'")
                    continue
                node_a = parts[0]
                node_b = parts[1]
                weight = float(parts[2]) if len(parts) >= 3 else 1.0

                if node_a not in name_to_idx:
                    raise ValueError(f"  ✗ Edge references unknown node '{node_a}' in: '{line}'")
                if node_b not in name_to_idx:
                    raise ValueError(f"  ✗ Edge references unknown node '{node_b}' in: '{line}'")

                edges.append((name_to_idx[node_a], name_to_idx[node_b], weight))

    if not users:
        raise ValueError(f"  ✗ No nodes found in '{filepath}'. Check your [NODES] section.")
    if not edges:
        raise ValueError(f"  ✗ No edges found in '{filepath}'. Check your [EDGES] section.")

    G = nx.Graph()
    for idx, name in users.items():
        G.add_node(idx, name=name)
    for u, v, w in edges:
        G.add_edge(u, v, weight=w)

    print(f"  Loaded network from '{filepath}'")
    print(f"  → {len(users)} nodes : {', '.join(users.values())}")
    print(f"  → {len(edges)} edges")
    return G, users


def load_settings(filepath: str = "settings.txt") -> dict:
    """
    Parse settings.txt and return a dict of typed config values.

    File format:
        key = value   (# comments and blank lines are ignored)
    """
    defaults = {
        "p":            1,
        "shots":        2048,
        "top_k":        10,
        "max_iter":     200,
        "save_figures": True,
    }

    if not os.path.exists(filepath):
        print(f"  ⚠ '{filepath}' not found — using default settings.")
        return defaults

    settings = defaults.copy()
    type_map = {
        "p":            int,
        "shots":        int,
        "top_k":        int,
        "max_iter":     int,
        "save_figures": lambda v: v.strip().lower() == "true",
    }

    with open(filepath, "r") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip().lower()
            val = val.strip()
            if key in type_map:
                try:
                    settings[key] = type_map[key](val)
                except Exception:
                    print(f"  ⚠ Could not parse setting '{key} = {val}' — using default.")
            else:
                print(f"  ⚠ Unknown setting '{key}' — ignored.")

    print(f"  Loaded settings from '{filepath}'")
    print(f"  → p={settings['p']}  shots={settings['shots']}  "
          f"top_k={settings['top_k']}  max_iter={settings['max_iter']}  "
          f"save_figures={settings['save_figures']}")
    return settings


def build_social_network(network_file: str = "network.txt"):
    """Load the social network from a .txt file."""
    return load_network(network_file)


# ══════════════════════════════════════════════════════════
#  2.  COST-FUNCTION HELPERS
# ══════════════════════════════════════════════════════════

def compute_maxcut_value(bitstring: str, G: nx.Graph) -> float:
    """
    Evaluate the (weighted) Max-Cut value for a given bitstring assignment.
    bitstring[i] ∈ {'0','1'}  →  0 = Group A, 1 = Group B
    An edge (i,j) is *cut* when bitstring[i] ≠ bitstring[j].
    """
    cut = 0.0
    for u, v, data in G.edges(data=True):
        w = data.get("weight", 1)
        if bitstring[u] != bitstring[v]:
            cut += w
    return cut


def expectation_from_counts(counts: dict, G: nx.Graph, shots: int) -> float:
    """
    Compute the expected Max-Cut value from a measurement counts dict.
    We *minimise* –⟨C⟩, so return the negative expectation.
    """
    exp_val = 0.0
    for bitstring, count in counts.items():
        cut = compute_maxcut_value(bitstring, G)
        exp_val += cut * (count / shots)
    return -exp_val          # negative because scipy minimises


# ══════════════════════════════════════════════════════════
#  3.  QAOA CIRCUIT BUILDER
# ══════════════════════════════════════════════════════════

def build_qaoa_circuit(G: nx.Graph, p: int) -> QuantumCircuit:
    """
    Construct the QAOA circuit for Max-Cut with p alternating layers.

    Parameters
    ----------
    G : networkx.Graph   — the social network
    p : int              — number of QAOA layers (depth)

    Returns
    -------
    QuantumCircuit with symbolic Parameters γ₀…γₚ₋₁, β₀…βₚ₋₁
    """
    n = G.number_of_nodes()
    gamma = ParameterVector("γ", p)
    beta  = ParameterVector("β", p)

    qc = QuantumCircuit(n)

    # ── Initial state: equal superposition ────────────────
    qc.h(range(n))
    qc.barrier(label="init")

    # ── p alternating Cost + Mixer layers ─────────────────
    for layer in range(p):
        # Cost unitary  U_C(γ)
        qc.barrier(label=f"cost L{layer+1}")
        for u, v, data in G.edges(data=True):
            w = data.get("weight", 1)
            # e^{-i γ w (1–ZᵢZⱼ)/2}  ≡  Rzz(γ·w) up to global phase
            qc.rzz(2 * gamma[layer] * w, u, v)

        # Mixer unitary  U_B(β)
        qc.barrier(label=f"mix L{layer+1}")
        for qubit in range(n):
            qc.rx(2 * beta[layer], qubit)

    qc.barrier(label="measure")
    qc.measure_all()
    return qc


# ══════════════════════════════════════════════════════════
#  4.  CLASSICAL OPTIMISER LOOP
# ══════════════════════════════════════════════════════════

def run_qaoa(G: nx.Graph, p: int = 1, shots: int = 2048,
             max_iter: int = 200, verbose: bool = True):
    """
    Execute the full QAOA hybrid loop.

    Returns
    -------
    best_bitstring : str   — the highest-probability Max-Cut partition
    best_cut       : float — its cut value
    final_counts   : dict  — measurement counts at optimal γ,β
    cost_history   : list  — –⟨C⟩ values per optimiser iteration
    qc             : QuantumCircuit (un-bound, for visualisation)
    """
    simulator = AerSimulator()
    qc        = build_qaoa_circuit(G, p)
    n         = G.number_of_nodes()
    cost_history = []

    # ── Objective function passed to COBYLA ───────────────
    def objective(params):
        gamma_vals = params[:p]
        beta_vals  = params[p:]

        # Bind symbolic parameters
        param_dict = {}
        for i in range(p):
            param_dict[qc.parameters[i]]   = gamma_vals[i]   # γ params come first
            param_dict[qc.parameters[p+i]] = beta_vals[i]    # β params after

        bound_qc  = qc.assign_parameters(param_dict)
        job       = simulator.run(bound_qc, shots=shots)
        counts    = job.result().get_counts()
        cost      = expectation_from_counts(counts, G, shots)
        cost_history.append(-cost)                 # store positive ⟨C⟩
        return cost

    # ── Random initialisation ─────────────────────────────
    rng    = np.random.default_rng(42)
    x0     = rng.uniform(0, np.pi, 2 * p)

    if verbose:
        print(f"\n{'─'*55}")
        print(f"  QAOA Social Network Analysis  |  p={p}  shots={shots}")
        print(f"{'─'*55}")
        print(f"  Nodes : {n}   Edges : {G.number_of_edges()}")
        print(f"  Optimising γ,β with COBYLA …")

    result = minimize(
        objective,
        x0,
        method="COBYLA",
        options={"maxiter": max_iter, "rhobeg": 0.5},
    )

    # ── Final measurement at optimal parameters ────────────
    opt_params  = result.x
    param_dict  = {}
    for i in range(p):
        param_dict[qc.parameters[i]]   = opt_params[i]
        param_dict[qc.parameters[p+i]] = opt_params[p+i]

    bound_qc    = qc.assign_parameters(param_dict)
    job         = simulator.run(bound_qc, shots=shots)
    final_counts = job.result().get_counts()

    # ── Extract best bit string ────────────────────────────
    best_bitstring = max(final_counts, key=lambda s: compute_maxcut_value(s, G))
    best_cut       = compute_maxcut_value(best_bitstring, G)

    if verbose:
        print(f"  Optimal γ : {[f'{v:.4f}' for v in opt_params[:p]]}")
        print(f"  Optimal β : {[f'{v:.4f}' for v in opt_params[p:]]}")
        print(f"\n  Best bitstring : {best_bitstring}")
        print(f"  Max-Cut value  : {best_cut:.1f}")

        # Show group assignments
        users = nx.get_node_attributes(G, "name")
        groupA = [users.get(i, str(i)) for i, b in enumerate(best_bitstring) if b == "0"]
        groupB = [users.get(i, str(i)) for i, b in enumerate(best_bitstring) if b == "1"]
        print(f"\n  Group A (Influencers) : {', '.join(groupA)}")
        print(f"  Group B (Followers)   : {', '.join(groupB)}")
        print(f"{'─'*55}\n")

    return best_bitstring, best_cut, final_counts, cost_history, qc


# ══════════════════════════════════════════════════════════
#  5.  VISUALISATIONS
# ══════════════════════════════════════════════════════════

# ── Colour palette ────────────────────────────────────────
COL_A       = "#4FC3F7"   # sky-blue   → Group A (Influencers)
COL_B       = "#EF9A9A"   # soft-red   → Group B (Followers)
COL_CUT     = "#FFD54F"   # amber      → cut edges
COL_UNCUT   = "#B0BEC5"   # steel-grey → non-cut edges
BG          = "#0F1117"   # near-black background
FG          = "#E8EAF6"   # off-white text


def _apply_dark_style():
    plt.rcParams.update({
        "figure.facecolor": BG,
        "axes.facecolor":   BG,
        "text.color":       FG,
        "axes.labelcolor":  FG,
        "xtick.color":      FG,
        "ytick.color":      FG,
        "axes.edgecolor":   "#2C2C3C",
        "grid.color":       "#2C2C3C",
        "font.family":      "monospace",
    })


# ── 5A. Social Network Graph ──────────────────────────────

def plot_social_network(G: nx.Graph, best_bitstring: str,
                        users: dict, title_suffix: str = ""):
    """
    Draw the social network coloured by Max-Cut group assignment.
    Cut edges are highlighted in amber; non-cut edges in grey.
    """
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(9, 7), facecolor=BG)
    ax.set_facecolor(BG)

    pos = nx.spring_layout(G, seed=7, k=1.8)

    node_colors = [COL_A if best_bitstring[n] == "0" else COL_B
                   for n in G.nodes()]

    cut_edges    = [(u, v) for u, v in G.edges()
                    if best_bitstring[u] != best_bitstring[v]]
    non_cut_edges = [(u, v) for u, v in G.edges()
                     if (u, v) not in cut_edges]

    edge_weights = nx.get_edge_attributes(G, "weight")

    # Draw edges
    nx.draw_networkx_edges(G, pos, edgelist=non_cut_edges,
                           edge_color=COL_UNCUT, width=1.8,
                           alpha=0.6, ax=ax)
    nx.draw_networkx_edges(G, pos, edgelist=cut_edges,
                           edge_color=COL_CUT, width=3.0,
                           style="dashed", ax=ax,
                           arrows=False)

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_color=node_colors,
                           node_size=900, ax=ax,
                           edgecolors="white", linewidths=1.5)

    # Labels: show name + group
    labels = {n: f"{users[n]}\n({'A' if best_bitstring[n]=='0' else 'B'})"
              for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels,
                            font_size=8, font_color="black",
                            font_weight="bold", ax=ax)

    # Edge weight labels
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_weights,
                                 font_color=FG, font_size=8, ax=ax)

    # Legend
    patch_a   = mpatches.Patch(color=COL_A,   label="Group A – Influencers")
    patch_b   = mpatches.Patch(color=COL_B,   label="Group B – Followers")
    patch_cut = mpatches.Patch(color=COL_CUT, label="Cut Edges (maximised)")
    ax.legend(handles=[patch_a, patch_b, patch_cut],
              loc="upper left", facecolor="#1A1A2E",
              edgecolor="#4FC3F7", labelcolor=FG, fontsize=9)

    cut_val = compute_maxcut_value(best_bitstring, G)
    ax.set_title(
        f"Social Media Network — Max-Cut Partition{title_suffix}\n"
        f"Partition: {best_bitstring}   |   Cut Value: {cut_val:.0f}",
        color=FG, fontsize=11, pad=14)
    ax.axis("off")
    plt.tight_layout()
    return fig


# ── 5B. Probability Bar Chart ─────────────────────────────

def plot_probability_distribution(counts: dict, G: nx.Graph,
                                  shots: int, top_k: int = 10,
                                  title_suffix: str = ""):
    """
    Bar chart of the top-k most probable bitstrings.
    Bars are coloured by their Max-Cut value (darker = higher cut).
    """
    _apply_dark_style()

    # Sort by count, take top_k
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:top_k]
    bitstrings    = [x[0] for x in sorted_counts]
    probabilities = [x[1] / shots for x in sorted_counts]
    cut_values    = [compute_maxcut_value(b, G) for b in bitstrings]

    fig, ax = plt.subplots(figsize=(11, 5), facecolor=BG)
    ax.set_facecolor(BG)

    # Colour bars by cut value
    max_cv  = max(cut_values) if cut_values else 1
    colours = [plt.cm.YlOrRd(cv / max_cv) for cv in cut_values]

    bars = ax.bar(range(len(bitstrings)), probabilities,
                  color=colours, edgecolor="#1A1A2E", linewidth=0.8)

    # Annotate bars with cut value
    for i, (bar, cv) in enumerate(zip(bars, cut_values)):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.005,
                f"cut={cv:.0f}", ha="center", va="bottom",
                fontsize=7.5, color=FG)

    ax.set_xticks(range(len(bitstrings)))
    ax.set_xticklabels(bitstrings, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("Probability", color=FG)
    ax.set_xlabel("Bitstring (0=Group A, 1=Group B)", color=FG)
    ax.set_title(
        f"QAOA Measurement Distribution — Top {top_k} Outcomes{title_suffix}",
        color=FG, fontsize=11, pad=12)
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(0, max(probabilities) * 1.18)

    # Colourbar legend
    sm = plt.cm.ScalarMappable(cmap="YlOrRd",
                               norm=plt.Normalize(0, max_cv))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, pad=0.02, fraction=0.03)
    cbar.set_label("Max-Cut Value", color=FG, fontsize=9)
    cbar.ax.yaxis.set_tick_params(color=FG)
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color=FG)

    plt.tight_layout()
    return fig


# ── 5C. QAOA Circuit Diagram ──────────────────────────────

def plot_circuit(qc: QuantumCircuit, title_suffix: str = ""):
    """
    Draw the QAOA circuit using Qiskit's built-in matplotlib drawer.
    """
    fig = qc.draw(output="mpl",
                  style={"backgroundcolor": BG,
                         "textcolor": FG,
                         "gatetextcolor": "#1A1A2E",
                         "subtextcolor": FG,
                         "linecolor": "#4FC3F7",
                         "creglinecolor": "#EF9A9A",
                         "gatefacecolor": "#4FC3F7",
                         "barrierfacecolor": "#2C2C3C"},
                  fold=40, scale=0.75)
    fig.suptitle(f"QAOA Circuit{title_suffix}",
                 color=FG, fontsize=11, y=1.01)
    fig.patch.set_facecolor(BG)
    return fig


# ── 5D. Convergence Curve ─────────────────────────────────

def plot_convergence(cost_history: list, title_suffix: str = ""):
    """Line plot of ⟨C⟩ vs optimiser iteration."""
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG)
    ax.set_facecolor(BG)

    iters = range(1, len(cost_history) + 1)
    ax.plot(iters, cost_history, color=COL_A, linewidth=2.0, label="⟨C⟩")
    ax.fill_between(iters, cost_history, alpha=0.15, color=COL_A)
    ax.axhline(max(cost_history), color=COL_CUT,
               linestyle="--", linewidth=1.2, label=f"Max={max(cost_history):.2f}")

    ax.set_xlabel("Optimiser Iteration", color=FG)
    ax.set_ylabel("Expected Cut Value ⟨C⟩", color=FG)
    ax.set_title(f"COBYLA Convergence{title_suffix}", color=FG, fontsize=11, pad=12)
    ax.legend(facecolor="#1A1A2E", edgecolor=COL_A, labelcolor=FG)
    ax.grid(alpha=0.25)
    plt.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════
#  6.  FULL PIPELINE — easy to configure
# ══════════════════════════════════════════════════════════

def run_full_pipeline(p: int = 1, shots: int = 2048, top_k: int = 10,
                      max_iter: int = 200, save_figures: bool = True,
                      network_file: str = "network.txt"):
    """
    End-to-end QAOA pipeline for the social media Max-Cut problem.

    All parameters can be driven from settings.txt / network.txt —
    you should not need to edit this function directly.

    Parameters
    ----------
    p            : QAOA depth (number of alternating layers)
    shots        : Number of circuit shots for each measurement
    top_k        : How many bitstrings to show in the probability chart
    max_iter     : Maximum COBYLA optimiser iterations
    save_figures : If True, saves each plot as a PNG file
    network_file : Path to the network definition .txt file
    """

    # ── Step 1: Build graph ───────────────────────────────
    G, users = build_social_network(network_file)
    suffix   = f"  (p={p}, shots={shots})"

    # ── Step 2: Run QAOA ──────────────────────────────────
    best_bs, best_cut, counts, history, qc = run_qaoa(
        G, p=p, shots=shots, max_iter=max_iter, verbose=True)

    # ── Step 3: Visualise ─────────────────────────────────
    fig_graph = plot_social_network(G, best_bs, users, suffix)
    fig_prob  = plot_probability_distribution(counts, G, shots, top_k, suffix)
    fig_circ  = plot_circuit(qc, suffix)
    fig_conv  = plot_convergence(history, suffix)

    if save_figures:
        fig_graph.savefig("social_network_partition.png", dpi=150, bbox_inches="tight")
        fig_prob.savefig ("probability_distribution.png",  dpi=150, bbox_inches="tight")
        fig_circ.savefig ("qaoa_circuit.png",               dpi=150, bbox_inches="tight")
        fig_conv.savefig ("convergence_curve.png",          dpi=150, bbox_inches="tight")
        print("  Saved: social_network_partition.png")
        print("  Saved: probability_distribution.png")
        print("  Saved: qaoa_circuit.png")
        print("  Saved: convergence_curve.png")

    plt.show()

    return {
        "best_bitstring": best_bs,
        "best_cut_value": best_cut,
        "counts":         counts,
        "cost_history":   history,
    }


# ══════════════════════════════════════════════════════════
#  7.  ENTRY POINT
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═" * 55)
    print("  QAOA Social Network Analysis — loading config files")
    print("═" * 55)

    # ── Read settings.txt ─────────────────────────────────
    cfg = load_settings("settings.txt")

    # ── Run the pipeline (network.txt is read inside) ─────
    results = run_full_pipeline(
        p            = cfg["p"],
        shots        = cfg["shots"],
        top_k        = cfg["top_k"],
        max_iter     = cfg["max_iter"],
        save_figures = cfg["save_figures"],
        network_file = "network.txt",
    )
