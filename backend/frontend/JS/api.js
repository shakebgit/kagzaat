/**
 * api.js — Kagazat API Layer
 * All fetch() calls live here. No other file talks to the backend directly.
 * Version: 1.0.0
 */

const KagazatAPI = (function () {
    "use strict";

    const BASE =
        window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1"
            ? "http://127.0.0.1:5000"
            : "";

    // ── Core fetch wrapper ────────────────────────────────────
    async function request(method, path, body = null) {
        const opts = {
            method,
            credentials: "include",
            headers: {},
        };
        if (body) {
            opts.headers["Content-Type"] = "application/json";
            opts.body = JSON.stringify(body);
        }
        const res = await fetch(BASE + path, opts);
        if (!res.ok) {
            let msg = `HTTP ${res.status}`;
            try { const d = await res.json(); msg = d.message || d.error || msg; } catch (_) {}
            throw new Error(msg);
        }
        return res.json();
    }

    // ── Location ──────────────────────────────────────────────
    function getStates() {
        return request("GET", "/states");
    }

    function getCities(stateId) {
        return request("GET", `/cities?state_id=${stateId}`);
    }

    // ── Lookup dropdowns ──────────────────────────────────────
    function getCourts(stateId) {
        return request("GET", `/courts?state_id=${stateId}`);
    }

    function getDepartments() {
        return request("GET", "/departments");
    }

    function getAffidavitTypes(departmentId) {
        return request("GET", `/affidavit-types?department_id=${departmentId}`);
    }

    // ── Template ──────────────────────────────────────────────
    function getTemplate(stateId, courtId, departmentId, typeId) {
        const q = new URLSearchParams({
            state_id:      stateId,
            court_id:      courtId,
            department_id: departmentId,
            type_id:       typeId,
        });
        return request("GET", `/template?${q}`);
    }

    // ── Affidavit CRUD ────────────────────────────────────────
    function saveAffidavit(payload) {
        // payload: { user_id, template_id, form_data, generated_html }
        return request("POST", "/affidavit/save", payload);
    }

    function getUserAffidavits(userId) {
        return request("GET", `/affidavit/user/${userId}`);
    }

    function getAffidavit(id) {
        return request("GET", `/affidavit/${id}`);
    }

    function updateAffidavit(id, payload) {
        return request("PUT", `/affidavit/update/${id}`, payload);
    }

    // ── Auth (read-only — writes stay in nav.js) ─────────────
    function checkAuth() {
        return request("GET", "/check-auth");
    }

    return {
        BASE,
        getStates,
        getCities,
        getCourts,
        getDepartments,
        getAffidavitTypes,
        getTemplate,
        saveAffidavit,
        getUserAffidavits,
        getAffidavit,
        updateAffidavit,
        checkAuth,
    };
})();
