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
        // The tutor backend runs at localhost:8000 on the PyWebView desktop
        // (a local FastAPI process spawned by run.py). On the Hugging Face
        // Space deploy the same routes are mounted at the page's origin
        // (e.g. https://rsan0948-calculus-animator.hf.space/tutor/chat/stream)
        // so the browser must use the page's origin, not localhost — otherwise
        // every tutor request goes to the user's OWN computer, not the Space,
        // and surfaces as a red "Error: Failed to fetch" / "network error"
        // banner. Detect by protocol: http(s) → same-origin; file: / null
        // (PyWebView) → localhost:8000.
        const sameOriginCandidate =
            (typeof window !== 'undefined'
             && window.location
             && typeof window.location.protocol === 'string'
             && window.location.protocol.startsWith('http')
             && window.location.origin)
            ? window.location.origin
            : 'http://127.0.0.1:8000';
        this.apiBaseUrl = options.apiUrl || sameOriginCandidate;
        this.solverState = null;
        this.history = [];
        this.isOpen = false;
        this.isStreaming = false;
        this.pendingScreenshot = null;  // Stores captured screenshot until sent
        this.apiHealthy = null;          // null = unknown, true = up, false = down
        this.healthCheckInterval = null;
        this.healthAbortController = null;

        this.init();
    }

    init() {
        this.createPanel();
        this.attachStyles();
        this.bindEvents();
        this.startHealthCheck();
    }
    
    createPanel() {
        // Create panel HTML
        const panel = document.createElement('div');
        panel.id = 'ai-tutor-panel';
        panel.className = 'ai-tutor-panel';
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-modal', 'true');
        panel.setAttribute('aria-label', 'AI Tutor');
        panel.innerHTML = `
            <div class="tutor-header">
                <span class="tutor-title">🎓 Calculus Tutor</span>
                <select id="tutor-provider-select" class="tutor-provider-select" title="AI Provider" aria-label="AI provider">
                    <option value="deepseek">DeepSeek</option>
                    <option value="google">Gemini API</option>
                    <option value="gemini_cli">Gemini CLI</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="local">Local (Ollama)</option>
                </select>
                <button class="tutor-close" id="tutor-close" aria-label="Close tutor panel">×</button>
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

        // Drag-resize handle on the panel's left edge — Sangha-style.
        // Inserted as the panel's first child so it sits above siblings
        // for hit-testing without z-index gymnastics.
        const resizeHandle = document.createElement('div');
        resizeHandle.className = 'tutor-resize-handle';
        resizeHandle.setAttribute('role', 'separator');
        resizeHandle.setAttribute('aria-orientation', 'vertical');
        resizeHandle.setAttribute('aria-label', 'Resize tutor panel');
        panel.insertBefore(resizeHandle, panel.firstChild);

        // Backdrop: dim layer that captures taps to close. Sits between
        // the page and the panel (z-index 9998 < panel's 10000).
        const backdrop = document.createElement('div');
        backdrop.id = 'ai-tutor-backdrop';
        backdrop.className = 'ai-tutor-backdrop';
        document.body.appendChild(backdrop);

        // Create toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.id = 'tutor-toggle';
        toggleBtn.className = 'tutor-toggle';
        toggleBtn.innerHTML = '🎓';
        toggleBtn.title = 'AI Tutor (press ?)';
        toggleBtn.setAttribute('aria-label', 'Open AI Tutor');
        document.body.appendChild(toggleBtn);

        this.panel = panel;
        this.resizeHandle = resizeHandle;
        this.backdrop = backdrop;
        this.toggleBtn = toggleBtn;
        this.messagesContainer = document.getElementById('tutor-messages');
        this.inputField = document.getElementById('tutor-input');
        this.contextDisplay = document.getElementById('tutor-context');
        this.screenshotIndicator = document.getElementById('tutor-screenshot-indicator');
        this.providerSelect = document.getElementById('tutor-provider-select');
        this.sendBtn = document.getElementById('tutor-send');
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

            /* Health-check status dot. Pseudo-element so the existing
               toggle DOM stays untouched. Default gray = unknown /
               first ping in flight; green when /health responds; red
               when the heartbeat fails or aborts on 5s timeout. */
            .tutor-toggle::after {
                content: '';
                position: absolute;
                top: 4px;
                right: 4px;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.35);
                border: 2px solid rgba(0, 0, 0, 0.25);
                transition: background 0.3s;
            }
            .tutor-toggle.api-healthy::after {
                background: #4ade80;
            }
            .tutor-toggle.api-unhealthy::after {
                background: #f87171;
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

            /* Backdrop: dim the page when the panel is open and let the
               user dismiss by tapping outside. opacity transitions in
               sync with the panel's slide. */
            .ai-tutor-backdrop {
                position: fixed;
                inset: 0;
                background: rgba(0, 0, 0, 0.45);
                z-index: 9998;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.3s ease;
            }
            .ai-tutor-backdrop.open {
                opacity: 1;
                pointer-events: auto;
            }

            /* Drag-resize handle on the panel's left edge — same pattern
               as Sangha's chat-resize-handle: a thin strip with a small
               grip indicator that the user can drag horizontally to
               shrink/grow the panel. touch-action:none keeps mobile
               browsers from interpreting the drag as a page scroll. */
            .tutor-resize-handle {
                position: absolute;
                left: 0;
                top: 0;
                bottom: 0;
                width: 8px;
                cursor: col-resize;
                background: linear-gradient(90deg, rgba(255,255,255,0.04), rgba(0,0,0,0));
                z-index: 1;
                touch-action: none;
            }
            .tutor-resize-handle::after {
                content: "";
                position: absolute;
                left: 2px;
                top: 50%;
                transform: translateY(-50%);
                width: 4px;
                height: 36px;
                border-radius: 2px;
                background: rgba(255,255,255,0.25);
                pointer-events: none;
                transition: background 0.15s ease;
            }
            .tutor-resize-handle:hover::after,
            .tutor-resize-handle:active::after {
                background: rgba(255,255,255,0.5);
            }

            /* Phones: side-panel like Sangha's chat. Caps at 90vw so a
               10vw editor/page strip stays visible on the left as the
               click-off-to-close target (the existing backdrop click
               handler treats taps on that strip as a dismiss). Wider,
               more visible resize handle since fingers need a bigger
               touch target. */
            @media (max-width: 768px) {
                .ai-tutor-panel {
                    width: 90vw;
                    max-width: 90vw;
                    /* keep the desktop side-drawer geometry — top:0,
                       right:-400px (offscreen) → right:0 — but ensure
                       the bottom-sheet overrides from earlier rounds
                       are explicitly undone. */
                    top: 0;
                    bottom: auto;
                    left: auto;
                    border-top-left-radius: 16px;
                    border-bottom-left-radius: 16px;
                    border-top-right-radius: 0;
                    border-bottom-right-radius: 0;
                    transition: right 0.3s ease;
                }
                .tutor-resize-handle {
                    width: 18px;
                    left: -8px;
                }
                .tutor-resize-handle::after {
                    width: 5px;
                    height: 56px;
                    background: rgba(255,255,255,0.45);
                }
            }
        `;

        document.head.appendChild(styles);
    }
    
    bindEvents() {
        // Toggle panel
        this.toggleBtn.addEventListener('click', () => this.toggle());
        document.getElementById('tutor-close').addEventListener('click', () => this.close());
        // Tapping the backdrop dismisses the panel — clear escape path.
        this.backdrop.addEventListener('click', () => this.close());
        // Drag the left edge to resize. Mouse + touch.
        this.resizeHandle.addEventListener('mousedown', (e) => this.startResize(e));
        this.resizeHandle.addEventListener('touchstart', (e) => this.startResize(e), { passive: false });

        // Keyboard shortcuts: ? / / toggles, Escape closes when open.
        document.addEventListener('keydown', (e) => {
            // Escape always closes, even while typing in the tutor input.
            if (e.key === 'Escape' && this.isOpen) {
                e.preventDefault();
                this.close();
                return;
            }
            // Don't trigger ?/ shortcut if typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            // The tutor is contextually about solver state; on the Learning
            // screen the opener is CSS-hidden, so the shortcut must not
            // summon the panel (and its click-blocking backdrop) there.
            if (this.isLearningScreenActive()) return;
            if (e.key === '?' || e.key === '/') {
                e.preventDefault();
                this.toggle();
            }
        });

        // Crossing the mobile/desktop breakpoint invalidates any inline
        // width left behind by drag-resize; clear it so the responsive
        // CSS (90vw mobile / 380px desktop) takes over again.
        this._lastViewportMobile = this.isMobileViewport();
        window.addEventListener('resize', () => {
            const mobile = this.isMobileViewport();
            if (mobile !== this._lastViewportMobile) {
                this._lastViewportMobile = mobile;
                this.panel.style.width = '';
                this.panel.style.maxWidth = '';
            }
        });
        // Double-click (or double-tap) the handle to restore default width.
        this.resizeHandle.addEventListener('dblclick', () => {
            this.panel.style.width = '';
            this.panel.style.maxWidth = '';
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
                // Assigning an unknown value to a <select> silently no-ops,
                // leaving the dropdown showing a provider the backend isn't
                // using. Surface that instead of lying.
                if (data.provider && this.providerSelect.value !== data.provider) {
                    console.warn(`Tutor backend uses unknown provider "${data.provider}"; dropdown may not reflect it.`);
                }
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
    
    isMobileViewport() {
        return typeof window !== 'undefined'
            && typeof window.matchMedia === 'function'
            && window.matchMedia('(max-width: 768px)').matches;
    }

    isLearningScreenActive() {
        const learning = document.getElementById('learningScreen');
        return !!(learning && learning.classList.contains('active'));
    }

    /**
     * Drag the left edge of the panel to resize. Mirrors Sangha's
     * FlowEditor.svelte startChatResize: handles both MouseEvent and
     * TouchEvent, computes mobile-aware bounds (lower min and a
     * viewport-relative max so the panel can shrink past the desktop
     * floor on phones), and calls preventDefault on touchmove so the
     * drag doesn't double as a page scroll.
     */
    startResize(event) {
        event.preventDefault();
        const isTouch = event.type === 'touchstart';
        const startX = isTouch ? event.touches[0].clientX : event.clientX;
        const startWidth = this.panel.getBoundingClientRect().width;
        const isMobile = this.isMobileViewport();
        const minWidth = isMobile ? 200 : 320;
        const maxWidth = isMobile
            ? Math.floor(window.innerWidth * 0.9)
            : Math.max(420, Math.floor(window.innerWidth * 0.5));

        const onMove = (e) => {
            const clientX = e.touches?.[0]?.clientX ?? e.clientX;
            if (clientX === undefined) return;
            // Panel is anchored right:0; dragging left increases width,
            // dragging right shrinks it. delta = startX - currentX.
            const delta = startX - clientX;
            const next = Math.max(minWidth, Math.min(maxWidth, startWidth + delta));
            this.panel.style.width = `${next}px`;
            // Override the CSS max-width:90vw rule for mobile so the
            // user can drag larger than the default cap if they want.
            this.panel.style.maxWidth = `${maxWidth}px`;
            if (e.cancelable && e.touches) e.preventDefault();
        };

        const onUp = () => {
            window.removeEventListener('mousemove', onMove);
            window.removeEventListener('mouseup', onUp);
            window.removeEventListener('touchmove', onMove);
            window.removeEventListener('touchend', onUp);
            window.removeEventListener('touchcancel', onUp);
        };

        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
        // Non-passive so onMove can preventDefault page scrolling.
        window.addEventListener('touchmove', onMove, { passive: false });
        window.addEventListener('touchend', onUp);
        window.addEventListener('touchcancel', onUp);
    }

    toggle() {
        this.isOpen = !this.isOpen;
        this.panel.classList.toggle('open', this.isOpen);
        this.backdrop.classList.toggle('open', this.isOpen);
        this.toggleBtn.classList.toggle('hidden', this.isOpen);

        if (this.isOpen) {
            this.updateContextDisplay();
            // On phones, don't auto-focus the input — that pops the
            // virtual keyboard and turns the slide-in into an immediate
            // takeover. Let the user tap the input themselves.
            if (!this.isMobileViewport()) {
                this.inputField.focus();
            }
        }
    }

    open() {
        this.isOpen = true;
        this.panel.classList.add('open');
        this.backdrop.classList.add('open');
        this.toggleBtn.classList.add('hidden');
        this.updateContextDisplay();
        if (!this.isMobileViewport()) {
            this.inputField.focus();
        }
    }

    close() {
        this.isOpen = false;
        this.panel.classList.remove('open');
        this.backdrop.classList.remove('open');
        this.toggleBtn.classList.remove('hidden');
        // If the input had focus on mobile, blur to dismiss the keyboard
        // so the close transition isn't visually fighting an open one.
        if (typeof document !== 'undefined' && document.activeElement === this.inputField) {
            this.inputField.blur();
        }
    }

    /**
     * 30-second heartbeat against /health (~20 bytes, <300ms typical).
     * Surfaces a small status dot on the floating toggle so a stale or
     * slept HF Space is visible at a glance — green = reachable, red =
     * unreachable, default gray = unknown / first check in flight.
     */
    startHealthCheck() {
        if (this.healthCheckInterval) clearInterval(this.healthCheckInterval);
        this.checkHealth();
        this.healthCheckInterval = setInterval(() => this.checkHealth(), 30000);
    }

    async checkHealth() {
        if (this.healthAbortController) this.healthAbortController.abort();
        this.healthAbortController = new AbortController();
        const timeout = setTimeout(() => this.healthAbortController.abort(), 5000);
        try {
            const resp = await fetch(`${this.apiBaseUrl}/health`, {
                signal: this.healthAbortController.signal,
                cache: 'no-store',
            });
            this.setApiHealthy(resp.ok);
        } catch (_) {
            this.setApiHealthy(false);
        } finally {
            clearTimeout(timeout);
        }
    }

    setApiHealthy(healthy) {
        if (healthy === this.apiHealthy) return;
        this.apiHealthy = healthy;
        if (!this.toggleBtn) return;
        this.toggleBtn.classList.toggle('api-healthy', healthy === true);
        this.toggleBtn.classList.toggle('api-unhealthy', healthy === false);
        this.toggleBtn.title = healthy
            ? 'AI Tutor (press ?)'
            : 'AI Tutor offline — backend unreachable (press ?)';
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

        // Backend rejects requests without a real solver_state.expression
        // with a 422, surfacing as a generic "network error" in the chat.
        // If the user opened the tutor before loading or solving a problem,
        // give them inline feedback instead of firing a doomed request.
        const hasSolverContext = !!(this.solverState && this.solverState.expression);
        if (!hasSolverContext) {
            this.addMessage(text, 'user');
            this.history.push({ role: 'user', content: text });
            const hint = 'Load or solve a problem first — then I can help with the steps.';
            this.addMessage(hint, 'assistant');
            this.history.push({ role: 'assistant', content: hint });
            return;
        }

        // Check if we have a pending screenshot
        const hasScreenshot = this.pendingScreenshot !== null;

        // Build request
        const requestBody = {
            message: text,
            solver_state: this.solverState,
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
        if (this.sendBtn) this.sendBtn.disabled = true;

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
            if (this.sendBtn) this.sendBtn.disabled = false;
        }
    }

    async handleStreamingResponse(response) {
        const msg = document.createElement('div');
        msg.className = 'tutor-message assistant streaming';
        this.messagesContainer.appendChild(msg);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = '';

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                fullText += chunk;
                msg.textContent = fullText;
                this.scrollToBottom();
            }
            // Flush the decoder so a trailing multi-byte character split
            // across the final chunk boundary isn't silently dropped.
            fullText += decoder.decode();
        } catch (error) {
            // Mid-stream failure (dropped connection, backend died): keep
            // the partial answer visible and in history so the next turn's
            // context matches what's on screen. If nothing arrived at all,
            // remove the empty bubble and let sendMessage render the error.
            console.error('Tutor stream interrupted:', error);
            if (!fullText) {
                msg.remove();
                throw error;
            }
            fullText += '\n[response interrupted — connection lost]';
        } finally {
            msg.classList.remove('streaming');
        }

        if (!fullText) {
            // Empty 200 body — don't leave a blank assistant bubble behind.
            msg.remove();
            this.addMessage('The tutor returned an empty response. Please try again.', 'error');
            return;
        }
        msg.textContent = fullText;
        this.scrollToBottom();
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
