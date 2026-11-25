"use strict";
const el = id => document.getElementById(id);
let active = null;
let page = 1;
let focused = null;
let pending = false;

const labels = {
  supplier_name: "Supplier", invoice_number: "Invoice number", invoice_date: "Invoice date",
  currency: "Currency", subtotal: "Subtotal", tax: "Tax", discount: "Discount", total: "Total",
  description: "Description", quantity: "Quantity", unit_price: "Unit price", line_amount: "Line amount",
};
const pathName = path => {
  const parts = path.split(".");
  return parts[0] === "line_items" && parts.length === 3
    ? "Line " + (Number(parts[1]) + 1) + " · " + labels[parts[2]]
    : labels[parts[1]] || "Line items";
};
const endpoint = () => "/api/invoices/" + active.id;

async function request(url, options) {
  const response = await fetch(url, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || "Request failed");
  return value;
}

function showPage(number, box = null) {
  page = Number(number);
  el("pages").value = String(page);
  const entry = active.pages.find(item => item.number === page);
  const url = endpoint() + "/page/" + page;
  if (el("image").getAttribute("src") !== url) el("image").src = url;
  el("page-info").textContent = [entry.engine, entry.rotation ? "Corrected " + entry.rotation + "° rotation" : null,
    entry.low_resolution ? "Low resolution" : null, entry.blank ? "Blank page" : null].filter(Boolean).join(" · ");
  el("ocr").textContent = entry.words.map(word => word.text).join(" ");
  const area = el("region");
  area.hidden = !box;
  if (box) {
    const [x1, y1, x2, y2] = box;
    Object.assign(area.style, {left: x1 * 100 + "%", top: y1 * 100 + "%",
      width: (x2 - x1) * 100 + "%", height: (y2 - y1) * 100 + "%"});
    const reveal = () => { if (!area.hidden) area.scrollIntoView({block: "nearest", inline: "nearest"}); };
    if (el("image").complete) reveal(); else el("image").addEventListener("load", reveal, {once: true});
  }
}
function focusEvidence(path, item) {
  focused = path;
  if (item.evidence) showPage(item.evidence.page, item.evidence.box);
  else showPage(page);
}
function find(path) {
  const [group, a, b] = path.split(".");
  return group === "header" ? active.current.header[a] : active.current.line_items[Number(a)]?.[b];
}

async function mutate(operation, data = {}) {
  if (pending) return;
  pending = true;
  el("review-message").textContent = "";
  try {
    active = await request(endpoint(), {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({operation, revision: active.revision, ...data})});
    if (operation === "remove_row") focused = null;
    render();
    el("review-message").textContent = operation === "correct" ? "Correction saved." :
      operation === "approve" ? "Approved. JSON and CSV are ready to export." : "Line items updated.";
  } catch (error) {
    el("review-message").textContent = error.message;
  } finally {
    pending = false;
  }
}

function fieldNode(path, item) {
  const box = document.createElement("div");
  box.className = "field" + (active.flags[path] ? " flagged" : "");
  box.dataset.path = path;
  const label = document.createElement("label");
  label.textContent = labels[path.split(".").at(-1)];
  const input = document.createElement("input");
  input.value = item.value ?? "";
  input.placeholder = "Missing";
  input.readOnly = active.status === "approved";
  input.addEventListener("focus", () => focusEvidence(path, item));
  input.addEventListener("change", () => mutate("correct", {path, value: input.value}));
  input.addEventListener("keydown", event => { if (event.key === "Enter") input.blur(); });
  label.append(input);
  const locate = document.createElement("button");
  locate.type = "button";
  locate.className = "locate";
  locate.textContent = item.evidence ? "Locate on page " + item.evidence.page : "No source region";
  locate.setAttribute("aria-label", "Locate " + pathName(path));
  locate.title = item.raw ?? "";
  locate.addEventListener("click", () => focusEvidence(path, item));
  box.append(label, locate);
  return box;
}

function list(id, values, item) {
  el(id).replaceChildren(...values.map(item));
}
function node(tag, value) {
  const element = document.createElement(tag);
  element.textContent = value;
  return element;
}
function render() {
  const approved = active.status === "approved";
  el("workspace").hidden = false;
  el("filename").textContent = active.source.filename;
  el("model").textContent = active.current.model + " · " + active.pages.length + " page(s)";
  el("status").textContent = approved ? (active.history.at(-1).event === "auto_approved" ? "Auto-approved" : "Approved") : "Needs review";
  el("status").classList.toggle("good", approved);
  for (const kind of ["json", "csv"]) {
    el(kind).hidden = !approved;
    el(kind).href = endpoint() + "/export/" + kind;
  }
  el("approval").hidden = approved;
  el("add").hidden = approved;
  const flags = Object.entries(active.flags);
  el("flag-count").textContent = flags.length + " flagged";
  list("flags", flags, ([path, reason]) => {
    const button = node("button", pathName(path) + " · " + reason);
    button.type = "button";
    button.onclick = () => {
      const target = [...document.querySelectorAll("[data-path]")].find(field => field.dataset.path === path);
      if (target) target.querySelector("input").focus();
      else el("items").scrollIntoView({block: "nearest"});
    };
    return button;
  });
  list("headers", Object.entries(active.current.header).sort((a, b) =>
    Number(Boolean(active.flags["header." + b[0]])) - Number(Boolean(active.flags["header." + a[0]]))),
    ([key, value]) => fieldNode("header." + key, value));
  list("items", active.current.line_items, (item, index) => {
    const row = node("div", "");
    row.className = "line";
    const head = node("div", "");
    head.className = "panel-head";
    head.append(node("strong", "Line " + (index + 1)));
    if (!approved) {
      const drop = node("button", "Remove line");
      drop.type = "button";
      drop.onclick = () => mutate("remove_row", {index});
      head.append(drop);
    }
    const fields = node("div", "");
    fields.className = "line-fields";
    fields.append(...Object.entries(item).map(([key, value]) => fieldNode("line_items." + index + "." + key, value)));
    row.append(head, fields);
    return row;
  });
  list("checks", [...active.checks].sort((a, b) => Number(b.status === "fail") - Number(a.status === "fail")), check => {
    const detail = check.status === "unavailable" ? "missing input" : "recorded " + check.actual + ", expected " + check.expected;
    const item = node("li", check.name + " · " + pathName(check.path) + " · " + detail);
    item.className = check.status;
    return item;
  });
  list("history", active.history, entry => node("li",
    entry.event.replaceAll("_", " ") + (entry.path ? " · " + pathName(entry.path) + " · "
      + (entry.before ?? "missing") + " → " + (entry.after ?? "missing") : "")
      + (entry.note ? " · " + entry.note : "") + " · " + new Date(entry.at).toLocaleTimeString()));
  list("pages", active.pages, item => {
    const option = node("option", String(item.number));
    option.value = String(item.number);
    return option;
  });
  const selected = focused && find(focused);
  showPage(selected?.evidence?.page ?? page, selected?.evidence?.box);
}

el("pages").addEventListener("change", event => { focused = null; showPage(event.target.value); });
el("add").onclick = () => mutate("add_row");
el("approve").onclick = () => mutate("approve", {note: el("note").value});
el("upload").addEventListener("submit", async event => {
  event.preventDefault();
  const file = el("file").files[0];
  if (!file) return;
  el("process").disabled = true;
  el("message").textContent = "Reading document and extracting fields…";
  try {
    active = await request("/api/invoices?method=" + encodeURIComponent(el("method").value), {
      method: "POST", headers: {"X-Invoice-Filename": encodeURIComponent(file.name)}, body: file,
    });
    page = 1;
    focused = null;
    el("note").value = "";
    el("review-message").textContent = "";
    el("message").textContent = "";
    render();
  } catch (error) {
    el("message").textContent = error.message;
  } finally {
    el("process").disabled = false;
  }
});

