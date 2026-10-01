/** Actions — every state change funnels through here. */
import { api } from "./api.js";
import { getState, setState, pushLog, pushActivity, pushTerminal } from "./store.js";

let toastTimer = null;

export function toast(kind, message) {
  setState({ toast: { kind, message, id: Date.now() } });
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => setState({ toast: null }), 4200);
}

async function guard(label, fn, { quiet = false } = {}) {
  setState({ busy: label });
  try {
    const result = await fn();
    return result;
  } catch (error) {
    if (!quiet) {
      toast("err", error.message || String(error));
      pushLog("error", `${label} failed: ${error.message}`);
      pushActivity(label, error.message, "error");
    }
    return null;
  } finally {
    setState({ busy: null });
  }
}

export const actions = {
  async boot() {
    const [system, settingsPayload, projectList] = await Promise.all([
      api.system().catch(() => null),
      api.settings().catch(() => null),
      api.listProjects().catch(() => ({ projects: [] })),
    ]);
    const settings = settingsPayload?.settings ?? null;
    const aiAvailable = (system?.providers ?? []).some(
      (provider) => provider.id === settings?.provider && provider.available
    );
    setState({
      booted: true,
      system,
      settings,
      projects: projectList.projects ?? [],
      aiAvailable,
      view: (projectList.projects ?? []).length ? "workspace" : "firstrun",
    });
    if (settings) applyAppearance(settings);
  },

  async loadProjects(search = "") {
    const result = await api.listProjects(search).catch(() => ({ projects: [] }));
    setState({ projects: result.projects ?? [], projectSearch: search });
  },

  async openProject(id) {
    const payload = await guard("Opening project", () => api.getProject(id));
    if (!payload) return;
    setState({ project: payload.project, view: "workspace", centerTab: "chat" });
    await Promise.all([
      actions.refreshFiles(),
      actions.loadConversation(),
      actions.refreshRuntime(),
      actions.refreshDiff(),
      actions.refreshPreview(),
    ]);
    pushActivity("Project opened", payload.project.name, "info");
  },

  async createProject(body) {
    const payload = await guard("Creating project", () => api.createProject(body));
    if (!payload) return;
    setState({ modal: null });
    await actions.loadProjects();
    await actions.openProject(payload.project.id);
    toast("ok", `Project "${payload.project.name}" created`);
  },

  async renameProject(id, name) {
    await guard("Renaming project", async () => {
      await api.updateProject(id, { name });
      const state = getState();
      if (state.project?.id === id) {
        setState({ project: { ...state.project, name } });
      }
      await actions.loadProjects();
    });
    setState({ modal: null });
    toast("ok", "Project renamed");
  },

  async deleteProject(id) {
    await guard("Deleting project", async () => {
      await api.deleteProject(id);
      const state = getState();
      const patch = { modal: null };
      if (state.project?.id === id) {
        patch.project = null;
        patch.files = [];
        patch.openFiles = [];
        patch.activePath = null;
        patch.messages = [];
      }
      setState(patch);
      await actions.loadProjects();
      if (!getState().project) setState({ view: "firstrun" });
    });
    toast("ok", "Project deleted");
  },

  // ------------------------------------------------------------- files --- //
  async refreshFiles() {
    const state = getState();
    if (!state.project) return;
    const result = await guard("Refreshing files", () => api.listFiles(state.project.id), { quiet: true });
    if (result) setState({ files: result.files ?? [] });
  },

  async openFile(path) {
    const state = getState();
    if (!state.project) return;
    const payload = await guard("Opening file", () => api.readFile(state.project.id, path));
    if (!payload) return;
    const openFiles = state.openFiles.includes(path) ? state.openFiles : [...state.openFiles, path];
    setState({
      openFiles,
      activePath: path,
      fileDraft: payload.file.content ?? "",
      dirty: false,
      centerTab: "code",
    });
  },

  closeFile(path) {
    const state = getState();
    const openFiles = state.openFiles.filter((item) => item !== path);
    const activePath = state.activePath === path ? openFiles[openFiles.length - 1] ?? null : state.activePath;
    setState({ openFiles, activePath, dirty: false });
  },

  setDraft(value) {
    setState({ fileDraft: value, dirty: true });
  },

  async saveActiveFile() {
    const state = getState();
    if (!state.project || !state.activePath) return;
    const path = state.activePath;
    const content = state.fileDraft ?? "";
    const result = await guard("Saving file", () => api.writeFile(state.project.id, path, content));
    if (!result) return;
    setState({ dirty: false });
    await actions.refreshFiles();
    await actions.refreshDiff();
    toast("ok", `Saved ${path}`);
    pushActivity("File saved", path, "succeeded");
  },

  async createFile(path, content = "") {
    const state = getState();
    if (!state.project) return;
    const result = await guard("Creating file", () => api.createFile(state.project.id, path, content));
    if (!result) return;
    setState({ modal: null });
    await actions.refreshFiles();
    await actions.openFile(path);
    toast("ok", `Created ${path}`);
  },

  async createFolder(path) {
    const state = getState();
    if (!state.project) return;
    const result = await guard("Creating folder", () => api.createDirectory(state.project.id, path));
    if (!result) return;
    setState({ modal: null });
    await actions.refreshFiles();
    toast("ok", `Created ${path}/`);
  },

  async renameFile(path, newPath) {
    const state = getState();
    if (!state.project) return;
    const result = await guard("Renaming", () => api.renameFile(state.project.id, path, newPath));
    if (!result) return;
    setState({ modal: null });
    await actions.refreshFiles();
    toast("ok", `Renamed to ${newPath}`);
  },

  async deleteFile(path) {
    const state = getState();
    if (!state.project) return;
    await guard("Deleting", async () => {
      await api.deleteFile(state.project.id, path);
      setState({ modal: null });
      const openFiles = getState().openFiles.filter((item) => item !== path);
      const activePath = getState().activePath === path ? openFiles[openFiles.length - 1] ?? null : getState().activePath;
      setState({ openFiles, activePath });
      await actions.refreshFiles();
      await actions.refreshDiff();
    });
    toast("ok", `Deleted ${path}`);
  },

  async search(term) {
    const state = getState();
    setState({ searchTerm: term });
    if (!state.project || !term.trim()) {
      setState({ searchResults: null });
      return;
    }
    const result = await api.searchFiles(state.project.id, term, true).catch(() => null);
    if (result) setState({ searchResults: result.matches ?? [] });
  },

  async refreshWorkspace() {
    const state = getState();
    if (!state.project) return;
    await guard("Materialising workspace", async () => {
      const result = await api.refresh(state.project.id);
      toast("ok", `Workspace refreshed (${result.files} nodes)`);
    });
  },

  // ---------------------------------------------------------------- ai --- //
  async loadConversation() {
    const state = getState();
    if (!state.project) return;
    const payload = await api.messages(state.project.id).catch(() => null);
    if (payload) setState({ messages: payload.messages ?? [], conversation: payload.conversation });
  },

  async sendMessage(text) {
    const state = getState();
    if (!state.project || !text.trim()) return;
    const optimistic = {
      id: `local-${Date.now()}`, role: "user", content: text, created_at: Date.now() / 1000,
    };
    setState({ messages: [...state.messages, optimistic], centerTab: "chat" });
    pushActivity("Prompt sent", text.slice(0, 80), "info");
    const result = await guard("AI response", () => api.chat(state.project.id, text));
    if (!result) {
      await actions.loadConversation();
      return;
    }
    if (result.error) {
      toast("err", result.error);
      pushLog("error", result.error);
    }
    await actions.loadConversation();
  },

  async enhancePrompt(text) {
    const state = getState();
    if (!state.project) return;
    const original = text?.trim();
    if (!original) {
      toast("err", "Write a prompt first");
      return;
    }
    const result = await guard("Enhancing prompt", () => api.enhance(state.project.id, original));
    if (!result) return;
    setState({ enhancement: { original: result.original, enhanced: result.enhanced, history: [] } });
    pushActivity("Prompt enhanced", `${result.provider} · ${result.model}`, "succeeded");
  },

  acceptEnhancement() {
    const state = getState();
    if (!state.enhancement) return;
    setState({ promptDraft: state.enhancement.enhanced, enhancement: null });
    toast("ok", "Enhanced prompt accepted");
  },

  rejectEnhancement() {
    setState({ enhancement: null });
  },

  undoEnhancement() {
    const state = getState();
    const history = state.enhancement?.history ?? [];
    if (!history.length) {
      toast("err", "Nothing to undo");
      return;
    }
    const previous = history[history.length - 1];
    setState({
      enhancement: {
        ...state.enhancement,
        enhanced: previous,
        history: history.slice(0, -1),
      },
    });
  },

  editEnhancement(value) {
    const state = getState();
    if (!state.enhancement) return;
    setState({
      enhancement: {
        ...state.enhancement,
        history: [...(state.enhancement.history ?? []), state.enhancement.enhanced],
        enhanced: value,
      },
    });
  },

  async runPlan(text) {
    const state = getState();
    if (!state.project || !text?.trim()) return;
    const result = await guard("Planning", () => api.plan(state.project.id, text));
    if (!result) return;
    setState({ stages: result.stages ?? [], plans: result.plan });
    await actions.refreshRuntime();
    pushActivity("Plan generated", result.plan?.summary ?? "", "succeeded");
    pushLog("info", `Plan generated with ${result.tasks?.length ?? 0} tasks`);
  },

  async runAgent(text, mode = "build", role = "coding") {
    const state = getState();
    if (!state.project || !text?.trim()) return;
    const result = await guard("Agent run", () => api.agent(state.project.id, { request: text, mode, role }));
    if (!result) return;
    setState({ stages: result.stages ?? [], plans: result.plan ?? getState().plans, centerTab: "chat" });
    await Promise.all([actions.refreshRuntime(), actions.refreshFiles(), actions.refreshDiff(), actions.refreshPreview()]);
    const verified = (result.verifications ?? []).filter((v) => v.status === "verified").length;
    pushActivity("Agent run complete", `${verified} claims verified`, "succeeded");
    toast("ok", `Agent run finished — ${verified} verified claims`);
  },

  // ----------------------------------------------------------- runtime --- //
  async refreshRuntime() {
    const state = getState();
    if (!state.project) return;
    const [tasks, verifications, memory] = await Promise.all([
      api.tasks(state.project.id).catch(() => null),
      api.verifications(state.project.id).catch(() => null),
      api.memory(state.project.id).catch(() => null),
    ]);
    setState({
      tasks: tasks?.tasks ?? [],
      verifications: verifications?.verifications ?? [],
      memory: memory ?? null,
    });
  },

  async refreshDiff() {
    const state = getState();
    if (!state.project) return;
    const diff = await api.diff(state.project.id).catch(() => null);
    if (diff) setState({ diff });
  },

  async refreshPreview() {
    const state = getState();
    if (!state.project) return;
    const preview = await api.previewStatus(state.project.id).catch(() => null);
    if (preview) setState({ preview });
  },

  async runTerminal(command) {
    const state = getState();
    if (!state.project || !command.trim()) return;
    pushTerminal({ kind: "cmd", text: `$ ${command}` });
    const result = await guard("Command", () => api.terminal(state.project.id, command), { quiet: true });
    if (!result) {
      pushTerminal({ kind: "stderr", text: "Command could not be executed." });
      return;
    }
    if (result.stdout) pushTerminal({ kind: "stdout", text: result.stdout.trimEnd() });
    if (result.stderr) pushTerminal({ kind: "stderr", text: result.stderr.trimEnd() });
    pushTerminal({
      kind: "meta",
      text: `exit ${result.exitCode ?? "—"} · ${result.durationMs}ms · ${result.status}`,
    });
    pushLog(result.status === "succeeded" ? "info" : "error",
      `$ ${command} → ${result.status} (exit ${result.exitCode ?? "—"})`);
  },

  async startPreview() {
    const state = getState();
    if (!state.project) return;
    const result = await guard("Starting preview", () => api.previewStart(state.project.id));
    if (!result) return;
    setState({ preview: result });
    if (result.error) toast("err", result.error);
    else toast("ok", "Preview process started");
    pushActivity("Preview", result.running ? `running at ${result.url}` : result.error ?? "not running",
      result.running ? "succeeded" : "blocked");
  },

  async stopPreview() {
    const state = getState();
    if (!state.project) return;
    const result = await guard("Stopping preview", () => api.previewStop(state.project.id));
    if (result) setState({ preview: result });
    toast("ok", "Preview stopped");
  },

  // ---------------------------------------------------------- settings --- //
  async saveSettings(patch) {
    const result = await guard("Saving settings", () => api.saveSettings(patch));
    if (!result) return;
    setState({ settings: result.settings });
    applyAppearance(result.settings);
    const aiAvailable = (result.providers ?? []).some(
      (provider) => provider.id === result.settings.provider && provider.available
    );
    setState({ aiAvailable, system: { ...(getState().system ?? {}), providers: result.providers } });
    toast("ok", "Settings saved");
  },

  setTheme(theme) {
    setState({ settings: { ...(getState().settings ?? {}), theme } });
    applyAppearance({ ...(getState().settings ?? {}), theme });
    actions.saveSettings({ theme });
  },

  setAccent(accent) {
    setState({ settings: { ...(getState().settings ?? {}), accent } });
    applyAppearance({ ...(getState().settings ?? {}), accent });
    actions.saveSettings({ accent });
  },

  setNav(nav) {
    setState({ nav });
  },

  setCenterTab(tab) {
    setState({ centerTab: tab });
  },

  setBottomTab(tab) {
    setState({ bottomTab: tab });
  },

  openModal(modal) {
    setState({ modal });
  },

  closeModal() {
    setState({ modal: null });
  },

  setView(view) {
    setState({ view });
  },

  setLayout(patch) {
    setState({ layout: { ...getState().layout, ...patch } });
  },

  setPromptDraft(value) {
    setState({ promptDraft: value });
  },
};

export function applyAppearance(settings) {
  const root = document.documentElement;
  if (settings?.theme) root.dataset.theme = settings.theme;
  if (settings?.accent) root.dataset.accent = settings.accent;
}
