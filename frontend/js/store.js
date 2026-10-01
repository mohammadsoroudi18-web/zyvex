/** Application store — single source of truth with a tiny pub/sub. */

const state = {
  booted: false,
  system: null,
  settings: null,
  projects: [],
  project: null,
  files: [],
  openFiles: [],
  activePath: null,
  fileDraft: null,
  dirty: false,
  messages: [],
  conversation: null,
  tasks: [],
  verifications: [],
  stages: [],
  diff: null,
  preview: null,
  memory: null,
  aiAvailable: false,
  busy: null,
  nav: "projects",
  centerTab: "chat",
  bottomTab: "terminal",
  terminalLines: [],
  logs: [],
  errors: [],
  activity: [],
  searchTerm: "",
  searchResults: null,
  modal: null,
  plans: null,
  toast: null,
  layout: { sidebar: 248, right: 320, bottom: 220, showRight: true, showBottom: true },
  view: "workspace",
};

const listeners = new Set();

export function getState() {
  return state;
}

export function setState(patch) {
  Object.assign(state, patch);
  for (const listener of listeners) listener(state);
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function pushLog(kind, message) {
  const entry = { kind, message, at: Date.now() / 1000 };
  const logs = [entry, ...state.logs].slice(0, 200);
  const patch = { logs };
  if (kind === "error") patch.errors = [entry, ...state.errors].slice(0, 100);
  setState(patch);
}

export function pushActivity(label, detail = "", status = "info") {
  setState({
    activity: [{ label, detail, status, at: Date.now() / 1000 }, ...state.activity].slice(0, 120),
  });
}

export function pushTerminal(line) {
  setState({ terminalLines: [...state.terminalLines, line].slice(-500) });
}
