/**
 * AI Tutor Panel - Socratic tutoring integration
 * 
 * ZDS-ID: TOOL-405 (Teacher-in-the-Loop)
 * 
 * Features:
 * - Slide-out panel with chat interface
 * - Context-aware questions (solver state)
 * - Screenshot capture for vision
 * - Streaming response display
 */

class AITutorPanel {
    constructor(options = {}) {
        this.apiBaseUrl = options.apiUrl || 'http://127.0.0.1:8000';
        this.solverState = null;
        this.history = [];
        this.isOpen = false;
        this.isStreaming = false;
        this.pendingScreenshot = null;  // Stores captured screenshot until sent
        
        this.init();
    }
    
    init() {
        this.createPanel();
        this.attachStyles();
        this.bindEvents();
    }
    
    createPanel() {
        // Create panel HTML
        const panel = document.createElement('div');
        panel.id = 'ai-tutor-panel';
        panel.className = 'ai-tutor-panel';
        panel.innerHTML = `
            <div class="tutor-header">
                <span class="tutor-title">🎓 Calculus Tutor</span>
                <select id="tutor-provider-select" class="tutor-provider-select" title="AI Provider">
                    <option value="deepseek">DeepSeek</option>
                    <option value="google">Gemini API</option>
                    <option value="gemini_cli">Gemini CLI</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="local">Local (Ollama)</option>
                </select>
                <button class="tutor-close" id="tutor-close">×</button>
            </div>
            <div class="tutor-messages" id="tutor-messages"></div>
            <div class="tutor-input-area">
                <div class="tutor-context" id="tutor-context"></div>
                <div class="tutor-screenshot-indicator" id="tutor-screenshot-indicator" style="display: none;">
                    <span class="screenshot-badge">📷 Screenshot attached</span>
                    <button class="screenshot-remove" id="tutor-remove-screenshot" title="Remove screenshot">×</button>
                </div>
                <div class="tutor-input-row">
                    <input 
                        type="text" 
                        id="tutor-input" 
                        class="tutor-input" 
                        placeholder="Ask about this step..."
                        autocomplete="off"
                    />
                    <button class="tutor-send" id="tutor-send">Ask</button>
                </div>
                <div class="tutor-actions">
                    <button class="tutor-action-btn" id="tutor-screenshot" title="Attach screenshot">
                        📷 Attach Screenshot
                    </button>
                    <button class="tutor-action-btn" id="tutor-clear" title="Clear conversation">
                        🗑️ Clear
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(panel);
        
        // Create toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.id = 'tutor-toggle';
        toggleBtn.className = 'tutor-toggle';
        toggleBtn.innerHTML = '🎓';
        toggleBtn.title = 'AI Tutor (press ?)';
        document.body.appendChild(toggleBtn);
        
        this.panel = panel;
        this.toggleBtn = toggleBtn;
        this.messagesContainer = document.getElementById('tutor-messages');
        this.inputField = document.getElementById('tutor-input');
        this.contextDisplay = document.getElementById('tutor-context');
        this.screenshotIndicator = document.getElementById('tutor-screenshot-indicator');
        this.providerSelect = document.getElementById('tutor-provider-select');
    }
    
    attachStyles() {
        // Add styles if not already present
        if (document.getElementById('ai-tutor-styles')) return;
        
        const styles = document.createElement('style');
        styles.id = 'ai-tutor-styles';
        styles.textContent = `
            .ai-tutor-panel {
                position: fixed;
                right: -400px;
                top: 0;
                width: 380px;
                height: 100vh;
                background: #1a1a2e;
                color: #eee;
                display: flex;
                flex-direction: column;
                box-shadow: -2px 0 20px rgba(0,0,0,0.5);
                transition: right 0.3s ease;
                z-index: 10000;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            
            .ai-tutor-panel.open {
                right: 0;
            }
            
            .tutor-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 15px 20px;
                background: #16213e;
                border-bottom: 1px solid #0f3460;
            }
            
            .tutor-title {
                font-weight: 600;
                font-size: 16px;
            }
            
            .tutor-provider-select {
                background: #0f3460;
                color: #eee;
                border: 1px solid #1a4a80;
                border-radius: 5px;
                padding: 4px 6px;
                font-size: 12px;
                cursor: pointer;
            }

            .tutor-provider-select:focus {
                outline: none;
                border-color: #e94560;
            }

            .tutor-close {
                background: none;
                border: none;
                color: #eee;
                font-size: 24px;
                cursor: pointer;
                padding: 0 5px;
            }
            
            .tutor-messages {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                display: flex;
                flex-direction: column;
                gap: 15px;
            }
            
            .tutor-message {
                max-width: 90%;
                padding: 12px 16px;
                border-radius: 12px;
                font-size: 14px;
                line-height: 1.5;
            }
            
            .tutor-message.user {
                align-self: flex-end;
                background: #0f3460;
                color: #fff;
            }
            
            .tutor-message.assistant {
                align-self: flex-start;
                background: #2d2d44;
                color: #eee;
            }
            
            .tutor-message.streaming {
                opacity: 0.8;
            }
            
            .tutor-message.error {
                background: #5c2a2a;
                color: #ff9999;
            }
            
            .tutor-input-area {
                padding: 15px 20px;
                background: #16213e;
                border-top: 1px solid #0f3460;
            }
            
            .tutor-context {
                font-size: 12px;
                color: #888;
                margin-bottom: 10px;
                padding: 8px 12px;
                background: rgba(0,0,0,0.3);
                border-radius: 6px;
                display: none;
            }
            
            .tutor-context.visible {
                display: block;
            }
            
            .tutor-input-row {
                display: flex;
                gap: 10px;
            }
            
            .tutor-input {
                flex: 1;
                padding: 10px 15px;
                border: 1px solid #0f3460;
                border-radius: 8px;
                background: #1a1a2e;
                color: #eee;
                font-size: 14px;
            }
            
            .tutor-input:focus {
                outline: none;
                border-color: #e94560;
            }
            
            .tutor-send {
                padding: 10px 20px;
                background: #e94560;
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 500;
            }
            
            .tutor-send:hover {
                background: #ff6b6b;
            }
            
            .tutor-send:disabled {
                background: #666;
                cursor: not-allowed;
            }
            
            .tutor-actions {
                display: flex;
                gap: 10px;
                margin-top: 10px;
            }
            
            .tutor-action-btn {
                padding: 6px 12px;
                background: rgba(255,255,255,0.1);
                border: 1px solid #0f3460;
                border-radius: 6px;
                color: #aaa;
                font-size: 12px;
                cursor: pointer;
            }
            
            .tutor-action-btn:hover {
                background: rgba(255,255,255,0.15);
                color: #fff;
            }
            
            .tutor-screenshot-indicator {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 8px 12px;
                background: rgba(102, 126, 234, 0.2);
                border: 1px solid #667eea;
                border-radius: 6px;
                margin-bottom: 10px;
            }
            
            .screenshot-badge {
                font-size: 12px;
                color: #a5b4fc;
            }
            
            .screenshot-remove {
                background: none;
                border: none;
                color: #a5b4fc;
                font-size: 18px;
                cursor: pointer;
                padding: 0 4px;
                line-height: 1;
            }
            
            .screenshot-remove:hover {
                color: #fff;
            }
            
            .tutor-toggle {
                position: fixed;
                bottom: 30px;
                right: 30px;
                width: 56px;
                height: 56px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: 2px solid rgba(255,255,255,0.2);
                font-size: 28px;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                z-index: 9999;
                transition: transform 0.2s, box-shadow 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .tutor-toggle:hover {
                transform: scale(1.1);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
            }
            
            .tutor-toggle.hidden {
                display: none;
            }
            
            .tutor-question-btn {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 24px;
                height: 24px;
                border-radius: 50%;
                background: #0f3460;
                color: #e94560;
                border: 1px solid #e94560;
                font-size: 14px;
                font-weight: bold;
                cursor: pointer;
                margin-left: 10px;
                transition: all 0.2s;
            }
            
            .tutor-question-btn:hover {
                background: #e94560;
                color: white;
            }
            
            /* Typing indicator */
            .tutor-typing {
                display: flex;
                gap: 4px;
                padding: 12px 16px;
            }
            
            .tutor-typing span {
                width: 8px;
                height: 8px;
                background: #888;
                border-radius: 50%;
                animation: typing 1.4s infinite;
            }
            
            .tutor-typing span:nth-child(2) { animation-delay: 0.2s; }
            .tutor-typing span:nth-child(3) { animation-delay: 0.4s; }
            
            @keyframes typing {
                0%, 60%, 100% { transform: translateY(0); }
                30% { transform: translateY(-10px); }
            }
        `;
        
        document.head.appendChild(styles);
    }
    
    bindEvents() {
        // Toggle panel
        this.toggleBtn.addEventListener('click', () => this.toggle());
        document.getElementById('tutor-close').addEventListener('click', () => this.close());
        
        // Keyboard shortcut (press ? to toggle)
        document.addEventListener('keydown', (e) => {
            // Don't trigger if typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            if (e.key === '?' || e.key === '/') {
                e.preventDefault();
                this.toggle();
            }
        });
        
        // Send message
        document.getElementById('tutor-send').addEventListener('click', () => this.sendMessage());
        this.inputField.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });
        
        // Screenshot - now just captures and shows indicator
        document.getElementById('tutor-screenshot').addEventListener('click', () => {
            this.attachScreenshot();
        });
        
        // Remove screenshot button
        document.getElementById('tutor-remove-screenshot').addEventListener('click', () => {
            this.removeScreenshot();
        });
        
        // Clear
        document.getElementById('tutor-clear').addEventListener('click', () => {
            this.clearHistory();
        });

        // Provider selector
        this.loadCurrentProvider();
        this.providerSelect.addEventListener('change', () => this.changeProvider());
    }

    async loadCurrentProvider() {
        try {
            const resp = await fetch(`${this.apiBaseUrl}/settings/`);
            if (resp.ok) {
                const data = await resp.json();
                this.providerSelect.value = data.provider;
            }
        } catch (e) {
            // Backend not ready yet, silently ignore
        }
    }

    async changeProvider() {
        const provider = this.providerSelect.value;
        try {
            const resp = await fetch(`${this.apiBaseUrl}/settings/provider`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider })
            });
            if (!resp.ok) {
                const err = await resp.json();
                this.addMessage(`Could not switch provider: ${JSON.stringify(err.detail)}`, 'error');
                // Revert dropdown to what the backend still has
                this.loadCurrentProvider();
            }
        } catch (e) {
            this.addMessage(`Error switching provider: ${e.message}`, 'error');
            this.loadCurrentProvider();
        }
    }
    
    toggle() {
        this.isOpen = !this.isOpen;
        this.panel.classList.toggle('open', this.isOpen);
        this.toggleBtn.classList.toggle('hidden', this.isOpen);
        
        if (this.isOpen) {
            this.inputField.focus();
            this.updateContextDisplay();
        }
    }
    
    open() {
        this.isOpen = true;
        this.panel.classList.add('open');
        this.toggleBtn.classList.add('hidden');
        this.inputField.focus();
        this.updateContextDisplay();
    }
    
    close() {
        this.isOpen = false;
        this.panel.classList.remove('open');
        this.toggleBtn.classList.remove('hidden');
    }
    
    updateSolverState(state) {
        this.solverState = state;
        this.updateContextDisplay();
    }
    
    updateContextDisplay() {
        if (!this.solverState) {
            this.contextDisplay.classList.remove('visible');
            return;
        }
        
        const { operation, step_index, rule_used } = this.solverState;
        let text = `Working on: ${operation}`;
        
        if (step_index !== undefined) {
            text += ` • Step ${step_index + 1}`;
        }
        
        if (rule_used) {
            text += ` • ${rule_used}`;
        }
        
        this.contextDisplay.textContent = text;
        this.contextDisplay.classList.add('visible');
    }
    
    addMessage(content, role = 'user') {
        const msg = document.createElement('div');
        msg.className = `tutor-message ${role}`;
        msg.textContent = content;
        this.messagesContainer.appendChild(msg);
        this.scrollToBottom();
        return msg;
    }
    
    showTyping() {
        const typing = document.createElement('div');
        typing.className = 'tutor-message assistant tutor-typing';
        typing.id = 'tutor-typing';
        typing.innerHTML = '<span></span><span></span><span></span>';
        this.messagesContainer.appendChild(typing);
        this.scrollToBottom();
    }
    
    hideTyping() {
        const typing = document.getElementById('tutor-typing');
        if (typing) typing.remove();
    }
    
    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    async sendMessage(message = null) {
        const text = message || this.inputField.value.trim();
        if (!text || this.isStreaming) return;
        
        // Clear input if using field
        if (!message) {
            this.inputField.value = '';
        }
        
        // Check if we have a pending screenshot
        const hasScreenshot = this.pendingScreenshot !== null;
        
        // Build request
        const requestBody = {
            message: text,
            solver_state: this.solverState || {
                expression: '',
                operation: 'derivative',
                step_index: 0,
                step_count: 0
            },
            history: this.history.slice(-6) // Keep last 6 messages
        };
        
        // Add screenshot if attached
        if (hasScreenshot) {
            requestBody.screenshot_b64 = this.pendingScreenshot;
        }
        
        // Clear the pending screenshot now that we're sending it
        if (hasScreenshot) {
            this.pendingScreenshot = null;
            this.hideScreenshotIndicator();
            this.inputField.placeholder = 'Ask about this step...';
        }
        
        // Add user message to UI
        this.addMessage(text, 'user');
        this.history.push({ role: 'user', content: text });
        
        // Show typing
        this.showTyping();
        this.isStreaming = true;
        
        try {
            // Choose endpoint based on whether we have screenshot
            const endpoint = hasScreenshot 
                ? '/tutor/chat/vision' 
                : '/tutor/chat/stream';
            
            // Send request
            const response = await fetch(`${this.apiBaseUrl}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });
            
            this.hideTyping();
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${await response.text()}`);
            }
            
            // Handle streaming vs non-streaming
            if (endpoint.includes('/stream')) {
                await this.handleStreamingResponse(response);
            } else {
                const data = await response.json();
                this.addMessage(data.response, 'assistant');
                this.history.push({ role: 'assistant', content: data.response });
            }
            
        } catch (error) {
            this.hideTyping();
            console.error('Tutor error:', error);
            this.addMessage(`Error: ${error.message}`, 'error');
        } finally {
            this.isStreaming = false;
        }
    }
    
    async handleStreamingResponse(response) {
        const msg = document.createElement('div');
        msg.className = 'tutor-message assistant streaming';
        this.messagesContainer.appendChild(msg);
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            fullText += chunk;
            msg.textContent = fullText;
            this.scrollToBottom();
        }
        
        msg.classList.remove('streaming');
        this.history.push({ role: 'assistant', content: fullText });
    }
    
    async attachScreenshot() {
        // Capture screenshot and show 'attached' indicator (doesn't send yet).
        try {
            const screenshot = await this.captureScreenshot();
            
            if (!screenshot) {
                console.warn('No screenshot captured');
                this.inputField.placeholder = 'Could not capture screenshot. Try again.';
                setTimeout(() => {
                    this.inputField.placeholder = 'Ask about this step...';
                }, 3000);
                return;
            }
            
            // Store the screenshot
            this.pendingScreenshot = screenshot;
            
            // Show the indicator
            this.showScreenshotIndicator();
            
            // Focus input for user to type question
            this.inputField.focus();
            this.inputField.placeholder = 'Screenshot attached! Type your question...';
            
        } catch (error) {
            console.error('Failed to attach screenshot:', error);
            this.inputField.placeholder = 'Failed to capture screenshot';
            setTimeout(() => {
                this.inputField.placeholder = 'Ask about this step...';
            }, 3000);
        }
    }
    
    showScreenshotIndicator() {
        // Show the 'screenshot attached' indicator.
        if (this.screenshotIndicator) {
            this.screenshotIndicator.style.display = 'flex';
        }
    }
    
    hideScreenshotIndicator() {
        // Hide the screenshot indicator.
        if (this.screenshotIndicator) {
            this.screenshotIndicator.style.display = 'none';
        }
    }
    
    removeScreenshot() {
        // Remove the pending screenshot.
        this.pendingScreenshot = null;
        this.hideScreenshotIndicator();
        this.inputField.placeholder = 'Ask about this step...';
    }
    
    async captureScreenshot() {
        // This needs to be implemented based on how the desktop app captures canvas
        // For now, return null and the backend will handle missing screenshot
        
        // If pywebview bridge is available:
        if (window.pywebview && window.pywebview.api) {
            try {
                return await window.pywebview.api.capture_canvas();
            } catch (e) {
                console.warn('Screenshot capture failed:', e);
            }
        }
        
        // Fallback: capture the canvas element directly
        const canvas = document.querySelector('canvas');
        if (canvas) {
            return canvas.toDataURL('image/png').split(',')[1];
        }
        
        return null;
    }
    
    clearHistory() {
        this.messagesContainer.innerHTML = '';
        this.history = [];
        this.pendingScreenshot = null;
        this.hideScreenshotIndicator();
        this.addMessage('Conversation cleared. How can I help you?', 'assistant');
    }
    
    // Static method to create question buttons on solver steps
    static addQuestionButton(element, stepIndex, ruleName) {
        const btn = document.createElement('button');
        btn.className = 'tutor-question-btn';
        btn.innerHTML = '?';
        btn.title = 'Ask AI Tutor about this step';
        
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            
            // Update tutor state
            if (window.aiTutor) {
                const state = window.aiTutor.solverState || {};
                state.step_index = stepIndex;
                state.rule_used = ruleName;
                window.aiTutor.updateSolverState(state);
                window.aiTutor.open();
                
                // Pre-fill question
                window.aiTutor.inputField.value = `Help me understand step ${stepIndex + 1}`;
                window.aiTutor.inputField.focus();
            }
        });
        
        element.appendChild(btn);
        return btn;
    }
}

// Global instance
window.aiTutor = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.aiTutor = new AITutorPanel();
    console.log('🎓 AI Tutor initialized');
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AITutorPanel };
}
