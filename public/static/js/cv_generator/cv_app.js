/* CV Generator UI: "My CVs" (pick, rename, new, duplicate, delete), a step-by-step form
 * (personal details + photo, summary, experience, projects, education, skills + languages,
 * certifications, hobbies + references, then template + colour + download). The open CV is
 * saved to the store (stores.js) as you type: the account for a logged-in user, this browser
 * for a guest. "Download PDF" sends the form to the server, which returns the PDF and keeps
 * nothing. All user-visible text comes from data-text-* attributes.
 *
 * Repeating rows (jobs, projects, languages, ...) live in [data-list="<kind>"] and are cloned
 * from <template data-entry-template="<kind>">; short word lists (skills, hobbies) are chips. */
(function () {
  "use strict";

  var root = document.querySelector("[data-cv-app]");
  if (!root || !window.CvStores || !window.CvPhoto) return;

  var data = root.dataset;
  var isLoggedIn = data.loggedIn === "true";
  function number(value, fallback) { return parseInt(value, 10) || fallback; }

  var ENTRY_KINDS = ["experience", "projects", "education", "languages", "certifications", "references"];
  var WORD_KINDS = ["skills", "hobbies"];
  var MAX = {
    cvs: number(data.maxCvs, 20),
    experience: number(data.maxExperience, 15),
    education: number(data.maxEducation, 10),
    projects: number(data.maxProjects, 10),
    certifications: number(data.maxCertifications, 15),
    languages: number(data.maxLanguages, 10),
    references: number(data.maxReferences, 4),
    skills: number(data.maxSkills, 40),
    hobbies: number(data.maxHobbies, 15),
  };
  var WORD_LENGTH = { skills: number(data.maxSkillsLength, 60), hobbies: number(data.maxHobbiesLength, 40) };
  var store = isLoggedIn
    ? window.CvStores.makeServerStore(data.apiCvs, data.apiCvTemplate, data.apiCvPhotoTemplate)
    : window.CvStores.makeGuestStore(MAX.cvs);
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var SAVE_DELAY = isLoggedIn ? 900 : 400;
  var DEFAULTS = {
    template: data.defaultTemplate || "modern",
    accent: data.defaultAccent || "indigo",
    language: data.defaultLanguage || "en",
  };
  var TEXT = {
    nameRequired:  data.textNameRequired,
    genericError:  data.textGenericError,
    networkError:  data.textNetworkError,
    tooMany: {
      experience: data.textTooManyExperience,
      education: data.textTooManyEducation,
      projects: data.textTooManyProjects,
      certifications: data.textTooManyCertifications,
      languages: data.textTooManyLanguages,
      references: data.textTooManyReferences,
      skills: data.textTooManySkills,
      hobbies: data.textTooManyHobbies,
    },
    entryTitle: {
      experience: data.textJob,
      education: data.textEducation,
      projects: data.textProject,
      certifications: data.textCertification,
      references: data.textReference,
    },
    wordExists:    data.textWordExists,
    removeWord:    data.textRemoveWord,
    photo: {
      photo_invalid: data.textPhotoInvalid,
      photo_too_large: data.textPhotoTooLarge,
      storage_full: data.textPhotoStorageFull,
    },
    saved:         data.textSaved,
    saving:        data.textSaving,
    saveFailed:    data.textSaveFailed,
    loadFailed:    data.textLoadFailed,
    untitled:      data.textUntitled,
    copyOf:        data.textCopyOf,
    deleteConfirm: data.textDeleteConfirm,
    cvLimit:       data.textCvLimit,
    downloaded:    data.textDownloaded,
    clearConfirm:  data.textClearConfirm,
    stepOf:        data.textStepOf,
  };
  var ICONS = {
    close: '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>',
  };

  // ── DOM refs ──────────────────────────────────────────────────────────────

  var form           = root.querySelector("[data-cv-form]");
  var picker         = root.querySelector("[data-cv-picker]");
  var titleInput     = root.querySelector("[data-cv-title]");
  var stepLinks      = root.querySelectorAll("[data-step-link]");
  var panels         = root.querySelectorAll("[data-step-panel]");
  var STEPS          = Array.prototype.map.call(panels, function (panel) { return panel.dataset.stepPanel; });
  var stepCounter    = root.querySelector("[data-step-counter]");
  var saveStatus     = root.querySelector("[data-save-status]");
  var lists          = {};
  ENTRY_KINDS.forEach(function (kind) { lists[kind] = root.querySelector('[data-list="' + kind + '"]'); });
  var words          = {};
  WORD_KINDS.forEach(function (kind) {
    words[kind] = {
      input: root.querySelector('[data-word-input="' + kind + '"]'),
      list: root.querySelector('[data-word-list="' + kind + '"]'),
      count: root.querySelector('[data-word-count="' + kind + '"]'),
    };
  });
  var photoInput     = root.querySelector("[data-photo-input]");
  var photoPreview   = root.querySelector("[data-photo-preview]");
  var photoEmpty     = root.querySelector("[data-photo-empty]");
  var photoRemoveBtn = root.querySelector('[data-action="remove-photo"]');
  var templatePicker = root.querySelector("[data-template-picker]");
  var templateBtns   = root.querySelectorAll("[data-template]");
  var accentBtns     = root.querySelectorAll("[data-accent]");
  var languageBtns   = root.querySelectorAll("[data-language]");
  var downloadBtn    = root.querySelector('[data-action="download"]');
  var previewBtn     = root.querySelector('[data-action="preview"]');
  var busyEl         = root.querySelector("[data-busy]");
  var previewBox     = root.querySelector("[data-preview]");
  var previewFrame   = root.querySelector("[data-preview-frame]");
  var toastStack     = root.querySelector("[data-cv-toasts]");

  var state = {
    cvs: [],            // summaries for the picker, newest first
    id: null,           // the open CV (null if the CVs could not be loaded)
    step: STEPS[0],
    words: { skills: [], hobbies: [] },
    photo: null,        // data: URL of the open CV's photo, or null
    template: DEFAULTS.template,
    accent: DEFAULTS.accent,
    language: DEFAULTS.language,
    busy: false,
    previewUrl: null,
    dirty: false,       // changes not saved yet
    saving: null,       // the save in progress (a Promise)
  };
  var saveTimer = null;

  // ── Init ──────────────────────────────────────────────────────────────────

  renderStep();
  renderChoices();
  renderPhoto();
  loadLibrary();

  stepLinks.forEach(function (link) {
    link.addEventListener("click", function () { goTo(link.dataset.stepLink); });
  });

  form.addEventListener("submit", function (e) { e.preventDefault(); });
  form.addEventListener("input", function (e) {
    if (e.target.matches("[data-word-input], [data-photo-input]")) return;
    clearInvalid(e.target);
    updateCounts();
    scheduleSave();
  });
  form.addEventListener("change", function (e) {
    if (e.target.matches('[data-key="current"]')) syncCurrentJob(e.target.closest("[data-entry]"));
    if (e.target.matches('select, input[type="checkbox"]')) scheduleSave();
  });

  root.addEventListener("click", function (e) {
    var button = e.target.closest("[data-action]");
    if (!button || !root.contains(button)) return;
    var action = button.dataset.action;
    if (action === "next") goTo(STEPS[STEPS.indexOf(state.step) + 1]);
    else if (action === "back") goTo(STEPS[STEPS.indexOf(state.step) - 1]);
    else if (action === "add-entry") addEntry(button.dataset.kind, {}, true);
    else if (action === "remove-entry") removeEntry(button.closest("[data-entry]"));
    else if (action === "add-word") addWordsFromInput(button.dataset.kind);
    else if (action === "remove-photo") removePhoto();
    else if (action === "download") makePdf("download");
    else if (action === "preview") makePdf("preview");
    else if (action === "clear") clearForm();
    else if (action === "new-cv") newCv();
    else if (action === "duplicate-cv") duplicateCv();
    else if (action === "delete-cv") deleteCv();
  });

  picker.addEventListener("change", function () { openCv(picker.value); });
  titleInput.addEventListener("input", function () {
    var current = currentSummary();
    if (current) {
      current.title = titleInput.value;
      renderPicker();
    }
    scheduleSave();
  });

  WORD_KINDS.forEach(function (kind) {
    words[kind].input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === ",") {
        e.preventDefault();
        addWordsFromInput(kind);
      }
    });
  });

  photoInput.addEventListener("change", function () {
    var file = photoInput.files && photoInput.files[0];
    photoInput.value = "";
    if (file) setPhotoFromFile(file);
  });

  templateBtns.forEach(function (btn) {
    btn.addEventListener("click", function () { choose("template", btn.dataset.template); });
  });
  accentBtns.forEach(function (btn) {
    btn.addEventListener("click", function () { choose("accent", btn.dataset.accent); });
  });
  languageBtns.forEach(function (btn) {
    btn.addEventListener("click", function () { choose("language", btn.dataset.language); });
  });

  // Save what's left when the page is closed or hidden (e.g. switching apps on a phone).
  window.addEventListener("pagehide", function () { flush({ keepalive: true }); });
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") flush({ keepalive: true });
  });

  // Guest CVs moved into the account (shared/guest_import.js): show them in the list.
  document.addEventListener("toolverse:guest-imported", function (e) {
    if (!isLoggedIn || !e.detail || e.detail.key !== window.CvStores.GUEST_KEY) return;
    store.list().then(function (cvs) {
      state.cvs = cvs;
      renderPicker();
    }).catch(function () { /* the list refreshes on the next page load */ });
  });

  // ── For ai_writer.js: read the form, and put accepted AI text back in ──────

  window.CvApp = {
    collect: collect,
    entries: function (kind) {
      return Array.prototype.slice.call(lists[kind].querySelectorAll("[data-entry]"));
    },
    setPath: function (path, value) {
      var input = root.querySelector('[data-path="' + path + '"]');
      if (!input) return;
      input.value = value;
      clearInvalid(input);
      updateCounts();
      scheduleSave();
    },
    setEntryField: function (entry, key, value) {
      var input = entry && entry.querySelector('[data-key="' + key + '"]');
      if (!input) return;
      input.value = value;
      scheduleSave();
    },
    setSkills: function (skills) {
      setWords("skills", skills);
      scheduleSave();
    },
    addSkills: function (skills) {
      setWords("skills", state.words.skills.concat(skills));
      scheduleSave();
    },
    toast: function (message, kind) { showToast(message, kind); },
  };

  // ── My CVs ────────────────────────────────────────────────────────────────

  function loadLibrary() {
    setLibraryBusy(true);
    store.list()
      .then(function (cvs) {
        state.cvs = cvs;
        if (cvs.length) return openCv(cvs[0].id);
        return store.create(blankRecord()).then(function (record) {
          state.cvs = [summaryOf(record)];
          return showRecord(record);
        });
      })
      .catch(function () {
        state.id = null;
        setStatus(TEXT.loadFailed);
      })
      .then(function () { setLibraryBusy(false); });
  }

  function openCv(id) {
    if (!id || id === state.id) return Promise.resolve();
    setLibraryBusy(true);
    return flush()
      .then(function () { return store.get(id); })
      .then(showRecord)
      .catch(function (error) { showToast(messageFor(error), "error"); renderPicker(); })
      .then(function () { setLibraryBusy(false); });
  }

  function newCv() {
    createAndOpen(blankRecord(), null);
  }

  function duplicateCv() {
    var copy = snapshot();
    copy.title = TEXT.copyOf.replace("__TITLE__", copy.title || TEXT.untitled);
    createAndOpen(copy, state.photo);
  }

  function createAndOpen(record, photo) {
    setLibraryBusy(true);
    flush()
      .then(function () { return store.create(record); })
      .then(function (created) {
        // The server keeps photos apart from the form, so a copied photo is stored separately.
        if (!photo) return created;
        return store.setPhoto(created.id, photo).then(function () {
          created.hasPhoto = true;
          return created;
        }).catch(function () { return created; });
      })
      .then(function (created) {
        state.cvs.unshift(summaryOf(created));
        return showRecord(created);
      })
      .then(function () { goTo(STEPS[0]); })
      .catch(function (error) { showToast(messageFor(error), "error"); })
      .then(function () { setLibraryBusy(false); });
  }

  function deleteCv() {
    if (!state.id || !window.confirm(TEXT.deleteConfirm)) return;
    var id = state.id;
    window.clearTimeout(saveTimer);
    state.dirty = false;
    setLibraryBusy(true);
    store.remove(id)
      .then(function () {
        state.cvs = state.cvs.filter(function (cv) { return cv.id !== id; });
        state.id = null;
        if (state.cvs.length) return openCv(state.cvs[0].id);
        return store.create(blankRecord()).then(function (record) {
          state.cvs = [summaryOf(record)];
          return showRecord(record);
        });
      })
      .catch(function (error) { showToast(messageFor(error), "error"); })
      .then(function () { setLibraryBusy(false); });
  }

  function blankRecord() {
    return {
      title: TEXT.untitled,
      cv: {},
      template: DEFAULTS.template,
      accent: DEFAULTS.accent,
      language: DEFAULTS.language,
    };
  }

  function summaryOf(record) {
    return {
      id: record.id, title: record.title, template: record.template, accent: record.accent,
      language: record.language, hasPhoto: !!record.hasPhoto, updatedAt: record.updatedAt,
    };
  }

  function currentSummary() {
    return state.cvs.find(function (cv) { return cv.id === state.id; });
  }

  function renderPicker() {
    picker.innerHTML = "";
    state.cvs.forEach(function (cv) {
      var option = document.createElement("option");
      option.value = cv.id;
      option.textContent = (cv.title || "").trim() || TEXT.untitled;
      option.selected = cv.id === state.id;
      picker.appendChild(option);
    });
  }

  function setLibraryBusy(busy) {
    picker.disabled = busy;
    root.querySelectorAll('[data-action="new-cv"], [data-action="duplicate-cv"], [data-action="delete-cv"]')
      .forEach(function (btn) { btn.disabled = busy; });
  }

  // ── Fill / read the form ──────────────────────────────────────────────────

  function showRecord(record) {
    var cv = record.cv || {};
    var personal = cv.personal || {};
    state.id = record.id;
    state.dirty = false;
    state.template = record.template || DEFAULTS.template;
    state.accent = record.accent || DEFAULTS.accent;
    state.language = record.language || DEFAULTS.language;
    titleInput.value = record.title || "";
    root.querySelectorAll("[data-path]").forEach(function (input) {
      var path = input.dataset.path.split(".");
      var value = path[0] === "personal" ? personal[path[1]] : cv[path[0]];
      if (input.type === "checkbox") input.checked = value === true;
      else input.value = typeof value === "string" ? value : "";
      input.classList.remove("is-invalid");
    });
    ENTRY_KINDS.forEach(function (kind) {
      lists[kind].innerHTML = "";
      (Array.isArray(cv[kind]) ? cv[kind] : []).slice(0, MAX[kind]).forEach(function (item) {
        if (item && typeof item === "object") addEntry(kind, item, false);
      });
    });
    WORD_KINDS.forEach(function (kind) { setWords(kind, Array.isArray(cv[kind]) ? cv[kind] : []); });
    panels.forEach(function (panel) { hideStepError(panel.dataset.stepPanel); });
    // AI suggestions belonged to the CV that was open before.
    root.querySelectorAll("[data-suggestion]").forEach(function (card) { card.remove(); });
    closePreview();
    renderPicker();
    renderChoices();
    updateCounts();
    setStatus("");

    state.photo = null;
    renderPhoto();
    var id = record.id;
    var hasPhoto = record.photo || record.hasPhoto;
    if (!hasPhoto) return Promise.resolve();
    return store.getPhoto(id).then(function (photo) {
      if (state.id !== id) return;
      state.photo = photo;
      renderPhoto();
    }).catch(function () { /* the CV still works without its photo */ });
  }

  function collect() {
    var cv = { personal: {}, summary: "" };
    root.querySelectorAll("[data-path]").forEach(function (input) {
      var path = input.dataset.path.split(".");
      var value = input.type === "checkbox" ? input.checked : input.value;
      if (path[0] === "personal") cv.personal[path[1]] = value;
      else cv[path[0]] = value;
    });
    ENTRY_KINDS.forEach(function (kind) {
      cv[kind] = [];
      lists[kind].querySelectorAll("[data-entry]").forEach(function (entry) {
        var item = {};
        entry.querySelectorAll("[data-key]").forEach(function (input) {
          item[input.dataset.key] = input.type === "checkbox" ? input.checked : input.value;
        });
        cv[kind].push(item);
      });
    });
    WORD_KINDS.forEach(function (kind) { cv[kind] = state.words[kind].slice(); });
    return cv;
  }

  function snapshot() {
    return {
      title: titleInput.value.trim(),
      cv: collect(),
      template: state.template,
      accent: state.accent,
      language: state.language,
    };
  }

  // ── Saving ────────────────────────────────────────────────────────────────

  function scheduleSave() {
    if (!state.id) return;
    state.dirty = true;
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(save, SAVE_DELAY);
  }

  // Saves one at a time; changes made while a save runs are saved right after it.
  function save(options) {
    if (!state.id || !state.dirty) return state.saving || Promise.resolve();
    if (state.saving) {
      return state.saving.then(function () { return save(options); });
    }
    var id = state.id;
    var snap = snapshot();
    state.dirty = false;
    setStatus(TEXT.saving);
    state.saving = store.update(id, snap, options)
      .then(function (record) {
        var current = state.cvs.find(function (cv) { return cv.id === id; });
        if (current) {
          current.updatedAt = record.updatedAt;
          current.title = record.title;
        }
        if (id === state.id && !state.dirty) setStatus(TEXT.saved);
      })
      .catch(function (error) {
        if (id === state.id) {
          state.dirty = true;  // try again with the next change
          setStatus(error && error.code === "too_large" ? messageFor(error) : TEXT.saveFailed);
        }
      })
      .then(function () { state.saving = null; });
    return state.saving;
  }

  function flush(options) {
    window.clearTimeout(saveTimer);
    return save(options);
  }

  function setStatus(text) {
    saveStatus.textContent = text || "";
  }

  function clearForm() {
    if (!window.confirm(TEXT.clearConfirm)) return;
    root.querySelectorAll("[data-path]").forEach(function (input) {
      if (input.type === "checkbox") input.checked = false;
      else input.value = "";
    });
    ENTRY_KINDS.forEach(function (kind) { lists[kind].innerHTML = ""; });
    WORD_KINDS.forEach(function (kind) { setWords(kind, []); });
    closePreview();
    updateCounts();
    scheduleSave();
    goTo(STEPS[0]);
  }

  // ── Photo ─────────────────────────────────────────────────────────────────

  function setPhotoFromFile(file) {
    if (!state.id) return;
    var id = state.id;
    hideStepError("personal");
    window.CvPhoto.compress(file)
      .then(function (photo) {
        return store.setPhoto(id, photo).then(function () {
          if (state.id !== id) return;
          state.photo = photo;
          markHasPhoto(id, true);
          renderPhoto();
          refreshPreview();
        });
      })
      .catch(function (error) {
        showStepError("personal", TEXT.photo[error && error.code] || messageFor(error));
      });
  }

  function removePhoto() {
    if (!state.id) return;
    var id = state.id;
    store.removePhoto(id)
      .then(function () {
        if (state.id !== id) return;
        state.photo = null;
        markHasPhoto(id, false);
        renderPhoto();
        refreshPreview();
      })
      .catch(function (error) { showToast(messageFor(error), "error"); });
  }

  function markHasPhoto(id, value) {
    var current = state.cvs.find(function (cv) { return cv.id === id; });
    if (current) current.hasPhoto = value;
  }

  function renderPhoto() {
    var has = !!state.photo;
    photoPreview.hidden = !has;
    photoEmpty.hidden = has;
    photoRemoveBtn.hidden = !has;
    if (has) photoPreview.src = state.photo;
    else photoPreview.removeAttribute("src");
  }

  // ── Steps ─────────────────────────────────────────────────────────────────

  function goTo(step) {
    if (STEPS.indexOf(step) === -1) return;
    state.step = step;
    renderStep();
    var heading = panelFor(step).querySelector("h2");
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

  function stepOf(element) {
    var panel = element && element.closest("[data-step-panel]");
    return panel ? panel.dataset.stepPanel : STEPS[STEPS.length - 1];
  }

  // ── Repeating rows (jobs, projects, languages, ...) ───────────────────────

  function addEntry(kind, item, focus) {
    var list = lists[kind];
    if (!list) return;
    var count = list.querySelectorAll("[data-entry]").length;
    if (count >= MAX[kind]) {
      showStepError(stepOf(list), TEXT.tooMany[kind]);
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
    var kind = entry.parentElement.dataset.list;
    entry.remove();
    renumber(kind);
    hideStepError(stepOf(lists[kind]));
    scheduleSave();
  }

  function renumber(kind) {
    var label = TEXT.entryTitle[kind];
    if (!label) return;
    lists[kind].querySelectorAll("[data-entry]").forEach(function (entry, index) {
      var title = entry.querySelector("[data-entry-title]");
      if (title) title.textContent = label.replace("__N__", index + 1);
    });
  }

  function syncCurrentJob(entry) {
    if (!entry) return;
    var current = entry.querySelector('[data-key="current"]');
    var end = entry.querySelector('[data-key="end"]');
    if (current && end) end.disabled = current.checked;
  }

  // ── Word chips (skills, hobbies) ──────────────────────────────────────────

  function addWordsFromInput(kind) {
    var input = words[kind].input;
    var parts = input.value.split(",").map(function (part) { return part.trim(); }).filter(Boolean);
    if (!parts.length) return;
    var step = stepOf(input);
    hideStepError(step);
    var list = state.words[kind];
    for (var i = 0; i < parts.length; i++) {
      var word = parts[i].slice(0, WORD_LENGTH[kind]);
      var exists = list.some(function (existing) { return existing.toLowerCase() === word.toLowerCase(); });
      if (exists) { showStepError(step, TEXT.wordExists); continue; }
      if (list.length >= MAX[kind]) { showStepError(step, TEXT.tooMany[kind]); break; }
      list.push(word);
    }
    input.value = "";
    renderWords(kind);
    scheduleSave();
  }

  // Replace the list (trimmed, no empties, no repeats, within the limit).
  function setWords(kind, values) {
    var seen = {};
    state.words[kind] = values.map(function (value) { return String(value).trim().slice(0, WORD_LENGTH[kind]); })
      .filter(function (value) {
        var key = value.toLowerCase();
        if (!value || seen[key]) return false;
        seen[key] = true;
        return true;
      })
      .slice(0, MAX[kind]);
    renderWords(kind);
  }

  function renderWords(kind) {
    var refs = words[kind];
    refs.list.innerHTML = "";
    state.words[kind].forEach(function (word, index) {
      var chip = document.createElement("span");
      chip.className = "cv-skill";
      var text = document.createElement("span");
      text.dir = "auto";
      text.textContent = word;
      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "cv-skill-remove";
      remove.setAttribute("aria-label", TEXT.removeWord.replace("__SKILL__", word));
      remove.innerHTML = svg(ICONS.close, "h-3 w-3");
      remove.addEventListener("click", function () {
        state.words[kind].splice(index, 1);
        hideStepError(stepOf(refs.input));
        renderWords(kind);
        scheduleSave();
        refs.input.focus();
      });
      chip.appendChild(text);
      chip.appendChild(remove);
      refs.list.appendChild(chip);
    });
    refs.count.textContent = state.words[kind].length + " / " + MAX[kind];
  }

  // ── Template, colour and language ─────────────────────────────────────────

  function choose(kind, value) {
    if (state[kind] === value) return;
    state[kind] = value;
    renderChoices();
    scheduleSave();
    refreshPreview();
  }

  function renderChoices() {
    templateBtns.forEach(function (btn) {
      btn.setAttribute("aria-pressed", btn.dataset.template === state.template ? "true" : "false");
    });
    var hex = null;
    accentBtns.forEach(function (btn) {
      var on = btn.dataset.accent === state.accent;
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      if (on) hex = btn.dataset.hex;
    });
    if (hex && templatePicker) templatePicker.style.setProperty("--cv-accent", hex);
    languageBtns.forEach(function (btn) {
      btn.setAttribute("aria-pressed", btn.dataset.language === state.language ? "true" : "false");
    });
  }

  // ── PDF ───────────────────────────────────────────────────────────────────

  function makePdf(mode) {
    if (state.busy) return;
    hideStepError("download");
    var snap = snapshot();
    if (!snap.cv.personal.full_name || !snap.cv.personal.full_name.trim()) {
      goTo(STEPS[0]);
      markInvalid(root.querySelector('[data-path="personal.full_name"]'), STEPS[0], TEXT.nameRequired);
      return;
    }
    setBusy(true);
    var headers = { "Content-Type": "application/json", "Accept": "application/pdf, application/json" };
    var csrfEl = document.querySelector('meta[name="csrf-token"]');
    if (csrfEl) headers["X-CSRFToken"] = csrfEl.content;
    var body = { cv: snap.cv, template: snap.template, accent: snap.accent, language: snap.language };
    if (state.photo) body.photo = state.photo;

    fetch(data.apiPdf, {
      method: "POST",
      headers: headers,
      credentials: "same-origin",
      body: JSON.stringify(body),
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
      return response.json().catch(function () { return null; }).then(function (result) {
        setBusy(false);
        showServerError(result);
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

  // The server names the field that has a problem, e.g. "projects.1.link" or "personal.email".
  function showServerError(result) {
    var message = (result && result.message) || TEXT.genericError;
    var field = result && result.field;
    if (!field) { showStepError("download", message); return; }
    var parts = field.split(".");
    var input = null;
    if (parts[0] === "personal" || field === "summary" || field === "references_on_request") {
      input = root.querySelector('[data-path="' + field + '"]');
    } else if (lists[parts[0]] && parts.length === 3) {
      var entry = lists[parts[0]].querySelectorAll("[data-entry]")[parseInt(parts[1], 10)];
      if (entry) input = entry.querySelector('[data-key="' + parts[2] + '"]');
    } else if (words[parts[0]]) {
      input = words[parts[0]].input;
    } else if (field === "photo") {
      input = photoInput;
    }
    var step = input ? stepOf(input) : (lists[parts[0]] ? stepOf(lists[parts[0]]) : "download");
    goTo(step);
    markInvalid(input && input !== photoInput ? input : null, step, message);
  }

  // ── Errors ────────────────────────────────────────────────────────────────

  function messageFor(error) {
    if (error && error.code === "cv_limit") return TEXT.cvLimit;
    if (error && TEXT.photo[error.code]) return TEXT.photo[error.code];
    if (error && error.message && error.message !== error.code && error.code !== "request_failed") return error.message;
    return error instanceof TypeError ? TEXT.networkError : TEXT.genericError;
  }

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
    var panel = panelFor(step);
    if (panel) panel.querySelector("[data-step-error]").hidden = true;
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
