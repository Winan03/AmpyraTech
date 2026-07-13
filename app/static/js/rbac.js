(function () {
    const LOGIN_URL = "/login";
    const TERMS_URL = "/terms";
    const ROLE_LABELS = {
        admin: "Admin / Custodio",
        auditor: "Direccion",
    };
    const ROLE_HOME = {
        admin: "/",
        auditor: "/schedule",
    };

    function getToken() {
        return localStorage.getItem("safyraToken");
    }

    function getAuthHeader() {
        const token = getToken();
        return { "Authorization": `Bearer ${token}` };
    }

    function clearSession() {
        localStorage.removeItem("safyraToken");
        localStorage.removeItem("safyraAuthProvider");
        localStorage.removeItem("safyraRole");
        localStorage.removeItem("safyraUsername");
    }

    function logout() {
        clearSession();
        window.location.href = LOGIN_URL;
    }

    function getTokenOrRedirect() {
        const token = getToken();
        if (!token) {
            window.location.href = LOGIN_URL;
        }
        return token;
    }

    function normalizeRoles(roles) {
        if (Array.isArray(roles)) {
            return roles;
        }
        return String(roles || "")
            .split(",")
            .map((role) => role.trim().toLowerCase())
            .filter(Boolean);
    }

    function hasAnyRole(user, roles) {
        if (!user) {
            return false;
        }
        return normalizeRoles(roles).includes(String(user.role || "").toLowerCase());
    }

    function roleHome(role) {
        return ROLE_HOME[role] || "/";
    }

    function buildTermsUrl(nextPath) {
        const next = nextPath || `${window.location.pathname}${window.location.search}`;
        return `${TERMS_URL}?next=${encodeURIComponent(next)}`;
    }

    async function fetchCurrentUser() {
        getTokenOrRedirect();
        const response = await fetch("/users/me", { headers: getAuthHeader() });
        if (response.status === 401) {
            logout();
            return null;
        }
        if (!response.ok) {
            throw new Error("No se pudo validar el usuario actual");
        }
        return response.json();
    }

    async function fetchConsentStatus() {
        const response = await fetch("/consent/status", { headers: getAuthHeader() });
        if (response.status === 401) {
            logout();
            return null;
        }
        if (!response.ok) {
            throw new Error("No se pudo validar el consentimiento vigente");
        }
        return response.json();
    }

    async function ensureTermsAccepted() {
        if (window.location.pathname === TERMS_URL) {
            return true;
        }

        const status = await fetchConsentStatus();
        if (!status) {
            return false;
        }
        if (status.requires_acceptance && !status.accepted) {
            window.location.href = buildTermsUrl();
            return false;
        }
        return true;
    }

    function applyRoleUI(user) {
        if (!user) {
            return;
        }

        user.role = String(user.role || "").toLowerCase();
        localStorage.setItem("safyraRole", user.role);
        localStorage.setItem("safyraUsername", user.username);

        document.querySelectorAll("[data-role-badge]").forEach((element) => {
            element.textContent = ROLE_LABELS[user.role] || user.role;
            element.title = user.email || user.username;
        });

        document.querySelectorAll("[data-user-label]").forEach((element) => {
            element.textContent = user.full_name || user.email || user.username;
        });

        document.querySelectorAll("[data-roles]").forEach((element) => {
            const visible = hasAnyRole(user, element.getAttribute("data-roles"));
            element.hidden = !visible;
            element.style.display = visible ? "" : "none";
            element.setAttribute("aria-hidden", visible ? "false" : "true");
        });
    }

    function renderAccessDenied(allowedRoles) {
        const container = document.querySelector(".container") || document.body;
        const roles = normalizeRoles(allowedRoles)
            .map((role) => ROLE_LABELS[role] || role)
            .join(", ");
        container.innerHTML = `
            <section style="
                max-width: 760px;
                margin: 12vh auto;
                padding: 32px;
                border: 1px solid rgba(255,255,255,.14);
                border-radius: 18px;
                background: rgba(21,25,50,.92);
                color: #fff;
                box-shadow: 0 8px 32px rgba(0,245,255,.14);
            ">
                <h1 style="font-size: 1.7rem; margin-bottom: 12px;">Acceso no autorizado</h1>
                <p style="color: #a8b2d1; line-height: 1.6;">
                    Tu rol no tiene permisos para esta vista. Roles permitidos: ${roles}.
                </p>
                <button onclick="SafyraAuth.goHome()" style="
                    margin-top: 22px;
                    padding: 12px 18px;
                    border: 0;
                    border-radius: 10px;
                    cursor: pointer;
                    font-weight: 700;
                    color: #0a0e27;
                    background: #00f5ff;
                ">Ir a mi vista principal</button>
            </section>
        `;
    }

    async function requireRoles(allowedRoles, options) {
        const config = options || {};
        const user = await fetchCurrentUser();
        if (!user) {
            return null;
        }

        applyRoleUI(user);
        const termsAccepted = await ensureTermsAccepted();
        if (!termsAccepted) {
            return null;
        }

        if (hasAnyRole(user, allowedRoles)) {
            return user;
        }

        const target = (config.redirectByRole && config.redirectByRole[user.role]) || roleHome(user.role);
        if (config.redirect !== false && target && window.location.pathname !== target) {
            window.location.href = target;
            return null;
        }

        renderAccessDenied(allowedRoles);
        return null;
    }

    function handleProtectedResponse(response) {
        if (response.status === 401) {
            logout();
            return true;
        }
        if (response.status === 403) {
            response.clone().json().then((data) => {
                if (String(data.detail || "").toLowerCase().includes("terminos")) {
                    window.location.href = buildTermsUrl();
                    return;
                }
                renderAccessDenied([]);
            }).catch(() => renderAccessDenied([]));
            return true;
        }
        return false;
    }

    function goHome() {
        const role = localStorage.getItem("safyraRole");
        window.location.href = roleHome(role);
    }

    // ==========================================================
    // FLOATING ACCESSIBILITY WIDGET (WCAG Compliance)
    // ==========================================================
    function initAccessibility() {
        // 1. Inject Styles
        const style = document.createElement("style");
        style.textContent = `
            .safyra-acc-widget {
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 99999;
                display: flex;
                flex-direction: column-reverse;
                align-items: flex-end;
                gap: 10px;
                font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            .safyra-acc-btn {
                width: 50px;
                height: 50px;
                border-radius: 50%;
                background: #00f5ff;
                color: #0a0e27;
                border: 2px solid #ffffff;
                cursor: pointer;
                box-shadow: 0 6px 20px rgba(0, 245, 255, 0.45);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            }
            .safyra-acc-btn:hover {
                transform: scale(1.15) rotate(15deg);
                box-shadow: 0 8px 24px rgba(0, 245, 255, 0.6);
            }
            .safyra-acc-menu {
                display: none;
                flex-direction: column;
                gap: 8px;
                background: rgba(10, 14, 39, 0.96);
                border: 1px solid rgba(0, 245, 255, 0.3);
                border-radius: 14px;
                padding: 14px;
                box-shadow: 0 12px 40px rgba(0, 0, 0, 0.7);
                backdrop-filter: blur(10px);
                width: 210px;
                animation: slideUpAcc 0.25s ease-out;
            }
            @keyframes slideUpAcc {
                from { transform: translateY(15px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            .safyra-acc-menu.active {
                display: flex;
            }
            .safyra-acc-title {
                color: #00f5ff;
                font-size: 13px;
                font-weight: 700;
                margin-bottom: 6px;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                border-bottom: 1px solid rgba(0, 245, 255, 0.2);
                padding-bottom: 4px;
            }
            .safyra-acc-item {
                padding: 9px 12px;
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.05);
                color: #ffffff;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
                border: 1px solid transparent;
                text-align: left;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            .safyra-acc-item:hover {
                background: rgba(0, 245, 255, 0.15);
                border-color: rgba(0, 245, 255, 0.4);
                color: #00f5ff;
            }
            .safyra-acc-item.selected {
                background: rgba(0, 245, 255, 0.25);
                border-color: #00f5ff;
                color: #00f5ff;
            }
            .safyra-acc-item.selected::after {
                content: "✓";
                font-weight: 700;
            }
            
            /* Root accessibility overrides - Using CSS Zoom on containers (bypasses flexbox zoom bugs) */
            body.acc-sz-large .container,
            body.acc-sz-large .schedule-container {
                zoom: 1.08 !important;
            }
            body.acc-sz-xlarge .container,
            body.acc-sz-xlarge .schedule-container {
                zoom: 1.16 !important;
            }
            body.acc-high-contrast .container,
            body.acc-high-contrast .schedule-container {
                filter: contrast(1.4) saturate(1.15) !important;
            }
            /* Target only workspace content for Colorblind mode (preserves sidebar & brand colors!) */
            body.acc-colorblind .container,
            body.acc-colorblind .schedule-container {
                filter: hue-rotate(50deg) saturate(1.3) !important;
            }
        `;
        document.head.appendChild(style);

        // 2. Create Widget Markup
        const widget = document.createElement("div");
        widget.className = "safyra-acc-widget";
        widget.innerHTML = `
            <button class="safyra-acc-btn" title="Opciones de Accesibilidad Visual" aria-label="Opciones de Accesibilidad Visual">♿</button>
            <div class="safyra-acc-menu">
                <div class="safyra-acc-title">Tamaño de Fuente</div>
                <button class="safyra-acc-item" id="acc-sz-normal">Texto Normal</button>
                <button class="safyra-acc-item" id="acc-sz-large">Texto Grande (A+)</button>
                <button class="safyra-acc-item" id="acc-sz-xlarge">Texto Extra (A++)</button>
                
                <div class="safyra-acc-title" style="margin-top: 10px;">Filtros Visuales</div>
                <button class="safyra-acc-item" id="acc-toggle-contrast">Alto Contraste</button>
                <button class="safyra-acc-item" id="acc-toggle-colorblind">Modo Daltonismo</button>
            </div>
        `;
        document.body.appendChild(widget);

        const bodyEl = document.body;
        const mainBtn = widget.querySelector(".safyra-acc-btn");
        const menu = widget.querySelector(".safyra-acc-menu");

        // Load settings from storage
        let currentSize = localStorage.getItem("safyraAccSize") || "normal";
        let isContrast = localStorage.getItem("safyraAccContrast") === "true";
        let isColorblind = localStorage.getItem("safyraAccColorblind") === "true";

        applySize(currentSize);
        applyContrast(isContrast);
        applyColorblind(isColorblind);

        // UI Event Listeners
        mainBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            menu.classList.toggle("active");
        });
        document.addEventListener("click", () => {
            menu.classList.remove("active");
        });
        menu.addEventListener("click", (e) => {
            e.stopPropagation();
        });

        widget.querySelector("#acc-sz-normal").addEventListener("click", () => applySize("normal"));
        widget.querySelector("#acc-sz-large").addEventListener("click", () => applySize("large"));
        widget.querySelector("#acc-sz-xlarge").addEventListener("click", () => applySize("xlarge"));
        widget.querySelector("#acc-toggle-contrast").addEventListener("click", () => applyContrast(!isContrast));
        widget.querySelector("#acc-toggle-colorblind").addEventListener("click", () => applyColorblind(!isColorblind));

        function applySize(size) {
            currentSize = size;
            bodyEl.classList.remove("acc-sz-large", "acc-sz-xlarge");
            widget.querySelectorAll("[id^='acc-sz-']").forEach(b => b.classList.remove("selected"));
            
            if (size === "large") {
                bodyEl.classList.add("acc-sz-large");
                widget.querySelector("#acc-sz-large").classList.add("selected");
            } else if (size === "xlarge") {
                bodyEl.classList.add("acc-sz-xlarge");
                widget.querySelector("#acc-sz-xlarge").classList.add("selected");
            } else {
                widget.querySelector("#acc-sz-normal").classList.add("selected");
            }
            localStorage.setItem("safyraAccSize", size);
        }

        function applyContrast(enable) {
            isContrast = enable;
            const btn = widget.querySelector("#acc-toggle-contrast");
            if (enable) {
                bodyEl.classList.add("acc-high-contrast");
                btn.classList.add("selected");
            } else {
                bodyEl.classList.remove("acc-high-contrast");
                btn.classList.remove("selected");
            }
            localStorage.setItem("safyraAccContrast", enable ? "true" : "false");
        }

        function applyColorblind(enable) {
            isColorblind = enable;
            const btn = widget.querySelector("#acc-toggle-colorblind");
            if (enable) {
                bodyEl.classList.add("acc-colorblind");
                btn.classList.add("selected");
            } else {
                bodyEl.classList.remove("acc-colorblind");
                btn.classList.remove("selected");
            }
            localStorage.setItem("safyraAccColorblind", enable ? "true" : "false");
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initAccessibility);
    } else {
        initAccessibility();
    }

    window.SafyraAuth = {
        applyRoleUI,
        fetchCurrentUser,
        fetchConsentStatus,
        getAuthHeader,
        getToken,
        getTokenOrRedirect,
        goHome,
        handleProtectedResponse,
        hasAnyRole,
        logout,
        requireRoles,
        roleHome,
    };
})();
