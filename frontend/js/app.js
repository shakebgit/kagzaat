/**
 * app.js — Kagazat Affidavit Generator Orchestrator
 * Wires all modules: API, State, UI, FormRenderer, TemplateEngine.
 * Zero inline logic — only coordinates the other modules.
 * Exposes window.* globals for any HTML onclick= hooks.
 * Version: 1.0.0
 */

(function () {
    "use strict";

    // ── Init on DOM ready ─────────────────────────────────────
    document.addEventListener("DOMContentLoaded", init);

    async function init() {
        // 1. Identify logged-in user (js/nav.js already handles display;
        //    we just need the user ID for API calls)
        await _loadUser();

        // 2. Load top-level dropdowns
        await _loadStates();
        await _loadDepartments();

        // 3. Load sidebar history
        await _loadHistory();

        // 4. Wire all event listeners
        _bindDropdowns();
        _bindPreview();
        _bindSidebar();
        _bindModal();
        _bindSaveButton();
        _bindNewDraft();

        // 5. Initial UI state
        KagazatUI.setPreviewPlaceholder();
        KagazatUI.setSaveLabel(false);
    }

    // ── Auth — get user id from /check-auth ───────────────────
    async function _loadUser() {
        try {
            const data = await KagazatAPI.checkAuth();
            AppState.setUser(data.id || data.user_id || data.email || "", data.name || data.email || "");
        } catch (_) {
            // js/nav.js will redirect to login; nothing to do here
        }
    }

    // ════════════════════════════════════════════════════════
    //  DROPDOWNS
    // ════════════════════════════════════════════════════════

    async function _loadStates() {
        try {
            const data = await KagazatAPI.getStates();
            KagazatUI.populateSelect("stateSelect", data, "— राज्य चुनें —");
        } catch (e) {
            KagazatUI.showToast("राज्य लोड नहीं हुए: " + e.message, "error");
        }
    }

    async function _loadCities(stateId) {
        KagazatUI.lockSelect("citySelect",  "— लोड हो रहा है... —");
        KagazatUI.lockSelect("courtSelect", "— पहले शहर चुनें —");
        try {
            const data = await KagazatAPI.getCities(stateId);
            KagazatUI.populateSelect("citySelect", data, "— शहर चुनें —");
        } catch (e) {
            KagazatUI.showToast("शहर लोड नहीं हुए: " + e.message, "error");
        }
    }

    async function _loadCourts(stateId) {
        KagazatUI.lockSelect("courtSelect", "— लोड हो रहा है... —");
        try {
            const data = await KagazatAPI.getCourts(stateId);
            KagazatUI.populateSelect("courtSelect", data, "— न्यायालय चुनें —");
        } catch (e) {
            KagazatUI.showToast("न्यायालय लोड नहीं हुए: " + e.message, "error");
        }
    }

    async function _loadDepartments() {
        try {
            const data = await KagazatAPI.getDepartments();
            KagazatUI.populateSelect("departmentSelect", data, "— विभाग चुनें —");
        } catch (e) {
            KagazatUI.showToast("विभाग लोड नहीं हुए: " + e.message, "error");
        }
    }

    async function _loadAffidavitTypes(departmentId) {
        KagazatUI.lockSelect("typeSelect", "— लोड हो रहा है... —");
        try {
            const data = await KagazatAPI.getAffidavitTypes(departmentId);
            KagazatUI.populateSelect("typeSelect", data, "— हलफनामे का प्रकार चुनें —");
        } catch (e) {
            KagazatUI.showToast("हलफनामा प्रकार लोड नहीं हुए: " + e.message, "error");
        }
    }

    // ── Bind cascade: state→city+court, dept→type, type→template ─
    function _bindDropdowns() {
        _on("stateSelect", "change", async function () {
            const stateId = this.value;
            if (!stateId) return;
            AppState.setSelection("stateId", stateId);
            await Promise.all([
                _loadCities(stateId),
                _loadCourts(stateId),
            ]);
            _maybeLoadTemplate();
        });

        _on("citySelect", "change", function () {
            AppState.setSelection("cityId", this.value);
            // City doesn't trigger template — just stored
        });

        _on("courtSelect", "change", function () {
            AppState.setSelection("courtId", this.value);
            _maybeLoadTemplate();
        });

        _on("departmentSelect", "change", async function () {
            const deptId = this.value;
            if (!deptId) return;
            AppState.setSelection("departmentId", deptId);
            KagazatUI.lockSelect("typeSelect", "— लोड हो रहा है... —");
            await _loadAffidavitTypes(deptId);
            _maybeLoadTemplate();
        });

        _on("typeSelect", "change", function () {
            AppState.setSelection("typeId", this.value);
            _maybeLoadTemplate();
        });
    }

    // ── Load template when all 4 keys are selected ────────────
    async function _maybeLoadTemplate() {
        const { stateId, courtId, departmentId, typeId } = AppState.getSelections();
        if (!stateId || !courtId || !departmentId || !typeId) return;

        KagazatUI.setTemplateStatus("loading");

        try {
            const data = await KagazatAPI.getTemplate(stateId, courtId, departmentId, typeId);

            if (!data || !data.html) {
                KagazatUI.setTemplateStatus("not_found");
                FormRenderer.clear();
                KagazatUI.setPreviewPlaceholder();
                return;
            }

            // Parse placeholders
            const placeholders = TemplateEngine.parse(data.html);
            AppState.setTemplate(data.id, data.html, placeholders);
            AppState.clearFormData();
            AppState.setUserEdited(false);

            // Render dynamic form (empty — new draft)
            FormRenderer.render(placeholders, {}, _onFieldChange);

            // Render initial preview (all blanks)
            const rendered = TemplateEngine.render(data.html, {});
            AppState.setAutoHtml(rendered);
            KagazatUI.setPreviewHtml(rendered);
            KagazatUI.showManualEditBadge(false);
            KagazatUI.setTemplateStatus("loaded");
            KagazatUI.setSaveLabel(false);
            AppState.setCurrentAffidavit(null);

        } catch (e) {
            KagazatUI.setTemplateStatus("not_found");
            KagazatUI.showToast("टेम्पलेट लोड नहीं हुई: " + e.message, "error");
        }
    }

    // ── Field change callback from FormRenderer ───────────────
    function _onFieldChange(key, value) {
        if (AppState.get("userEdited")) return; // user has manual control

        AppState.setFormField(key, value);

        const preview = document.getElementById("preview");
        if (!preview) return;

        TemplateEngine.updateField(preview, key, value);

        // Keep autoHtml fresh for reset
        const tpl = AppState.getTemplate();
        if (tpl.html) {
            const fresh = TemplateEngine.render(tpl.html, AppState.getFormData());
            AppState.setAutoHtml(fresh);
        }
    }

    // ════════════════════════════════════════════════════════
    //  PREVIEW — manual edit detection + reset
    // ════════════════════════════════════════════════════════

    function _bindPreview() {
        const preview = document.getElementById("preview");
        if (!preview) return;

        preview.addEventListener("input", function () {
            if (!AppState.get("userEdited")) {
                AppState.setUserEdited(true);
                KagazatUI.showManualEditBadge(true);
            }
        });
    }

    function _resetToAutoPreview() {
        if (!confirm("फ़ॉर्म की जानकारी से प्रीव्यू रीसेट करें?\nआपके मैन्युअल बदलाव हट जाएंगे।")) return;
        AppState.setUserEdited(false);
        KagazatUI.showManualEditBadge(false);
        KagazatUI.setPreviewHtml(AppState.get("autoHtml"));
    }

    // ════════════════════════════════════════════════════════
    //  SAVE → DB → MODAL
    // ════════════════════════════════════════════════════════

    function _bindSaveButton() {
        const btn = document.getElementById("saveAndPrintBtn");
        if (!btn) return;
        btn.addEventListener("click", _handleSave);
    }

    async function _handleSave() {
        const preview = document.getElementById("preview");
        if (!preview) return;

        const text = preview.textContent || preview.innerText || "";
        if (!text.trim() || text.includes("यहाँ आपका")) {
            KagazatUI.showToast("पहले जानकारी भरें और टेम्पलेट चुनें।", "error");
            return;
        }

        const tpl  = AppState.getTemplate();
        const user = AppState.getUser();

        if (!tpl.id) {
            KagazatUI.showToast("कोई टेम्पलेट नहीं चुना गया।", "error");
            return;
        }

        const generatedHtml = TemplateEngine.snapshot(preview);
        const formData      = FormRenderer.readAll(tpl.placeholders);
        const currentId     = AppState.get("currentAffidavitId");
        const isUpdate      = !!currentId;

        KagazatUI.setButtonLoading("saveAndPrintBtn", true, "");

        try {
            let savedId;

            if (isUpdate) {
                await KagazatAPI.updateAffidavit(currentId, {
                    form_data:      formData,
                    generated_html: generatedHtml,
                });
                savedId = currentId;
                KagazatUI.showToast("हलफनामा अपडेट हो गया।", "success");
            } else {
                const res = await KagazatAPI.saveAffidavit({
                    user_id:        user.id,
                    template_id:    tpl.id,
                    form_data:      formData,
                    generated_html: generatedHtml,
                });
                savedId = res.id || res.affidavit_id;
                AppState.setCurrentAffidavit(savedId);
                KagazatUI.setSaveLabel(true);
                KagazatUI.showToast("हलफनामा सहेजा गया।", "success");
            }

            // Refresh sidebar history
            await _loadHistory();
            if (savedId) KagazatUI.setHistoryItemActive(savedId);

            // Open print modal
            KagazatUI.openModal(generatedHtml);

        } catch (e) {
            KagazatUI.showToast("सहेजने में विफल: " + e.message, "error");
        } finally {
            KagazatUI.setButtonLoading("saveAndPrintBtn", false,
                isUpdate ? "💾 अपडेट करें और प्रिंट करें →" : "🖨️ सहेजें और प्रिंट करें →");
        }
    }

    // ════════════════════════════════════════════════════════
    //  HISTORY — sidebar
    // ════════════════════════════════════════════════════════

    async function _loadHistory() {
        const data = AppState.getUser();
        const user = data.id;
        if (!user.id) return;
        try {
            
            const items = await KagazatAPI.getUserAffidavits(user.id);
             
            KagazatUI.renderHistory(items, _loadSavedAffidavit);
        } catch (_) {
            // Sidebar history is non-critical — fail silently
        }
    }

    async function _loadSavedAffidavit(id) {
        try { 
            const data = await KagazatAPI.getAffidavit(id);           
            // Restore dropdown selections silently (set values, no cascade)
            _restoreSelections(data);

            // Restore template
            const placeholders = TemplateEngine.parse(data.template_html);
            AppState.setTemplate(data.template_id, data.template_html, placeholders);
            AppState.setFormData(data.form_data || {});
            AppState.setCurrentAffidavit(id);
            AppState.setUserEdited(false);

            // Re-render form with saved values
            FormRenderer.render(placeholders, data.form_data || {}, _onFieldChange);

            // Render preview
            const rendered = TemplateEngine.render(data.template_html, data.form_data || {});
            AppState.setAutoHtml(rendered);
            KagazatUI.setPreviewHtml(rendered);
            KagazatUI.showManualEditBadge(false);
            KagazatUI.setTemplateStatus("loaded");
            KagazatUI.setSaveLabel(true);

        } catch (e) {
            KagazatUI.showToast("ड्राफ्ट लोड नहीं हुआ: " + e.message, "error");
        }
    }

    // Quietly set dropdown values from saved affidavit metadata
    // (does NOT trigger cascade — avoids re-fetching everything)
    function _restoreSelections(data) {
        const map = {
            stateSelect:      { key: "stateId",      value: data.state_id },
            citySelect:       { key: "cityId",       value: data.city_id },
            courtSelect:      { key: "courtId",      value: data.court_id },
            departmentSelect: { key: "departmentId", value: data.department_id },
            typeSelect:       { key: "typeId",       value: data.type_id },
        };
        Object.entries(map).forEach(([selectId, { key, value }]) => {
            const sel = document.getElementById(selectId);
            if (sel && value) {
                // Add option if not present (history load skips cascade)
                if (!sel.querySelector(`option[value="${value}"]`)) {
                    const opt       = document.createElement("option");
                    opt.value       = value;
                    opt.textContent = data[`${key.replace("Id","_name")}`] || value;
                    sel.appendChild(opt);
                }
                sel.value = value;
                AppState.setSelection(key, value);
            }
        });
    }

    // ════════════════════════════════════════════════════════
    //  NEW DRAFT
    // ════════════════════════════════════════════════════════

    function _bindNewDraft() {
        const btn = document.getElementById("newDraftBtn");
        if (btn) btn.addEventListener("click", _createNewDraft);
    }

    function _createNewDraft() {
        AppState.resetDraft();
        FormRenderer.clear();
        KagazatUI.setPreviewPlaceholder();
        KagazatUI.showManualEditBadge(false);
        KagazatUI.setTemplateStatus("");
        KagazatUI.setSaveLabel(false);

        // Reset all dropdowns to placeholder
        ["stateSelect","citySelect","courtSelect","departmentSelect","typeSelect"].forEach((id) => {
            const sel = document.getElementById(id);
            if (sel) sel.selectedIndex = 0;
        });

        // Deselect history
        document.querySelectorAll(".draft-item").forEach(d =>
            d.classList.remove("active"));
    }

    // ════════════════════════════════════════════════════════
    //  SIDEBAR TOGGLE
    // ════════════════════════════════════════════════════════

    function _bindSidebar() {
        const btn = document.getElementById("sidebarToggle");
        if (btn) btn.addEventListener("click", _toggleSidebar);
    }

    function _toggleSidebar() {
        const next = !AppState.get("sidebarOpen");
        AppState.setSidebarOpen(next);
        KagazatUI.setSidebarState(next);
    }

    // ════════════════════════════════════════════════════════
    //  MODAL — print
    // ════════════════════════════════════════════════════════

       function _bindModal() {
            const modal = document.getElementById("previewModal");
            if (modal) {
                modal.addEventListener("click", function (e) {
                    if (e.target === this) KagazatUI.closeModal();
                });
            }
            _on("downloadPdfBtn", "click", _doDownloadPdf);  // ← add this line
            _on("closeModalBtn",  "click", KagazatUI.closeModal);
            _on("closeModalBtn2", "click", KagazatUI.closeModal);
            _on("printBtn",       "click", _doPrint);
        }

    function _doPrint() {
        const mc = document.getElementById("modalContent");
        if (!mc) return;
        const pa = document.getElementById("printArea");
        if (!pa) return;
        pa.innerHTML      = mc.innerHTML;
        pa.style.display  = "block";
        window.print();
        pa.style.display  = "none";
    }

    // ════════════════════════════════════════════════════════
    //  UTILITIES
    // ════════════════════════════════════════════════════════

    function _on(id, event, fn) {
        const el = document.getElementById(id);
        if (el) el.addEventListener(event, fn);
    }

    // ════════════════════════════════════════════════════════
    //  GLOBALS — for any remaining HTML onclick= attributes
    // ════════════════════════════════════════════════════════
    window.toggleSidebar      = _toggleSidebar;
    window.resetToAutoPreview = _resetToAutoPreview;
    window.closeModal         = KagazatUI.closeModal;
    window.doPrint            = _doPrint;

})();

async function _doDownloadPdf() {
    const btn = document.getElementById("downloadPdfBtn");
    const mc  = document.getElementById("modalContent");
    if (!mc) return;

    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "PDF बन रही है...";

    try {
        const res = await fetch(KagazatAPI.BASE + "/generate_pdf", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ html: mc.innerHTML }),
        });

        if (!res.ok) {
            const text = await res.text();
            throw new Error(text);
        }

        // 🔥 KEY CHANGE: use blob instead of json
        const blob = await res.blob();

        const url = window.URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = "affidavit.pdf";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        window.URL.revokeObjectURL(url);

        KagazatUI.showToast("PDF डाउनलोड हो रही है!", "success");

    } catch (e) {
        KagazatUI.showToast("PDF Error: " + e.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}