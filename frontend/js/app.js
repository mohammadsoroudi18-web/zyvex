/** Application shell: layout, rendering, resizing, shortcuts. */
import { h, clear } from "./ui.js";
import { getState, setState, subscribe } from "./store.js";
import { actions, applyAppearance } from "./actions.js";
import { mountEditor, languageForPath } from "./editor.js";
import { renderSidebar, renderRightPanel, renderBottomPanel, renderModal, renderToasts } from "./components.js";
import { renderCenter } from "./workspace.js";
import { renderSettings, renderFirstRun } from "./settings.js";

const root = document.getElementById("root");

// Persistent editor host so the Monaco instance survives re-renders.
const editorHost = h("div", { class: "editor-host" });
let editor = null;
let editorPath = null;

function ensureEditor() {
  if (editor) return editor;
  editor = mountEditor(editorHost, {
    onChange: (value) => {
      if (value !== getState().fileDraft) actions.setDraft(value);
    },
  });
  return editor;
}

function syncEditor(state) {
  if (state.centerTab !== "code" || !state.activePath) return;
  const instance = ensureEditor();
  instance.setTheme(document.documentElement.dataset.theme);
  if (editorPath !== state.activePath) {
    instance.setValue(state.fileDraft ?? "");
    instance.setLanguage(languageForPath(state.activePath));
    editorPath = state.activePath;
  }
}

/** Rebuild a region while preserving focus/caret in text inputs. */
function rebuildPreservingFocus(container, builder) {
  const active = document.activeElement;
  const inside = active && container.contains(active) &&
    ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName);
  const snapshot = inside
    ? { field: active.dataset.field, value: active.value, start: active.selectionStart, end: active.selectionEnd }
    : null;

  clear(container);
  builder(container);

  if (snapshot?.field) {
    const restored = container.querySelector(`[data-field="${snapshot.field}"]`);
    if (restored) {
      if ("value" in restored) restored.value = snapshot.value;
      restored.focus();
      try { restored.setSelectionRange(snapshot.start, snapshot.end); } catch { /* not a text input */ }
    }
  }
}

// ------------------------------------------------------------- shell ----- //

const topbar = h("div", { class: "topbar" });
const sidebarSlot = h("div", { style: { display: "contents" } });
const centerSlot = h("div", { style: { display: "contents" } });
const rightSlot = h("div", { style: { display: "contents" } });
const bottomSlot = h("div", { style: { display: "contents" } });
const overlaySlot = h("div", {});
const toastsSlot = h("div", {});

const splitLeft = h("div", { class: "splitter vertical", style: { left: "calc(var(--sidebar-w) - 2px)" } });
const splitRight = h("div", { class: "splitter vertical", style: { right: "calc(var(--right-w) - 2px)" } });
const splitBottom = h("div", { class: "splitter horizontal", style: { bottom: "calc(var(--bottom-h) - 2px)" } });

const workspace = h("div", { class: "workspace" },
  sidebarSlot, centerSlot, rightSlot, bottomSlot, splitLeft, splitRight, splitBottom);

const shell = h("div", { class: "col", style: { height: "100%", gap: "0" } }, topbar, workspace);
root.append(shell, overlaySlot, toastsSlot);

// ---------------------------------------------------------- rendering ---- //

const regionKeys = { sidebar: "", center: "", right: "", bottom: "", top: "" };

function keyOf(...parts) {
  return parts.map((part) => JSON.stringify(part ?? null)).join("|");
}

function renderTopbar(state) {
  const key = keyOf(state.project?.id, state.project?.name, state.aiAvailable, state.settings?.theme, state.projects.length);
  if (key === regionKeys.top) return;
  regionKeys.top = key;
  rebuildPreservingFocus(topbar, (container) => {
    container.append(
      h("div", { class: "brand" }, h("span", { class: "brand-mark" }, "N"), "NEXORA AI Builder",
        h("span", { class: "brand-sub" }, "workspace")),
      h("div", { class: "topbar-spacer" }),
      state.project
        ? h("div", { class: "project-chip" },
            h("span", { class: `dot`, style: { background: state.project.status === "error" ? "var(--err)" : "var(--ok)" } }),
            h("strong", { class: "ellipsis", style: { maxWidth: "200px" } }, state.project.name))
        : null,
      h("span", { class: `badge ${state.aiAvailable ? "ok" : "warn"}` },
        state.aiAvailable ? "AI ready" : "AI not configured"),
      h("div", { class: "row mobile-nav" },
        h("button", { class: "btn ghost sm", onclick: () => toggleMobile("show-sidebar") }, "Panels"),
        h("button", { class: "btn ghost sm", onclick: () => toggleMobile("show-right") }, "Inspector")),
      h("button", {
        class: "btn ghost sm",
        title: "Toggle theme",
        onclick: () => actions.setTheme(state.settings?.theme === "light" ? "dark" : "light"),
      }, state.settings?.theme === "light" ? "☾" : "☀"),
      h("button", { class: "btn ghost sm", onclick: () => actions.setView(state.view === "settings" ? "workspace" : "settings") }, "⚙"),
      h("button", { class: "btn ghost sm", onclick: () => actions.loadProjects() }, "⟳"),
    );
  });
}

function toggleMobile(cls) {
  workspace.classList.toggle(cls);
}

function renderSidebarRegion(state) {
  const key = keyOf(state.nav, state.project?.id, state.projects.length, state.files.length,
    state.searchTerm, state.searchResults?.length, state.diff?.changedCount, state.updatedTick);
  if (key === regionKeys.sidebar) return;
  regionKeys.sidebar = key;
  rebuildPreservingFocus(sidebarSlot, (container) => container.append(renderSidebar(state, actions)));
}

function renderCenterRegion(state) {
  const key = keyOf(state.centerTab, state.activePath, state.dirty, state.openFiles.join(","),
    state.messages.length, state.messages.at(-1)?.id, state.stages.map((s) => `${s.id}:${s.status}:${s.detail}`).join(","),
    state.plans ? JSON.stringify(state.plans.tasks?.length ?? 0) + (state.plans.source ?? "") : null,
    state.enhancement ? state.enhancement.enhanced.length : null,
    state.tasks.length, state.busy);
  if (key === regionKeys.center) return;
  regionKeys.center = key;
  rebuildPreservingFocus(centerSlot, (container) => container.append(renderCenter(state, actions, editorHost)));
  syncEditor(state);
}

function renderRightRegion(state) {
  const key = keyOf(state.project?.id, state.preview?.running, state.preview?.url, state.tasks.length,
    state.verifications.length, state.aiAvailable, state.settings?.provider,
    state.files.length, state.project?.status, state.project?.current_task, state.system?.capabilities);
  if (key === regionKeys.right) return;
  regionKeys.right = key;
  rebuildPreservingFocus(rightSlot, (container) => container.append(renderRightPanel(state, actions)));
}

function renderBottomRegion(state) {
  const key = keyOf(state.bottomTab, state.terminalLines.length, state.logs.length, state.errors.length,
    state.activity.length, state.tasks.length, state.project?.id);
  if (key === regionKeys.bottom) return;
  regionKeys.bottom = key;
  rebuildPreservingFocus(bottomSlot, (container) => container.append(renderBottomPanel(state, actions)));
}

function renderOverlay(state) {
  clear(overlaySlot);
  const modal = renderModal(state, actions);
  if (modal) overlaySlot.append(modal);
}

function renderToastsRegion(state) {
  clear(toastsSlot);
  const toasts = renderToasts(state);
  if (toasts) toastsSlot.append(toasts);
}

function render(state) {
  const showWorkspace = state.view === "workspace" && (state.project || state.projects.length);

  if (state.view === "firstrun") {
    clear(centerSlot);
    clear(sidebarSlot);
    clear(rightSlot);
    clear(bottomSlot);
    clear(topbar);
    regionKeys.sidebar = regionKeys.center = regionKeys.right = regionKeys.bottom = regionKeys.top = "hidden";
    centerSlot.append(h("div", { style: { gridArea: "sidebar / sidebar / bottom / center" } }, renderFirstRun(state, actions)));
    workspace.classList.add("no-right", "no-bottom");
  } else if (state.view === "settings") {
    clear(centerSlot);
    clear(sidebarSlot);
    clear(rightSlot);
    clear(bottomSlot);
    regionKeys.sidebar = regionKeys.center = regionKeys.right = regionKeys.bottom = "hidden";
    renderTopbar(state);
    centerSlot.append(h("div", { style: { gridColumn: "1 / -1", gridRow: "1 / -1", overflow: "auto" } }, renderSettings(state, actions)));
    workspace.classList.add("no-right", "no-bottom");
  } else {
    workspace.classList.remove("no-right", "no-bottom");
    workspace.style.setProperty("--sidebar-w", `${state.layout.sidebar}px`);
    workspace.style.setProperty("--right-w", state.layout.showRight ? `${state.layout.right}px` : "0px");
    workspace.style.setProperty("--bottom-h", state.layout.showBottom ? `${state.layout.bottom}px` : "0px");
    renderTopbar(state);
    renderSidebarRegion(state);
    renderCenterRegion(state);
    renderRightRegion(state);
    if (state.layout.showBottom) renderBottomRegion(state);
    else { clear(bottomSlot); regionKeys.bottom = "hidden"; }
    if (!state.project) {
      clear(centerSlot);
      regionKeys.center = "hidden";
      centerSlot.append(h("div", { style: { display: "contents" } }, h("div", { class: "pane center" },
        h("div", { class: "empty-state" }, h("div", {},
          h("div", { class: "big" }, "No project open"),
          h("div", {}, "Open a project from the sidebar or create a new one."),
          h("button", { class: "btn primary", style: { marginTop: "12px" }, onclick: () => actions.openModal({ type: "newProject" }) }, "Create project"))))));
    }
  }

  renderOverlay(state);
  renderToastsRegion(state);
  applyAppearance(state.settings ?? {});
}

// ---------------------------------------------------------- resizing ----- //

function makeDraggable(handle, onMove) {
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    const startX = event.clientX;
    const startY = event.clientY;
    const onPointerMove = (moveEvent) => onMove(moveEvent.clientX - startX, moveEvent.clientY - startY);
    const onPointerUp = () => {
      handle.releasePointerCapture(event.pointerId);
      handle.removeEventListener("pointermove", onPointerMove);
      handle.removeEventListener("pointerup", onPointerUp);
    };
    handle.addEventListener("pointermove", onPointerMove);
    handle.addEventListener("pointerup", onPointerUp);
  });
}

makeDraggable(splitLeft, (dx) => {
  const layout = getState().layout;
  actions.setLayout({ sidebar: Math.min(460, Math.max(180, layout.sidebar + dx)) });
  regionKeys.sidebar = "";
});
makeDraggable(splitRight, (dx) => {
  const layout = getState().layout;
  actions.setLayout({ right: Math.min(560, Math.max(240, layout.right - dx)) });
  regionKeys.right = "";
});
makeDraggable(splitBottom, (dy) => {
  const layout = getState().layout;
  actions.setLayout({ bottom: Math.min(520, Math.max(120, layout.bottom - dy)) });
  regionKeys.bottom = "";
});

// --------------------------------------------------------- shortcuts ----- //

window.addEventListener("keydown", (event) => {
  const state = getState();
  if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "e") {
    event.preventDefault();
    actions.enhancePrompt(state.promptDraft);
  }
  if (event.key === "Escape" && state.modal) actions.closeModal();
});

// ------------------------------------------------------------- boot ----- //

subscribe((state) => render(state));

actions.boot().then(() => render(getState())).catch((error) => {
  root.append(h("div", { style: { padding: "24px", color: "var(--err)" } },
    `Failed to start NEXORA: ${error.message}`));
});
