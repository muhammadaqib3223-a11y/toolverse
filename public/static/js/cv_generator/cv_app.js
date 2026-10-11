/* CV Generator UI: a step-by-step form (personal details, summary, experience, education,
 * skills, then template + download). The form is saved to the store (stores.js) as you type;
 * "Download PDF" sends it to the server, which returns the PDF and keeps nothing.
 * All user-visible text comes from data-text-* attributes. */
(function () {
  "use strict";

  var root = document.querySelector("[data-cv-app]");
  if (!root || !window.CvStores) return;

  var store = window.CvStores.GuestStore;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var STEPS = ["personal", "summary", "experience", "education", "skills", "download"];
  var MAX = {
    experience: parseInt(root.dataset.maxExperience, 10) || 15,
    education: parseInt(root.dataset.maxEducation, 10) || 10,
    skills: parseInt(root.dataset.maxSkills, 10) || 40,
    skillLength: parseInt(root.dataset.maxSkillLength, 10) || 60,
  };
  var TEXT = {
    nameRequired:      root.dataset.textNameRequired,
    genericError:      root.dataset.textGenericError,
    networkError:      root.dataset.textNetworkError,
    tooManyExperience: root.dataset.textTooManyExperience,
    tooManyEducation:  root.dataset.textTooManyEducation,
    tooManySkills:     root.dataset.textTooManySkills,
    skillExists:       root.dataset.textSkillExists,
    removeSkill:       root.dataset.textRemoveSkill,
    job:               root.dataset.textJob,
    education:         root.dataset.textEducation,
    saved:             root.dataset.textSaved,
    downloaded:        root.dataset.textDownloaded,
    clearConfirm:      root.dataset.textClearConfirm,
    stepOf:            root.dataset.textStepOf,
  };
  var ICONS = {
    close: '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>',
  };

  // ── DOM refs ──────────────────────────────────────────────────────────────

  var form         = root.querySelector("[data-cv-form]");
  var stepLinks    = root.querySelectorAll("[data-step-link]");
  var panels       = root.querySelectorAll("[data-step-panel]");
  var stepCounter  = root.querySelector("[data-step-counter]");
  var saveStatus   = root.querySelector("[data-save-status]");
  var lists        = { experience: root.querySelector('[data-list="experience"]'), education: root.querySelector('[data-list="education"]') };
  var skillInput   = root.querySelector("[data-skill-input]");
  var skillsList   = root.querySelector("[data-skills-list]");
  var skillsCount  = root.querySelector("[data-skills-count]");
  var templateBtns = root.querySelectorAll("[data-template]");
  var languageBtns = root.querySelectorAll("[data-language]");
  var downloadBtn  = root.querySelector('[data-action="download"]');
  var previewBtn   = root.querySelector('[data-action="preview"]');
  var busyEl       = root.querySelector("[data-busy]");
  var previewBox   = root.querySelector("[data-preview]");
  var previewFrame = root.querySelector("[data-preview-frame]");
  var toastStack   = root.querySelector("[data-cv-toasts]");

  var state = {
    id: null,
    step: "personal",
    skills: [],
    template: root.dataset.defaultTemplate || "classic",
    language: root.dataset.defaultLanguage || "en",
    busy: false,
    previewUrl: null,
  };
  var saveTimer = null;

  // ── Init ──────────────────────────────────────────────────────────────────

  store.list().then(function (cvs) {
    if (cvs.length) {
      load(cvs[0]);
      return;
    }
    return store.create(snapshot()).then(function (cv) { state.id = cv.id; });
  }).then(function () {
    render();
  });

  stepLinks.forEach(function (link) {
    link.addEventListener("click", function () { goTo(link.dataset.stepLink); });
  });

  form.addEventListener("submit", function (e) { e.preventDefault(); });
  form.addEventListener("input", function (e) {
    if (e.target === skillInput) return;
    clearInvalid(e.target);
    updateCounts();
    scheduleSave();
  });
  form.addEventListener("change", function (e) {
    if (e.target.matches('[data-key="current"]')) {
      syncCurrentJob(e.target.closest("[data-entry]"));
      scheduleSave();
    }
  });

  form.addEventListener("click", function (e) {
    var button = e.target.closest("[data-action]");
    if (!button) return;
    var action = button.dataset.action;
    if (action === "next") goTo(STEPS[STEPS.indexOf(state.step) + 1]);
    else if (action === "back") goTo(STEPS[STEPS.indexOf(state.step) - 1]);
    else if (action === "add-experience") addEntry("experience", {}, true);
    else if (action === "add-education") addEntry("education", {}, true);
    else if (action === "remove-entry") removeEntry(button.closest("[data-entry]"));
    else if (action === "add-skill") addSkillFromInput();
    else if (action === "download") makePdf("download");
    else if (action === "preview") makePdf("preview");
    else if (action === "clear") clearForm();
  });

  skillInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addSkillFromInput();
    }
  });

  templateBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      state.template = btn.dataset.template;
      renderChoices();
      scheduleSave();
      refreshPreview();
    });
  });
  languageBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      state.language = btn.dataset.language;
      renderChoices();
      scheduleSave();
      refreshPreview();
    });
  });

  // ── Steps ─────────────────────────────────────────────────────────────────

  function goTo(step) {
    if (STEPS.indexOf(step) === -1) return;
    state.step = step;
    renderStep();
    var panel = panelFor(step);
    var heading = panel.querySelector("h2");
    if (heading) {
      heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
    }
    form.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  }

  function renderStep() {
    panels.forEach(function (panel) { panel.hidden = panel.dataset.stepPanel !== state.step; });
    stepLinks.forEach(function (link) {
      link.setAttribute("aria-current", link.dataset.stepLink === state.step ? "step" : "false");
    });
    stepCounter.textContent = TEXT.stepOf
      .replace("__CURRENT__", STEPS.indexOf(state.step) + 1)
      .replace("__TOTAL__", STEPS.length);
  }

  function panelFor(step) {
    return root.querySelector('[data-step-panel="' + step + '"]');
  }

  // ── Load / save ───────────────────────────────────────────────────────────

  function load(saved) {
    var cv = saved.cv || {};
    var personal = cv.personal || {};
    state.id = saved.id;
    if (saved.template) state.template = saved.template;
    if (saved.language) state.language = saved.language;
    root.querySelectorAll("[data-path]").forEach(function (input) {
      var path = input.dataset.path.split(".");
      var value = path[0] === "personal" ? personal[path[1]] : cv[path[0]];
      input.value = typeof value === "string" ? value : "";
    });
    (Array.isArray(cv.experience) ? cv.experience : []).slice(0, MAX.experience).forEach(function (item) {
      addEntry("experience", item, false);
    });
    (Array.isArray(cv.education) ? cv.education : []).slice(0, MAX.education).forEach(function (item) {
      addEntry("education", item, false);
    });
    state.skills = (Array.isArray(cv.skills) ? cv.skills : [])
      .filter(function (skill) { return typeof skill === "string" && skill.trim(); })
      .slice(0, MAX.skills);
  }

  function render() {
    renderStep();
    renderSkills();
    renderChoices();
    updateCounts();
  }

  function collect() {
    var cv = { personal: {}, summary: "", experience: [], education: [], skills: state.skills.slice() };
    root.querySelectorAll("[data-path]").forEach(function (input) {
      var path = input.dataset.path.split(".");
      if (path[0] === "personal") cv.personal[path[1]] = input.value;
      else cv[path[0]] = input.value;
    });
    ["experience", "education"].forEach(function (kind) {
      lists[kind].querySelectorAll("[data-entry]").forEach(function (entry) {
        var item = {};
        entry.querySelectorAll("[data-key]").forEach(function (input) {
          item[input.dataset.key] = input.type === "checkbox" ? input.checked : input.value;
        });
        cv[kind].push(item);
      });
    });
    return cv;
  }

  function snapshot() {
    return { cv: collect(), template: state.template, language: state.language };
  }

  function scheduleSave() {
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(save, 400);
  }

  function save() {
    if (!state.id) return;
    store.update(state.id, snapshot())
      .then(function () { saveStatus.textContent = TEXT.saved; })
      .catch(function () { saveStatus.textContent = ""; });
  }

  function clearForm() {
    if (!window.confirm(TEXT.clearConfirm)) return;
    root.querySelectorAll("[data-path]").forEach(function (input) { input.value = ""; });
    lists.experience.innerHTML = "";
    lists.education.innerHTML = "";
    state.skills = [];
    closePreview();
    renderSkills();
    updateCounts();
    save();
    goTo("personal");
  }

  // ── Experience / education entries ───────────────────────────────────────

  function addEntry(kind, item, focus) {
    var list = lists[kind];
    var count = list.querySelectorAll("[data-entry]").length;
    if (count >= MAX[kind]) {
      showStepError(kind, kind === "experience" ? TEXT.tooManyExperience : TEXT.tooManyEducation);
      return;
    }
    var template = root.querySelector('[data-entry-template="' + kind + '"]');
    var entry = template.content.firstElementChild.cloneNode(true);
    var uidPrefix = "cv-" + kind + "-" + Date.now() + "-" + count + "-";
    entry.querySelectorAll("[data-key]").forEach(function (input) {
      var key = input.dataset.key;
      input.id = uidPrefix + key;
      var label = entry.querySelector('[data-label-for="' + key + '"]');
      if (label) label.setAttribute("for", input.id);
      var value = item[key];
      if (input.type === "checkbox") input.checked = value === true;
      else input.value = typeof value === "string" ? value : "";
    });
    list.appendChild(entry);
    syncCurrentJob(entry);
    renumber(kind);
    if (focus) {
      var first = entry.querySelector("input[type=text]");
      if (first) first.focus();
      scheduleSave();
    }
  }

  function removeEntry(entry) {
    if (!entry) return;
    var kind = entry.parentElement === lists.experience ? "experience" : "education";
    entry.remove();
    renumber(kind);
    hideStepError(kind);
    scheduleSave();
  }

  function renumber(kind) {
    var label = kind === "experience" ? TEXT.job : TEXT.education;
    lists[kind].querySelectorAll("[data-entry]").forEach(function (entry, index) {
      entry.querySelector("[data-entry-title]").textContent = label.replace("__N__", index + 1);
    });
  }

  function syncCurrentJob(entry) {
    if (!entry) return;
    var current = entry.querySelector('[data-key="current"]');
    var end = entry.querySelector('[data-key="end"]');
    if (current && end) end.disabled = current.checked;
  }

  // ── Skills ────────────────────────────────────────────────────────────────

  function addSkillFromInput() {
    var parts = skillInput.value.split(",").map(function (part) { return part.trim(); }).filter(Boolean);
    if (!parts.length) return;
    hideStepError("skills");
    for (var i = 0; i < parts.length; i++) {
      var skill = parts[i].slice(0, MAX.skillLength);
      var exists = state.skills.some(function (existing) { return existing.toLowerCase() === skill.toLowerCase(); });
      if (exists) { showStepError("skills", TEXT.skillExists); continue; }
      if (state.skills.length >= MAX.skills) { showStepError("skills", TEXT.tooManySkills); break; }
      state.skills.push(skill);
    }
    skillInput.value = "";
    renderSkills();
    scheduleSave();
  }

  function renderSkills() {
    skillsList.innerHTML = "";
    state.skills.forEach(function (skill, index) {
      var chip = document.createElement("span");
      chip.className = "cv-skill";
      var text = document.createElement("span");
      text.dir = "auto";
      text.textContent = skill;
      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "cv-skill-remove";
      remove.setAttribute("aria-label", TEXT.removeSkill.replace("__SKILL__", skill));
      remove.innerHTML = svg(ICONS.close, "h-3 w-3");
      remove.addEventListener("click", function () {
        state.skills.splice(index, 1);
        hideStepError("skills");
        renderSkills();
        scheduleSave();
        skillInput.focus();
      });
      chip.appendChild(text);
      chip.appendChild(remove);
      skillsList.appendChild(chip);
    });
    skillsCount.textContent = state.skills.length + " / " + MAX.skills;
  }

  // ── Template and language ─────────────────────────────────────────────────

  function renderChoices() {
    templateBtns.forEach(function (btn) {
      btn.setAttribute("aria-pressed", btn.dataset.template === state.template ? "true" : "false");
    });
    languageBtns.forEach(function (btn) {
      btn.setAttribute("aria-pressed", btn.dataset.language === state.language ? "true" : "false");
    });
  }

  // ── PDF ───────────────────────────────────────────────────────────────────

  function makePdf(mode) {
    if (state.busy) return;
    hideStepError("download");
    var data = snapshot();
    if (!data.cv.personal.full_name || !data.cv.personal.full_name.trim()) {
      goTo("personal");
      markInvalid(root.querySelector('[data-path="personal.full_name"]'), "personal", TEXT.nameRequired);
      return;
    }
    setBusy(true);
    var headers = { "Content-Type": "application/json", "Accept": "application/pdf, application/json" };
    var csrfEl = document.querySelector('meta[name="csrf-token"]');
    if (csrfEl) headers["X-CSRFToken"] = csrfEl.content;

    fetch(root.dataset.apiPdf, {
      method: "POST",
      headers: headers,
      credentials: "same-origin",
      body: JSON.stringify(data),
    }).then(function (response) {
      var type = response.headers.get("Content-Type") || "";
      if (response.ok && type.indexOf("application/pdf") === 0) {
        return response.blob().then(function (blob) {
          setBusy(false);
          var name = filenameFrom(response.headers.get("Content-Disposition"));
          if (mode === "preview") showPreview(blob);
          else downloadBlob(blob, name);
        });
      }
      return response.json().catch(function () { return null; }).then(function (body) {
        setBusy(false);
        showServerError(body);
      });
    }).catch(function () {
      setBusy(false);
      showStepError("download", TEXT.networkError);
    });
  }

  function refreshPreview() {
    if (previewBox && !previewBox.hidden) makePdf("preview");
  }

  function setBusy(busy) {
    state.busy = busy;
    downloadBtn.disabled = busy;
    if (previewBtn) previewBtn.disabled = busy;
    busyEl.hidden = !busy;
  }

  function downloadBlob(blob, name) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
    showToast(TEXT.downloaded, "success");
  }

  function showPreview(blob) {
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = URL.createObjectURL(blob);
    previewFrame.src = state.previewUrl + "#toolbar=0&view=FitH";
    previewBox.hidden = false;
  }

  function closePreview() {
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = null;
    previewFrame.removeAttribute("src");
    previewBox.hidden = true;
  }

  function filenameFrom(header) {
    if (header) {
      var star = /filename\*=UTF-8''([^;]+)/i.exec(header);
      if (star) {
        try { return decodeURIComponent(star[1]); } catch (e) { /* fall through */ }
      }
      var plain = /filename="([^"]+)"/i.exec(header);
      if (plain) return plain[1];
    }
    return "CV.pdf";
  }

  // The server names the field that has a problem, e.g. "experience.1.description".
  function showServerError(body) {
    var message = (body && body.message) || TEXT.genericError;
    var field = body && body.field;
    if (!field) { showStepError("download", message); return; }
    var parts = field.split(".");
    var step = parts[0];
    var input = null;
    if (step === "personal" || step === "summary") {
      input = root.querySelector('[data-path="' + field + '"]');
    } else if ((step === "experience" || step === "education") && parts.length === 3) {
      var entry = lists[step].querySelectorAll("[data-entry]")[parseInt(parts[1], 10)];
      if (entry) input = entry.querySelector('[data-key="' + parts[2] + '"]');
    } else if (step === "skills") {
      input = skillInput;
    } else {
      step = "download";
    }
    if (STEPS.indexOf(step) === -1) step = "download";
    goTo(step);
    markInvalid(input, step, message);
  }

  // ── Errors ────────────────────────────────────────────────────────────────

  function markInvalid(input, step, message) {
    showStepError(step, message);
    if (input) {
      input.classList.add("is-invalid");
      input.setAttribute("aria-invalid", "true");
      input.focus();
    }
  }

  function clearInvalid(input) {
    if (!input || !input.classList || !input.classList.contains("is-invalid")) return;
    input.classList.remove("is-invalid");
    input.removeAttribute("aria-invalid");
    var panel = input.closest("[data-step-panel]");
    if (panel) hideStepError(panel.dataset.stepPanel);
  }

  function showStepError(step, message) {
    var el = panelFor(step).querySelector("[data-step-error]");
    el.textContent = message || TEXT.genericError;
    el.hidden = false;
  }

  function hideStepError(step) {
    var el = panelFor(step).querySelector("[data-step-error]");
    el.hidden = true;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  function updateCounts() {
    root.querySelectorAll("[data-count-for]").forEach(function (counter) {
      var input = root.querySelector('[data-path="' + counter.dataset.countFor + '"]');
      if (input) counter.textContent = input.value.length + " / " + input.maxLength;
    });
  }

  function svg(paths, cls) {
    return '<svg class="' + cls + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + paths + "</svg>";
  }

  function showToast(message, kind) {
    if (!toastStack || !message) return;
    var el = document.createElement("div");
    el.className = "toast toast-" + (kind || "info");
    var text = document.createElement("p");
    text.textContent = message;
    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "toast-close";
    closeBtn.setAttribute("aria-label", "Close");
    closeBtn.innerHTML = svg(ICONS.close, "h-3.5 w-3.5");
    closeBtn.addEventListener("click", function () { closeToast(el); });
    el.appendChild(text);
    el.appendChild(closeBtn);
    toastStack.appendChild(el);
    window.setTimeout(function () { closeToast(el); }, 4000);
  }

  function closeToast(el) {
    if (!el.isConnected) return;
    if (reduceMotion) { el.remove(); return; }
    el.classList.add("is-leaving");
    el.addEventListener("animationend", function () { el.remove(); }, { once: true });
  }
})();
