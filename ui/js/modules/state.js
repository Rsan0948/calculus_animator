/**
 * Global state management for the Calculus Animator.
 */
export const state = {
    mathField: null,
    allFormulas: [],
    currentSteps: [],
    stepIdx: -1,
    animPlaying: false,
    animTimer: null,
    zoom: 1,
    graphData: null,
    solveResult: null,
    demoMap: {},
    learningLibrary: { categories: [], symbols: [], formulas: [], topics: [] },
    learningTopicById: {},
    learningFormulaById: {},
    learningSymbolById: {},
    learningActiveCategory: "all",
    learningActiveView: "concepts",
    learningSelectedTopicId: "",
    learningSelectedFormulaId: "",
    learningSelectedSymbolId: "",
    learningMode: "home",
    curriculum: { pathways: [] },
    glossary: { terms: [] },
    glossaryById: {},
    glossaryLexicon: [],
    selectedPathwayId: "",
    selectedChapterId: "",
    selectedSlideIndex: 0,
    learningProgress: {},
    // Furthest-slide-reached marker per chapter. Persisted in localStorage
    // and rendered as "Slide N of M" on chapter cards. Updated whenever
    // renderCurrentSlide runs, so any path that lands on a slide
    // (next-click, restore, direct chapter click) contributes.
    chapterProgress: {},
    relatedTopicPicks: [],
    stepRenderToken: 0,
    // Monotonic tokens guarding async round trips against out-of-order
    // responses (each consumer bumps its token per request and discards
    // any response whose token is no longer current).
    solveToken: 0,
    graphToken: 0,
    capacityRenderToken: 0,
    // Set by ui_events.bindUI so the DOM-ready fallback nav in app.js
    // stops handling screen-button clicks once the real handlers exist.
    uiEventsBound: false,
    baseLatex: "",
    transitionBusy: false,
    queuedDirection: 0,
    currentAnimCopyText: "",
    learningSlideRenderToken: 0,
    pathwaySidebarCollapsed: false,
    solverSidebarCollapsed: false,
    // On mobile the rendered slide visual is small and the bullet text
    // is the primary content surface, so default the "Show Slide Text"
    // toggle to expanded on phones. Desktop stays false (the rendered
    // slide image is larger and the text is supplementary). Toggle is
    // still reachable via the existing Show/Hide Slide Text button on
    // any viewport.
    showSlideTextDetails: (typeof window !== "undefined"
        && typeof window.matchMedia === "function"
        && window.matchMedia("(max-width: 768px)").matches),
    slideNotesOpen: false,
    slideNotesWidth: 420,
    showPathwayPicker: false,
    quickSymbolGroups: {},
    activeQuickSymbolTab: "Calculus",
    capacityState: {
        pageIndex: 0,
        totalPages: 0,
        allPagesText: [],
        pageText: "",
        withImage: false,
        text: "",
        lastStats: null,
    },
    badgeTimer: null,
    descTimer: null,
    
    // Constants
    AUTO_STEP_MS: 4000,
    GLYPH_ONLY_MS: 1500,
    POST_REVEAL_MS: 450,
    TRANSITION_MS: 1500 + 450, // GLYPH_ONLY_MS + POST_REVEAL_MS

    // Canvases
    gCanvas: null,
    gCtx: null,
    aCanvas: null,
    aCtx: null,
};
