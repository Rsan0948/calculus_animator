/**
 * UI Events module for handling DOM events and user interactions.
 */
import { state } from './state.js';
import * as utils from './utils.js';
import { bridge } from './bridge.js';
import { renderer } from './renderer.js';

export const ui_events = {
    bindUI(app) {
        document.getElementById("solveBtn").addEventListener("click", () => app.solve({ focusAnimation: true }));
        document.getElementById("clearBtn").addEventListener("click", () => app.clear());
        document.getElementById("calcTypeSelect").addEventListener("change", () => app.updateParams());
        document.getElementById("runDemoBtn").addEventListener("click", () => app.runSelectedDemo());
        document.getElementById("demoSelect").addEventListener("change", () => app.runSelectedDemo());
        document.getElementById("copyAnimStepBtn").addEventListener("click", () => app.copyCurrentAnimationText());
        state.mathField.addEventListener("input", () => app.normalizeInputField());
        document.getElementById("selectInputBtn").addEventListener("click", () => {
            state.mathField.focus();
            state.mathField.select();
        });
        document.getElementById("copyInputBtn").addEventListener("click", () => utils.copyText(state.mathField.value || ""));
        document.getElementById("deleteInputBtn").addEventListener("click", () => {
            state.mathField.value = "";
            state.mathField.focus();
        });
        document.getElementById("resultDisplay").addEventListener("click", () => {
            const text = document.getElementById("resultDisplay").dataset.copyText || "";
            if (text) utils.copyText(text);
        });
        const animLearnToggleBtn = document.getElementById("animLearnToggleBtn");
        if (animLearnToggleBtn) {
            animLearnToggleBtn.addEventListener("click", () => {
                const menu = document.getElementById("animRelatedMenu");
                if (!menu || !state.relatedTopicPicks.length) return;
                menu.classList.toggle("hidden");
            });
        }

        document.getElementById("formulaList").addEventListener("click", e => {
            const item = e.target.closest(".formula-item");
            if (!item) return;
            state.mathField.value = utils.normalizeDisplayMath(item.dataset.latex);
            const tag = item.dataset.tag;
            if (tag) document.getElementById("calcTypeSelect").value = tag;
            const p = JSON.parse(item.dataset.params || "{}");
            app.applyParams(p);
            app.updateParams();
        });
        const quickSymbolTabs = document.getElementById("quickSymbolTabs");
        if (quickSymbolTabs) {
            quickSymbolTabs.addEventListener("click", e => {
                const btn = e.target.closest("[data-symbol-tab]");
                if (!btn) return;
                state.activeQuickSymbolTab = btn.dataset.symbolTab || state.activeQuickSymbolTab;
                document.querySelectorAll(".quick-symbol-tab").forEach(t => t.classList.toggle("active", t.dataset.symbolTab === state.activeQuickSymbolTab));
                renderer.renderQuickSymbolGrid();
            });
        }
        const quickSymbolGrid = document.getElementById("quickSymbolGrid");
        if (quickSymbolGrid) {
            quickSymbolGrid.addEventListener("click", e => {
                const btn = e.target.closest(".sym-btn");
                if (!btn) return;
                app.insertSymbol(btn.dataset.latex || "");
            });
        }

        document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => {
            app.setActiveTab(tab.dataset.tab);
        }));
        document.querySelectorAll(".screen-btn").forEach(btn => {
            btn.addEventListener("click", () => app.setActiveScreen(btn.dataset.screen));
        });
        const toggleSolverSidebarBtn = document.getElementById("toggleSolverSidebarBtn");
        if (toggleSolverSidebarBtn) {
            toggleSolverSidebarBtn.addEventListener("click", () => {
                state.solverSidebarCollapsed = !state.solverSidebarCollapsed;
                const shell = document.getElementById("solverAppContainer");
                if (shell) shell.classList.toggle("solver-collapsed", state.solverSidebarCollapsed);
                toggleSolverSidebarBtn.textContent = state.solverSidebarCollapsed ? "Show Sidebar" : "Hide Sidebar";
            });
        }
        const learningSearch = document.getElementById("learningSearch");
        if (learningSearch) {
            learningSearch.addEventListener("input", () => renderer.renderLearningItems());
        }
        const learningModeTabs = document.getElementById("learningModeTabs");
        if (learningModeTabs) {
            learningModeTabs.addEventListener("click", e => {
                const btn = e.target.closest(".learning-mode-btn");
                if (!btn) return;
                app.setLearningMode(btn.dataset.learningMode || "home");
            });
        }
        const learningHome = document.getElementById("learningHomeMode");
        if (learningHome) {
            learningHome.addEventListener("click", e => {
                const card = e.target.closest("[data-home-mode]");
                if (!card) return;
                app.setLearningMode(card.dataset.homeMode || "library");
            });
        }
        const learningViews = document.getElementById("learningViewTabs");
        if (learningViews) {
            learningViews.addEventListener("click", e => {
                const btn = e.target.closest(".learning-view-btn");
                if (!btn) return;
                state.learningActiveView = btn.dataset.learningView || "concepts";
                renderer.renderLearningItems();
            });
        }
        const learningCats = document.getElementById("learningCategoryChips");
        if (learningCats) {
            learningCats.addEventListener("click", e => {
                const btn = e.target.closest(".learning-chip");
                if (!btn) return;
                state.learningActiveCategory = btn.dataset.learningCategory || "all";
                renderer.renderLearningItems();
            });
        }
        const learningList = document.getElementById("learningItemList");
        if (learningList) {
            learningList.addEventListener("click", e => {
                const btn = e.target.closest(".learning-topic-btn");
                if (!btn) return;
                const kind = btn.dataset.learningItemType;
                const id = btn.dataset.learningItemId || "";
                if (kind === "concept") state.learningSelectedTopicId = id;
                if (kind === "formula") state.learningSelectedFormulaId = id;
                if (kind === "symbol") state.learningSelectedSymbolId = id;
                renderer.renderLearningItems();
            });
        }
        const learningDetail = document.getElementById("learningDetail");
        if (learningDetail) {
            learningDetail.addEventListener("click", e => {
                const toggle = e.target.closest('[data-learning-toggle]');
                if (toggle) {
                    const block = toggle.closest(".learning-block.collapsible");
                    if (block) block.classList.toggle("collapsed");
                    return;
                }
                const btn = e.target.closest(".learning-related-btn");
                if (!btn) return;
                state.learningSelectedTopicId = btn.dataset.relatedTopic || "";
                state.learningActiveView = "concepts";
                renderer.renderLearningItems();
            });
        }
        const glossaryDetail = document.getElementById("glossaryDetail");
        if (glossaryDetail) {
            glossaryDetail.addEventListener("click", e => {
                const btn = e.target.closest(".learning-related-btn");
                if (!btn) return;
                state.learningSelectedTopicId = btn.dataset.relatedTopic || "";
                state.learningActiveView = "concepts";
                app.setLearningMode("library");
            });
        }
        const pathwaySearch = document.getElementById("pathwaySearch");
        if (pathwaySearch) {
            pathwaySearch.addEventListener("input", () => {
                if (state.showPathwayPicker) renderer.renderPathwayList();
                renderer.renderChapterList();
                renderer.renderCurrentSlide();
            });
        }
        const pathwayList = document.getElementById("pathwayList");
        if (pathwayList) {
            pathwayList.addEventListener("click", e => {
                const btn = e.target.closest("[data-pathway-id]");
                if (!btn) return;
                state.selectedPathwayId = btn.dataset.pathwayId || "";
                state.selectedChapterId = "";
                state.selectedSlideIndex = 0;
                state.showPathwayPicker = false;
                renderer.renderPathwayList();
                renderer.renderChapterList();
                renderer.renderCurrentSlide();
                app.saveState();
            });
        }
        const pathwayPickerToggleBtn = document.getElementById("pathwayPickerToggleBtn");
        if (pathwayPickerToggleBtn) {
            pathwayPickerToggleBtn.addEventListener("click", () => {
                state.showPathwayPicker = !state.showPathwayPicker;
                renderer.renderPathwayList();
            });
        }
        const chapterList = document.getElementById("chapterList");
        if (chapterList) {
            chapterList.addEventListener("click", e => {
                const btn = e.target.closest("[data-chapter-id]");
                if (!btn) return;
                state.selectedChapterId = btn.dataset.chapterId || "";
                state.selectedSlideIndex = 0;
                renderer.renderChapterList();
                renderer.renderCurrentSlide();
                app.saveState();
            });
        }
        const toggleSidebarBtn = document.getElementById("togglePathwaySidebarBtn");
        if (toggleSidebarBtn) {
            toggleSidebarBtn.addEventListener("click", () => {
                state.pathwaySidebarCollapsed = !state.pathwaySidebarCollapsed;
                const shell = document.querySelector("#learningPathwaysMode .learning-shell");
                if (shell) shell.classList.toggle("collapsed", state.pathwaySidebarCollapsed);
                toggleSidebarBtn.textContent = state.pathwaySidebarCollapsed ? "Show Sidebar" : "Hide Sidebar";
            });
        }
        const slideStage = document.getElementById("slideStage");
        if (slideStage) {
            slideStage.addEventListener("click", e => {
                const btn = e.target.closest("[data-stage-action]");
                if (!btn) return;
                const action = btn.dataset.stageAction;
                if (action === "toggle-text") {
                    state.showSlideTextDetails = !state.showSlideTextDetails;
                    const wrap = document.getElementById("learningSlideTextWrap");
                    if (wrap) wrap.classList.toggle("show", state.showSlideTextDetails);
                    const toggle = document.getElementById("toggleSlideTextBtn");
                    if (toggle) toggle.textContent = state.showSlideTextDetails ? "Hide Slide Text" : "Show Slide Text";
                    return;
                }
                if (action === "prev") {
                    state.selectedSlideIndex = Math.max(0, state.selectedSlideIndex - 1);
                    renderer.renderCurrentSlide();
                    app.saveState();
                    return;
                }
                if (action === "next") {
                    const pathway = (state.curriculum.pathways || []).find(p => p.id === state.selectedPathwayId);
                    const chapter = pathway ? (pathway.chapters || []).find(c => c.id === state.selectedChapterId) : null;
                    if (!chapter) return;
                    const progress = state.learningProgress[state.selectedPathwayId]?.[chapter.id] || {};
                    const midpoint = Math.floor((chapter.slides || []).length / 2);
                    if (chapter.midpoint_quiz && !progress.midpointTaken && state.selectedSlideIndex >= midpoint + 1) return;
                    state.selectedSlideIndex = Math.min((chapter.slides || []).length, state.selectedSlideIndex + 1);
                    renderer.renderCurrentSlide();
                    app.saveState();
                    return;
                }
                if (action === "toggle-notes") {
                    app.setSlideNotesOpen(!state.slideNotesOpen);
                }
            });
        }
        const slideNotesToggleBtn = document.getElementById("slideNotesToggleBtn");
        if (slideNotesToggleBtn) {
            slideNotesToggleBtn.addEventListener("click", () => app.setSlideNotesOpen(!state.slideNotesOpen));
        }
        const slideNotesTab = document.getElementById("slideNotesTab");
        if (slideNotesTab) {
            slideNotesTab.addEventListener("click", () => app.setSlideNotesOpen(!state.slideNotesOpen));
        }
        const notesResizer = document.getElementById("slideNotesResizer");
        if (notesResizer) {
            let drag = false;
            notesResizer.addEventListener("mousedown", () => { drag = true; });
            window.addEventListener("mouseup", () => { drag = false; });
            window.addEventListener("mousemove", e => {
                if (!drag || !state.slideNotesOpen) return;
                const layout = document.getElementById("learningStageLayout");
                const panel = document.getElementById("slideNotesPanel");
                if (!layout || !panel) return;
                const rect = layout.getBoundingClientRect();
                const desired = rect.right - e.clientX;
                state.slideNotesWidth = Math.max(300, Math.min(700, Math.round(desired)));
                panel.style.width = `${state.slideNotesWidth}px`;
            });
        }
        const quizGate = document.getElementById("quizGate");
        if (quizGate) {
            quizGate.addEventListener("click", e => {
                const btn = e.target.closest('[data-action="submit-mid-quiz"]');
                const microBtn = e.target.closest('[data-action="take-micro-quiz"]');
                const pathway = (state.curriculum.pathways || []).find(p => p.id === state.selectedPathwayId);
                const chapter = pathway ? (pathway.chapters || []).find(c => c.id === state.selectedChapterId) : null;
                if (!chapter) return;
                state.learningProgress[state.selectedPathwayId] = state.learningProgress[state.selectedPathwayId] || {};
                state.learningProgress[state.selectedPathwayId][chapter.id] = state.learningProgress[state.selectedPathwayId][chapter.id] || { microTaken: {} };
                const progress = state.learningProgress[state.selectedPathwayId][chapter.id];
                if (microBtn) {
                    const k = microBtn.dataset.microKey || String(state.selectedSlideIndex);
                    progress.microTaken[k] = true;
                    renderer.renderCurrentSlide();
                    return;
                }
                if (!btn) return;
                progress.midpointTaken = true;
                renderer.renderCurrentSlide();
            });
            quizGate.addEventListener("change", e => {
                const picked = e.target.closest('input[data-mid-quiz-choice]');
                if (!picked) return;
                const pathway = (state.curriculum.pathways || []).find(p => p.id === state.selectedPathwayId);
                const chapter = pathway ? (pathway.chapters || []).find(c => c.id === state.selectedChapterId) : null;
                if (!chapter) return;
                state.learningProgress[state.selectedPathwayId] = state.learningProgress[state.selectedPathwayId] || {};
                state.learningProgress[state.selectedPathwayId][chapter.id] = state.learningProgress[state.selectedPathwayId][chapter.id] || {};
                const progress = state.learningProgress[state.selectedPathwayId][chapter.id];
                progress.midpointTaken = true;
                renderer.renderCurrentSlide();
            });
        }
        const chapterTestPanel = document.getElementById("chapterTestPanel");
        if (chapterTestPanel) {
            chapterTestPanel.addEventListener("click", e => {
                const btn = e.target.closest('[data-action="take-final-test"]');
                if (!btn) return;
                const pathway = (state.curriculum.pathways || []).find(p => p.id === state.selectedPathwayId);
                const chapter = pathway ? (pathway.chapters || []).find(c => c.id === state.selectedChapterId) : null;
                if (!chapter) return;
                state.learningProgress[state.selectedPathwayId] = state.learningProgress[state.selectedPathwayId] || {};
                state.learningProgress[state.selectedPathwayId][chapter.id] = state.learningProgress[state.selectedPathwayId][chapter.id] || {};
                state.learningProgress[state.selectedPathwayId][chapter.id].testTaken = true;
                renderer.renderCurrentSlide();
            });
            chapterTestPanel.addEventListener("change", e => {
                const picked = e.target.closest('input[data-final-quiz-choice]');
                if (!picked) return;
                const pathway = (state.curriculum.pathways || []).find(p => p.id === state.selectedPathwayId);
                const chapter = pathway ? (pathway.chapters || []).find(c => c.id === state.selectedChapterId) : null;
                if (!chapter) return;
                state.learningProgress[state.selectedPathwayId] = state.learningProgress[state.selectedPathwayId] || {};
                state.learningProgress[state.selectedPathwayId][chapter.id] = state.learningProgress[state.selectedPathwayId][chapter.id] || {};
                state.learningProgress[state.selectedPathwayId][chapter.id].testTaken = true;
                renderer.renderCurrentSlide();
            });
        }
        const glossarySearch = document.getElementById("glossarySearch");
        if (glossarySearch) {
            glossarySearch.addEventListener("input", () => renderer.renderGlossaryList());
        }
        const glossaryList = document.getElementById("glossaryList");
        if (glossaryList) {
            glossaryList.addEventListener("click", e => {
                const btn = e.target.closest("[data-glossary-id]");
                if (!btn) return;
                app.openGlossaryTerm(btn.dataset.glossaryId || "");
            });
        }
        const capacityAnalyzeBtn = document.getElementById("capacityAnalyzeBtn");
        if (capacityAnalyzeBtn) {
            capacityAnalyzeBtn.addEventListener("click", () => app.runCapacityAnalysis(0));
        }
        const capacityLoadSyntheticBtn = document.getElementById("capacityLoadSyntheticBtn");
        if (capacityLoadSyntheticBtn) {
            capacityLoadSyntheticBtn.addEventListener("click", () => {
                const input = document.getElementById("capacityInput");
                if (!input) return;
                input.value = app.buildSyntheticCapacityText();
                state.capacityState.text = input.value;
                state.capacityState.pageIndex = 0;
                app.runCapacityAnalysis(0);
            });
        }
        const capacityLoadDenseBtn = document.getElementById("capacityLoadDenseBtn");
        if (capacityLoadDenseBtn) {
            capacityLoadDenseBtn.addEventListener("click", () => {
                const input = document.getElementById("capacityInput");
                if (!input) return;
                input.value = app.buildDenseSyntheticCapacityText();
                state.capacityState.text = input.value;
                state.capacityState.pageIndex = 0;
                app.runCapacityAnalysis(0);
            });
        }
        const capacityPrevBtn = document.getElementById("capacityPrevBtn");
        if (capacityPrevBtn) {
            capacityPrevBtn.addEventListener("click", () => app.runCapacityAnalysis(Math.max(0, state.capacityState.pageIndex - 1)));
        }
        const capacityNextBtn = document.getElementById("capacityNextBtn");
        if (capacityNextBtn) {
            capacityNextBtn.addEventListener("click", () => app.runCapacityAnalysis(state.capacityState.pageIndex + 1));
        }
        const capacityCopyPageBtn = document.getElementById("capacityCopyPageBtn");
        if (capacityCopyPageBtn) {
            capacityCopyPageBtn.addEventListener("click", () => utils.copyText(state.capacityState.pageText || ""));
        }
        const capacityCopyAllBtn = document.getElementById("capacityCopyAllBtn");
        if (capacityCopyAllBtn) {
            capacityCopyAllBtn.addEventListener("click", () => utils.copyText((state.capacityState.allPagesText || []).join("\n\n")));
        }
        const capacityCopyReportBtn = document.getElementById("capacityCopyReportBtn");
        if (capacityCopyReportBtn) {
            capacityCopyReportBtn.addEventListener("click", () => {
                const report = document.getElementById("capacityReportOutput");
                utils.copyText((report && report.value) ? report.value : "");
            });
        }
        document.addEventListener("click", e => {
            const link = e.target.closest(".glossary-link");
            if (!link) return;
            const termId = link.dataset.glossaryId || "";
            if (termId) app.openGlossaryTerm(termId);
        });
        const relatedPanel = document.getElementById("relatedLearningPanel");
        if (relatedPanel) {
            relatedPanel.addEventListener("click", e => {
                const btn = e.target.closest(".related-learning-link");
                if (!btn) return;
                app.openLearningTopic(btn.dataset.topicId || "");
            });
        }
        const animRelatedMenu = document.getElementById("animRelatedMenu");
        if (animRelatedMenu) {
            animRelatedMenu.addEventListener("click", e => {
                const btn = e.target.closest(".related-learning-link");
                if (!btn) return;
                app.openLearningTopic(btn.dataset.topicId || "");
            });
        }

        document.getElementById("animateAllBtn").addEventListener("click", () => app.playAnim());
        document.getElementById("pauseBtn").addEventListener("click", () => app.pauseAnim());
        document.getElementById("prevStepBtn").addEventListener("click", () => {
            app.pauseAnim();
            app.stepBack();
        });
        document.getElementById("nextStepBtn").addEventListener("click", () => {
            app.pauseAnim();
            app.stepForward();
        });
        document.getElementById("speedSlider").addEventListener("input", e => {
            document.getElementById("speedLabel").textContent = e.target.value + "×";
        });

        document.getElementById("zoomIn").addEventListener("click", () => { state.zoom *= 1.4; app.refreshGraph(); });
        document.getElementById("zoomOut").addEventListener("click", () => { state.zoom = Math.max(0.1, state.zoom / 1.4); app.refreshGraph(); });
        document.getElementById("resetView").addEventListener("click", () => { state.zoom = 1; app.refreshGraph(); });

        app.setSlideNotesOpen(false);
    }
};
