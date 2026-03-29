/**
 * Utility functions for string escaping, math normalization, and particles.
 */
import { state } from './state.js';

export function esc(s) {
    return s ? String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;") : "";
}

export function escAttr(s) {
    return String(s || "")
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

export function prettyText(s) {
    return applyGlossaryLinks(formatPrettyMathHtml(normalizePrettyMathSource(s || "")));
}

export function normalizePrettyMathSource(text) {
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

export function formatPrettyMathHtml(text) {
    let t = esc(text || "");
    for (let i = 0; i < 6; i++) {
        const next = t.replace(/\(([^()]+)\)\s*\/\s*\(([^()]+)\)/g, (_m, num, den) =>
            `<span class="math-frac"><span class="math-frac-num">${num}</span><span class="math-frac-bar"></span><span class="math-frac-den">${den}</span></span>`
        );
        if (next === t) break;
        t = next;
    }
    t = t.replace(/(^|[\s=+\-*(])([a-zA-Z0-9.]+)\s*\/\s*([a-zA-Z0-9.]+)(?=$|[\s=+\-*)])/g,
        (_m, pre, num, den) => `${pre}<span class="math-frac"><span class="math-frac-num">${num}</span><span class="math-frac-bar"></span><span class="math-frac-den">${den}</span></span>`);
    t = t.replace(/\^\{([^}]+)\}/g, (_m, exp) => `<sup>${exp}</sup>`);
    t = t.replace(/\^\(([^)]+)\)/g, (_m, exp) => `<sup>${exp}</sup>`);
    t = t.replace(/\^([a-zA-Z0-9+\-]+)/g, (_m, exp) => `<sup>${exp}</sup>`);
    t = t.replace(/_\{([^}]+)\}/g, (_m, sub) => `<sub>${sub}</sub>`);
    t = t.replace(/_\(([^)]+)\)/g, (_m, sub) => `<sub>${sub}</sub>`);
    t = t.replace(/_([a-zA-Z0-9+\-]+)/g, (_m, sub) => `<sub>${sub}</sub>`);
    return t;
}

export function applyGlossaryLinks(html) {
    if (!html || !state.glossaryLexicon || !state.glossaryLexicon.length) return html;
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
        state.glossaryLexicon.slice(0, 30).forEach(entry => {
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

export function normalizeDisplayMath(text) {
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

export function applyPrettyScripts(s) {
    s = s.replace(/\^\(([^)]+)\)/g, (_, p1) => toSuperscript("(" + p1 + ")"));
    s = s.replace(/_\(([^)]+)\)/g, (_, p1) => toSubscript("(" + p1 + ")"));
    s = s.replace(/\^([+\-]?\d+)/g, (_, p1) => toSuperscript(p1));
    s = s.replace(/\^([a-zA-Z]+)/g, (_, p1) => toSuperscript(p1));
    s = s.replace(/_([+\-]?\d+)/g, (_, p1) => toSubscript(p1));
    s = s.replace(/_([a-zA-Z]+)/g, (_, p1) => toSubscript(p1));
    return s;
}

export function revertPrettyScripts(s) {
    s = s.replace(/([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁽⁾⁼ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂ]+)/g, (_, p1) => "^" + fromSuperscript(p1));
    s = s.replace(/([₀₁₂₃₄₅₆₇₈₉₊₋₍₎₌ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ]+)/g, (_, p1) => "_" + fromSubscript(p1));
    return s;
}

export function toSuperscript(raw) {
    const map = {"0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵","6":"⁶","7":"⁷","8":"⁸","9":"⁹","+":"⁺","-":"⁻","(":"⁽",")":"⁾","=":"⁼","a":"ᵃ","b":"ᵇ","c":"ᶜ","d":"ᵈ","e":"ᵉ","f":"ᶠ","g":"ᵍ","h":"ʰ","i":"ⁱ","j":"ʲ","k":"ᵏ","l":"ˡ","m":"ᵐ","n":"ⁿ","o":"ᵒ","p":"ᵖ","r":"ʳ","s":"ˢ","t":"ᵗ","u":"ᵘ","v":"ᵛ","w":"ʷ","x":"ˣ","y":"ʸ","z":"ᶻ","A":"ᴬ","B":"ᴮ","D":"ᴰ","E":"ᴱ","G":"ᴳ","H":"ᴴ","I":"ᴵ","J":"ᴶ","K":"ᴷ","L":"ᴸ","M":"ᴹ","N":"ᴺ","O":"ᴼ","P":"ᴾ","R":"ᴿ","T":"ᵀ","U":"ᵁ","V":"ⱽ","W":"ᵂ"};
    return String(raw).split("").map(ch => map[ch] || ch).join("");
}

export function toSubscript(raw) {
    const map = {"0":"₀","1":"₁","2":"₂","3":"₃","4":"₄","5":"₅","6":"₆","7":"₇","8":"₈","9":"₉","+":"₊","-":"₋","(":"₍",")":"₎","=":"₌","a":"ₐ","e":"ₑ","h":"ₕ","i":"ᵢ","j":"ⱼ","k":"ₖ","l":"ₗ","m":"ₘ","n":"ₙ","o":"ₒ","p":"ₚ","r":"ᵣ","s":"ₛ","t":"ₜ","u":"ᵤ","v":"ᵥ","x":"ₓ"};
    return String(raw).split("").map(ch => map[ch] || ch).join("");
}

export function fromSuperscript(raw) {
    const map = {"⁰":"0","¹":"1","²":"2","³":"3","⁴":"4","⁵":"5","⁶":"6","⁷":"7","⁸":"8","⁹":"9","⁺":"+","⁻":"-","⁽":"(","⁾":")","⁼":"=","ᵃ":"a","ᵇ":"b","ᶜ":"c","ᵈ":"d","ᵉ":"e","ᶠ":"f","ᵍ":"g","ʰ":"h","ⁱ":"i","ʲ":"j","ᵏ":"k","ˡ":"l","ᵐ":"m","ⁿ":"n","ᵒ":"o","ᵖ":"p","ʳ":"r","ˢ":"s","ᵗ":"t","ᵘ":"u","ᵛ":"v","ʷ":"w","ˣ":"x","ʸ":"y","ᶻ":"z","ᴬ":"A","ᴮ":"B","ᴰ":"D","ᴱ":"E","ᴳ":"G","ᴴ":"H","ᴵ":"I","ᴶ":"J","ᴷ":"K","ᴸ":"L","ᴹ":"M","ᴺ":"N","ᴼ":"O","ᴾ":"P","ᴿ":"R","ᵀ":"T","ᵁ":"U","ⱽ":"V","ᵂ":"W"};
    return String(raw).split("").map(ch => map[ch] || ch).join("");
}

export function fromSubscript(raw) {
    const map = {"₀":"0","₁":"1","₂":"2","₃":"3","₄":"4","₅":"5","₆":"6","₇":"7","₈":"8","₉":"9","₊":"+","₋":"-","₍":"(","₎":")","₌":"=","ₐ":"a","ₑ":"e","ₕ":"h","ᵢ":"i","ⱼ":"j","ₖ":"k","ₗ":"l","ₘ":"m","ₙ":"n","ₒ":"o","ₚ":"p","ᵣ":"r","ₛ":"s","ₜ":"t","ᵤ":"u","ᵥ":"v","ₓ":"x"};
    return String(raw).split("").map(ch => map[ch] || ch).join("");
}

export function hashString(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) {
        h ^= str.charCodeAt(i);
        h = Math.imul(h, 16777619);
    }
    return h >>> 0;
}

export function mulberry32(seed) {
    let t = seed >>> 0;
    return function () {
        t += 0x6D2B79F5;
        let r = Math.imul(t ^ (t >>> 15), 1 | t);
        r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
        return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
}

export function lerp(a, b, t) { return a + (b - a) * t; }

export function copyText(text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
        return;
    }
    fallbackCopy(text);
}

export function fallbackCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (_) {}
    ta.remove();
}

export function tokenizeGlyphTokens(latex) {
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
    const clipped = merged.filter(Boolean).slice(0, 40);
    return clipped.length ? clipped : ["x"];
}
