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
    // FLOATING ACCESSIBILITY PANEL (UserWay High-Fidelity Clone)
    // ==========================================================
    function initAccessibility() {
        // 1. Inject Styles
        const style = document.createElement("style");
        style.textContent = `
            .safyra-acc-widget-trigger {
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 999998;
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
            .safyra-acc-widget-trigger:hover {
                transform: scale(1.15) rotate(15deg);
                box-shadow: 0 8px 24px rgba(0, 245, 255, 0.6);
            }
            .safyra-acc-panel {
                position: fixed;
                top: 0;
                right: -360px;
                width: 340px;
                height: 100vh;
                background: #0d122e;
                border-left: 2px solid #00f5ff;
                z-index: 999999;
                box-shadow: -10px 0 40px rgba(0, 0, 0, 0.8);
                display: flex;
                flex-direction: column;
                transition: right 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                color: #ffffff;
                font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            .safyra-acc-panel.active {
                right: 0;
            }
            .safyra-acc-hdr {
                background: linear-gradient(135deg, #0b153b, #04081c);
                padding: 18px 20px;
                border-bottom: 1px solid rgba(0, 245, 255, 0.2);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .safyra-acc-hdr h3 {
                margin: 0;
                font-size: 15px;
                font-weight: 700;
                color: #00f5ff;
                text-transform: uppercase;
                letter-spacing: 0.8px;
            }
            .safyra-acc-close {
                background: none;
                border: none;
                color: #ffffff;
                font-size: 22px;
                cursor: pointer;
                transition: color 0.2s;
                line-height: 1;
            }
            .safyra-acc-close:hover {
                color: #ff4d4d;
            }
            .safyra-acc-body {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                display: flex;
                flex-direction: column;
                gap: 15px;
            }
            .safyra-acc-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            }
            .safyra-acc-btn-opt {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(0, 245, 255, 0.15);
                border-radius: 12px;
                padding: 16px 8px;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 8px;
                cursor: pointer;
                transition: all 0.2s ease;
                color: #ffffff;
                text-align: center;
                user-select: none;
            }
            .safyra-acc-btn-opt:hover {
                background: rgba(0, 245, 255, 0.1);
                border-color: rgba(0, 245, 255, 0.4);
                color: #00f5ff;
            }
            .safyra-acc-btn-opt.active {
                background: rgba(0, 245, 255, 0.18);
                border-color: #00f5ff;
                color: #00f5ff;
            }
            .safyra-acc-opt-icon {
                font-size: 24px;
                line-height: 1;
            }
            .safyra-acc-opt-lbl {
                font-size: 11px;
                font-weight: 600;
                line-height: 1.3;
            }
            
            /* UserWay active indicators */
            .safyra-acc-indicator-bar {
                display: flex;
                gap: 4px;
                margin-top: 4px;
            }
            .safyra-acc-indicator-dot {
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.25);
            }
            .safyra-acc-indicator-dot.active {
                background: #00f5ff;
                box-shadow: 0 0 6px #00f5ff;
            }
            
            .safyra-acc-reset-btn {
                background: rgba(255, 77, 77, 0.1);
                border: 1px solid rgba(255, 77, 77, 0.3);
                color: #ff4d4d;
                border-radius: 10px;
                padding: 12px;
                font-size: 12px;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.2s;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                margin-top: 15px;
                text-align: center;
            }
            .safyra-acc-reset-btn:hover {
                background: #ff4d4d;
                color: #ffffff;
                box-shadow: 0 4px 12px rgba(255, 77, 77, 0.3);
            }
            
            /* Root accessibility overrides - Scoped Zoom */
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
            body.acc-colorblind .container,
            body.acc-colorblind .schedule-container {
                filter: hue-rotate(50deg) saturate(1.3) !important;
            }
            
            /* SVG Big Cursor */
            body.acc-large-cursor, body.acc-large-cursor * {
                cursor: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="white" stroke="black" stroke-width="2"><path d="M4 4l12 12h-5l5 5-2 2-5-5v5z"/></svg>'), auto !important;
            }
            
            /* Custom Text spacing */
            body.acc-text-spacing *, body.acc-text-spacing p, body.acc-text-spacing span, body.acc-text-spacing div {
                letter-spacing: 0.06em !important;
                word-spacing: 0.12em !important;
            }
            
            /* Dyslexic friendly font (Comic Sans MS works perfectly on Windows) */
            body.acc-dyslexic *, body.acc-dyslexic p, body.acc-dyslexic span, body.acc-dyslexic div, body.acc-dyslexic h1, body.acc-dyslexic h2, body.acc-dyslexic h3, body.acc-dyslexic h4 {
                font-family: "Comic Sans MS", "Comic Sans", cursive, sans-serif !important;
            }
            
            /* Highlight links style */
            body.acc-highlight-links a {
                background-color: #ffff00 !important;
                color: #000000 !important;
                outline: 2px solid #ff4d4d !important;
                text-decoration: underline !important;
                font-weight: bold !important;
            }
        `;
        document.head.appendChild(style);

        // 2. Create Panel & Trigger Button Markup
        const trigger = document.createElement("button");
        trigger.className = "safyra-acc-widget-trigger";
        trigger.title = "Menú de Accesibilidad";
        trigger.innerHTML = "♿";
        document.body.appendChild(trigger);

        const panel = document.createElement("div");
        panel.className = "safyra-acc-panel";
        panel.innerHTML = `
            <div class="safyra-acc-hdr">
                <h3>Menú de Accesibilidad</h3>
                <button class="safyra-acc-close" aria-label="Cerrar">×</button>
            </div>
            <div class="safyra-acc-body">
                <div class="safyra-acc-grid">
                    <button class="safyra-acc-btn-opt" id="opt-text-size">
                        <span class="safyra-acc-opt-icon">Tт</span>
                        <span class="safyra-acc-opt-lbl">Agrandar Texto</span>
                        <div class="safyra-acc-indicator-bar" id="dots-text-size">
                            <div class="safyra-acc-indicator-dot" id="dot-sz-1"></div>
                            <div class="safyra-acc-indicator-dot" id="dot-sz-2"></div>
                        </div>
                    </button>
                    <button class="safyra-acc-btn-opt" id="opt-contrast">
                        <span class="safyra-acc-opt-icon">◑</span>
                        <span class="safyra-acc-opt-lbl">Contraste +</span>
                        <div class="safyra-acc-indicator-bar">
                            <div class="safyra-acc-indicator-dot" id="dot-contrast"></div>
                        </div>
                    </button>
                    <button class="safyra-acc-btn-opt" id="opt-highlight-links">
                        <span class="safyra-acc-opt-icon">🔗</span>
                        <span class="safyra-acc-opt-lbl">Resaltar Enlaces</span>
                        <div class="safyra-acc-indicator-bar">
                            <div class="safyra-acc-indicator-dot" id="dot-links"></div>
                        </div>
                    </button>
                    <button class="safyra-acc-btn-opt" id="opt-dyslexic">
                        <span class="safyra-acc-opt-icon">Ab</span>
                        <span class="safyra-acc-opt-lbl">Apto Dislexia</span>
                        <div class="safyra-acc-indicator-bar">
                            <div class="safyra-acc-indicator-dot" id="dot-dyslexic"></div>
                        </div>
                    </button>
                    <button class="safyra-acc-btn-opt" id="opt-cursor">
                        <span class="safyra-acc-opt-icon">⬈</span>
                        <span class="safyra-acc-opt-lbl">Cursor Grande</span>
                        <div class="safyra-acc-indicator-bar">
                            <div class="safyra-acc-indicator-dot" id="dot-cursor"></div>
                        </div>
                    </button>
                    <button class="safyra-acc-btn-opt" id="opt-spacing">
                        <span class="safyra-acc-opt-icon">↔</span>
                        <span class="safyra-acc-opt-lbl">Espaciado Texto</span>
                        <div class="safyra-acc-indicator-bar">
                            <div class="safyra-acc-indicator-dot" id="dot-spacing"></div>
                        </div>
                    </button>
                    <button class="safyra-acc-btn-opt" id="opt-colorblind" style="grid-column: span 2;">
                        <span class="safyra-acc-opt-icon">🎨</span>
                        <span class="safyra-acc-opt-lbl">Modo Daltonismo</span>
                        <div class="safyra-acc-indicator-bar">
                            <div class="safyra-acc-indicator-dot" id="dot-colorblind"></div>
                        </div>
                    </button>
                </div>
                <button class="safyra-acc-reset-btn">Restablecer Todo</button>
            </div>
        `;
        document.body.appendChild(panel);

        const bodyEl = document.body;
        const closeBtn = panel.querySelector(".safyra-acc-close");

        // Load settings from storage
        let textSize = localStorage.getItem("safyraAccSize") || "normal";
        let isContrast = localStorage.getItem("safyraAccContrast") === "true";
        let isLinks = localStorage.getItem("safyraAccLinks") === "true";
        let isDyslexic = localStorage.getItem("safyraAccDyslexic") === "true";
        let isCursor = localStorage.getItem("safyraAccCursor") === "true";
        let isSpacing = localStorage.getItem("safyraAccSpacing") === "true";
        let isColorblind = localStorage.getItem("safyraAccColorblind") === "true";

        applyTextSize(textSize);
        applyContrast(isContrast);
        applyLinks(isLinks);
        applyDyslexic(isDyslexic);
        applyCursor(isCursor);
        applySpacing(isSpacing);
        applyColorblind(isColorblind);

        // Sidebar slide events
        trigger.addEventListener("click", (e) => {
            e.stopPropagation();
            panel.classList.toggle("active");
        });
        closeBtn.addEventListener("click", () => {
            panel.classList.remove("active");
        });
        document.addEventListener("click", (e) => {
            if (!panel.contains(e.target) && e.target !== trigger) {
                panel.classList.remove("active");
            }
        });
        panel.addEventListener("click", (e) => {
            e.stopPropagation();
        });

        // Trigger Click Events
        panel.querySelector("#opt-text-size").addEventListener("click", () => {
            if (textSize === "normal") applyTextSize("large");
            else if (textSize === "large") applyTextSize("xlarge");
            else applyTextSize("normal");
        });
        panel.querySelector("#opt-contrast").addEventListener("click", () => applyContrast(!isContrast));
        panel.querySelector("#opt-highlight-links").addEventListener("click", () => applyLinks(!isLinks));
        panel.querySelector("#opt-dyslexic").addEventListener("click", () => applyDyslexic(!isDyslexic));
        panel.querySelector("#opt-cursor").addEventListener("click", () => applyCursor(!isCursor));
        panel.querySelector("#opt-spacing").addEventListener("click", () => applySpacing(!isSpacing));
        panel.querySelector("#opt-colorblind").addEventListener("click", () => applyColorblind(!isColorblind));
        panel.querySelector(".safyra-acc-reset-btn").addEventListener("click", resetAll);

        // Actions Implementations
        function applyTextSize(size) {
            textSize = size;
            bodyEl.classList.remove("acc-sz-large", "acc-sz-xlarge");
            const btn = panel.querySelector("#opt-text-size");
            const dot1 = panel.querySelector("#dot-sz-1");
            const dot2 = panel.querySelector("#dot-sz-2");
            
            btn.classList.remove("active");
            dot1.classList.remove("active");
            dot2.classList.remove("active");

            if (size === "large") {
                bodyEl.classList.add("acc-sz-large");
                btn.classList.add("active");
                dot1.classList.add("active");
            } else if (size === "xlarge") {
                bodyEl.classList.add("acc-sz-xlarge");
                btn.classList.add("active");
                dot1.classList.add("active");
                dot2.classList.add("active");
            }
            localStorage.setItem("safyraAccSize", size);
        }

        function applyContrast(enable) {
            isContrast = enable;
            const btn = panel.querySelector("#opt-contrast");
            const dot = panel.querySelector("#dot-contrast");
            if (enable) {
                bodyEl.classList.add("acc-high-contrast");
                btn.classList.add("active");
                dot.classList.add("active");
            } else {
                bodyEl.classList.remove("acc-high-contrast");
                btn.classList.remove("active");
                dot.classList.remove("active");
            }
            localStorage.setItem("safyraAccContrast", enable ? "true" : "false");
        }

        function applyLinks(enable) {
            isLinks = enable;
            const btn = panel.querySelector("#opt-highlight-links");
            const dot = panel.querySelector("#dot-links");
            if (enable) {
                bodyEl.classList.add("acc-highlight-links");
                btn.classList.add("active");
                dot.classList.add("active");
            } else {
                bodyEl.classList.remove("acc-highlight-links");
                btn.classList.remove("active");
                dot.classList.remove("active");
            }
            localStorage.setItem("safyraAccLinks", enable ? "true" : "false");
        }

        function applyDyslexic(enable) {
            isDyslexic = enable;
            const btn = panel.querySelector("#opt-dyslexic");
            const dot = panel.querySelector("#dot-dyslexic");
            if (enable) {
                bodyEl.classList.add("acc-dyslexic");
                btn.classList.add("active");
                dot.classList.add("active");
            } else {
                bodyEl.classList.remove("acc-dyslexic");
                btn.classList.remove("active");
                dot.classList.remove("active");
            }
            localStorage.setItem("safyraAccDyslexic", enable ? "true" : "false");
        }

        function applyCursor(enable) {
            isCursor = enable;
            const btn = panel.querySelector("#opt-cursor");
            const dot = panel.querySelector("#dot-cursor");
            if (enable) {
                bodyEl.classList.add("acc-large-cursor");
                btn.classList.add("active");
                dot.classList.add("active");
            } else {
                bodyEl.classList.remove("acc-large-cursor");
                btn.classList.remove("active");
                dot.classList.remove("active");
            }
            localStorage.setItem("safyraAccCursor", enable ? "true" : "false");
        }

        function applySpacing(enable) {
            isSpacing = enable;
            const btn = panel.querySelector("#opt-spacing");
            const dot = panel.querySelector("#dot-spacing");
            if (enable) {
                bodyEl.classList.add("acc-text-spacing");
                btn.classList.add("active");
                dot.classList.add("active");
            } else {
                bodyEl.classList.remove("acc-text-spacing");
                btn.classList.remove("active");
                dot.classList.remove("active");
            }
            localStorage.setItem("safyraAccSpacing", enable ? "true" : "false");
        }

        function applyColorblind(enable) {
            isColorblind = enable;
            const btn = panel.querySelector("#opt-colorblind");
            const dot = panel.querySelector("#dot-colorblind");
            if (enable) {
                bodyEl.classList.add("acc-colorblind");
                btn.classList.add("active");
                dot.classList.add("active");
            } else {
                bodyEl.classList.remove("acc-colorblind");
                btn.classList.remove("active");
                dot.classList.remove("active");
            }
            localStorage.setItem("safyraAccColorblind", enable ? "true" : "false");
        }

        function resetAll() {
            applyTextSize("normal");
            applyContrast(false);
            applyLinks(false);
            applyDyslexic(false);
            applyCursor(false);
            applySpacing(false);
            applyColorblind(false);
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
