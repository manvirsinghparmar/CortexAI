// ===== CONFIGURATION =====
const API_BASE_URL = 'http://localhost:5000/api';
let sessionId = 'default';

// Available models with their display names and identifiers
// IMPORTANT: These must match the model_type values supported by CortexOrchestrator
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
let activeModelCount = 2;  // Default to 2 models (Gemini + OpenAI - the ones with API keys)
let dropdownStates = {
    slot1: false,
    slot2: false,
    slot3: false
};

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

        // Create dropdown menu
        const menu = document.createElement('div');
        menu.className = 'dropdown-menu';
        menu.id = `dropdown-menu-${slotId}`;

        // Add model options
        AVAILABLE_MODELS.forEach(model => {
            const option = document.createElement('div');
            option.className = 'dropdown-option';
            option.innerHTML = `
                <div class="model-icon" style="color: ${model.color}">
                    ${model.icon}
                </div>
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

        // Insert menu after dropdown
        dropdown.parentElement.appendChild(menu);

        // Update initial selection
        updateDropdownDisplay(slotId, selectedModels[slotId]);
    });
}

function updateDropdownDisplay(slotId, model) {
    const slotIndex = parseInt(slotId.replace('slot', '')) - 1;
    const dropdown = modelDropdowns[slotIndex];

    if (dropdown) {
        const icon = dropdown.querySelector('.model-icon');
        const name = dropdown.querySelector('.model-name');

        if (icon) {
            icon.textContent = model.icon;
            icon.style.color = model.color;
        }
        if (name) {
            name.textContent = model.name;
        }
    }

    // Update menu checkmarks
    const menu = document.getElementById(`dropdown-menu-${slotId}`);
    if (menu) {
        const options = menu.querySelectorAll('.dropdown-option');
        options.forEach((option, i) => {
            if (AVAILABLE_MODELS[i].id === model.id) {
                option.classList.add('selected');
            } else {
                option.classList.remove('selected');
            }
        });
    }
}

function selectModel(slotId, model) {
    selectedModels[slotId] = model;
    updateDropdownDisplay(slotId, model);
    console.log(`Selected ${model.name} for ${slotId}`);
}

function toggleDropdown(slotId) {
    const menu = document.getElementById(`dropdown-menu-${slotId}`);
    const wasOpen = dropdownStates[slotId];

    // Close all dropdowns
    Object.keys(dropdownStates).forEach(id => {
        closeDropdown(id);
    });

    // Toggle this dropdown
    if (!wasOpen && menu) {
        menu.classList.add('show');
        dropdownStates[slotId] = true;
    }
}

function closeDropdown(slotId) {
    const menu = document.getElementById(`dropdown-menu-${slotId}`);
    if (menu) {
        menu.classList.remove('show');
        dropdownStates[slotId] = false;
    }
}

// Close dropdowns when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.model-dropdown') && !e.target.closest('.dropdown-menu')) {
        Object.keys(dropdownStates).forEach(closeDropdown);
    }
});

// ===== EVENT LISTENERS =====
function setupEventListeners() {
    // Compare button
    if (compareBtn) {
        compareBtn.addEventListener('click', handleCompareModels);
    }

    // Example cards
    exampleCards.forEach(card => {
        card.addEventListener('click', () => {
            const query = card.getAttribute('data-query');
            if (query && promptInput) {
                promptInput.value = query;
                promptInput.focus();

                card.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    card.style.transform = '';
                }, 150);
            }
        });
    });

    // Model count toggle buttons
    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const modelCount = parseInt(btn.getAttribute('data-models'));
            setActiveModelCount(modelCount);

            toggleBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });

    // Model dropdown interactions
    modelDropdowns.forEach((dropdown, index) => {
        const slotId = `slot${index + 1}`;
        dropdown.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleDropdown(slotId);
        });
    });

    // Keyboard shortcuts
    if (promptInput) {
        promptInput.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                handleCompareModels();
            }
        });
    }

    // Navigation buttons
    if (homeBtn) {
        homeBtn.addEventListener('click', resetToInitialState);
    }

    if (historyBtn) {
        historyBtn.addEventListener('click', () => {
            console.log('History clicked');
        });
    }
}

// ===== MODEL SELECTION =====
function setActiveModelCount(count) {
    activeModelCount = count;
    const slots = document.querySelectorAll('.model-slot');

    slots.forEach((slot, index) => {
        if (index < count) {
            slot.style.opacity = '1';
            slot.style.pointerEvents = 'auto';
        } else {
            slot.style.opacity = '0.4';
            slot.style.pointerEvents = 'none';
        }
    });

    console.log(`Active model count set to: ${count}`);
}

// ===== COMPARISON LOGIC =====
async function handleCompareModels() {
    const prompt = promptInput.value.trim();

    if (!prompt) {
        promptInput.style.animation = 'shake 0.3s';
        setTimeout(() => {
            promptInput.style.animation = '';
        }, 300);
        promptInput.focus();
        return;
    }

    console.log('Comparing models with prompt:', prompt);

    // Disable button and show loading state
    compareBtn.disabled = true;
    const originalText = compareBtn.innerHTML;
    compareBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" style="animation: spin 1s linear infinite;">
            <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="2" stroke-dasharray="15 10" fill="none"/>
        </svg>
        <span>Comparing...</span>
    `;

    try {
        // Get active models
        const modelsToCompare = getActiveModels();
        const modelIds = modelsToCompare.map(m => m.id);

        console.log('Selected models for comparison:', modelIds);

        // Call API
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: prompt,
                session_id: sessionId,
                compare_mode: true,
                models: modelIds  // Send selected model IDs
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to get comparison results');
        }

        const data = await response.json();
        console.log('Comparison results:', data);

        // Filter comparisons to match active model count
        let comparisons = data.comparisons || [];
        if (comparisons.length > 0) {
            // Limit to active model count
            comparisons = comparisons.slice(0, activeModelCount);

            // Update with selected model names
            comparisons.forEach((comp, index) => {
                const slotId = `slot${index + 1}`;
                const selectedModel = selectedModels[slotId];
                comp.displayName = selectedModel.name;
                comp.icon = selectedModel.icon;
                comp.color = selectedModel.color;
            });

            displayComparisonResults(comparisons, prompt);
        } else {
            // Fallback: create single model response
            displayComparisonResults([{
                displayName: selectedModels.slot1.name,
                icon: selectedModels.slot1.icon,
                color: selectedModels.slot1.color,
                model: selectedModels.slot1.id,
                response: data.response,
                tokens: data.stats?.tokens || 0,
                latency_ms: data.stats?.latency_ms || 0,
                cost: data.stats?.cost || 0,
                error: null
            }], prompt);
        }

    } catch (error) {
        console.error('Error comparing models:', error);
        showErrorNotification('Failed to compare models. Please try again.');
    } finally {
        // Reset button
        compareBtn.disabled = false;
        compareBtn.innerHTML = originalText;
    }
}

function getActiveModels() {
    const models = [];
    const slots = ['slot1', 'slot2', 'slot3'];

    for (let i = 0; i < activeModelCount; i++) {
        models.push(selectedModels[slots[i]]);
    }

    return models;
}

// ===== INLINE RESULTS DISPLAY =====
function displayComparisonResults(comparisons, prompt) {
    // Create or update results container
    let resultsContainer = document.getElementById('resultsContainer');
    if (!resultsContainer) {
        resultsContainer = document.createElement('div');
        resultsContainer.id = 'resultsContainer';
        resultsContainer.className = 'results-container';

        // Insert after prompt container
        const promptContainer = document.querySelector('.prompt-container');
        promptContainer.parentElement.insertBefore(resultsContainer, promptContainer.nextSibling);
    }

    // Build results HTML
    resultsContainer.innerHTML = `
        <div class="prompt-display">
            <div class="prompt-label">PROMPT:</div>
            <div class="prompt-text">${escapeHtml(prompt)}</div>
        </div>
        
        <div class="comparison-grid" style="grid-template-columns: repeat(${comparisons.length}, 1fr);">
            ${comparisons.map((comp, index) => createResponseCard(comp, index)).join('')}
        </div>
    `;

    // Animate in
    resultsContainer.style.display = 'block';
    resultsContainer.style.animation = 'fadeIn 0.5s ease-out';

    // Scroll to results
    setTimeout(() => {
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

function createResponseCard(comparison, index) {
    const slotNumber = index + 1;

    return `
        <div class="response-card" style="animation-delay: ${index * 0.1}s; border-color: ${comparison.color}20;">
            <div class="response-header">
                <div class="response-icon" style="color: ${comparison.color}">${comparison.icon}</div>
                <div class="response-title">
                    <div class="response-model">${comparison.displayName}</div>
                    <div class="response-slot">Slot ${slotNumber}</div>
                </div>
            </div>
            
            <div class="response-content">
                ${formatResponseText(comparison.response || comparison.error || 'No response')}
            </div>
            
            ${!comparison.error ? `
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
                    
                    <button class="vote-btn" onclick="voteForResponse(${index}, '${comparison.displayName}')" style="background: ${comparison.color};">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M8 2L10 6H14L11 9L12 13L8 10L4 13L5 9L2 6H6L8 2Z" fill="currentColor"/>
                        </svg>
                        Vote Best
                    </button>
                </div>
            ` : `
                <div class="response-error">
                    ⚠️ Error: ${comparison.error}
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
        return (num / 1000).toFixed(1) + 'k';
    }
    return num.toString();
}

// ===== UI ACTIONS =====
function resetToInitialState() {
    const resultsContainer = document.getElementById('resultsContainer');
    if (resultsContainer) {
        resultsContainer.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => {
            resultsContainer.style.display = 'none';
            resultsContainer.innerHTML = '';
        }, 300);
    }

    if (promptInput) {
        promptInput.value = '';
        promptInput.focus();
    }
}

function voteForResponse(index, modelName) {
    console.log(`Voted for ${modelName} (index ${index})`);
    showNotification(`Vote recorded for ${modelName}! 🎉`);

    const cards = document.querySelectorAll('.response-card');
    if (cards[index]) {
        cards[index].classList.add('voted');
        setTimeout(() => {
            cards[index].classList.remove('voted');
        }, 1000);
    }
}

// ===== NOTIFICATIONS =====
function showNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'notification success';
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => notification.classList.add('show'), 10);

    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function showErrorNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'notification error';
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => notification.classList.add('show'), 10);

    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// ===== STYLES (injected) =====
const additionalStyles = document.createElement('style');
additionalStyles.textContent = `
    /* Dropdown Menu Styles */
    .model-slot {
        position: relative;
    }
    
    .dropdown-menu {
        position: absolute;
        top: calc(100% + 8px);
        left: 0;
        right: 0;
        background: rgba(10, 14, 26, 0.95);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: var(--radius-lg);
        padding: var(--spacing-sm);
        opacity: 0;
        visibility: hidden;
        transform: translateY(-10px);
        transition: all var(--transition-base);
        z-index: 1000;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    }
    
    .dropdown-menu.show {
        opacity: 1;
        visibility: visible;
        transform: translateY(0);
    }
    
    .dropdown-option {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm) var(--spacing-md);
        border-radius: var(--radius-md);
        cursor: pointer;
        transition: all var(--transition-fast);
        position: relative;
    }
    
    .dropdown-option:hover {
        background: rgba(255, 255, 255, 0.05);
    }
    
    .dropdown-option .model-icon {
        font-size: var(--font-size-lg);
    }
    
    .dropdown-option span {
        flex: 1;
        color: var(--color-text-primary);
        font-size: var(--font-size-sm);
    }
    
    .dropdown-option .check-icon {
        opacity: 0;
        color: var(--color-accent-blue);
    }
    
    .dropdown-option.selected .check-icon {
        opacity: 1;
    }
    
    /* Results Container */
    .results-container {
        width: 100%;
        margin-top: var(--spacing-2xl);
        display: none;
    }
    
    .prompt-display {
        background: var(--color-glass-bg);
        backdrop-filter: blur(20px);
        border: 1px solid var(--color-glass-border);
        border-radius: var(--radius-xl);
        padding: var(--spacing-lg);
        margin-bottom: var(--spacing-xl);
    }
    
    .prompt-label {
        font-size: var(--font-size-xs);
        font-weight: 600;
        color: var(--color-text-tertiary);
        letter-spacing: 0.1em;
        margin-bottom: var(--spacing-sm);
    }
    
    .prompt-text {
        font-size: var(--font-size-base);
        color: var(--color-text-primary);
        line-height: 1.6;
    }
    
    .comparison-grid {
        display: grid;
        gap: var(--spacing-lg);
    }
    
    .response-card {
        background: var(--color-glass-bg);
        backdrop-filter: blur(20px);
        border: 2px solid rgba(255, 255, 255, 0.1);
        border-radius: var(--radius-xl);
        padding: var(--spacing-lg);
        animation: fadeIn 0.5s ease-out backwards;
        transition: all var(--transition-base);
    }
    
    .response-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 0 30px rgba(124, 58, 237, 0.3);
    }
    
    .response-card.voted {
        border-color: var(--color-accent-purple) !important;
        box-shadow: 0 0 40px rgba(124, 58, 237, 0.5) !important;
    }
    
    .response-header {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        margin-bottom: var(--spacing-md);
        padding-bottom: var(--spacing-md);
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .response-icon {
        font-size: 1.5rem;
    }
    
    .response-title {
        flex: 1;
    }
    
    .response-model {
        font-size: var(--font-size-lg);
        font-weight: 600;
        color: var(--color-text-primary);
    }
    
    .response-slot {
        font-size: var(--font-size-xs);
        color: var(--color-text-tertiary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .response-content {
        padding: var(--spacing-md);
        background: rgba(10, 14, 26, 0.5);
        border-radius: var(--radius-md);
        font-size: var(--font-size-sm);
        line-height: 1.6;
        color: var(--color-text-secondary);
        margin-bottom: var(--spacing-md);
        min-height: 120px;
        max-height: 400px;
        overflow-y: auto;
    }
    
    .response-footer {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
    }
    
    .response-stats {
        display: flex;
        justify-content: space-around;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm);
        background: rgba(255, 255, 255, 0.02);
        border-radius: var(--radius-md);
    }
    
    .stat-item {
        text-align: center;
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
    }
    
    .stat-value {
        font-size: var(--font-size-base);
        font-weight: 600;
        color: var(--color-text-primary);
    }
    
    .stat-label {
        font-size: var(--font-size-xs);
        color: var(--color-text-tertiary);
    }
    
    .vote-btn {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--spacing-xs);
        padding: var(--spacing-sm) var(--spacing-md);
        border-radius: var(--radius-md);
        font-size: var(--font-size-sm);
        font-weight: 600;
        color: white;
        transition: all var(--transition-base);
    }
    
    .vote-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    .response-error {
        padding: var(--spacing-md);
        background: rgba(220, 38, 38, 0.1);
        border: 1px solid rgba(220, 38, 38, 0.3);
        border-radius: var(--radius-md);
        color: #fca5a5;
        text-align: center;
        font-size: var(--font-size-sm);
    }
    
    /* Notifications */
    .notification {
        position: fixed;
        bottom: var(--spacing-xl);
        right: var(--spacing-xl);
        padding: var(--spacing-md) var(--spacing-xl);
        background: var(--color-glass-bg);
        backdrop-filter: blur(20px);
        border: 1px solid var(--color-glass-border);
        border-radius: var(--radius-lg);
        color: var(--color-text-primary);
        font-size: var(--font-size-sm);
        font-weight: 500;
        box-shadow: var(--shadow-glass);
        opacity: 0;
        transform: translateY(20px);
        transition: all var(--transition-base);
        z-index: 1000;
    }
    
    .notification.show {
        opacity: 1;
        transform: translateY(0);
    }
    
    .notification.success {
        border-color: rgba(34, 197, 94, 0.4);
    }
    
    .notification.error {
        border-color: rgba(220, 38, 38, 0.4);
    }
    
    /* Animations */
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-10px); }
        75% { transform: translateX(10px); }
    }
    
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    @keyframes fadeOut {
        from { opacity: 1; transform: translateY(0); }
        to { opacity: 0; transform: translateY(-20px); }
    }
`;
document.head.appendChild(additionalStyles);
