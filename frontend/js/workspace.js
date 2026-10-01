/** Center workspace: chat, code area and diff view. */
import { h, statusBadge, timeAgo, clock } from "./ui.js";

const STAGE_LABELS = ["understand", "inspect", "plan", "execute", "test", "inspect_errors", "fix", "retest", "verify"];

function renderStages(state) {
  const stages = state.stages?.length
    ? state.stages
    : STAGE_LABELS.map((id) => ({ id, label: id.replace("_", " "), status: "pending", detail: "" }));
  const wrap = h("div", { class: "panel-section" },
    h("div", { class: "section-title" }, h("span", {}, "Activity"), 
      h("span", { class: "badge" }, `${stages.filter((s) => s.status === "succeeded").length}/${stages.length}`)));
  const list = h("div", { class: "stage-list", style: { padding: "0 12px 12px" } });
  for (const stage of stages) {
    list.append(h("div", { class: `stage ${["running"].includes(stage.status) ? "active" : ""}` },
      statusBadge(stage.status), h("span", { class: "ellipsis" }, stage.label)));
    if (stage.detail) list.append(h("div", { class: "stage detail" }, stage.detail));
  }
  wrap.append(list);
  return wrap;
}

function renderEnhancement(state, actions) {
  const enhancement = state.enhancement;
  if (!enhancement) return null;
  const editor = h("textarea", { class: "textarea", dataset: { field: "enhancement" }, style: { minHeight: "140px" } }, enhancement.enhanced);
  editor.addEventListener("input", () => { enhancement.enhanced = editor.value; });
  return h("div", { class: "panel-section", style: { background: "var(--surface-2)" } },
    h("div", { class: "section-title" }, h("span", {}, "Enhanced specification"),
      h("span", { class: "badge accent" }, "review")),
    h("div", { style: { padding: "0 12px 12px" } },
      h("div", { class: "muted", style: { marginBottom: "6px", fontSize: "11px" } },
        `Original: ${enhancement.original.slice(0, 120)}`),
      editor,
      h("div", { class: "row wrap", style: { marginTop: "8px" } },
        h("button", { class: "btn primary sm", onclick: () => actions.acceptEnhancement() }, "Accept"),
        h("button", { class: "btn sm", onclick: () => actions.editEnhancement(editor.value) }, "Save edit"),
        h("button", { class: "btn sm", onclick: () => actions.undoEnhancement() }, "Undo"),
        h("button", { class: "btn danger sm", onclick: () => actions.rejectEnhancement() }, "Reject"))));
}

function renderPlan(state, actions) {
  const plan = state.plans;
  if (!plan?.tasks) return null;
  const source = plan.source ?? "deterministic";
  return h("div", { class: "panel-section", style: { background: "var(--surface-2)" } },
    h("div", { class: "section-title" }, h("span", {}, "Plan"),
      h("span", { class: `badge ${source === "ai" ? "accent" : "warn"}` }, source)),
    h("div", { style: { padding: "0 12px 12px" } },
      h("div", { style: { marginBottom: "8px" } }, plan.summary ?? ""),
      plan.note ? h("div", { class: "banner" }, h("div", {}, plan.note)) : null,
      h("ol", { style: { paddingLeft: "18px", display: "flex", flexDirection: "column", gap: "4px" } },
        ...plan.tasks.map((task) => h("li", {},
          h("strong", {}, task.title), task.description ? ` — ${task.description}` : ""))),
      h("div", { class: "row wrap", style: { marginTop: "10px" } },
        h("button", {
          class: "btn primary sm",
          onclick: () => actions.runAgent(state.promptDraft || plan.summary || "Build the plan", "build"),
        }, "Approve & build"),
        h("button", { class: "btn sm", onclick: () => actions.runPlan(state.promptDraft || plan.summary) }, "Re-plan"),
        h("button", { class: "btn danger sm", onclick: () => actions.setState?.({ plans: null }) }, "Reject"))));
}

function renderMessages(state) {
  const scroll = h("div", { class: "chat-scroll" });
  if (!state.messages.length) {
    scroll.append(h("div", { class: "empty-state" },
      h("div", {},
        h("div", { class: "big" }, "Describe what you want to build"),
        h("div", {}, "NEXORA will enhance the prompt, plan the work, build files and verify results."),
        h("div", { class: "muted", style: { marginTop: "10px", fontFamily: "var(--mono)", fontSize: "11px" } },
          "Try: “Create a simple React task manager with a clean dashboard.”"))));
    return scroll;
  }
  for (const message of state.messages) {
    const isError = message.meta?.error;
    scroll.append(h("div", { class: `msg ${message.role} ${isError ? "error" : ""}` },
      h("div", { class: "avatar" }, message.role === "user" ? "YOU" : "NX"),
      h("div", { class: "grow" },
        h("div", { class: "bubble" }, message.content),
        message.meta?.model
          ? h("div", { class: "meta" }, `${message.meta.provider} · ${message.meta.model}`)
          : null)));
  }
  return scroll;
}

function renderComposer(state, actions) {
  const textarea = h("textarea", { dataset: { field: "composer" }, placeholder: "Describe a feature, or ask about the project…" });
  textarea.value = state.promptDraft ?? "";
  textarea.addEventListener("input", () => actions.setPromptDraft(textarea.value));
  textarea.addEventListener("keydown", (event) => {
    if (event.ctrlKey && !event.shiftKey && event.key === "Enter") {
      event.preventDefault();
      actions.sendMessage(textarea.value);
      actions.setPromptDraft("");
    }
  });

  return h("div", { class: "composer" },
    h("div", { class: "composer-row" },
      textarea,
      h("div", { class: "composer-actions" },
        h("button", { class: "btn sm", onclick: () => actions.enhancePrompt(textarea.value) }, "Enhance"),
        h("button", { class: "btn primary sm", onclick: () => { actions.sendMessage(textarea.value); actions.setPromptDraft(""); } }, "Send"),
        h("button", { class: "btn sm", onclick: () => actions.runPlan(textarea.value) }, "Plan"),
        h("button", { class: "btn sm", onclick: () => actions.runAgent(textarea.value, "build") }, "Build"))),
    h("div", { class: "composer-hint" },
      h("span", {}, h("kbd", {}, state.settings?.shortcut_enhance ?? "Ctrl+Shift+E"), " enhance"),
      h("span", {}, h("kbd", {}, state.settings?.shortcut_send ?? "Ctrl+Enter"), " send"),
      h("span", { class: "muted" }, state.busy ? `${state.busy}…` : "")));
}

function renderChatTab(state, actions) {
  return h("div", { class: "chat" },
    renderMessages(state),
    renderEnhancement(state, actions),
    renderPlan(state, actions),
    renderComposer(state, actions));
}

function renderCodeTab(state, actions, editorHost) {
  const wrap = h("div", { class: "col", style: { height: "100%", minHeight: "0", gap: "0" } });
  const bar = h("div", { class: "toolbar" });
  bar.append(
    h("span", { class: "mono", style: { fontSize: "11.5px" } }, state.activePath ?? "no file"),
    state.dirty ? h("span", { class: "badge warn" }, "unsaved") : null,
  );
  bar.append(h("div", { class: "spacer" }));
  if (state.activePath) {
    bar.append(
      h("button", { class: "btn sm primary", onclick: () => actions.saveActiveFile() }, "Save"),
      h("button", { class: "btn sm", onclick: () => actions.openModal({ type: "renameFile", path: state.activePath }) }, "Rename"),
      h("button", { class: "btn sm danger", onclick: () => actions.openModal({ type: "deleteFile", path: state.activePath }) }, "Delete"),
    );
  }
  wrap.append(bar);
  if (!state.activePath) {
    wrap.append(h("div", { class: "empty-state" },
      h("div", {}, h("div", { class: "big" }, "No file open"),
        h("div", {}, "Open a file from the Files panel to edit it here."))));
  } else {
    wrap.append(editorHost);
  }
  return wrap;
}

function renderDiffTab(state) {
  const body = h("div", { class: "pane-body", style: { height: "100%" } });
  const diff = state.diff;
  if (!diff || !diff.files?.length) {
    body.append(h("div", { class: "empty-state" },
      h("div", {}, h("div", { class: "big" }, "No changes recorded"),
        h("div", {}, "Diffs are computed from real stored file versions."))));
    return body;
  }
  body.append(h("div", { class: "row wrap", style: { marginBottom: "10px" } },
    h("span", { class: "badge" }, `${diff.changedCount} changed`),
    h("span", { class: "badge ok" }, `+${diff.additions}`),
    h("span", { class: "badge err" }, `-${diff.deletions}`)));
  for (const file of diff.files) {
    const lines = h("div", { class: "diff-body" });
    for (const line of (file.diff ?? "").split("\n")) {
      const kind = line.startsWith("+") && !line.startsWith("+++") ? "add"
        : line.startsWith("-") && !line.startsWith("---") ? "del"
        : line.startsWith("@@") ? "hunk" : "";
      lines.append(h("div", { class: `diff-line ${kind}` }, line));
    }
    body.append(h("div", { class: "diff-file" },
      h("div", { class: "diff-head" },
        h("span", { class: "badge" }, file.change),
        h("span", { class: "grow ellipsis" }, file.path),
        h("span", { class: "badge ok" }, `+${file.additions}`),
        h("span", { class: "badge err" }, `-${file.deletions}`)),
      lines));
  }
  return body;
}

export function renderCenter(state, actions, editorHost) {
  const pane = h("div", { class: "pane center" });
  const tabs = h("div", { class: "tabs" });
  const centerTabs = [
    { id: "chat", label: "AI conversation" },
    { id: "code", label: "Code" },
    { id: "diff", label: "Diff" },
    { id: "activity", label: "Plan / Build / Fix / Verify" },
  ];
  for (const tab of centerTabs) {
    tabs.append(h("button", {
      class: `tab ${state.centerTab === tab.id ? "active" : ""}`,
      onclick: () => actions.setCenterTab(tab.id),
    }, tab.label));
  }
  tabs.append(h("div", { style: { flex: "1" } }));
  for (const path of state.openFiles ?? []) {
    tabs.append(h("button", { class: `tab ${state.activePath === path ? "active" : ""}`, onclick: () => actions.openFile(path) },
      h("span", { class: "ellipsis", style: { maxWidth: "140px" } }, path.split("/").pop()),
      h("span", { class: "close", onclick: (event) => { event.stopPropagation(); actions.closeFile(path); } }, "✕")));
  }
  pane.append(tabs);

  const body = h("div", { style: { flex: "1", minHeight: "0", display: "flex", flexDirection: "column" } });
  if (state.centerTab === "chat") body.append(renderChatTab(state, actions));
  else if (state.centerTab === "code") body.append(renderCodeTab(state, actions, editorHost));
  else if (state.centerTab === "diff") body.append(renderDiffTab(state));
  else body.append(h("div", { class: "pane-body" },
    renderStages(state),
    h("div", { class: "panel-section" },
      h("div", { class: "section-title" }, h("span", {}, "Task status")),
      h("div", { style: { padding: "0 12px 12px" } },
        state.tasks.length
          ? h("div", { class: "stack-sm" }, ...state.tasks.map((task) =>
              h("div", { class: "row wrap" }, statusBadge(task.state),
                h("span", {}, task.title), h("span", { class: "muted mono", style: { fontSize: "10.5px" } },
                  `${task.stage} · ${timeAgo(task.updated_at)}`))))
          : h("div", { class: "muted" }, "No tasks yet — run Plan or Build.")))),
  );
  pane.append(body);
  return pane;
}
