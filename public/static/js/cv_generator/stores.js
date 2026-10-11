/* Where CVs are kept: GuestStore (this browser's localStorage) or ServerStore (the API, for a
 * logged-in user). Both have the same methods and return Promises, so cv_app.js does not need
 * to know which one it is talking to (same idea as the Notes and Expenses stores).
 *
 * A CV record: { id, title, cv, template, accent, language, updatedAt }.
 * list() returns records WITHOUT `cv` (the form data); get(id) returns the full record.
 * Errors are Error objects with a `code` (e.g. "cv_limit") and, from the server, a message. */
(function (window) {
  "use strict";

  var GUEST_KEY = "toolverse_guest_cvs";

  // Guest ids are UUIDs so the server can keep them as client_id when the CVs move to the account.
  function uuid() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = Math.random() * 16 | 0;
      return (c === "x" ? r : (r & 0x3 | 0x8)).toString(16);
    });
  }

  function codedError(code, message) {
    var error = new Error(message || code);
    error.code = code;
    return error;
  }

  function summary(record) {
    return {
      id: record.id,
      title: record.title,
      template: record.template,
      accent: record.accent,
      language: record.language,
      updatedAt: record.updatedAt,
    };
  }

  // ── Guest: this browser only ─────────────────────────────────────────────

  function readCvs() {
    try {
      var raw = window.localStorage.getItem(GUEST_KEY);
      var cvs = raw ? JSON.parse(raw) : [];
      return Array.isArray(cvs) ? cvs.filter(function (cv) { return cv && typeof cv === "object" && cv.id; }) : [];
    } catch (error) {
      return [];
    }
  }

  function writeCvs(cvs) {
    try {
      window.localStorage.setItem(GUEST_KEY, JSON.stringify(cvs));
      return true;
    } catch (error) {
      // Private browsing or a full browser storage: the CV just won't survive a reload.
      return false;
    }
  }

  function guestRecord(id, data) {
    return {
      id: id,
      title: data.title || "",
      cv: data.cv || {},
      template: data.template || "",
      accent: data.accent || "",
      language: data.language || "",
      updatedAt: Date.now(),
    };
  }

  function makeGuestStore(maxCvs) {
    return {
      isGuest: true,

      list: function () {
        var cvs = readCvs().sort(function (a, b) { return (b.updatedAt || 0) - (a.updatedAt || 0); });
        return Promise.resolve(cvs.map(summary));
      },

      get: function (id) {
        var cv = readCvs().find(function (candidate) { return candidate.id === id; });
        return cv ? Promise.resolve(cv) : Promise.reject(codedError("not_found"));
      },

      create: function (data) {
        var cvs = readCvs();
        if (cvs.length >= maxCvs) return Promise.reject(codedError("cv_limit"));
        var cv = guestRecord(uuid(), data || {});
        cvs.push(cv);
        writeCvs(cvs);
        return Promise.resolve(cv);
      },

      update: function (id, data) {
        var cvs = readCvs();
        var index = cvs.findIndex(function (candidate) { return candidate.id === id; });
        if (index === -1) return Promise.reject(codedError("not_found"));
        cvs[index] = guestRecord(id, data || {});
        if (!writeCvs(cvs)) return Promise.reject(codedError("storage_full"));
        return Promise.resolve(cvs[index]);
      },

      remove: function (id) {
        writeCvs(readCvs().filter(function (cv) { return cv.id !== id; }));
        return Promise.resolve();
      },
    };
  }

  // ── Logged in: the account (via the API) ─────────────────────────────────

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
      keepalive: !!options.keepalive,
      body: options.body ? JSON.stringify(options.body) : undefined,
    }).then(function (response) {
      if (response.status === 204) return {};
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) throw codedError(data.code || "request_failed", data.message);
        return data;
      });
    });
  }

  function fromServer(cv) {
    var record = {
      id: cv.id,
      title: cv.title,
      template: cv.template,
      accent: cv.accent,
      language: cv.language,
      updatedAt: Date.parse(cv.updated_at) || Date.now(),
    };
    if (cv.cv) record.cv = cv.cv;
    return record;
  }

  function toServer(data) {
    return {
      title: data.title || "",
      cv: data.cv || {},
      template: data.template,
      accent: data.accent,
      language: data.language,
    };
  }

  function makeServerStore(listUrl, itemTemplate) {
    function itemUrl(id) {
      return itemTemplate.replace("__ID__", encodeURIComponent(id));
    }

    return {
      isGuest: false,

      list: function () {
        return apiFetch(listUrl).then(function (data) { return (data.cvs || []).map(fromServer); });
      },

      get: function (id) {
        return apiFetch(itemUrl(id)).then(function (data) { return fromServer(data.cv); });
      },

      create: function (data) {
        return apiFetch(listUrl, { method: "POST", body: toServer(data || {}) })
          .then(function (result) { return fromServer(result.cv); });
      },

      // options.keepalive: let the save finish even if the page is being closed.
      update: function (id, data, options) {
        return apiFetch(itemUrl(id), { method: "PATCH", body: toServer(data || {}), keepalive: options && options.keepalive })
          .then(function (result) { return fromServer(result.cv); });
      },

      remove: function (id) {
        return apiFetch(itemUrl(id), { method: "DELETE" });
      },
    };
  }

  window.CvStores = {
    GUEST_KEY: GUEST_KEY,
    makeGuestStore: makeGuestStore,
    makeServerStore: makeServerStore,
  };
})(window);
