/**
 * templateEngine.js — Kagazat Template Engine
 * Parses {{placeholder}} tokens from DB template HTML.
 * Performs live substitution as the user types.
 * Version: 1.0.0
 */

const TemplateEngine = (function () {
    "use strict";

    // ── Parse ─────────────────────────────────────────────────
    // Extracts all unique {{key}} tokens from a template string.
    // Returns array of unique key strings e.g. ['name','address','date']
    function parse(templateHtml) {
        const regex = /\{\{(\w+)\}\}/g;
        const keys  = new Set();
        let match;
        while ((match = regex.exec(templateHtml)) !== null) {
            keys.add(match[1]);
        }
        return Array.from(keys);
    }

    // ── Render ────────────────────────────────────────────────
    // Replaces all {{key}} tokens with values from formData object.
    // Keys with no value get a styled blank span so user can see what's missing.
    function render(templateHtml, formData) {
        return templateHtml.replace(/\{\{(\w+)\}\}/g, (_, key) => {
            const val = (formData[key] || "").trim();
            if (val) {
                return `<span class="tpl-value" data-key="${key}">${val}</span>`;
            }
            // Empty — show a blank underline so the user sees the gap
            return `<span class="tpl-blank" data-key="${key}">________</span>`;
        });
    }

    // ── Live update ───────────────────────────────────────────
    // Called on every field input event.
    // Re-renders only the specific span for the changed key —
    // avoids full innerHTML replacement (preserves scroll position).
    function updateField(previewEl, key, value) {
        const spans = previewEl.querySelectorAll(`[data-key="${key}"]`);
        spans.forEach((span) => {
            if (value && value.trim()) {
                span.textContent = value.trim();
                span.className   = "tpl-value";
            } else {
                span.textContent = "________";
                span.className   = "tpl-blank";
            }
        });
    }

    // ── Snapshot ──────────────────────────────────────────────
    // Returns the final HTML for saving to DB (strips the data-key spans,
    // replaces them with plain text values).
    function snapshot(previewEl) {
        // Clone so we don't mutate the live DOM
        const clone = previewEl.cloneNode(true);
        clone.querySelectorAll("[data-key]").forEach((span) => {
            const text = document.createTextNode(span.textContent);
            span.replaceWith(text);
        });
        return clone.innerHTML;
    }

    return { parse, render, updateField, snapshot };
})();
