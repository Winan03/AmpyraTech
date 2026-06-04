(function () {
    const AUTH_HEADER = SafyraAuth.getAuthHeader();
    const DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday"];
    const DAY_LABELS = {
        monday: "Lunes",
        tuesday: "Martes",
        wednesday: "Mi\u00e9rcoles",
        thursday: "Jueves",
        friday: "Viernes",
    };
    const HOURS = [8, 9, 10, 11, 12, 13, 14];
    const PIXELS_PER_HOUR = 56;
    const START_HOUR = 8;
    const SCHOOL_START_MINUTES = START_HOUR * 60;
    const SCHOOL_END_MINUTES = (14 * 60) + 30;
    const SCHOOL_START_TIME = "08:00";
    const SCHOOL_END_TIME = "14:30";
    const WRITE_ROLE = "auditor";
    const DEFAULT_CLASS_LABEL = "Clase de computaci\u00f3n";
    const NO_CLASS_LABEL = "D\u00eda sin clase";
    const SUSPENSION_LABEL = "Suspensi\u00f3n de clases";

    let schedules = [];
    let currentWeekStart = startOfWeek(new Date());
    let canWriteSchedule = false;
    let editTarget = null;
    let formConstraints = {
        editing: false,
        lockedDate: "",
    };

    const form = document.getElementById("schedule-form");
    const modal = document.getElementById("schedule-modal");
    const modalDialog = document.querySelector(".schedule-modal-dialog");
    const modalBackdrop = document.querySelector("#schedule-modal [data-modal-close]");
    const openScheduleButton = document.getElementById("open-schedule-modal");
    const closeModalButton = document.getElementById("close-schedule-modal");
    const readonlyPanel = document.getElementById("schedule-readonly-panel");
    const messageBox = document.getElementById("schedule-message");
    const calendarBoard = document.getElementById("calendar-board");
    const scheduleList = document.getElementById("schedule-list");
    const refreshListButton = document.getElementById("refresh-schedules-list");
    const clearButton = document.getElementById("clear-form");
    const weekRange = document.getElementById("week-range");
    const kindSelect = document.getElementById("schedule-kind");
    const labelInput = document.getElementById("label");
    const sourceScheduleInput = document.getElementById("source-schedule-id");
    const dayInput = document.getElementById("day-of-week");
    const startInput = document.getElementById("start-time");
    const endInput = document.getElementById("end-time");
    const validFromInput = document.getElementById("valid-from");
    const validToInput = document.getElementById("valid-to");
    const statusSelect = document.getElementById("schedule-status");
    const modalEyebrow = document.getElementById("schedule-modal-eyebrow");
    const modalTitle = document.getElementById("schedule-modal-title");
    const modalHint = document.getElementById("schedule-modal-hint");
    const submitButton = document.getElementById("schedule-submit");

    if (form) {
        form.noValidate = true;
    }

    function showMessage(text, type) {
        if (!messageBox) {
            return;
        }
        messageBox.textContent = text;
        messageBox.className = `schedule-message ${type} show`;
    }

    function loadTheme() {
        const savedTheme = localStorage.getItem("theme") || "light";
        document.body.setAttribute("data-theme", savedTheme);
        document.getElementById("theme-text").textContent = savedTheme === "light" ? "Modo Claro" : "Modo Oscuro";
    }

    window.toggleTheme = function () {
        const nextTheme = document.body.getAttribute("data-theme") === "dark" ? "light" : "dark";
        document.body.setAttribute("data-theme", nextTheme);
        localStorage.setItem("theme", nextTheme);
        document.getElementById("theme-text").textContent = nextTheme === "light" ? "Modo Claro" : "Modo Oscuro";
    };

    window.logout = function () {
        SafyraAuth.logout();
    };

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function normalizeScheduleLabel(value) {
        return String(value || "")
            .replace(/\s+/g, " ")
            .replace(/[0-9]/g, "")
            .replace(/inform[a\u00e1]tica/gi, "computaci\u00f3n")
            .replace(/computaci[o\u00f3]n/gi, "computaci\u00f3n")
            .trim();
    }

    function displayScheduleLabel(item) {
        return normalizeScheduleLabel(item.label || "");
    }

    function startOfWeek(date) {
        const copy = new Date(date);
        const day = copy.getDay() || 7;
        copy.setDate(copy.getDate() - day + 1);
        copy.setHours(0, 0, 0, 0);
        return copy;
    }

    function addDays(date, days) {
        const copy = new Date(date);
        copy.setDate(copy.getDate() + days);
        return copy;
    }

    function formatShortDate(date) {
        return date.toLocaleDateString("es-PE", { day: "2-digit", month: "short" });
    }

    function formatDateLocal(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function todayLocalText() {
        return formatDateLocal(new Date());
    }

    function normalizeTime(value) {
        return String(value || "").trim();
    }

    function sanitizeVisibleLabel(value) {
        return normalizeScheduleLabel(value).replace(/[0-9]/g, "");
    }

    function stripLabelDigits(value) {
        return String(value || "").replace(/[0-9]/g, "");
    }

    function formatMinutes(minutes) {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
    }

    function buildTimeOptions() {
        const options = [];
        for (let minutes = SCHOOL_START_MINUTES; minutes <= SCHOOL_END_MINUTES; minutes += 30) {
            options.push(formatMinutes(minutes));
        }
        return options;
    }

    function populateTimeSelect(select) {
        if (!select) {
            return;
        }

        const previousValue = String(select.value || "");
        select.innerHTML = buildTimeOptions()
            .map((timeValue) => `<option value="${timeValue}">${timeValue}</option>`)
            .join("");

        if (previousValue && select.querySelector(`option[value="${previousValue}"]`)) {
            select.value = previousValue;
            return;
        }

        select.value = select.id === "start-time" ? SCHOOL_START_TIME : "10:00";
    }

    function parseMinutes(value) {
        const parts = String(value || "").split(":").map(Number);
        if (parts.length !== 2 || parts.some(Number.isNaN)) {
            return SCHOOL_START_MINUTES;
        }
        return parts[0] * 60 + parts[1];
    }

    function scheduleKind(item) {
        return String(item.kind || "class").toLowerCase() === "no_class" ? "no_class" : "class";
    }

    function scheduleKindLabel(item) {
        return scheduleKind(item) === "no_class" ? NO_CLASS_LABEL : "Clase regular";
    }

    function isNoClassSchedule(item) {
        return scheduleKind(item) === "no_class";
    }

    function applyFormConstraints() {
        if (!startInput || !endInput || !validFromInput || !validToInput) {
            return;
        }

        startInput.disabled = false;
        endInput.disabled = false;
        validFromInput.disabled = false;
        validToInput.disabled = false;

        if (startInput.tagName === "SELECT") {
            populateTimeSelect(startInput);
        }
        if (endInput.tagName === "SELECT") {
            populateTimeSelect(endInput);
        }

        if (formConstraints.lockedDate) {
            validFromInput.min = formConstraints.lockedDate;
            validFromInput.max = formConstraints.lockedDate;
            validToInput.min = formConstraints.lockedDate;
            validToInput.max = formConstraints.lockedDate;
            validFromInput.setAttribute("min", formConstraints.lockedDate);
            validFromInput.setAttribute("max", formConstraints.lockedDate);
            validToInput.setAttribute("min", formConstraints.lockedDate);
            validToInput.setAttribute("max", formConstraints.lockedDate);
            validFromInput.value = formConstraints.lockedDate;
            validToInput.value = formConstraints.lockedDate;
            validFromInput.disabled = true;
            validToInput.disabled = true;
            return;
        }

        const today = todayLocalText();
        const fromValue = String(validFromInput.value || "");
        const toFloor = fromValue && fromValue > today ? fromValue : today;

        validFromInput.min = today;
        validFromInput.max = "";
        validToInput.min = toFloor;
        validToInput.max = "";
        validFromInput.setAttribute("min", today);
        validFromInput.removeAttribute("max");
        validToInput.setAttribute("min", toFloor);
        validToInput.removeAttribute("max");
    }

    function setFormConstraints({ editing = false, lockedDate = "" } = {}) {
        formConstraints = {
            editing,
            lockedDate,
        };
        applyFormConstraints();
    }

    function scheduleMatchKey(item) {
        return [
            String(item.day_of_week || ""),
            normalizeTime(item.start_time),
            normalizeTime(item.end_time),
            String(item.valid_from || ""),
            String(item.valid_to || ""),
        ].join("|");
    }

    function isLinkedException(candidate, baseItem) {
        if (!candidate || !baseItem || !isNoClassSchedule(candidate)) {
            return false;
        }

        const sourceScheduleId = String(candidate.source_schedule_id || "");
        if (sourceScheduleId && sourceScheduleId === String(baseItem.id || "")) {
            return true;
        }

        return scheduleMatchKey(candidate) === scheduleMatchKey(baseItem);
    }

    function findVisibleException(baseItem, dateText) {
        const visibleDate = dateText || visibleDateForDay(baseItem.day_of_week);
        const matches = schedules.filter((candidate) => {
            if (!isLinkedException(candidate, baseItem)) {
                return false;
            }
            return String(candidate.valid_from || "") === visibleDate && String(candidate.valid_to || "") === visibleDate;
        });
        return matches.find((candidate) => String(candidate.status || "activo").toLowerCase() === "activo") || null;
    }

    function shouldRenderInWeek(item, dayDate) {
        const dateText = formatDateLocal(dayDate);
        if (String(item.status || "activo").toLowerCase() !== "activo") {
            return false;
        }
        if (item.valid_from && dateText < item.valid_from) {
            return false;
        }
        if (item.valid_to && dateText > item.valid_to) {
            return false;
        }
        return true;
    }

    function isDateInsideScheduleValidity(item, dateText) {
        if (!dateText || String(item.status || "activo").toLowerCase() !== "activo") {
            return false;
        }
        if (item.valid_from && dateText < item.valid_from) {
            return false;
        }
        if (item.valid_to && dateText > item.valid_to) {
            return false;
        }
        return true;
    }

    function renderWeekHeader() {
        const friday = addDays(currentWeekStart, 4);
        weekRange.textContent = `${formatShortDate(currentWeekStart)} - ${formatShortDate(friday)}`;
    }

    function visibleDateForDay(day) {
        const dayIndex = DAY_ORDER.indexOf(day);
        if (dayIndex < 0) {
            return "";
        }
        return formatDateLocal(addDays(currentWeekStart, dayIndex));
    }

    function enforceLabelRules() {
        if (!labelInput) {
            return;
        }

        const sanitized = sanitizeVisibleLabel(labelInput.value);
        if (labelInput.value !== sanitized) {
            labelInput.value = sanitized;
        }
    }

    function blockLabelDigits(event) {
        if (!labelInput || !event) {
            return;
        }

        if (event.inputType && event.inputType.startsWith("insert")) {
            const text = event.data || "";
            if (/[0-9]/.test(text)) {
                event.preventDefault();
            }
        }
    }

    function filterLabelPaste(event) {
        if (!labelInput) {
            return;
        }

        const pasteText = event.clipboardData?.getData("text") || "";
        const filtered = stripLabelDigits(pasteText);
        if (pasteText && pasteText !== filtered) {
            event.preventDefault();
            const selectionStart = labelInput.selectionStart ?? labelInput.value.length;
            const selectionEnd = labelInput.selectionEnd ?? labelInput.value.length;
            const nextValue = `${labelInput.value.slice(0, selectionStart)}${filtered}${labelInput.value.slice(selectionEnd)}`;
            labelInput.value = nextValue;
            enforceLabelRules();
        }
    }

    function enforceTimeRules() {
        const minimum = SCHOOL_START_MINUTES;
        const maximum = SCHOOL_END_MINUTES;

        const ensureValidTime = (input) => {
            if (!input || !input.value) {
                return true;
            }
            const minutes = parseMinutes(input.value);
            if (minutes < minimum || minutes > maximum) {
                input.value = "";
                return false;
            }
            return true;
        };

        const startValid = ensureValidTime(startInput);
        const endValid = ensureValidTime(endInput);
        if (!startValid || !endValid) {
            showMessage(`El horario debe ubicarse entre ${SCHOOL_START_TIME} y ${SCHOOL_END_TIME}.`, "error");
            return false;
        }

        if (startInput.value && endInput.value && parseMinutes(startInput.value) >= parseMinutes(endInput.value)) {
            endInput.value = "";
            showMessage("La hora inicial debe ser menor que la hora final.", "error");
            return false;
        }

        return true;
    }

    function enforceDateRules() {
        if (formConstraints.lockedDate) {
            return true;
        }

        applyFormConstraints();

        const enforceSingleDate = (input) => {
            if (!input || !input.value) {
                return true;
            }

            const minValue = input.min || "";
            const maxValue = input.max || "";
            if (minValue && input.value < minValue) {
                input.value = minValue;
                return false;
            }
            if (maxValue && input.value > maxValue) {
                input.value = maxValue;
                return false;
            }
            return true;
        };

        const fromValid = enforceSingleDate(validFromInput);
        const toValid = enforceSingleDate(validToInput);
        if (!fromValid || !toValid) {
            if (formConstraints.lockedDate) {
                showMessage("La suspensión queda fijada en la fecha visible.", "error");
            } else {
                showMessage("La vigencia no puede ser anterior a hoy.", "error");
            }
            return false;
        }

        if (validFromInput.value && validToInput.value && validFromInput.value > validToInput.value) {
            validToInput.value = validFromInput.value;
            showMessage("La fecha inicial no puede ser mayor que la fecha final.", "error");
            return false;
        }

        return true;
    }

    function openScheduleModal() {
        if (!modal) {
            return;
        }
        applyFormConstraints();
        modal.hidden = false;
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("modal-open");
        window.requestAnimationFrame(() => {
            if (labelInput) {
                labelInput.focus();
                labelInput.select?.();
            }
        });
    }

    function closeScheduleModal() {
        if (!modal) {
            return;
        }
        modal.hidden = true;
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("modal-open");
    }

    function setModalMode(title, eyebrow, hint) {
        if (modalTitle) {
            modalTitle.textContent = title;
        }
        if (modalEyebrow) {
            modalEyebrow.textContent = eyebrow;
        }
        if (modalHint) {
            modalHint.textContent = hint;
        }
    }

    function renderCalendar() {
        renderWeekHeader();
        const dayHeaders = DAY_ORDER.map((day, index) => {
            const date = addDays(currentWeekStart, index);
            return `
                <div class="calendar-day">
                    <strong>${DAY_LABELS[day]}</strong>
                    <span>${date.getDate()}</span>
                </div>
            `;
        }).join("");

        const hourRows = HOURS.map((hour) => `
            <div class="calendar-hour">${String(hour).padStart(2, "0")}:00</div>
        `).join("");

        const dayColumns = DAY_ORDER.map((day, index) => {
            const dayDate = addDays(currentWeekStart, index);
            const activeDayItems = schedules
                .filter((item) => item.day_of_week === day && shouldRenderInWeek(item, dayDate))
                .sort((left, right) => {
                    const timeDiff = String(left.start_time || "").localeCompare(String(right.start_time || ""));
                    if (timeDiff !== 0) {
                        return timeDiff;
                    }
                    return Number(scheduleKind(left) === "no_class") - Number(scheduleKind(right) === "no_class");
                });
            const hasNoClass = activeDayItems.some((item) => scheduleKind(item) === "no_class");
            const events = activeDayItems
                .map((item) => renderCalendarEvent(item, dayDate, { hasNoClass }))
                .join("");
            return `<div class="calendar-column" data-day="${day}">${events}</div>`;
        }).join("");

        calendarBoard.innerHTML = `
            <div class="calendar-grid">
                <div class="calendar-corner"></div>
                ${dayHeaders}
                <div>
                    ${hourRows}
                </div>
                ${dayColumns}
            </div>
        `;
    }

    function renderCalendarEvent(item, dayDate, options = {}) {
        const start = Math.max(parseMinutes(item.start_time), SCHOOL_START_MINUTES);
        const end = Math.min(parseMinutes(item.end_time), SCHOOL_END_MINUTES);
        const top = ((start - SCHOOL_START_MINUTES) / 60) * PIXELS_PER_HOUR;
        const height = Math.max(((end - start) / 60) * PIXELS_PER_HOUR, 38);
        const kind = scheduleKind(item);
        const overlapClass = kind === "class" && options.hasNoClass ? " has-no-class" : "";
        const scheduleId = escapeHtml(item.id || "");

        return `
            <article class="calendar-event ${kind}${overlapClass}" style="top:${top}px;height:${height}px" data-schedule-id="${scheduleId}">
                ${escapeHtml(displayScheduleLabel(item))}
                <small>${escapeHtml(item.start_time)} - ${escapeHtml(item.end_time)}</small>
            </article>
        `;
    }

    function formatExceptionRange(item) {
        const dayText = DAY_LABELS[item.day_of_week] || item.day_of_week;
        const fromDate = item.valid_from || "sin inicio";
        const toDate = item.valid_to || "sin fin";
        return `${dayText} ${item.start_time} - ${item.end_time} | ${fromDate} / ${toDate}`;
    }

    function renderExceptionCard(item) {
        const status = String(item.status || "activo").toLowerCase();
        const pillClass = status === "inactivo" ? "inactivo" : "no_class";
        const scheduleId = escapeHtml(item.id || "");
        const actions = canWriteSchedule
            ? `
                <div class="schedule-item-actions schedule-item-actions--compact">
                    <button class="schedule-mini-btn" type="button" data-list-action="edit" data-schedule-id="${scheduleId}">Editar</button>
                    ${status === "activo" ? `<button class="schedule-mini-btn warning" type="button" data-list-action="revoke" data-schedule-id="${scheduleId}">Revocar</button>` : ""}
                </div>
            `
            : "";

        return `
            <div class="schedule-list-item schedule-list-item--exception">
                <div class="schedule-list-item-body">
                    <strong>${escapeHtml(DAY_LABELS[item.day_of_week] || item.day_of_week)} - ${escapeHtml(scheduleKindLabel(item))}</strong>
                    <span>${escapeHtml(formatExceptionRange(item))} | ${escapeHtml(displayScheduleLabel(item))}</span>
                    <small>${status === "activo" ? "Suspensi\u00f3n activa" : "Suspensi\u00f3n revocada"}</small>
                </div>
                <span class="schedule-pill ${escapeHtml(pillClass)}">${escapeHtml(status)}</span>
                ${actions}
            </div>
        `;
    }

    function renderLinkedExceptions(baseItem, exceptions) {
        if (!exceptions.length) {
            return "";
        }

        return `
            <div class="schedule-linked-exceptions">
                <span>Suspensiones vinculadas</span>
                ${exceptions.map((item) => renderExceptionCard(item)).join("")}
            </div>
        `;
    }

    function renderScheduleListItem(item, exceptions) {
        const kind = scheduleKind(item);
        const status = String(item.status || "activo").toLowerCase();
        const pillClass = status === "inactivo" ? "inactivo" : kind;
        const scheduleId = escapeHtml(item.id || "");
        const visibleDate = visibleDateForDay(item.day_of_week);
        const canSuspendVisibleDate = kind === "class" && isDateInsideScheduleValidity(item, visibleDate);
        const visibleException = findVisibleException(item, visibleDate);
        const actions = canWriteSchedule
            ? `
                <div class="schedule-item-actions">
                    <button class="schedule-mini-btn" type="button" data-list-action="edit" data-schedule-id="${scheduleId}">Editar bloque</button>
                    ${
                        canSuspendVisibleDate
                            ? (
                                visibleException
                                    ? `<button class="schedule-mini-btn warning" type="button" data-list-action="edit" data-schedule-id="${escapeHtml(visibleException.id || "")}">Editar suspensión visible</button>`
                                    : `<button class="schedule-mini-btn warning" type="button" data-list-action="suspend-visible" data-schedule-id="${scheduleId}" data-day-date="${escapeHtml(visibleDate)}">Suspender fecha visible</button>`
                            )
                            : ""
                    }
                </div>
            `
            : "";

        return `
            <article class="schedule-list-item ${exceptions.length ? "has-exceptions" : ""}">
                <div class="schedule-list-item-body">
                    <strong>${escapeHtml(DAY_LABELS[item.day_of_week] || item.day_of_week)} - ${escapeHtml(scheduleKindLabel(item))}</strong>
                    <span>${escapeHtml(item.start_time)} - ${escapeHtml(item.end_time)} | ${escapeHtml(displayScheduleLabel(item))}</span>
                    <small>Vigencia: ${escapeHtml(item.valid_from || "sin inicio")} / ${escapeHtml(item.valid_to || "sin fin")}</small>
                    ${renderLinkedExceptions(item, exceptions)}
                </div>
                <div class="schedule-list-item-side">
                    <span class="schedule-pill ${escapeHtml(pillClass)}">${escapeHtml(status)}</span>
                    ${actions}
                </div>
            </article>
        `;
    }

    function renderScheduleList() {
        if (!schedules.length) {
            scheduleList.innerHTML = '<div class="schedule-empty">No hay bloques registrados para el laboratorio.</div>';
            return;
        }

        const sorted = [...schedules].sort((left, right) => {
            const dayDiff = DAY_ORDER.indexOf(left.day_of_week) - DAY_ORDER.indexOf(right.day_of_week);
            if (dayDiff !== 0) {
                return dayDiff;
            }
            return String(left.start_time || "").localeCompare(String(right.start_time || ""));
        });

        const consumed = new Set();
        const listItems = [];

        for (const item of sorted) {
            if (consumed.has(String(item.id || ""))) {
                continue;
            }

            if (scheduleKind(item) === "class") {
                const exceptions = sorted.filter((candidate) => !consumed.has(String(candidate.id || "")) && isLinkedException(candidate, item));
                exceptions.forEach((candidate) => consumed.add(String(candidate.id || "")));
                listItems.push(renderScheduleListItem(item, exceptions));
                continue;
            }
        }

        for (const item of sorted) {
            const itemId = String(item.id || "");
            if (consumed.has(itemId) || scheduleKind(item) !== "no_class") {
                continue;
            }

            const linkedBase = sorted.find((candidate) => scheduleKind(candidate) === "class" && isLinkedException(item, candidate));
            if (linkedBase) {
                continue;
            }

            listItems.push(renderExceptionCard(item));
        }

        scheduleList.innerHTML = listItems.join("");
    }

    async function loadSchedules() {
        scheduleList.innerHTML = '<div class="schedule-empty">Cargando horarios...</div>';
        const response = await fetch("/api/data/schedule?room_id=LAB-PC-01", { headers: AUTH_HEADER });
        if (SafyraAuth.handleProtectedResponse(response)) {
            return;
        }
        if (!response.ok) {
            scheduleList.innerHTML = '<div class="schedule-empty">No se pudo cargar la agenda.</div>';
            return;
        }

        const data = await response.json();
        schedules = data.data || [];
        renderCalendar();
        renderScheduleList();
    }

    function findScheduleById(scheduleId) {
        return schedules.find((item) => String(item.id || "") === String(scheduleId || ""));
    }

    function setSubmitText(text) {
        if (submitButton) {
            submitButton.textContent = text;
        }
    }

    function editSchedule(item) {
        if (!canWriteSchedule || !item) {
            return;
        }

        editTarget = {
            roomId: item.room_id || "LAB-PC-01",
            id: item.id,
        };
        document.getElementById("room-id").value = item.room_id || "LAB-PC-01";
        if (sourceScheduleInput) {
            sourceScheduleInput.value = item.source_schedule_id || "";
        }
        kindSelect.value = scheduleKind(item);
        labelInput.value = displayScheduleLabel(item) || DEFAULT_CLASS_LABEL;
        dayInput.value = item.day_of_week || "monday";
        startInput.value = item.start_time || SCHOOL_START_TIME;
        endInput.value = item.end_time || "10:00";
        validFromInput.value = item.valid_from || "";
        validToInput.value = item.valid_to || "";
        statusSelect.value = item.status || "activo";
        setFormConstraints({
            editing: true,
            lockedDate: scheduleKind(item) === "no_class" ? (item.valid_from || item.valid_to || "") : "",
        });
        setModalMode(
            "Editar bloque",
            "Registro limitado",
            "Actualiza el bloque desde la ventana modal. Si editas una suspensión, se conserva la trazabilidad del registro."
        );
        setSubmitText("Actualizar");
        clearButton.textContent = "Cancelar";
        showMessage("Editando bloque seleccionado. Guarda para aplicar cambios.", "ok");
        openScheduleModal();
    }

    function prepareNoClassException(item, dateText) {
        if (!canWriteSchedule || !item) {
            return;
        }

        const selectedDate = dateText || visibleDateForDay(item.day_of_week);
        const existingException = findVisibleException(item, selectedDate);
        if (existingException) {
            editSchedule(existingException);
            showMessage("Ya existe una suspensión para esta fecha. Se abrió para edición.", "ok");
            return;
        }

        editTarget = null;
        document.getElementById("room-id").value = item.room_id || "LAB-PC-01";
        if (sourceScheduleInput) {
            sourceScheduleInput.value = item.id || "";
        }
        kindSelect.value = "no_class";
        labelInput.value = SUSPENSION_LABEL;
        dayInput.value = item.day_of_week || "monday";
        startInput.value = SCHOOL_START_TIME;
        endInput.value = SCHOOL_END_TIME;
        validFromInput.value = selectedDate;
        validToInput.value = selectedDate;
        statusSelect.value = "activo";
        setFormConstraints({
            editing: false,
            lockedDate: selectedDate,
        });
        setModalMode(
            "Nueva suspensi\u00f3n",
            "Registro limitado",
            "Para un paro, feriado o suspensi\u00f3n puntual, guarda una fecha visible. La lista agrupar\u00e1 la excepci\u00f3n con su bloque base."
        );
        setSubmitText("Guardar suspensi\u00f3n");
        clearButton.textContent = "Limpiar";
        showMessage("Se prepar\u00f3 un d\u00eda sin clase para la fecha visible. Guarda para registrar la excepci\u00f3n.", "ok");
        openScheduleModal();
    }

    function resetForm(clearMessage) {
        editTarget = null;
        form.reset();
        document.getElementById("room-id").value = "LAB-PC-01";
        if (sourceScheduleInput) {
            sourceScheduleInput.value = "";
        }
        kindSelect.value = "class";
        labelInput.value = DEFAULT_CLASS_LABEL;
        dayInput.value = "monday";
        startInput.value = SCHOOL_START_TIME;
        endInput.value = "10:00";
        validFromInput.value = "";
        validToInput.value = "";
        statusSelect.value = "activo";
        setFormConstraints({
            editing: false,
            lockedDate: "",
        });
        setModalMode(
            "Nuevo bloque",
            "Registro limitado",
            "Agrega un horario recurrente de uso del laboratorio o registra una suspensi\u00f3n puntual para una fecha visible."
        );
        setSubmitText("Guardar");
        clearButton.textContent = "Limpiar";
        if (clearMessage !== false && messageBox) {
            messageBox.className = "schedule-message";
            messageBox.textContent = "";
        }
    }

    function applyKindDefaults() {
        if (kindSelect.value === "no_class") {
            if (!labelInput.value || normalizeScheduleLabel(labelInput.value) === DEFAULT_CLASS_LABEL) {
                labelInput.value = NO_CLASS_LABEL;
            }
            startInput.value = SCHOOL_START_TIME;
            endInput.value = SCHOOL_END_TIME;
            const visibleDate = validFromInput.value || validToInput.value || todayLocalText();
            validFromInput.value = visibleDate;
            validToInput.value = visibleDate;
            setFormConstraints({
                editing: Boolean(editTarget),
                lockedDate: "",
            });
            return;
        }

        if (!labelInput.value || labelInput.value === NO_CLASS_LABEL || labelInput.value === SUSPENSION_LABEL) {
            labelInput.value = DEFAULT_CLASS_LABEL;
        }
        if (startInput.value === SCHOOL_START_TIME && endInput.value === SCHOOL_END_TIME) {
            endInput.value = "10:00";
        }
        setFormConstraints({
            editing: Boolean(editTarget),
            lockedDate: "",
        });
    }

    function validateClientPayload(payload, isEditing) {
        const today = todayLocalText();
        const currentSchedule = isEditing && editTarget ? findScheduleById(editTarget.id) : null;

        if (!payload.kind) {
            return "Debes seleccionar un tipo de bloque.";
        }

        if (!payload.day_of_week) {
            return "Debes seleccionar un d\u00eda de la semana.";
        }

        if (!payload.label || !String(payload.label).trim()) {
            return "El nombre visible es obligatorio.";
        }

        if (!payload.start_time || !payload.end_time) {
            return "Debes completar la hora de inicio y la hora de fin.";
        }

        const startMinutes = parseMinutes(payload.start_time);
        const endMinutes = parseMinutes(payload.end_time);

        if (startMinutes >= endMinutes) {
            return "La hora inicial debe ser menor que la hora final.";
        }

        if (startMinutes < SCHOOL_START_MINUTES || endMinutes > SCHOOL_END_MINUTES) {
            return `El horario debe ubicarse entre ${SCHOOL_START_TIME} y ${SCHOOL_END_TIME}.`;
        }

        if (payload.label && /[0-9]/.test(payload.label)) {
            return "El nombre visible no debe incluir n\u00fameros.";
        }

        if (payload.valid_from && payload.valid_to && payload.valid_from > payload.valid_to) {
            return "La fecha inicial no puede ser mayor que la fecha final.";
        }

        if (payload.kind === "no_class") {
            if (!payload.valid_from || !payload.valid_to) {
                return "Para un d\u00eda sin clase coloca una vigencia. Para un feriado, usa la misma fecha en inicio y fin.";
            }
            if (payload.valid_from !== payload.valid_to) {
                return "La suspensi\u00f3n debe usar la misma fecha en inicio y fin.";
            }
        }

        if (payload.valid_from && (!currentSchedule || payload.valid_from !== String(currentSchedule.valid_from || "")) && payload.valid_from < today) {
            return "La vigencia no puede iniciar en una fecha pasada.";
        }

        if (payload.valid_to && (!currentSchedule || payload.valid_to !== String(currentSchedule.valid_to || "")) && payload.valid_to < today) {
            return "La vigencia no puede cerrar en una fecha pasada.";
        }
        return "";
    }

    async function revokeSchedule(item) {
        if (!canWriteSchedule || !item) {
            return;
        }

        if (!window.confirm("Confirmar la revocaci\u00f3n de esta suspensi\u00f3n?")) {
            return;
        }

        const response = await fetch(
            `/api/data/schedule/${encodeURIComponent(item.room_id || "LAB-PC-01")}/${encodeURIComponent(item.id)}`,
            {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    ...AUTH_HEADER,
                },
                body: JSON.stringify({ status: "inactivo" }),
            }
        );

        if (SafyraAuth.handleProtectedResponse(response)) {
            return;
        }

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            showMessage(data.detail || "No se pudo revocar la suspensi\u00f3n.", "error");
            return;
        }

        showMessage("Suspensi\u00f3n revocada correctamente.", "ok");
        resetForm(false);
        await loadSchedules();
    }

    function handleClearAction() {
        if (editTarget) {
            resetForm(false);
            closeScheduleModal();
            return;
        }

        resetForm();
    }

    async function saveSchedule(event) {
        event.preventDefault();
        if (!canWriteSchedule) {
            showMessage("Solo Direcci\u00f3n puede registrar o modificar horarios.", "error");
            return;
        }

        enforceLabelRules();
        const timeRulesOk = enforceTimeRules();
        const dateRulesOk = enforceDateRules();
        if (!timeRulesOk || !dateRulesOk) {
            return;
        }

        const formData = new FormData(form);
        const payload = {
            room_id: formData.get("room_id"),
            kind: formData.get("kind"),
            day_of_week: formData.get("day_of_week"),
            start_time: formData.get("start_time"),
            end_time: formData.get("end_time"),
            label: sanitizeVisibleLabel(formData.get("label")),
            valid_from: formConstraints.lockedDate || formData.get("valid_from") || null,
            valid_to: formConstraints.lockedDate || formData.get("valid_to") || null,
            status: formData.get("status"),
            source_schedule_id: formData.get("source_schedule_id") || null,
        };

        const isEditing = Boolean(editTarget && editTarget.id);
        const clientError = validateClientPayload(payload, isEditing);
        if (clientError) {
            showMessage(clientError, "error");
            return;
        }

        const currentKind = isEditing && editTarget ? scheduleKind(findScheduleById(editTarget.id) || {}) : null;
        if (payload.kind === "no_class" && payload.status === "activo" && currentKind !== "no_class" && !window.confirm("Confirmar el registro de esta suspensi\u00f3n?")) {
            return;
        }

        const url = isEditing
            ? `/api/data/schedule/${encodeURIComponent(editTarget.roomId)}/${encodeURIComponent(editTarget.id)}`
            : "/api/data/schedule";
        const method = isEditing ? "PATCH" : "POST";

        if (isEditing) {
            delete payload.room_id;
        }

        const response = await fetch(url, {
            method,
            headers: {
                "Content-Type": "application/json",
                ...AUTH_HEADER,
            },
            body: JSON.stringify(payload),
        });

        if (SafyraAuth.handleProtectedResponse(response)) {
            return;
        }

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            showMessage(data.detail || "No se pudo guardar el horario.", "error");
            return;
        }

        resetForm(false);
        showMessage(isEditing ? "Bloque actualizado correctamente." : "Bloque registrado correctamente.", "ok");
        closeScheduleModal();
        await loadSchedules();
    }

    function handleListAction(event) {
        const actionButton = event.target.closest("[data-list-action]");
        if (!actionButton) {
            return;
        }

        const item = findScheduleById(actionButton.dataset.scheduleId);
        if (actionButton.dataset.listAction === "edit") {
            editSchedule(item);
            return;
        }

        if (actionButton.dataset.listAction === "suspend-visible") {
            prepareNoClassException(item, actionButton.dataset.dayDate);
            return;
        }

        if (actionButton.dataset.listAction === "revoke") {
            revokeSchedule(item);
        }
    }

    function applyRoleMode(currentUser) {
        canWriteSchedule = currentUser.role === WRITE_ROLE;

        if (canWriteSchedule) {
            if (openScheduleButton) {
                openScheduleButton.hidden = false;
            }
            if (readonlyPanel) {
                readonlyPanel.hidden = true;
            }
            return;
        }

        if (openScheduleButton) {
            openScheduleButton.hidden = true;
        }
        if (readonlyPanel) {
            readonlyPanel.hidden = false;
        }
    }

    document.addEventListener("DOMContentLoaded", async function () {
        const currentUser = await SafyraAuth.requireRoles(["admin", "auditor"]);
        if (!currentUser) {
            return;
        }

        loadTheme();
        populateTimeSelect(startInput);
        populateTimeSelect(endInput);
        applyRoleMode(currentUser);
        form.addEventListener("submit", saveSchedule);
        kindSelect.addEventListener("change", applyKindDefaults);
        labelInput.addEventListener("beforeinput", blockLabelDigits);
        labelInput.addEventListener("input", enforceLabelRules);
        labelInput.addEventListener("paste", filterLabelPaste);
        labelInput.addEventListener("blur", enforceLabelRules);
        startInput.addEventListener("input", enforceTimeRules);
        startInput.addEventListener("change", enforceTimeRules);
        endInput.addEventListener("input", enforceTimeRules);
        endInput.addEventListener("change", enforceTimeRules);
        validFromInput.addEventListener("input", enforceDateRules);
        validFromInput.addEventListener("change", enforceDateRules);
        validToInput.addEventListener("input", enforceDateRules);
        validToInput.addEventListener("change", enforceDateRules);
        validFromInput.addEventListener("focus", applyFormConstraints);
        validToInput.addEventListener("focus", applyFormConstraints);
        scheduleList.addEventListener("click", handleListAction);
        if (openScheduleButton) {
            openScheduleButton.addEventListener("click", () => {
                resetForm(false);
                openScheduleModal();
            });
        }
        if (closeModalButton) {
            closeModalButton.addEventListener("click", closeScheduleModal);
        }
        if (modalBackdrop) {
            modalBackdrop.addEventListener("click", closeScheduleModal);
        }
        if (modalDialog) {
            modalDialog.addEventListener("click", (event) => {
                if (event.target === modalDialog) {
                    closeScheduleModal();
                }
            });
        }
        window.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && modal && !modal.hidden) {
                closeScheduleModal();
            }
        });
        if (refreshListButton) {
            refreshListButton.addEventListener("click", loadSchedules);
        }
        clearButton.addEventListener("click", handleClearAction);
        document.getElementById("prev-week").addEventListener("click", () => {
            currentWeekStart = addDays(currentWeekStart, -7);
            renderCalendar();
        });
        document.getElementById("next-week").addEventListener("click", () => {
            currentWeekStart = addDays(currentWeekStart, 7);
            renderCalendar();
        });
        document.getElementById("today-week").addEventListener("click", () => {
            currentWeekStart = startOfWeek(new Date());
            renderCalendar();
        });

        renderCalendar();
        await loadSchedules();
    });
})();
