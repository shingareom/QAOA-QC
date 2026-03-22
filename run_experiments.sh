#!/usr/bin/env bash
# ================================================================
#  QAOA Experiment Runner
#  Runs qaoa_social_network.py 15 times with incrementally
#  varying node counts (3→15) and settings, saves each run to
#  its own folder, then calls analyze_results.py for a summary.
#
#  Usage:  bash run_experiments.sh
# ================================================================

set -uo pipefail

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="$PROJ_DIR/analysis_results"
PYTHON="$PROJ_DIR/qaoa_env/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "✗ Could not find Python at $PYTHON"
  echo "  Activate your venv first or update PYTHON= in this script."
  exit 1
fi

export MPLBACKEND=Agg   # non-interactive backend → plt.show() is a no-op

mkdir -p "$RESULTS_DIR"

# ── 15 run configs: NODES  P  SHOTS  MAX_ITER  TOP_K ─────────────
# Node count grows 3→15; settings ramp up incrementally.
# Runs 13-15 keep n=15 and vary only p, shots, max_iter for comparison.
CONFIGS=(
  "3  1  512   100  8"
  "4  1  512   100  8"
  "5  1  1024  150  8"
  "6  1  1024  150  10"
  "7  1  1024  200  10"
  "8  2  1024  200  10"
  "9  2  2048  200  10"
  "10 2  2048  250  12"
  "11 2  2048  250  12"
  "12 2  2048  300  12"
  "13 3  2048  300  14"
  "14 3  4096  300  14"
  "15 3  4096  300  16"
  "15 2  2048  200  12"
  "15 1  1024  150  10"
)

# ── 15 node names (indices 0-14) ─────────────────────────────────
NAMES=("Alice" "Bob" "Carol" "Dave" "Eve" "Frank"
       "Grace" "Henry" "Isla" "Jack" "Karen" "Leo"
       "Mia" "Nathan" "Olivia")

# ── Master edge list: "A_idx B_idx weight" ───────────────────────
# For N nodes, edges where both indices < N are used.
# Path edges guarantee connectivity for every N ≥ 3.
EDGES=(
  "0 1 3"  "1 2 2"  "2 3 3"  "3 4 2"  "4 5 1"
  "5 6 3"  "6 7 2"  "7 8 3"  "8 9 1"  "9 10 2"
  "10 11 3" "11 12 2" "12 13 3" "13 14 2"
  "0 2 1"  "1 3 2"  "2 4 3"  "3 5 1"  "4 6 2"
  "5 7 3"  "6 8 1"  "7 9 2"  "8 10 3" "9 11 1"
  "10 12 2" "11 13 3" "12 14 1"
  "0 3 2"  "1 4 1"  "2 5 2"  "3 6 3"  "4 7 1"
  "5 8 2"  "6 9 3"  "7 10 1" "8 11 2" "9 12 3"
)

# ── Generate network.txt for N nodes ─────────────────────────────
gen_network() {
  local n=$1
  local out=$2
  {
    echo "# Auto-generated network for $n nodes"
    echo ""
    echo "[NODES]"
    for (( i=0; i<n; i++ )); do echo "${NAMES[$i]}"; done
    echo ""
    echo "[EDGES]"
    echo "# NodeA  NodeB  Weight"
    for edge in "${EDGES[@]}"; do
      read -r a b w <<< "$edge"
      if (( a < n && b < n )); then
        echo "${NAMES[$a]}  ${NAMES[$b]}  $w"
      fi
    done
  } > "$out"
}

# ── Backup originals ─────────────────────────────────────────────
cd "$PROJ_DIR"
cp network.txt  network.txt.bak
cp settings.txt settings.txt.bak
echo "  Backed up network.txt and settings.txt"

# ── Main experiment loop ──────────────────────────────────────────
RUN_NUM=0
TOTAL=${#CONFIGS[@]}

for config in "${CONFIGS[@]}"; do
  RUN_NUM=$((RUN_NUM + 1))
  read -r N P SHOTS MAX_ITER TOP_K <<< "$config"

  RUN_ID=$(printf "run_%02d_n%02d_p%d_s%d" "$RUN_NUM" "$N" "$P" "$SHOTS")
  RUN_DIR="$RESULTS_DIR/$RUN_ID"
  mkdir -p "$RUN_DIR"

  echo ""
  echo "══════════════════════════════════════════════════════"
  echo "  Run $RUN_NUM/$TOTAL  |  n=$N  p=$P  shots=$SHOTS  max_iter=$MAX_ITER  top_k=$TOP_K"
  echo "══════════════════════════════════════════════════════"

  # Write config files
  gen_network "$N" "$PROJ_DIR/network.txt"

  cat > "$PROJ_DIR/settings.txt" << SETTINGS
# Auto-generated — Run $RUN_NUM
p = $P
shots = $SHOTS
top_k = $TOP_K
max_iter = $MAX_ITER
save_figures = True
SETTINGS

  # Save copies to run folder
  cp "$PROJ_DIR/network.txt"  "$RUN_DIR/network.txt"
  cp "$PROJ_DIR/settings.txt" "$RUN_DIR/settings.txt"

  # Run QAOA and record timing
  START_TS=$(date +%s)
  set +e
  "$PYTHON" qaoa_social_network.py > "$RUN_DIR/output.log" 2>&1
  EXIT_CODE=$?
  set -e
  END_TS=$(date +%s)
  DURATION=$((END_TS - START_TS))

  # Show output in terminal too
  cat "$RUN_DIR/output.log"

  STATUS="SUCCESS"
  [[ $EXIT_CODE -ne 0 ]] && STATUS="FAILED"

  # Save metadata
  cat > "$RUN_DIR/meta.json" << META
{
  "run": $RUN_NUM,
  "nodes": $N,
  "p": $P,
  "shots": $SHOTS,
  "max_iter": $MAX_ITER,
  "top_k": $TOP_K,
  "duration_sec": $DURATION,
  "status": "$STATUS"
}
META

  # Move PNG outputs into run folder
  for png in social_network_partition.png probability_distribution.png \
              qaoa_circuit.png convergence_curve.png; do
    [[ -f "$PROJ_DIR/$png" ]] && mv "$PROJ_DIR/$png" "$RUN_DIR/$png"
  done

  echo "  ✓ Run $RUN_NUM done in ${DURATION}s — $STATUS"
done

# ── Restore originals ────────────────────────────────────────────
cp network.txt.bak  network.txt
cp settings.txt.bak settings.txt
rm -f network.txt.bak settings.txt.bak
echo ""
echo "  ✓ Restored original network.txt and settings.txt"

# ── Generate analysis ─────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
echo "  Running analysis — analyze_results.py"
echo "══════════════════════════════════════════════════════"
"$PYTHON" "$PROJ_DIR/analyze_results.py" "$RESULTS_DIR"

echo ""
echo "  All done!  Results → $RESULTS_DIR"
