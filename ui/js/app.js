/**
 * Calculus Animator - Main Orchestrator
 */
import { state } from './modules/state.js';
import * as utils from './modules/utils.js';
import { bridge } from './modules/bridge.js';
import { renderer } from './modules/renderer.js';
import { ui_events } from './modules/ui_events.js';

// Local copy of the prototype-pollution guard the renderer module uses.
// Kept duplicated rather than imported so this file's safety boundary
// stands on its own and survives independent refactors of renderer.js.
const _UNSAFE_PROTO_KEYS = new Set(["__proto__", "constructor", "prototype"]);

function _setSafe(obj, key, value) {
    const k = String(key);
    if (_UNSAFE_PROTO_KEYS.has(k)) {
        bridge.log(`Refusing prototype-polluting key: ${k}`, "warn");
        return;
    }
    Object.defineProperty(obj, k, {
        value,
        writable: true,
        configurable: true,
        enumerable: true,
    });
}

const app = {
    async boot() {
        bridge.log("Booting Calculus Animator...");
        try {
            state.mathField = document.getElementById("mathInput");
            if (state.mathField) {
                state.mathField.value = utils.normalizeDisplayMath(state.mathField.value || "");
            }
            
            // Un-nest glossary if not already done in state.js
            if (state.glossary && !state.glossaryLexicon) {
                state.glossaryLexicon = state.glossary.glossaryLexicon || [];
            }
            
            // Setup UI and canvases before loading data
            renderer.setupCanvases();
            ui_events.bindUI(this);
            
            // Load all data concurrently
            bridge.log("Loading application data...");
            const [formulas, demos, symbols, lib, curr, gloss] = await Promise.all([
                bridge.loadFormulas(),
                bridge.loadDemoProblems(),
                bridge.loadSymbols(),
                bridge.loadLearningLibrary(),
                bridge.loadCurriculum(),
                bridge.loadGlossary()
            ]);

            bridge.log("Processing formulas...");
            state.allFormulas = formulas.formulas || [];
            renderer.renderCategories(formulas.categories || [], (cat) => {
                renderer.renderFormulas(cat === "all" ? state.allFormulas : state.allFormulas.filter(f => f.category === cat));
            });
            renderer.renderFormulas(state.allFormulas);
            
            bridge.log("Processing demos...");
            renderer.renderDemoDropdown(demos.collections || []);
            
            bridge.log("Processing symbols...");
            renderer.renderSymbols(symbols.groups || []);
            
            bridge.log("Processing learning library...");
            renderer.renderLearningLibrary(lib);
            
            bridge.log("Processing curriculum...");
            state.curriculum = { pathways: Array.isArray(curr?.pathways) ? curr.pathways : [] };

            // Restore last session position
            try {
                const saved = JSON.parse(localStorage.getItem('calcAnimState') || '{}');
                const ids = state.curriculum.pathways.map(p => p.id);
                if (saved.selectedPathwayId && ids.includes(saved.selectedPathwayId)) {
                    state.selectedPathwayId = saved.selectedPathwayId;
                    const pathway = state.curriculum.pathways.find(p => p.id === state.selectedPathwayId);
                    const chapterIds = (pathway?.chapters || []).map(c => c.id);
                    if (saved.selectedChapterId && chapterIds.includes(saved.selectedChapterId)) {
                        state.selectedChapterId = saved.selectedChapterId;
                        state.selectedSlideIndex = saved.selectedSlideIndex || 0;
                    }
                }
                if (saved.learningMode) state.learningMode = saved.learningMode;
            } catch (err) {
                bridge.log(`Failed to restore saved session: ${err && err.message ? err.message : err}`, "warn");
            }

            if (!state.selectedPathwayId && state.curriculum.pathways.length) {
                state.selectedPathwayId = state.curriculum.pathways[0].id;
                bridge.log(`Set default pathway to ${state.selectedPathwayId}`);
            }
            
            bridge.log("Processing glossary...");
            state.glossary = { terms: Array.isArray(gloss?.terms) ? gloss.terms : [] };
            state.glossaryById = {};
            state.glossaryLexicon = [];
            state.glossary.terms.forEach(t => {
                if (!t?.id) return;
                _setSafe(state.glossaryById, t.id, t);
                const variants = [t.term, ...(t.aliases || [])].filter(Boolean);
                variants.forEach(v => state.glossaryLexicon.push({ token: String(v), id: t.id }));
            });
            state.glossaryLexicon.sort((a, b) => b.token.length - a.token.length);

            // Initial rendering
            bridge.log("Rendering UI components...");
            renderer.renderPathwayList();
            renderer.renderChapterList();
            renderer.renderCurrentSlide();
            renderer.renderGlossaryList();
            renderer.renderLearningHome();

        } catch (e) {
            bridge.log(`Boot process failed: ${e.message}`, "error");
        }

        this.updateParams();
        this.clearAnimStage();
        bridge.log("Boot complete.");
    },

    saveState() {
        try {
            localStorage.setItem('calcAnimState', JSON.stringify({
                selectedPathwayId: state.selectedPathwayId,
                selectedChapterId: state.selectedChapterId,
                selectedSlideIndex: state.selectedSlideIndex,
                learningMode: state.learningMode,
            }));
        } catch (err) {
            bridge.log(`Failed to persist session state: ${err && err.message ? err.message : err}`, "warn");
        }
    },

    async solve(options = {}) {
        const focusAnimation = !!options.focusAnimation;
        const displayExpr = state.mathField.value;
        const latex = this.buildSolverExpression(displayExpr);
        if (!latex.trim()) {
            const inp = document.getElementById("mathInput") || state.mathField;
            inp.classList.add("shake-input");
            setTimeout(() => inp.classList.remove("shake-input"), 500);
            return;
        }
        this.pauseAnim();

        const calcType = document.getElementById("calcTypeSelect").value || null;
        const params = {
            variable: document.getElementById("varInput").value || "x",
            lower: document.getElementById("lowerBound").value,
            upper: document.getElementById("upperBound").value,
            point: document.getElementById("limitPoint").value,
            direction: document.getElementById("limitDir").value,
            order: parseInt(document.getElementById("seriesOrder").value, 10) || 6,
        };

        this.showLoading();
        const result = await bridge.solve(latex, calcType, params);
        state.solveResult = result;
        if (result.success) {
            this.showResult(result);
            this.renderRelatedLearningLinks(result);
            state.currentSteps = result.animation_steps || [];
            this.showSteps(state.currentSteps);
            this.renderAnimationStepList(state.currentSteps);
            state.baseLatex = state.currentSteps[0]?.before || state.mathField.value || "";
            state.stepIdx = -1;
            this.clearAnimStage();
            renderer.renderStationaryStage(state.baseLatex, "");

            if (focusAnimation) {
                this.setActiveTab("animation");
                this.playAnim();
            }
            this.updateIndicator();
            await this.refreshGraph();
        } else {
            this.showError(result.error || "Unknown error");
        }
    },

    buildSolverExpression(displayText) {
        let s = String(displayText || "");
        s = utils.revertPrettyScripts(s);
        s = s.replace(/×|·/g, "*");
        s = s.replace(/π/g, "pi");
        s = s.replace(/∞/g, "oo");
        s = s.replace(/→/g, "->");
        s = s.replace(/∫/g, "int");
        s = s.replace(/√/g, "sqrt");
        return s;
    },

    clear() {
        this.pauseAnim();
        state.stepRenderToken++;
        state.mathField.value = "";
        document.getElementById("resultDisplay").innerHTML = '<p class="placeholder">Enter an expression and click <strong>Solve &amp; Animate</strong></p>';
        document.getElementById("resultDisplay").dataset.copyText = "";
        document.getElementById("resultDisplay").classList.remove("copyable");
        this.clearRelatedLearning();
        document.getElementById("stepsContainer").innerHTML = "";
        document.getElementById("animStepsPanel").innerHTML = "";
        state.currentSteps = [];
        state.stepIdx = -1;
        state.baseLatex = "";
        state.queuedDirection = 0;
        state.solveResult = null;
        renderer.clearCanvases();
        this.clearAnimStage();
        this.updateIndicator();
    },

    pauseAnim() {
        state.animPlaying = false;
        clearTimeout(state.animTimer);
    },

    playAnim() {
        if (state.animPlaying || !state.currentSteps.length || state.transitionBusy) return;
        state.animPlaying = true;
        if (state.stepIdx >= state.currentSteps.length - 1) {
            state.stepIdx = -1;
            renderer.renderStationaryStage(state.baseLatex, "");
            this.updateIndicator();
        }
        this.runAnimLoop();
    },

    runAnimLoop() {
        if (!state.animPlaying) return;
        if (state.transitionBusy) {
            state.animTimer = setTimeout(() => this.runAnimLoop(), 100);
            return;
        }
        if (state.stepIdx >= state.currentSteps.length - 1) {
            state.animPlaying = false;
            return;
        }
        const advanced = this.stepForward();
        if (!advanced) {
            state.animPlaying = false;
            return;
        }
        const speed = parseFloat(document.getElementById("speedSlider").value) || 1;
        state.animTimer = setTimeout(() => this.runAnimLoop(), state.AUTO_STEP_MS / speed);
    },

    stepForward() {
        if (state.transitionBusy) {
            state.queuedDirection = 1;
            return true;
        }
        if (state.stepIdx >= state.currentSteps.length - 1) return false;
        renderer.showAnimStep(state.stepIdx + 1);
        return true;
    },

    stepBack() {
        if (state.transitionBusy) {
            state.queuedDirection = -1;
            return true;
        }
        if (state.stepIdx < 0) return false;
        if (state.stepIdx === 0) {
            state.stepIdx = -1;
            renderer.renderStationaryStage(state.baseLatex, "");
            document.querySelectorAll(".step-card").forEach((c) => c.classList.remove("highlight"));
            document.querySelectorAll(".anim-step-item").forEach((c) => c.classList.remove("active"));
            this.updateIndicator();
            return true;
        }
        renderer.showAnimStep(state.stepIdx - 1);
        return true;
    },

    async refreshGraph() {
        const displayExpr = state.mathField.value;
        const latex = this.buildSolverExpression(displayExpr);
        if (!latex.trim()) return;
        const calcType = document.getElementById("calcTypeSelect").value || null;
        const params = {
            variable: document.getElementById("varInput").value || "x",
            lower: document.getElementById("lowerBound").value,
            upper: document.getElementById("upperBound").value,
            point: document.getElementById("limitPoint").value,
            direction: document.getElementById("limitDir").value,
            order: parseInt(document.getElementById("seriesOrder").value, 10) || 6,
        };
        const data = await bridge.getGraphData(latex, calcType, params, -10/state.zoom, 10/state.zoom);
        state.graphData = data;
        renderer.drawGraph();
    },

    setActiveTab(tabName) {
        document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === tabName));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.toggle("active", c.id === (tabName + "Tab")));
    },

    setActiveScreen(screenName) {
        document.querySelectorAll(".screen-btn").forEach(btn => btn.classList.toggle("active", btn.dataset.screen === screenName));
        document.getElementById("solverScreen").classList.toggle("active", screenName === "solver");
        document.getElementById("learningScreen").classList.toggle("active", screenName === "learning");
        if (screenName !== "solver") this.pauseAnim();
        if (screenName === "learning") this.setLearningMode(state.learningMode || "home");
    },

    setLearningMode(mode) {
        state.learningMode = mode;
        this.saveState();
        document.querySelectorAll(".learning-mode-btn").forEach(btn => btn.classList.toggle("active", btn.dataset.learningMode === mode));
        document.querySelectorAll(".learning-mode").forEach(el => el.classList.remove("active"));
        const modeEl = document.getElementById(
            mode === "home" ? "learningHomeMode" :
            mode === "pathways" ? "learningPathwaysMode" :
            mode === "glossary" ? "learningGlossaryMode" :
            mode === "capacity" ? "learningCapacityMode" : "learningLibraryMode"
        );
        if (modeEl) modeEl.classList.add("active");
        if (mode === "home") renderer.renderLearningHome();
        else if (mode === "pathways") { state.showPathwayPicker = false; renderer.renderPathwayList(); renderer.renderChapterList(); renderer.renderCurrentSlide(); }
        else if (mode === "glossary") renderer.renderGlossaryList();
        else if (mode === "capacity") renderer.renderCapacityPage();
        else renderer.renderLearningItems();
    },

    openLearningTopic(topicId) {
        if (!topicId || !state.learningTopicById[topicId]) return;
        state.learningActiveView = "concepts";
        state.learningSelectedTopicId = topicId;
        this.setActiveScreen("learning");
        this.setLearningMode("library");
        renderer.renderLearningItems();
    },

    async runSelectedDemo() {
        const id = document.getElementById("demoSelect").value;
        if (!id || !state.demoMap[id]) return;
        const demo = state.demoMap[id];
        if (demo.latex) state.mathField.value = utils.normalizeDisplayMath(demo.latex);
        document.getElementById("calcTypeSelect").value = demo.tag || "";
        this.applyParams(demo.params || {});
        this.updateParams();
    },

    applyParams(p) {
        if (p.variable) document.getElementById("varInput").value = p.variable;
        if (p.lower !== undefined) document.getElementById("lowerBound").value = p.lower;
        if (p.upper !== undefined) document.getElementById("upperBound").value = p.upper;
        if (p.point !== undefined) document.getElementById("limitPoint").value = p.point;
        if (p.direction) document.getElementById("limitDir").value = p.direction;
        if (p.order !== undefined) document.getElementById("seriesOrder").value = p.order;
    },

    updateParams() {
        const t = document.getElementById("calcTypeSelect").value;
        document.getElementById("boundsParam").classList.toggle("hidden", t !== "definite_integral");
        document.getElementById("limitParam").classList.toggle("hidden", t !== "limit");
        document.getElementById("orderParam").classList.toggle("hidden", t !== "taylor" && t !== "series");
    },

    showLoading() {
        document.getElementById("resultDisplay").innerHTML = '<p class="placeholder">Computing…</p>';
        document.getElementById("resultDisplay").dataset.copyText = "";
        document.getElementById("resultDisplay").classList.remove("copyable");
        this.clearRelatedLearning();
        document.getElementById("stepsContainer").innerHTML = "";
        document.getElementById("animStepsPanel").innerHTML = "";
    },

    showResult(data) {
        const el = document.getElementById("resultDisplay");
        el.innerHTML = "";
        const plain = utils.normalizeDisplayMath(data.result_latex || "");
        el.dataset.copyText = plain;
        el.classList.add("copyable");
        try {
            katex.render(data.result_latex, el, { throwOnError: false, displayMode: true, trust: false });
        } catch (err) {
            bridge.log(`KaTeX render failed in showResult: ${err && err.message ? err.message : err}`, "warn");
            el.textContent = data.result_latex;
        }
    },

    showError(msg) {
        const el = document.getElementById("resultDisplay");
        el.textContent = "";
        const span = document.createElement("span");
        span.style.color = "var(--accent)";
        span.textContent = `Error: ${msg}`;
        el.appendChild(span);
        el.dataset.copyText = "";
        el.classList.remove("copyable");
        this.clearRelatedLearning();
    },

    renderRelatedLearningLinks(result) {
        const panel = document.getElementById("relatedLearningPanel");
        const picks = this.getTopRelatedTopics(result, 3);
        state.relatedTopicPicks = picks;
        this.renderAnimRelatedLearningLinks(picks);
        if (!panel) return;
        if (!picks.length) { this.clearRelatedLearning(); return; }
        panel.classList.remove("hidden");
        panel.innerHTML = `
            <div class="related-learning-title">Learn Why This Works</div>
            <div class="related-learning-links">
                ${picks.map(p => `<button class="related-learning-link" data-topic-id="${utils.escAttr(p.id)}">${utils.prettyText(p.title)}</button>`).join("")}
            </div>
        `;
    },

    clearRelatedLearning() {
        const panel = document.getElementById("relatedLearningPanel");
        if (panel) { panel.classList.add("hidden"); panel.innerHTML = ""; }
        state.relatedTopicPicks = [];
        this.renderAnimRelatedLearningLinks([]);
    },

    renderAnimRelatedLearningLinks(picks) {
        const menu = document.getElementById("animRelatedMenu");
        const btn = document.getElementById("animLearnToggleBtn");
        if (btn) btn.disabled = !picks.length;
        if (!menu) return;
        if (!picks.length) { menu.classList.add("hidden"); menu.innerHTML = ""; return; }
        menu.innerHTML = picks.map(p => `<button class="related-learning-link" data-topic-id="${utils.escAttr(p.id)}">${utils.prettyText(p.title)}</button>`).join("");
        menu.classList.add("hidden");
    },

    getTopRelatedTopics(result, limit) {
        const topics = state.learningLibrary.topics || [];
        if (!topics.length || !result) return [];
        const haystack = this.buildSolveHaystack(result);
        const keywords = this.extractKeywords(haystack);
        const scored = topics.map(t => {
            const text = [t.title, t.summary, t.narrative, ...(t.formulas || []), ...(t.symbols || [])].join(" ").toLowerCase();
            let score = 0;
            keywords.forEach(k => { if (k.length > 2 && text.includes(k)) score += 1; });
            return { id: t.id, title: t.title || t.id, score };
        }).filter(x => x.score > 0);
        if (!scored.length) return topics.slice(0, limit).map(t => ({ id: t.id, title: t.title || t.id }));
        return scored.sort((a, b) => b.score - a.score).slice(0, limit);
    },

    buildSolveHaystack(result) {
        return [state.mathField.value, result.result, result.result_latex, result.detected_type].join(" ").toLowerCase();
    },

    extractKeywords(text) {
        return String(text || "").replace(/[^a-z0-9_ ]+/g, " ").split(/\s+/).filter(Boolean);
    },

    showSteps(steps) {
        const c = document.getElementById("stepsContainer");
        if (!steps.length) { c.innerHTML = '<p style="color:var(--text2)">No intermediate steps.</p>'; return; }
        c.innerHTML = steps.map((s, i) => `<div class="step-card" data-step="${i}">
            <div class="step-header"><span class="step-number">${s.step}</span><span class="step-rule">${(s.rule || "").replace(/_/g, " ")}</span></div>
            <div class="step-description">${utils.prettyText(s.description)}</div>
            <div class="step-math"><span class="before"></span>${s.before && s.after ? '<span class="arrow">→</span>' : ''}<span class="after"></span></div>
        </div>`).join("");
        c.querySelectorAll(".step-card").forEach((card, i) => {
            const s = steps[i];
            try {
                if (s.before) katex.render(s.before, card.querySelector(".before"), { throwOnError: false, trust: false });
            } catch (err) {
                bridge.log(`KaTeX render failed in showSteps.before: ${err && err.message ? err.message : err}`, "warn");
            }
            try {
                if (s.after) katex.render(s.after, card.querySelector(".after"), { throwOnError: false, trust: false });
            } catch (err) {
                bridge.log(`KaTeX render failed in showSteps.after: ${err && err.message ? err.message : err}`, "warn");
            }
            card.addEventListener("click", () => { this.pauseAnim(); this.setActiveTab("animation"); renderer.showAnimStep(i); });
        });
    },

    renderAnimationStepList(steps) {
        const panel = document.getElementById("animStepsPanel");
        if (!steps.length) { panel.innerHTML = '<div class="anim-step-item">No animation steps.</div>'; return; }
        panel.innerHTML = steps.map((s, i) => `<button class="anim-step-item" data-anim-step="${i}">
            <span class="anim-step-num">Step ${i + 1}</span><span class="anim-step-text">${utils.prettyText(s.description || s.rule)}</span>
            <span class="anim-step-detail"><span class="math before"></span>${s.before && s.after ? '<span class="arr">→</span>' : ''}<span class="math after"></span></span>
        </button>`).join("");
        panel.querySelectorAll(".anim-step-item").forEach((btn, i) => {
            const s = steps[i];
            try {
                if (s.before) katex.render(s.before, btn.querySelector(".math.before"), { throwOnError: false, trust: false });
            } catch (err) {
                bridge.log(`KaTeX render failed in renderAnimationStepList.before: ${err && err.message ? err.message : err}`, "warn");
            }
            try {
                if (s.after) katex.render(s.after, btn.querySelector(".math.after"), { throwOnError: false, trust: false });
            } catch (err) {
                bridge.log(`KaTeX render failed in renderAnimationStepList.after: ${err && err.message ? err.message : err}`, "warn");
            }
            btn.addEventListener("click", () => { this.pauseAnim(); renderer.showAnimStep(i); });
        });
    },

    clearAnimStage() {
        document.getElementById("animMathDisplay").innerHTML = "";
        clearTimeout(state.badgeTimer); clearTimeout(state.descTimer);
        const badge = document.getElementById("animRuleBadge"); const desc = document.getElementById("animDescription");
        badge.className = "anim-rule-badge"; desc.className = "anim-description";
        badge.textContent = ""; desc.textContent = "";
        state.aCanvas.style.display = "none";
        state.transitionBusy = false; state.queuedDirection = 0; state.currentAnimCopyText = "";
    },

    updateIndicator() { renderer.updateIndicator(); },

    setSlideNotesOpen(open) {
        state.slideNotesOpen = !!open;
        const layout = document.getElementById("learningStageLayout");
        const panel = document.getElementById("slideNotesPanel");
        const btn = document.getElementById("slideNotesToggleBtn");
        if (layout) layout.classList.toggle("notes-collapsed", !state.slideNotesOpen);
        if (panel) panel.style.width = state.slideNotesOpen ? `${state.slideNotesWidth}px` : "0px";
        if (btn) btn.textContent = state.slideNotesOpen ? "Hide" : "Show";
        renderer.renderCurrentSlide();
    },

    insertSymbol(latex) {
        const start = state.mathField.selectionStart || 0;
        const end = state.mathField.selectionEnd || 0;
        const cur = state.mathField.value || "";
        const nextRaw = cur.slice(0, start) + latex + cur.slice(end);
        const next = utils.normalizeDisplayMath(nextRaw);
        state.mathField.value = next;
        const pos = Math.min(next.length, start + utils.normalizeDisplayMath(latex).length);
        state.mathField.focus(); state.mathField.setSelectionRange(pos, pos);
    },

    normalizeInputField() {
        const start = state.mathField.selectionStart || 0;
        const left = (state.mathField.value || "").slice(0, start);
        const normalizedLeft = utils.normalizeDisplayMath(left);
        const normalizedAll = utils.normalizeDisplayMath(state.mathField.value || "");
        if (normalizedAll !== state.mathField.value) {
            state.mathField.value = normalizedAll;
            const caret = Math.min(normalizedLeft.length, normalizedAll.length);
            state.mathField.setSelectionRange(caret, caret);
        }
    },

    openGlossaryTerm(termId) {
        const detail = document.getElementById("glossaryDetail");
        const t = state.glossaryById[termId];
        if (!detail || !t) return;
        this.setActiveScreen("learning");
        this.setLearningMode("glossary");
        detail.innerHTML = `
            <div class="learning-detail-head"><h2>${utils.prettyText(t.term || t.id)}</h2><p>${utils.prettyText(t.definition || "")}</p></div>
            <section class="learning-block"><h3>Aliases</h3><div class="learning-related-row">${(t.aliases || []).map(a => `<span class="glossary-chip">${utils.prettyText(a)}</span>`).join("") || 'None'}</div></section>
            <section class="learning-block"><h3>Related Topics</h3><div class="learning-related-row">${(t.related_topic_ids || []).map(id => `<button class="learning-related-btn" data-related-topic="${utils.escAttr(id)}">${utils.prettyText((state.learningTopicById[id] || {}).title || id)}</button>`).join("") || 'None'}</div></section>
        `;
    },

    async runCapacityAnalysis(pageIndex = 0) {
        const textEl = document.getElementById("capacityInput");
        const imgEl = document.getElementById("capacityWithImage");
        const preview = document.getElementById("capacityPreview");
        if (!textEl || !imgEl || !preview) return;
        state.capacityState.text = textEl.value || "";
        state.capacityState.withImage = !!imgEl.checked;
        state.capacityState.pageIndex = Math.max(0, pageIndex);
        preview.classList.add("loading");
        const res = await bridge.capacityTestSlide(state.capacityState.text, state.capacityState.withImage, state.capacityState.pageIndex, 1300, 812);
        if (!res.success) {
            preview.classList.remove("loading");
            // The bridge returns {success: false, error: "capability_unavailable", reason: "..."}
            // when the capacity worker is not wired up. Surface the human-readable
            // reason when present so the UI is honest about why nothing renders.
            const detail = res.reason || res.error;
            preview.textContent = res.error === "capability_unavailable"
                ? `Capacity render unavailable in this build${detail && detail !== res.error ? `: ${detail}` : "."}`
                : (detail ? `Capacity render unavailable: ${detail}` : "Capacity render unavailable");
            return;
        }
        state.capacityState.totalPages = Number(res.total_pages || 1);
        state.capacityState.pageIndex = Number(res.page_index || 0);
        state.capacityState.pageText = res.page_text || "";
        state.capacityState.allPagesText = Array.isArray(res.all_pages_text) ? res.all_pages_text : [state.capacityState.pageText];
        renderer.renderCapacityPage(res);
    },

    buildSyntheticCapacityText() {
        const sections = [];
        for (let i = 1; i <= 48; i += 1) {
            const id = String(i).padStart(3, "0");
            sections.push(`[CHK-${id}] Synthetic sentence ${i} for calibration.`);
        }
        return sections.join("\n\n");
    },

    buildDenseSyntheticCapacityText() {
        return "Alpha Beta Gamma Delta Epsilon ".repeat(20);
    },

    copyCurrentAnimationText() {
        if (state.currentAnimCopyText) utils.copyText(state.currentAnimCopyText);
        else { const fb = (document.getElementById("animMathDisplay")?.innerText || "").trim(); if (fb) utils.copyText(fb); }
    }
};

window.appAPI = app;
if (window.pywebview) app.boot();
else window.addEventListener("pywebviewready", () => app.boot());

// Bind screen navigation at DOM-ready so the static shell is navigable
// even when pywebview / boot() has not run yet (e.g. static file tests).
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".screen-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".screen-btn").forEach(b =>
                b.classList.toggle("active", b === btn));
            const solver = document.getElementById("solverScreen");
            const learning = document.getElementById("learningScreen");
            if (solver) solver.classList.toggle("active", btn.dataset.screen === "solver");
            if (learning) learning.classList.toggle("active", btn.dataset.screen === "learning");
        });
    });
});

export default app;
