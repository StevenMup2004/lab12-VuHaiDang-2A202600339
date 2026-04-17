/**
 * Travel Planning Agent — Frontend Application
 * Handles chat interface, mode switching, and ReAct trace visualization
 */

// ======== STATE ========
const state = {
    currentMode: 'agent_v2',
    isLoading: false,
    messages: [],
    testCases: []
};

// ======== DOM ELEMENTS ========
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const elements = {
    messageInput: $('#messageInput'),
    sendBtn: $('#sendBtn'),
    messagesContainer: $('#messagesContainer'),
    messages: $('#messages'),
    headerMode: $('#headerMode'),
    inputModeIndicator: $('#inputModeIndicator'),
    testCases: $('#testCases'),
    rightPanel: $('#rightPanel'),
    panelContent: $('#panelContent'),
    sidebar: $('#sidebar'),
    menuToggle: $('#menuToggle'),
    closePanel: $('#closePanel'),
    clearChat: $('#clearChat')
};

// ======== INITIALIZATION ========
document.addEventListener('DOMContentLoaded', () => {
    initModeSelector();
    initInput();
    loadTestCases();
    initSidebar();
    initPanel();
});

// ======== MODE SELECTOR ========
function initModeSelector() {
    $$('.mode-card').forEach(card => {
        card.addEventListener('click', () => {
            const mode = card.dataset.mode;
            setMode(mode);
        });
    });
}

function setMode(mode) {
    state.currentMode = mode;
    
    // Update UI
    $$('.mode-card').forEach(c => c.classList.remove('active'));
    $(`.mode-card[data-mode="${mode}"]`).classList.add('active');
    
    const modeLabels = {
        'chatbot': { name: 'Chatbot Baseline', icon: '💬', status: 'No tools' },
        'agent_v1': { name: 'Agent v1', icon: '🤖', status: 'Basic ReAct' },
        'agent_v2': { name: 'Agent v2', icon: '🚀', status: 'Improved + Guardrails' }
    };
    
    const label = modeLabels[mode];
    elements.headerMode.textContent = `${label.name} — ${label.status}`;
    elements.inputModeIndicator.textContent = `${label.icon} ${label.name}`;
}

// ======== INPUT HANDLING ========
function initInput() {
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    elements.sendBtn.addEventListener('click', sendMessage);
    
    // Auto-resize textarea
    elements.messageInput.addEventListener('input', () => {
        elements.messageInput.style.height = 'auto';
        elements.messageInput.style.height = Math.min(elements.messageInput.scrollHeight, 120) + 'px';
    });
    
    elements.clearChat.addEventListener('click', clearChat);
}

// ======== SEND MESSAGE ========
async function sendMessage() {
    const text = elements.messageInput.value.trim();
    if (!text || state.isLoading) return;
    
    state.isLoading = true;
    elements.sendBtn.disabled = true;
    elements.messageInput.value = '';
    elements.messageInput.style.height = 'auto';
    
    // Add user message
    addMessage('user', text);
    
    // Show typing indicator
    const typingEl = showTypingIndicator();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                mode: state.currentMode
            })
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Server error');
        }
        
        const data = await response.json();
        
        // Remove typing indicator
        typingEl.remove();
        
        // Add bot response
        addBotResponse(data);
        
        // Update right panel
        updateRightPanel(data);
        
    } catch (error) {
        typingEl.remove();
        addMessage('bot', `❌ Error: ${error.message}`, { isError: true });
    } finally {
        state.isLoading = false;
        elements.sendBtn.disabled = false;
        elements.messageInput.focus();
    }
}

// ======== MESSAGES ========
function addMessage(type, text, options = {}) {
    const messageEl = document.createElement('div');
    messageEl.className = `message ${type === 'user' ? 'user-message' : 'bot-message'}`;
    
    const avatar = type === 'user' ? '👤' : '🌍';
    
    messageEl.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-bubble">
                <div class="answer-text">${escapeHtml(text)}</div>
            </div>
        </div>
    `;
    
    elements.messages.appendChild(messageEl);
    scrollToBottom();
}

function addBotResponse(data) {
    const messageEl = document.createElement('div');
    messageEl.className = 'message bot-message';
    
    const modeLabel = {
        'chatbot': '💬 Chatbot',
        'agent_v1': '🤖 Agent v1',
        'agent_v2': '🚀 Agent v2'
    }[data.mode] || data.mode;
    
    let stepsHtml = '';
    if (data.steps && data.steps.length > 0) {
        stepsHtml = `
            <div class="steps-toggle">
                <button class="steps-toggle-btn" onclick="toggleSteps(this)">
                    🔍 View ReAct Trace (${data.steps.length} steps)
                </button>
                <div class="steps-detail">
                    ${data.steps.map(s => `
                        <div class="step-item">
                            <span class="step-type ${s.type}">${getStepLabel(s.type)}</span>
                            <span class="step-content">${escapeHtml(s.content || '').substring(0, 300)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    const metrics = data.metrics || {};
    const metricsHtml = `
        <div class="metrics-bar">
            <span class="metric-chip" title="Total latency">
                <span class="metric-icon">⚡</span> ${metrics.latency_ms || 0}ms
            </span>
            <span class="metric-chip" title="Total tokens">
                <span class="metric-icon">🔤</span> ${metrics.total_tokens || 0} tokens
            </span>
            <span class="metric-chip" title="Steps count">
                <span class="metric-icon">🔄</span> ${metrics.steps_count || 0} steps
            </span>
            <span class="metric-chip" title="Mode">
                <span class="metric-icon">🏷️</span> ${modeLabel}
            </span>
        </div>
    `;
    
    messageEl.innerHTML = `
        <div class="message-avatar">🌍</div>
        <div class="message-content">
            <div class="message-bubble">
                <div class="answer-text">${formatAnswer(data.answer)}</div>
            </div>
            ${metricsHtml}
            ${stepsHtml}
        </div>
    `;
    
    elements.messages.appendChild(messageEl);
    scrollToBottom();
}

function formatAnswer(text) {
    if (!text) return '';
    // Basic markdown-like formatting
    let html = escapeHtml(text);
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    return html;
}

function getStepLabel(type) {
    const labels = {
        'thought': '💭 Think',
        'action': '⚡ Action',
        'observation': '👁️ Observe',
        'final_answer': '🎯 Answer',
        'error': '❌ Error',
        'retry': '🔄 Retry'
    };
    return labels[type] || type;
}

function toggleSteps(btn) {
    const detail = btn.parentElement.querySelector('.steps-detail');
    detail.classList.toggle('open');
    btn.textContent = detail.classList.contains('open') 
        ? '🔍 Hide ReAct Trace' 
        : `🔍 View ReAct Trace`;
}

function showTypingIndicator() {
    const el = document.createElement('div');
    el.className = 'typing-indicator';
    el.innerHTML = `
        <div class="message-avatar">🌍</div>
        <div>
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
            <div class="typing-text">Agent is reasoning...</div>
        </div>
    `;
    elements.messages.appendChild(el);
    scrollToBottom();
    return el;
}

function clearChat() {
    // Keep only the welcome message
    const welcomeMsg = elements.messages.querySelector('.welcome-message');
    elements.messages.innerHTML = '';
    if (welcomeMsg) elements.messages.appendChild(welcomeMsg);
    
    // Clear right panel
    elements.panelContent.innerHTML = `
        <div class="panel-empty">
            <div class="panel-empty-icon">🔍</div>
            <p>Send a message to see the agent's reasoning trace here</p>
        </div>
    `;
}

function scrollToBottom() {
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

// ======== RIGHT PANEL ========
function initPanel() {
    elements.closePanel.addEventListener('click', () => {
        elements.rightPanel.classList.remove('open');
    });
}

function updateRightPanel(data) {
    if (!data.steps || data.steps.length === 0) {
        elements.panelContent.innerHTML = `
            <div class="panel-empty">
                <div class="panel-empty-icon">💬</div>
                <p>Chatbot mode doesn't use the ReAct loop — no trace to show.</p>
            </div>
        `;
        return;
    }
    
    const metrics = data.metrics || {};
    
    let html = `
        <div class="panel-metrics">
            <div class="panel-metric-card">
                <div class="metric-label">Latency</div>
                <div class="metric-value blue">${metrics.latency_ms || 0}<span style="font-size:11px">ms</span></div>
            </div>
            <div class="panel-metric-card">
                <div class="metric-label">Tokens</div>
                <div class="metric-value emerald">${metrics.total_tokens || 0}</div>
            </div>
            <div class="panel-metric-card">
                <div class="metric-label">Steps</div>
                <div class="metric-value amber">${metrics.steps_count || 0}</div>
            </div>
            <div class="panel-metric-card">
                <div class="metric-label">Cost Est.</div>
                <div class="metric-value purple">$${((metrics.total_tokens || 0) / 1000 * 0.01).toFixed(4)}</div>
            </div>
        </div>
        
        <div class="panel-steps-title">Reasoning Trace</div>
    `;
    
    data.steps.forEach((step, i) => {
        html += `
            <div class="panel-step ${step.type}" style="animation-delay: ${i * 0.1}s">
                <div class="panel-step-type">${getStepLabel(step.type)} ${step.tool ? `— ${step.tool}` : ''}</div>
                <div class="panel-step-content">${escapeHtml((step.content || '').substring(0, 500))}</div>
            </div>
        `;
    });
    
    elements.panelContent.innerHTML = html;
    
    // Open panel on mobile
    if (window.innerWidth <= 1200) {
        elements.rightPanel.classList.add('open');
    }
}

// ======== TEST CASES ========
async function loadTestCases() {
    try {
        const response = await fetch('/api/test-cases');
        const cases = await response.json();
        state.testCases = cases;
        
        elements.testCases.innerHTML = cases.map((tc, i) => `
            <button class="test-case-btn" onclick="useTestCase(${i})" title="${tc.query}">
                <span style="flex:1">${tc.name}</span>
                <span class="test-case-type">${tc.type}</span>
            </button>
        `).join('');
    } catch (e) {
        elements.testCases.innerHTML = '<p style="color:var(--text-muted);font-size:11px">Could not load test cases</p>';
    }
}

function useTestCase(index) {
    const tc = state.testCases[index];
    if (tc) {
        elements.messageInput.value = tc.query;
        elements.messageInput.style.height = 'auto';
        elements.messageInput.style.height = Math.min(elements.messageInput.scrollHeight, 120) + 'px';
        elements.messageInput.focus();
        
        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            elements.sidebar.classList.remove('open');
            document.querySelector('.sidebar-overlay')?.classList.remove('active');
        }
    }
}

// ======== SIDEBAR ========
function initSidebar() {
    elements.menuToggle.addEventListener('click', () => {
        elements.sidebar.classList.toggle('open');
        
        // Create overlay if needed
        let overlay = document.querySelector('.sidebar-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'sidebar-overlay';
            document.body.appendChild(overlay);
            overlay.addEventListener('click', () => {
                elements.sidebar.classList.remove('open');
                overlay.classList.remove('active');
            });
        }
        overlay.classList.toggle('active');
    });
}

// ======== UTILITIES ========
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Make toggleSteps globally accessible
window.toggleSteps = toggleSteps;
window.useTestCase = useTestCase;
