/** API client — thin wrappers over the NEXORA HTTP API. */

async function request(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { detail: text };
  }
  if (!response.ok) {
    const message = payload?.detail || `${response.status} ${response.statusText}`;
    const error = new Error(typeof message === "string" ? message : JSON.stringify(message));
    error.status = response.status;
    throw error;
  }
  return payload;
}

const pid = (projectId) => `/api/projects/${projectId}`;

export const api = {
  health: () => request("GET", "/api/health"),
  system: () => request("GET", "/api/system"),
  tools: () => request("GET", "/api/tools"),

  // projects
  listProjects: (search = "") =>
    request("GET", `/api/projects?search=${encodeURIComponent(search)}`),
  createProject: (body) => request("POST", "/api/projects", body),
  getProject: (id) => request("GET", pid(id)),
  updateProject: (id, body) => request("PATCH", pid(id), body),
  deleteProject: (id) => request("DELETE", pid(id)),

  // files
  listFiles: (id) => request("GET", `${pid(id)}/files`),
  readFile: (id, path) => request("GET", `${pid(id)}/file?path=${encodeURIComponent(path)}`),
  writeFile: (id, path, content) => request("PUT", `${pid(id)}/file`, { path, content }),
  createFile: (id, path, content = "") => request("POST", `${pid(id)}/file`, { path, content }),
  createDirectory: (id, path) => request("POST", `${pid(id)}/directory`, { path }),
  renameFile: (id, path, newPath) => request("POST", `${pid(id)}/rename`, { path, new_path: newPath }),
  deleteFile: (id, path) => request("DELETE", `${pid(id)}/file?path=${encodeURIComponent(path)}`),
  searchFiles: (id, term, content = false) =>
    request("GET", `${pid(id)}/search?term=${encodeURIComponent(term)}&content=${content}`),
  refresh: (id) => request("POST", `${pid(id)}/refresh`),

  // ai
  messages: (id) => request("GET", `${pid(id)}/messages`),
  chat: (id, message, role = "coding") => request("POST", `${pid(id)}/chat`, { message, role }),
  enhance: (id, prompt) => request("POST", `${pid(id)}/enhance`, { prompt }),
  plan: (id, text) => request("POST", `${pid(id)}/plan`, { request: text }),
  agent: (id, body) => request("POST", `${pid(id)}/agent`, body),

  // runtime state
  tasks: (id) => request("GET", `${pid(id)}/tasks`),
  verifications: (id) => request("GET", `${pid(id)}/verifications`),
  diff: (id) => request("GET", `${pid(id)}/diff`),
  memory: (id) => request("GET", `${pid(id)}/memory`),

  // terminal + preview
  terminal: (id, command, timeout = 120) =>
    request("POST", `${pid(id)}/terminal`, { command, timeout }),
  previewStatus: (id) => request("GET", `${pid(id)}/preview`),
  previewStart: (id, command = null) => request("POST", `${pid(id)}/preview`, { command }),
  previewStop: (id) => request("DELETE", `${pid(id)}/preview`),

  // settings
  settings: () => request("GET", "/api/settings"),
  saveSettings: (body) => request("PUT", "/api/settings", body),
};
