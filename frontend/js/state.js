/**
 * state.js — Kagazat Global State
 * Single source of truth for all runtime data.
 * No module stores its own state — everything lives here.
 * Version: 1.0.0
 */

const AppState = (function () {
    "use strict";

    const _state = {
        // ── Auth ─────────────────────────────────────────────
        user: {
            id:   null,
            name: null,
        },

        // ── Dropdown selections ───────────────────────────────
        selections: {
            stateId:      null,
            cityId:       null,
            courtId:      null,
            departmentId: null,
            typeId:       null,
        },

        // ── Active template from DB ───────────────────────────
        template: {
            id:           null,     // template_id from DB
            html:         null,     // raw HTML string with {{placeholders}}
            placeholders: [],       // ['name', 'father_name', 'address', ...]
        },

        // ── Form data — keyed by placeholder name ─────────────
        // e.g. { name: 'राम कुमार', address: 'प्रयागराज' }
        formData: {},

        // ── Affidavit being edited (null = new) ───────────────
        currentAffidavitId: null,

        // ── Preview state ─────────────────────────────────────
        userEdited:  false,   // true once user manually types in #preview
        autoHtml:    '',      // last engine-generated HTML (for reset)

        // ── UI ────────────────────────────────────────────────
        sidebarOpen: true,
    };

    // ── Getters ───────────────────────────────────────────────
    function get(key) {
        return _state[key];
    }

    function getUser()       { return _state.user; }
    function getSelections() { return _state.selections; }
    function getTemplate()   { return _state.template; }
    function getFormData()   { return _state.formData; }

    // ── Setters ───────────────────────────────────────────────
    function setUser(id, name) {
        _state.user.id   = id;
        _state.user.name = name;
    }

    function setSelection(key, value) {
        // key: 'stateId' | 'cityId' | 'courtId' | 'departmentId' | 'typeId'
        _state.selections[key] = value;
    }

    function setTemplate(id, html, placeholders) {
        _state.template.id           = id;
        _state.template.html         = html;
        _state.template.placeholders = placeholders;
    }

    function setFormField(key, value) {
        _state.formData[key] = value;
    }

    function setFormData(obj) {
        _state.formData = { ...obj };
    }

    function clearFormData() {
        _state.formData = {};
    }

    function setCurrentAffidavit(id) {
        _state.currentAffidavitId = id;
    }

    function setUserEdited(val) {
        _state.userEdited = val;
    }

    function setAutoHtml(html) {
        _state.autoHtml = html;
    }

    function setSidebarOpen(val) {
        _state.sidebarOpen = val;
    }

    // ── Reset — back to blank new draft ──────────────────────
    function resetDraft() {
        _state.template             = { id: null, html: null, placeholders: [] };
        _state.formData             = {};
        _state.currentAffidavitId   = null;
        _state.userEdited           = false;
        _state.autoHtml             = '';
        _state.selections           = {
            stateId: null, cityId: null,
            courtId: null, departmentId: null, typeId: null,
        };
    }

    return {
        get,
        getUser,
        getSelections,
        getTemplate,
        getFormData,
        setUser,
        setSelection,
        setTemplate,
        setFormField,
        setFormData,
        clearFormData,
        setCurrentAffidavit,
        setUserEdited,
        setAutoHtml,
        setSidebarOpen,
        resetDraft,
    };
})();
