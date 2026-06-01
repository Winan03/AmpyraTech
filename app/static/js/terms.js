const token = localStorage.getItem("safyraToken");
const role = localStorage.getItem("safyraRole");
const params = new URLSearchParams(window.location.search);
const requestedNext = params.get("next");
const nextUrl = requestedNext && requestedNext.startsWith("/") && !requestedNext.startsWith("//")
    ? requestedNext
    : (role === "auditor" ? "/history" : "/");

const acceptCheck = document.getElementById("accept-check");
const acceptBtn = document.getElementById("accept-btn");
const logoutBtn = document.getElementById("logout-btn");
const message = document.getElementById("message");
const versionEl = document.getElementById("terms-version");
const userLabel = document.getElementById("user-label");
let currentTermsVersion = null;

function showMessage(text, type) {
    message.textContent = text;
    message.className = `message ${type} show`;
}

function clearSession() {
    localStorage.removeItem("safyraToken");
    localStorage.removeItem("safyraAuthProvider");
    localStorage.removeItem("safyraRole");
    localStorage.removeItem("safyraUsername");
}

function authHeaders(extraHeaders) {
    return {
        "Authorization": `Bearer ${token}`,
        ...(extraHeaders || {}),
    };
}

async function loadConsentStatus() {
    if (!token) {
        window.location.href = "/login";
        return;
    }

    const response = await fetch("/consent/status", { headers: authHeaders() });
    if (response.status === 401) {
        clearSession();
        window.location.href = "/login";
        return;
    }
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || "No se pudo validar el consentimiento");
    }

    currentTermsVersion = data.terms_version;
    versionEl.textContent = data.terms_version;
    userLabel.textContent = localStorage.getItem("safyraUsername") || "Usuario autenticado";

    if (!data.requires_acceptance || data.accepted) {
        showMessage("Consentimiento vigente. Redirigiendo...", "ok");
        setTimeout(() => { window.location.href = nextUrl; }, 450);
    }
}

acceptCheck.addEventListener("change", () => {
    acceptBtn.disabled = !acceptCheck.checked || !currentTermsVersion;
});

acceptBtn.addEventListener("click", async () => {
    if (!acceptCheck.checked || !currentTermsVersion) return;
    acceptBtn.disabled = true;
    acceptBtn.textContent = "Registrando...";

    try {
        const response = await fetch("/consent/accept", {
            method: "POST",
            headers: authHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ terms_version: currentTermsVersion }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "No se pudo registrar el consentimiento");
        }
        showMessage(`Consentimiento registrado el ${new Date(data.accepted_at).toLocaleString("es-PE")}.`, "ok");
        setTimeout(() => { window.location.href = nextUrl; }, 700);
    } catch (error) {
        acceptBtn.disabled = false;
        acceptBtn.textContent = "Aceptar y continuar";
        showMessage(error.message, "error");
    }
});

logoutBtn.addEventListener("click", () => {
    clearSession();
    window.location.href = "/login";
});

loadConsentStatus().catch((error) => {
    showMessage(error.message, "error");
});
