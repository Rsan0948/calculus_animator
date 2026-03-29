/**
 * Renderer module for Canvas drawing and UI component rendering.
 */
import { state } from './state.js';
import * as utils from './utils.js';
import { bridge } from './bridge.js';

export const renderer = {
    setupCanvases() {
        state.gCanvas = document.getElementById("graphCanvas");
        state.gCtx = state.gCanvas.getContext("2d");
        state.aCanvas = document.getElementById("animCanvas");
        state.aCtx = state.aCanvas.getContext("2d");
        const dpr = window.devicePixelRatio || 1;
        for (const [cv, ctx] of [[state.gCanvas, state.gCtx], [state.aCanvas, state.aCtx]]) {
            const w = cv.width, h = cv.height;
            cv.width = w * dpr;
            cv.height = h * dpr;
            cv.style.width = w + "px";
            cv.style.height = h + "px";
            ctx.scale(dpr, dpr);
        }
        this.clearCanvases();
    },

    clearCanvases() {
        this.fillBg(state.gCtx, state.gCanvas);
        this.fillBg(state.aCtx, state.aCanvas);
    },

    fillBg(ctx, cv) {
        const dpr = window.devicePixelRatio || 1;
        ctx.fillStyle = "#0f0f23";
        ctx.fillRect(0, 0, cv.width / dpr, cv.height / dpr);
    },

    drawGraph() {
        const ctx = state.gCtx, data = state.graphData;
        const dpr = window.devicePixelRatio || 1;
        const W = state.gCanvas.width / dpr, H = state.gCanvas.height / dpr;
        this.fillBg(ctx, state.gCanvas);
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

        const xRange = Array.isArray(data.x_range) && data.x_range.length === 2 ? data.x_range : [-10 / state.zoom, 10 / state.zoom];
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
    },

    renderCategories(cats, onCategoryClick) {
        const el = document.getElementById("categoryList");
        if (!el) return;
        el.innerHTML = '<button class="category-btn active" data-category="all">All</button>' +
            cats.map(c => `<button class="category-btn" data-category="${c.id}">${c.icon} ${c.name}</button>`).join("");
        el.addEventListener("click", e => {
            const btn = e.target.closest(".category-btn");
            if (!btn) return;
            el.querySelectorAll(".category-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            if (onCategoryClick) onCategoryClick(btn.dataset.category);
        });
    },

    renderFormulas(list) {
        const el = document.getElementById("formulaList");
        if (!el) return;
        el.innerHTML = list.map(f => {
            const escLatex = utils.escAttr(f.latex);
            const escTag = utils.escAttr(f.tag || "");
            const escParams = utils.escAttr(JSON.stringify(f.params || {}));
            return `<div class="formula-item" data-latex="${escLatex}" data-tag="${escTag}" data-params="${escParams}">
                <div class="name">${f.name}</div><div class="preview"></div></div>`;
        }).join("");
        el.querySelectorAll(".formula-item").forEach(item => {
            try { katex.render(item.dataset.latex, item.querySelector(".preview"), { throwOnError: false, displayMode: false }); } catch (_) {}
        });
    },

    renderDemoDropdown(collections) {
        const sel = document.getElementById("demoSelect");
        if (!sel) return;
        state.demoMap = {};
        let html = '<option value="">Select a demo problem…</option>';
        collections.forEach(c => {
            const demos = c.demos || [];
            if (!demos.length) return;
            html += `<optgroup label="${utils.escAttr(c.name || "Demo Collection")}">`;
            demos.forEach(d => {
                state.demoMap[d.id] = d;
                html += `<option value="${utils.escAttr(d.id)}">${utils.esc(d.title || d.id)}${d.subtitle ? " - " + utils.esc(d.subtitle) : ""}</option>`;
            });
            html += "</optgroup>";
        });
        sel.innerHTML = html;
    },

    renderSymbols(groups) {
        state.quickSymbolGroups = {};
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
            state.quickSymbolGroups[k] = g.symbols || [];
        });
        const order = ["Calculus", "Functions", "Greek", "Operators"];
        if (!order.some(k => k === state.activeQuickSymbolTab && (state.quickSymbolGroups[k] || []).length)) {
            state.activeQuickSymbolTab = order.find(k => (state.quickSymbolGroups[k] || []).length) || "Calculus";
        }
        const tabs = document.getElementById("quickSymbolTabs");
        const grid = document.getElementById("quickSymbolGrid");
        if (!tabs || !grid) return;
        tabs.innerHTML = order.map(name => {
            const count = (state.quickSymbolGroups[name] || []).length;
            if (!count) return "";
            return `<button class="quick-symbol-tab${name === state.activeQuickSymbolTab ? " active" : ""}" data-symbol-tab="${utils.escAttr(name)}">${name}</button>`;
        }).join("");
        this.renderQuickSymbolGrid();
    },

    renderQuickSymbolGrid() {
        const grid = document.getElementById("quickSymbolGrid");
        if (!grid) return;
        const symbols = state.quickSymbolGroups[state.activeQuickSymbolTab] || [];
        if (!symbols.length) {
            grid.innerHTML = `<span class="learning-empty-inline">No symbols in this group.</span>`;
            return;
        }
        grid.innerHTML = symbols.map(s =>
            `<button class="sym-btn" data-latex="${utils.escAttr(s.latex || "")}" title="${utils.escAttr(s.latex || "")}">${utils.esc(s.label || "")}</button>`
        ).join("");
    },

    renderLearningLibrary(data) {
        bridge.log(`renderLearningLibrary called with ${Object.keys(data || {}).length} keys`);
        state.learningLibrary = {
            categories: Array.isArray(data?.categories) ? data.categories : [],
            symbols: Array.isArray(data?.symbols) ? data.symbols : [],
            formulas: Array.isArray(data?.formulas) ? data.formulas : [],
            topics: Array.isArray(data?.topics) ? data.topics : [],
        };
        state.learningTopicById = {};
        state.learningFormulaById = {};
        state.learningSymbolById = {};
        state.learningLibrary.topics.forEach(t => {
            if (t?.id) state.learningTopicById[t.id] = t;
        });
        state.learningLibrary.formulas.forEach(f => {
            if (f?.id) state.learningFormulaById[f.id] = f;
        });
        state.learningLibrary.symbols.forEach(s => {
            if (s?.id) state.learningSymbolById[s.id] = s;
        });
        if (!state.learningSelectedTopicId && state.learningLibrary.topics.length) state.learningSelectedTopicId = state.learningLibrary.topics[0].id;
        if (!state.learningSelectedFormulaId && state.learningLibrary.formulas.length) state.learningSelectedFormulaId = state.learningLibrary.formulas[0].id;
        if (!state.learningSelectedSymbolId && state.learningLibrary.symbols.length) state.learningSelectedSymbolId = state.learningLibrary.symbols[0].id;
        
        bridge.log(`State initialized: ${state.learningLibrary.topics.length} topics, ${state.learningLibrary.formulas.length} formulas`);
        this.renderLearningViewTabs();
        this.renderLearningCategories();
        this.renderLearningItems();
    },

    renderLearningViewTabs() {
        const el = document.getElementById("learningViewTabs");
        if (!el) return;
        const views = [
            { id: "concepts", label: "Concepts" },
            { id: "formulas", label: "Formulas" },
            { id: "symbols", label: "Symbols" },
        ];
        el.innerHTML = views.map(v => `<button class="learning-view-btn${v.id === state.learningActiveView ? " active" : ""}" data-learning-view="${v.id}">${v.label}</button>`).join("");
    },

    renderLearningCategories() {
        const el = document.getElementById("learningCategoryChips");
        if (!el) return;
        if (state.learningActiveView !== "concepts") {
            el.innerHTML = `<div class="learning-chip-note">Category filters apply to concept pages.</div>`;
            return;
        }
        const chips = ['<button class="learning-chip active" data-learning-category="all">All Topics</button>'];
        state.learningLibrary.categories.forEach(c => {
            if (!c?.id) return;
            chips.push(`<button class="learning-chip" data-learning-category="${utils.escAttr(c.id)}">${utils.esc(c.name || c.id)}</button>`);
        });
        el.innerHTML = chips.join("");
        el.querySelectorAll(".learning-chip").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.learningCategory === state.learningActiveCategory);
        });
    },

    renderLearningItems() {
        const list = document.getElementById("learningItemList");
        if (!list) return;
        this.renderLearningViewTabs();
        this.renderLearningCategories();
        const q = (document.getElementById("learningSearch")?.value || "").toLowerCase().trim();
        if (state.learningActiveView === "concepts") {
            const filteredTopics = state.learningLibrary.topics.filter(topic => {
                if (!topic) return false;
                if (state.learningActiveCategory !== "all" && topic.category !== state.learningActiveCategory) return false;
                if (!q) return true;
                const hay = [
                    topic.title || "",
                    topic.summary || "",
                    topic.narrative || "",
                    ...(Array.isArray(topic.symbols) ? topic.symbols : []),
                    ...(Array.isArray(topic.formulas) ? topic.formulas : []),
                ].join(" ").toLowerCase();
                return hay.includes(q);
            });
            if (!filteredTopics.length) {
                list.innerHTML = '<div class="learning-topic-empty">No concepts match this filter yet.</div>';
                this.renderLearningDetail({ type: "concept", topic: null });
                return;
            }
            list.innerHTML = filteredTopics.map(topic => `
                <button class="learning-topic-btn${topic.id === state.learningSelectedTopicId ? " active" : ""}" data-learning-item-type="concept" data-learning-item-id="${utils.escAttr(topic.id)}">
                    <span class="learning-topic-title">${utils.prettyText(topic.title || topic.id)}</span>
                    <span class="learning-topic-summary">${utils.prettyText(topic.summary || "Concept overview placeholder")}</span>
                </button>
            `).join("");
            if (!state.learningSelectedTopicId || !filteredTopics.some(t => t.id === state.learningSelectedTopicId)) {
                state.learningSelectedTopicId = filteredTopics[0].id;
            }
            this.renderLearningDetail({ type: "concept", topic: state.learningTopicById[state.learningSelectedTopicId] || null });
            list.querySelectorAll(".learning-topic-btn").forEach(btn => {
                btn.classList.toggle("active", btn.dataset.learningItemId === state.learningSelectedTopicId);
            });
            return;
        }

        if (state.learningActiveView === "formulas") {
            const filteredFormulas = state.learningLibrary.formulas.filter(formula => {
                if (!formula) return false;
                if (!q) return true;
                const hay = [formula.name || "", formula.plain || "", formula.latex || "", ...(formula.tags || [])].join(" ").toLowerCase();
                return hay.includes(q);
            });
            if (!filteredFormulas.length) {
                list.innerHTML = '<div class="learning-topic-empty">No formulas match this filter yet.</div>';
                this.renderLearningDetail({ type: "formula", formula: null });
                return;
            }
            list.innerHTML = filteredFormulas.map(formula => `
                <button class="learning-topic-btn${formula.id === state.learningSelectedFormulaId ? " active" : ""}" data-learning-item-type="formula" data-learning-item-id="${utils.escAttr(formula.id)}">
                    <span class="learning-topic-title">${utils.prettyText(formula.name || formula.id)}</span>
                    <span class="learning-topic-summary">${utils.prettyText(formula.plain || formula.latex || "Formula reference")}</span>
                </button>
            `).join("");
            if (!state.learningSelectedFormulaId || !filteredFormulas.some(f => f.id === state.learningSelectedFormulaId)) {
                state.learningSelectedFormulaId = filteredFormulas[0].id;
            }
            this.renderLearningDetail({ type: "formula", formula: state.learningFormulaById[state.learningSelectedFormulaId] || null });
            list.querySelectorAll(".learning-topic-btn").forEach(btn => {
                btn.classList.toggle("active", btn.dataset.learningItemId === state.learningSelectedFormulaId);
            });
            return;
        }

        const filteredSymbols = state.learningLibrary.symbols.filter(symbol => {
            if (!symbol) return false;
            if (!q) return true;
            const hay = [symbol.symbol || "", symbol.name || "", symbol.meaning || ""].join(" ").toLowerCase();
            return hay.includes(q);
        });
        if (!filteredSymbols.length) {
            list.innerHTML = '<div class="learning-topic-empty">No symbols match this filter yet.</div>';
            this.renderLearningDetail({ type: "symbol", symbol: null });
            return;
        }
        list.innerHTML = filteredSymbols.map(symbol => `
            <button class="learning-topic-btn${symbol.id === state.learningSelectedSymbolId ? " active" : ""}" data-learning-item-type="symbol" data-learning-item-id="${utils.escAttr(symbol.id)}">
                <span class="learning-topic-title">${utils.prettyText((symbol.symbol ? symbol.symbol + " " : "") + (symbol.name || symbol.id))}</span>
                <span class="learning-topic-summary">${utils.prettyText(symbol.meaning || "Symbol reference")}</span>
            </button>
        `).join("");
        if (!state.learningSelectedSymbolId || !filteredSymbols.some(s => s.id === state.learningSelectedSymbolId)) {
            state.learningSelectedSymbolId = filteredSymbols[0].id;
        }
        this.renderLearningDetail({ type: "symbol", symbol: state.learningSymbolById[state.learningSelectedSymbolId] || null });
        list.querySelectorAll(".learning-topic-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.learningItemId === state.learningSelectedSymbolId);
        });
    },

    renderLearningDetail(model) {
        const detail = document.getElementById("learningDetail");
        if (!detail) return;
        const section = (title, bodyHtml, options = {}) => {
            const collapsible = options.collapsible !== false;
            const collapsed = options.collapsed !== false;
            if (!collapsible) {
                return `<section class="learning-block">
                    <h3>${utils.prettyText(title)}</h3>
                    <div class="learning-block-content">${bodyHtml}</div>
                </section>`;
            }
            return `<section class="learning-block collapsible${collapsed ? " collapsed" : ""}" data-learning-block="${utils.escAttr(options.key || title.toLowerCase())}">
                <button class="learning-block-toggle" type="button" data-learning-toggle="1">
                    <h3>${utils.prettyText(title)}</h3>
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
            const linkedTopics = state.learningLibrary.topics.filter(t => (t.formulas || []).includes(formula.id));
            detail.innerHTML = `
                <div class="learning-detail-head">
                    <h2>${utils.prettyText(formula.name || formula.id)}</h2>
                    <p>Formula reference</p>
                </div>
                ${section("Plain Form", `<p>${utils.prettyText(formula.plain || "")}</p>`, { key: "plain_form", collapsible: false })}
                ${section("LaTeX Form", `<p>${utils.prettyText(formula.latex || "")}</p>`, { key: "latex_form", collapsed: true })}
                ${section("Associated Topics", `<div class="learning-related-row">
                        ${linkedTopics.map(t => `<button class="learning-related-btn" data-related-topic="${utils.escAttr(t.id)}">${utils.prettyText(t.title || t.id)}</button>`).join("") || '<span class="learning-empty-inline">No linked concept topics yet.</span>'}
                    </div>`, { key: "associated_topics", collapsed: true })}
            `;
            return;
        }

        if (model.type === "symbol") {
            const symbol = model.symbol;
            const linkedTopics = state.learningLibrary.topics.filter(t => (t.symbols || []).includes(symbol.id));
            detail.innerHTML = `
                <div class="learning-detail-head">
                    <h2>${utils.prettyText(symbol.symbol || symbol.name || symbol.id)}</h2>
                    <p>${utils.prettyText(symbol.name || "Symbol reference")}</p>
                </div>
                ${section("Meaning", `<p>${utils.prettyText(symbol.meaning || "Meaning placeholder")}</p>`, { key: "symbol_meaning", collapsible: false })}
                ${section("Associated Topics", `<div class="learning-related-row">
                        ${linkedTopics.map(t => `<button class="learning-related-btn" data-related-topic="${utils.escAttr(t.id)}">${utils.prettyText(t.title || t.id)}</button>`).join("") || '<span class="learning-empty-inline">No linked concept topics yet.</span>'}
                    </div>`, { key: "symbol_topics", collapsed: true })}
            `;
            return;
        }

        const topic = model.topic;
        const symbolCards = (topic.symbols || []).map(id => {
            const sym = state.learningSymbolById[id];
            if (!sym) return null;
            return `<div class="learning-mini-card">
                <div class="learning-mini-head">${utils.prettyText(sym.symbol || sym.name || id)}</div>
                <div class="learning-mini-body">${utils.prettyText(sym.meaning || sym.name || "")}</div>
            </div>`;
        }).filter(Boolean).join("");

        const formulaCards = (topic.formulas || []).map(id => {
            const f = state.learningFormulaById[id];
            if (!f) return null;
            return `<div class="learning-mini-card">
                <div class="learning-mini-head">${utils.prettyText(f.name || id)}</div>
                <div class="learning-mini-body">${utils.prettyText(f.plain || f.latex || "")}</div>
            </div>`;
        }).filter(Boolean).join("");

        const exampleCards = (topic.examples || []).map(ex => `
            <article class="learning-example-card">
                <h4>${utils.prettyText(ex.title || "Example")}</h4>
                <p class="learning-example-problem">${utils.prettyText(ex.problem || "Problem placeholder")}</p>
                <div class="learning-example-steps">
                    ${(ex.steps || []).map((st, i) => `
                        <div class="learning-example-step">
                            <div class="learning-example-step-title">${i + 1}. ${utils.prettyText(st.title || "Step")}</div>
                            <div class="learning-example-step-explain">${utils.prettyText(st.explanation || "")}</div>
                            <div class="learning-example-step-math">${utils.prettyText(st.math || "")}</div>
                        </div>
                    `).join("") || '<div class="learning-example-step-empty">Steps will appear here when content is added.</div>'}
                </div>
            </article>
        `).join("");

        const related = (topic.related || []).map(id => {
            const t = state.learningTopicById[id];
            if (!t) return null;
            return `<button class="learning-related-btn" data-related-topic="${utils.escAttr(id)}">${utils.prettyText(t.title || id)}</button>`;
        }).filter(Boolean).join("");

        detail.innerHTML = `
            <div class="learning-detail-head">
                <h2>${utils.prettyText(topic.title || topic.id)}</h2>
                <p>${utils.prettyText(topic.summary || "")}</p>
            </div>
            ${section("Narrative", `<p>${utils.prettyText(topic.narrative || "Narrative placeholder for teaching notes.")}</p>`, { key: "narrative", collapsible: false })}
            ${section("Symbols", `<div class="learning-mini-grid">${symbolCards || '<div class="learning-empty-inline">No linked symbols yet.</div>'}</div>`, { key: "symbols", collapsed: true })}
            ${section("Formulas", `<div class="learning-mini-grid">${formulaCards || '<div class="learning-empty-inline">No linked formulas yet.</div>'}</div>`, { key: "formulas", collapsed: true })}
            ${section("Step-by-Step Examples", `<div class="learning-example-grid">${exampleCards || '<div class="learning-empty-inline">No examples linked yet.</div>'}</div>`, { key: "examples", collapsed: true })}
            ${section("Related Topics", `<div class="learning-related-row">${related || '<span class="learning-empty-inline">No related topics yet.</span>'}</div>`, { key: "related_topics", collapsed: true })}
        `;
    },

    renderGlossaryList() {
        const list = document.getElementById("glossaryList");
        if (!list) return;
        const q = (document.getElementById("glossarySearch")?.value || "").toLowerCase().trim();
        const terms = (state.glossary.terms || []).filter(t => {
            if (!q) return true;
            return [t.term, ...(t.aliases || []), t.definition].join(" ").toLowerCase().includes(q);
        });
        list.innerHTML = terms.map(t => `
            <button class="learning-topic-btn" data-glossary-id="${utils.escAttr(t.id)}">
                <span class="learning-topic-title">${utils.prettyText(t.term || t.id)}</span>
                <span class="learning-topic-summary">${utils.prettyText(t.definition || "")}</span>
            </button>
        `).join("") || '<div class="learning-topic-empty">No glossary terms match this search.</div>';
    },

    renderLearningHome() {
        const stats = document.getElementById("learningHomeStats");
        if (!stats) return;
        const pathways = state.curriculum.pathways || [];
        const chapters = pathways.reduce((n, p) => n + ((p.chapters || []).length), 0);
        const slides = pathways.reduce((n, p) => n + (p.chapters || []).reduce((m, c) => m + ((c.slides || []).length), 0), 0);
        const concepts = (state.learningLibrary.topics || []).length;
        const formulas = (state.learningLibrary.formulas || []).length;
        const symbols = (state.learningLibrary.symbols || []).length;
        const terms = (state.glossary.terms || []).length;
        stats.innerHTML = [
            `<span class="learning-home-pill">${pathways.length} pathway${pathways.length === 1 ? "" : "s"}</span>`,
            `<span class="learning-home-pill">${chapters} chapters</span>`,
            `<span class="learning-home-pill">${slides} slides</span>`,
            `<span class="learning-home-pill">${concepts} concepts</span>`,
            `<span class="learning-home-pill">${formulas} formulas</span>`,
            `<span class="learning-home-pill">${symbols} symbols</span>`,
            `<span class="learning-home-pill">${terms} glossary terms</span>`,
        ].join("");
    },

    renderPathwayList() {
        const list = document.getElementById("pathwayList");
        const pickerWrap = document.getElementById("pathwayPickerWrap");
        const selectedLabel = document.getElementById("selectedPathwayLabel");
        const pickerToggle = document.getElementById("pathwayPickerToggleBtn");
        if (!list) return;
        const q = (document.getElementById("pathwaySearch")?.value || "").toLowerCase().trim();
        const items = (state.curriculum.pathways || []).filter(p => {
            if (!q) return true;
            const hay = [p.title || "", p.level || "", p.description || ""].join(" ").toLowerCase();
            return hay.includes(q);
        });
        if (!items.length) {
            list.innerHTML = '<div class="learning-topic-empty">No pathways match this search.</div>';
            return;
        }
        if (!state.selectedPathwayId || !items.some(p => p.id === state.selectedPathwayId)) state.selectedPathwayId = items[0].id;
        list.innerHTML = items.map(p => `
            <button class="learning-topic-btn${p.id === state.selectedPathwayId ? " active" : ""}" data-pathway-id="${utils.escAttr(p.id)}">
                <span class="learning-topic-title">${utils.prettyText(p.title || p.id)}</span>
                <span class="learning-topic-summary">${utils.prettyText(p.description || p.level || "")}</span>
            </button>
        `).join("");
        const selected = items.find(p => p.id === state.selectedPathwayId) || null;
        if (selectedLabel) selectedLabel.innerHTML = selected ? utils.prettyText(selected.title || selected.id) : "No course selected";
        if (pickerWrap) pickerWrap.classList.toggle("is-hidden", !state.showPathwayPicker);
        if (pickerToggle) pickerToggle.textContent = state.showPathwayPicker ? "Hide Courses" : "Change Course";
    },

    renderChapterList() {
        const list = document.getElementById("chapterList");
        if (!list) return;
        const pathway = (state.curriculum.pathways || []).find(p => p.id === state.selectedPathwayId);
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
        if (!state.selectedChapterId || !allChapters.some(c => c.id === state.selectedChapterId)) {
            state.selectedChapterId = allChapters[0]?.id || "";
            state.selectedSlideIndex = 0;
        }
        if (state.selectedChapterId && !chapters.some(c => c.id === state.selectedChapterId) && chapters.length) {
            state.selectedChapterId = chapters[0].id;
            state.selectedSlideIndex = 0;
        }
        list.innerHTML = chapters.map(c => `
            <button class="learning-topic-btn${c.id === state.selectedChapterId ? " active" : ""}" data-chapter-id="${utils.escAttr(c.id)}">
                <span class="learning-topic-title">${utils.prettyText(c.title || c.id)}</span>
                <span class="learning-topic-summary">${utils.prettyText(c.description || "")}</span>
            </button>
        `).join("") || '<div class="learning-topic-empty">No chapters yet.</div>';
    },

    renderCurrentSlide() {
        const stage = document.getElementById("slideStage");
        const quizGate = document.getElementById("quizGate");
        const testPanel = document.getElementById("chapterTestPanel");
        const notesBody = document.getElementById("slideNotesBody");
        if (!stage || !quizGate || !testPanel) return;
        const pathway = (state.curriculum.pathways || []).find(p => p.id === state.selectedPathwayId);
        const chapter = pathway ? (pathway.chapters || []).find(c => c.id === state.selectedChapterId) : null;
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
            testPanel.innerHTML = this.renderChapterTest(chapter, pathway.id);
            if (notesBody) notesBody.innerHTML = "";
            return;
        }
        state.selectedSlideIndex = Math.max(0, Math.min(slides.length, state.selectedSlideIndex));
        const introMode = state.selectedSlideIndex === 0;
        const contentIndex = Math.max(0, state.selectedSlideIndex - 1);
        const slide = slides[contentIndex];
        const slideTitle = (slide?.title || slide?.id || "Slide");
        const titleLower = String(slideTitle).toLowerCase();
        const isWorkedTitle = titleLower.includes("worked example");
        const isCompactTitle = isWorkedTitle || String(slideTitle).length > 44;
        const titleClass = `learning-slide-title${isCompactTitle ? " compact" : ""}${isWorkedTitle ? " worked" : ""}`;
        const blocks = (slide?.content_blocks || []).map(b => `
            <div class="learning-block-card ${utils.escAttr(b.kind || "text")}">
                ${utils.prettyText(b.text || "")}
            </div>
        `).join("");
        const graphics = (slide?.graphics || []).map(g => `<span class="glossary-chip">${utils.prettyText(g.kind || "graphic")}: ${utils.prettyText(g.name || "")}</span>`).join("");
        if (introMode) {
            stage.innerHTML = `
                <div class="learning-stage-top">
                    <button class="btn btn-small" id="prevSlideBtn" data-stage-action="prev">← Previous Slide</button>
                    <button class="btn btn-small" id="nextSlideBtn" data-stage-action="next">Next Slide →</button>
                    <button class="btn btn-small btn-secondary" data-stage-action="toggle-notes">${state.slideNotesOpen ? "Hide Notes" : "Show Notes"}</button>
                </div>
                <div class="learning-slide-sub">${utils.prettyText(pathway.title || "Pathway")} · Slide 0 / ${slides.length}</div>
                <div class="learning-slide-title">${utils.prettyText(chapter.title || "Chapter")}</div>
                <div class="learning-empty-inline">${utils.prettyText(chapter.description || "Chapter overview")}</div>
            `;
        } else {
            stage.innerHTML = `
                <div class="learning-stage-top">
                    <button class="btn btn-small" id="prevSlideBtn" data-stage-action="prev">← Previous Slide</button>
                    <button class="btn btn-small" id="nextSlideBtn" data-stage-action="next">Next Slide →</button>
                    <button class="btn btn-small btn-secondary" data-stage-action="toggle-notes">${state.slideNotesOpen ? "Hide Notes" : "Show Notes"}</button>
                    <button class="btn btn-small btn-secondary" id="toggleSlideTextBtn" data-stage-action="toggle-text">${state.showSlideTextDetails ? "Hide Slide Text" : "Show Slide Text"}</button>
                </div>
                <div class="learning-slide-sub">${utils.prettyText(chapter.title)} · Slide ${state.selectedSlideIndex} / ${slides.length}</div>
                <div class="${titleClass}">${utils.prettyText(slideTitle)}</div>
                <div id="learningSlideVisualHost" class="learning-slide-visual loading">Rendering slide visual…</div>
                <div id="learningSlideTextWrap" class="learning-slide-text${state.showSlideTextDetails ? " show" : ""}">
                    ${graphics ? `<div class="learning-related-row" style="margin-bottom:10px">${graphics}</div>` : ""}
                    ${blocks || '<div class="learning-empty-inline">No blocks in this slide yet.</div>'}
                </div>
            `;
            this.renderLearningSlideVisual(pathway.id, chapter.id, contentIndex);
        }
        if (notesBody) {
            if (introMode) {
                notesBody.innerHTML = `
                    <div class="slide-notes-item"><span class="k">chapter</span><div>${utils.prettyText(chapter.description || "No chapter notes yet.")}</div></div>
                `;
            } else {
                const fullBlocks = slide?.content_blocks || [];
                notesBody.innerHTML = fullBlocks.map(b => `
                    <div class="slide-notes-item">
                        <span class="k">${utils.prettyText((b.kind || "text").toUpperCase())}</span>
                        <div>${utils.prettyText(b.text || "")}</div>
                    </div>
                `).join("") || '<div class="slide-notes-item">No notes for this slide.</div>';
            }
        }

        quizGate.innerHTML = [this.renderMicroQuiz(pathway.id, chapter), this.renderQuizGate(pathway.id, chapter)].filter(Boolean).join("");
        testPanel.innerHTML = this.renderChapterTest(chapter, pathway.id);
        this.updateSlideControlState(pathway.id, chapter);
    },

    async renderLearningSlideVisual(pathwayId, chapterId, slideIndex) {
        const token = ++state.learningSlideRenderToken;
        const host = document.getElementById("learningSlideVisualHost");
        if (!host) return;
        try {
            const dpr = Math.max(1.4, Math.min(2.2, window.devicePixelRatio || 1.6));
            const w = Math.max(1600, Math.floor((host.clientWidth || 980) * dpr));
            const h = Math.floor(w * 10 / 16);
            const res = await bridge.renderLearningSlide(pathwayId, chapterId, slideIndex, w, h);
            if (token !== state.learningSlideRenderToken) return;
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
            if (token !== state.learningSlideRenderToken) return;
            host.classList.remove("loading");
            host.innerHTML = `<div class="learning-empty-inline">Slide visual unavailable.</div>`;
            const textWrap = document.getElementById("learningSlideTextWrap");
            if (textWrap) textWrap.classList.add("show");
        }
    },

    renderMicroQuiz(pathwayId, chapter) {
        const interval = Number(chapter?.micro_quiz_interval || 0);
        if (!interval || interval < 2) return "";
        const slides = chapter.slides || [];
        if (state.selectedSlideIndex <= 0) return "";
        const contentNumber = state.selectedSlideIndex;
        if (slides.length < interval + 2 || contentNumber >= slides.length) return "";
        if (contentNumber % interval !== 0) return "";
        state.learningProgress[pathwayId] = state.learningProgress[pathwayId] || {};
        state.learningProgress[pathwayId][chapter.id] = state.learningProgress[pathwayId][chapter.id] || { microTaken: {} };
        const progress = state.learningProgress[pathwayId][chapter.id];
        const key = String(contentNumber);
        return `
            <div class="learning-quiz-title">Micro Quiz Checkpoint</div>
            <div class="learning-q-meta">Long chapter check-in at slide ${contentNumber}. Recommended for retention.</div>
            <button class="btn btn-small btn-secondary" data-action="take-micro-quiz" data-micro-key="${utils.escAttr(key)}">${progress.microTaken[key] ? "Micro Quiz Taken" : "Take Micro Quiz"}</button>
        `;
    },

    renderQuizGate(pathwayId, chapter) {
        const slides = chapter.slides || [];
        if (!slides.length || !chapter.midpoint_quiz) return "";
        const midpoint = Math.floor(slides.length / 2);
        state.learningProgress[pathwayId] = state.learningProgress[pathwayId] || {};
        state.learningProgress[pathwayId][chapter.id] = state.learningProgress[pathwayId][chapter.id] || {};
        const progress = state.learningProgress[pathwayId][chapter.id];
        if (state.selectedSlideIndex <= 0) return "";
        const shouldShow = state.selectedSlideIndex >= midpoint + 1 || progress.midpointTaken;
        if (!shouldShow) return "";
        const quiz = chapter.midpoint_quiz;
        const qList = (quiz.questions || []);
        const questions = qList.map((q, idx) => `
            <div class="learning-question">
                <div class="learning-q-prompt">${idx + 1}. ${utils.prettyText(q.prompt || "")}</div>
                ${(q.choices || []).map((c, cidx) => `<label class="learning-q-choice"><input data-mid-quiz-choice="1" type="radio" name="quiz_${utils.escAttr(q.id || idx)}" value="${cidx}"> ${utils.prettyText(c)}</label>`).join("")}
                <div class="learning-q-meta">${utils.prettyText(q.explanation || "")}</div>
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
    },

    renderChapterTest(chapter, pathwayId) {
        if (!chapter?.final_test) return "";
        const slides = chapter.slides || [];
        if (!slides.length || state.selectedSlideIndex < slides.length) return "";
        state.learningProgress[pathwayId] = state.learningProgress[pathwayId] || {};
        state.learningProgress[pathwayId][chapter.id] = state.learningProgress[pathwayId][chapter.id] || {};
        const progress = state.learningProgress[pathwayId][chapter.id];
        const t = chapter.final_test;
        const qList = t.questions || [];
        const questions = qList.slice(0, 1).map((q, idx) => `
            <div class="learning-question">
                <div class="learning-q-prompt">${idx + 1}. ${utils.prettyText(q.prompt || "Choose any answer to mark this optional test attempted.")}</div>
                ${((q.choices || []).length ? q.choices : ["Option A", "Option B"]).map((c, cidx) => `<label class="learning-q-choice"><input data-final-quiz-choice="1" type="radio" name="final_quiz_${utils.escAttr(q.id || idx)}" value="${cidx}"> ${utils.prettyText(c)}</label>`).join("")}
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
            <div class="learning-q-meta">${utils.prettyText(t.title || "Chapter Test")}</div>
            <div class="learning-q-meta">Questions: ${(t.questions || []).length}</div>
            ${questions || placeholderQuestion}
            <button class="btn btn-small btn-secondary" data-action="take-final-test">${progress.testTaken ? "Test Attempted" : "Start Test (Optional)"}</button>
        `;
    },

    updateSlideControlState(pathwayId, chapter) {
        const prevBtn = document.getElementById("prevSlideBtn");
        const nextBtn = document.getElementById("nextSlideBtn");
        const slides = chapter.slides || [];
        state.learningProgress[pathwayId] = state.learningProgress[pathwayId] || {};
        state.learningProgress[pathwayId][chapter.id] = state.learningProgress[pathwayId][chapter.id] || {};
        const progress = state.learningProgress[pathwayId][chapter.id];
        const midpoint = Math.floor(slides.length / 2);
        if (prevBtn) prevBtn.disabled = state.selectedSlideIndex <= 0;
        if (nextBtn) {
            const blockedByQuiz = chapter.midpoint_quiz && !progress.midpointTaken && state.selectedSlideIndex >= midpoint + 1;
            nextBtn.disabled = state.selectedSlideIndex >= slides.length || blockedByQuiz;
        }
    },

    renderCapacityPage(res = null) {
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
            text.textContent = state.capacityState.pageText || "";
            const p = state.capacityState.pageIndex + 1;
            const t = Math.max(1, state.capacityState.totalPages);
            meta.textContent = `Page ${p} / ${t}`;
            stats.textContent = `Chars on page: ${res.chars_on_page || 0} · Usable chars (non-space): ${res.usable_chars_on_page || 0} · Lines: ${res.max_lines || 0}`;
            state.capacityState.lastStats = {
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
                `with_image=${state.capacityState.lastStats.withImage}`,
                `page=${state.capacityState.lastStats.page}/${state.capacityState.lastStats.totalPages}`,
                `chars_on_page=${state.capacityState.lastStats.charsOnPage}`,
                `usable_chars_on_page=${state.capacityState.lastStats.usableCharsOnPage}`,
                `max_lines=${state.capacityState.lastStats.maxLines}`,
                `line_height_px=${state.capacityState.lastStats.lineHeightPx}`,
                `overflow_chars=${state.capacityState.lastStats.overflowChars}`,
                "",
                "PAGE_TEXT_START",
                state.capacityState.pageText || "",
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

        prevBtn.disabled = state.capacityState.pageIndex <= 0;
        nextBtn.disabled = state.capacityState.pageIndex >= Math.max(0, state.capacityState.totalPages - 1);
    },

    showAnimStep(idx) {
        if (!state.currentSteps.length) return;
        idx = Math.max(0, Math.min(state.currentSteps.length - 1, idx));
        if (state.transitionBusy) return;
        const step = state.currentSteps[idx];
        const renderToken = ++state.stepRenderToken;
        const fromLatex = state.stepIdx >= 0 ? (state.currentSteps[state.stepIdx].after || state.currentSteps[state.stepIdx].before || "") : state.baseLatex;
        const toLatex = step.after || step.before || "";
        state.currentAnimCopyText = utils.normalizeDisplayMath(toLatex || fromLatex || "");
        state.transitionBusy = true;
        state.stepIdx = idx;
        this.updateIndicator();

        document.querySelectorAll(".step-card").forEach((c, i) => c.classList.toggle("highlight", i === idx));
        document.querySelectorAll(".anim-step-item").forEach((c, i) => c.classList.toggle("active", i === idx));

        const display = document.getElementById("animMathDisplay");
        const badge = document.getElementById("animRuleBadge");
        const desc = document.getElementById("animDescription");

        clearTimeout(state.badgeTimer);
        clearTimeout(state.descTimer);
        badge.className = "anim-rule-badge";
        desc.className = "anim-description";
        badge.textContent = "";
        desc.textContent = "";

        const onDone = () => {
            state.transitionBusy = false;
            if (state.queuedDirection !== 0) {
                const dir = state.queuedDirection;
                state.queuedDirection = 0;
                // These will be called on app object
                window.appAPI.stepForward(); 
            }
        };
        if (step.rule === "final_result") {
            this.renderFinalSolution(display, toLatex, renderToken, onDone);
            badge.textContent = "SOLUTION";
            badge.classList.add("solution");
        } else {
            this.animateMathTransition(display, fromLatex, toLatex, renderToken, onDone);
            badge.textContent = (step.rule || "").replace(/_/g, " ");
            badge.classList.add("rule");
        }
        desc.innerHTML = utils.prettyText(step.description || "");
        state.badgeTimer = setTimeout(() => {
            if (renderToken !== state.stepRenderToken) return;
            badge.classList.add("visible");
        }, 180);
        state.descTimer = setTimeout(() => {
            if (renderToken !== state.stepRenderToken) return;
            desc.classList.add("visible");
        }, 320);

        this.drawAnimCanvas(step);
    },

    animateMathTransition(display, beforeLatex, afterLatex, renderToken, onDone) {
        display.classList.remove("fade-in");
        display.classList.add("fade-out");
        setTimeout(() => {
            if (renderToken !== state.stepRenderToken) return;
            display.innerHTML = "";

            const frame = document.createElement("div");
            frame.className = "anim-transition-frame";
            const compare = document.createElement("div");
            compare.className = "anim-compare";

            const prev = document.createElement("div");
            prev.className = "anim-eq prev";
            this.renderMath(prev, beforeLatex || afterLatex || "");

            const arrow = document.createElement("div");
            arrow.className = "anim-arrow";
            arrow.textContent = "→";

            const next = document.createElement("div");
            next.className = "anim-eq next";
            this.renderMath(next, afterLatex || beforeLatex || "");

            compare.appendChild(prev);
            compare.appendChild(arrow);
            compare.appendChild(next);
            frame.appendChild(compare);
            display.appendChild(frame);
            compare.style.opacity = "0";
            compare.style.transform = "translateY(8px)";
            compare.style.transition = "opacity 420ms ease, transform 420ms ease";
            this.renderMotionLayer(frame, beforeLatex, afterLatex, renderToken, state.GLYPH_ONLY_MS);
            requestAnimationFrame(() => {
                if (renderToken !== state.stepRenderToken) return;
                setTimeout(() => {
                    if (renderToken !== state.stepRenderToken) return;
                    compare.style.opacity = "1";
                    compare.style.transform = "translateY(0)";
                    next.classList.add("enter");
                    arrow.classList.add("enter");
                }, state.GLYPH_ONLY_MS);
            });

            display.classList.remove("fade-out");
            display.classList.add("fade-in");
            setTimeout(() => {
                if (renderToken !== state.stepRenderToken) return;
                if (typeof onDone === "function") onDone();
            }, state.TRANSITION_MS);
        }, 220);
    },

    renderFinalSolution(display, finalLatex, renderToken, onDone) {
        display.classList.remove("fade-in");
        display.classList.add("fade-out");
        setTimeout(() => {
            if (renderToken !== state.stepRenderToken) return;
            display.innerHTML = "";
            const wrap = document.createElement("div");
            wrap.className = "anim-final-solution";
            const title = document.createElement("div");
            title.className = "anim-final-title";
            title.textContent = "Solution";
            const eq = document.createElement("div");
            eq.className = "anim-eq settled";
            this.renderMath(eq, finalLatex || "");
            state.currentAnimCopyText = utils.normalizeDisplayMath(finalLatex || "");
            wrap.appendChild(title);
            wrap.appendChild(eq);
            display.appendChild(wrap);
            display.classList.remove("fade-out");
            display.classList.add("fade-in");
            setTimeout(() => {
                if (renderToken !== state.stepRenderToken) return;
                if (typeof onDone === "function") onDone();
            }, 650);
        }, 180);
    },

    renderMotionLayer(frame, beforeLatex, afterLatex, renderToken, durationMs) {
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

        const leftTokens = utils.tokenizeGlyphTokens(beforeLatex);
        const rightTokens = utils.tokenizeGlyphTokens(afterLatex);
        if (!leftTokens.length && !rightTokens.length) {
            canvas.remove();
            return;
        }
        const seed = utils.hashString(`${beforeLatex}=>${afterLatex}`);
        const rng = utils.mulberry32(seed || 1);
        const glyphs = this.buildGlyphParticles(leftTokens, rightTokens, rng, w, h, seed);

        const t0 = performance.now();
        const duration = Math.max(300, durationMs || state.GLYPH_ONLY_MS);
        const paint = (now) => {
            if (renderToken !== state.stepRenderToken) {
                canvas.remove();
                return;
            }
            const t = Math.min(1, (now - t0) / duration);
            ctx.clearRect(0, 0, w, h);
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            glyphs.forEach((g, i) => {
                const p = this.particlePosition(g, t);
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
        };
        requestAnimationFrame(paint);
    },

    renderStationaryStage(leftLatex, rightLatex) {
        const display = document.getElementById("animMathDisplay");
        if (!display) return;
        display.innerHTML = "";
        const frame = document.createElement("div");
        frame.className = "anim-transition-frame";
        const compare = document.createElement("div");
        compare.className = "anim-compare";
        const left = document.createElement("div");
        left.className = "anim-eq prev";
        this.renderMath(left, leftLatex || "");
        compare.appendChild(left);
        if (rightLatex) {
            const arrow = document.createElement("div");
            arrow.className = "anim-arrow enter";
            arrow.textContent = "→";
            const right = document.createElement("div");
            right.className = "anim-eq next enter";
            this.renderMath(right, rightLatex);
            compare.appendChild(arrow);
            compare.appendChild(right);
        }
        frame.appendChild(compare);
        display.appendChild(frame);
        state.currentAnimCopyText = utils.normalizeDisplayMath(rightLatex || leftLatex || "");
    },

    particlePosition(g, t) {
        const split = g.split || 0.55;
        if (t <= split) {
            const u = this.easeOutCubic(t / split);
            return {
                x: utils.lerp(g.start.x, g.mid.x, u),
                y: utils.lerp(g.start.y, g.mid.y, u),
            };
        }
        const u = this.easeInOutCubic((t - split) / (1 - split));
        return {
            x: utils.lerp(g.mid.x, g.end.x, u),
            y: utils.lerp(g.mid.y, g.end.y, u),
        };
    },

    easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); },
    easeInOutCubic(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; },

    buildGlyphParticles(leftTokens, rightTokens, rng, w, h, seed) {
        const particles = [];
        let leftOut = 0, rightOut = 0, leftIn = 0, rightIn = 0;
        const count = leftTokens.length + rightTokens.length;
        const cols = count > 14 ? 10 : 7;
        const spreadX = count > 20 ? 18 : 26;
        const spreadY = count > 20 ? 16 : 20;
        const halfCols = Math.floor(cols / 2);
        const mkSidePos = (side, slot, lane, inward) => {
            const row = Math.floor(slot / cols);
            const col = slot % cols;
            const baseX = side === "left" ? (inward ? w * 0.28 : w * 0.2) : (inward ? w * 0.72 : w * 0.8);
            const baseY = h * 0.52;
            return {
                x: baseX + (col - halfCols) * spreadX + (lane * 2),
                y: baseY + (row - 1) * spreadY,
            };
        };
        const mkMid = (i) => ({
            x: w * 0.5 + (rng() - 0.5) * 110 + Math.sin((seed + i * 17) * 0.005) * 12,
            y: h * 0.48 + (rng() - 0.5) * 46,
        });
        const baseSize = Math.max(11, 28 - Math.floor(count / 4));
        const mkSize = () => Math.floor(baseSize + rng() * Math.min(6, baseSize - 11));
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
    },

    renderMath(el, latex) {
        try { katex.render(latex, el, { throwOnError: false, displayMode: false }); }
        catch (_) { el.textContent = latex; }
    },

    drawAnimCanvas(step) {
        const needsVisual = step.type === "area" || step.type === "approach";
        state.aCanvas.style.display = needsVisual ? "block" : "none";
        if (!needsVisual) return;

        const dpr = window.devicePixelRatio || 1;
        const W = state.aCanvas.width / dpr, H = state.aCanvas.height / dpr;
        this.fillBg(state.aCtx, state.aCanvas);

        const ctx = state.aCtx;
        const hints = step.hints || {};

        if (step.type === "area" && state.graphData && state.graphData.success) {
            this.drawMiniGraph(ctx, W, H, state.graphData, true, false);
        } else if (step.type === "approach" && state.graphData && state.graphData.success) {
            this.drawMiniGraph(ctx, W, H, state.graphData, false, true);
        }

        if (hints.formula) {
            ctx.fillStyle = "rgba(15,15,35,0.8)";
            ctx.fillRect(W / 2 - 120, H - 50, 240, 36);
            ctx.fillStyle = "#fbbf24";
            ctx.font = "14px monospace";
            ctx.textAlign = "center";
            ctx.fillText(hints.formula, W / 2, H - 28);
        }
    },

    drawMiniGraph(ctx, W, H, data, showArea, showApproach) {
        const pad = 30, w = W - pad * 2, h = H - pad * 2;
        const xs = data.x, ys = data.y;
        if (!xs || !ys) return;
        const valid = xs.map((x, i) => [x, ys[i]]).filter(p => p[1] !== null);
        if (!valid.length) return;

        const xMin = valid[0][0], xMax = valid[valid.length - 1][0];
        let yArr = valid.map(p => p[1]);
        yArr.sort((a, b) => a - b);
        const yLo = yArr[Math.floor(yArr.length * 0.02)] - 1;
        const yHi = yArr[Math.floor(yArr.length * 0.98)] + 1;

        const tx = x => pad + ((x - xMin) / (xMax - xMin || 1)) * w;
        const ty = y => pad + h - ((y - yLo) / (yHi - yLo || 1)) * h;

        if (showArea && state.solveResult && state.solveResult.detected_type === "INTEGRAL_DEFINITE") {
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
    },

    updateIndicator() {
        const el = document.getElementById("stepIndicator");
        if (el) el.textContent = `Step ${Math.max(0, state.stepIdx + 1)} / ${state.currentSteps.length}`;
    }
};
