/**
 * formRenderer.js — Kagazat Dynamic Form Builder
 * Reads {{placeholder}} keys → generates labelled input fields.
 * Container is fixed height; content scrolls inside.
 * Calls onChangeFn(key, value) on every input event.
 * Version: 1.0.0
 */

const FormRenderer = (function () {
    "use strict";

    // ── Field metadata ────────────────────────────────────────
    // Maps placeholder key → human-readable Hindi label + input type.
    // Unknown keys fall back to a sensible default.
    const FIELD_META = {
        name:           { label: "पूरा नाम",                   type: "text",     placeholder: "जैसे: राम कुमार शर्मा" },
        full_name:      { label: "पूरा नाम",                   type: "text",     placeholder: "जैसे: राम कुमार शर्मा" },
        father_name:    { label: "पिता / पति का नाम",          type: "text",     placeholder: "जैसे: मोहन लाल शर्मा" },
        mother_name:    { label: "माता का नाम",                type: "text",     placeholder: "जैसे: सुमन देवी" },
        husband_name:   { label: "पति का नाम",                 type: "text",     placeholder: "" },
        age:            { label: "आयु (वर्ष)",                 type: "number",   placeholder: "जैसे: 35" },
        dob:            { label: "जन्म तिथि",                  type: "date",     placeholder: "" },
        gender:         { label: "लिंग",                       type: "select",   options: ["पुरुष","महिला","अन्य"] },
        address:        { label: "पूरा पता",                   type: "textarea", placeholder: "मकान नंबर, मोहल्ला, शहर, जिला, पिनकोड" },
        current_address:{ label: "वर्तमान पता",                type: "textarea", placeholder: "" },
        permanent_address:{ label:"स्थायी पता",                type: "textarea", placeholder: "" },
        mobile:         { label: "मोबाइल नंबर",               type: "tel",      placeholder: "10 अंकों का मोबाइल नंबर" },
        email:          { label: "ईमेल",                       type: "email",    placeholder: "" },
        aadhaar:        { label: "आधार के अंतिम 4 अंक",       type: "text",     placeholder: "XXXX" },
        pan:            { label: "PAN नंबर",                   type: "text",     placeholder: "ABCDE1234F" },
        current_name:   { label: "वर्तमान नाम",               type: "text",     placeholder: "" },
        new_name:       { label: "नया नाम",                    type: "text",     placeholder: "" },
        old_name:       { label: "पुराना नाम",                 type: "text",     placeholder: "" },
        reason:         { label: "कारण",                       type: "textarea", placeholder: "" },
        purpose:        { label: "उद्देश्य",                   type: "textarea", placeholder: "" },
        vehicle_number: { label: "वाहन संख्या",                type: "text",     placeholder: "जैसे: UP70AB1234" },
        property_address:{ label:"संपत्ति का पता",             type: "textarea", placeholder: "" },
        date:           { label: "दिनांक",                    type: "date",     placeholder: "" },
        doc_date:       { label: "दस्तावेज़ दिनांक",          type: "date",     placeholder: "" },
        place:          { label: "स्थान",                      type: "text",     placeholder: "जैसे: प्रयागराज" },
        witness_name:   { label: "गवाह का नाम",               type: "text",     placeholder: "" },
        court_name:     { label: "न्यायालय का नाम",           type: "text",     placeholder: "" },
        notary_name:    { label: "नोटरी का नाम",              type: "text",     placeholder: "" },
    };

    function _getMeta(key) {
        return FIELD_META[key] || {
            label:       key.replace(/_/g, " "),
            type:        "text",
            placeholder: "",
        };
    }

    // ── Build one field element ───────────────────────────────
    function _buildField(key, meta, currentValue, onChangeFn) {
        const wrapper = document.createElement("div");
        wrapper.className = "form-field-wrap";

        // Label
        const label       = document.createElement("label");
        label.htmlFor     = `field_${key}`;
        label.textContent = meta.label;
        label.style.cssText =
            "font-size:0.85rem;color:#6b7280;display:block;margin-bottom:4px;font-weight:500;";

        let input;

        if (meta.type === "textarea") {
            input          = document.createElement("textarea");
            input.rows     = 2;
            input.style.resize = "vertical";
        } else if (meta.type === "select") {
            input = document.createElement("select");
            const blank = document.createElement("option");
            blank.value       = "";
            blank.textContent = "— चुनें —";
            input.appendChild(blank);
            (meta.options || []).forEach((opt) => {
                const o       = document.createElement("option");
                o.value       = opt;
                o.textContent = opt;
                input.appendChild(o);
            });
        } else {
            input      = document.createElement("input");
            input.type = meta.type;
        }

        input.id          = `field_${key}`;
        input.className   = "field";
        input.placeholder = meta.placeholder || "";
        if (currentValue) input.value = currentValue;

        // Fire on every keystroke / change
        input.addEventListener("input",  () => onChangeFn(key, input.value));
        input.addEventListener("change", () => onChangeFn(key, input.value));

        // Auto-set today's date for date fields if empty
        if (meta.type === "date" && !currentValue) {
            input.value = new Date().toISOString().split("T")[0];
            // Notify so state and preview are in sync from the start
            onChangeFn(key, input.value);
        }

        wrapper.appendChild(label);
        wrapper.appendChild(input);
        return wrapper;
    }

    // ── Public: render ────────────────────────────────────────
    // placeholders : string[] from TemplateEngine.parse()
    // savedData    : {} existing values when loading a saved affidavit
    // onChangeFn   : (key, value) => void
    function render(placeholders, savedData, onChangeFn) {
        const container = document.getElementById("dynamicFormFields");
        if (!container) return;

        container.innerHTML = "";

        if (!placeholders || placeholders.length === 0) {
            container.innerHTML =
                `<p style="color:#9ca3af;font-size:0.875rem;padding:8px 0;">
                    इस टेम्पलेट में कोई फ़ील्ड नहीं है।
                 </p>`;
            return;
        }

        // Grid wrapper — 2 columns, auto-adjusts
        const grid = document.createElement("div");
        grid.style.cssText =
            "display:grid;grid-template-columns:1fr 1fr;gap:12px;";

        placeholders.forEach((key) => {
            const meta    = _getMeta(key);
            const current = (savedData || {})[key] || "";
            const field   = _buildField(key, meta, current, onChangeFn);

            // Textarea and wide fields span full width
            if (meta.type === "textarea" || meta.type === "email") {
                field.style.gridColumn = "1 / -1";
            }

            grid.appendChild(field);
        });

        container.appendChild(grid);
    }

    // ── Public: read all values ───────────────────────────────
    // Returns { key: value } for every rendered field
    function readAll(placeholders) {
        const data = {};
        (placeholders || []).forEach((key) => {
            const el = document.getElementById(`field_${key}`);
            if (el) data[key] = el.value;
        });
        return data;
    }

    // ── Public: clear ─────────────────────────────────────────
    function clear() {
        const container = document.getElementById("dynamicFormFields");
        if (container) container.innerHTML = "";
    }

    return { render, readAll, clear };
})();
