/* ═══════════════════════════════════════════════════════════════
   QAOA Social Network Analyzer — Frontend
   Stack: GSAP 3 · D3.js 7 · Chart.js 4
═══════════════════════════════════════════════════════════════ */

/* ── Color palette (mirrors CSS vars) ─────────────────────── */
const C = {
    bg:      '#080808',
    surface: '#111111',
    border:  '#252525',
    blue:    '#4FC3F7',   // D3 Group-A nodes & Chart.js — keep colored
    red:     '#EF9A9A',   // D3 Group-B nodes — keep colored
    amber:   '#FFD54F',   // D3 cut edges & Chart.js — keep colored
    text:    '#F0F0F0',
    muted:   '#555555',
};

/* ── Shots lookup ──────────────────────────────────────────── */
const SHOTS_MAP = [512, 1024, 2048, 4096];

/* ── Chart instances (kept for destroy-on-re-run) ─────────── */
let probChart = null;
let convChart = null;

/* ── DOM refs ──────────────────────────────────────────────── */
const form       = document.getElementById('sim-form');
const runBtn     = document.getElementById('run-btn');
const runLoader  = document.getElementById('run-loader');
const runBtnText = document.getElementById('run-btn-text');
const emptyState = document.getElementById('empty-state');
const resultsCt  = document.getElementById('results-content');
const errorToast = document.getElementById('error-toast');

/* ════════════════════════════════════════════════════════════
   PAGE LOAD
════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
    gsap.from('.site-header', {
        y: -30, opacity: 0, duration: 0.9, ease: 'power3.out'
    });
    gsap.from('#controls-panel', {
        x: -30, opacity: 0, duration: 0.9, delay: 0.15, ease: 'power3.out'
    });
    gsap.from('.empty-state', {
        x: 30, opacity: 0, duration: 0.9, delay: 0.25, ease: 'power3.out'
    });

    initSliders();
    initModeToggle();
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await runSimulation();
    });
});

/* ════════════════════════════════════════════════════════════
   SLIDER INIT
════════════════════════════════════════════════════════════ */
function initSliders() {
    const configs = [
        { id: 'num_nodes', valId: 'nodes-val',  fmt: v => v },
        { id: 'p_layers',  valId: 'layers-val', fmt: v => v },
        { id: 'shots_idx', valId: 'shots-val',  fmt: v => SHOTS_MAP[+v].toLocaleString() },
        { id: 'max_iter',  valId: 'iter-val',   fmt: v => v },
        { id: 'top_k',     valId: 'topk-val',   fmt: v => v },
    ];

    configs.forEach(({ id, valId, fmt }) => {
        const slider = document.getElementById(id);
        const label  = document.getElementById(valId);
        if (!slider || !label) return;
        label.textContent = fmt(slider.value);
        slider.addEventListener('input', () => {
            label.textContent = fmt(slider.value);
            gsap.fromTo(label,
                { scale: 1.35, color: '#fff' },
                { scale: 1, color: C.blue, duration: 0.25, ease: 'back.out(4)' }
            );
        });
    });
}

/* ════════════════════════════════════════════════════════════
   MODE TOGGLE
════════════════════════════════════════════════════════════ */
function initModeToggle() {
    const btns   = document.querySelectorAll('.mode-btn');
    const random = document.getElementById('random-params');
    const custom = document.getElementById('custom-params');

    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            btns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            if (btn.dataset.mode === 'random') {
                random.classList.remove('hidden');
                custom.classList.add('hidden');
            } else {
                random.classList.add('hidden');
                custom.classList.remove('hidden');
            }
        });
    });
}

/* ════════════════════════════════════════════════════════════
   RUN SIMULATION
════════════════════════════════════════════════════════════ */
async function runSimulation() {
    setLoading(true);
    hideError();

    const activeMode = document.querySelector('.mode-btn.active')?.dataset.mode ?? 'random';

    const payload = {
        num_nodes:      parseInt(document.getElementById('num_nodes').value),
        p_layers:       parseInt(document.getElementById('p_layers').value),
        shots:          SHOTS_MAP[parseInt(document.getElementById('shots_idx').value)],
        max_iter:       parseInt(document.getElementById('max_iter').value),
        top_k:          parseInt(document.getElementById('top_k').value),
        network_mode:   activeMode,
        custom_network: activeMode === 'custom'
            ? document.getElementById('custom-network').value
            : '',
    };

    try {
        const res  = await fetch('/run_simulation', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload),
        });
        const data = await res.json();

        if (!res.ok) {
            showError(data.error ?? 'Simulation failed.');
            return;
        }

        renderResults(data);

    } catch (err) {
        showError('Network error — is the Flask server running?');
    } finally {
        setLoading(false);
    }
}

/* ════════════════════════════════════════════════════════════
   RENDER RESULTS
════════════════════════════════════════════════════════════ */
function renderResults(data) {
    emptyState.classList.add('hidden');
    resultsCt.classList.remove('hidden');

    /* Meta bar */
    document.getElementById('meta-nodes').textContent = data.meta.nodes;
    document.getElementById('meta-edges').textContent = data.meta.edges;
    document.getElementById('meta-p').textContent     = data.meta.p;
    document.getElementById('meta-shots').textContent = data.meta.shots.toLocaleString();
    document.getElementById('meta-iters').textContent = data.meta.iterations;

    /* Summary cards */
    animateCount('res-cut', data.best_cut, 1);
    document.getElementById('res-bitstring').textContent = data.best_bitstring;
    renderPillList('list-group-a', data.group_a);
    renderPillList('list-group-b', data.group_b);

    /* Visualizations */
    renderD3Network(data.graph_data);
    renderProbChart(data.counts_data);
    renderConvChart(data.history);
    document.getElementById('circuit-img').src = 'data:image/png;base64,' + data.circuit_img;

    /* GSAP stagger reveal */
    animateReveal();
    setTimeout(() => resultsCt.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120);
}

/* ── Pill list ──────────────────────────────────────────────── */
function renderPillList(id, names) {
    const ul = document.getElementById(id);
    ul.innerHTML = '';
    names.forEach(name => {
        const li = document.createElement('li');
        li.textContent = name;
        ul.appendChild(li);
    });
}

/* ── Animated counter ───────────────────────────────────────── */
function animateCount(id, target, decimals) {
    const el  = document.getElementById(id);
    const obj = { val: 0 };
    gsap.to(obj, {
        val: target, duration: 1.4, ease: 'power2.out',
        onUpdate: () => { el.textContent = obj.val.toFixed(decimals); },
    });
}

/* ════════════════════════════════════════════════════════════
   D3 FORCE NETWORK
════════════════════════════════════════════════════════════ */
function renderD3Network(graphData) {
    const container = document.getElementById('d3-network');
    container.innerHTML = '';

    const W = container.clientWidth  || 760;
    const H = container.clientHeight || 400;

    const svg = d3.select('#d3-network')
        .append('svg')
        .attr('viewBox', `0 0 ${W} ${H}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');

    /* Zoom/pan layer */
    const g = svg.append('g');
    svg.call(
        d3.zoom().scaleExtent([0.25, 5])
            .on('zoom', (event) => g.attr('transform', event.transform))
    );

    /* Tooltip */
    const tooltip = document.createElement('div');
    tooltip.className = 'd3-tooltip';
    container.appendChild(tooltip);

    /* Deep-clone so D3 can mutate freely */
    const nodes = graphData.nodes.map(d => ({ ...d }));
    const edges = graphData.edges.map(d => ({ ...d }));

    /* Force simulation */
    const sim = d3.forceSimulation(nodes)
        .force('link',      d3.forceLink(edges).id(d => d.id).distance(90).strength(0.6))
        .force('charge',    d3.forceManyBody().strength(-260))
        .force('center',    d3.forceCenter(W / 2, H / 2))
        .force('collision', d3.forceCollide(28));

    /* ── Edges ── */
    const link = g.append('g')
        .selectAll('line')
        .data(edges)
        .join('line')
        .attr('stroke',           d => d.is_cut ? C.amber : C.border)
        .attr('stroke-width',     d => d.is_cut ? 2.5 : 1.5)
        .attr('stroke-dasharray', d => d.is_cut ? '7 4' : null)
        .attr('stroke-opacity',   d => d.is_cut ? 1.0 : 0.55);

    /* Edge weight labels */
    const edgeLabel = g.append('g')
        .selectAll('text')
        .data(edges)
        .join('text')
        .attr('fill', C.muted)
        .attr('font-size', 8.5)
        .attr('font-family', "'JetBrains Mono', monospace")
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .text(d => d.weight);

    /* ── Nodes ── */
    const node = g.append('g')
        .selectAll('g')
        .data(nodes)
        .join('g')
        .style('cursor', 'pointer')
        .call(
            d3.drag()
                .on('start', (event, d) => {
                    if (!event.active) sim.alphaTarget(0.3).restart();
                    d.fx = d.x; d.fy = d.y;
                })
                .on('drag',  (event, d) => { d.fx = event.x; d.fy = event.y; })
                .on('end',   (event, d) => {
                    if (!event.active) sim.alphaTarget(0);
                    d.fx = null; d.fy = null;
                })
        );

    /* Outer glow ring */
    node.append('circle')
        .attr('r', 22)
        .attr('fill', d => d.group === 0
            ? 'rgba(79,195,247,0.07)' : 'rgba(239,154,154,0.07)')
        .attr('stroke', 'none');

    /* Main circle */
    node.append('circle')
        .attr('r', 16)
        .attr('fill', d => d.group === 0
            ? 'rgba(79,195,247,0.18)' : 'rgba(239,154,154,0.18)')
        .attr('stroke',       d => d.group === 0 ? C.blue : C.red)
        .attr('stroke-width', 2);

    /* Name label */
    node.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '0.35em')
        .attr('fill',        d => d.group === 0 ? C.blue : C.red)
        .attr('font-size', 8.5)
        .attr('font-family', "'JetBrains Mono', monospace")
        .attr('font-weight', '600')
        .text(d => d.name.length > 6 ? d.name.slice(0, 5) + '…' : d.name);

    /* Group badge */
    node.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '2.6em')
        .attr('fill', C.muted)
        .attr('font-size', 7)
        .attr('font-family', "'Inter', sans-serif")
        .text(d => d.group === 0 ? '(A)' : '(B)');

    /* Hover tooltip */
    node
        .on('mouseenter', (event, d) => {
            const col = d.group === 0 ? C.blue : C.red;
            tooltip.style.opacity = '1';
            tooltip.innerHTML =
                `<span style="color:${col};font-weight:700">${d.name}</span><br>` +
                `Group ${d.group === 0 ? 'A &mdash; Influencer' : 'B &mdash; Follower'}`;
        })
        .on('mousemove', (event) => {
            const rect = container.getBoundingClientRect();
            tooltip.style.left = (event.clientX - rect.left + 14) + 'px';
            tooltip.style.top  = (event.clientY - rect.top  - 12) + 'px';
        })
        .on('mouseleave', () => { tooltip.style.opacity = '0'; });

    /* Tick */
    sim.on('tick', () => {
        link
            .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);

        edgeLabel
            .attr('x', d => (d.source.x + d.target.x) / 2)
            .attr('y', d => (d.source.y + d.target.y) / 2);

        node.attr('transform', d => `translate(${d.x},${d.y})`);
    });
}

/* ════════════════════════════════════════════════════════════
   CHART.JS — PROBABILITY
════════════════════════════════════════════════════════════ */
function renderProbChart(countsData) {
    if (typeof Chart === 'undefined') {
        document.getElementById('prob-chart').closest('.viz-card').querySelector('.viz-title').textContent += ' — Chart.js failed to load';
        return;
    }
    if (probChart) probChart.destroy();

    const ctx    = document.getElementById('prob-chart').getContext('2d');
    const labels = countsData.map(d => d.bitstring);
    const probs  = countsData.map(d => d.probability);
    const cuts   = countsData.map(d => d.cut_value);
    const maxCut = Math.max(...cuts, 1);

    /* Colour each bar: blue (low cut) → amber (high cut) */
    const colors = cuts.map(cv => {
        const t  = cv / maxCut;
        const r  = Math.round(79  + (255 - 79)  * t);
        const gg = Math.round(195 + (213 - 195) * t);
        const b  = Math.round(247 + (79  - 247) * t);
        return `rgba(${r},${gg},${b},0.85)`;
    });

    probChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: probs,
                backgroundColor: colors,
                borderColor: 'transparent',
                borderRadius: 5,
                borderSkipped: false,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 900, easing: 'easeOutQuart' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1A1A2E',
                    borderColor: C.blue,
                    borderWidth: 1,
                    titleColor: C.text,
                    bodyColor:  C.muted,
                    titleFont:  { family: "'JetBrains Mono'" },
                    callbacks: {
                        label: (ctx) => {
                            const cd = countsData[ctx.dataIndex];
                            return [
                                `  Prob : ${(cd.probability * 100).toFixed(1)}%`,
                                `  Cut  : ${cd.cut_value.toFixed(0)}`,
                            ];
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks:  { color: C.muted, font: { family: "'JetBrains Mono'", size: 8 }, maxRotation: 45 },
                    grid:   { color: C.border },
                    border: { color: C.border },
                },
                y: {
                    ticks:  { color: C.muted, font: { size: 9 } },
                    grid:   { color: C.border },
                    border: { color: C.border },
                    title:  { display: true, text: 'Probability', color: C.muted, font: { size: 10 } },
                },
            },
        },
    });
}

/* ════════════════════════════════════════════════════════════
   CHART.JS — CONVERGENCE
════════════════════════════════════════════════════════════ */
function renderConvChart(history) {
    if (typeof Chart === 'undefined') return;
    if (convChart) convChart.destroy();

    const ctx = document.getElementById('conv-chart').getContext('2d');

    convChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: history.map((_, i) => i + 1),
            datasets: [{
                label: '⟨C⟩',
                data: history,
                borderColor: C.blue,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHoverBackgroundColor: C.blue,
                fill: true,
                backgroundColor: 'rgba(79,195,247,0.07)',
                tension: 0.35,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 1000, easing: 'easeOutQuart' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1A1A2E',
                    borderColor: C.blue,
                    borderWidth: 1,
                    titleColor: C.text,
                    bodyColor:  C.muted,
                    callbacks: {
                        title: (items) => `Iteration ${items[0].label}`,
                        label: (item)  => `  ⟨C⟩ = ${item.raw.toFixed(3)}`,
                    },
                },
            },
            scales: {
                x: {
                    ticks:  { color: C.muted, font: { size: 9 }, maxTicksLimit: 10 },
                    grid:   { color: C.border },
                    border: { color: C.border },
                    title:  { display: true, text: 'Iteration', color: C.muted, font: { size: 10 } },
                },
                y: {
                    ticks:  { color: C.muted, font: { size: 9 } },
                    grid:   { color: C.border },
                    border: { color: C.border },
                    title:  { display: true, text: '⟨C⟩', color: C.muted, font: { size: 10 } },
                },
            },
        },
    });
}

/* ════════════════════════════════════════════════════════════
   GSAP REVEAL
════════════════════════════════════════════════════════════ */
function animateReveal() {
    gsap.timeline()
        .from('#meta-bar .meta-item', {
            y: 16, opacity: 0, duration: 0.35, stagger: 0.05, ease: 'power2.out',
        })
        .from('.summary-card', {
            y: 28, opacity: 0, duration: 0.45, stagger: 0.07, ease: 'power3.out',
        }, '-=0.1')
        .from('.viz-card', {
            y: 28, opacity: 0, duration: 0.45, stagger: 0.08, ease: 'power3.out',
        }, '-=0.2');
}

/* ════════════════════════════════════════════════════════════
   UI HELPERS
════════════════════════════════════════════════════════════ */
function setLoading(on) {
    runBtn.disabled = on;
    runBtnText.textContent = on ? 'Simulating…' : 'Run Simulation';
    runLoader.classList.toggle('hidden', !on);
}

function showError(msg) {
    errorToast.textContent = '✕  ' + msg;
    errorToast.classList.remove('hidden');
    gsap.fromTo(errorToast,
        { x: 30, opacity: 0 },
        { x: 0,  opacity: 1, duration: 0.4, ease: 'power3.out' }
    );
    setTimeout(() => {
        gsap.to(errorToast, {
            opacity: 0, x: 30, duration: 0.4,
            onComplete: () => errorToast.classList.add('hidden'),
        });
    }, 5000);
}

function hideError() {
    errorToast.classList.add('hidden');
}
