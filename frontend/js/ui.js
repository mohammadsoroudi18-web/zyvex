/** Minimal DOM helpers — a tiny `h()` hyperscript. */

export function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;
    else if (key === "text") node.textContent = value;
    else if (key === "style" && typeof value === "object") Object.assign(node.style, value);
    else if (key === "dataset" && typeof value === "object") Object.assign(node.dataset, value);
    else if (key.startsWith("on") && typeof value === "function")
      node.addEventListener(key.slice(2).toLowerCase(), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  append(node, children);
  return node;
}

export function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false || child === true) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export const icon = (glyph, extra = "") => h("span", { class: `icon ${extra}` }, glyph);

export function timeAgo(seconds) {
  if (!seconds) return "—";
  const delta = Math.max(0, Date.now() / 1000 - seconds);
  if (delta < 60) return `${Math.floor(delta)}s ago`;
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  return `${Math.floor(delta / 86400)}d ago`;
}

export const clock = (seconds) =>
  seconds ? new Date(seconds * 1000).toLocaleTimeString([], { hour12: false }) : "—";

export function statusBadge(status) {
  const map = {
    succeeded: "ok", verified: "ok", running: "info", planned: "accent",
    failed: "err", blocked: "warn", unverified: "warn", timed_out: "err",
    skipped: "", cancelled: "warn", pending: "",
  };
  return h("span", { class: `badge ${map[status] ?? ""}` }, String(status));
}
