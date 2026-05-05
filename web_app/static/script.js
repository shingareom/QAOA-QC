document.addEventListener('DOMContentLoaded', () => {
    const numNodes = document.getElementById('num_nodes');
    const nodesVal = document.getElementById('nodes-val');
    const pLayers = document.getElementById('p_layers');
    const layersVal = document.getElementById('layers-val');
    
    const form = document.getElementById('sim-form');
    const btnText = document.querySelector('.btn-text');
    const loader = document.querySelector('.loader');
    const runBtn = document.getElementById('run-btn');
    
    const resultsSection = document.getElementById('results-section');

    // Update slider values
    numNodes.addEventListener('input', (e) => {
        nodesVal.textContent = e.target.value;
    });

    pLayers.addEventListener('input', (e) => {
        layersVal.textContent = e.target.value;
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // UI State: Loading
        runBtn.disabled = true;
        btnText.textContent = "Simulating...";
        loader.classList.remove('hidden');
        resultsSection.classList.add('hidden');

        try {
            const response = await fetch('/run_simulation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    num_nodes: parseInt(numNodes.value),
                    p_layers: parseInt(pLayers.value)
                })
            });

            if (!response.ok) {
                throw new Error("Simulation failed");
            }

            const data = await response.json();
            
            // Populate Data
            document.getElementById('res-cut').textContent = data.best_cut.toFixed(1);
            document.getElementById('res-bitstring').textContent = data.best_bitstring;

            // Populate Groups
            const listA = document.getElementById('list-group-a');
            listA.innerHTML = '';
            data.group_a.forEach(user => {
                const li = document.createElement('li');
                li.textContent = user;
                listA.appendChild(li);
            });

            const listB = document.getElementById('list-group-b');
            listB.innerHTML = '';
            data.group_b.forEach(user => {
                const li = document.createElement('li');
                li.textContent = user;
                listB.appendChild(li);
            });

            // Populate Images
            document.getElementById('img-graph').src = "data:image/png;base64," + data.images.graph;
            document.getElementById('img-prob').src = "data:image/png;base64," + data.images.probability;
            document.getElementById('img-conv').src = "data:image/png;base64," + data.images.convergence;
            document.getElementById('img-circ').src = "data:image/png;base64," + data.images.circuit;

            // Show results with animation
            resultsSection.classList.remove('hidden');
            resultsSection.classList.add('fade-in');
            
            // Scroll to results
            setTimeout(() => {
                resultsSection.scrollIntoView({ behavior: 'smooth' });
            }, 100);

        } catch (error) {
            console.error("Error:", error);
            alert("An error occurred during the quantum simulation.");
        } finally {
            // Restore UI State
            runBtn.disabled = false;
            btnText.textContent = "Run Quantum Simulation";
            loader.classList.add('hidden');
        }
    });

    // Lightbox & Zoom Logic
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxClose = document.getElementById('lightbox-close');
    
    let currentScale = 1;
    let isDragging = false;
    let startX, startY, translateX = 0, translateY = 0;

    function updateTransform() {
        lightboxImg.style.transform = `translate(${translateX}px, ${translateY}px) scale(${currentScale})`;
    }

    // Use event delegation for images inside visualizations
    document.querySelector('.visualizations').addEventListener('click', (e) => {
        if (e.target.tagName === 'IMG' && e.target.src) {
            lightboxImg.src = e.target.src;
            lightbox.classList.add('active');
            currentScale = 1;
            translateX = 0;
            translateY = 0;
            updateTransform();
        }
    });

    lightboxClose.addEventListener('click', () => {
        lightbox.classList.remove('active');
    });

    document.getElementById('zoom-in').addEventListener('click', () => {
        currentScale += 0.3;
        updateTransform();
    });

    document.getElementById('zoom-out').addEventListener('click', () => {
        currentScale = Math.max(0.3, currentScale - 0.3);
        updateTransform();
    });

    document.getElementById('zoom-reset').addEventListener('click', () => {
        currentScale = 1;
        translateX = 0;
        translateY = 0;
        updateTransform();
    });

    // Drag to pan logic
    lightboxImg.addEventListener('mousedown', (e) => {
        e.preventDefault();
        isDragging = true;
        startX = e.clientX - translateX;
        startY = e.clientY - translateY;
        lightboxImg.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        translateX = e.clientX - startX;
        translateY = e.clientY - startY;
        updateTransform();
    });

    window.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            lightboxImg.style.cursor = 'grab';
        }
    });
    
    // Close on background click
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) {
            lightbox.classList.remove('active');
        }
    });

    // Wheel to zoom
    lightbox.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (e.deltaY < 0) {
            currentScale += 0.1;
        } else {
            currentScale = Math.max(0.2, currentScale - 0.1);
        }
        updateTransform();
    }, { passive: false });
});
