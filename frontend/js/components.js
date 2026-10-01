/** Reusable UI components: sidebar, right panel, bottom panel, modal, toasts. */
import { h, icon, clear, statusBadge, timeAgo, clock } from "./ui.js";

const NAV = [
  { id: "projects", label: "Projects", glyph: "▤" },
  { id: "files", label: "Files", glyph: "❏" },
  { id: "search", label: "Search", glyph: "⌕" },
  { id: "git", label: "Git", glyph: "⎇" },
  { id: "settings", label: "Settings", glyph: "⚙" },
];

function buildTree(files) {
  const root = { children: new Map() };
  for (const file of files) {
    const parts = file.path.split("/");
    let node = root;
    for (let index = 0; index < parts.length; index += 1) {
      const name = parts[index];
      const isLeaf = index === parts.length - 1;
      if (!node.children.has(name)) {
        node.children.set(name, { name, children: new Map(), isDir: isLeaf ? file.isDir : true, path: parts.slice(0, index + 1).join("/") });
      }
      node = node.children.get(name);
    }
  }
  const sort = (node) => {
    const children = [...node.children.values()].sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    children.forEach(sort);
    node.sorted = children;
    return node;
  };
  sort(root);
  return root;
}

function renderTreeNode(node, depth, state, actions) {
  const rows = [];
  for (const child of node.sorted ?? []) {
    const isActive = state.activePath === child.path;
    const row = h(
      "button",
      {
        class: `tree-item ${isActive ? "active" : ""}`,
        style: { paddingLeft: `${8 + depth * 12}px` },
        onclick: () => {
          if (child.isDir) return;
          actions.openFile(child.path);
        },
        oncontextmenu: (event) => {
          event.preventDefault();
          if (child.isDir) return;
          actions.openModal({ type: "renameFile", path: child.path });
        },
      },
      icon(child.isDir ? "▸" : "·"),
      h("span", { class: "ellipsis" }, child.name),
    );
    rows.push(row);
    if (child.isDir && child.sorted?.length) {
      rows.push(...renderTreeNode(child, depth + 1, state, actions));
    }
  }
  return rows;
}

function renderProjectsNav(state, actions) {
  const body = h("div", { class: "pane-body" });
  body.append(
    h("div", { class: "searchbox", style: { marginBottom: "10px" } },
      icon("⌕"),
      h("input", {
        class: "input", placeholder: "Search projects",
        dataset: { field: "projectSearch" },
        value: state.projectSearch ?? "",
        oninput: (event) => actions.loadProjects(event.target.value),
      }),
    ),
    h("button", { class: "btn primary block", onclick: () => actions.openModal({ type: "newProject" }) },
      "+ New project"),
    h("div", { style: { height: "10px" } }),
  );

  if (!state.projects.length) {
    body.append(h("div", { class: "muted", style: { padding: "8px" } }, "No projects yet."));
  }

  for (const project of state.projects) {
    const active = state.project?.id === project.id;
    body.append(
      h("button", { class: `list-row ${active ? "active" : ""}`, onclick: () => actions.openProject(project.id) },
        h("div", { class: "grow" },
          h("div", { class: "row" },
            h("strong", { class: "ellipsis" }, project.name),
            h("span", { class: "badge" }, project.template === "react_vite_ts" ? "React" : "Empty"),
          ),
          h("div", { class: "meta ellipsis" }, project.description || "No description"),
          h("div", { class: "meta" }, `updated ${timeAgo(project.updated_at)}`),
        ),
        h("div", { class: "col", style: { gap: "4px" } },
          h("button", {
            class: "btn ghost sm", title: "Rename",
            onclick: (event) => { event.stopPropagation(); actions.openModal({ type: "renameProject", project }); },
          }, "✎"),
          h("button", {
            class: "btn ghost sm", title: "Delete",
            onclick: (event) => { event.stopPropagation(); actions.openModal({ type: "deleteProject", project }); },
          }, "🗑"),
        ),
      ),
    );
  }
  return body;
}

function renderFilesNav(state, actions) {
  const body = h("div", { class: "pane-body" });
  if (!state.project) {
    body.append(h("div", { class: "muted" }, "Open a project to browse files."));
    return body;
  }

  body.append(
    h("div", { class: "row wrap", style: { marginBottom: "8px" } },
      h("button", { class: "btn sm", onclick: () => actions.openModal({ type: "newFile" }) }, "+ File"),
      h("button", { class: "btn sm", onclick: () => actions.openModal({ type: "newFolder" }) }, "+ Folder"),
      h("button", { class: "btn sm", onclick: () => actions.refreshFiles() }, "⟳"),
    ),
  );

  if (!state.files.length) {
    body.append(h("div", { class: "muted" }, "No files yet. Create one to get started."));
    return body;
  }

  const tree = buildTree(state.files);
  body.append(h("div", { class: "tree" }, ...renderTreeNode(tree, 0, state, actions)));
  return body;
}

function renderSearchNav(state, actions) {
  const body = h("div", { class: "pane-body" });
  if (!state.project) {
    body.append(h("div", { class: "muted" }, "Open a project to search."));
    return body;
  }
  body.append(
    h("div", { class: "searchbox", style: { marginBottom: "10px" } },
      icon("⌕"),
      h("input", {
        class: "input", placeholder: "Search paths and contents",
        dataset: { field: "fileSearch" },
        value: state.searchTerm ?? "",
        oninput: (event) => actions.search(event.target.value),
      }),
    ),
  );
  if (state.searchResults === null) {
    body.append(h("div", { class: "muted" }, "Type to search the project."));
    return body;
  }
  if (!state.searchResults.length) {
    body.append(h("div", { class: "muted" }, "No matches."));
    return body;
  }
  for (const match of state.searchResults) {
    body.append(
      h("button", { class: "tree-item", onclick: () => actions.openFile(match.path) },
        icon("·"), h("span", { class: "ellipsis" }, match.path)),
    );
  }
  return body;
}

function renderGitNav(state, actions) {
  const body = h("div", { class: "pane-body" });
  const diff = state.diff;
  if (!diff) {
    body.append(h("div", { class: "muted" }, "No change data."));
    return body;
  }
  body.append(
    h("div", { class: "row wrap", style: { marginBottom: "10px" } },
      h("span", { class: "badge" }, `${diff.changedCount} files`),
      h("span", { class: "badge ok" }, `+${diff.additions}`),
      h("span", { class: "badge err" }, `-${diff.deletions}`),
    ),
    h("button", { class: "btn sm block", onclick: () => actions.setCenterTab("diff") }, "Open diff view"),
    h("div", { style: { height: "8px" } }),
  );
  for (const file of diff.files ?? []) {
    body.append(
      h("button", { class: "tree-item", onclick: () => { actions.openFile(file.path); } },
        h("span", { class: "badge" }, file.change),
        h("span", { class: "ellipsis" }, file.path)),
    );
  }
  return body;
}

function renderSettingsNav(state, actions) {
  return h("div", { class: "pane-body" },
    h("button", { class: "btn primary block", onclick: () => actions.setView("settings") }, "Open settings"),
    h("div", { style: { height: "10px" } }),
    h("div", { class: "muted" }, "Theme, accent, AI provider, model and shortcuts."),
  );
}

export function renderSidebar(state, actions) {
  const pane = h("div", { class: "pane sidebar" });
  const rail = h("div", { class: "navrail" });
  for (const item of NAV) {
    rail.append(
      h("button", {
        class: `navrail-item ${state.nav === item.id ? "active" : ""}`,
        onclick: () => (item.id === "settings" ? actions.setView("settings") : actions.setNav(item.id)),
      }, icon(item.glyph), item.label),
    );
  }
  pane.append(rail);

  const header = h("div", { class: "pane-header" },
    h("span", {}, state.nav),
    state.project ? h("span", { class: "badge" }, state.project.name.slice(0, 18)) : null,
  );
  pane.append(header);

  const renderers = {
    projects: renderProjectsNav, files: renderFilesNav, search: renderSearchNav,
    git: renderGitNav, settings: renderSettingsNav,
  };
  pane.append((renderers[state.nav] ?? renderProjectsNav)(state, actions));
  return pane;
}

// --------------------------------------------------------------- right --- //

function panelSection(title, extra, ...children) {
  return h("div", { class: "panel-section" },
    h("div", { class: "section-title" }, h("span", {}, title), extra ?? null),
    ...children,
  );
}

export function renderRightPanel(state, actions) {
  const pane = h("div", { class: "pane rightpanel" });
  const preview = state.preview ?? { running: false };
  const project = state.project;

  const previewBody = h("div", { style: { padding: "0 12px 12px" } });
  if (!project) {
    previewBody.append(h("div", { class: "muted" }, "No project open."));
  } else if (preview.running) {
    previewBody.append(
      h("div", { class: "row", style: { marginBottom: "6px" } },
        h("span", { class: "badge ok" }, "running"),
        h("span", { class: "mono ellipsis", style: { fontSize: "11px" } }, preview.url ?? "")),
      h("div", { class: "row wrap" },
        h("a", { class: "btn sm", href: preview.url, target: "_blank", rel: "noopener" }, "Open"),
        h("button", { class: "btn sm danger", onclick: () => actions.stopPreview() }, "Stop")),
      h("div", { class: "mono muted", style: { marginTop: "6px", fontSize: "10.5px" } }, preview.command ?? ""),
    );
  } else {
    previewBody.append(
      h("div", { class: "banner info" },
        h("div", {},
          h("strong", {}, "Preview"),
          "Starts a real process for the open project when a runnable entry point exists.")),
      h("button", { class: "btn sm primary block", onclick: () => actions.startPreview() }, "Start preview"),
    );
  }

  pane.append(
    h("div", { class: "pane-header" }, h("span", {}, "Inspector"),
      h("button", { class: "btn ghost sm", onclick: () => actions.setLayout({ showRight: false }) }, "✕")),
    panelSection("Live Preview", null, previewBody),

    panelSection("Project Status", null,
      h("dl", { class: "kv" },
        h("dt", {}, "Name"), h("dd", {}, project?.name ?? "—"),
        h("dt", {}, "Template"), h("dd", {}, project?.template ?? "—"),
        h("dt", {}, "Status"), h("dd", {}, project?.status ?? "—"),
        h("dt", {}, "Files"), h("dd", {}, String(state.files.filter((f) => !f.isDir).length)),
        h("dt", {}, "Current task"), h("dd", {}, project?.current_task || "—"),
      )),

    panelSection("Agent Status", h("span", { class: `badge ${state.aiAvailable ? "ok" : "warn"}` },
      state.aiAvailable ? "AI ready" : "AI not configured"),
      h("div", { style: { padding: "0 12px 12px" } },
        h("div", { class: "muted", style: { marginBottom: "8px" } },
          state.system?.providers?.find((p) => p.id === state.settings?.provider)?.unavailable_reason
          ?? `Provider: ${state.settings?.provider ?? "—"} · Model: ${state.settings?.model || "default"}`),
        h("div", { class: "row wrap" },
          h("button", { class: "btn sm", onclick: () => actions.setNav("files") }, "Files"),
          h("button", { class: "btn sm", onclick: () => actions.setCenterTab("diff") }, "Diff"),
          h("button", { class: "btn sm", onclick: () => actions.setView("settings") }, "Configure")),
      )),

    panelSection("Verification", null,
      h("div", { style: { padding: "0 12px 12px", maxHeight: "220px", overflow: "auto" } },
        state.verifications.length
          ? h("div", { class: "stack-sm" }, ...state.verifications.slice(0, 25).map((v) =>
              h("div", { class: "row wrap", style: { alignItems: "flex-start" } },
                statusBadge(v.status),
                h("div", { class: "grow" },
                  h("div", { class: "ellipsis", style: { fontSize: "11.5px" } }, v.claim),
                  h("div", { class: "mono muted", style: { fontSize: "10px" } }, v.method)))))
          : h("div", { class: "muted" }, "No verification records yet."),
      )),
    panelSection("Tool Capabilities", null,
      h("div", { class: "row wrap", style: { padding: "0 12px 12px" } },
        ...Object.entries(state.system?.capabilities ?? {}).map(([name, available]) =>
          h("span", { class: `badge ${available ? "ok" : ""}` }, `${name} ${available ? "✓" : "✕"}`)))),
  );
  return pane;
}

// -------------------------------------------------------------- bottom --- //

const BOTTOM_TABS = [
  { id: "terminal", label: "Terminal" }, { id: "logs", label: "Logs" },
  { id: "errors", label: "Errors" }, { id: "activity", label: "Task activity" },
  { id: "tasks", label: "Tasks" },
];

export function renderBottomPanel(state, actions) {
  const pane = h("div", { class: "pane bottompanel" });
  const tabs = h("div", { class: "tabs-inline" });
  for (const tab of BOTTOM_TABS) {
    const count = tab.id === "errors" ? state.errors.length : tab.id === "tasks" ? state.tasks.length : null;
    tabs.append(h("button", {
      class: state.bottomTab === tab.id ? "active" : "",
      onclick: () => actions.setBottomTab(tab.id),
    }, tab.label, count ? h("span", { class: "badge", style: { marginLeft: "6px" } }, String(count)) : null));
  }
  tabs.append(h("div", { style: { flex: "1" } }));
  tabs.append(h("button", { class: "btn ghost sm", onclick: () => actions.setLayout({ showBottom: false }) }, "✕"));
  pane.append(tabs);

  if (state.bottomTab === "terminal") {
    pane.append(renderTerminal(state, actions));
  } else {
    const source =
      state.bottomTab === "logs" ? state.logs
      : state.bottomTab === "errors" ? state.errors
      : state.bottomTab === "activity" ? state.activity
      : null;
    const list = h("div", { class: "pane-body" });
    if (state.bottomTab === "tasks") {
      if (!state.tasks.length) list.append(h("div", { class: "muted" }, "No tasks recorded."));
      for (const task of state.tasks) {
        list.append(h("div", { class: "entry" },
          statusBadge(task.state),
          h("div", { class: "grow" },
            h("div", {}, task.title),
            h("div", { class: "mono muted", style: { fontSize: "10.5px" } },
              `stage ${task.stage} · attempt ${task.attempt}/${task.max_retries} · ${task.description?.slice(0, 90) ?? ""}`)),
          h("span", { class: "time" }, timeAgo(task.updated_at))));
      }
    } else {
      if (!source.length) list.append(h("div", { class: "muted" }, "Nothing yet."));
      for (const entry of source) {
        list.append(h("div", { class: "entry" },
          h("span", { class: "time" }, clock(entry.at)),
          h("span", { class: `badge ${entry.status === "error" || entry.kind === "error" ? "err" : entry.status === "succeeded" ? "ok" : ""}` },
            entry.label ?? entry.kind),
          h("div", { class: "grow" }, entry.detail ?? entry.message)));
      }
    }
    pane.append(list);
  }
  return pane;
}

function renderTerminal(state, actions) {
  const wrap = h("div", { class: "col", style: { flex: "1", minHeight: "0" } });
  const output = h("div", { class: "terminal" });
  if (!state.terminalLines.length) {
    output.append(h("div", { class: "meta" },
      "Real command execution inside the project workspace. Commands run in the sandbox container."));
  }
  for (const line of state.terminalLines) {
    output.append(h("div", { class: `line ${line.kind}` }, line.text));
  }
  wrap.append(output);

  const capabilities = state.system?.capabilities ?? {};
  const missing = Object.entries(capabilities).filter(([, available]) => !available).map(([name]) => name);
  if (missing.length) {
    wrap.append(h("div", { class: "banner", style: { margin: "8px 10px" } },
      h("div", {},
        h("strong", {}, "External execution backend required"),
        `Not available in this runner: ${missing.join(", ")}. Commands needing these runtimes will fail honestly.`)));
  }

  const input = h("input", { class: "input", dataset: { field: "terminal" }, placeholder: "Run a command (e.g. python3 -c \"print(1)\")" });
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    actions.runTerminal(input.value);
    input.value = "";
  });
  wrap.append(h("div", { class: "terminal-input" }, input,
    h("button", { class: "btn sm", onclick: () => { actions.runTerminal(input.value); input.value = ""; } }, "Run")));
  return wrap;
}

// --------------------------------------------------------------- modal --- //

function formField(label, input) {
  return h("div", { class: "field" }, h("label", {}, label), input);
}

export function renderModal(state, actions) {
  const modal = state.modal;
  if (!modal) return null;

  let title = "";
  let body = null;
  let footer = null;

  if (modal.type === "newProject") {
    title = "Create project";
    let template = state.settings?.default_template ?? "empty";
    const nameInput = h("input", { class: "input", dataset: { field: "newProjectName" }, placeholder: "My project", value: "" });
    const descriptionInput = h("textarea", { class: "textarea", dataset: { field: "newProjectDescription" }, placeholder: "What are you building?" });
    const grid = h("div", { class: "template-grid" });
    for (const item of state.system?.templates ?? []) {
      const card = h("button", {
        class: `template-card ${template === item.id ? "active" : ""}`,
        onclick: () => {
          template = item.id;
          [...grid.children].forEach((child) => child.classList.remove("active"));
          card.classList.add("active");
        },
      }, h("strong", {}, item.label), h("span", {}, item.description));
      grid.append(card);
    }
    body = h("div", {},
      h("div", { class: "banner info" },
        h("div", {}, h("strong", {}, "First run"),
          "Create your first project to open the developer workspace.")),
      formField("Name", nameInput),
      formField("Description", descriptionInput),
      formField("Template", grid));
    footer = h("div", { class: "modal-foot" },
      h("button", { class: "btn", onclick: () => actions.closeModal() }, "Cancel"),
      h("button", {
        class: "btn primary",
        onclick: () => actions.createProject({
          name: nameInput.value.trim() || "Untitled project",
          description: descriptionInput.value.trim(),
          template,
        }),
      }, "Create project"));
  }

  if (["newFile", "newFolder"].includes(modal.type)) {
    const isFolder = modal.type === "newFolder";
    title = isFolder ? "New folder" : "New file";
    const pathInput = h("input", { class: "input", dataset: { field: "newPath" }, placeholder: isFolder ? "src/components" : "src/app.tsx" });
    body = h("div", {}, formField("Path", pathInput),
      h("div", { class: "muted", style: { fontSize: "11px" } }, "Nested paths are created automatically."));
    footer = h("div", { class: "modal-foot" },
      h("button", { class: "btn", onclick: () => actions.closeModal() }, "Cancel"),
      h("button", {
        class: "btn primary",
        onclick: () => {
          const value = pathInput.value.trim();
          if (!value) return;
          isFolder ? actions.createFolder(value) : actions.createFile(value, "");
        },
      }, isFolder ? "Create folder" : "Create file"));
  }

  if (modal.type === "renameFile") {
    title = "Rename file";
    const pathInput = h("input", { class: "input", dataset: { field: "renamePath" }, value: modal.path });
    body = h("div", {}, formField("New path", pathInput));
    footer = h("div", { class: "modal-foot" },
      h("button", { class: "btn", onclick: () => actions.closeModal() }, "Cancel"),
      h("button", { class: "btn primary", onclick: () => actions.renameFile(modal.path, pathInput.value.trim()) }, "Rename"));
  }

  if (modal.type === "renameProject") {
    title = "Rename project";
    const nameInput = h("input", { class: "input", dataset: { field: "renameProjectName" }, value: modal.project.name });
    body = h("div", {}, formField("Name", nameInput));
    footer = h("div", { class: "modal-foot" },
      h("button", { class: "btn", onclick: () => actions.closeModal() }, "Cancel"),
      h("button", { class: "btn primary", onclick: () => actions.renameProject(modal.project.id, nameInput.value.trim()) }, "Save"));
  }

  if (modal.type === "deleteProject") {
    title = "Delete project";
    body = h("div", {},
      h("div", { class: "banner" },
        h("div", {}, h("strong", {}, "This cannot be undone"),
          `"${modal.project.name}" and all of its files, tasks and verification records will be deleted.`)));
    footer = h("div", { class: "modal-foot" },
      h("button", { class: "btn", onclick: () => actions.closeModal() }, "Cancel"),
      h("button", { class: "btn danger", onclick: () => actions.deleteProject(modal.project.id) }, "Delete project"));
  }

  if (modal.type === "deleteFile") {
    title = "Delete file";
    body = h("div", {}, h("div", { class: "banner" }, h("div", {}, h("strong", {}, "Delete this path"),
      `"${modal.path}" will be removed from the project.`)));
    footer = h("div", { class: "modal-foot" },
      h("button", { class: "btn", onclick: () => actions.closeModal() }, "Cancel"),
      h("button", { class: "btn danger", onclick: () => actions.deleteFile(modal.path) }, "Delete"));
  }

  if (!body) return null;

  return h("div", { class: "overlay", onclick: (event) => { if (event.target.classList.contains("overlay")) actions.closeModal(); } },
    h("div", { class: "modal" },
      h("div", { class: "modal-head" }, h("h2", {}, title),
        h("button", { class: "btn ghost sm", onclick: () => actions.closeModal() }, "✕")),
      h("div", { class: "modal-body" }, body),
      footer));
}

export function renderToasts(state) {
  if (!state.toast) return null;
  const { kind, message } = state.toast;
  return h("div", { class: "toasts" },
    h("div", { class: `toast ${kind}`, key: state.toast.id },
      h("span", { class: `badge ${kind === "err" ? "err" : "ok"}` }, kind === "err" ? "error" : "ok"),
      h("span", {}, message)));
}
