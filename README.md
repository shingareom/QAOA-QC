# QAOA — Social Media Network Analysis (Max-Cut)

> **Quantum Approximate Optimization Algorithm** implemented in **Qiskit**  
> Partitions a social network into *Influencers* vs *Followers* by solving the Max-Cut problem.

---

## Team

| Name               | Roll No.    |
|--------------------|-------------|
| Rohit Rao          | 612303152   |
| Viraj Nalbalwar    | 642403013   |
| Shreesh Kolhatkar  | 642403009   |
| Om Shingare        | 642403020   |

---

## What This Does

Given a social network graph where:
- **Nodes** = Users (Alice, Bob, Carol, Dave, Eve, Frank)
- **Edges** = Friendships / connections
- **Edge weights** = Interaction strength / influence score

QAOA finds the partition of users into **Group A (Influencers)** and **Group B (Followers)**
that **maximises cross-group connections** — the Max-Cut solution.

---

## Installation

```bash
pip install qiskit qiskit-aer networkx matplotlib scipy numpy
```

Or using the requirements file:

```bash
pip install -r requirements.txt
```

---

## Running the Code

```bash
python qaoa_social_network.py
```

---

## Configuration

Edit the bottom of `qaoa_social_network.py`:

```python
results = run_full_pipeline(
    p           = 1,     # QAOA depth — try 1, 2, or 3
    shots       = 2048,  # Measurement samples per circuit evaluation
    top_k       = 10,    # How many bitstrings to show in probability chart
    save_figures= True,  # Saves all plots as PNG files
)
```

| Parameter | Meaning                       | Suggested Values     |
|-----------|-------------------------------|----------------------|
| `p`       | QAOA layer depth              | 1 (fast), 2, 3       |
| `shots`   | Circuit measurement samples   | 1024, 2048, 4096     |
| `top_k`   | Bars in probability chart     | 8 – 16               |

Higher `p` → deeper circuit → closer to optimal, but slower to optimise.

---

## Output

The pipeline produces **4 visualisations**:

### 1. `social_network_partition.png` — Graph with Group Colouring
- Blue nodes = Group A (Influencers)
- Red nodes = Group B (Followers)
- Amber dashed edges = Cut edges (maximised by QAOA)
- Grey edges = Non-cut edges

### 2. `probability_distribution.png` — Measurement Probability Bar Chart
- X-axis: bitstrings (each character = one user, 0=GroupA, 1=GroupB)
- Y-axis: probability of measuring that bitstring
- Bar colour: darker = higher Max-Cut value
- Best solutions cluster at the top

### 3. `qaoa_circuit.png` — Quantum Circuit Diagram
- H gates: initial superposition layer
- Rzz gates: cost unitary U_C(γ) for each edge
- Rx gates: mixer unitary U_B(β) for each qubit
- Repeated p times

### 4. `convergence_curve.png` — COBYLA Optimiser Convergence
- Shows ⟨C⟩ (expected cut value) improving across iterations
- Flat region at the top = convergence achieved

---

## How It Works — Step by Step

```
Social Network Graph
       ↓
  Max-Cut QUBO Formulation
  Maximise: Σ(i,j)∈E  wᵢⱼ · (xᵢ + xⱼ − 2xᵢxⱼ)
       ↓
  Ising Hamiltonian
  Hc = Σ(i,j)∈E  (wᵢⱼ/2)(1 − ZᵢZⱼ)
       ↓
  QAOA Circuit  (p layers)
  |ψ(γ,β)⟩ = U_B(βₚ) U_C(γₚ) … U_B(β₁) U_C(γ₁) |+⟩ⁿ
       ↓
  COBYLA Classical Optimiser tunes γ,β
       ↓
  Measurement → Probability Distribution
       ↓
  Best Bitstring = Max-Cut Partition
       ↓
  Group A = Influencers | Group B = Followers
```

---

## Project Structure

```
qaoa_social_network.py   ← Main implementation (all-in-one)
requirements.txt         ← Python dependencies
README.md                ← This file

Generated outputs:
social_network_partition.png
probability_distribution.png
qaoa_circuit.png
convergence_curve.png
```

---

## Key Equations

**Cost Function (Max-Cut):**
```
f(x) = Σ_(i,j)∈E  wᵢⱼ · (xᵢ + xⱼ − 2xᵢxⱼ)
```

**Ising Hamiltonian:**
```
Hc = Σ_(i,j)∈E  (wᵢⱼ/2)(1 − Zᵢ⊗Zⱼ)
```

**QAOA State:**
```
|ψ(γ,β)⟩ = [∏ₖ U_B(βₖ) U_C(γₖ)] |+⟩^⊗n
```

**Cost Layer:**
```
U_C(γ) = e^{−iγHc}  =  ∏_(i,j) Rzz(2γwᵢⱼ)
```

**Mixer Layer:**
```
U_B(β) = e^{−iβΣᵢXᵢ}  =  ∏ᵢ Rx(2β)
```

---

## Reference

IBM Quantum — Quantum Computing in Practice, Episode 3 (Olivia Lans, 2024)  
https://youtu.be/P3s7TIMIvZ0
