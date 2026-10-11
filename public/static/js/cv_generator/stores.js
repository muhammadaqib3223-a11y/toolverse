/* Where CVs are kept. For now only GuestStore (this browser's localStorage) exists, used by
 * everyone; saved CVs in the account (a ServerStore with the same methods) come in part B.
 * Same four methods as the Notes/Expenses stores, all returning a Promise, so cv_app.js
 * won't need to change when the server store is added. */
(function (window) {
  "use strict";

  var GUEST_KEY = "toolverse_guest_cvs";

  function uid() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "cv-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  }

  function readCvs() {
    try {
      var raw = window.localStorage.getItem(GUEST_KEY);
      var cvs = raw ? JSON.parse(raw) : [];
      return Array.isArray(cvs) ? cvs.filter(function (cv) { return cv && typeof cv === "object"; }) : [];
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

  function record(id, data) {
    return {
      id: id,
      cv: data.cv || {},
      template: data.template || "",
      language: data.language || "",
      updatedAt: Date.now(),
    };
  }

  var GuestStore = {
    isGuest: true,

    list: function () {
      var cvs = readCvs().sort(function (a, b) { return (b.updatedAt || 0) - (a.updatedAt || 0); });
      return Promise.resolve(cvs);
    },

    create: function (data) {
      var cvs = readCvs();
      var cv = record(uid(), data || {});
      cvs.push(cv);
      writeCvs(cvs);
      return Promise.resolve(cv);
    },

    update: function (id, data) {
      var cvs = readCvs();
      var index = cvs.findIndex(function (candidate) { return candidate.id === id; });
      if (index === -1) return Promise.reject(new Error("not_found"));
      cvs[index] = record(id, data || {});
      if (!writeCvs(cvs)) return Promise.reject(new Error("storage_full"));
      return Promise.resolve(cvs[index]);
    },

    remove: function (id) {
      writeCvs(readCvs().filter(function (cv) { return cv.id !== id; }));
      return Promise.resolve();
    },
  };

  window.CvStores = { GuestStore: GuestStore };
})(window);
