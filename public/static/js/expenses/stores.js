/* Where expenses are kept: GuestStore (localStorage) or ServerStore (API for logged-in users).
 * Both expose the same five methods and return a Promise, so expenses_app.js does not know which
 * one it is using. Data shape: { id, amount, description, currency, spentAt } where spentAt
 * is a YYYY-MM-DD string. */
(function (window) {
  "use strict";

  var GUEST_KEY = "toolverse_guest_expenses";
  var CURRENCY_DEFAULT = "PKR";

  function uid() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "e-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  }

  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function readGuest() {
    try {
      var raw = window.localStorage.getItem(GUEST_KEY);
      var items = raw ? JSON.parse(raw) : [];
      return Array.isArray(items) ? items : [];
    } catch (e) {
      return [];
    }
  }

  function writeGuest(items) {
    try {
      window.localStorage.setItem(GUEST_KEY, JSON.stringify(items));
    } catch (e) { /* private browsing or storage full */ }
  }

  function inMonth(expense, year, month) {
    var prefix = year + "-" + (month < 10 ? "0" : "") + month;
    return (expense.spentAt || "").startsWith(prefix);
  }

  var GuestStore = {
    isGuest: true,

    listMonth: function (year, month) {
      var items = readGuest()
        .filter(function (e) { return inMonth(e, year, month); })
        .sort(function (a, b) {
          if (a.spentAt !== b.spentAt) return b.spentAt < a.spentAt ? -1 : 1;
          return b.createdAt - a.createdAt;
        });
      var total = items.reduce(function (sum, e) { return sum + (parseFloat(e.amount) || 0); }, 0);
      return Promise.resolve({ expenses: items, total: Math.round(total * 100) / 100 });
    },

    create: function (data) {
      var err = _validate(data);
      if (err) return Promise.reject(err);
      var all = readGuest();
      var expense = {
        id: uid(),
        amount: parseFloat(data.amount),
        description: data.description.trim(),
        currency: (data.currency || CURRENCY_DEFAULT).toUpperCase(),
        spentAt: data.spentAt || today(),
        createdAt: Date.now(),
      };
      all.push(expense);
      writeGuest(all);
      return Promise.resolve(expense);
    },

    update: function (id, data) {
      var err = _validate(data);
      if (err) return Promise.reject(err);
      var all = readGuest();
      var expense = all.find(function (e) { return e.id === id; });
      if (!expense) return Promise.reject(new Error("not_found"));
      expense.amount = parseFloat(data.amount);
      expense.description = data.description.trim();
      expense.currency = (data.currency || expense.currency || CURRENCY_DEFAULT).toUpperCase();
      expense.spentAt = data.spentAt || expense.spentAt;
      writeGuest(all);
      return Promise.resolve(expense);
    },

    remove: function (id) {
      writeGuest(readGuest().filter(function (e) { return e.id !== id; }));
      return Promise.resolve();
    },
  };

  function _validate(data) {
    var amount = parseFloat(String(data.amount || "").replace(",", "."));
    if (!data.amount && data.amount !== 0) {
      return _err("amount_required");
    }
    if (isNaN(amount) || amount <= 0) {
      return _err("amount_invalid");
    }
    if (!data.description || !data.description.trim()) {
      return _err("description_required");
    }
    return null;
  }

  function _err(code) {
    var e = new Error(code);
    e.code = code;
    return e;
  }

  function apiFetch(url, options) {
    options = options || {};
    var headers = { Accept: "application/json" };
    if (options.body) headers["Content-Type"] = "application/json";
    if (options.method && options.method !== "GET") {
      var csrfEl = document.querySelector('meta[name="csrf-token"]');
      if (csrfEl) headers["X-CSRFToken"] = csrfEl.content;
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
          var err = new Error(data.message || "request_failed");
          err.code = data.code;
          throw err;
        }
        return data;
      });
    });
  }

  function fromServer(exp) {
    return {
      id: exp.id,
      amount: parseFloat(exp.amount),
      description: exp.description,
      currency: exp.currency,
      spentAt: exp.spent_at,
      createdAt: Date.parse(exp.created_at),
    };
  }

  function makeServerStore(root) {
    var baseUrl = root.dataset.apiExpenses;
    var expTemplate = root.dataset.apiExpenseTemplate;

    function expUrl(id) {
      return expTemplate.replace("__ID__", encodeURIComponent(id));
    }

    return {
      isGuest: false,

      listMonth: function (year, month) {
        return apiFetch(baseUrl + "?year=" + year + "&month=" + month).then(function (data) {
          return {
            expenses: (data.expenses || []).map(fromServer),
            total: data.total || 0,
          };
        });
      },

      create: function (data) {
        return apiFetch(baseUrl, {
          method: "POST",
          body: { amount: data.amount, description: data.description, currency: data.currency, spent_at: data.spentAt },
        }).then(function (res) { return fromServer(res.expense); });
      },

      update: function (id, data) {
        return apiFetch(expUrl(id), {
          method: "PATCH",
          body: { amount: data.amount, description: data.description, currency: data.currency, spent_at: data.spentAt },
        }).then(function (res) { return fromServer(res.expense); });
      },

      remove: function (id) {
        return apiFetch(expUrl(id), { method: "DELETE" });
      },
    };
  }

  window.ToolverseExpenses = { GuestStore: GuestStore, makeServerStore: makeServerStore, GUEST_KEY: GUEST_KEY };
})(window);
