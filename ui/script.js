// ===== CONFIGURATION =====
const API_BASE_URL = 'http://localhost:8000';
const API_KEY = 'dev-key-1';

// Available models — id values must match FastAPI provider pattern
const AVAILABLE_MODELS = [
    { id: 'gemini', name: 'Gemini', icon: '⭐', color: '#4285f4' },
    { id: 'openai', name: 'OpenAI GPT', icon: '🎯', color: '#10a37f' },
    { id: 'deepseek', name: 'DeepSeek', icon: '🧠', color: '#8b5cf6' },
    { id: 'grok', name: 'Grok', icon: '🤖', color: '#06b6d4' }
];

// State
let selectedModels = {
    slot1: AVAILABLE_MODELS[0],  // gemini
    slot2: AVAILABLE_MODELS[1],  // openai
    slot3: AVAILABLE_MODELS[2]   // deepseek
};
let activeModelCount = 2;
let dropdownStates = { slot1: false, slot2: false, slot3: false };

// ===== DOM ELEMENTS =====
const promptInput = document.getElementById('promptInput');
const compareBtn = document.getElementById('compareBtn');
const exampleCards = document.querySelectorAll('.example-card');
const toggleBtns = document.querySelectorAll('.toggle-btn');
const modelDropdowns = document.querySelectorAll('.model-dropdown');
const homeBtn = document.getElementById('homeBtn');
const historyBtn = document.getElementById('historyBtn');

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', () => {
    console.log('CortexAI Arena initialized');
    setupEventListeners();
    createDropdownMenus();
});

// ===== DROPDOWN MENUS =====
function createDropdownMenus() {
    modelDropdowns.forEach((dropdown, index) => {
        const slotId = `slot${index + 1}`;

        const menu = document.createElement('div');
        menu.className = 'dropdown-menu';
        menu.id = `dropdown-menu-${slotId}`;

        AVAILABLE_MODELS.forEach(model => {
            const option = document.createElement('div');
            option.className = 'dropdown-option';
            option.innerHTML = `
                <div class="model-icon" style="color: ${model.color}">${model.icon}</div>
                <span>${model.name}</span>
                <svg class="check-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M13 4L6 11L3 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            `;
            option.addEventListener('click', (e) => {
                e.stopPropagation();
                selectModel(slotId, model);
                closeDropdown(slotId);
            });
            menu.appendChild(option);
        });

        dropdown.parentElement.appendChild(menu);
        updateDropdownDisplay(slotId, selectedModels[slotId]);
    });
}

function updateDropdownDisplay(slotId, model) {
    const slotIndex = parseInt(slotId.replace('slot', '')) - 1;
    const dropdown = modelDropdowns[slotIndex];

    if (dropdown) {
        const icon = dropdown.querySelector('.model-icon');
        const name = dropdown.querySelector('.model-name');
        if (icon) { icon.textContent = model.icon; icon.style.color = model.color; }
        if (name) { name.textContent = model.name; }
    }

    const menu = document.getElementById(`dropdown-menu-${slotId}`);
    if (menu) {
        menu.querySelectorAll('.dropdown-option').forEach((option, i) => {
            option.classList.toggle('selected', AVAILABLE_MODELS[i].id === model.id);
        });
    }
}

function selectModel(slotId, model) {
    selectedModels[slotId] = model;
    updateDropdownDisplay(slotId, model);
}

function toggleDropdown(slotId) {
    const menu = document.getElementById(`dropdown-menu-${slotId}`);
    const wasOpen = dropdownStates[slotId];
    Object.keys(dropdownStates).forEach(id => closeDropdown(id));
    if (!wasOpen && menu) {
        menu.classList.add('show');
        dropdownStates[slotId] = true;
    }
}

function closeDropdown(slotId) {
    const menu = document.getElementById(`dropdown-menu-${slotId}`);
    if (menu) { menu.classList.remove('show'); dropdownStates[slotId] = false; }
}

document.addEventListener('click', (e) => {
    if (!e.target.closest('.model-dropdown') && !e.target.closest('.dropdown-menu')) {
        Object.keys(dropdownStates).forEach(closeDropdown);
    }
});

// ===== EVENT LISTENERS =====
function setupEventListeners() {
    if (compareBtn) compareBtn.addEventListener('click', handleSubmit);

    exampleCards.forEach(card => {
        card.addEventListener('click', () => {
            const query = card.getAttribute('data-query');
            if (query && promptInput) {
                promptInput.value = query;
                promptInput.focus();
                card.style.transform = 'scale(0.95)';
                setTimeout(() => { card.style.transform = ''; }, 150);
            }
        });
    });

    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const modelCount = parseInt(btn.getAttribute('data-models'));
            setActiveModelCount(modelCount);
            toggleBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });

    modelDropdowns.forEach((dropdown, index) => {
        const slotId = `slot${index + 1}`;
        dropdown.addEventListener('click', (e) => { e.stopPropagation(); toggleDropdown(slotId); });
    });

    if (promptInput) {
        promptInput.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                handleSubmit();
            }
        });
    }

    if (homeBtn) homeBtn.addEventListener('click', resetToInitialState);
    if (historyBtn) historyBtn.addEventListener('click', () => console.log('History clicked'));
}

// ===== MODEL SELECTION =====
function setActiveModelCount(count) {
    activeModelCount = count;
    document.querySelectorAll('.model-slot').forEach((slot, index) => {
        slot.style.opacity = index < count ? '1' : '0.4';
        slot.style.pointerEvents = index < count ? 'auto' : 'none';
    });
}

function getActiveModels() {
    return ['slot1', 'slot2', 'slot3'].slice(0, activeModelCount).map(s => selectedModels[s]);
}

// ===== API HELPERS =====
function apiHeaders() {
    return { 'Content-Type': 'application/json', 'X-API-Key': API_KEY };
}

// ===== MAIN SUBMIT HANDLER =====
async function handleSubmit() {
    const prompt = promptInput.value.trim();
    if (!prompt) {
        promptInput.style.animation = 'shake 0.3s';
        setTimeout(() => { promptInput.style.animation = ''; }, 300);
        promptInput.focus();
        return;
    }

    // Loading state
    compareBtn.disabled = true;
    const originalHTML = compareBtn.innerHTML;
    compareBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" style="animation: spin 1s linear infinite;">
            <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="2" stroke-dasharray="15 10" fill="none"/>
        </svg>
        <span>${activeModelCount > 1 ? 'Comparing...' : 'Thinking...'}</span>
    `;

    try {
        const models = getActiveModels();

        if (activeModelCount === 1) {
            // ── Single model: POST /v1/chat ──────────────────────────────────
            await handleSingleChat(prompt, models[0]);
        } else {
            // ── Multi-model: POST /v1/compare ────────────────────────────────
            await handleCompare(prompt, models);
        }
    } catch (error) {
        console.error('Request failed:', error);
        showErrorNotification(error.message || 'Request failed. Please try again.');
    } finally {
        compareBtn.disabled = false;
        compareBtn.innerHTML = originalHTML;
    }
}

// ── Single model chat (chat.py → POST /v1/chat) ──────────────────────────────
async function handleSingleChat(prompt, model) {
    const body = {
        prompt,
        provider: model.id,
        model: null          // let the backend pick the default model for the provider
    };

    const res = await fetch(`${API_BASE_URL}/v1/chat`, {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify(body)
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    // ChatResponseDTO: { text, provider, model, latency_ms, token_usage, estimated_cost, error }
    const card = {
        displayName: model.name,
        icon: model.icon,
        color: model.color,
        response: data.error ? null : data.text,
        error: data.error ? data.error.message : null,
        tokens: data.token_usage?.total_tokens ?? 0,
        latency_ms: data.latency_ms ?? 0,
        cost: data.estimated_cost ?? 0
    };

    displayResults([card], prompt);
}

// ── Multi-model compare (compare.py → POST /v1/compare) ──────────────────────
async function handleCompare(prompt, models) {
    const body = {
        prompt,
        targets: models.map(m => ({ provider: m.id }))
    };

    const res = await fetch(`${API_BASE_URL}/v1/compare`, {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify(body)
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    // CompareResponseDTO: { responses: ChatResponseDTO[], success_count, error_count, total_tokens, total_cost }
    const cards = data.responses.map((r, i) => {
        const uiModel = models[i] || { name: r.provider, icon: '🤖', color: '#888' };
        return {
            displayName: uiModel.name,
            icon: uiModel.icon,
            color: uiModel.color,
            response: r.error ? null : r.text,
            error: r.error ? r.error.message : null,
            tokens: r.token_usage?.total_tokens ?? 0,
            latency_ms: r.latency_ms ?? 0,
            cost: r.estimated_cost ?? 0
        };
    });

    displayResults(cards, prompt);
}

// ===== RESULTS DISPLAY =====
function displayResults(cards, prompt) {
    let container = document.getElementById('resultsContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'resultsContainer';
        container.className = 'results-container';
        const promptContainer = document.querySelector('.prompt-container');
        promptContainer.parentElement.insertBefore(container, promptContainer.nextSibling);
    }

    container.innerHTML = `
        <div class="prompt-display">
            <div class="prompt-label">PROMPT:</div>
            <div class="prompt-text">${escapeHtml(prompt)}</div>
        </div>
        <div class="comparison-grid" style="grid-template-columns: repeat(${cards.length}, 1fr);">
            ${cards.map((card, i) => createResponseCard(card, i)).join('')}
        </div>
    `;

    container.style.display = 'block';
    container.style.animation = 'fadeIn 0.5s ease-out';
    setTimeout(() => container.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
}

function createResponseCard(card, index) {
    return `
        <div class="response-card" style="animation-delay: ${index * 0.1}s; border-color: ${card.color}20;">
            <div class="response-header">
                <div class="response-icon" style="color: ${card.color}">${card.icon}</div>
                <div class="response-title">
                    <div class="response-model">${card.displayName}</div>
                    <div class="response-slot">Slot ${index + 1}</div>
                </div>
            </div>

            <div class="response-content">
                ${formatResponseText(card.response || card.error || 'No response')}
            </div>

            ${!card.error ? `
                <div class="response-footer">
                    <div class="response-stats">
                        <div class="stat-item">
                            <span class="stat-value">${formatNumber(card.tokens)}</span>
                            <span class="stat-label">tokens</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">${card.latency_ms}ms</span>
                            <span class="stat-label">latency</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">$${card.cost.toFixed(6)}</span>
                            <span class="stat-label">cost</span>
                        </div>
                    </div>
                    <button class="vote-btn" onclick="voteForResponse(${index}, '${card.displayName}')" style="background: ${card.color};">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M8 2L10 6H14L11 9L12 13L8 10L4 13L5 9L2 6H6L8 2Z" fill="currentColor"/>
                        </svg>
                        Vote Best
                    </button>
                </div>
            ` : `
                <div class="response-error">⚠️ Error: ${escapeHtml(card.error)}</div>
            `}
        </div>
    `;
}

// ===== UTILITIES =====
function formatResponseText(text) {
    return escapeHtml(text)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatNumber(num) {
    return num >= 1000 ? (num / 1000).toFixed(1) + 'k' : String(num);
}

// ===== UI ACTIONS =====
function resetToInitialState() {
    const container = document.getElementById('resultsContainer');
    if (container) {
        container.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => { container.style.display = 'none'; container.innerHTML = ''; }, 300);
    }
    if (promptInput) { promptInput.value = ''; promptInput.focus(); }
}

function voteForResponse(index, modelName) {
    showNotification(`Vote recorded for ${modelName}! 🎉`);
    const cards = document.querySelectorAll('.response-card');
    if (cards[index]) {
        cards[index].classList.add('voted');
        setTimeout(() => cards[index].classList.remove('voted'), 1000);
    }
}

// ===== NOTIFICATIONS =====
function showNotification(message) {
    _notify(message, 'success');
}

function showErrorNotification(message) {
    _notify(message, 'error');
}

function _notify(message, type) {
    const n = document.createElement('div');
    n.className = `notification ${type}`;
    n.textContent = message;
    document.body.appendChild(n);
    setTimeout(() => n.classList.add('show'), 10);
    setTimeout(() => { n.classList.remove('show'); setTimeout(() => n.remove(), 300); }, 3000);
}

// ===== INJECTED STYLES =====
const additionalStyles = document.createElement('style');
additionalStyles.textContent = `
    .model-slot { position: relative; }

    .dropdown-menu {
        position: absolute;
        top: calc(100% + 8px);
        left: 0; right: 0;
        background: rgba(10, 14, 26, 0.95);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: var(--radius-lg);
        padding: var(--spacing-sm);
        opacity: 0; visibility: hidden;
        transform: translateY(-10px);
        transition: all var(--transition-base);
        z-index: 1000;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    }
    .dropdown-menu.show { opacity: 1; visibility: visible; transform: translateY(0); }

    .dropdown-option {
        display: flex; align-items: center; gap: var(--spacing-sm);
        padding: var(--spacing-sm) var(--spacing-md);
        border-radius: var(--radius-md);
        cursor: pointer; transition: all var(--transition-fast); position: relative;
    }
    .dropdown-option:hover { background: rgba(255,255,255,0.05); }
    .dropdown-option .model-icon { font-size: var(--font-size-lg); }
    .dropdown-option span { flex: 1; color: var(--color-text-primary); font-size: var(--font-size-sm); }
    .dropdown-option .check-icon { opacity: 0; color: var(--color-accent-blue); }
    .dropdown-option.selected .check-icon { opacity: 1; }

    .results-container { width: 100%; margin-top: var(--spacing-2xl); display: none; }

    .prompt-display {
        background: var(--color-glass-bg);
        backdrop-filter: blur(20px);
        border: 1px solid var(--color-glass-border);
        border-radius: var(--radius-xl);
        padding: var(--spacing-lg);
        margin-bottom: var(--spacing-xl);
    }
    .prompt-label {
        font-size: var(--font-size-xs); font-weight: 600;
        color: var(--color-text-tertiary); letter-spacing: 0.1em;
        margin-bottom: var(--spacing-sm);
    }
    .prompt-text { font-size: var(--font-size-base); color: var(--color-text-primary); line-height: 1.6; }

    .comparison-grid { display: grid; gap: var(--spacing-lg); }

    .response-card {
        background: var(--color-glass-bg);
        backdrop-filter: blur(20px);
        border: 2px solid rgba(255,255,255,0.1);
        border-radius: var(--radius-xl);
        padding: var(--spacing-lg);
        animation: fadeIn 0.5s ease-out backwards;
        transition: all var(--transition-base);
    }
    .response-card:hover { transform: translateY(-5px); box-shadow: 0 0 30px rgba(124,58,237,0.3); }
    .response-card.voted { border-color: var(--color-accent-purple) !important; box-shadow: 0 0 40px rgba(124,58,237,0.5) !important; }

    .response-header {
        display: flex; align-items: center; gap: var(--spacing-sm);
        margin-bottom: var(--spacing-md); padding-bottom: var(--spacing-md);
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .response-icon { font-size: 1.5rem; }
    .response-title { flex: 1; }
    .response-model { font-size: var(--font-size-lg); font-weight: 600; color: var(--color-text-primary); }
    .response-slot { font-size: var(--font-size-xs); color: var(--color-text-tertiary); text-transform: uppercase; letter-spacing: 0.05em; }

    .response-content {
        padding: var(--spacing-md);
        background: rgba(10,14,26,0.5);
        border-radius: var(--radius-md);
        font-size: var(--font-size-sm); line-height: 1.6;
        color: var(--color-text-secondary);
        margin-bottom: var(--spacing-md);
        min-height: 120px; max-height: 400px; overflow-y: auto;
    }

    .response-footer { display: flex; flex-direction: column; gap: var(--spacing-md); }
    .response-stats {
        display: flex; justify-content: space-around; gap: var(--spacing-sm);
        padding: var(--spacing-sm);
        background: rgba(255,255,255,0.02); border-radius: var(--radius-md);
    }
    .stat-item { text-align: center; display: flex; flex-direction: column; gap: var(--spacing-xs); }
    .stat-value { font-size: var(--font-size-base); font-weight: 600; color: var(--color-text-primary); }
    .stat-label { font-size: var(--font-size-xs); color: var(--color-text-tertiary); }

    .vote-btn {
        width: 100%; display: flex; align-items: center; justify-content: center;
        gap: var(--spacing-xs); padding: var(--spacing-sm) var(--spacing-md);
        border-radius: var(--radius-md); font-size: var(--font-size-sm);
        font-weight: 600; color: white; transition: all var(--transition-base);
    }
    .vote-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }

    .response-error {
        padding: var(--spacing-md);
        background: rgba(220,38,38,0.1);
        border: 1px solid rgba(220,38,38,0.3);
        border-radius: var(--radius-md);
        color: #fca5a5; text-align: center; font-size: var(--font-size-sm);
    }

    .notification {
        position: fixed; bottom: var(--spacing-xl); right: var(--spacing-xl);
        padding: var(--spacing-md) var(--spacing-xl);
        background: var(--color-glass-bg); backdrop-filter: blur(20px);
        border: 1px solid var(--color-glass-border); border-radius: var(--radius-lg);
        color: var(--color-text-primary); font-size: var(--font-size-sm); font-weight: 500;
        box-shadow: var(--shadow-glass);
        opacity: 0; transform: translateY(20px);
        transition: all var(--transition-base); z-index: 1000;
    }
    .notification.show { opacity: 1; transform: translateY(0); }
    .notification.success { border-color: rgba(34,197,94,0.4); }
    .notification.error   { border-color: rgba(220,38,38,0.4); }

    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25%       { transform: translateX(-10px); }
        75%       { transform: translateX(10px); }
    }
    @keyframes spin {
        from { transform: rotate(0deg); }
        to   { transform: rotate(360deg); }
    }
    @keyframes fadeOut {
        from { opacity: 1; transform: translateY(0); }
        to   { opacity: 0; transform: translateY(-20px); }
    }
`;
document.head.appendChild(additionalStyles);
