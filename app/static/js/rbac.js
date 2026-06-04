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
