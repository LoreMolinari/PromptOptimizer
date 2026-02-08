document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('refineBtn').addEventListener('click', startRefinement);
});

async function startRefinement() {
    const btn = document.getElementById('refineBtn');
    const promptInput = document.getElementById('roughPrompt');
    const resultSection = document.getElementById('resultSection');
    const refinedDisplay = document.getElementById('refinedPrompt');
    const historyList = document.getElementById('versionsList');

    if (!promptInput.value.trim()) return;

    btn.disabled = true;
    btn.textContent = 'Refining...';
    resultSection.style.display = 'none';
    document.getElementById('testSection').style.display = 'none';
    historyList.innerHTML = '';

    try {
        // Start
        const startResp = await fetch('/api/refine', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                rough_prompt: promptInput.value,
                context: document.getElementById('context').value || null,
                domain: document.getElementById('domainSelect').value,
                max_iterations: parseInt(document.getElementById('iterations').value) || 3
            })
        });

        if (!startResp.ok) throw new Error('Failed to start refinement');

        // Poll for results
        const poll = setInterval(async () => {
            try {
                const statusResp = await fetch('/api/refine/status');
                const status = await statusResp.json();

                if (status.result) {
                    clearInterval(poll);

                    resultSection.style.display = 'block';
                    refinedDisplay.textContent = status.result.final_prompt;

                    document.getElementById('testSection').style.display = 'block';

                    const grouped = {};
                    status.result.all_versions.forEach(ver => {
                        if (!grouped[ver.iteration]) grouped[ver.iteration] = [];
                        grouped[ver.iteration].push(ver);
                    });

                    Object.keys(grouped).sort((a, b) => a - b).forEach(iter => {
                        const iterDiv = document.createElement('div');
                        iterDiv.className = 'iteration-group';
                        iterDiv.innerHTML = `<h3>Iteration ${iter}</h3>`;

                        grouped[iter].forEach(ver => {
                            const verDiv = document.createElement('div');
                            verDiv.className = 'version' + (ver.is_best ? ' highlight' : '');
                            verDiv.innerHTML = `
                                <div class="version-header">
                                    <span class="badge ${ver.is_best ? 'badge-success' : 'badge-secondary'}">
                                        Score: ${ver.score || 'N/A'}
                                    </span>
                                    <span class="model-name">${ver.model_name || 'human'}</span>
                                </div>
                                <p>${ver.content}</p>
                                ${ver.critique ? `<p class="critique"><strong>Critique:</strong> ${ver.critique}</p>` : ''}
                            `;
                            iterDiv.appendChild(verDiv);
                        });
                        historyList.appendChild(iterDiv);
                    });

                    btn.disabled = false;
                    btn.textContent = 'Refine Prompt';
                } else if (status.error) {
                    clearInterval(poll);
                    alert(status.error);
                    btn.disabled = false;
                    btn.textContent = 'Refine Prompt';
                }
            } catch (e) {
                console.error(e);
            }
        }, 1000);

    } catch (e) {
        alert(e.message);
        btn.disabled = false;
        btn.textContent = 'Refine Prompt';
    }
}

async function testPrompt() {
    const input = document.getElementById('testInput');
    const output = document.getElementById('testOutput');
    const resultDiv = document.getElementById('testResult');
    const btn = document.getElementById('testBtn');

    const refinedPromptContent = document.getElementById('refinedPrompt').textContent;

    if (!input.value.trim() || !refinedPromptContent) {
        alert("Please ensure you have a refined prompt and entered test input.");
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Testing...';
    resultDiv.style.display = 'none';

    try {
        const response = await fetch('/api/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt_content: refinedPromptContent,
                user_input: input.value
            })
        });

        if (!response.ok) throw new Error('Test failed');

        const result = await response.json();
        resultDiv.style.display = 'block';
        output.textContent = result.output;

    } catch (e) {
        alert(e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Test';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('refineBtn').addEventListener('click', startRefinement);
    const testBtn = document.getElementById('testBtn');
    if (testBtn) testBtn.addEventListener('click', testPrompt);

    // Add domain change listener
    const domainSelect = document.getElementById('domainSelect');
    if (domainSelect) {
        domainSelect.addEventListener('change', updateExample);
        // Initialize with default example
        updateExample();
    }
});

function updateExample() {
    const domain = document.getElementById('domainSelect').value;
    const roughPrompt = document.getElementById('roughPrompt');
    const context = document.getElementById('context');

    if (domain === 'code') {
        roughPrompt.value = "Write a well structured Python script";
        context.value = "System Administrator Expert. Handle security problems and errors gracefully.";
    } else {
        roughPrompt.value = "Identify a book by its quote";
        context.value = "Literary Assistant. Identify the book, author, and year. Explain the quote's significance";
    }
}
