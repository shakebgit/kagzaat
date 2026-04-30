/**
 * nav.js  –  Kagazat Shared Navigation Module
 * Version : 2.2.0  (all fixes applied)
 *
 * KEY FIXES:
 *  - showLoggedOut() called IMMEDIATELY before fetch — guest buttons always visible on load
 *  - showLoggedIn() sets display correctly for both <a> and <div> elements
 *  - Dropdown: display:none/block only — no opacity/visibility conflict
 *  - No rogue redirects — page-level auth guards stay in each page
 *  - toggleMobileMenu exposed on window for onclick= attributes
 */

const KagazatNav = (function () {
    "use strict";

    const API_URL =
        window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1"
            ? "http://127.0.0.1:5000"
            : '';

    // ── Helpers ──────────────────────────────────────────────
    function getInitials(name) {
        if (!name) return "?";
        return name
            .trim()
            .split(/\s+/)
            .slice(0, 2)
            .map((w) => w[0].toUpperCase())
            .join("");
    }

    // ── Auth state rendering ──────────────────────────────────
    function showLoggedIn(name) {
        // Hide all guest elements
        document.querySelectorAll(".nav-guest").forEach((el) => {
            el.style.display = "none";
        });
        // Show all auth elements with correct display type
        document.querySelectorAll(".nav-auth").forEach((el) => {
            // div needs "block", inline <a> needs "" (inherits)
            el.style.display = el.tagName === "DIV" ? "block" : "";
        });
        // Fill initials in avatar circles
        document.querySelectorAll(".nav-avatar-initials").forEach((el) => {
            el.textContent = getInitials(name);
        });
        // Fill name in all name slots
        document.querySelectorAll(".nav-user-name").forEach((el) => {
            el.textContent = name || "My Account";
        });
    }

    function showLoggedOut() {
        // Show guest elements — restore natural display
        document.querySelectorAll(".nav-guest").forEach((el) => {
            el.style.display = "";
        });
        // Hide all auth elements
        document.querySelectorAll(".nav-auth").forEach((el) => {
            el.style.display = "none";
        });
    }

    // ── Dropdown ──────────────────────────────────────────────
    function initDropdown() {
    const trigger  = document.getElementById("navAvatarTrigger");
    const dropdown = document.getElementById("navDropdown");
    if (!trigger || !dropdown) return;

    // Click: toggle for mobile / keyboard users
    trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        const isVisible = dropdown.style.display === "block";
        dropdown.style.display = isVisible ? "none" : "block";
    });

    // Close on outside click
    document.addEventListener("click", (e) => {
        if (!trigger.contains(e.target)) {
            dropdown.style.display = "none";
        }
    });
    }

    // ── Logout ────────────────────────────────────────────────
    async function handleLogout() {
        try {
            await fetch(API_URL + "/logout", {
                method: "POST",
                credentials: "include",
            });
        } catch (_) {
            // network error — still redirect
        } finally {
            window.location.href = "login.html";
        }
    }

    // ── Mobile menu ───────────────────────────────────────────
    function toggleMobileMenu() {
        const menu = document.getElementById("mobileMenu");
        if (menu) menu.classList.toggle("hidden");
    }

    // ── Init ──────────────────────────────────────────────────
    async function init() {
        // CRITICAL: show guest state immediately — do NOT wait for network
        // This ensures Login/Register buttons are always visible on load
        showLoggedOut();

        try {
            const res = await fetch(API_URL + "/check-auth", {
                credentials: "include",
            });
            if (res.ok) {
                const data = await res.json();
                showLoggedIn(data.name || data.email || "");
            }
            // If not ok — showLoggedOut already called, nothing to do
        } catch (_) {
            // Network error — guest state already shown, nothing to do
        }

        initDropdown();
    }

    return { API_URL, init, handleLogout, toggleMobileMenu };
})();

// Auto-init on DOM ready
document.addEventListener("DOMContentLoaded", KagazatNav.init);

// Expose for onclick= attributes in HTML
window.handleLogout      = KagazatNav.handleLogout;
window.toggleMobileMenu  = KagazatNav.toggleMobileMenu;
