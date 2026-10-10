/* Expense Tracker UI: currency picker, month nav, totals, quick-add, day-grouped list, edit/delete.
 * Works identically for guests (GuestStore) and logged-in users (ServerStore) — see stores.js.
 * All user-visible text comes from data-text-* attributes on the root element. */
(function () {
  "use strict";

  var root = document.querySelector("[data-expenses-app]");
  if (!root || !window.ToolverseExpenses) return;

  var isLoggedIn = root.dataset.loggedIn === "true";
  var store = isLoggedIn
    ? window.ToolverseExpenses.makeServerStore(root)
    : window.ToolverseExpenses.GuestStore;

  var GUEST_CURRENCY_KEY = "toolverse_expenses_currency";
  var SUPPORTED_CURRENCIES = ["PKR", "USD", "EUR", "GBP", "AED", "SAR", "INR"];
  var CURRENCY_DEFAULT = root.dataset.currencyDefault || "PKR";
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ── DOM refs ──────────────────────────────────────────────────────────────

  var currencyPicker  = root.querySelector("[data-currency-picker]");
  var monthLabel      = root.querySelector("[data-month-label]");
  var prevBtn         = root.querySelector('[data-action="prev-month"]');
  var nextBtn         = root.querySelector('[data-action="next-month"]');
  var totalEl         = root.querySelector("[data-monthly-total]");
  var totalSpinner    = root.querySelector("[data-total-spinner]");
  var addForm         = root.querySelector("[data-add-form]");
  var listEl          = root.querySelector("[data-expense-list]");
  var listSpinner     = root.querySelector("[data-list-spinner]");
  var emptyState      = root.querySelector("[data-empty-state]");
  var toastStack      = root.querySelector("[data-expenses-toasts]");
  var editBackdrop    = root.querySelector("[data-edit-backdrop]");
  var editForm        = root.querySelector("[data-edit-form]");
  var editError       = root.querySelector("[data-edit-error]");
  var currencySymbolEls = root.querySelectorAll("[data-currency-symbol], [data-edit-currency-symbol]");

  var TEXT = {
    empty:              root.dataset.textEmpty,
    saved:              root.dataset.textSaved,
    saving:             root.dataset.textSaving,
    saveFailed:         root.dataset.textSaveFailed,
    amountRequired:     root.dataset.textAmountRequired,
    amountInvalid:      root.dataset.textAmountInvalid,
    descRequired:       root.dataset.textDescriptionRequired,
    descTooLong:        root.dataset.textDescriptionTooLong,
    deleteConfirm:      root.dataset.textDeleteConfirm,
    deleteFailed:       root.dataset.textDeleteFailed,
    loadFailed:         root.dataset.textLoadFailed,
    today:              root.dataset.textToday,
    yesterday:          root.dataset.textYesterday,
  };

  // ── State ─────────────────────────────────────────────────────────────────

  var now = new Date();
  var state = {
    year:     now.getFullYear(),
    month:    now.getMonth() + 1,  // 1-based
    expenses: [],
    loading:  false,
    currency: CURRENCY_DEFAULT,
  };

  // ── Currency: load preference ─────────────────────────────────────────────

  function loadCurrencyPreference() {
    var saved;
    if (isLoggedIn) {
      saved = (root.dataset.userCurrency || "").trim().toUpperCase();
    } else {
      try { saved = localStorage.getItem(GUEST_CURRENCY_KEY) || ""; } catch (e) { saved = ""; }
    }
    if (saved && SUPPORTED_CURRENCIES.indexOf(saved) !== -1) {
      state.currency = saved;
    }
    if (currencyPicker) currencyPicker.value = state.currency;
    updateCurrencyHints();
  }

  function saveCurrencyPreference(currency) {
    state.currency = currency;
    updateCurrencyHints();
    if (isLoggedIn) {
      var url = root.dataset.apiSetCurrency;
      if (!url) return;
      var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ currency: currency }),
      }).catch(function () { /* best effort */ });
    } else {
      try { localStorage.setItem(GUEST_CURRENCY_KEY, currency); } catch (e) { /* noop */ }
    }
  }

  if (currencyPicker) {
    currencyPicker.addEventListener("change", function () {
      saveCurrencyPreference(currencyPicker.value);
      renderTotal();
    });
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  loadCurrencyPreference();
  setDefaultDate();
  loadMonth();

  // ── Month navigation ──────────────────────────────────────────────────────

  prevBtn.addEventListener("click", function () {
    if (state.month === 1) { state.year -= 1; state.month = 12; }
    else { state.month -= 1; }
    loadMonth();
  });

  nextBtn.addEventListener("click", function () {
    if (state.month === 12) { state.year += 1; state.month = 1; }
    else { state.month += 1; }
    loadMonth();
  });

  // ── Add form ──────────────────────────────────────────────────────────────

  addForm.addEventListener("submit", function (e) {
    e.preventDefault();
    clearFieldErrors(addForm);
    var data = readAddForm();
    var err = validateData(data);
    if (err) { showFieldError(addForm, err.field, errText(err.code)); return; }

    var addBtn = addForm.querySelector('[data-action="add"]');
    addBtn.disabled = true;

    store.create(data)
      .then(function (expense) {
        addBtn.disabled = false;
        clearAddForm();
        if (expense.spentAt && monthOf(expense.spentAt) === state.year + "-" + pad(state.month)) {
          state.expenses.unshift(expense);
          renderList();
          renderTotal();
        }
        showToast(TEXT.saved, "success");
      })
      .catch(function (err) {
        addBtn.disabled = false;
        var code = (err && err.code) || "";
        var field = fieldForCode(code);
        showFieldError(addForm, field, errText(code));
      });
  });

  // Clear error state on input.
  addForm.addEventListener("input", function (e) {
    var field = e.target.closest("[data-field]");
    if (field) clearFieldError(addForm, field.dataset.field);
  });

  // ── Edit modal ────────────────────────────────────────────────────────────

  editBackdrop.addEventListener("click", function (e) {
    if (e.target === editBackdrop) closeEdit();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !editBackdrop.hidden) closeEdit();
  });

  editForm.querySelector('[data-action="cancel"]').addEventListener("click", closeEdit);

  editForm.addEventListener("submit", function (e) {
    e.preventDefault();
    clearFieldErrors(editForm);
    editError.hidden = true;
    var id = editForm.querySelector('[data-field="id"]').value;
    var data = readEditForm();
    var err = validateData(data);
    if (err) { showEditFieldError(err.field, errText(err.code)); return; }

    var saveBtn = editForm.querySelector('[data-action="save"]');
    saveBtn.disabled = true;

    store.update(id, data)
      .then(function (updated) {
        saveBtn.disabled = false;
        closeEdit();
        var idx = state.expenses.findIndex(function (e) { return e.id === id; });
        if (idx !== -1) {
          if (updated.spentAt && monthOf(updated.spentAt) === state.year + "-" + pad(state.month)) {
            state.expenses[idx] = updated;
          } else {
            state.expenses.splice(idx, 1);
          }
        }
        renderList();
        renderTotal();
        showToast(TEXT.saved, "success");
      })
      .catch(function (err) {
        saveBtn.disabled = false;
        var code = (err && err.code) || "";
        var field = fieldForCode(code);
        if (field) {
          showEditFieldError(field, errText(code));
        } else {
          editError.textContent = errText(code);
          editError.hidden = false;
        }
      });
  });

  editForm.querySelector('[data-action="delete"]').addEventListener("click", function () {
    var id = editForm.querySelector('[data-field="id"]').value;
    if (!window.confirm(TEXT.deleteConfirm)) return;

    store.remove(id)
      .then(function () {
        var idx = state.expenses.findIndex(function (e) { return e.id === id; });
        if (idx !== -1) state.expenses.splice(idx, 1);
        closeEdit();
        renderList();
        renderTotal();
      })
      .catch(function () {
        showToast(TEXT.deleteFailed, "error");
      });
  });

  editForm.addEventListener("input", function (e) {
    var field = e.target.closest("[data-field]");
    if (field) clearEditFieldError(field.dataset.field);
  });

  // ── Load & render ─────────────────────────────────────────────────────────

  function loadMonth() {
    state.loading = true;
    renderMonthLabel();
    totalEl.textContent = "—";
    if (totalSpinner) totalSpinner.hidden = false;
    listEl.innerHTML = '<div class="flex items-center justify-center py-10">'
      + '<span class="spinner" aria-hidden="true"></span></div>';
    emptyState.hidden = true;

    store.listMonth(state.year, state.month)
      .then(function (result) {
        state.expenses = result.expenses;
        state.loading = false;
        if (totalSpinner) totalSpinner.hidden = true;
        renderTotal();
        renderList();
      })
      .catch(function () {
        state.loading = false;
        if (totalSpinner) totalSpinner.hidden = true;
        listEl.innerHTML = "";
        showToast(TEXT.loadFailed, "error");
      });
  }

  function renderMonthLabel() {
    var d = new Date(state.year, state.month - 1, 1);
    monthLabel.textContent = d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  }

  function renderTotal() {
    // Group amounts by currency; show separate totals if there are multiple currencies.
    var totals = {};
    state.expenses.forEach(function (exp) {
      var c = (exp.currency || state.currency).toUpperCase();
      totals[c] = (totals[c] || 0) + (parseFloat(exp.amount) || 0);
    });
    var keys = Object.keys(totals);
    if (!keys.length) {
      totalEl.textContent = formatAmount(0, state.currency);
      return;
    }
    totalEl.textContent = keys.map(function (c) {
      return formatAmount(Math.round(totals[c] * 100) / 100, c);
    }).join("  ·  ");
  }

  function renderList() {
    listEl.innerHTML = "";

    if (!state.expenses.length) {
      emptyState.textContent = TEXT.empty;
      emptyState.hidden = false;
      return;
    }
    emptyState.hidden = true;

    // Group by spentAt date.
    var groups = [];
    var byDate = {};
    state.expenses.forEach(function (exp) {
      var d = exp.spentAt || "unknown";
      if (!byDate[d]) { byDate[d] = []; groups.push(d); }
      byDate[d].push(exp);
    });
    groups.sort(function (a, b) { return b < a ? -1 : b > a ? 1 : 0; });

    groups.forEach(function (dateStr) {
      var section = document.createElement("div");
      section.className = "mb-4";

      var header = document.createElement("p");
      header.className = "mb-2 text-[12px] text-faint label-mono";
      header.textContent = formatDate(dateStr);
      section.appendChild(header);

      byDate[dateStr].forEach(function (exp) {
        section.appendChild(makeExpenseRow(exp));
      });
      listEl.appendChild(section);
    });
  }

  function makeExpenseRow(exp) {
    var row = document.createElement("button");
    row.type = "button";
    row.className = "surface mb-2 flex w-full items-center gap-3 p-4 text-start transition-all hover:-translate-y-px hover:border-border-hover";
    row.setAttribute("data-expense-id", exp.id);

    var desc = document.createElement("span");
    desc.className = "min-w-0 flex-1 truncate text-[14px]";
    desc.textContent = exp.description;

    var amount = document.createElement("span");
    amount.className = "shrink-0 text-[14px] font-semibold tabular-nums";
    amount.textContent = formatAmount(exp.amount, exp.currency || state.currency);

    row.appendChild(desc);
    row.appendChild(amount);
    row.addEventListener("click", function () { openEdit(exp); });
    return row;
  }

  // ── Edit modal helpers ─────────────────────────────────────────────────────

  function openEdit(exp) {
    editForm.querySelector('[data-field="id"]').value = exp.id;
    editForm.querySelector('[data-field="amount"]').value = exp.amount;
    editForm.querySelector('[data-field="description"]').value = exp.description;
    editForm.querySelector('[data-field="spent_at"]').value = exp.spentAt || "";
    var editSymbol = editForm.querySelector("[data-edit-currency-symbol]");
    if (editSymbol) editSymbol.textContent = currencySymbol(exp.currency || state.currency);
    clearFieldErrors(editForm);
    editError.hidden = true;
    editBackdrop.hidden = false;
    var firstInput = editForm.querySelector("input:not([type=hidden])");
    if (firstInput) firstInput.focus();
  }

  function closeEdit() {
    editBackdrop.hidden = true;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  function readAddForm() {
    return {
      amount:      addForm.querySelector('[data-field="amount"]').value,
      description: addForm.querySelector('[data-field="description"]').value,
      currency:    state.currency,
      spentAt:     addForm.querySelector('[data-field="spent_at"]').value,
    };
  }

  function readEditForm() {
    return {
      amount:      editForm.querySelector('[data-field="amount"]').value,
      description: editForm.querySelector('[data-field="description"]').value,
      currency:    state.currency,
      spentAt:     editForm.querySelector('[data-field="spent_at"]').value,
    };
  }

  function clearAddForm() {
    addForm.querySelector('[data-field="amount"]').value = "";
    addForm.querySelector('[data-field="description"]').value = "";
    setDefaultDate();
  }

  function setDefaultDate() {
    var dateInput = addForm && addForm.querySelector('[data-field="spent_at"]');
    if (dateInput) dateInput.value = new Date().toISOString().slice(0, 10);
  }

  function validateData(data) {
    var amount = parseFloat(String(data.amount || "").replace(",", "."));
    if (!data.amount && data.amount !== 0) return { field: "amount", code: "amount_required" };
    if (isNaN(amount) || amount <= 0) return { field: "amount", code: "amount_invalid" };
    var desc = String(data.description || "").trim();
    if (!desc) return { field: "description", code: "description_required" };
    if (desc.length > 200) return { field: "description", code: "description_too_long" };
    return null;
  }

  function fieldForCode(code) {
    if (code === "amount_required" || code === "amount_invalid") return "amount";
    if (code === "description_required" || code === "description_too_long") return "description";
    if (code === "date_invalid") return "spent_at";
    return null;
  }

  function errText(code) {
    if (code === "amount_required") return TEXT.amountRequired;
    if (code === "amount_invalid")  return TEXT.amountInvalid;
    if (code === "description_required") return TEXT.descRequired;
    if (code === "description_too_long") return TEXT.descTooLong;
    return TEXT.saveFailed;
  }

  // Per-field error helpers for the add form.
  function showFieldError(form, fieldName, msg) {
    if (!fieldName) {
      // Fall back to a generic error on the submit button's row.
      var genericSlot = form.querySelector("[data-field-error]");
      if (genericSlot) { genericSlot.textContent = msg; genericSlot.hidden = false; }
      return;
    }
    var input = form.querySelector('[data-field="' + fieldName + '"]');
    if (input) input.classList.add("is-invalid");
    var slot = form.querySelector('[data-field-error="' + fieldName + '"]');
    if (slot) { slot.textContent = msg; slot.hidden = false; }
  }

  function clearFieldError(form, fieldName) {
    var input = form.querySelector('[data-field="' + fieldName + '"]');
    if (input) input.classList.remove("is-invalid");
    var slot = form.querySelector('[data-field-error="' + fieldName + '"]');
    if (slot) { slot.textContent = ""; slot.hidden = true; }
  }

  function clearFieldErrors(form) {
    form.querySelectorAll("[data-field-error]").forEach(function (el) {
      el.textContent = ""; el.hidden = true;
    });
    form.querySelectorAll(".is-invalid").forEach(function (el) {
      el.classList.remove("is-invalid");
    });
  }

  // Per-field error helpers for the edit form (uses data-edit-field-error).
  function showEditFieldError(fieldName, msg) {
    if (!fieldName) {
      editError.textContent = msg; editError.hidden = false; return;
    }
    var input = editForm.querySelector('[data-field="' + fieldName + '"]');
    if (input) input.classList.add("is-invalid");
    var slot = editForm.querySelector('[data-edit-field-error="' + fieldName + '"]');
    if (slot) { slot.textContent = msg; slot.hidden = false; }
  }

  function clearEditFieldError(fieldName) {
    var input = editForm.querySelector('[data-field="' + fieldName + '"]');
    if (input) input.classList.remove("is-invalid");
    var slot = editForm.querySelector('[data-edit-field-error="' + fieldName + '"]');
    if (slot) { slot.textContent = ""; slot.hidden = true; }
  }

  function updateCurrencyHints() {
    var sym = currencySymbol(state.currency);
    currencySymbolEls.forEach(function (el) { el.textContent = sym; });
  }

  function currencySymbol(currency) {
    var sym = { PKR: "Rs", USD: "$", EUR: "€", GBP: "£", AED: "AED", SAR: "SAR", INR: "₹" };
    return sym[(currency || "").toUpperCase()] || currency || "Rs";
  }

  function formatAmount(amount, currency) {
    var num = parseFloat(amount) || 0;
    var sym = currencySymbol(currency || state.currency);
    return sym + " " + num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }

  function formatDate(dateStr) {
    var todayStr = new Date().toISOString().slice(0, 10);
    var yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    if (dateStr === todayStr) return TEXT.today;
    if (dateStr === yesterday) return TEXT.yesterday;
    try {
      var parts = dateStr.split("-");
      var d = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
      return d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
    } catch (e) { return dateStr; }
  }

  function monthOf(dateStr) {
    return dateStr ? dateStr.slice(0, 7) : "";
  }

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  // ── Toasts ────────────────────────────────────────────────────────────────

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
    text.textContent = message;
    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "toast-close";
    closeBtn.setAttribute("aria-label", "Close");
    closeBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    closeBtn.addEventListener("click", function () { closeToast(el); });
    el.appendChild(text);
    el.appendChild(closeBtn);
    toastStack.appendChild(el);
    window.setTimeout(function () { closeToast(el); }, 4000);
  }
})();
