/* Expense Tracker UI: month nav, monthly total, quick add, day-grouped list, edit/delete.
 * Works identically for guests (GuestStore) and logged-in users (ServerStore) — see stores.js.
 * All user-visible text comes from data-text-* attributes on the root element. */
(function () {
  "use strict";

  var root = document.querySelector("[data-expenses-app]");
  if (!root || !window.ToolverseExpenses) return;

  var store = root.dataset.loggedIn === "true"
    ? window.ToolverseExpenses.makeServerStore(root)
    : window.ToolverseExpenses.GuestStore;

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ── DOM refs ──────────────────────────────────────────────────────────────

  var monthLabel   = root.querySelector("[data-month-label]");
  var prevBtn      = root.querySelector('[data-action="prev-month"]');
  var nextBtn      = root.querySelector('[data-action="next-month"]');
  var totalEl      = root.querySelector("[data-monthly-total]");
  var totalSpinner = root.querySelector("[data-total-spinner]");
  var addForm      = root.querySelector("[data-add-form]");
  var addError     = root.querySelector("[data-add-error]");
  var listEl       = root.querySelector("[data-expense-list]");
  var listSpinner  = root.querySelector("[data-list-spinner]");
  var emptyState   = root.querySelector("[data-empty-state]");
  var toastStack   = root.querySelector("[data-expenses-toasts]");
  var editBackdrop = root.querySelector("[data-edit-backdrop]");
  var editForm     = root.querySelector("[data-edit-form]");
  var editError    = root.querySelector("[data-edit-error]");
  var currencySymbolEls = root.querySelectorAll("[data-currency-symbol], [data-edit-currency-symbol]");

  var TEXT = {
    empty:              root.dataset.textEmpty,
    saved:              root.dataset.textSaved,
    saving:             root.dataset.textSaving,
    saveFailed:         root.dataset.textSaveFailed,
    amountRequired:     root.dataset.textAmountRequired,
    amountInvalid:      root.dataset.textAmountInvalid,
    descRequired:       root.dataset.textDescriptionRequired,
    deleteConfirm:      root.dataset.textDeleteConfirm,
    deleteFailed:       root.dataset.textDeleteFailed,
    loadFailed:         root.dataset.textLoadFailed,
    today:              root.dataset.textToday,
    yesterday:          root.dataset.textYesterday,
  };

  var CURRENCY_DEFAULT = root.dataset.currencyDefault || "PKR";

  // ── State ─────────────────────────────────────────────────────────────────

  var now = new Date();
  var state = {
    year: now.getFullYear(),
    month: now.getMonth() + 1,  // 1-based
    expenses: [],
    total: 0,
    loading: false,
    currency: CURRENCY_DEFAULT,
  };

  // Detect currency from first stored expense (guest) or from any existing expense.
  // The add form's currency field defaults to this.
  function detectedCurrency() {
    return (state.expenses[0] && state.expenses[0].currency) || CURRENCY_DEFAULT;
  }

  // ── Init ──────────────────────────────────────────────────────────────────

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
    var data = readAddForm();
    var err = validateData(data);
    if (err) { showAddError(errText(err)); return; }
    showAddError("");
    var addBtn = addForm.querySelector('[data-action="add"]');
    addBtn.disabled = true;

    store.create(data)
      .then(function (expense) {
        addBtn.disabled = false;
        clearAddForm();
        if (expense.spentAt && monthOf(expense.spentAt) === state.year + "-" + pad(state.month)) {
          state.expenses.unshift(expense);
          state.total = roundTotal(state.total + (parseFloat(expense.amount) || 0));
          renderList();
          renderTotal();
        }
        showToast(TEXT.saved, "success");
      })
      .catch(function (err) {
        addBtn.disabled = false;
        showAddError(errText(err));
      });
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
    var id = editForm.querySelector('[data-field="id"]').value;
    var data = readEditForm();
    var err = validateData(data);
    if (err) { showEditError(errText(err)); return; }
    showEditError("");

    var saveBtn = editForm.querySelector('[data-action="save"]');
    saveBtn.disabled = true;

    store.update(id, data)
      .then(function (updated) {
        saveBtn.disabled = false;
        closeEdit();
        var idx = state.expenses.findIndex(function (e) { return e.id === id; });
        if (idx !== -1) {
          var old = state.expenses[idx];
          state.total = roundTotal(state.total - (parseFloat(old.amount) || 0) + (parseFloat(updated.amount) || 0));
          // Keep in list only if still in this month; otherwise remove.
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
        showEditError(errText(err));
      });
  });

  editForm.querySelector('[data-action="delete"]').addEventListener("click", function () {
    var id = editForm.querySelector('[data-field="id"]').value;
    if (!window.confirm(TEXT.deleteConfirm)) return;

    store.remove(id)
      .then(function () {
        var idx = state.expenses.findIndex(function (e) { return e.id === id; });
        if (idx !== -1) {
          state.total = roundTotal(state.total - (parseFloat(state.expenses[idx].amount) || 0));
          state.expenses.splice(idx, 1);
        }
        closeEdit();
        renderList();
        renderTotal();
      })
      .catch(function () {
        showToast(TEXT.deleteFailed, "error");
      });
  });

  // ── Load & render ─────────────────────────────────────────────────────────

  function loadMonth() {
    state.loading = true;
    renderMonthLabel();
    totalEl.textContent = "—";
    if (totalSpinner) { totalSpinner.hidden = false; }
    listEl.innerHTML = '<div class="flex items-center justify-center py-10">'
      + '<span class="spinner" aria-hidden="true"></span></div>';
    emptyState.hidden = true;

    store.listMonth(state.year, state.month)
      .then(function (result) {
        state.expenses = result.expenses;
        state.total = result.total;
        state.loading = false;
        if (totalSpinner) { totalSpinner.hidden = true; }
        renderTotal();
        renderList();
        updateCurrencyHints();
      })
      .catch(function () {
        state.loading = false;
        if (totalSpinner) { totalSpinner.hidden = true; }
        listEl.innerHTML = "";
        showToast(TEXT.loadFailed, "error");
      });
  }

  function renderMonthLabel() {
    var d = new Date(state.year, state.month - 1, 1);
    monthLabel.textContent = d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  }

  function renderTotal() {
    var currency = detectedCurrency();
    totalEl.textContent = formatAmount(state.total, currency);
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
    amount.textContent = formatAmount(exp.amount, exp.currency);

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
    var editSymbol = editForm.querySelector('[data-edit-currency-symbol]');
    if (editSymbol) editSymbol.textContent = currencySymbol(exp.currency || CURRENCY_DEFAULT);
    showEditError("");
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
      currency:    CURRENCY_DEFAULT,
      spentAt:     addForm.querySelector('[data-field="spent_at"]').value,
    };
  }

  function readEditForm() {
    return {
      amount:      editForm.querySelector('[data-field="amount"]').value,
      description: editForm.querySelector('[data-field="description"]').value,
      currency:    CURRENCY_DEFAULT,
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
    if (!data.amount && data.amount !== 0) return "amount_required";
    if (isNaN(amount) || amount <= 0) return "amount_invalid";
    if (!data.description || !String(data.description).trim()) return "description_required";
    return null;
  }

  function errText(err) {
    var code = (err && err.code) || (typeof err === "string" ? err : "");
    if (code === "amount_required") return TEXT.amountRequired;
    if (code === "amount_invalid")  return TEXT.amountInvalid;
    if (code === "description_required") return TEXT.descRequired;
    return TEXT.saveFailed;
  }

  function showAddError(msg) {
    addError.textContent = msg;
    addError.hidden = !msg;
  }

  function showEditError(msg) {
    editError.textContent = msg;
    editError.hidden = !msg;
  }

  function updateCurrencyHints() {
    var sym = currencySymbol(detectedCurrency());
    currencySymbolEls.forEach(function (el) { el.textContent = sym; });
  }

  function currencySymbol(currency) {
    if (currency === "PKR") return "Rs";
    if (currency === "USD") return "$";
    if (currency === "EUR") return "€";
    if (currency === "GBP") return "£";
    return currency;
  }

  function formatAmount(amount, currency) {
    var num = parseFloat(amount) || 0;
    var sym = currencySymbol(currency || CURRENCY_DEFAULT);
    return sym + " " + num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
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
    } catch (e) {
      return dateStr;
    }
  }

  function monthOf(dateStr) {
    return dateStr ? dateStr.slice(0, 7) : "";
  }

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function roundTotal(n) {
    return Math.round((parseFloat(n) || 0) * 100) / 100;
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
