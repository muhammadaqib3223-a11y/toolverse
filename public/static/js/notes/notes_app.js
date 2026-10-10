/* The Notes screen: list, search, create, edit, delete. Works the same for a guest
 * (GuestStore, browser storage) and a logged-in user (ServerStore, the API) — see stores.js.
 * All visible text comes from data-text-* attributes set by the template (translated server-side),
 * the same pattern public/static/js/auth.js uses for its show/hide password labels. */
(function () {
  "use strict";

  var root = document.querySelector("[data-notes-app]");
  if (!root || !window.ToolverseNotes) return;

  var store = root.dataset.loggedIn === "true"
    ? window.ToolverseNotes.makeServerStore(root)
    : window.ToolverseNotes.GuestStore;

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var layout = root.querySelector(".notes-layout");
  var searchInput = root.querySelector("[data-search]");
  var newBtn = root.querySelector('[data-action="new"]');
  var backBtn = root.querySelector('[data-action="back"]');
  var listEl = root.querySelector("[data-notes-list]");
  var emptyState = root.querySelector("[data-empty-state]");
  var loadMoreBtn = root.querySelector('[data-action="load-more"]');
  var listSpinner = root.querySelector("[data-list-spinner]");
  var editorEmpty = root.querySelector("[data-editor-empty]");
  var editorForm = root.querySelector("[data-editor-form]");
  var titleField = editorForm.querySelector('[data-field="title"]');
  var contentField = editorForm.querySelector('[data-field="content"]');
  var deleteBtn = editorForm.querySelector('[data-action="delete"]');
  var saveStatusEls = root.querySelectorAll("[data-save-status]");
  var toastStack = root.querySelector("[data-notes-toasts]");

  var LIMIT = 50;
  var state = { notes: [], offset: 0, search: "", hasMore: false, selectedId: null, dirty: false };

  // --- Toasts (same markup/classes as the flash messages in partials/flash_messages.html) ---

  function closeToast(el) {
    if (!el.isConnected) return;
    if (reduceMotion) { el.remove(); return; }
    el.classList.add("is-leaving");
    el.addEventListener("animationend", function () { el.remove(); }, { once: true });
  }

  function showToast(message, kind) {
    if (!toastStack || !message) return;
    var el = document.createElement("div");
    el.className = "toast toast-" + (kind || "info");

    var text = document.createElement("p");
    text.className = "min-w-0 flex-1";
    text.textContent = message;

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "toast-close";
    closeBtn.textContent = "×";
    closeBtn.setAttribute("aria-label", root.dataset.textClose || "Close");
    closeBtn.addEventListener("click", function () { closeToast(el); });

    el.appendChild(text);
    el.appendChild(closeBtn);
    toastStack.appendChild(el);
    if (kind !== "error") setTimeout(function () { closeToast(el); }, 4000);
  }

  function messageForError(error) {
    if (error && error.code === "title_required") return root.dataset.textTitleRequired;
    return error && error.code && error.message ? error.message : null;
  }

  // --- List rendering ---

  function formatDate(ms) {
    try {
      return new Date(ms).toLocaleDateString(document.documentElement.lang || undefined, {
        year: "numeric", month: "short", day: "numeric",
      });
    } catch (error) {
      return "";
    }
  }

  function snippet(content) {
    var text = (content || "").replace(/\s+/g, " ").trim();
    return text.length > 80 ? text.slice(0, 80) + "…" : text;
  }

  function renderList() {
    listEl.innerHTML = "";
    state.notes.forEach(function (note) {
      var li = document.createElement("li");
      var button = document.createElement("button");
      button.type = "button";
      button.className = "notes-item" + (note.id === state.selectedId ? " is-active" : "");
      button.addEventListener("click", function () { openNote(note.id); });

      var title = document.createElement("span");
      title.className = "notes-item-title";
      title.textContent = note.title;
      button.appendChild(title);

      var preview = snippet(note.content);
      if (preview) {
        var previewEl = document.createElement("span");
        previewEl.className = "notes-item-preview";
        previewEl.textContent = preview;
        button.appendChild(previewEl);
      }

      var date = document.createElement("span");
      date.className = "notes-item-date";
      date.textContent = formatDate(note.updatedAt);
      button.appendChild(date);

      li.appendChild(button);
      listEl.appendChild(li);
    });

    var isEmpty = state.notes.length === 0;
    emptyState.hidden = !isEmpty;
    if (isEmpty) emptyState.textContent = state.search ? root.dataset.textNoMatches : root.dataset.textEmpty;
    loadMoreBtn.hidden = !state.hasMore;
  }

  function loadNotes(reset) {
    if (reset) { state.offset = 0; state.notes = []; }
    listSpinner.hidden = false;
    loadMoreBtn.hidden = true;
    return store.list({ search: state.search, offset: state.offset, limit: LIMIT })
      .then(function (result) {
        state.notes = reset ? result.notes : state.notes.concat(result.notes);
        state.hasMore = result.hasMore;
        state.offset = state.notes.length;
        renderList();
      })
      .catch(function () { showToast(root.dataset.textLoadFailed, "error"); })
      .then(function () { listSpinner.hidden = true; });
  }

  // --- Editor ---

  function enterEditorView() { layout.dataset.view = "editor"; }
  function enterListView() { layout.dataset.view = "list"; }

  function setSaveStatus(text) {
    saveStatusEls.forEach(function (el) { el.textContent = text || ""; });
  }

  function confirmDiscard() {
    return !state.dirty || window.confirm(root.dataset.textDiscardConfirm);
  }

  // Puts the editor fields back to what is actually saved, after the user agreed to discard
  // their changes (so re-opening the same note later shows the saved text, not the discarded one).
  function revertEditor() {
    var note = state.selectedId && state.notes.find(function (candidate) { return candidate.id === state.selectedId; });
    titleField.value = note ? note.title : "";
    contentField.value = note ? note.content : "";
    state.dirty = false;
    setSaveStatus("");
  }

  function showEditorForm() {
    editorEmpty.hidden = true;
    editorForm.hidden = false;
  }

  function showEditorEmpty() {
    editorEmpty.hidden = false;
    editorForm.hidden = true;
    state.selectedId = null;
    state.dirty = false;
  }

  function openNote(id) {
    if (state.selectedId === id) { enterEditorView(); return; } // already open: keep any unsaved edits
    if (!confirmDiscard()) return;
    var note = state.notes.find(function (candidate) { return candidate.id === id; });
    if (!note) return;
    state.selectedId = id;
    state.dirty = false;
    titleField.value = note.title;
    contentField.value = note.content;
    deleteBtn.hidden = false;
    setSaveStatus("");
    showEditorForm();
    renderList();
    enterEditorView();
  }

  function startNewNote() {
    if (state.selectedId === null && !state.dirty && !editorForm.hidden) {
      enterEditorView();
      titleField.focus();
      return;
    }
    if (!confirmDiscard()) return;
    state.selectedId = null;
    state.dirty = false;
    titleField.value = "";
    contentField.value = "";
    deleteBtn.hidden = true;
    setSaveStatus("");
    showEditorForm();
    renderList();
    enterEditorView();
    titleField.focus();
  }

  function upsertLocal(note) {
    var index = state.notes.findIndex(function (candidate) { return candidate.id === note.id; });
    if (index > -1) state.notes[index] = note; else state.notes.unshift(note);
    state.notes.sort(function (a, b) { return b.updatedAt - a.updatedAt; });
  }

  function saveCurrent() {
    var title = titleField.value.trim();
    if (!title) {
      showToast(root.dataset.textTitleRequired, "error");
      titleField.focus();
      return;
    }
    setSaveStatus(root.dataset.textSaving);
    var payload = { title: title, content: contentField.value };
    var action = state.selectedId ? store.update(state.selectedId, payload) : store.create(payload);
    action.then(function (note) {
      state.dirty = false;
      state.selectedId = note.id;
      deleteBtn.hidden = false;
      upsertLocal(note);
      renderList();
      setSaveStatus(root.dataset.textSaved);
    }).catch(function (error) {
      setSaveStatus("");
      showToast(messageForError(error) || root.dataset.textSaveFailed, "error");
    });
  }

  function deleteCurrent() {
    if (!state.selectedId) return;
    if (!window.confirm(root.dataset.textDeleteConfirm)) return;
    var id = state.selectedId;
    store.remove(id).then(function () {
      state.notes = state.notes.filter(function (note) { return note.id !== id; });
      showEditorEmpty();
      renderList();
      enterListView();
    }).catch(function () {
      showToast(root.dataset.textDeleteFailed, "error");
    });
  }

  // --- Wiring ---

  newBtn.addEventListener("click", startNewNote);
  backBtn.addEventListener("click", function () {
    if (!confirmDiscard()) return;
    revertEditor();
    enterListView();
  });
  deleteBtn.addEventListener("click", deleteCurrent);
  editorForm.addEventListener("submit", function (event) {
    event.preventDefault();
    saveCurrent();
  });
  [titleField, contentField].forEach(function (field) {
    field.addEventListener("input", function () {
      state.dirty = true;
      setSaveStatus("");
    });
  });

  document.addEventListener("keydown", function (event) {
    var isSave = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s";
    if (isSave && !editorForm.hidden) {
      event.preventDefault();
      saveCurrent();
    }
  });

  window.addEventListener("beforeunload", function (event) {
    if (!state.dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  var searchTimer = null;
  searchInput.addEventListener("input", function () {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(function () {
      state.search = searchInput.value.trim();
      loadNotes(true);
    }, 300);
  });

  loadMoreBtn.addEventListener("click", function () { loadNotes(false); });

  loadNotes(true);
})();
