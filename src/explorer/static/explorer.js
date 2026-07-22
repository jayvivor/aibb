// The explorer is a pure view over the sim's event log: every render fetches a
// replayed snapshot for the slider's turn and draws it. No state is kept here
// beyond the season's fixed geometry and the current selection.

const SVG_NS = "http://www.w3.org/2000/svg";

const state = {
    season: null,
    layout: {},        // room name -> {x, y, w, h}
    curIndex: 1,
    maxIndex: 1,
    marks: [],         // phase starts: {index, week_number, phase_number}
    running: false,
    turn: null,        // last fetched /api/turn payload
    selected: null,    // {kind: "houseguest"|"room", name}
};

const ROLE_BADGES = {
    "Head of Household": "HOH",
    "Nominee": "NOM",
    "Power of Veto": "POV",
    "Outgoing HOH": "oHOH",
    "Drawn for Veto": "drawn",
    "Winner": "WIN",
};


// ---- Layout: place rooms by their adjacencies with a small force simulation

function layoutRooms(season) {
    const names = season.rooms.map(r => r.name);
    const pos = {};
    names.forEach((name, i) => {
        const angle = (2 * Math.PI * i) / names.length;
        pos[name] = { x: 600 + 260 * Math.cos(angle), y: 340 + 180 * Math.sin(angle) };
    });

    const isNeighbor = {};
    season.adjacencies.forEach(([a, b]) => {
        isNeighbor[a + "|" + b] = true;
        isNeighbor[b + "|" + a] = true;
    });

    for (let step = 0; step < 600; step++) {
        const force = {};
        names.forEach(name => force[name] = { x: 0, y: 0 });

        for (const a of names) {
            for (const b of names) {
                if (a === b) continue;
                const dx = pos[b].x - pos[a].x;
                const dy = pos[b].y - pos[a].y;
                const dist = Math.max(Math.hypot(dx, dy), 1);
                // Everyone repels; neighbors also pull toward a fixed spacing
                const repel = -14000 / (dist * dist);
                force[a].x += repel * dx / dist;
                force[a].y += repel * dy / dist;
                if (isNeighbor[a + "|" + b]) {
                    const pull = 0.02 * (dist - 210);
                    force[a].x += pull * dx / dist;
                    force[a].y += pull * dy / dist;
                }
            }
        }

        const cool = 1 - step / 600;
        for (const name of names) {
            pos[name].x += Math.max(-14, Math.min(14, force[name].x)) * cool;
            pos[name].y += Math.max(-14, Math.min(14, force[name].y)) * cool;
        }
    }

    // Normalize into the viewBox and freeze as boxes
    const xs = names.map(n => pos[n].x);
    const ys = names.map(n => pos[n].y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const layout = {};
    names.forEach(name => {
        const nx = (pos[name].x - minX) / Math.max(maxX - minX, 1);
        const ny = (pos[name].y - minY) / Math.max(maxY - minY, 1);
        layout[name] = { x: 30 + nx * (1200 - 220 - 60), y: 24 + ny * (720 - 120 - 48), w: 220, h: 120 };
    });
    return layout;
}


// ---- Rendering

function el(tag, attrs, text) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const key in attrs) node.setAttribute(key, attrs[key]);
    if (text !== undefined) node.textContent = text;
    return node;
}

function centerOf(box) {
    return { x: box.x + box.w / 2, y: box.y + box.h / 2 };
}

function badgesFor(name, roles) {
    const badges = [];
    for (const role in ROLE_BADGES) {
        if ((roles[role] || []).includes(name)) badges.push(ROLE_BADGES[role]);
    }
    return badges;
}

function renderHouse() {
    const svg = document.getElementById("house-svg");
    svg.innerHTML = "";
    if (!state.season || !state.turn) return;
    const roles = state.turn.state.roles;
    const positions = state.turn.state.positions;

    // Adjacency lines under everything
    state.season.adjacencies.forEach(([a, b]) => {
        const ca = centerOf(state.layout[a]);
        const cb = centerOf(state.layout[b]);
        svg.appendChild(el("line", { x1: ca.x, y1: ca.y, x2: cb.x, y2: cb.y, class: "adjacency" }));
    });

    state.season.rooms.forEach(room => {
        const box = state.layout[room.name];
        const group = el("g", { class: "room" });
        const rect = el("rect", { x: box.x, y: box.y, width: box.w, height: box.h, rx: 8, class: "room-box" });
        rect.addEventListener("click", () => openPanel("room", room.name));
        group.appendChild(rect);
        group.appendChild(el("text", { x: box.x + 8, y: box.y + 16, class: "room-name" }, room.name));

        (positions[room.name] || []).forEach((name, i) => {
            const cx = box.x + 10 + (i % 3) * 70;
            const cy = box.y + 26 + Math.floor(i / 3) * 22;
            const chip = el("g", { class: "chip" });
            const badges = badgesFor(name, roles);
            const label = badges.length ? `${name} [${badges.join(",")}]` : name;
            chip.appendChild(el("rect", { x: cx, y: cy, width: 66, height: 18, rx: 9, class: "chip-box" + (badges.length ? " chip-titled" : "") }));
            chip.appendChild(el("text", { x: cx + 33, y: cy + 13, "text-anchor": "middle", class: "chip-name" }, label));
            chip.addEventListener("mousemove", event => showTooltip(event, name));
            chip.addEventListener("mouseleave", hideTooltip);
            chip.addEventListener("click", event => { event.stopPropagation(); openPanel("houseguest", name); });
            group.appendChild(chip);
        });
        svg.appendChild(group);
    });

    renderTray();
    renderLabel();
}

function renderTray() {
    const tray = document.getElementById("tray");
    const s = state.turn.state;
    const section = (title, names) => names.length
        ? `<div class="tray-section"><b>${title}</b> ${names.map(n => `<span class="tray-chip" data-name="${n}">${n}</span>`).join(" ")}</div>`
        : "";
    tray.innerHTML =
        section("Winner", s.winner ? [s.winner] : []) +
        section("Jury", s.jury) +
        section("Pre-jury", s.pre_jury);
    tray.querySelectorAll(".tray-chip").forEach(chip => {
        chip.addEventListener("click", () => openPanel("houseguest", chip.dataset.name));
    });
}

function phaseNameAt(index) {
    let current = null;
    for (const mark of state.marks) {
        if (mark.index > index) break;
        current = mark;
    }
    if (!current || !state.season) return "";
    const week = state.season.schedule[current.week_number - 1];
    const phase = week ? week.phases[current.phase_number - 1] : "";
    return { week: current.week_number, weekName: week ? week.name : "", phase };
}

function renderLabel() {
    const info = phaseNameAt(state.curIndex);
    document.getElementById("turn-label").textContent =
        info ? `Week ${info.week} \u00b7 ${info.phase} \u00b7 turn ${state.curIndex} / ${state.maxIndex}` : `turn ${state.curIndex}`;
}


// ---- Tooltip: the hovered player's observable actions this turn

function showTooltip(event, name) {
    const tooltip = document.getElementById("tooltip");
    const acted = state.turn.events.filter(e => e.actor === name);
    const lines = acted.length ? acted.map(e => e.description) : ["No observable action this turn."];
    tooltip.innerHTML = `<b>${name}</b><br>` + lines.map(l => `<div>${l}</div>`).join("");
    tooltip.style.left = (event.clientX + 14) + "px";
    tooltip.style.top = (event.clientY + 14) + "px";
    tooltip.classList.remove("hidden");
}

function hideTooltip() {
    document.getElementById("tooltip").classList.add("hidden");
}


// ---- Side panel: houseguest / room history up to the current turn

async function openPanel(kind, name) {
    state.selected = { kind, name };
    const panel = document.getElementById("side-panel");
    panel.classList.remove("hidden");
    document.getElementById("side-panel-title").textContent = `${name} \u2014 history to turn ${state.curIndex}`;
    const body = document.getElementById("side-panel-body");
    body.innerHTML = "loading\u2026";

    const response = await fetch(`/api/${kind}/${encodeURIComponent(name)}?upto=${state.curIndex}`);
    const payload = await response.json();
    body.innerHTML = "";
    if (payload.total > payload.events.length) {
        const note = document.createElement("div");
        note.className = "history-note";
        note.textContent = `showing the latest ${payload.events.length} of ${payload.total} events`;
        body.appendChild(note);
    }

    // Conversation events collapse into threads; everything else is chronological
    const threads = {};
    const items = [];
    payload.events.forEach(e => {
        if (e.convo_id) {
            if (!threads[e.convo_id]) {
                threads[e.convo_id] = [];
                items.push({ thread: e.convo_id });
            }
            threads[e.convo_id].push(e);
        } else {
            items.push({ event: e });
        }
    });

    items.forEach(item => {
        if (item.thread) {
            const events = threads[item.thread];
            const details = document.createElement("details");
            const whispers = events.filter(e => e.type === "WhisperedMessage").length;
            const summary = document.createElement("summary");
            summary.textContent = `Conversation (${events.length} events, ${whispers} whispers)`;
            details.appendChild(summary);
            events.forEach(e => details.appendChild(historyItem(e)));
            body.appendChild(details);
        } else {
            body.appendChild(historyItem(item.event));
        }
    });
    if (!items.length) body.textContent = "Nothing yet.";
}

function historyItem(e) {
    const div = document.createElement("div");
    div.className = "history-item " + e.type;
    div.textContent = e.description;
    div.title = "Jump to this turn";
    div.addEventListener("click", () => setIndex(e.index));
    return div;
}

document.getElementById("side-panel-close").addEventListener("click", () => {
    state.selected = null;
    document.getElementById("side-panel").classList.add("hidden");
});


// ---- Scrubbing

let fetchPending = null;

async function fetchTurn() {
    const index = state.curIndex;
    const response = await fetch(`/api/turn/${index}`);
    if (index !== state.curIndex) return;  // stale
    state.turn = await response.json();
    renderHouse();
    if (state.selected) openPanel(state.selected.kind, state.selected.name);
}

function setIndex(index) {
    state.curIndex = Math.max(1, Math.min(index, state.maxIndex));
    document.getElementById("turn-slider").value = state.curIndex;
    renderLabel();
    clearTimeout(fetchPending);
    fetchPending = setTimeout(fetchTurn, 60);
}

function stepPhase(direction) {
    const indices = state.marks.map(m => m.index);
    if (direction > 0) {
        const next = indices.find(i => i > state.curIndex);
        setIndex(next !== undefined ? next : state.maxIndex);
    } else {
        const before = indices.filter(i => i < state.curIndex);
        setIndex(before.length ? before[before.length - 1] : 1);
    }
}

document.getElementById("turn-slider").addEventListener("input", event => setIndex(Number(event.target.value)));
document.getElementById("prev-turn").addEventListener("click", () => setIndex(state.curIndex - 1));
document.getElementById("next-turn").addEventListener("click", () => setIndex(state.curIndex + 1));
document.getElementById("prev-phase").addEventListener("click", () => stepPhase(-1));
document.getElementById("next-phase").addEventListener("click", () => stepPhase(1));
document.addEventListener("keydown", event => {
    if (event.key === "ArrowLeft") event.shiftKey ? stepPhase(-1) : setIndex(state.curIndex - 1);
    if (event.key === "ArrowRight") event.shiftKey ? stepPhase(1) : setIndex(state.curIndex + 1);
});


// ---- Sim lifecycle

async function refreshStatus() {
    const response = await fetch("/api/status");
    const status = await response.json();
    state.running = status.running;
    state.marks = status.marks;
    const grew = status.max_index > state.maxIndex;
    state.maxIndex = Math.max(status.max_index, 1);
    document.getElementById("turn-slider").max = state.maxIndex;
    document.getElementById("status-text").textContent =
        status.error ? `error: ${status.error}` : (status.running ? `running\u2026 (${status.max_index} turns)` : `idle (${status.max_index} turns)`);
    if (grew && !state.turn) setIndex(1);
    renderLabel();
}

async function startRun(fresh) {
    // Any run against an existing season gets a fresh house server-side, so
    // always reload the season geometry and clear the view
    await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fresh }) });
    state.turn = null;
    state.selected = null;
    state.curIndex = 1;
    document.getElementById("side-panel").classList.add("hidden");
    await init();
}

document.getElementById("run-button").addEventListener("click", () => startRun(false));
document.getElementById("rerun-button").addEventListener("click", () => startRun(true));
document.getElementById("stop-button").addEventListener("click", () => fetch("/api/stop", { method: "POST" }));


// ---- Boot

async function init() {
    const response = await fetch("/api/season");
    state.season = await response.json();
    state.layout = layoutRooms(state.season);
    await refreshStatus();
    if (state.maxIndex > 1) { state.curIndex = Math.min(state.curIndex, state.maxIndex); fetchTurn(); }
}

setInterval(refreshStatus, 1500);
init();
