/** Settings page and first-run experience. */
import { h } from "./ui.js";

const ACCENTS = ["indigo", "emerald", "sky", "amber", "rose"];

function card(title, subtitle, ...children) {
  return h("section", { class: "panel-section", style: { border: "1px solid var(--border)", borderRadius: "10px", marginBottom: "14px" } },
    h("div", { class: "section-title" }, h("span", {}, title)),
    subtitle ? h("div", { class: "muted", style: { padding: "0 12px 10px", marginTop: "-4px" } }, subtitle) : null,
    h("div", { style: { padding: "0 12px 14px" } }, ...children));
}

function field(label, input) {
  return h("div", { class: "field" }, h("label", {}, label), input);
}

export function renderSettings(state, actions) {
  const settings = state.settings ?? {};
  const providers = state.system?.providers ?? [];
  const activeProvider = providers.find((provider) => provider.id === settings.provider) ?? {};

  const providerSelect = h("select", { class: "select" },
    ...providers.map((provider) => h("option", {
      value: provider.id, selected: provider.id === settings.provider,
    }, `${provider.label}${provider.available ? "" : " — not configured"}`)));
  providerSelect.addEventListener("change", () => actions.saveSettings({ provider: providerSelect.value }));

  const modelInput = h("input", { class: "input", dataset: { field: "model" }, value: settings.model ?? "", placeholder: activeProvider.default_model || "model id" });
  const baseUrlInput = h("input", { class: "input", dataset: { field: "baseUrl" }, value: settings.base_url ?? "", placeholder: activeProvider.default_base_url || "https://…" });
  const temperatureInput = h("input", { class: "input", dataset: { field: "temperature" }, type: "number", min: "0", max: "1", step: "0.1", value: settings.temperature ?? 0.2 });
  const maxTokensInput = h("input", { class: "input", dataset: { field: "maxTokens" }, type: "number", min: "256", step: "256", value: settings.max_tokens ?? 4096 });

  const keyBanner = activeProvider.requires_key
    ? (activeProvider.key_present
        ? h("div", { class: "banner info" }, h("div", {}, h("strong", {}, "Credential detected"),
            `${activeProvider.env_key} is present in the environment.`))
        : h("div", { class: "banner" }, h("div", {}, h("strong", {}, "External credential required"),
            `${activeProvider.env_key} is not configured. Add it as an app secret to enable AI features. Keys are read from the environment and are never stored in the database.`)))
    : null;

  const themeToggle = h("div", { class: "row" },
    h("button", { class: `btn sm ${settings.theme !== "light" ? "primary" : ""}`, onclick: () => actions.setTheme("dark") }, "Dark"),
    h("button", { class: `btn sm ${settings.theme === "light" ? "primary" : ""}`, onclick: () => actions.setTheme("light") }, "Light"));

  const accentRow = h("div", { class: "row wrap" },
    ...ACCENTS.map((accent) => h("button", {
      class: `btn sm ${settings.accent === accent ? "primary" : ""}`,
      onclick: () => actions.setAccent(accent),
    }, accent)));

  const enhanceShortcut = h("input", { class: "input", dataset: { field: "shortcutEnhance" }, value: settings.shortcut_enhance ?? "Ctrl+Shift+E" });
  const sendShortcut = h("input", { class: "input", dataset: { field: "shortcutSend" }, value: settings.shortcut_send ?? "Ctrl+Enter" });

  const templateSelect = h("select", { class: "select" },
    ...(state.system?.templates ?? []).map((template) => h("option", {
      value: template.id, selected: template.id === settings.default_template,
    }, template.label)));

  const capabilities = state.system?.capabilities ?? {};
  const backends = state.system?.externalBackends ?? [];

  const view = h("div", { class: "pane-body", style: { padding: "18px 20px", maxWidth: "820px", margin: "0 auto", width: "100%" } });

  view.append(
    h("div", { class: "row", style: { marginBottom: "14px" } },
      h("button", { class: "btn sm", onclick: () => actions.setView("workspace") }, "← Workspace"),
      h("strong", { style: { fontSize: "15px" } }, "Settings")),

    card("AI", "UI → AI Service → Provider → Model. Keys come from the platform's managed secret file.",
      keyBanner,
      field("Provider", providerSelect),
      field("Model", modelInput),
      field("Base URL (optional override)", baseUrlInput),
      h("div", { class: "row" },
        h("div", { style: { flex: "1" } }, field("Temperature", temperatureInput)),
        h("div", { style: { flex: "1" } }, field("Max tokens", maxTokensInput))),
      h("button", {
        class: "btn primary",
        onclick: () => actions.saveSettings({
          model: modelInput.value, base_url: baseUrlInput.value,
          temperature: Number(temperatureInput.value), max_tokens: Number(maxTokensInput.value),
        }),
      }, "Save AI settings")),

    card("Appearance", "Theme and accent.", field("Theme", themeToggle), field("Accent", accentRow)),

    card("Shortcuts", "Keyboard bindings used in the composer.",
      field("Enhance prompt", enhanceShortcut),
      field("Send prompt", sendShortcut),
      h("button", {
        class: "btn",
        onclick: () => actions.saveSettings({
          shortcut_enhance: enhanceShortcut.value, shortcut_send: sendShortcut.value,
        }),
      }, "Save shortcuts")),

    card("Project", "Defaults for new projects.", field("Default template", templateSelect),
      h("button", { class: "btn", onclick: () => actions.saveSettings({ default_template: templateSelect.value }) }, "Save project settings")),

    card("Capabilities & external execution",
      "What this environment can do for real, and what requires an external execution backend.",
      h("div", { class: "row wrap", style: { marginBottom: "10px" } },
        ...Object.entries(capabilities).map(([name, available]) =>
          h("span", { class: `badge ${available ? "ok" : ""}` }, `${name} ${available ? "available" : "missing"}`))),
      ...backends.map((backend) => h("div", { class: `banner ${backend.supported ? "info" : ""}`, style: { marginTop: "8px" } },
        h("div", {}, h("strong", {}, backend.label), backend.note)))),
  );

  return view;
}

export function renderFirstRun(state, actions) {
  const wrap = h("div", { style: { display: "grid", placeItems: "center", height: "100%", padding: "24px" } });
  const inner = h("div", { style: { maxWidth: "620px", width: "100%" } });
  inner.append(
    h("div", { style: { marginBottom: "18px" } },
      h("div", { class: "brand", style: { fontSize: "18px", marginBottom: "6px" } },
        h("span", { class: "brand-mark" }, "N"), "NEXORA AI Builder"),
      h("div", { class: "muted" }, "Prompt → Enhance → Understand → Plan → Build → Inspect → Files → Preview → Test → Fix → Verify. Create your first project to begin.")),
  );
  const grid = h("div", { class: "template-grid" });
  for (const template of state.system?.templates ?? []) {
    grid.append(h("button", {
      class: "template-card",
      onclick: () => actions.createProject({
        name: template.id === "react_vite_ts" ? "Task Manager" : "New Project",
        description: template.description,
        template: template.id,
      }),
    }, h("strong", {}, template.label), h("span", {}, template.description),
       h("span", { class: "badge accent", style: { marginTop: "6px" } }, "Create")));
  }
  inner.append(h("div", { style: { marginBottom: "8px", fontWeight: 600 } }, "Create your first project"), grid);
  inner.append(h("button", { class: "btn block", style: { marginTop: "12px" }, onclick: () => actions.openModal({ type: "newProject" }) },
    "Custom project (choose name and template)"));
  wrap.append(inner);
  return wrap;
}
