/**
 * ui.js — Kagazat DOM Layer
 * All DOM reads and writes live here.
 * No business logic — only rendering and user feedback.
 * Version: 1.0.0
 */

const KagazatUI = (function () {
    "use strict";

    // ── Toast notification ────────────────────────────────────
    // Creates a self-dismissing toast. type: 'success' | 'error' | 'info'
    function showToast(message, type = "info") {
        let container = document.getElementById("toastContainer");
        if (!container) {
            container = document.createElement("div");
            container.id = "toastContainer";
            container.style.cssText =
                "position:fixed;bottom:24px;right:24px;z-index:9999;" +
                "display:flex;flex-direction:column;gap:8px;";
            document.body.appendChild(container);
        }

        const colors = {
            success: { bg: "#16a34a", icon: "✓" },
            error:   { bg: "#dc2626", icon: "✕" },
            info:    { bg: "#2563eb", icon: "ℹ" },
        };
        const { bg, icon } = colors[type] || colors.info;

        const toast = document.createElement("div");
        toast.style.cssText =
            `background:${bg};color:#fff;padding:12px 18px;border-radius:8px;` +
            `font-size:0.9rem;display:flex;align-items:center;gap:10px;` +
            `box-shadow:0 4px 12px rgba(0,0,0,0.2);max-width:320px;` +
            `animation:slideIn 0.2s ease;`;
        toast.innerHTML = `<span style="font-weight:700;">${icon}</span><span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transition = "opacity 0.3s";
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    // ── Button loading state ──────────────────────────────────
    function setButtonLoading(btnId, isLoading, originalText) {
        const btn = document.getElementById(btnId);
        if (!btn) return;
        btn.disabled       = isLoading;
        btn.textContent    = isLoading ? "लोड हो रहा है..." : originalText;
        btn.style.opacity  = isLoading ? "0.7" : "1";
        btn.style.cursor   = isLoading ? "wait" : "";
    }

    // ── Dropdown population ───────────────────────────────────
    // items: [{ id, name }]
    function populateSelect(selectId, items, placeholder) {
        const sel = document.getElementById(selectId);
        if (!sel) return;
        sel.innerHTML = `<option value="">${placeholder}</option>`;
        items.forEach(({ id, name }) => {
            const opt = document.createElement("option");
            opt.value       = id;
            opt.textContent = name;
            sel.appendChild(opt);
        });
        sel.disabled = items.length === 0;
    }

    function lockSelect(selectId, placeholderText) {
        const sel = document.getElementById(selectId);
        if (!sel) return;
        sel.innerHTML = `<option value="">${placeholderText}</option>`;
        sel.disabled  = true;
    }

    // ── Sidebar toggle ────────────────────────────────────────
    function setSidebarState(isOpen) {
        const sidebar = document.getElementById("sidebar");
        const toggle  = document.getElementById("sidebarToggle");
        if (!sidebar) return;
        sidebar.classList.toggle("collapsed", !isOpen);
        if (toggle) toggle.setAttribute("aria-expanded", isOpen);
    }

    // ── Mobile menu ───────────────────────────────────────────
    function toggleMobileMenu() {
        const menu = document.getElementById("mobileMenu");
        if (!menu) return;
        const hidden = menu.classList.contains("hidden");
        menu.classList.toggle("hidden", !hidden);
    }

    // ── Sidebar history list ──────────────────────────────────
    // items: [{ id, title, created_at }]
    function renderHistory(items, onClickFn) {
        const list = document.getElementById("historyList");
        if (!list) return;
         if (!items || items.length === 0) {
            list.innerHTML =
                `<p style="font-size:0.85rem;color:#9ca3af;padding:8px 4px;">
                    कोई पुराना ड्राफ्ट नहीं मिला।
                 </p>`;
            return;
        }

        list.innerHTML = "";
        items.forEach((item) => {
            const div = document.createElement("div");
            div.className        = "draft-item";
            div.dataset.id       = item.id;
            const dateStr = item.created_at
                ? new Date(item.created_at).toLocaleDateString("hi-IN",
                    { day: "numeric", month: "short" })
                : "";
            div.innerHTML =
                `<div style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                    ${item.title || "हलफनामा"}
                 </div>
                 <div style="font-size:0.78rem;color:#9ca3af;margin-top:2px;">${dateStr}</div>`;
            div.addEventListener("click", () => {
                // Mark active
                list.querySelectorAll(".draft-item").forEach(d =>
                    d.classList.remove("active"));
                div.classList.add("active");
                onClickFn(item.id);
            });
            list.appendChild(div);
        });
    }

    function setHistoryItemActive(id) {
        document.querySelectorAll(".draft-item").forEach((d) => {
            d.classList.toggle("active", d.dataset.id === String(id));
        });
    }

    // ── Preview panel ─────────────────────────────────────────
    function setPreviewHtml(html) {
        const el = document.getElementById("preview");
        if (!el) return;
        el.innerHTML           = html;
        el.classList.remove("placeholder");
        el.style.color         = "#111";
        el.contentEditable     = "true";
        el.dataset.userEdited  = "false";
        // Show chrome
        _showPreviewChrome(true);
    }

    function setPreviewPlaceholder() {
        const el = document.getElementById("preview");
        if (!el) return;
        el.textContent       = "यहाँ आपका हलफनामा दिखाई देगा...\n\nजानकारी भरने के बाद यह स्वतः अपडेट होता रहेगा।";
        el.style.color       = "#9ca3af";
        el.contentEditable   = "false";
        el.classList.add("placeholder");
        _showPreviewChrome(false);
    }

    function _showPreviewChrome(show) {
        const ids = ["editBadge", "editHint", "pencilHint"];
        ids.forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.style.display = show ? (id === "editBadge" ? "inline-flex" : "flex") : "none";
        });
        // pencilHint uses block
        const ph = document.getElementById("pencilHint");
        if (ph) ph.style.display = show ? "block" : "none";
    }

    function showManualEditBadge(show) {
        const badge   = document.getElementById("manualBadge");
        const resetBtn = document.getElementById("resetBtn");
        if (badge)    badge.style.display    = show ? "inline-flex" : "none";
        if (resetBtn) resetBtn.style.display = show ? "inline-block" : "none";
    }

    // ── Template loading indicator inside filter card ─────────
    function setTemplateStatus(status) {
        // status: 'loading' | 'loaded' | 'not_found' | ''
        let el = document.getElementById("templateStatus");
        if (!el) {
            el = document.createElement("div");
            el.id = "templateStatus";
            el.style.cssText =
                "font-size:0.8rem;margin-top:8px;padding:6px 10px;" +
                "border-radius:6px;display:none;";
            const filterCard = document.getElementById("filterCard");
            if (filterCard) filterCard.appendChild(el);
        }
        const map = {
            loading:   { text: "⏳ टेम्पलेट लोड हो रहा है...", bg: "#fffbeb", color: "#78350f" },
            loaded:    { text: "✓ टेम्पलेट तैयार है — जानकारी भरें", bg: "#f0fdf4", color: "#15803d" },
            not_found: { text: "⚠️ इस संयोजन के लिए टेम्पलेट उपलब्ध नहीं है।", bg: "#fef2f2", color: "#991b1b" },
            "":        null,
        };
        const cfg = map[status];
        if (!cfg) { el.style.display = "none"; return; }
        el.textContent    = cfg.text;
        el.style.background = cfg.bg;
        el.style.color      = cfg.color;
        el.style.display    = "block";
    }

    // ── Modal ─────────────────────────────────────────────────
    function openModal(htmlContent) {
        const mc = document.getElementById("modalContent");
        const m  = document.getElementById("previewModal");
        if (!mc || !m) return;
        mc.innerHTML = htmlContent;
        m.classList.add("open");
    }

    function closeModal() {
        const m = document.getElementById("previewModal");
        if (m) m.classList.remove("open");
    }

    // ── Save button label (new vs update) ─────────────────────
    function setSaveLabel(isUpdate) {
        const btn = document.getElementById("saveAndPrintBtn");
        if (!btn) return;
        btn.textContent = isUpdate
            ? "💾 अपडेट करें और प्रिंट करें →"
            : "🖨️ सहेजें और प्रिंट करें →";
    }

    return {
        showToast,
        setButtonLoading,
        populateSelect,
        lockSelect,
        setSidebarState,
        toggleMobileMenu,
        renderHistory,
        setHistoryItemActive,
        setPreviewHtml,
        setPreviewPlaceholder,
        showManualEditBadge,
        setTemplateStatus,
        openModal,
        closeModal,
        setSaveLabel,
    };
})();
