const AVAILABLE_MODELS = [
    { id: 'openai', name: 'OpenAI GPT', icon: 'OA', color: '#10a37f', defaultModel: 'gpt-4o-mini' },
    { id: 'gemini', name: 'Gemini', icon: 'GM', color: '#4285f4', defaultModel: 'gemini-2.5-flash-lite' },
    { id: 'deepseek', name: 'DeepSeek', icon: 'DS', color: '#8b5cf6', defaultModel: 'deepseek-chat' },
    { id: 'grok', name: 'Grok', icon: 'GK', color: '#06b6d4', defaultModel: 'grok-4-1-fast-non-reasoning' }
];

const STORAGE = {
    apiKey: 'cortex_api_key',
    apiBaseUrl: 'cortex_api_base_url',
    sessionId: 'cortex_session_id',
    mode: 'cortex_mode',
    smartRouting: 'cortex_smart_routing',
    promptOptimization: 'cortex_prompt_optimization',
    research: 'cortex_research'
};

function resolveApiBaseUrl() {
    const configuredBase = localStorage.getItem(STORAGE.apiBaseUrl);
    if (configuredBase) {
        return configuredBase.replace(/\/$/, '');
    }

    if (
        (window.location.protocol === 'http:' || window.location.protocol === 'https:')
        && window.location.port === '8000'
    ) {
        return `${window.location.origin}/v1`;
    }
    return 'http://127.0.0.1:8000/v1';
}

const API_BASE_URL = resolveApiBaseUrl();

let selectedModels = {
    slot1: AVAILABLE_MODELS[0],
    slot2: AVAILABLE_MODELS[1]
};

let dropdownStates = {
    slot1: false,
    slot2: false
};

let appMode = loadMode();
let smartRoutingEnabled = loadBoolean(STORAGE.smartRouting, true);
let promptOptimizationEnabled = loadBoolean(STORAGE.promptOptimization, false);
let researchEnabled = loadBoolean(STORAGE.research, false);
let sessionId = loadOrCreateSessionId();
let conversationHistory = [];

const promptInput = document.getElementById('promptInput');
const compareBtn = document.getElementById('compareBtn');
const submitBtnLabel = document.getElementById('submitBtnLabel');
const exampleCards = document.querySelectorAll('.example-card');
const modelDropdowns = document.querySelectorAll('.model-dropdown');
const homeBtn = document.getElementById('homeBtn');
const historyBtn = document.getElementById('historyBtn');
const singleModeBtn = document.getElementById('singleModeBtn');
const compareModeBtn = document.getElementById('compareModeBtn');
const modeHint = document.getElementById('modeHint');
const slot1Label = document.getElementById('slot1Label');
const slot2Container = document.getElementById('slot2Container');
const apiKeyInput = document.getElementById('apiKeyInput');
const smartRoutingToggle = document.getElementById('smartRoutingToggle');
const smartRoutingRow = document.getElementById('smartRoutingRow');
const promptOptToggle = document.getElementById('promptOptToggle');
const researchToggle = document.getElementById('researchToggle');

document.addEventListener('DOMContentLoaded', () => {
    hydrateControls();
    createDropdownMenus();
    setupEventListeners();
    applyModeUi();
});

function hydrateControls() {
    apiKeyInput.value = localStorage.getItem(STORAGE.apiKey) || 'dev-key-1';
    smartRoutingToggle.checked = smartRoutingEnabled;
    promptOptToggle.checked = promptOptimizationEnabled;
    researchToggle.checked = researchEnabled;
}

function setupEventListeners() {
    if (compareBtn) {
        compareBtn.addEventListener('click', handleSubmit);
    }

    exampleCards.forEach((card) => {
        card.addEventListener('click', () => {
            const query = card.getAttribute('data-query');
            if (query && promptInput) {
                promptInput.value = query;
                promptInput.focus();
            }
        });
    });

    modelDropdowns.forEach((dropdown) => {
        dropdown.addEventListener('click', (e) => {
            e.stopPropagation();
            if (dropdown.classList.contains('disabled')) {
                return;
            }
            const slot = dropdown.getAttribute('data-slot');
            toggleDropdown(`slot${slot}`);
        });
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.model-dropdown') && !e.target.closest('.dropdown-menu')) {
            Object.keys(dropdownStates).forEach(closeDropdown);
        }
    });

    if (promptInput) {
        promptInput.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                handleSubmit();
            }
        });
    }

    if (homeBtn) {
        homeBtn.addEventListener('click', resetToInitialState);
    }

    if (historyBtn) {
        historyBtn.addEventListener('click', () => {
            showNotification(`Stored turns: ${Math.floor(conversationHistory.length / 2)}`);
        });
    }

    singleModeBtn.addEventListener('click', () => setMode('single'));
    compareModeBtn.addEventListener('click', () => setMode('compare'));

    apiKeyInput.addEventListener('change', () => {
        localStorage.setItem(STORAGE.apiKey, apiKeyInput.value.trim());
    });

    smartRoutingToggle.addEventListener('change', () => {
        smartRoutingEnabled = smartRoutingToggle.checked;
        localStorage.setItem(STORAGE.smartRouting, String(smartRoutingEnabled));
        applyModeUi();
    });

    promptOptToggle.addEventListener('change', () => {
        promptOptimizationEnabled = promptOptToggle.checked;
        localStorage.setItem(STORAGE.promptOptimization, String(promptOptimizationEnabled));
    });

    researchToggle.addEventListener('change', () => {
        researchEnabled = researchToggle.checked;
        localStorage.setItem(STORAGE.research, String(researchEnabled));
    });
}

function setMode(mode) {
    appMode = mode;
    localStorage.setItem(STORAGE.mode, mode);
    applyModeUi();
}

function applyModeUi() {
    const isSingle = appMode === 'single';

    singleModeBtn.classList.toggle('active', isSingle);
    compareModeBtn.classList.toggle('active', !isSingle);

    smartRoutingRow.classList.toggle('is-hidden', !isSingle);

    const slot1 = document.querySelector('.model-slot[data-slot="1"]');
    const showManualSingleModel = isSingle && !smartRoutingEnabled;

    slot1.classList.toggle('is-hidden', isSingle && !showManualSingleModel);
    slot2Container.classList.toggle('is-hidden', isSingle);

    const slot1Dropdown = document.querySelector('.model-dropdown[data-slot="1"]');
    if (slot1Dropdown) {
        slot1Dropdown.classList.toggle('disabled', isSingle && smartRoutingEnabled);
    }

    if (isSingle) {
        submitBtnLabel.textContent = 'Send Message';
        promptInput.placeholder = smartRoutingEnabled
            ? 'Ask anything. Smart routing is ON.'
            : 'Ask anything. Manual model mode is ON.';

        if (smartRoutingEnabled) {
            modeHint.textContent = 'Single mode uses /v1/chat with smart routing ON by default.';
        } else {
            modeHint.textContent = 'Single mode uses /v1/chat with explicit provider/model selection.';
        }

        slot1Label.textContent = 'PRIMARY MODEL (manual mode)';
    } else {
        submitBtnLabel.textContent = 'Compare 2 Models';
        promptInput.placeholder = 'Compare two models side by side using /v1/compare.';
        modeHint.textContent = 'Compare mode calls /v1/compare with exactly two models. Smart routing is disabled here.';
        slot1Label.textContent = 'COMPARE MODEL 1';
    }
}

function createDropdownMenus() {
    modelDropdowns.forEach((dropdown, index) => {
        const slotId = `slot${index + 1}`;
        const menu = document.createElement('div');
        menu.className = 'dropdown-menu';
        menu.id = `dropdown-menu-${slotId}`;

        AVAILABLE_MODELS.forEach((model) => {
            const option = document.createElement('div');
            option.className = 'dropdown-option';
            option.innerHTML = `
                <div class="model-icon" style="color: ${model.color}">${model.icon}</div>
                <span>${escapeHtml(model.name)} <small>(${escapeHtml(model.defaultModel)})</small></span>
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
    const slotIndex = Number.parseInt(slotId.replace('slot', ''), 10) - 1;
    const dropdown = modelDropdowns[slotIndex];
    if (!dropdown) {
        return;
    }

    const icon = dropdown.querySelector('.model-icon');
    const name = dropdown.querySelector('.model-name');

    if (icon) {
        icon.textContent = model.icon;
        icon.style.color = model.color;
    }

    if (name) {
        name.textContent = model.name;
    }

    const menu = document.getElementById(`dropdown-menu-${slotId}`);
    if (menu) {
        const options = menu.querySelectorAll('.dropdown-option');
        options.forEach((option, optionIndex) => {
            option.classList.toggle('selected', AVAILABLE_MODELS[optionIndex].id === model.id);
        });
    }
}

function selectModel(slotId, model) {
    selectedModels[slotId] = model;
    updateDropdownDisplay(slotId, model);
}

function toggleDropdown(slotId) {
    const wasOpen = dropdownStates[slotId];
    Object.keys(dropdownStates).forEach(closeDropdown);
    if (!wasOpen) {
        const menu = document.getElementById(`dropdown-menu-${slotId}`);
        if (menu) {
            menu.classList.add('show');
            dropdownStates[slotId] = true;
        }
    }
}

function closeDropdown(slotId) {
    const menu = document.getElementById(`dropdown-menu-${slotId}`);
    if (menu) {
        menu.classList.remove('show');
    }
    dropdownStates[slotId] = false;
}

async function handleSubmit() {
    const prompt = promptInput.value.trim();
    const apiKey = apiKeyInput.value.trim();

    if (!prompt) {
        promptInput.focus();
        showErrorNotification('Prompt is required.');
        return;
    }

    if (!apiKey) {
        apiKeyInput.focus();
        showErrorNotification('API key is required.');
        return;
    }

    compareBtn.disabled = true;
    const originalText = submitBtnLabel.textContent;
    submitBtnLabel.textContent = appMode === 'compare' ? 'Comparing...' : 'Sending...';

    try {
        const { endpoint, payload } = buildRequest(prompt);
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': apiKey,
                'X-Request-ID': generateRequestId()
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(resolveErrorMessage(data));
        }

        const cards = appMode === 'compare'
            ? mapCompareResponse(data)
            : mapSingleResponse(data);

        displayComparisonResults(cards, prompt);
        updateConversation(prompt, cards);
    } catch (error) {
        showErrorNotification(error.message || 'Request failed.');
    } finally {
        compareBtn.disabled = false;
        submitBtnLabel.textContent = originalText;
    }
}

function buildRequest(prompt) {
    const common = {
        prompt,
        research_mode: researchEnabled ? 'on' : 'off',
        prompt_optimization_enabled: promptOptimizationEnabled,
        context: buildRequestContext()
    };

    if (appMode === 'compare') {
        return {
            endpoint: `${API_BASE_URL}/compare`,
            payload: {
                ...common,
                timeout_s: 60,
                targets: [
                    {
                        provider: selectedModels.slot1.id,
                        model: selectedModels.slot1.defaultModel
                    },
                    {
                        provider: selectedModels.slot2.id,
                        model: selectedModels.slot2.defaultModel
                    }
                ]
            }
        };
    }

    const payload = {
        ...common,
        routing_mode: 'smart'
    };

    if (!smartRoutingEnabled) {
        payload.provider = selectedModels.slot1.id;
        payload.model = selectedModels.slot1.defaultModel;
    }

    return {
        endpoint: `${API_BASE_URL}/chat`,
        payload
    };
}

function buildRequestContext() {
    const trimmedHistory = conversationHistory.slice(-10);
    return {
        conversation_history: trimmedHistory
    };
}

function mapSingleResponse(data) {
    const providerId = data.provider || selectedModels.slot1.id;
    const providerMeta = AVAILABLE_MODELS.find((model) => model.id === providerId) || selectedModels.slot1;
    return [
        {
            displayName: providerMeta.name,
            icon: providerMeta.icon,
            color: providerMeta.color,
            model: data.model || providerMeta.defaultModel,
            response: data.text || '',
            tokens: data.token_usage?.total_tokens || 0,
            latency_ms: data.latency_ms || 0,
            cost: data.estimated_cost || 0,
            error: data.error?.message || null,
            request_id: data.request_id || ''
        }
    ];
}

function mapCompareResponse(data) {
    const responses = Array.isArray(data.responses) ? data.responses : [];
    if (responses.length === 0) {
        return [{
            displayName: 'Compare',
            icon: 'NA',
            color: '#9ca3af',
            model: 'n/a',
            response: '',
            tokens: 0,
            latency_ms: 0,
            cost: 0,
            error: 'No compare responses returned.',
            request_id: ''
        }];
    }

    return responses.slice(0, 2).map((item, index) => {
        const slotModel = index === 0 ? selectedModels.slot1 : selectedModels.slot2;
        return {
            displayName: slotModel.name,
            icon: slotModel.icon,
            color: slotModel.color,
            model: item.model || slotModel.defaultModel,
            response: item.text || '',
            tokens: item.token_usage?.total_tokens || 0,
            latency_ms: item.latency_ms || 0,
            cost: item.estimated_cost || 0,
            error: item.error?.message || null,
            request_id: item.request_id || ''
        };
    });
}

function updateConversation(prompt, cards) {
    const firstSuccess = cards.find((card) => !card.error && card.response);
    conversationHistory.push({ role: 'user', content: prompt });
    if (firstSuccess) {
        conversationHistory.push({ role: 'assistant', content: firstSuccess.response });
    }

    if (conversationHistory.length > 20) {
        conversationHistory = conversationHistory.slice(-20);
    }
}

function displayComparisonResults(comparisons, prompt) {
    let resultsContainer = document.getElementById('resultsContainer');
    if (!resultsContainer) {
        resultsContainer = document.createElement('div');
        resultsContainer.id = 'resultsContainer';
        resultsContainer.className = 'results-container';

        const promptContainer = document.querySelector('.prompt-container');
        promptContainer.parentElement.insertBefore(resultsContainer, promptContainer.nextSibling);
    }

    resultsContainer.innerHTML = `
        <div class="prompt-display">
            <div class="prompt-label">PROMPT</div>
            <div class="prompt-text">${escapeHtml(prompt)}</div>
        </div>
        <div class="comparison-grid" style="grid-template-columns: repeat(${comparisons.length}, 1fr);">
            ${comparisons.map((comp, index) => createResponseCard(comp, index)).join('')}
        </div>
    `;

    resultsContainer.style.display = 'block';
    resultsContainer.style.animation = 'fadeIn 0.4s ease-out';

    setTimeout(() => {
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 60);
}

function createResponseCard(comparison, index) {
    return `
        <div class="response-card" style="animation-delay: ${index * 0.08}s; border-color: ${comparison.color}20;">
            <div class="response-header">
                <div class="response-icon" style="color: ${comparison.color}">${escapeHtml(comparison.icon)}</div>
                <div class="response-title">
                    <div class="response-model">${escapeHtml(comparison.displayName)}</div>
                    <div class="response-slot">${escapeHtml(comparison.model)}</div>
                </div>
            </div>
            <div class="response-content">${formatResponseText(comparison.response || comparison.error || 'No response')}</div>
            ${comparison.request_id ? `<div class="request-id">request_id: ${escapeHtml(comparison.request_id)}</div>` : ''}
            ${comparison.error ? `
                <div class="response-error">Error: ${escapeHtml(comparison.error)}</div>
            ` : `
                <div class="response-footer">
                    <div class="response-stats">
                        <div class="stat-item">
                            <span class="stat-value">${formatNumber(comparison.tokens || 0)}</span>
                            <span class="stat-label">tokens</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">${comparison.latency_ms || 0}ms</span>
                            <span class="stat-label">latency</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">$${(comparison.cost || 0).toFixed(6)}</span>
                            <span class="stat-label">cost</span>
                        </div>
                    </div>
                </div>
            `}
        </div>
    `;
}

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
    if (num >= 1000) {
        return `${(num / 1000).toFixed(1)}k`;
    }
    return String(num);
}

function resolveErrorMessage(data) {
    if (!data) {
        return 'Request failed.';
    }
    if (typeof data.detail === 'string') {
        return data.detail;
    }
    if (typeof data.error === 'string') {
        return data.error;
    }
    if (data.error && typeof data.error.message === 'string') {
        return data.error.message;
    }
    return 'Request failed.';
}

function resetToInitialState() {
    const resultsContainer = document.getElementById('resultsContainer');
    if (resultsContainer) {
        resultsContainer.remove();
    }

    promptInput.value = '';
    promptInput.focus();
    conversationHistory = [];
    sessionId = createSessionId();
    localStorage.setItem(STORAGE.sessionId, sessionId);
}

function showNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'notification success';
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => notification.classList.add('show'), 10);
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 250);
    }, 2200);
}

function showErrorNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'notification error';
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => notification.classList.add('show'), 10);
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 250);
    }, 2800);
}

function loadMode() {
    const saved = localStorage.getItem(STORAGE.mode);
    return saved === 'compare' ? 'compare' : 'single';
}

function loadBoolean(key, fallback) {
    const value = localStorage.getItem(key);
    if (value === null) {
        return fallback;
    }
    return value === 'true';
}

function loadOrCreateSessionId() {
    const existing = localStorage.getItem(STORAGE.sessionId);
    if (existing) {
        return existing;
    }
    const newId = createSessionId();
    localStorage.setItem(STORAGE.sessionId, newId);
    return newId;
}

function createSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        return window.crypto.randomUUID();
    }
    return `session-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
}

function generateRequestId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        return window.crypto.randomUUID();
    }
    return `req-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
}
