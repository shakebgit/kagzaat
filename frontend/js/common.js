/**
 * common.js — Kagazat Shared Config
 * Load this FIRST on every page — before nav.js, api.js, or any inline script.
 * Provides API_URL globally so no page needs to define it.
 */
const API_URL =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1"
        ? "http://127.0.0.1:5000"
        : "";