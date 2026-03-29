/**
 * Bridge module for pywebview API communication.
 */
import { state } from './state.js';

export const bridge = {
    // Utility to log back to python console
    log(msg, level = "info") {
        if (window.pywebview && pywebview.api && pywebview.api.log_to_python) {
            pywebview.api.log_to_python(msg, level);
        }
        console[level === "error" ? "error" : "log"](`[JS] ${msg}`);
    },

    async loadFormulas() {
        try {
            const raw = await pywebview.api.get_formulas();
            return JSON.parse(raw);
        } catch (e) {
            this.log(`formulas load failed: ${e.message}`, "error");
            return { categories: [], formulas: [] };
        }
    },

    async loadDemoProblems() {
        try {
            const raw = await pywebview.api.get_demo_problems();
            return JSON.parse(raw);
        } catch (e) {
            this.log(`demo load failed: ${e.message}`, "error");
            return { collections: [] };
        }
    },

    async loadSymbols() {
        try {
            const raw = await pywebview.api.get_symbols();
            return JSON.parse(raw);
        } catch (e) {
            this.log(`loadSymbols failed: ${e.message}`, "error");
            return { groups: [] };
        }
    },

    async loadLearningLibrary() {
        try {
            const raw = await pywebview.api.get_learning_library();
            return JSON.parse(raw);
        } catch (e) {
            this.log(`learning load failed: ${e.message}`, "warn");
            return { categories: [], symbols: [], formulas: [], topics: [] };
        }
    },

    async loadCurriculum() {
        try {
            const raw = await pywebview.api.get_curriculum();
            const data = JSON.parse(raw);
            this.log(`curriculum loaded: ${Array.isArray(data?.pathways) ? data.pathways.length : 0} pathways`);
            return data;
        } catch (e) {
            this.log(`curriculum load failed: ${e.message}`, "error");
            return { pathways: [] };
        }
    },

    async loadGlossary() {
        try {
            const raw = await pywebview.api.get_glossary();
            return JSON.parse(raw);
        } catch (e) {
            this.log(`glossary load failed: ${e.message}`, "warn");
            return { terms: [] };
        }
    },

    async solve(latex, calcType, params) {
        try {
            const raw = await pywebview.api.solve(latex, calcType, JSON.stringify(params));
            return JSON.parse(raw);
        } catch (e) {
            this.log(`solve failed: ${e.message}`, "error");
            return { success: false, error: e.message };
        }
    },

    async getGraphData(latex, calcType, params, xMin, xMax) {
        try {
            const raw = await pywebview.api.get_graph_data(latex, calcType, JSON.stringify(params), xMin, xMax);
            return JSON.parse(raw);
        } catch (e) {
            this.log(`getGraphData failed: ${e.message}`, "error");
            return { success: false, error: e.message };
        }
    },

    async renderLearningSlide(pathwayId, chapterId, slideIndex, w, h) {
        try {
            const raw = await pywebview.api.render_learning_slide(pathwayId, chapterId, slideIndex, w, h);
            return JSON.parse(raw);
        } catch (e) {
            this.log(`renderLearningSlide failed: ${e.message}`, "error");
            return { success: false, error: e.message };
        }
    },

    async capacityTestSlide(text, withImage, pageIndex, width, height) {
        try {
            const raw = await pywebview.api.capacity_test_slide(text, withImage, pageIndex, width, height);
            return JSON.parse(raw);
        } catch (e) {
            this.log(`capacityTestSlide failed: ${e.message}`, "error");
            return { success: false, error: e.message };
        }
    }
};
