/* "Improve with AI" for the CV Generator. Sends the form (via window.CvApp from cv_app.js) to
 * the server, then shows the AI's suggestion: nothing changes until the user accepts it, and the
 * suggestion can be edited first. One button per section (summary, each job, skills) plus
 * "Make my whole CV professional", which opens a dialog to pick what to apply.
 * All user-visible text comes from data-text-* attributes on [data-cv-app]. */
(function () {
  "use strict";

  var root = document.querySelector("[data-cv-app]");
  if (!root || !window.CvApp) return;
  var app = window.CvApp;

  var isLoggedIn = root.dataset.loggedIn === "true";
  var TEXT = {
    working:       root.dataset.textAiWorking,
    left:          root.dataset.textAiLeft,
    noneLeftGuest: root.dataset.textAiNoneLeftGuest,
    noneLeftUser:  root.dataset.textAiNoneLeftUser,
    removed:       root.dataset.textAiRemoved,
    applied:       root.dataset.textAiApplied,
    nothing:       root.dataset.textAiNothing,
    networkError:  root.dataset.textNetworkError,
    genericError:  root.dataset.textGenericError,
    headline:      root.dataset.textHeadline,
    summary:       root.dataset.textSummary,
    skills:        root.dataset.textSkills,
    job:           root.dataset.textJob,
  };

  var usageEls = root.querySelectorAll("[data-ai-usage]");
  var cardTemplate = root.querySelector("[data-suggestion-template]");
  var dialog = root.querySelector("[data-ai-dialog]");
  var dialogItems = dialog.querySelector("[data-ai-dialog-items]");
  var dialogNote = dialog.querySelector("[data-ai-dialog-note]");
  var busy = false;
  var remaining = null;

  loadUsage();

  root.addEventListener("click", function (e) {
    var button = e.target.closest("[data-action]");
    if (!button) return;
    var action = button.dataset.action;
    if (action === "ai-improve") improveSection(button);
    else if (action === "ai-improve-all") improveAll(button);
    else if (action === "ai-dialog-close") dialog.close();
    else if (action === "ai-dialog-apply") applyDialog();
  });

  // ── One section ───────────────────────────────────────────────────────────

  function improveSection(button) {
    var section = button.dataset.section;
    var slot = button.closest("[data-ai-slot]");
    var body = { section: section, cv: app.collect() };
    var entry = null;
    if (section === "experience") {
      entry = button.closest("[data-entry]");
      body.index = app.entries("experience").indexOf(entry);
    }
    removeCard(slot);
    send(body, button).then(function (data) {
      if (!data) return;
      var suggestion = data.suggestion || {};
      var text = section === "summary" ? suggestion.summary
        : section === "experience" ? suggestion.description
        : (suggestion.skills || []).join(", ");
      if (!text) { app.toast(TEXT.nothing, "info"); return; }
      showCard(slot, text, data.removed, function (finalText) {
        if (section === "summary") app.setPath("summary", finalText);
        else if (section === "experience") app.setEntryField(entry, "description", finalText);
        else app.setSkills(splitSkills(finalText));
      });
    });
  }

  function showCard(slot, text, removed, onAccept) {
    var card = cardTemplate.content.firstElementChild.cloneNode(true);
    var textarea = card.querySelector("[data-suggestion-text]");
    var label = card.querySelector("[data-suggestion-label]");
    textarea.id = "cv-ai-" + Date.now();
    label.setAttribute("for", textarea.id);
    textarea.value = text;
    setNote(card.querySelector("[data-suggestion-note]"), removed);
    card.querySelector('[data-action="ai-accept"]').addEventListener("click", function () {
      onAccept(textarea.value.trim());
      card.remove();
      app.toast(TEXT.applied, "success");
    });
    card.querySelector('[data-action="ai-discard"]').addEventListener("click", function () { card.remove(); });
    slot.insertAdjacentElement("afterend", card);
    textarea.focus({ preventScroll: true });
    card.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
  }

  function removeCard(slot) {
    var next = slot.nextElementSibling;
    if (next && next.matches("[data-suggestion]")) next.remove();
  }

  // ── Whole CV ──────────────────────────────────────────────────────────────

  function improveAll(button) {
    send({ section: "all", cv: app.collect() }, button).then(function (data) {
      if (!data) return;
      var s = data.suggestion || {};
      var entries = app.entries("experience");
      dialogItems.innerHTML = "";
      if (s.headline) addDialogItem(TEXT.headline, s.headline, function (v) { app.setPath("personal.headline", v); }, 1);
      if (s.summary) addDialogItem(TEXT.summary, s.summary, function (v) { app.setPath("summary", v); }, 4);
      (s.experience || []).forEach(function (job) {
        var entry = entries[job.index];
        if (!entry) return;
        var title = entry.querySelector('[data-key="job_title"]').value || entry.querySelector('[data-key="company"]').value;
        var label = TEXT.job.replace("__N__", job.index + 1) + (title ? " · " + title : "");
        addDialogItem(label, job.description, function (v) { app.setEntryField(entry, "description", v); }, 5);
      });
      if (s.skills && s.skills.length) {
        addDialogItem(TEXT.skills, s.skills.join(", "), function (v) { app.setSkills(splitSkills(v)); }, 3);
      }
      if (!dialogItems.children.length) { app.toast(TEXT.nothing, "info"); return; }
      setNote(dialogNote, data.removed);
      dialog.showModal();
    });
  }

  function addDialogItem(labelText, text, apply, rows) {
    var id = "cv-ai-item-" + dialogItems.children.length;
    var item = document.createElement("div");
    item.className = "cv-ai-item";
    item.applyValue = apply;

    var head = document.createElement("label");
    head.className = "flex items-center gap-2 text-[13px] font-medium text-fg";
    var check = document.createElement("input");
    check.type = "checkbox";
    check.className = "cv-checkbox";
    check.checked = true;
    check.dataset.aiUse = "";
    var title = document.createElement("span");
    title.textContent = labelText;
    head.appendChild(check);
    head.appendChild(title);

    var textarea = document.createElement("textarea");
    textarea.className = "input cv-textarea";
    textarea.rows = rows;
    textarea.dir = "auto";
    textarea.id = id;
    textarea.value = text;
    textarea.setAttribute("aria-label", labelText);
    check.addEventListener("change", function () { textarea.disabled = !check.checked; });

    item.appendChild(head);
    item.appendChild(textarea);
    dialogItems.appendChild(item);
  }

  function applyDialog() {
    Array.prototype.forEach.call(dialogItems.children, function (item) {
      var use = item.querySelector("[data-ai-use]");
      var value = item.querySelector("textarea").value.trim();
      if (use.checked && value) item.applyValue(value);
    });
    dialog.close();
    app.toast(TEXT.applied, "success");
  }

  // ── Talking to the server ────────────────────────────────────────────────

  // Resolves to the response data, or null after showing the error.
  function send(body, button) {
    if (busy) return Promise.resolve(null);
    setBusy(true, button);
    var headers = { "Content-Type": "application/json", Accept: "application/json" };
    var csrfEl = document.querySelector('meta[name="csrf-token"]');
    if (csrfEl) headers["X-CSRFToken"] = csrfEl.content;
    return fetch(root.dataset.apiImprove, {
      method: "POST",
      headers: headers,
      credentials: "same-origin",
      body: JSON.stringify(body),
    }).then(function (response) {
      return response.json().catch(function () { return null; }).then(function (data) {
        setBusy(false, button);
        if (!response.ok) {
          if (data && (data.code === "limit_guest" || data.code === "limit_user")) renderUsage(0, null);
          app.toast((data && data.message) || TEXT.genericError, "error");
          return null;
        }
        renderUsage(data.remaining, data.limit);
        return data;
      });
    }).catch(function () {
      setBusy(false, button);
      app.toast(TEXT.networkError, "error");
      return null;
    });
  }

  function setBusy(on, button) {
    busy = on;
    root.querySelectorAll('[data-action="ai-improve"], [data-action="ai-improve-all"]').forEach(function (btn) {
      btn.disabled = on || remaining === 0;
    });
    if (!button) return;
    var label = button.querySelector("span");
    if (on) {
      button.dataset.label = label.textContent;
      label.textContent = TEXT.working;
      button.classList.add("is-working");
    } else if (button.dataset.label) {
      label.textContent = button.dataset.label;
      button.classList.remove("is-working");
    }
  }

  function loadUsage() {
    fetch(root.dataset.apiAiUsage, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) { if (data) renderUsage(data.remaining, data.limit); })
      .catch(function () { /* the counter is only a hint */ });
  }

  function renderUsage(left, limit) {
    remaining = left;
    var text = left === 0
      ? (isLoggedIn ? TEXT.noneLeftUser : TEXT.noneLeftGuest)
      : limit != null ? TEXT.left.replace("__REMAINING__", left).replace("__LIMIT__", limit) : "";
    usageEls.forEach(function (el) { if (text) el.textContent = text; });
    setBusy(busy, null);
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  function setNote(el, removed) {
    if (removed > 0) {
      el.textContent = TEXT.removed.replace("__COUNT__", removed);
      el.hidden = false;
    } else {
      el.hidden = true;
    }
  }

  function splitSkills(text) {
    return text.split(/[,\n]/).map(function (skill) { return skill.trim(); }).filter(Boolean);
  }
})();
