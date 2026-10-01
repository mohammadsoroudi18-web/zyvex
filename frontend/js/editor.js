/** Code editor — a real editor is available immediately (plain text), and is
 *  upgraded in-place to Monaco when it can be fetched. The upgrade never blocks
 *  the workspace: if the CDN is unreachable the plain-text editor simply stays.
 */

const MONACO_VERSION = "0.52.2";
const VS_BASE = `https://cdn.jsdelivr.net/npm/monaco-editor@${MONACO_VERSION}/min/vs`;
const LOAD_TIMEOUT_MS = 8000;

let monacoPromise = null;

export function loadMonaco() {
  if (window.monaco) return Promise.resolve(window.monaco);
  if (monacoPromise) return monacoPromise;
  monacoPromise = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Monaco load timed out")), LOAD_TIMEOUT_MS);
    const settle = (fn, value) => { clearTimeout(timer); fn(value); };
    const loader = document.createElement("script");
    loader.src = `${VS_BASE}/loader.js`;
    loader.onload = () => {
      try {
        window.require.config({ paths: { vs: VS_BASE } });
        window.require(["vs/editor/editor.main"],
          () => settle(resolve, window.monaco),
          (error) => settle(reject, error));
      } catch (error) {
        settle(reject, error);
      }
    };
    loader.onerror = () => settle(reject, new Error("Monaco loader could not be fetched"));
    document.head.appendChild(loader);
  });
  return monacoPromise;
}

const LANGUAGE_BY_EXT = {
  py: "python", js: "javascript", jsx: "javascript", ts: "typescript", tsx: "typescript",
  json: "json", md: "markdown", html: "html", css: "css", scss: "scss", yml: "yaml",
  yaml: "yaml", sh: "shell", sql: "sql", go: "go", rs: "rust", java: "java", rb: "ruby",
};

export function languageForPath(path = "") {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  return LANGUAGE_BY_EXT[ext] ?? "plaintext";
}

/** Mounts an editor into `host` synchronously; upgrades to Monaco if possible. */
export function mountEditor(host, { onChange } = {}) {
  let mode = "plain";
  let language = "plaintext";
  let monacoApi = null;

  const textarea = document.createElement("textarea");
  textarea.className = "fallback";
  textarea.spellcheck = false;
  textarea.addEventListener("input", () => {
    if (mode === "plain") onChange?.(textarea.value);
  });
  host.append(textarea);

  const controller = {
    get kind() { return mode; },
    getValue: () => (mode === "plain" ? textarea.value : monacoApi.getValue()),
    setValue: (value) => {
      if (mode === "plain") textarea.value = value ?? "";
      else monacoApi.setValue(value);
    },
    setLanguage: (next) => {
      language = next || "plaintext";
      monacoApi?.setLanguage(language);
    },
    setTheme: (theme) => monacoApi?.setTheme(theme),
    focus: () => (mode === "plain" ? textarea.focus() : monacoApi.focus()),
  };

  loadMonaco()
    .then((monaco) => {
      const initialValue = textarea.value;
      const editor = monaco.editor.create(host, {
        value: initialValue,
        language,
        theme: document.documentElement.dataset.theme === "light" ? "vs" : "vs-dark",
        automaticLayout: true,
        minimap: { enabled: false },
        fontSize: 12.5,
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        scrollBeyondLastLine: false,
        renderLineHighlight: "line",
        padding: { top: 12, bottom: 12 },
        tabSize: 2,
      });
      let suppress = false;
      editor.onDidChangeModelContent(() => {
        if (suppress) return;
        onChange?.(editor.getValue());
      });
      monacoApi = {
        getValue: () => editor.getValue(),
        setValue: (value) => {
          suppress = true;
          editor.setValue(value ?? "");
          setTimeout(() => { suppress = false; }, 0);
        },
        setLanguage: (next) =>
          monaco.editor.setModelLanguage(editor.getModel(), next || "plaintext"),
        setTheme: (theme) => monaco.editor.setTheme(theme === "light" ? "vs" : "vs-dark"),
        focus: () => editor.focus(),
      };
      textarea.remove();
      mode = "monaco";
    })
    .catch(() => { /* keep the plain-text editor */ });

  return controller;
}
