/* Where notes are kept: GuestStore (this browser's localStorage) or ServerStore (the API,
 * for a logged-in user). Both expose the same four methods and return a Promise, so
 * notes_app.js does not need to know which one it is talking to. */
(function (window) {
  "use strict";

  var GUEST_KEY = "toolverse_guest_notes";

  function uid() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "n-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  }

  function readGuestNotes() {
    try {
      var raw = window.localStorage.getItem(GUEST_KEY);
      var notes = raw ? JSON.parse(raw) : [];
      return Array.isArray(notes) ? notes : [];
    } catch (error) {
      return [];
    }
  }

  function writeGuestNotes(notes) {
    try {
      window.localStorage.setItem(GUEST_KEY, JSON.stringify(notes));
    } catch (error) {
      // Private browsing or a full browser storage: notes just won't survive a reload.
    }
  }

  var GuestStore = {
    isGuest: true,

    list: function (options) {
      options = options || {};
      var notes = readGuestNotes().sort(function (a, b) { return b.updatedAt - a.updatedAt; });
      if (options.search) {
        var needle = options.search.toLowerCase();
        notes = notes.filter(function (note) {
          return note.title.toLowerCase().indexOf(needle) > -1
            || (note.content || "").toLowerCase().indexOf(needle) > -1;
        });
      }
      var offset = options.offset || 0;
      var limit = options.limit || 50;
      var page = notes.slice(offset, offset + limit);
      return Promise.resolve({ notes: page, hasMore: offset + limit < notes.length });
    },

    create: function (data) {
      var error = _validate(data);
      if (error) return Promise.reject(error);
      var notes = readGuestNotes();
      var note = { id: uid(), title: data.title.trim(), content: data.content || "", updatedAt: Date.now() };
      notes.push(note);
      writeGuestNotes(notes);
      return Promise.resolve(note);
    },

    update: function (id, data) {
      var error = _validate(data);
      if (error) return Promise.reject(error);
      var notes = readGuestNotes();
      var note = notes.find(function (candidate) { return candidate.id === id; });
      if (!note) return Promise.reject(new Error("not_found"));
      note.title = data.title.trim();
      note.content = data.content || "";
      note.updatedAt = Date.now();
      writeGuestNotes(notes);
      return Promise.resolve(note);
    },

    remove: function (id) {
      writeGuestNotes(readGuestNotes().filter(function (note) { return note.id !== id; }));
      return Promise.resolve();
    },
  };

  function _validate(data) {
    if (!data.title || !data.title.trim()) {
      var error = new Error("title_required");
      error.code = "title_required";
      return error;
    }
    return null;
  }

  function apiFetch(url, options) {
    options = options || {};
    var headers = { Accept: "application/json" };
    if (options.body) headers["Content-Type"] = "application/json";
    if (options.method && options.method !== "GET") {
      var csrf = document.querySelector('meta[name="csrf-token"]');
      if (csrf) headers["X-CSRFToken"] = csrf.content;
    }
    return window.fetch(url, {
      method: options.method || "GET",
      headers: headers,
      credentials: "same-origin",
      body: options.body ? JSON.stringify(options.body) : undefined,
    }).then(function (response) {
      if (response.status === 204) return {};
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) {
          var error = new Error(data.message || "request_failed");
          error.code = data.code;
          throw error;
        }
        return data;
      });
    });
  }

  function fromServerNote(note) {
    return { id: note.id, title: note.title, content: note.content, updatedAt: Date.parse(note.updated_at) };
  }

  function makeServerStore(root) {
    var notesUrl = root.dataset.apiNotes;
    var noteTemplate = root.dataset.apiNoteTemplate; // contains the placeholder "__ID__"

    function noteUrl(id) {
      return noteTemplate.replace("__ID__", encodeURIComponent(id));
    }

    return {
      isGuest: false,

      list: function (options) {
        options = options || {};
        var params = new URLSearchParams();
        if (options.search) params.set("search", options.search);
        params.set("offset", String(options.offset || 0));
        params.set("limit", String(options.limit || 50));
        return apiFetch(notesUrl + "?" + params.toString()).then(function (data) {
          return { notes: (data.notes || []).map(fromServerNote), hasMore: !!data.has_more };
        });
      },

      create: function (data) {
        return apiFetch(notesUrl, { method: "POST", body: { title: data.title, content: data.content } })
          .then(function (response) { return fromServerNote(response.note); });
      },

      update: function (id, data) {
        return apiFetch(noteUrl(id), { method: "PATCH", body: { title: data.title, content: data.content } })
          .then(function (response) { return fromServerNote(response.note); });
      },

      remove: function (id) {
        return apiFetch(noteUrl(id), { method: "DELETE" });
      },
    };
  }

  window.ToolverseNotes = { GuestStore: GuestStore, makeServerStore: makeServerStore, GUEST_KEY: GUEST_KEY };
})(window);
