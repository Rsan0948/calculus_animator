/* Calculus Animator – main UI controller */
(function () {
    "use strict";

    let mathField, allFormulas = [], currentSteps = [], stepIdx = -1;
    let animPlaying = false, animTimer = null, zoom = 1, graphData = null;
    let solveResult = null;
    let demoMap = {};
    let learningLibrary = { categories: [], symbols: [], formulas: [], topics: [] };
    let learningTopicById = {};
    let learningFormulaById = {};
    let learningSymbolById = {};
    let learningActiveCategory = "all";
    let learningActiveView = "concepts";
    let learningSelectedTopicId = "";
    let learningSelectedFormulaId = "";
    let learningSelectedSymbolId = "";
    let learningMode = "home";
    let curriculum = { pathways: [] };
    let glossary = { terms: [] };
    let glossaryById = {};
    let glossaryLexicon = [];
    let selectedPathwayId = "";
    let selectedChapterId = "";
    let selectedSlideIndex = 0;
    const learningProgress = {};
    let relatedTopicPicks = [];
    let stepRenderToken = 0;
    let baseLatex = "";
    let transitionBusy = false;
    let queuedDirection = 0;
    let currentAnimCopyText = "";
    let learningSlideRenderToken = 0;
    let pathwaySidebarCollapsed = false;
    let solverSidebarCollapsed = false;
    let showSlideTextDetails = false;
    let slideNotesOpen = false;
    let slideNotesWidth = 420;
    let showPathwayPicker = false;
    let quickSymbolGroups = {};
    let activeQuickSymbolTab = "Calculus";
    let capacityState = {
        pageIndex: 0,
        totalPages: 0,
        allPagesText: [],
        pageText: "",
        withImage: false,
        text: "",
        lastStats: null,
    };
    let badgeTimer = null;
    let descTimer = null;
    const AUTO_STEP_MS = 4000;
    const GLYPH_ONLY_MS = 1500;
    const POST_REVEAL_MS = 450;
    const TRANSITION_MS = GLYPH_ONLY_MS + POST_REVEAL_MS;

    let gCanvas, gCtx, aCanvas, aCtx;

    function boot() {
        mathField = document.getElementById("mathInput");
        mathField.value = normalizeDisplayMath(mathField.value || "");
        bindUI();
        setupCanvases();
        loadFormulas();
        loadDemoProblems();
        loadSymbols();
        loadLearningLibrary();
        loadCurriculum();
        loadGlossary();
        updateParams();
        clearAnimStage();
    }

    if (window.pywebview) boot();
    else window.addEventListener("pywebviewready", boot);

    async function loadFormulas() {
        try {
            const raw = await pywebview.api.get_formulas();
            const data = JSON.parse(raw);
            allFormulas = data.formulas || [];
            renderCategories(data.categories || []);
            renderFormulas(allFormulas);
        } catch (e) { console.warn("formulas load failed", e); }
    }

    function renderCategories(cats) {
        const el = document.getElementById("categoryList");
        el.innerHTML = '<button class="category-btn active" data-category="all">All</button>' +
            cats.map(c => `<button class="category-btn" data-category="${c.id}">${c.icon} ${c.name}</button>`).join("");
        el.addEventListener("click", e => {
            const btn = e.target.closest(".category-btn");
            if (!btn) return;
            el.querySelectorAll(".category-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const cat = btn.dataset.category;
            renderFormulas(cat === "all" ? allFormulas : allFormulas.filter(f => f.category === cat));
        });
    }

    function renderFormulas(list) {
        const el = document.getElementById("formulaList");
        el.innerHTML = list.map(f => {
            const escLatex = escAttr(f.latex);
            const escTag = escAttr(f.tag || "");
            const escParams = escAttr(JSON.stringify(f.params || {}));
            return `<div class="formula-item" data-latex="${escLatex}" data-tag="${escTag}" data-params="${escParams}">
                <div class="name">${f.name}</div><div class="preview"></div></div>`;
        }).join("");
        el.querySelectorAll(".formula-item").forEach(item => {
            try { katex.render(item.dataset.latex, item.querySelector(".preview"), { throwOnError: false, displayMode: false }); } catch (_) {}
        });
    }

    async function loadDemoProblems() {
        try {
            const raw = await pywebview.api.get_demo_problems();
            const data = JSON.parse(raw);
            renderDemoDropdown(data.collections || []);
        } catch (e) {
            console.warn("demo load failed", e);
        }
    }

    function renderDemoDropdown(collections) {
        const sel = document.getElementById("demoSelect");
        demoMap = {};
        let html = '<option value="">Select a demo problem…</option>';
        collections.forEach(c => {
            const demos = c.demos || [];
            if (!demos.length) return;
            html += `<optgroup label="${escAttr(c.name || "Demo Collection")}">`;
            demos.forEach(d => {
                demoMap[d.id] = d;
                html += `<option value="${escAttr(d.id)}">${esc(d.title || d.id)}${d.subtitle ? " - " + esc(d.subtitle) : ""}</option>`;
            });
            html += "</optgroup>";
        });
        sel.innerHTML = html;
    }

    async function loadSymbols() {
        try {
            const raw = await pywebview.api.get_symbols();
            const data = JSON.parse(raw);
            renderSymbols(data.groups || []);
        } catch (_) {}
    }

    async function loadLearningLibrary() {
        try {
            const raw = await pywebview.api.get_learning_library();
            const data = JSON.parse(raw);
            renderLearningLibrary(data);
        } catch (e) {
            console.warn("learning load failed", e);
            renderLearningLibrary({ categories: [], symbols: [], formulas: [], topics: [] });
        }
        renderLearningHome();
    }

    async function loadCurriculum() {
        try {
            const raw = await pywebview.api.get_curriculum();
            const data = JSON.parse(raw);
            curriculum = { pathways: Array.isArray(data?.pathways) ? data.pathways : [] };
        } catch (e) {
            console.warn("curriculum load failed", e);
            curriculum = { pathways: [] };
        }
        if (!selectedPathwayId && curriculum.pathways.length) selectedPathwayId = curriculum.pathways[0].id;
        renderPathwayList();
        renderChapterList();
        renderCurrentSlide();
        renderLearningHome();
    }

    async function loadGlossary() {
        try {
            const raw = await pywebview.api.get_glossary();
            const data = JSON.parse(raw);
            glossary = { terms: Array.isArray(data?.terms) ? data.terms : [] };
        } catch (e) {
            console.warn("glossary load failed", e);
            glossary = { terms: [] };
        }
        glossaryById = {};
        glossaryLexicon = [];
        glossary.terms.forEach(t => {
            if (!t?.id) return;
            glossaryById[t.id] = t;
            const variants = [t.term, ...(t.aliases || [])].filter(Boolean);
            variants.forEach(v => glossaryLexicon.push({ token: String(v), id: t.id }));
        });
        glossaryLexicon.sort((a, b) => b.token.length - a.token.length);
        renderGlossaryList();
        renderLearningHome();
    }

    function renderLearningLibrary(data) {
        learningLibrary = {
            categories: Array.isArray(data?.categories) ? data.categories : [],
            symbols: Array.isArray(data?.symbols) ? data.symbols : [],
            formulas: Array.isArray(data?.formulas) ? data.formulas : [],
            topics: Array.isArray(data?.topics) ? data.topics : [],
        };
        learningTopicById = {};
        learningFormulaById = {};
        learningSymbolById = {};
        learningLibrary.topics.forEach(t => {
            if (t?.id) learningTopicById[t.id] = t;
        });
        learningLibrary.formulas.forEach(f => {
            if (f?.id) learningFormulaById[f.id] = f;
        });
        learningLibrary.symbols.forEach(s => {
            if (s?.id) learningSymbolById[s.id] = s;
        });
        if (!learningSelectedTopicId && learningLibrary.topics.length) learningSelectedTopicId = learningLibrary.topics[0].id;
        if (!learningSelectedFormulaId && learningLibrary.formulas.length) learningSelectedFormulaId = learningLibrary.formulas[0].id;
        if (!learningSelectedSymbolId && learningLibrary.symbols.length) learningSelectedSymbolId = learningLibrary.symbols[0].id;
        renderLearningViewTabs();
        renderLearningCategories();
        renderLearningItems();
        if (solveResult && solveResult.success) renderRelatedLearningLinks(solveResult);
    }

    function renderLearningViewTabs() {
        const el = document.getElementById("learningViewTabs");
        if (!el) return;
        const views = [
            { id: "concepts", label: "Concepts" },
            { id: "formulas", label: "Formulas" },
            { id: "symbols", label: "Symbols" },
        ];
        el.innerHTML = views.map(v => `<button class="learning-view-btn${v.id === learningActiveView ? " active" : ""}" data-learning-view="${v.id}">${v.label}</button>`).join("");
    }

    function renderLearningCategories() {
        const el = document.getElementById("learningCategoryChips");
        if (!el) return;
        if (learningActiveView !== "concepts") {
            el.innerHTML = `<div class="learning-chip-note">Category filters apply to concept pages.</div>`;
            return;
        }
        const chips = ['<button class="learning-chip active" data-learning-category="all">All Topics</button>'];
        learningLibrary.categories.forEach(c => {
            if (!c?.id) return;
            chips.push(`<button class="learning-chip" data-learning-category="${escAttr(c.id)}">${esc(c.name || c.id)}</button>`);
        });
        el.innerHTML = chips.join("");
        el.querySelectorAll(".learning-chip").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.learningCategory === learningActiveCategory);
        });
    }

    function renderLearningItems() {
        const list = document.getElementById("learningItemList");
        if (!list) return;
        renderLearningViewTabs();
        renderLearningCategories();
        const q = (document.getElementById("learningSearch")?.value || "").toLowerCase().trim();
        if (learningActiveView === "concepts") {
            const filteredTopics = learningLibrary.topics.filter(topic => {
                if (!topic) return false;
                if (learningActiveCategory !== "all" && topic.category !== learningActiveCategory) return false;
                if (!q) return true;
                const hay = [
                    topic.title || "",
                    topic.summary || "",
                    topic.narrative || "",
                    ...(topic.symbols || []),
                    ...(topic.formulas || []),
                ].join(" ").toLowerCase();
                return hay.includes(q);
            });
            if (!filteredTopics.length) {
                list.innerHTML = '<div class="learning-topic-empty">No concepts match this filter yet.</div>';
                renderLearningDetail({ type: "concept", topic: null });
                return;
            }
            list.innerHTML = filteredTopics.map(topic => `
                <button class="learning-topic-btn${topic.id === learningSelectedTopicId ? " active" : ""}" data-learning-item-type="concept" data-learning-item-id="${escAttr(topic.id)}">
                    <span class="learning-topic-title">${prettyText(topic.title || topic.id)}</span>
                    <span class="learning-topic-summary">${prettyText(topic.summary || "Concept overview placeholder")}</span>
                </button>
            `).join("");
            if (!learningSelectedTopicId || !filteredTopics.some(t => t.id === learningSelectedTopicId)) {
                learningSelectedTopicId = filteredTopics[0].id;
            }
            renderLearningDetail({ type: "concept", topic: learningTopicById[learningSelectedTopicId] || null });
            list.querySelectorAll(".learning-topic-btn").forEach(btn => {
                btn.classList.toggle("active", btn.dataset.learningItemId === learningSelectedTopicId);
            });
            return;
        }

        if (learningActiveView === "formulas") {
            const filteredFormulas = learningLibrary.formulas.filter(formula => {
                if (!formula) return false;
                if (!q) return true;
                const hay = [formula.name || "", formula.plain || "", formula.latex || "", ...(formula.tags || [])].join(" ").toLowerCase();
                return hay.includes(q);
            });
            if (!filteredFormulas.length) {
                list.innerHTML = '<div class="learning-topic-empty">No formulas match this filter yet.</div>';
                renderLearningDetail({ type: "formula", formula: null });
                return;
            }
            list.innerHTML = filteredFormulas.map(formula => `
                <button class="learning-topic-btn${formula.id === learningSelectedFormulaId ? " active" : ""}" data-learning-item-type="formula" data-learning-item-id="${escAttr(formula.id)}">
                    <span class="learning-topic-title">${prettyText(formula.name || formula.id)}</span>
                    <span class="learning-topic-summary">${prettyText(formula.plain || formula.latex || "Formula reference")}</span>
                </button>
            `).join("");
            if (!learningSelectedFormulaId || !filteredFormulas.some(f => f.id === learningSelectedFormulaId)) {
                learningSelectedFormulaId = filteredFormulas[0].id;
            }
            renderLearningDetail({ type: "formula", formula: learningFormulaById[learningSelectedFormulaId] || null });
            list.querySelectorAll(".learning-topic-btn").forEach(btn => {
                btn.classList.toggle("active", btn.dataset.learningItemId === learningSelectedFormulaId);
            });
            return;
        }

        const filteredSymbols = learningLibrary.symbols.filter(symbol => {
            if (!symbol) return false;
            if (!q) return true;
            const hay = [symbol.symbol || "", symbol.name || "", symbol.meaning || ""].join(" ").toLowerCase();
            return hay.includes(q);
        });
        if (!filteredSymbols.length) {
            list.innerHTML = '<div class="learning-topic-empty">No symbols match this filter yet.</div>';
            renderLearningDetail({ type: "symbol", symbol: null });
            return;
        }
        list.innerHTML = filteredSymbols.map(symbol => `
            <button class="learning-topic-btn${symbol.id === learningSelectedSymbolId ? " active" : ""}" data-learning-item-type="symbol" data-learning-item-id="${escAttr(symbol.id)}">
                <span class="learning-topic-title">${prettyText((symbol.symbol ? symbol.symbol + " " : "") + (symbol.name || symbol.id))}</span>
                <span class="learning-topic-summary">${prettyText(symbol.meaning || "Symbol reference")}</span>
            </button>
        `).join("");
        if (!learningSelectedSymbolId || !filteredSymbols.some(s => s.id === learningSelectedSymbolId)) {
            learningSelectedSymbolId = filteredSymbols[0].id;
        }
        renderLearningDetail({ type: "symbol", symbol: learningSymbolById[learningSelectedSymbolId] || null });
        list.querySelectorAll(".learning-topic-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.learningItemId === learningSelectedSymbolId);
        });
    }

    function renderLearningDetail(model) {
        const detail = document.getElementById("learningDetail");
        if (!detail) return;
        const section = (title, bodyHtml, options = {}) => {
            const collapsible = options.collapsible !== false;
            const collapsed = options.collapsed !== false;
            if (!collapsible) {
                return `<section class="learning-block">
                    <h3>${prettyText(title)}</h3>
                    <div class="learning-block-content">${bodyHtml}</div>
                </section>`;
            }
            return `<section class="learning-block collapsible${collapsed ? " collapsed" : ""}" data-learning-block="${escAttr(options.key || title.toLowerCase())}">
                <button class="learning-block-toggle" type="button" data-learning-toggle="1">
                    <h3>${prettyText(title)}</h3>
                    <span class="learning-block-caret">▾</span>
                </button>
                <div class="learning-block-content">${bodyHtml}</div>
            </section>`;
        };
        if (!model || (model.type === "concept" && !model.topic) || (model.type === "formula" && !model.formula) || (model.type === "symbol" && !model.symbol)) {
            detail.innerHTML = `<div class="learning-empty">
                <h3>Select an item</h3>
                <p>Choose a concept, formula, or symbol to view details.</p>
            </div>`;
            return;
        }

        if (model.type === "formula") {
            const formula = model.formula;
            const linkedTopics = learningLibrary.topics.filter(t => (t.formulas || []).includes(formula.id));
            detail.innerHTML = `
                <div class="learning-detail-head">
                    <h2>${prettyText(formula.name || formula.id)}</h2>
                    <p>Formula reference</p>
                </div>
                ${section("Plain Form", `<p>${prettyText(formula.plain || "")}</p>`, { key: "plain_form", collapsible: false })}
                ${section("LaTeX Form", `<p>${prettyText(formula.latex || "")}</p>`, { key: "latex_form", collapsed: true })}
                ${section("Associated Topics", `<div class="learning-related-row">
                        ${linkedTopics.map(t => `<button class="learning-related-btn" data-related-topic="${escAttr(t.id)}">${prettyText(t.title || t.id)}</button>`).join("") || '<span class="learning-empty-inline">No linked concept topics yet.</span>'}
                    </div>`, { key: "associated_topics", collapsed: true })}
            `;
            return;
        }

        if (model.type === "symbol") {
            const symbol = model.symbol;
            const linkedTopics = learningLibrary.topics.filter(t => (t.symbols || []).includes(symbol.id));
            detail.innerHTML = `
                <div class="learning-detail-head">
                    <h2>${prettyText(symbol.symbol || symbol.name || symbol.id)}</h2>
                    <p>${prettyText(symbol.name || "Symbol reference")}</p>
                </div>
                ${section("Meaning", `<p>${prettyText(symbol.meaning || "Meaning placeholder")}</p>`, { key: "symbol_meaning", collapsible: false })}
                ${section("Associated Topics", `<div class="learning-related-row">
                        ${linkedTopics.map(t => `<button class="learning-related-btn" data-related-topic="${escAttr(t.id)}">${prettyText(t.title || t.id)}</button>`).join("") || '<span class="learning-empty-inline">No linked concept topics yet.</span>'}
                    </div>`, { key: "symbol_topics", collapsed: true })}
            `;
            return;
        }

        const topic = model.topic;
        const symbolCards = (topic.symbols || []).map(id => {
            const sym = learningSymbolById[id];
            if (!sym) return null;
            return `<div class="learning-mini-card">
                <div class="learning-mini-head">${prettyText(sym.symbol || sym.name || id)}</div>
                <div class="learning-mini-body">${prettyText(sym.meaning || sym.name || "")}</div>
            </div>`;
        }).filter(Boolean).join("");

        const formulaCards = (topic.formulas || []).map(id => {
            const f = learningFormulaById[id];
            if (!f) return null;
            return `<div class="learning-mini-card">
                <div class="learning-mini-head">${prettyText(f.name || id)}</div>
                <div class="learning-mini-body">${prettyText(f.plain || f.latex || "")}</div>
            </div>`;
        }).filter(Boolean).join("");

        const exampleCards = (topic.examples || []).map(ex => `
            <article class="learning-example-card">
                <h4>${prettyText(ex.title || "Example")}</h4>
                <p class="learning-example-problem">${prettyText(ex.problem || "Problem placeholder")}</p>
                <div class="learning-example-steps">
                    ${(ex.steps || []).map((st, i) => `
                        <div class="learning-example-step">
                            <div class="learning-example-step-title">${i + 1}. ${prettyText(st.title || "Step")}</div>
                            <div class="learning-example-step-explain">${prettyText(st.explanation || "")}</div>
                            <div class="learning-example-step-math">${prettyText(st.math || "")}</div>
                        </div>
                    `).join("") || '<div class="learning-example-step-empty">Steps will appear here when content is added.</div>'}
                </div>
            </article>
        `).join("");

        const related = (topic.related || []).map(id => {
            const t = learningTopicById[id];
            if (!t) return null;
            return `<button class="learning-related-btn" data-related-topic="${escAttr(id)}">${prettyText(t.title || id)}</button>`;
        }).filter(Boolean).join("");

        detail.innerHTML = `
            <div class="learning-detail-head">
                <h2>${prettyText(topic.title || topic.id)}</h2>
                <p>${prettyText(topic.summary || "")}</p>
            </div>
            ${section("Narrative", `<p>${prettyText(topic.narrative || "Narrative placeholder for teaching notes.")}</p>`, { key: "narrative", collapsible: false })}
            ${section("Symbols", `<div class="learning-mini-grid">${symbolCards || '<div class="learning-empty-inline">No linked symbols yet.</div>'}</div>`, { key: "symbols", collapsed: true })}
            ${section("Formulas", `<div class="learning-mini-grid">${formulaCards || '<div class="learning-empty-inline">No linked formulas yet.</div>'}</div>`, { key: "formulas", collapsed: true })}
            ${section("Step-by-Step Examples", `<div class="learning-example-grid">${exampleCards || '<div class="learning-empty-inline">No examples linked yet.</div>'}</div>`, { key: "examples", collapsed: true })}
            ${section("Related Topics", `<div class="learning-related-row">${related || '<span class="learning-empty-inline">No related topics yet.</span>'}</div>`, { key: "related_topics", collapsed: true })}
        `;
    }

    function setLearningMode(mode) {
        learningMode = mode;
        document.querySelectorAll(".learning-mode-btn").forEach(btn => btn.classList.toggle("active", btn.dataset.learningMode === mode));
        document.querySelectorAll(".learning-mode").forEach(el => el.classList.remove("active"));
        const modeEl =
            document.getElementById(
                mode === "home" ? "learningHomeMode" :
                mode === "pathways" ? "learningPathwaysMode" :
                mode === "glossary" ? "learningGlossaryMode" :
                mode === "capacity" ? "learningCapacityMode" :
                "learningLibraryMode"
            );
        if (modeEl) modeEl.classList.add("active");
        if (mode === "home") {
            renderLearningHome();
        } else if (mode === "pathways") {
            showPathwayPicker = false;
            renderPathwayList();
            renderChapterList();
            renderCurrentSlide();
        } else if (mode === "glossary") {
            renderGlossaryList();
        } else if (mode === "capacity") {
            renderCapacityPage();
        } else {
            renderLearningItems();
        }
    }

    function renderLearningHome() {
        const stats = document.getElementById("learningHomeStats");
        if (!stats) return;
        const pathways = curriculum.pathways || [];
        const chapters = pathways.reduce((n, p) => n + ((p.chapters || []).length), 0);
        const slides = pathways.reduce((n, p) => n + (p.chapters || []).reduce((m, c) => m + ((c.slides || []).length), 0), 0);
        const concepts = (learningLibrary.topics || []).length;
        const formulas = (learningLibrary.formulas || []).length;
        const symbols = (learningLibrary.symbols || []).length;
        const terms = (glossary.terms || []).length;
        stats.innerHTML = [
            `<span class="learning-home-pill">${pathways.length} pathway${pathways.length === 1 ? "" : "s"}</span>`,
            `<span class="learning-home-pill">${chapters} chapters</span>`,
            `<span class="learning-home-pill">${slides} slides</span>`,
            `<span class="learning-home-pill">${concepts} concepts</span>`,
            `<span class="learning-home-pill">${formulas} formulas</span>`,
            `<span class="learning-home-pill">${symbols} symbols</span>`,
            `<span class="learning-home-pill">${terms} glossary terms</span>`,
        ].join("");
    }

    async function runCapacityAnalysis(pageIndex = 0) {
        const textEl = document.getElementById("capacityInput");
        const imgEl = document.getElementById("capacityWithImage");
        const preview = document.getElementById("capacityPreview");
        if (!textEl || !imgEl || !preview || !window.pywebview || !pywebview.api || !pywebview.api.capacity_test_slide) return;
        capacityState.text = textEl.value || "";
        capacityState.withImage = !!imgEl.checked;
        capacityState.pageIndex = Math.max(0, pageIndex);
        preview.classList.add("loading");
        preview.textContent = "Analyzing capacity...";
        try {
            const raw = await pywebview.api.capacity_test_slide(capacityState.text, capacityState.withImage, capacityState.pageIndex, 1300, 812);
            const res = JSON.parse(raw || "{}");
            if (!res.success) {
                preview.classList.remove("loading");
                preview.textContent = "Capacity render unavailable";
                return;
            }
            capacityState.totalPages = Number(res.total_pages || 1);
            capacityState.pageIndex = Number(res.page_index || 0);
            capacityState.pageText = res.page_text || "";
            capacityState.allPagesText = Array.isArray(res.all_pages_text) ? res.all_pages_text : [capacityState.pageText];
            renderCapacityPage(res);
        } catch (_) {
            preview.classList.remove("loading");
            preview.textContent = "Capacity render unavailable";
        }
    }

    function renderCapacityPage(res = null) {
        const preview = document.getElementById("capacityPreview");
        const text = document.getElementById("capacityPageText");
        const meta = document.getElementById("capacityPageMeta");
        const stats = document.getElementById("capacityStats");
        const report = document.getElementById("capacityReportOutput");
        const prevBtn = document.getElementById("capacityPrevBtn");
        const nextBtn = document.getElementById("capacityNextBtn");
        if (!preview || !text || !meta || !stats || !prevBtn || !nextBtn || !report) return;

        if (res && res.data_url) {
            preview.classList.remove("loading");
            preview.innerHTML = `<img class="learning-slide-visual-img" src="${res.data_url}" alt="Capacity test slide" draggable="false">`;
            text.textContent = capacityState.pageText || "";
            const p = capacityState.pageIndex + 1;
            const t = Math.max(1, capacityState.totalPages);
            meta.textContent = `Page ${p} / ${t}`;
            stats.textContent = `Chars on page: ${res.chars_on_page || 0} · Usable chars (non-space): ${res.usable_chars_on_page || 0} · Lines: ${res.max_lines || 0}`;
            capacityState.lastStats = {
                page: p,
                totalPages: t,
                charsOnPage: Number(res.chars_on_page || 0),
                usableCharsOnPage: Number(res.usable_chars_on_page || 0),
                maxLines: Number(res.max_lines || 0),
                lineHeightPx: Number(res.line_height_px || 0),
                withImage: !!res.with_image,
                overflowChars: Number(res.overflow_chars || 0),
            };
            report.value = [
                "Capacity Test Report",
                `with_image=${capacityState.lastStats.withImage}`,
                `page=${capacityState.lastStats.page}/${capacityState.lastStats.totalPages}`,
                `chars_on_page=${capacityState.lastStats.charsOnPage}`,
                `usable_chars_on_page=${capacityState.lastStats.usableCharsOnPage}`,
                `max_lines=${capacityState.lastStats.maxLines}`,
                `line_height_px=${capacityState.lastStats.lineHeightPx}`,
                `overflow_chars=${capacityState.lastStats.overflowChars}`,
                "",
                "PAGE_TEXT_START",
                capacityState.pageText || "",
                "PAGE_TEXT_END",
            ].join("\n");
        } else if (!preview.innerHTML) {
            preview.classList.remove("loading");
            preview.textContent = "Run analysis to render test slide.";
            text.textContent = "";
            meta.textContent = "";
            stats.textContent = "";
            report.value = "";
        }

        prevBtn.disabled = capacityState.pageIndex <= 0;
        nextBtn.disabled = capacityState.pageIndex >= Math.max(0, capacityState.totalPages - 1);
    }

    function buildSyntheticCapacityText() {
        const sections = [];
        for (let i = 1; i <= 48; i += 1) {
            const id = String(i).padStart(3, "0");
            sections.push(
                `[CHK-${id}] ` +
                `This is synthetic calibration sentence ${i}. ` +
                `It intentionally uses mixed word lengths to emulate realistic reading behavior. ` +
                `Marker CHK-${id} should help identify exact cutoff points.`
            );
        }
        return sections.join("\n\n");
    }

    function buildDenseSyntheticCapacityText() {
        const parts = [];
        for (let i = 1; i <= 64; i += 1) {
            const id = String(i).padStart(3, "0");
            parts.push(
                `[CHK-${id}] ` +
                `Dense block ${i}: alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau ` +
                `upsilon phi chi psi omega. This sequence is designed to stress wrapping and hard clipping behavior in a repeatable way.`
            );
        }
        return parts.join("\n");
    }

    function getSelectedPathway() {
        return (curriculum.pathways || []).find(p => p.id === selectedPathwayId) || null;
    }

    function getSelectedChapter() {
        const pathway = getSelectedPathway();
        if (!pathway) return null;
        return (pathway.chapters || []).find(c => c.id === selectedChapterId) || null;
    }

    function renderPathwayList() {
        const list = document.getElementById("pathwayList");
        const pickerWrap = document.getElementById("pathwayPickerWrap");
        const selectedLabel = document.getElementById("selectedPathwayLabel");
        const pickerToggle = document.getElementById("pathwayPickerToggleBtn");
        if (!list) return;
        const q = (document.getElementById("pathwaySearch")?.value || "").toLowerCase().trim();
        const items = (curriculum.pathways || []).filter(p => {
            if (!q) return true;
            return [p.title, p.level, p.description].join(" ").toLowerCase().includes(q);
        });
        if (!items.length) {
            list.innerHTML = '<div class="learning-topic-empty">No pathways match this search.</div>';
            return;
        }
        if (!selectedPathwayId || !items.some(p => p.id === selectedPathwayId)) selectedPathwayId = items[0].id;
        list.innerHTML = items.map(p => `
            <button class="learning-topic-btn${p.id === selectedPathwayId ? " active" : ""}" data-pathway-id="${escAttr(p.id)}">
                <span class="learning-topic-title">${prettyText(p.title || p.id)}</span>
                <span class="learning-topic-summary">${prettyText(p.description || p.level || "")}</span>
            </button>
        `).join("");
        const selected = items.find(p => p.id === selectedPathwayId) || null;
        if (selectedLabel) selectedLabel.innerHTML = selected ? prettyText(selected.title || selected.id) : "No course selected";
        if (pickerWrap) pickerWrap.classList.toggle("is-hidden", !showPathwayPicker);
        if (pickerToggle) pickerToggle.textContent = showPathwayPicker ? "Hide Courses" : "Change Course";
    }

    function renderChapterList() {
        const list = document.getElementById("chapterList");
        if (!list) return;
        const pathway = getSelectedPathway();
        if (!pathway) {
            list.innerHTML = '<div class="learning-topic-empty">No chapters loaded.</div>';
            return;
        }
        const q = (document.getElementById("pathwaySearch")?.value || "").toLowerCase().trim();
        const chapters = (pathway.chapters || []).filter(c => {
            if (!q) return true;
            return [c.title, c.description].join(" ").toLowerCase().includes(q);
        });
        const allChapters = pathway.chapters || [];
        if (!selectedChapterId || !allChapters.some(c => c.id === selectedChapterId)) {
            selectedChapterId = allChapters[0]?.id || "";
            selectedSlideIndex = 0;
        }
        if (selectedChapterId && !chapters.some(c => c.id === selectedChapterId) && chapters.length) {
            selectedChapterId = chapters[0].id;
            selectedSlideIndex = 0;
        }
        list.innerHTML = chapters.map(c => `
            <button class="learning-topic-btn${c.id === selectedChapterId ? " active" : ""}" data-chapter-id="${escAttr(c.id)}">
                <span class="learning-topic-title">${prettyText(c.title || c.id)}</span>
                <span class="learning-topic-summary">${prettyText(c.description || "")}</span>
            </button>
        `).join("") || '<div class="learning-topic-empty">No chapters yet.</div>';
    }

    function getChapterProgress(pathwayId, chapterId) {
        learningProgress[pathwayId] = learningProgress[pathwayId] || {};
        learningProgress[pathwayId][chapterId] = learningProgress[pathwayId][chapterId] || { midpointTaken: false, testTaken: false, microTaken: {} };
        return learningProgress[pathwayId][chapterId];
    }

    function renderCurrentSlide() {
        const stage = document.getElementById("slideStage");
        const quizGate = document.getElementById("quizGate");
        const testPanel = document.getElementById("chapterTestPanel");
        const notesBody = document.getElementById("slideNotesBody");
        if (!stage || !quizGate || !testPanel) return;
        const pathway = getSelectedPathway();
        const chapter = getSelectedChapter();
        if (!pathway || !chapter) {
            stage.innerHTML = '<div class="learning-empty">Select a chapter to begin.</div>';
            quizGate.innerHTML = "";
            testPanel.innerHTML = "";
            if (notesBody) notesBody.innerHTML = "";
            return;
        }
        const slides = chapter.slides || [];
        if (!slides.length) {
            stage.innerHTML = `<div class="learning-empty">This chapter is scaffolded and ready for content. Add slides to <code>data/curriculum.json</code>.</div>`;
            quizGate.innerHTML = "";
            testPanel.innerHTML = renderChapterTest(chapter, pathway.id);
            if (notesBody) notesBody.innerHTML = "";
            return;
        }
        selectedSlideIndex = Math.max(0, Math.min(slides.length, selectedSlideIndex));
        const introMode = selectedSlideIndex === 0;
        const contentIndex = Math.max(0, selectedSlideIndex - 1);
        const slide = slides[contentIndex];
        const slideTitle = (slide?.title || slide?.id || "Slide");
        const titleLower = String(slideTitle).toLowerCase();
        const isWorkedTitle = titleLower.includes("worked example");
        const isCompactTitle = isWorkedTitle || String(slideTitle).length > 44;
        const titleClass = `learning-slide-title${isCompactTitle ? " compact" : ""}${isWorkedTitle ? " worked" : ""}`;
        const blocks = (slide.content_blocks || []).map(b => `
            <div class="learning-block-card ${escAttr(b.kind || "text")}">
                ${prettyText(b.text || "")}
            </div>
        `).join("");
        const graphics = (slide.graphics || []).map(g => `<span class="glossary-chip">${prettyText(g.kind || "graphic")}: ${prettyText(g.name || "")}</span>`).join("");
        if (introMode) {
            stage.innerHTML = `
                <div class="learning-stage-top">
                    <button class="btn btn-small" id="prevSlideBtn" data-stage-action="prev">← Previous Slide</button>
                    <button class="btn btn-small" id="nextSlideBtn" data-stage-action="next">Next Slide →</button>
                    <button class="btn btn-small btn-secondary" data-stage-action="toggle-notes">${slideNotesOpen ? "Hide Notes" : "Show Notes"}</button>
                </div>
                <div class="learning-slide-sub">${prettyText(pathway.title || "Pathway")} · Slide 0 / ${slides.length}</div>
                <div class="learning-slide-title">${prettyText(chapter.title || "Chapter")}</div>
                <div class="learning-empty-inline">${prettyText(chapter.description || "Chapter overview")}</div>
            `;
        } else {
            stage.innerHTML = `
                <div class="learning-stage-top">
                    <button class="btn btn-small" id="prevSlideBtn" data-stage-action="prev">← Previous Slide</button>
                    <button class="btn btn-small" id="nextSlideBtn" data-stage-action="next">Next Slide →</button>
                    <button class="btn btn-small btn-secondary" data-stage-action="toggle-notes">${slideNotesOpen ? "Hide Notes" : "Show Notes"}</button>
                    <button class="btn btn-small btn-secondary" id="toggleSlideTextBtn" data-stage-action="toggle-text">${showSlideTextDetails ? "Hide Slide Text" : "Show Slide Text"}</button>
                </div>
                <div class="learning-slide-sub">${prettyText(chapter.title)} · Slide ${selectedSlideIndex} / ${slides.length}</div>
                <div class="${titleClass}">${prettyText(slideTitle)}</div>
                <div id="learningSlideVisualHost" class="learning-slide-visual loading">Rendering slide visual…</div>
                <div id="learningSlideTextWrap" class="learning-slide-text${showSlideTextDetails ? " show" : ""}">
                    ${graphics ? `<div class="learning-related-row" style="margin-bottom:10px">${graphics}</div>` : ""}
                    ${blocks || '<div class="learning-empty-inline">No blocks in this slide yet.</div>'}
                </div>
            `;
            renderLearningSlideVisual(pathway.id, chapter.id, contentIndex);
        }
        if (notesBody) {
            if (introMode) {
                notesBody.innerHTML = `
                    <div class="slide-notes-item"><span class="k">chapter</span><div>${prettyText(chapter.description || "No chapter notes yet.")}</div></div>
                `;
            } else {
                const fullBlocks = slide.content_blocks || [];
                notesBody.innerHTML = fullBlocks.map(b => `
                    <div class="slide-notes-item">
                        <span class="k">${prettyText((b.kind || "text").toUpperCase())}</span>
                        <div>${prettyText(b.text || "")}</div>
                    </div>
                `).join("") || '<div class="slide-notes-item">No notes for this slide.</div>';
            }
        }

        quizGate.innerHTML = [renderMicroQuiz(pathway.id, chapter), renderQuizGate(pathway.id, chapter)].filter(Boolean).join("");
        testPanel.innerHTML = renderChapterTest(chapter, pathway.id);
        updateSlideControlState(pathway.id, chapter);
    }

    async function renderLearningSlideVisual(pathwayId, chapterId, slideIndex) {
        const token = ++learningSlideRenderToken;
        const host = document.getElementById("learningSlideVisualHost");
        if (!host || !window.pywebview || !pywebview.api || !pywebview.api.render_learning_slide) return;
        try {
            const dpr = Math.max(1.4, Math.min(2.2, window.devicePixelRatio || 1.6));
            const w = Math.max(1600, Math.floor((host.clientWidth || 980) * dpr));
            const h = Math.floor(w * 10 / 16);
            const raw = await pywebview.api.render_learning_slide(pathwayId, chapterId, slideIndex, w, h);
            if (token !== learningSlideRenderToken) return;
            const res = JSON.parse(raw || "{}");
            if (!res.success || !res.data_url) {
                host.classList.remove("loading");
                host.innerHTML = `<div class="learning-empty-inline">Slide visual unavailable.</div>`;
                const textWrap = document.getElementById("learningSlideTextWrap");
                if (textWrap) textWrap.classList.add("show");
                return;
            }
            host.classList.remove("loading");
            host.innerHTML = `<img class="learning-slide-visual-img" src="${res.data_url}" alt="Rendered learning slide">`;
        } catch (_) {
            if (token !== learningSlideRenderToken) return;
            host.classList.remove("loading");
            host.innerHTML = `<div class="learning-empty-inline">Slide visual unavailable.</div>`;
            const textWrap = document.getElementById("learningSlideTextWrap");
            if (textWrap) textWrap.classList.add("show");
        }
    }

    function renderMicroQuiz(pathwayId, chapter) {
        const interval = Number(chapter?.micro_quiz_interval || 0);
        if (!interval || interval < 2) return "";
        const slides = chapter.slides || [];
        if (selectedSlideIndex <= 0) return "";
        const contentNumber = selectedSlideIndex;
        if (slides.length < interval + 2 || contentNumber >= slides.length) return "";
        if (contentNumber % interval !== 0) return "";
        const progress = getChapterProgress(pathwayId, chapter.id);
        const key = String(contentNumber);
        return `
            <div class="learning-quiz-title">Micro Quiz Checkpoint</div>
            <div class="learning-q-meta">Long chapter check-in at slide ${contentNumber}. Recommended for retention.</div>
            <button class="btn btn-small btn-secondary" data-action="take-micro-quiz" data-micro-key="${escAttr(key)}">${progress.microTaken[key] ? "Micro Quiz Taken" : "Take Micro Quiz"}</button>
        `;
    }

    function renderQuizGate(pathwayId, chapter) {
        const slides = chapter.slides || [];
        if (!slides.length || !chapter.midpoint_quiz) return "";
        const midpoint = Math.floor(slides.length / 2);
        const progress = getChapterProgress(pathwayId, chapter.id);
        if (selectedSlideIndex <= 0) return "";
        const shouldShow = selectedSlideIndex >= midpoint + 1 || progress.midpointTaken;
        if (!shouldShow) return "";
        const quiz = chapter.midpoint_quiz;
        const qList = (quiz.questions || []);
        const questions = qList.map((q, idx) => `
            <div class="learning-question">
                <div class="learning-q-prompt">${idx + 1}. ${prettyText(q.prompt || "")}</div>
                ${(q.choices || []).map((c, cidx) => `<label class="learning-q-choice"><input data-mid-quiz-choice="1" type="radio" name="quiz_${escAttr(q.id || idx)}" value="${cidx}"> ${prettyText(c)}</label>`).join("")}
                <div class="learning-q-meta">${prettyText(q.explanation || "")}</div>
            </div>
        `).join("");
        const placeholderQuestion = `
            <div class="learning-question">
                <div class="learning-q-prompt">Quick checkpoint (placeholder): pick any answer to continue.</div>
                <label class="learning-q-choice"><input data-mid-quiz-choice="1" type="radio" name="quiz_placeholder" value="0"> I understand this section enough to continue</label>
                <label class="learning-q-choice"><input data-mid-quiz-choice="1" type="radio" name="quiz_placeholder" value="1"> I want to continue and review notes as needed</label>
            </div>
        `;
        return `
            <div class="learning-quiz-title">Required Mid-Chapter Quiz (Take Required, Pass Not Required)</div>
            ${questions || placeholderQuestion}
            <button class="btn btn-small btn-secondary" data-action="submit-mid-quiz">${progress.midpointTaken ? "Quiz Taken" : "Mark Quiz As Taken"}</button>
        `;
    }

    function renderChapterTest(chapter, pathwayId) {
        if (!chapter?.final_test) return "";
        const slides = chapter.slides || [];
        if (!slides.length || selectedSlideIndex < slides.length) return "";
        const progress = getChapterProgress(pathwayId, chapter.id);
        const t = chapter.final_test;
        const qList = t.questions || [];
        const questions = qList.slice(0, 1).map((q, idx) => `
            <div class="learning-question">
                <div class="learning-q-prompt">${idx + 1}. ${prettyText(q.prompt || "Choose any answer to mark this optional test attempted.")}</div>
                ${((q.choices || []).length ? q.choices : ["Option A", "Option B"]).map((c, cidx) => `<label class="learning-q-choice"><input data-final-quiz-choice="1" type="radio" name="final_quiz_${escAttr(q.id || idx)}" value="${cidx}"> ${prettyText(c)}</label>`).join("")}
            </div>
        `).join("");
        const placeholderQuestion = `
            <div class="learning-question">
                <div class="learning-q-prompt">Optional chapter test placeholder: click any answer to mark attempted.</div>
                <label class="learning-q-choice"><input data-final-quiz-choice="1" type="radio" name="final_quiz_placeholder" value="0"> Continue to next chapter</label>
                <label class="learning-q-choice"><input data-final-quiz-choice="1" type="radio" name="final_quiz_placeholder" value="1"> Revisit this chapter first</label>
            </div>
        `;
        return `
            <div class="learning-test-title">Optional Recommended Chapter Test</div>
            <div class="learning-q-meta">${prettyText(t.title || "Chapter Test")}</div>
            <div class="learning-q-meta">Questions: ${(t.questions || []).length}</div>
            ${questions || placeholderQuestion}
            <button class="btn btn-small btn-secondary" data-action="take-final-test">${progress.testTaken ? "Test Attempted" : "Start Test (Optional)"}</button>
        `;
    }

    function updateSlideControlState(pathwayId, chapter) {
        const prevBtn = document.getElementById("prevSlideBtn");
        const nextBtn = document.getElementById("nextSlideBtn");
        const slides = chapter.slides || [];
        const progress = getChapterProgress(pathwayId, chapter.id);
        const midpoint = Math.floor(slides.length / 2);
        if (prevBtn) prevBtn.disabled = selectedSlideIndex <= 0;
        if (nextBtn) {
            const blockedByQuiz = chapter.midpoint_quiz && !progress.midpointTaken && selectedSlideIndex >= midpoint + 1;
            nextBtn.disabled = selectedSlideIndex >= slides.length || blockedByQuiz;
        }
    }

    function renderGlossaryList() {
        const list = document.getElementById("glossaryList");
        if (!list) return;
        const q = (document.getElementById("glossarySearch")?.value || "").toLowerCase().trim();
        const terms = (glossary.terms || []).filter(t => {
            if (!q) return true;
            return [t.term, ...(t.aliases || []), t.definition].join(" ").toLowerCase().includes(q);
        });
        list.innerHTML = terms.map(t => `
            <button class="learning-topic-btn" data-glossary-id="${escAttr(t.id)}">
                <span class="learning-topic-title">${prettyText(t.term || t.id)}</span>
                <span class="learning-topic-summary">${prettyText(t.definition || "")}</span>
            </button>
        `).join("") || '<div class="learning-topic-empty">No glossary terms match this search.</div>';
    }

    function openGlossaryTerm(termId) {
        const detail = document.getElementById("glossaryDetail");
        const t = glossaryById[termId];
        if (!detail || !t) return;
        setActiveScreen("learning");
        setLearningMode("glossary");
        detail.innerHTML = `
            <div class="learning-detail-head">
                <h2>${prettyText(t.term || t.id)}</h2>
                <p>${prettyText(t.definition || "")}</p>
            </div>
            <section class="learning-block">
                <h3>Aliases</h3>
                <div class="learning-related-row">${(t.aliases || []).map(a => `<span class="glossary-chip">${prettyText(a)}</span>`).join("") || '<span class="learning-empty-inline">No aliases.</span>'}</div>
            </section>
            <section class="learning-block">
                <h3>Related Topics</h3>
                <div class="learning-related-row">${(t.related_topic_ids || []).map(id => `<button class="learning-related-btn" data-related-topic="${escAttr(id)}">${prettyText((learningTopicById[id] || {}).title || id)}</button>`).join("") || '<span class="learning-empty-inline">No related topics.</span>'}</div>
            </section>
        `;
    }

    function renderSymbols(groups) {
        quickSymbolGroups = {};
        const normalizeKey = (name) => {
            const n = String(name || "").toLowerCase();
            if (n.includes("calc")) return "Calculus";
            if (n.includes("func")) return "Functions";
            if (n.includes("greek")) return "Greek";
            if (n.includes("oper")) return "Operators";
            return null;
        };
        (groups || []).forEach(g => {
            const k = normalizeKey(g.name);
            if (!k) return;
            quickSymbolGroups[k] = g.symbols || [];
        });
        const order = ["Calculus", "Functions", "Greek", "Operators"];
        if (!order.some(k => k === activeQuickSymbolTab && (quickSymbolGroups[k] || []).length)) {
            activeQuickSymbolTab = order.find(k => (quickSymbolGroups[k] || []).length) || "Calculus";
        }
        const tabs = document.getElementById("quickSymbolTabs");
        const grid = document.getElementById("quickSymbolGrid");
        if (!tabs || !grid) return;
        tabs.innerHTML = order.map(name => {
            const count = (quickSymbolGroups[name] || []).length;
            if (!count) return "";
            return `<button class="quick-symbol-tab${name === activeQuickSymbolTab ? " active" : ""}" data-symbol-tab="${escAttr(name)}">${name}</button>`;
        }).join("");
        renderQuickSymbolGrid();
    }

    function renderQuickSymbolGrid() {
        const grid = document.getElementById("quickSymbolGrid");
        if (!grid) return;
        const symbols = quickSymbolGroups[activeQuickSymbolTab] || [];
        if (!symbols.length) {
            grid.innerHTML = `<span class="learning-empty-inline">No symbols in this group.</span>`;
            return;
        }
        grid.innerHTML = symbols.map(s =>
            `<button class="sym-btn" data-latex="${escAttr(s.latex || "")}" title="${escAttr(s.latex || "")}">${esc(s.label || "")}</button>`
        ).join("");
    }

    function insertSymbol(latex) {
        if (!mathField) return;
        const start = mathField.selectionStart || 0;
        const end = mathField.selectionEnd || 0;
        const cur = mathField.value || "";
        const nextRaw = cur.slice(0, start) + latex + cur.slice(end);
        const next = normalizeDisplayMath(nextRaw);
        mathField.value = next;
        const pos = Math.min(next.length, start + normalizeDisplayMath(latex).length);
        mathField.focus();
        mathField.setSelectionRange(pos, pos);
    }

    function bindUI() {
        document.getElementById("solveBtn").addEventListener("click", () => solve({ focusAnimation: true }));
        document.getElementById("clearBtn").addEventListener("click", clear);
        document.getElementById("calcTypeSelect").addEventListener("change", updateParams);
        document.getElementById("runDemoBtn").addEventListener("click", runSelectedDemo);
        document.getElementById("demoSelect").addEventListener("change", runSelectedDemo);
        document.getElementById("copyAnimStepBtn").addEventListener("click", copyCurrentAnimationText);
        mathField.addEventListener("input", () => normalizeInputField());
        document.getElementById("selectInputBtn").addEventListener("click", () => {
            mathField.focus();
            mathField.select();
        });
        document.getElementById("copyInputBtn").addEventListener("click", () => copyText(mathField.value || ""));
        document.getElementById("deleteInputBtn").addEventListener("click", () => {
            mathField.value = "";
            mathField.focus();
        });
        document.getElementById("resultDisplay").addEventListener("click", () => {
            const text = document.getElementById("resultDisplay").dataset.copyText || "";
            if (text) copyText(text);
        });
        const animLearnToggleBtn = document.getElementById("animLearnToggleBtn");
        if (animLearnToggleBtn) {
            animLearnToggleBtn.addEventListener("click", () => {
                const menu = document.getElementById("animRelatedMenu");
                if (!menu || !relatedTopicPicks.length) return;
                menu.classList.toggle("hidden");
            });
        }

        document.getElementById("formulaList").addEventListener("click", e => {
            const item = e.target.closest(".formula-item");
            if (!item) return;
            mathField.value = normalizeDisplayMath(item.dataset.latex);
            const tag = item.dataset.tag;
            if (tag) document.getElementById("calcTypeSelect").value = tag;
            const p = JSON.parse(item.dataset.params || "{}");
            applyParams(p);
            updateParams();
        });
        const quickSymbolTabs = document.getElementById("quickSymbolTabs");
        if (quickSymbolTabs) {
            quickSymbolTabs.addEventListener("click", e => {
                const btn = e.target.closest("[data-symbol-tab]");
                if (!btn) return;
                activeQuickSymbolTab = btn.dataset.symbolTab || activeQuickSymbolTab;
                document.querySelectorAll(".quick-symbol-tab").forEach(t => t.classList.toggle("active", t.dataset.symbolTab === activeQuickSymbolTab));
                renderQuickSymbolGrid();
            });
        }
        const quickSymbolGrid = document.getElementById("quickSymbolGrid");
        if (quickSymbolGrid) {
            quickSymbolGrid.addEventListener("click", e => {
                const btn = e.target.closest(".sym-btn");
                if (!btn) return;
                insertSymbol(btn.dataset.latex || "");
            });
        }

        document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => {
            setActiveTab(tab.dataset.tab);
        }));
        document.querySelectorAll(".screen-btn").forEach(btn => {
            btn.addEventListener("click", () => setActiveScreen(btn.dataset.screen));
        });
        const toggleSolverSidebarBtn = document.getElementById("toggleSolverSidebarBtn");
        if (toggleSolverSidebarBtn) {
            toggleSolverSidebarBtn.addEventListener("click", () => {
                solverSidebarCollapsed = !solverSidebarCollapsed;
                const shell = document.getElementById("solverAppContainer");
                if (shell) shell.classList.toggle("solver-collapsed", solverSidebarCollapsed);
                toggleSolverSidebarBtn.textContent = solverSidebarCollapsed ? "Show Sidebar" : "Hide Sidebar";
            });
        }
        const learningSearch = document.getElementById("learningSearch");
        if (learningSearch) {
            learningSearch.addEventListener("input", () => renderLearningItems());
        }
        const learningModeTabs = document.getElementById("learningModeTabs");
        if (learningModeTabs) {
            learningModeTabs.addEventListener("click", e => {
                const btn = e.target.closest(".learning-mode-btn");
                if (!btn) return;
                setLearningMode(btn.dataset.learningMode || "home");
            });
        }
        const learningHome = document.getElementById("learningHomeMode");
        if (learningHome) {
            learningHome.addEventListener("click", e => {
                const card = e.target.closest("[data-home-mode]");
                if (!card) return;
                setLearningMode(card.dataset.homeMode || "library");
            });
        }
        const learningViews = document.getElementById("learningViewTabs");
        if (learningViews) {
            learningViews.addEventListener("click", e => {
                const btn = e.target.closest(".learning-view-btn");
                if (!btn) return;
                learningActiveView = btn.dataset.learningView || "concepts";
                renderLearningItems();
            });
        }
        const learningCats = document.getElementById("learningCategoryChips");
        if (learningCats) {
            learningCats.addEventListener("click", e => {
                const btn = e.target.closest(".learning-chip");
                if (!btn) return;
                learningActiveCategory = btn.dataset.learningCategory || "all";
                renderLearningItems();
            });
        }
        const learningList = document.getElementById("learningItemList");
        if (learningList) {
            learningList.addEventListener("click", e => {
                const btn = e.target.closest(".learning-topic-btn");
                if (!btn) return;
                const kind = btn.dataset.learningItemType;
                const id = btn.dataset.learningItemId || "";
                if (kind === "concept") learningSelectedTopicId = id;
                if (kind === "formula") learningSelectedFormulaId = id;
                if (kind === "symbol") learningSelectedSymbolId = id;
                renderLearningItems();
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
                learningSelectedTopicId = btn.dataset.relatedTopic || "";
                learningActiveView = "concepts";
                renderLearningItems();
            });
        }
        const glossaryDetail = document.getElementById("glossaryDetail");
        if (glossaryDetail) {
            glossaryDetail.addEventListener("click", e => {
                const btn = e.target.closest(".learning-related-btn");
                if (!btn) return;
                learningSelectedTopicId = btn.dataset.relatedTopic || "";
                learningActiveView = "concepts";
                setLearningMode("library");
            });
        }
        const pathwaySearch = document.getElementById("pathwaySearch");
        if (pathwaySearch) {
            pathwaySearch.addEventListener("input", () => {
                if (showPathwayPicker) renderPathwayList();
                renderChapterList();
                renderCurrentSlide();
            });
        }
        const pathwayList = document.getElementById("pathwayList");
        if (pathwayList) {
            pathwayList.addEventListener("click", e => {
                const btn = e.target.closest("[data-pathway-id]");
                if (!btn) return;
                selectedPathwayId = btn.dataset.pathwayId || "";
                selectedChapterId = "";
                selectedSlideIndex = 0;
                showPathwayPicker = false;
                renderPathwayList();
                renderChapterList();
                renderCurrentSlide();
            });
        }
        const pathwayPickerToggleBtn = document.getElementById("pathwayPickerToggleBtn");
        if (pathwayPickerToggleBtn) {
            pathwayPickerToggleBtn.addEventListener("click", () => {
                showPathwayPicker = !showPathwayPicker;
                renderPathwayList();
            });
        }
        const chapterList = document.getElementById("chapterList");
        if (chapterList) {
            chapterList.addEventListener("click", e => {
                const btn = e.target.closest("[data-chapter-id]");
                if (!btn) return;
                selectedChapterId = btn.dataset.chapterId || "";
                selectedSlideIndex = 0;
                renderChapterList();
                renderCurrentSlide();
            });
        }
        const toggleSidebarBtn = document.getElementById("togglePathwaySidebarBtn");
        if (toggleSidebarBtn) {
            toggleSidebarBtn.addEventListener("click", () => {
                pathwaySidebarCollapsed = !pathwaySidebarCollapsed;
                const shell = document.querySelector("#learningPathwaysMode .learning-shell");
                if (shell) shell.classList.toggle("collapsed", pathwaySidebarCollapsed);
                toggleSidebarBtn.textContent = pathwaySidebarCollapsed ? "Show Sidebar" : "Hide Sidebar";
            });
        }
        const slideStage = document.getElementById("slideStage");
        if (slideStage) {
            slideStage.addEventListener("click", e => {
                const btn = e.target.closest("[data-stage-action]");
                if (!btn) return;
                const action = btn.dataset.stageAction;
                if (action === "toggle-text") {
                    showSlideTextDetails = !showSlideTextDetails;
                    const wrap = document.getElementById("learningSlideTextWrap");
                    if (wrap) wrap.classList.toggle("show", showSlideTextDetails);
                    const toggle = document.getElementById("toggleSlideTextBtn");
                    if (toggle) toggle.textContent = showSlideTextDetails ? "Hide Slide Text" : "Show Slide Text";
                    return;
                }
                if (action === "prev") {
                    selectedSlideIndex = Math.max(0, selectedSlideIndex - 1);
                    renderCurrentSlide();
                    return;
                }
                if (action === "next") {
                    const chapter = getSelectedChapter();
                    if (!chapter) return;
                    const progress = getChapterProgress(selectedPathwayId, chapter.id);
                    const midpoint = Math.floor((chapter.slides || []).length / 2);
                    if (chapter.midpoint_quiz && !progress.midpointTaken && selectedSlideIndex >= midpoint + 1) return;
                    selectedSlideIndex = Math.min((chapter.slides || []).length, selectedSlideIndex + 1);
                    renderCurrentSlide();
                    return;
                }
                if (action === "toggle-notes") {
                    setSlideNotesOpen(!slideNotesOpen);
                }
            });
        }
        const slideNotesToggleBtn = document.getElementById("slideNotesToggleBtn");
        if (slideNotesToggleBtn) {
            slideNotesToggleBtn.addEventListener("click", () => setSlideNotesOpen(!slideNotesOpen));
        }
        const slideNotesTab = document.getElementById("slideNotesTab");
        if (slideNotesTab) {
            slideNotesTab.addEventListener("click", () => setSlideNotesOpen(!slideNotesOpen));
        }
        const notesResizer = document.getElementById("slideNotesResizer");
        if (notesResizer) {
            let drag = false;
            notesResizer.addEventListener("mousedown", () => { drag = true; });
            window.addEventListener("mouseup", () => { drag = false; });
            window.addEventListener("mousemove", e => {
                if (!drag || !slideNotesOpen) return;
                const layout = document.getElementById("learningStageLayout");
                const panel = document.getElementById("slideNotesPanel");
                if (!layout || !panel) return;
                const rect = layout.getBoundingClientRect();
                const desired = rect.right - e.clientX;
                slideNotesWidth = Math.max(300, Math.min(700, Math.round(desired)));
                panel.style.width = `${slideNotesWidth}px`;
            });
        }
        const quizGate = document.getElementById("quizGate");
        if (quizGate) {
            quizGate.addEventListener("click", e => {
                const btn = e.target.closest('[data-action="submit-mid-quiz"]');
                const microBtn = e.target.closest('[data-action="take-micro-quiz"]');
                const chapter = getSelectedChapter();
                if (!chapter) return;
                const progress = getChapterProgress(selectedPathwayId, chapter.id);
                if (microBtn) {
                    const k = microBtn.dataset.microKey || String(selectedSlideIndex);
                    progress.microTaken[k] = true;
                    renderCurrentSlide();
                    return;
                }
                if (!btn) return;
                progress.midpointTaken = true;
                renderCurrentSlide();
            });
            quizGate.addEventListener("change", e => {
                const picked = e.target.closest('input[data-mid-quiz-choice]');
                if (!picked) return;
                const chapter = getSelectedChapter();
                if (!chapter) return;
                const progress = getChapterProgress(selectedPathwayId, chapter.id);
                progress.midpointTaken = true;
                renderCurrentSlide();
            });
        }
        const chapterTestPanel = document.getElementById("chapterTestPanel");
        if (chapterTestPanel) {
            chapterTestPanel.addEventListener("click", e => {
                const btn = e.target.closest('[data-action="take-final-test"]');
                if (!btn) return;
                const chapter = getSelectedChapter();
                if (!chapter) return;
                getChapterProgress(selectedPathwayId, chapter.id).testTaken = true;
                renderCurrentSlide();
            });
            chapterTestPanel.addEventListener("change", e => {
                const picked = e.target.closest('input[data-final-quiz-choice]');
                if (!picked) return;
                const chapter = getSelectedChapter();
                if (!chapter) return;
                getChapterProgress(selectedPathwayId, chapter.id).testTaken = true;
                renderCurrentSlide();
            });
        }
        const glossarySearch = document.getElementById("glossarySearch");
        if (glossarySearch) {
            glossarySearch.addEventListener("input", () => renderGlossaryList());
        }
        const glossaryList = document.getElementById("glossaryList");
        if (glossaryList) {
            glossaryList.addEventListener("click", e => {
                const btn = e.target.closest("[data-glossary-id]");
                if (!btn) return;
                openGlossaryTerm(btn.dataset.glossaryId || "");
            });
        }
        const capacityAnalyzeBtn = document.getElementById("capacityAnalyzeBtn");
        if (capacityAnalyzeBtn) {
            capacityAnalyzeBtn.addEventListener("click", () => runCapacityAnalysis(0));
        }
        const capacityLoadSyntheticBtn = document.getElementById("capacityLoadSyntheticBtn");
        if (capacityLoadSyntheticBtn) {
            capacityLoadSyntheticBtn.addEventListener("click", () => {
                const input = document.getElementById("capacityInput");
                if (!input) return;
                input.value = buildSyntheticCapacityText();
                capacityState.text = input.value;
                capacityState.pageIndex = 0;
                runCapacityAnalysis(0);
            });
        }
        const capacityLoadDenseBtn = document.getElementById("capacityLoadDenseBtn");
        if (capacityLoadDenseBtn) {
            capacityLoadDenseBtn.addEventListener("click", () => {
                const input = document.getElementById("capacityInput");
                if (!input) return;
                input.value = buildDenseSyntheticCapacityText();
                capacityState.text = input.value;
                capacityState.pageIndex = 0;
                runCapacityAnalysis(0);
            });
        }
        const capacityPrevBtn = document.getElementById("capacityPrevBtn");
        if (capacityPrevBtn) {
            capacityPrevBtn.addEventListener("click", () => runCapacityAnalysis(Math.max(0, capacityState.pageIndex - 1)));
        }
        const capacityNextBtn = document.getElementById("capacityNextBtn");
        if (capacityNextBtn) {
            capacityNextBtn.addEventListener("click", () => runCapacityAnalysis(capacityState.pageIndex + 1));
        }
        const capacityCopyPageBtn = document.getElementById("capacityCopyPageBtn");
        if (capacityCopyPageBtn) {
            capacityCopyPageBtn.addEventListener("click", () => copyText(capacityState.pageText || ""));
        }
        const capacityCopyAllBtn = document.getElementById("capacityCopyAllBtn");
        if (capacityCopyAllBtn) {
            capacityCopyAllBtn.addEventListener("click", () => copyText((capacityState.allPagesText || []).join("\n\n")));
        }
        const capacityCopyReportBtn = document.getElementById("capacityCopyReportBtn");
        if (capacityCopyReportBtn) {
            capacityCopyReportBtn.addEventListener("click", () => {
                const report = document.getElementById("capacityReportOutput");
                copyText((report && report.value) ? report.value : "");
            });
        }
        document.addEventListener("click", e => {
            const link = e.target.closest(".glossary-link");
            if (!link) return;
            const termId = link.dataset.glossaryId || "";
            if (termId) openGlossaryTerm(termId);
        });
        const relatedPanel = document.getElementById("relatedLearningPanel");
        if (relatedPanel) {
            relatedPanel.addEventListener("click", e => {
                const btn = e.target.closest(".related-learning-link");
                if (!btn) return;
                openLearningTopic(btn.dataset.topicId || "");
            });
        }
        const animRelatedMenu = document.getElementById("animRelatedMenu");
        if (animRelatedMenu) {
            animRelatedMenu.addEventListener("click", e => {
                const btn = e.target.closest(".related-learning-link");
                if (!btn) return;
                openLearningTopic(btn.dataset.topicId || "");
            });
        }

        document.getElementById("animateAllBtn").addEventListener("click", playAnim);
        document.getElementById("pauseBtn").addEventListener("click", pauseAnim);
        document.getElementById("prevStepBtn").addEventListener("click", () => {
            pauseAnim();
            stepBack();
        });
        document.getElementById("nextStepBtn").addEventListener("click", () => {
            pauseAnim();
            stepForward();
        });
        document.getElementById("speedSlider").addEventListener("input", e => {
            document.getElementById("speedLabel").textContent = e.target.value + "×";
        });

        document.getElementById("zoomIn").addEventListener("click", () => { zoom *= 1.4; refreshGraph(); });
        document.getElementById("zoomOut").addEventListener("click", () => { zoom = Math.max(0.1, zoom / 1.4); refreshGraph(); });
        document.getElementById("resetView").addEventListener("click", () => { zoom = 1; refreshGraph(); });

        // Start with notes collapsed; user can expand via tab/button.
        setSlideNotesOpen(false);
    }

    function setSlideNotesOpen(open) {
        slideNotesOpen = !!open;
        const layout = document.getElementById("learningStageLayout");
        const panel = document.getElementById("slideNotesPanel");
        const btn = document.getElementById("slideNotesToggleBtn");
        if (layout) layout.classList.toggle("notes-collapsed", !slideNotesOpen);
        if (panel) panel.style.width = slideNotesOpen ? `${slideNotesWidth}px` : "0px";
        if (btn) btn.textContent = slideNotesOpen ? "Hide" : "Show";
        renderCurrentSlide();
    }

    async function runSelectedDemo() {
        const id = document.getElementById("demoSelect").value;
        if (!id || !demoMap[id]) return;
        const demo = demoMap[id];
        if (demo.latex) mathField.value = normalizeDisplayMath(demo.latex);
        document.getElementById("calcTypeSelect").value = demo.tag || "";
        applyParams(demo.params || {});
        updateParams();
        await solve({ focusAnimation: true });
    }

    function setActiveTab(tabName) {
        document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === tabName));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.toggle("active", c.id === (tabName + "Tab")));
    }

    function setActiveScreen(screenName) {
        document.querySelectorAll(".screen-btn").forEach(btn => btn.classList.toggle("active", btn.dataset.screen === screenName));
        document.getElementById("solverScreen").classList.toggle("active", screenName === "solver");
        document.getElementById("learningScreen").classList.toggle("active", screenName === "learning");
        if (screenName !== "solver") pauseAnim();
        if (screenName === "learning") setLearningMode(learningMode || "home");
    }

    function openLearningTopic(topicId) {
        if (!topicId || !learningTopicById[topicId]) return;
        learningActiveView = "concepts";
        learningSelectedTopicId = topicId;
        setActiveScreen("learning");
        setLearningMode("library");
        renderLearningItems();
    }

    function getAnimMode() {
        return document.getElementById("animModeSelect")?.value || "default";
    }

    function updateParams() {
        const t = document.getElementById("calcTypeSelect").value;
        document.getElementById("boundsParam").classList.toggle("hidden", t !== "definite_integral");
        document.getElementById("limitParam").classList.toggle("hidden", t !== "limit");
        document.getElementById("orderParam").classList.toggle("hidden", t !== "taylor" && t !== "series");
    }

    function applyParams(p) {
        if (p.variable) document.getElementById("varInput").value = p.variable;
        if (p.lower !== undefined) document.getElementById("lowerBound").value = p.lower;
        if (p.upper !== undefined) document.getElementById("upperBound").value = p.upper;
        if (p.point !== undefined) document.getElementById("limitPoint").value = p.point;
        if (p.direction) document.getElementById("limitDir").value = p.direction;
        if (p.order !== undefined) document.getElementById("seriesOrder").value = p.order;
    }

    async function solve(options = {}) {
        const focusAnimation = !!options.focusAnimation;
        const displayExpr = mathField.value;
        const latex = buildSolverExpression(displayExpr);
        if (!latex.trim()) return;
        pauseAnim();

        const calcType = document.getElementById("calcTypeSelect").value || null;
        const params = {
            variable: document.getElementById("varInput").value || "x",
            lower: document.getElementById("lowerBound").value,
            upper: document.getElementById("upperBound").value,
            point: document.getElementById("limitPoint").value,
            direction: document.getElementById("limitDir").value,
            order: parseInt(document.getElementById("seriesOrder").value, 10) || 6,
        };

        showLoading();
        try {
            const raw = await pywebview.api.solve(latex, calcType, JSON.stringify(params));
            const data = JSON.parse(raw);
            solveResult = data;
            if (data.success) {
                showResult(data);
                renderRelatedLearningLinks(data);
                currentSteps = data.animation_steps || [];
                showSteps(currentSteps);
                renderAnimationStepList(currentSteps);
                baseLatex = currentSteps[0]?.before || mathField.value || "";
                stepIdx = -1;
                clearAnimStage();
                renderStationaryStage(baseLatex, "");

                if (focusAnimation) setActiveTab("animation");
                updateIndicator();
                await refreshGraph();
            } else {
                showError(data.error || "Unknown error");
            }
        } catch (e) {
            showError("Solve failed: " + e.message);
        }
    }

    function showLoading() {
        document.getElementById("resultDisplay").innerHTML = '<p class="placeholder">Computing…</p>';
        document.getElementById("resultDisplay").dataset.copyText = "";
        document.getElementById("resultDisplay").classList.remove("copyable");
        clearRelatedLearning();
        document.getElementById("stepsContainer").innerHTML = "";
        document.getElementById("animStepsPanel").innerHTML = "";
    }

    function showResult(data) {
        const el = document.getElementById("resultDisplay");
        el.innerHTML = "";
        const plain = normalizeDisplayMath(data.result_latex || "");
        el.dataset.copyText = plain;
        el.classList.add("copyable");
        try { katex.render(data.result_latex, el, { throwOnError: false, displayMode: true }); }
        catch (_) { el.textContent = data.result_latex; }
    }

    function showError(msg) {
        document.getElementById("resultDisplay").innerHTML = `<span style="color:var(--accent)">Error: ${msg}</span>`;
        document.getElementById("resultDisplay").dataset.copyText = "";
        document.getElementById("resultDisplay").classList.remove("copyable");
        clearRelatedLearning();
    }

    function renderRelatedLearningLinks(result) {
        const panel = document.getElementById("relatedLearningPanel");
        const picks = getTopRelatedTopics(result, 3);
        relatedTopicPicks = picks;
        renderAnimRelatedLearningLinks(picks);
        if (!panel) return;
        if (!picks.length) {
            clearRelatedLearning();
            return;
        }
        panel.classList.remove("hidden");
        panel.innerHTML = `
            <div class="related-learning-title">Learn Why This Works</div>
            <div class="related-learning-links">
                ${picks.map(p => `<button class="related-learning-link" data-topic-id="${escAttr(p.id)}">${prettyText(p.title)}</button>`).join("")}
            </div>
        `;
    }

    function clearRelatedLearning() {
        const panel = document.getElementById("relatedLearningPanel");
        if (panel) {
            panel.classList.add("hidden");
            panel.innerHTML = "";
        }
        relatedTopicPicks = [];
        renderAnimRelatedLearningLinks([]);
    }

    function renderAnimRelatedLearningLinks(picks) {
        const menu = document.getElementById("animRelatedMenu");
        const btn = document.getElementById("animLearnToggleBtn");
        if (btn) btn.disabled = !picks.length;
        if (!menu) return;
        if (!picks.length) {
            menu.classList.add("hidden");
            menu.innerHTML = "";
            return;
        }
        menu.innerHTML = picks.map(p => `<button class="related-learning-link" data-topic-id="${escAttr(p.id)}">${prettyText(p.title)}</button>`).join("");
        menu.classList.add("hidden");
    }

    function getTopRelatedTopics(result, limit) {
        const topics = learningLibrary.topics || [];
        if (!topics.length || !result) return [];
        const haystack = buildSolveHaystack(result);
        const keywords = extractKeywords(haystack);
        const detected = String(result.detected_type || "").toUpperCase();
        const typeBoosts = {
            DERIVATIVE: ["derivative", "power", "chain", "product", "quotient"],
            INTEGRAL: ["integral", "area", "antiderivative"],
            DEFINITE_INTEGRAL: ["integral", "definite", "area", "bounds"],
            LIMIT: ["limit", "approach", "infinity"],
            TAYLOR: ["series", "taylor", "approximation"],
        };
        const activeBoost = typeBoosts[detected] || [];

        const scored = topics.map(t => {
            const text = [
                t.title || "",
                t.summary || "",
                t.narrative || "",
                ...(t.formulas || []),
                ...(t.symbols || []),
            ].join(" ").toLowerCase();
            let score = 0;
            keywords.forEach(k => {
                if (k.length < 3) return;
                if (text.includes(k)) score += 1;
            });
            activeBoost.forEach(k => {
                if (text.includes(k)) score += 2;
            });
            if ((t.formulas || []).some(fid => haystack.includes(String(fid).toLowerCase()))) score += 2;
            return { id: t.id, title: t.title || t.id, score };
        }).filter(x => x.score > 0);

        if (!scored.length) {
            return topics.slice(0, Math.min(limit, topics.length)).map(t => ({ id: t.id, title: t.title || t.id }));
        }
        scored.sort((a, b) => b.score - a.score || a.title.localeCompare(b.title));
        return scored.slice(0, Math.min(limit, scored.length));
    }

    function buildSolveHaystack(result) {
        const parts = [];
        parts.push((mathField?.value || "").toLowerCase());
        parts.push(String(result.result || "").toLowerCase());
        parts.push(String(result.result_latex || "").toLowerCase());
        parts.push(String(result.detected_type || "").toLowerCase());
        const steps = result.steps || [];
        steps.forEach(s => {
            parts.push(String(s.description || "").toLowerCase());
            parts.push(String(s.rule || "").toLowerCase());
            parts.push(String(s.before || "").toLowerCase());
            parts.push(String(s.after || "").toLowerCase());
        });
        return parts.join(" ");
    }

    function extractKeywords(text) {
        const raw = String(text || "").replace(/[^a-z0-9_ ]+/g, " ").split(/\s+/).filter(Boolean);
        const stop = new Set(["the","and","for","with","from","into","this","that","then","step","rule","find","solve","when","over","under","to","of","in","on","a","an","x"]);
        const uniq = [];
        const seen = new Set();
        raw.forEach(tok => {
            if (tok.length < 3 || stop.has(tok) || seen.has(tok)) return;
            seen.add(tok);
            uniq.push(tok);
        });
        return uniq;
    }

    function showSteps(steps) {
        const c = document.getElementById("stepsContainer");
        if (!steps.length) {
            c.innerHTML = '<p style="color:var(--text2)">No intermediate steps.</p>';
            return;
        }
        c.innerHTML = steps.map((s, i) => `<div class="step-card" data-step="${i}">
            <div class="step-header">
                <span class="step-number">${s.step}</span>
                <span class="step-rule">${(s.rule || "").replace(/_/g, " ")}</span>
            </div>
            <div class="step-description">${prettyText(s.description)}</div>
            <div class="step-math">
                <span class="before"></span>
                ${s.before && s.after ? '<span class="arrow">→</span>' : ''}
                <span class="after"></span>
            </div>
        </div>`).join("");

        c.querySelectorAll(".step-card").forEach((card, i) => {
            const s = steps[i];
            try { if (s.before) katex.render(s.before, card.querySelector(".before"), { throwOnError: false }); } catch (_) { card.querySelector(".before").textContent = s.before; }
            try { if (s.after) katex.render(s.after, card.querySelector(".after"), { throwOnError: false }); } catch (_) { card.querySelector(".after").textContent = s.after; }
            card.addEventListener("click", () => {
                pauseAnim();
                setActiveTab("animation");
                showAnimStep(i);
            });
        });
    }

    function renderAnimationStepList(steps) {
        const panel = document.getElementById("animStepsPanel");
        if (!steps.length) {
            panel.innerHTML = '<div class="anim-step-item"><span class="anim-step-text">No animation steps available.</span></div>';
            return;
        }
        panel.innerHTML = steps.map((s, i) => `
            <button class="anim-step-item" data-anim-step="${i}">
                <span class="anim-step-num">Step ${i + 1}</span>
                <span class="anim-step-text">${prettyText(s.description || (s.rule || "Step"))}</span>
                <span class="anim-step-detail">
                    <span class="math before" data-kind="before"></span>
                    ${s.before && s.after ? '<span class="arr">→</span>' : ''}
                    <span class="math after" data-kind="after"></span>
                </span>
            </button>
        `).join("");

        panel.querySelectorAll(".anim-step-item").forEach((btn, i) => {
            const s = steps[i];
            const beforeEl = btn.querySelector('.math.before');
            const afterEl = btn.querySelector('.math.after');
            try { if (beforeEl && s.before) katex.render(s.before, beforeEl, { throwOnError: false, displayMode: false }); } catch (_) { if (beforeEl) beforeEl.textContent = s.before || ""; }
            try { if (afterEl && s.after) katex.render(s.after, afterEl, { throwOnError: false, displayMode: false }); } catch (_) { if (afterEl) afterEl.textContent = s.after || ""; }
            btn.addEventListener("click", () => {
                pauseAnim();
                showAnimStep(i);
            });
        });
    }

    function esc(s) {
        return s ? String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;") : "";
    }
    function prettyText(s) {
        return applyGlossaryLinks(formatPrettyMathHtml(normalizePrettyMathSource(s || "")));
    }
    function normalizePrettyMathSource(text) {
        let s = String(text || "");
        s = s.replace(/\r/g, "");
        s = s.replace(/\\left|\\right/g, "");
        s = s.replace(/\\,/g, " ");
        s = s.replace(/\\cdot/g, "·").replace(/\\times/g, "×");
        s = s.replace(/\\pi/g, "π").replace(/\\infty/g, "∞");
        s = s.replace(/\\to|\\rightarrow|->/g, "→");
        s = s.replace(/\\lim/g, "lim");
        s = s.replace(/\\int/g, "∫");
        s = s.replace(/\\sin/g, "sin").replace(/\\cos/g, "cos").replace(/\\tan/g, "tan");
        s = s.replace(/\\ln/g, "ln").replace(/\\log/g, "log").replace(/\\sqrt/g, "sqrt");
        s = s.replace(/\\frac\{d(?:\^(\d+)|\{([^{}]+)\})?\}\{d([a-zA-Z])(?:\^(\d+)|\{([^{}]+)\})?\}/g, (_m, p1, p1b, v, p2, p2b) => {
            const n = p1 || p1b || p2 || p2b || "";
            return `d${n ? "^(" + n + ")" : ""}/d${v}${n ? "^(" + n + ")" : ""}`;
        });
        // Convert simple latex fraction forms into slash form, then let formatter stack them.
        for (let i = 0; i < 6; i++) {
            const next = s.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "($1)/($2)");
            if (next === s) break;
            s = next;
        }
        s = s.replace(/[{}]/g, m => m === "{" ? "(" : ")");
        s = s.replace(/\\([a-zA-Z]+)/g, "$1");
        s = s.replace(/\bsqrt\b/g, "√");
        s = s.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
        return s;
    }
    function formatPrettyMathHtml(text) {
        let t = esc(text || "");

        // Parenthesized fractions: (a)/(b) -> stacked fraction
        for (let i = 0; i < 6; i++) {
            const next = t.replace(/\(([^()]+)\)\s*\/\s*\(([^()]+)\)/g, (_m, num, den) =>
                `<span class="math-frac"><span class="math-frac-num">${num}</span><span class="math-frac-bar"></span><span class="math-frac-den">${den}</span></span>`
            );
            if (next === t) break;
            t = next;
        }

        // Simple fractions: a/b -> stacked fraction (avoids URLs/long words).
        t = t.replace(/(^|[\s=+\-*(])([a-zA-Z0-9.]+)\s*\/\s*([a-zA-Z0-9.]+)(?=$|[\s=+\-*)])/g,
            (_m, pre, num, den) => `${pre}<span class="math-frac"><span class="math-frac-num">${num}</span><span class="math-frac-bar"></span><span class="math-frac-den">${den}</span></span>`);

        // Exponents: ^{...}, ^(...), and ^token
        t = t.replace(/\^\{([^}]+)\}/g, (_m, exp) => `<sup>${exp}</sup>`);
        t = t.replace(/\^\(([^)]+)\)/g, (_m, exp) => `<sup>${exp}</sup>`);
        t = t.replace(/\^([a-zA-Z0-9+\-]+)/g, (_m, exp) => `<sup>${exp}</sup>`);

        // Subscripts: _{...}, _(...), and _token
        t = t.replace(/_\{([^}]+)\}/g, (_m, sub) => `<sub>${sub}</sub>`);
        t = t.replace(/_\(([^)]+)\)/g, (_m, sub) => `<sub>${sub}</sub>`);
        t = t.replace(/_([a-zA-Z0-9+\-]+)/g, (_m, sub) => `<sub>${sub}</sub>`);

        return t;
    }
    function applyGlossaryLinks(html) {
        if (!html || !glossaryLexicon.length) return html;
        const root = document.createElement("div");
        root.innerHTML = html;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const textNodes = [];
        let node = walker.nextNode();
        while (node) {
            if (node.nodeValue && node.nodeValue.trim()) textNodes.push(node);
            node = walker.nextNode();
        }
        textNodes.forEach(textNode => {
            let text = textNode.nodeValue;
            let replaced = false;
            glossaryLexicon.slice(0, 30).forEach(entry => {
                const escaped = entry.token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
                const re = new RegExp(`\\b${escaped}\\b`, "i");
                if (!re.test(text)) return;
                text = text.replace(re, `<a class="glossary-link" data-glossary-id="${escAttr(entry.id)}">$&</a>`);
                replaced = true;
            });
            if (!replaced) return;
            const span = document.createElement("span");
            span.innerHTML = text;
            textNode.parentNode.replaceChild(span, textNode);
        });
        return root.innerHTML;
    }
    function escAttr(s) {
        return String(s || "")
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function normalizeInputField() {
        const start = mathField.selectionStart || 0;
        const left = (mathField.value || "").slice(0, start);
        const normalizedLeft = normalizeDisplayMath(left);
        const normalizedAll = normalizeDisplayMath(mathField.value || "");
        if (normalizedAll !== mathField.value) {
            mathField.value = normalizedAll;
            const caret = Math.min(normalizedLeft.length, normalizedAll.length);
            mathField.setSelectionRange(caret, caret);
        }
    }

    function normalizeDisplayMath(text) {
        let s = String(text || "");
        s = s.replace(/\r/g, "");
        s = s.replace(/\\left|\\right/g, "");
        s = s.replace(/\\,/g, " ");
        s = s.replace(/\\cdot/g, "·").replace(/\\times/g, "×");
        s = s.replace(/\\pi/g, "π").replace(/\\infty/g, "∞");
        s = s.replace(/\\to|\\rightarrow|->/g, "→");
        s = s.replace(/\\lim/g, "lim");
        s = s.replace(/\\int/g, "∫");
        s = s.replace(/\\sin/g, "sin").replace(/\\cos/g, "cos").replace(/\\tan/g, "tan");
        s = s.replace(/\\ln/g, "ln").replace(/\\log/g, "log").replace(/\\sqrt/g, "sqrt");
        s = s.replace(/\\frac\{d(?:\^(\d+))?\}\{d([a-zA-Z])(?:\^(\d+))?\}/g, (_, p1, v, p2) => {
            const n = p1 || p2 || "";
            return `d${n ? "^" + n : ""}/d${v}${n ? "^" + n : ""}`;
        });
        s = s.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "($1)/($2)");
        s = s.replace(/[{}]/g, m => m === "{" ? "(" : ")");
        s = s.replace(/\\([a-zA-Z]+)/g, "$1");
        s = s.replace(/\bsqrt\b/g, "√");
        s = applyPrettyScripts(s);
        s = s.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
        return s;
    }

    function buildSolverExpression(displayText) {
        let s = String(displayText || "");
        s = revertPrettyScripts(s);
        s = s.replace(/×|·/g, "*");
        s = s.replace(/π/g, "pi");
        s = s.replace(/∞/g, "oo");
        s = s.replace(/→/g, "->");
        s = s.replace(/∫/g, "int");
        s = s.replace(/√/g, "sqrt");
        return s;
    }

    function applyPrettyScripts(s) {
        // grouped exponents/subscripts: ^(n-5) -> ⁽ⁿ⁻⁵⁾
        s = s.replace(/\^\(([^)]+)\)/g, (_, p1) => toSuperscript("(" + p1 + ")"));
        s = s.replace(/_\(([^)]+)\)/g, (_, p1) => toSubscript("(" + p1 + ")"));
        // numeric/signed exponents: x^12 -> x¹², d^5 -> d⁵
        s = s.replace(/\^([+\-]?\d+)/g, (_, p1) => toSuperscript(p1));
        // simple symbolic exponents: x^n -> xⁿ
        s = s.replace(/\^([a-zA-Z]+)/g, (_, p1) => toSuperscript(p1));
        // numeric/signed subscripts: int_0^2 -> int₀²
        s = s.replace(/_([+\-]?\d+)/g, (_, p1) => toSubscript(p1));
        s = s.replace(/_([a-zA-Z]+)/g, (_, p1) => toSubscript(p1));
        return s;
    }

    function revertPrettyScripts(s) {
        // collapse runs of superscripts/subscripts back to ^... / _...
        s = s.replace(/([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁽⁾⁼ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂ]+)/g, (_, p1) => "^" + fromSuperscript(p1));
        s = s.replace(/([₀₁₂₃₄₅₆₇₈₉₊₋₍₎₌ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ]+)/g, (_, p1) => "_" + fromSubscript(p1));
        return s;
    }

    function toSuperscript(raw) {
        const map = {
            "0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵","6":"⁶","7":"⁷","8":"⁸","9":"⁹",
            "+":"⁺","-":"⁻","(":"⁽",")":"⁾","=":"⁼",
            "a":"ᵃ","b":"ᵇ","c":"ᶜ","d":"ᵈ","e":"ᵉ","f":"ᶠ","g":"ᵍ","h":"ʰ","i":"ⁱ","j":"ʲ","k":"ᵏ","l":"ˡ","m":"ᵐ","n":"ⁿ","o":"ᵒ","p":"ᵖ","r":"ʳ","s":"ˢ","t":"ᵗ","u":"ᵘ","v":"ᵛ","w":"ʷ","x":"ˣ","y":"ʸ","z":"ᶻ",
            "A":"ᴬ","B":"ᴮ","D":"ᴰ","E":"ᴱ","G":"ᴳ","H":"ᴴ","I":"ᴵ","J":"ᴶ","K":"ᴷ","L":"ᴸ","M":"ᴹ","N":"ᴺ","O":"ᴼ","P":"ᴾ","R":"ᴿ","T":"ᵀ","U":"ᵁ","V":"ⱽ","W":"ᵂ"
        };
        return String(raw).split("").map(ch => map[ch] || ch).join("");
    }

    function toSubscript(raw) {
        const map = {
            "0":"₀","1":"₁","2":"₂","3":"₃","4":"₄","5":"₅","6":"₆","7":"₇","8":"₈","9":"₉",
            "+":"₊","-":"₋","(":"₍",")":"₎","=":"₌",
            "a":"ₐ","e":"ₑ","h":"ₕ","i":"ᵢ","j":"ⱼ","k":"ₖ","l":"ₗ","m":"ₘ","n":"ₙ","o":"ₒ","p":"ₚ","r":"ᵣ","s":"ₛ","t":"ₜ","u":"ᵤ","v":"ᵥ","x":"ₓ"
        };
        return String(raw).split("").map(ch => map[ch] || ch).join("");
    }

    function fromSuperscript(raw) {
        const map = {
            "⁰":"0","¹":"1","²":"2","³":"3","⁴":"4","⁵":"5","⁶":"6","⁷":"7","⁸":"8","⁹":"9",
            "⁺":"+","⁻":"-","⁽":"(","⁾":")","⁼":"=",
            "ᵃ":"a","ᵇ":"b","ᶜ":"c","ᵈ":"d","ᵉ":"e","ᶠ":"f","ᵍ":"g","ʰ":"h","ⁱ":"i","ʲ":"j","ᵏ":"k","ˡ":"l","ᵐ":"m","ⁿ":"n","ᵒ":"o","ᵖ":"p","ʳ":"r","ˢ":"s","ᵗ":"t","ᵘ":"u","ᵛ":"v","ʷ":"w","ˣ":"x","ʸ":"y","ᶻ":"z",
            "ᴬ":"A","ᴮ":"B","ᴰ":"D","ᴱ":"E","ᴳ":"G","ᴴ":"H","ᴵ":"I","ᴶ":"J","ᴷ":"K","ᴸ":"L","ᴹ":"M","ᴺ":"N","ᴼ":"O","ᴾ":"P","ᴿ":"R","ᵀ":"T","ᵁ":"U","ⱽ":"V","ᵂ":"W"
        };
        return String(raw).split("").map(ch => map[ch] || ch).join("");
    }

    function fromSubscript(raw) {
        const map = {
            "₀":"0","₁":"1","₂":"2","₃":"3","₄":"4","₅":"5","₆":"6","₇":"7","₈":"8","₉":"9",
            "₊":"+","₋":"-","₍":"(","₎":")","₌":"=",
            "ₐ":"a","ₑ":"e","ₕ":"h","ᵢ":"i","ⱼ":"j","ₖ":"k","ₗ":"l","ₘ":"m","ₙ":"n","ₒ":"o","ₚ":"p","ᵣ":"r","ₛ":"s","ₜ":"t","ᵤ":"u","ᵥ":"v","ₓ":"x"
        };
        return String(raw).split("").map(ch => map[ch] || ch).join("");
    }

    function clear() {
        pauseAnim();
        stepRenderToken++;
        mathField.value = "";
        document.getElementById("resultDisplay").innerHTML = '<p class="placeholder">Enter an expression and click <strong>Solve &amp; Animate</strong></p>';
        document.getElementById("resultDisplay").dataset.copyText = "";
        document.getElementById("resultDisplay").classList.remove("copyable");
        clearRelatedLearning();
        document.getElementById("stepsContainer").innerHTML = "";
        document.getElementById("animStepsPanel").innerHTML = "";
        currentSteps = [];
        stepIdx = -1;
        baseLatex = "";
        queuedDirection = 0;
        solveResult = null;
        clearCanvases();
        clearAnimStage();
        updateIndicator();
    }

    function setupCanvases() {
        gCanvas = document.getElementById("graphCanvas");
        gCtx = gCanvas.getContext("2d");
        aCanvas = document.getElementById("animCanvas");
        aCtx = aCanvas.getContext("2d");
        const dpr = window.devicePixelRatio || 1;
        for (const [cv, ctx] of [[gCanvas, gCtx], [aCanvas, aCtx]]) {
            const w = cv.width, h = cv.height;
            cv.width = w * dpr;
            cv.height = h * dpr;
            cv.style.width = w + "px";
            cv.style.height = h + "px";
            ctx.scale(dpr, dpr);
        }
        clearCanvases();
    }

    function clearCanvases() {
        fillBg(gCtx, gCanvas);
        fillBg(aCtx, aCanvas);
    }

    function fillBg(ctx, cv) {
        const dpr = window.devicePixelRatio || 1;
        ctx.fillStyle = "#0f0f23";
        ctx.fillRect(0, 0, cv.width / dpr, cv.height / dpr);
    }

    async function refreshGraph() {
        const displayExpr = mathField.value;
        const latex = buildSolverExpression(displayExpr);
        if (!latex.trim()) return;
        try {
            const r = zoom;
            const calcType = document.getElementById("calcTypeSelect").value || null;
            const params = {
                variable: document.getElementById("varInput").value || "x",
                lower: document.getElementById("lowerBound").value,
                upper: document.getElementById("upperBound").value,
                point: document.getElementById("limitPoint").value,
                direction: document.getElementById("limitDir").value,
                order: parseInt(document.getElementById("seriesOrder").value, 10) || 6,
            };
            const raw = await pywebview.api.get_graph_data(latex, calcType, JSON.stringify(params), -10 / r, 10 / r);
            graphData = JSON.parse(raw);
            drawGraph();
        } catch (_) {}
    }

    function drawGraph() {
        const ctx = gCtx, data = graphData;
        const dpr = window.devicePixelRatio || 1;
        const W = gCanvas.width / dpr, H = gCanvas.height / dpr;
        fillBg(ctx, gCanvas);
        const pad = 58;
        const w = W - pad * 2, h = H - pad * 2;

        if (!data || !data.success) {
            ctx.fillStyle = "#aab3c5";
            ctx.font = "14px 'Segoe UI', system-ui, sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("Graph unavailable for this expression.", W / 2, H / 2);
            return;
        }

        const curves = Array.isArray(data.curves) && data.curves.length
            ? data.curves
            : ((Array.isArray(data.x) && Array.isArray(data.y)) ? [{ label: "f(x)", color: "#e94560", style: "solid", width: 2.6, x: data.x, y: data.y }] : []);
        if (!curves.length) {
            ctx.fillStyle = "#aab3c5";
            ctx.font = "14px 'Segoe UI', system-ui, sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("No plottable solution in real numbers.", W / 2, H / 2);
            return;
        }

        const xRange = Array.isArray(data.x_range) && data.x_range.length === 2 ? data.x_range : [-10 / zoom, 10 / zoom];
        let yRange = Array.isArray(data.y_range) && data.y_range.length === 2 ? data.y_range : null;
        if (!yRange) {
            const values = [];
            curves.forEach(c => (c.y || []).forEach(v => { if (v !== null && Number.isFinite(v)) values.push(v); }));
            if (!values.length) yRange = [-10, 10];
            else {
                values.sort((a, b) => a - b);
                const p2 = values[Math.floor(values.length * 0.02)];
                const p98 = values[Math.floor(values.length * 0.98)];
                const span = Math.max(1e-6, p98 - p2);
                yRange = [p2 - span * 0.2, p98 + span * 0.2];
            }
        }
        const xMin = Number(xRange[0]), xMax = Number(xRange[1]);
        const yLo = Number(yRange[0]), yHi = Number(yRange[1]);
        const tx = x => pad + ((x - xMin) / (xMax - xMin || 1)) * w;
        const ty = y => pad + h - ((y - yLo) / (yHi - yLo || 1)) * h;

        // Grid + tick labels
        ctx.strokeStyle = "#1e2740";
        ctx.lineWidth = 1;
        ctx.fillStyle = "#8e98ad";
        ctx.font = "11px 'Segoe UI', system-ui, sans-serif";
        ctx.textAlign = "center";
        for (let i = 0; i <= 8; i++) {
            const t = i / 8;
            const gx = pad + t * w;
            const gy = pad + t * h;
            ctx.beginPath(); ctx.moveTo(gx, pad); ctx.lineTo(gx, pad + h); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(pad, gy); ctx.lineTo(pad + w, gy); ctx.stroke();
            const xv = xMin + t * (xMax - xMin);
            if (i % 2 === 0) ctx.fillText(xv.toFixed(2).replace(/\.00$/, ""), gx, pad + h + 16);
        }
        ctx.textAlign = "right";
        for (let i = 0; i <= 8; i += 2) {
            const t = i / 8;
            const yv = yHi - t * (yHi - yLo);
            ctx.fillText(yv.toFixed(2).replace(/\.00$/, ""), pad - 8, pad + t * h + 4);
        }

        // Axes
        if (yLo <= 0 && yHi >= 0) {
            const y0 = ty(0);
            ctx.strokeStyle = "#4b5c84";
            ctx.lineWidth = 1.6;
            ctx.beginPath(); ctx.moveTo(pad, y0); ctx.lineTo(pad + w, y0); ctx.stroke();
        }
        if (xMin <= 0 && xMax >= 0) {
            const x0 = tx(0);
            ctx.strokeStyle = "#4b5c84";
            ctx.lineWidth = 1.6;
            ctx.beginPath(); ctx.moveTo(x0, pad); ctx.lineTo(x0, pad + h); ctx.stroke();
        }

        // Fills
        (data.fills || []).forEach(fill => {
            const fx = fill.x || [];
            const fy = fill.y || [];
            if (!fx.length || !fy.length) return;
            const base = Number.isFinite(fill.baseline) ? fill.baseline : 0;
            ctx.beginPath();
            let started = false;
            for (let i = 0; i < fx.length; i++) {
                const yv = fy[i];
                if (yv === null || !Number.isFinite(yv)) continue;
                const cx = tx(fx[i]);
                const cy = ty(Math.max(yLo, Math.min(yHi, yv)));
                if (!started) {
                    ctx.moveTo(cx, ty(base));
                    ctx.lineTo(cx, cy);
                    started = true;
                } else {
                    ctx.lineTo(cx, cy);
                }
            }
            for (let i = fx.length - 1; i >= 0; i--) {
                if (fy[i] === null || !Number.isFinite(fy[i])) continue;
                ctx.lineTo(tx(fx[i]), ty(base));
            }
            ctx.closePath();
            ctx.fillStyle = fill.color || "rgba(233,69,96,0.22)";
            ctx.fill();
        });

        // Curves
        curves.forEach(curve => {
            const xs = curve.x || [];
            const ys = curve.y || [];
            ctx.strokeStyle = curve.color || "#e94560";
            ctx.lineWidth = curve.width || 2.4;
            if (curve.style === "dashed") ctx.setLineDash([6, 5]); else ctx.setLineDash([]);
            ctx.beginPath();
            let started = false;
            for (let i = 0; i < xs.length; i++) {
                const yv = ys[i];
                if (yv === null || !Number.isFinite(yv)) { started = false; continue; }
                const cx = tx(xs[i]), cy = ty(Math.max(yLo, Math.min(yHi, yv)));
                if (cy < pad - 5 || cy > pad + h + 5) { started = false; continue; }
                if (!started) { ctx.moveTo(cx, cy); started = true; }
                else ctx.lineTo(cx, cy);
            }
            ctx.stroke();
            ctx.setLineDash([]);
        });

        // Vertical and horizontal guide lines
        (data.vlines || []).forEach(v => {
            const x = Number(v.x);
            if (!Number.isFinite(x)) return;
            const px = tx(x);
            ctx.setLineDash([5, 5]);
            ctx.strokeStyle = v.color || "#fbbf24";
            ctx.lineWidth = 1.4;
            ctx.beginPath(); ctx.moveTo(px, pad); ctx.lineTo(px, pad + h); ctx.stroke();
            ctx.setLineDash([]);
            if (v.label) {
                ctx.fillStyle = v.color || "#fbbf24";
                ctx.font = "11px 'Segoe UI', system-ui, sans-serif";
                ctx.textAlign = "center";
                ctx.fillText(v.label, px, pad - 8);
            }
        });
        (data.hlines || []).forEach(v => {
            const y = Number(v.y);
            if (!Number.isFinite(y)) return;
            const py = ty(y);
            ctx.setLineDash([5, 5]);
            ctx.strokeStyle = v.color || "#22c55e";
            ctx.lineWidth = 1.4;
            ctx.beginPath(); ctx.moveTo(pad, py); ctx.lineTo(pad + w, py); ctx.stroke();
            ctx.setLineDash([]);
            if (v.label) {
                ctx.fillStyle = v.color || "#22c55e";
                ctx.font = "11px 'Segoe UI', system-ui, sans-serif";
                ctx.textAlign = "left";
                ctx.fillText(v.label, pad + 6, py - 6);
            }
        });

        // Points
        (data.points || []).forEach(p => {
            const x = Number(p.x), y = Number(p.y);
            if (!Number.isFinite(x) || !Number.isFinite(y)) return;
            const cx = tx(x), cy = ty(y);
            ctx.fillStyle = p.color || "#22c55e";
            ctx.beginPath(); ctx.arc(cx, cy, 4, 0, Math.PI * 2); ctx.fill();
            if (p.label) {
                ctx.font = "11px 'Segoe UI', system-ui, sans-serif";
                ctx.textAlign = "left";
                ctx.fillText(p.label, cx + 6, cy - 6);
            }
        });

        // Title
        ctx.fillStyle = "#d6deee";
        ctx.font = "600 13px 'Segoe UI', system-ui, sans-serif";
        ctx.textAlign = "left";
        const typeLabel = String(data.calc_type || "").replace(/_/g, " ").trim();
        if (typeLabel) ctx.fillText(typeLabel, pad, 24);

        // Legend
        const legendItems = curves.map(c => ({ label: c.label || "Curve", color: c.color || "#e94560", style: c.style || "solid" }))
            .concat((data.fills || []).map(f => ({ label: f.label || "Area", color: f.color || "rgba(233,69,96,0.22)", style: "fill" })));
        if (legendItems.length) {
            const boxW = Math.min(250, W * 0.34);
            const boxH = 14 + legendItems.length * 18;
            const lx = W - pad - boxW;
            const ly = pad + 8;
            ctx.fillStyle = "rgba(10,15,30,0.78)";
            ctx.strokeStyle = "rgba(110,125,160,0.35)";
            ctx.lineWidth = 1;
            if (typeof ctx.roundRect === "function") {
                ctx.beginPath();
                ctx.roundRect(lx, ly, boxW, boxH, 8);
                ctx.fill();
                ctx.stroke();
            } else {
                ctx.fillRect(lx, ly, boxW, boxH);
                ctx.strokeRect(lx, ly, boxW, boxH);
            }
            legendItems.forEach((it, i) => {
                const y = ly + 16 + i * 18;
                if (it.style === "fill") {
                    ctx.fillStyle = it.color;
                    ctx.fillRect(lx + 10, y - 7, 16, 10);
                } else {
                    ctx.strokeStyle = it.color;
                    if (it.style === "dashed") ctx.setLineDash([5, 4]); else ctx.setLineDash([]);
                    ctx.lineWidth = 2.2;
                    ctx.beginPath(); ctx.moveTo(lx + 10, y - 1); ctx.lineTo(lx + 26, y - 1); ctx.stroke();
                    ctx.setLineDash([]);
                }
                ctx.fillStyle = "#d5dceb";
                ctx.font = "11px 'Segoe UI', system-ui, sans-serif";
                ctx.textAlign = "left";
                ctx.fillText(it.label, lx + 32, y + 2);
            });
        }
    }

    function playAnim() {
        if (animPlaying || !currentSteps.length || transitionBusy) return;
        animPlaying = true;
        if (stepIdx >= currentSteps.length - 1) {
            stepIdx = -1;
            renderStationaryStage(baseLatex, "");
            updateIndicator();
        }
        runAnimLoop();
    }

    function runAnimLoop() {
        if (!animPlaying) return;
        if (transitionBusy) {
            animTimer = setTimeout(runAnimLoop, 100);
            return;
        }
        if (stepIdx >= currentSteps.length - 1) {
            animPlaying = false;
            return;
        }
        const advanced = stepForward();
        if (!advanced) {
            animPlaying = false;
            return;
        }
        const speed = parseFloat(document.getElementById("speedSlider").value) || 1;
        const dur = AUTO_STEP_MS / speed;
        animTimer = setTimeout(() => {
            runAnimLoop();
        }, dur);
    }

    function pauseAnim() {
        animPlaying = false;
        clearTimeout(animTimer);
    }

    function showAnimStep(idx) {
        if (!currentSteps.length) return;
        idx = Math.max(0, Math.min(currentSteps.length - 1, idx));
        if (transitionBusy) return;
        const step = currentSteps[idx];
        const renderToken = ++stepRenderToken;
        const fromLatex = stepIdx >= 0 ? (currentSteps[stepIdx].after || currentSteps[stepIdx].before || "") : baseLatex;
        const toLatex = step.after || step.before || "";
        currentAnimCopyText = normalizeDisplayMath(toLatex || fromLatex || "");
        transitionBusy = true;
        stepIdx = idx;
        updateIndicator();

        document.querySelectorAll(".step-card").forEach((c, i) => c.classList.toggle("highlight", i === idx));
        document.querySelectorAll(".anim-step-item").forEach((c, i) => c.classList.toggle("active", i === idx));

        const display = document.getElementById("animMathDisplay");
        const badge = document.getElementById("animRuleBadge");
        const desc = document.getElementById("animDescription");

        clearTimeout(badgeTimer);
        clearTimeout(descTimer);
        badge.className = "anim-rule-badge";
        desc.className = "anim-description";
        badge.textContent = "";
        desc.textContent = "";

        const onDone = () => {
            transitionBusy = false;
            if (queuedDirection !== 0) {
                const dir = queuedDirection;
                queuedDirection = 0;
                if (dir > 0) stepForward();
                else stepBack();
            }
        };
        if (step.rule === "final_result") {
            renderFinalSolution(display, toLatex, renderToken, onDone);
            badge.textContent = "SOLUTION";
            badge.classList.add("solution");
        } else {
            animateMathTransition(display, fromLatex, toLatex, renderToken, onDone);
            badge.textContent = (step.rule || "").replace(/_/g, " ");
            badge.classList.add("rule");
        }
        desc.innerHTML = prettyText(step.description || "");
        badgeTimer = setTimeout(() => {
            if (renderToken !== stepRenderToken) return;
            badge.classList.add("visible");
        }, 180);
        descTimer = setTimeout(() => {
            if (renderToken !== stepRenderToken) return;
            desc.classList.add("visible");
        }, 320);

        drawAnimCanvas(step);
    }

    function animateMathTransition(display, beforeLatex, afterLatex, renderToken, onDone) {
        display.classList.remove("fade-in");
        display.classList.add("fade-out");
        setTimeout(() => {
            if (renderToken !== stepRenderToken) return;
            display.innerHTML = "";

            const frame = document.createElement("div");
            frame.className = "anim-transition-frame";
            const compare = document.createElement("div");
            compare.className = "anim-compare";

            const prev = document.createElement("div");
            prev.className = "anim-eq prev";
            renderMath(prev, beforeLatex || afterLatex || "");

            const arrow = document.createElement("div");
            arrow.className = "anim-arrow";
            arrow.textContent = "→";

            const next = document.createElement("div");
            next.className = "anim-eq next";
            renderMath(next, afterLatex || beforeLatex || "");

            compare.appendChild(prev);
            compare.appendChild(arrow);
            compare.appendChild(next);
            frame.appendChild(compare);
            display.appendChild(frame);
            compare.style.opacity = "0";
            compare.style.transform = "translateY(8px)";
            compare.style.transition = "opacity 420ms ease, transform 420ms ease";
            renderMotionLayer(frame, beforeLatex, afterLatex, renderToken, GLYPH_ONLY_MS);
            requestAnimationFrame(() => {
                if (renderToken !== stepRenderToken) return;
                setTimeout(() => {
                    if (renderToken !== stepRenderToken) return;
                    compare.style.opacity = "1";
                    compare.style.transform = "translateY(0)";
                    next.classList.add("enter");
                    arrow.classList.add("enter");
                }, GLYPH_ONLY_MS);
            });

            display.classList.remove("fade-out");
            display.classList.add("fade-in");
            setTimeout(() => {
                if (renderToken !== stepRenderToken) return;
                if (typeof onDone === "function") onDone();
            }, TRANSITION_MS);
        }, 220);
    }

    function renderFinalSolution(display, finalLatex, renderToken, onDone) {
        display.classList.remove("fade-in");
        display.classList.add("fade-out");
        setTimeout(() => {
            if (renderToken !== stepRenderToken) return;
            display.innerHTML = "";
            const wrap = document.createElement("div");
            wrap.className = "anim-final-solution";
            const title = document.createElement("div");
            title.className = "anim-final-title";
            title.textContent = "Solution";
            const eq = document.createElement("div");
            eq.className = "anim-eq settled";
            renderMath(eq, finalLatex || "");
            currentAnimCopyText = normalizeDisplayMath(finalLatex || "");
            wrap.appendChild(title);
            wrap.appendChild(eq);
            display.appendChild(wrap);
            display.classList.remove("fade-out");
            display.classList.add("fade-in");
            setTimeout(() => {
                if (renderToken !== stepRenderToken) return;
                if (typeof onDone === "function") onDone();
            }, 650);
        }, 180);
    }

    function renderMotionLayer(frame, beforeLatex, afterLatex, renderToken, durationMs) {
        const canvas = document.createElement("canvas");
        canvas.className = "anim-motion-canvas";
        frame.appendChild(canvas);
        const dpr = window.devicePixelRatio || 1;
        const w = Math.max(620, frame.clientWidth || 720);
        const h = Math.max(150, frame.clientHeight || 180);
        canvas.width = Math.floor(w * dpr);
        canvas.height = Math.floor(h * dpr);
        canvas.style.width = `${w}px`;
        canvas.style.height = `${h}px`;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.scale(dpr, dpr);

        const leftTokens = tokenizeGlyphTokens(beforeLatex);
        const rightTokens = tokenizeGlyphTokens(afterLatex);
        if (!leftTokens.length && !rightTokens.length) {
            canvas.remove();
            return;
        }
        const seed = hashString(`${beforeLatex}=>${afterLatex}`);
        const rng = mulberry32(seed || 1);
        const glyphs = buildGlyphParticles(leftTokens, rightTokens, rng, w, h, seed);

        const t0 = performance.now();
        const duration = Math.max(300, durationMs || GLYPH_ONLY_MS);
        function paint(now) {
            if (renderToken !== stepRenderToken) {
                canvas.remove();
                return;
            }
            const t = Math.min(1, (now - t0) / duration);
            ctx.clearRect(0, 0, w, h);
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            glyphs.forEach((g, i) => {
                const p = particlePosition(g, t);
                const wobble = Math.sin((t * 10.5) + i * 0.61) * (1 - t) * 6;
                const x = p.x + wobble;
                const y = p.y + Math.cos((t * 8.2) + i * 0.41) * (1 - t) * 3;
                const alpha = t < 0.4 ? t * 1.8 : (1 - t) * 1.4;
                const a = Math.max(0, Math.min(0.82, alpha));
                ctx.font = `700 ${g.size}px 'Segoe UI', system-ui, sans-serif`;
                ctx.strokeStyle = `rgba(12,16,25,${0.55 * a})`;
                ctx.lineWidth = 3;
                ctx.strokeText(g.text, x, y);
                ctx.fillStyle = g.color(a);
                ctx.fillText(g.text, x, y);
            });
            if (t < 1) requestAnimationFrame(paint);
            else canvas.remove();
        }
        requestAnimationFrame(paint);
    }

    function renderStationaryStage(leftLatex, rightLatex) {
        const display = document.getElementById("animMathDisplay");
        display.innerHTML = "";
        const frame = document.createElement("div");
        frame.className = "anim-transition-frame";
        const compare = document.createElement("div");
        compare.className = "anim-compare";
        const left = document.createElement("div");
        left.className = "anim-eq prev";
        renderMath(left, leftLatex || "");
        compare.appendChild(left);
        if (rightLatex) {
            const arrow = document.createElement("div");
            arrow.className = "anim-arrow enter";
            arrow.textContent = "→";
            const right = document.createElement("div");
            right.className = "anim-eq next enter";
            renderMath(right, rightLatex);
            compare.appendChild(arrow);
            compare.appendChild(right);
        }
        frame.appendChild(compare);
        display.appendChild(frame);
        currentAnimCopyText = normalizeDisplayMath(rightLatex || leftLatex || "");
    }

    function stepForward() {
        if (transitionBusy) {
            queuedDirection = 1;
            return true;
        }
        if (stepIdx >= currentSteps.length - 1) return false;
        showAnimStep(stepIdx + 1);
        return true;
    }

    function stepBack() {
        if (transitionBusy) {
            queuedDirection = -1;
            return true;
        }
        if (stepIdx < 0) return false;
        if (stepIdx === 0) {
            stepIdx = -1;
            renderStationaryStage(baseLatex, "");
            document.querySelectorAll(".step-card").forEach((c) => c.classList.remove("highlight"));
            document.querySelectorAll(".anim-step-item").forEach((c) => c.classList.remove("active"));
            updateIndicator();
            return true;
        }
        showAnimStep(stepIdx - 1);
        return true;
    }

    function renderMath(el, latex) {
        try { katex.render(latex, el, { throwOnError: false, displayMode: false }); }
        catch (_) { el.textContent = latex; }
    }

    function tokenizeGlyphTokens(latex) {
        const cmdMap = {
            "\\sin": "sin", "\\cos": "cos", "\\tan": "tan", "\\ln": "ln", "\\log": "log",
            "\\sqrt": "sqrt", "\\frac": "/", "\\cdot": "·", "\\times": "×", "\\pi": "pi", "\\infty": "∞",
        };
        const raw = String(latex || "").replace(/\\left|\\right|\\,/g, " ");
        const bits = raw.match(/\\[a-zA-Z]+|[A-Za-z]+(?:\^\d+)?|\d+|[+\-*/=()^]|./g) || [];
        const out = [];
        for (const b of bits) {
            const t = b.trim();
            if (!t || t === "{" || t === "}" || t === "_") continue;
            if (cmdMap[t]) { out.push(cmdMap[t]); continue; }
            if (t.startsWith("\\")) continue;
            out.push(t);
        }
        const merged = [];
        for (let i = 0; i < out.length; i++) {
            const t = out[i];
            if (i + 2 < out.length && out[i + 1] === "^" && /^[0-9a-zA-Z]+$/.test(out[i + 2])) {
                merged.push(`${t}^${out[i + 2]}`);
                i += 2;
                continue;
            }
            merged.push(t);
        }
        const clipped = merged.filter(Boolean).slice(0, 28);
        return clipped.length ? clipped : ["x"];
    }

    function buildGlyphParticles(leftTokens, rightTokens, rng, w, h, seed) {
        const particles = [];
        let leftOut = 0, rightOut = 0, leftIn = 0, rightIn = 0;
        const mkSidePos = (side, slot, lane, inward) => {
            const cols = 7;
            const row = Math.floor(slot / cols);
            const col = slot % cols;
            const spreadX = 26;
            const spreadY = 20;
            const baseX = side === "left" ? (inward ? w * 0.28 : w * 0.2) : (inward ? w * 0.72 : w * 0.8);
            const baseY = h * 0.52;
            return {
                x: baseX + (col - 3) * spreadX + (lane * 2),
                y: baseY + (row - 1) * spreadY,
            };
        };
        const mkMid = (i) => ({
            x: w * 0.5 + (rng() - 0.5) * 110 + Math.sin((seed + i * 17) * 0.005) * 12,
            y: h * 0.48 + (rng() - 0.5) * 46,
        });
        const mkSize = () => Math.floor(18 + rng() * 10);
        const leftColor = (a) => `rgba(245, 204, 102, ${a})`;
        const rightColor = (a) => `rgba(141, 204, 255, ${a})`;

        leftTokens.forEach((text, i) => {
            const toRight = ((i + seed) % 3) !== 0;
            const start = mkSidePos("left", leftOut++, 0, false);
            const end = toRight ? mkSidePos("right", rightIn++, 1, true) : mkSidePos("left", leftIn++, 1, true);
            particles.push({ text, start, mid: mkMid(i), end, split: 0.56, size: mkSize(), color: leftColor });
        });
        rightTokens.forEach((text, i) => {
            const toLeft = ((i + seed) % 3) !== 1;
            const start = mkSidePos("right", rightOut++, 0, false);
            const end = toLeft ? mkSidePos("left", leftIn++, 1, true) : mkSidePos("right", rightIn++, 1, true);
            particles.push({ text, start, mid: mkMid(i + 50), end, split: 0.54, size: mkSize(), color: rightColor });
        });
        return particles.slice(0, 56);
    }

    function particlePosition(g, t) {
        const split = g.split || 0.55;
        if (t <= split) {
            const u = easeOutCubic(t / split);
            return {
                x: lerp(g.start.x, g.mid.x, u),
                y: lerp(g.start.y, g.mid.y, u),
            };
        }
        const u = easeInOutCubic((t - split) / (1 - split));
        return {
            x: lerp(g.mid.x, g.end.x, u),
            y: lerp(g.mid.y, g.end.y, u),
        };
    }

    function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }
    function easeInOutCubic(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }

    function hashString(str) {
        let h = 2166136261;
        for (let i = 0; i < str.length; i++) {
            h ^= str.charCodeAt(i);
            h = Math.imul(h, 16777619);
        }
        return h >>> 0;
    }

    function mulberry32(seed) {
        let t = seed >>> 0;
        return function () {
            t += 0x6D2B79F5;
            let r = Math.imul(t ^ (t >>> 15), 1 | t);
            r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
            return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
        };
    }

    function lerp(a, b, t) { return a + (b - a) * t; }

    function copyText(text) {
        if (!text) return;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
            return;
        }
        fallbackCopy(text);
    }

    function fallbackCopy(text) {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); } catch (_) {}
        ta.remove();
    }

    function copyCurrentAnimationText() {
        if (currentAnimCopyText) {
            copyText(currentAnimCopyText);
            return;
        }
        const fallback = (document.getElementById("animMathDisplay")?.innerText || "").trim();
        if (fallback) copyText(fallback);
    }

    function drawAnimCanvas(step) {
        const needsVisual = step.type === "area" || step.type === "approach";
        aCanvas.style.display = needsVisual ? "block" : "none";
        if (!needsVisual) return;

        const dpr = window.devicePixelRatio || 1;
        const W = aCanvas.width / dpr, H = aCanvas.height / dpr;
        fillBg(aCtx, aCanvas);

        const ctx = aCtx;
        const hints = step.hints || {};

        if (step.type === "area" && graphData && graphData.success) {
            drawMiniGraph(ctx, W, H, graphData, true, false);
        } else if (step.type === "approach" && graphData && graphData.success) {
            drawMiniGraph(ctx, W, H, graphData, false, true);
        }

        if (hints.formula) {
            ctx.fillStyle = "rgba(15,15,35,0.8)";
            ctx.fillRect(W / 2 - 120, H - 50, 240, 36);
            ctx.fillStyle = "#fbbf24";
            ctx.font = "14px monospace";
            ctx.textAlign = "center";
            ctx.fillText(hints.formula, W / 2, H - 28);
        }
    }

    function drawMiniGraph(ctx, W, H, data, showArea, showApproach) {
        const pad = 30, w = W - pad * 2, h = H - pad * 2;
        const xs = data.x, ys = data.y;
        const valid = xs.map((x, i) => [x, ys[i]]).filter(p => p[1] !== null);
        if (!valid.length) return;

        const xMin = valid[0][0], xMax = valid[valid.length - 1][0];
        let yArr = valid.map(p => p[1]);
        yArr.sort((a, b) => a - b);
        const yLo = yArr[Math.floor(yArr.length * 0.02)] - 1;
        const yHi = yArr[Math.floor(yArr.length * 0.98)] + 1;

        const tx = x => pad + ((x - xMin) / (xMax - xMin || 1)) * w;
        const ty = y => pad + h - ((y - yLo) / (yHi - yLo || 1)) * h;

        if (showArea && solveResult && solveResult.detected_type === "INTEGRAL_DEFINITE") {
            const lo = parseFloat(document.getElementById("lowerBound").value) || 0;
            const hi = parseFloat(document.getElementById("upperBound").value) || 1;
            ctx.fillStyle = "rgba(233,69,96,0.25)";
            ctx.beginPath();
            ctx.moveTo(tx(lo), ty(0));
            for (let i = 0; i < xs.length; i++) {
                if (xs[i] < lo || xs[i] > hi || ys[i] === null) continue;
                ctx.lineTo(tx(xs[i]), ty(ys[i]));
            }
            ctx.lineTo(tx(hi), ty(0));
            ctx.closePath();
            ctx.fill();
        }

        ctx.strokeStyle = "#e94560";
        ctx.lineWidth = 2;
        ctx.beginPath();
        let started = false;
        for (let i = 0; i < xs.length; i++) {
            if (ys[i] === null) { started = false; continue; }
            const cx = tx(xs[i]), cy = ty(Math.max(yLo, Math.min(yHi, ys[i])));
            if (!started) { ctx.moveTo(cx, cy); started = true; }
            else { ctx.lineTo(cx, cy); }
        }
        ctx.stroke();

        if (showApproach) {
            const pt = parseFloat(document.getElementById("limitPoint").value);
            if (!isNaN(pt)) {
                const px = tx(pt);
                ctx.setLineDash([4, 4]);
                ctx.strokeStyle = "#fbbf24";
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.moveTo(px, pad);
                ctx.lineTo(px, pad + h);
                ctx.stroke();
                ctx.setLineDash([]);
                ctx.fillStyle = "#fbbf24";
                ctx.font = "12px sans-serif";
                ctx.textAlign = "center";
                ctx.fillText("x → " + pt, px, pad - 5);
            }
        }
    }

    function clearAnimStage() {
        document.getElementById("animMathDisplay").innerHTML = "";
        clearTimeout(badgeTimer);
        clearTimeout(descTimer);
        const badge = document.getElementById("animRuleBadge");
        const desc = document.getElementById("animDescription");
        badge.className = "anim-rule-badge";
        desc.className = "anim-description";
        badge.textContent = "";
        desc.textContent = "";
        aCanvas.style.display = "none";
        transitionBusy = false;
        queuedDirection = 0;
        currentAnimCopyText = "";
    }

    function updateIndicator() {
        document.getElementById("stepIndicator").textContent = `Step ${Math.max(0, stepIdx + 1)} / ${currentSteps.length}`;
    }
})();
