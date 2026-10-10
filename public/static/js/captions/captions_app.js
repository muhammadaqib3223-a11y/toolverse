/* Caption Generator UI: topic + platform form, editable caption cards with one-tap copy,
 * tries-left counter and (for logged-in users) the saved history.
 * Guests and logged-in users call the same API; the server decides the limit and only saves
 * history for logged-in users. All user-visible text comes from data-text-* attributes. */
(function () {
  "use strict";

  var root = document.querySelector("[data-captions-app]");
  if (!root) return;

  var isLoggedIn = root.dataset.loggedIn === "true";
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var TOPIC_MAX = parseInt(root.dataset.topicMax, 10) || 500;

  var ICONS = {
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    trash: '<path d="M4 7h16"/><path d="M9 7V4.5h6V7"/><path d="M6 7l1 13h10l1-13"/>',
    close: '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>',
  };

  var TEXT = {
    topicRequired:    root.dataset.textTopicRequired,
    topicTooLong:     root.dataset.textTopicTooLong,
    genericError:     root.dataset.textGenericError,
    networkError:     root.dataset.textNetworkError,
    copy:             root.dataset.textCopy,
    copied:           root.dataset.textCopied,
    copyFailed:       root.dataset.textCopyFailed,
    captionLabel:     root.dataset.textCaptionLabel,
    remaining:        root.dataset.textRemaining,
    noneLeftGuest:    root.dataset.textNoneLeftGuest,
    noneLeftUser:     root.dataset.textNoneLeftUser,
    historyEmpty:     root.dataset.textHistoryEmpty,
    historyFailed:    root.dataset.textHistoryLoadFailed,
    deleteConfirm:    root.dataset.textDeleteConfirm,
    deleteFailed:     root.dataset.textDeleteFailed,
    deleteLabel:      root.dataset.textDelete,
    instagram:        root.dataset.textInstagram,
    linkedin:         root.dataset.textLinkedin,
  };

  // ── DOM refs ──────────────────────────────────────────────────────────────

  var form          = root.querySelector("[data-generate-form]");
  var topicInput    = form.querySelector('[data-field="topic"]');
  var topicError    = form.querySelector('[data-field-error="topic"]');
  var topicCount    = form.querySelector("[data-topic-count]");
  var platformBtns  = form.querySelectorAll("[data-platform]");
  var generateBtn   = form.querySelector('[data-action="generate"]');
  var usageEl       = form.querySelector("[data-usage]");
  var formError     = form.querySelector("[data-form-error]");
  var resultsSection = root.querySelector("[data-results-section]");
  var loadingEl     = root.querySelector("[data-loading]");
  var resultsEl     = root.querySelector("[data-results]");
  var resultsHint   = root.querySelector("[data-results-hint]");
  var historyEl     = root.querySelector("[data-history]");
  var toastStack    = root.querySelector("[data-captions-toasts]");

  var state = {
    platform: platformBtns.length ? platformBtns[0].dataset.platform : "instagram",
    busy: false,
    remaining: null,
    history: [],
  };

  // ── Init ──────────────────────────────────────────────────────────────────

  platformBtns.forEach(function (btn) {
    btn.addEventListener("click", function () { setPlatform(btn.dataset.platform); });
  });

  topicInput.addEventListener("input", function () {
    updateTopicCount();
    hideFieldError();
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    generate();
  });

  updateTopicCount();
  loadUsage();
  if (isLoggedIn && historyEl) loadHistory();

  // ── Form ──────────────────────────────────────────────────────────────────

  function setPlatform(platform) {
    state.platform = platform;
    platformBtns.forEach(function (btn) {
      btn.setAttribute("aria-pressed", btn.dataset.platform === platform ? "true" : "false");
    });
  }

  function updateTopicCount() {
    topicCount.textContent = topicInput.value.length + " / " + TOPIC_MAX;
  }

  function showFieldError(message) {
    topicError.textContent = message;
    topicError.hidden = false;
    topicInput.classList.add("is-invalid");
    topicInput.focus();
  }

  function hideFieldError() {
    topicError.hidden = true;
    topicInput.classList.remove("is-invalid");
  }

  function showFormError(message) {
    formError.textContent = message || TEXT.genericError;
    formError.hidden = false;
  }

  function generate() {
    if (state.busy) return;
    formError.hidden = true;
    hideFieldError();

    var topic = topicInput.value.trim();
    if (!topic) { showFieldError(TEXT.topicRequired); return; }
    if (topic.length > TOPIC_MAX) { showFieldError(TEXT.topicTooLong); return; }

    setBusy(true);
    request("POST", root.dataset.apiGenerate, { topic: topic, platform: state.platform })
      .then(function (res) {
        setBusy(false);
        if (!res.ok) {
          if (res.data && (res.data.code === "limit_guest" || res.data.code === "limit_user")) {
            renderUsage(0, null);
          }
          if (res.data && (res.data.code === "topic_required" || res.data.code === "topic_too_long")) {
            showFieldError(res.data.message);
          } else {
            showFormError(res.data && res.data.message);
          }
          return;
        }
        var data = res.data;
        renderCaptions(data.captions);
        renderUsage(data.remaining, data.limit);
        if (data.saved) {
          state.history.unshift(data.saved);
          renderHistory();
        }
      })
      .catch(function () {
        setBusy(false);
        showFormError(TEXT.networkError);
      });
  }

  function setBusy(busy) {
    state.busy = busy;
    generateBtn.disabled = busy || state.remaining === 0;
    loadingEl.hidden = !busy;
    resultsSection.setAttribute("aria-busy", busy ? "true" : "false");
    if (busy) {
      resultsEl.innerHTML = "";
      resultsHint.hidden = true;
    }
  }

  // ── Usage ─────────────────────────────────────────────────────────────────

  function loadUsage() {
    request("GET", root.dataset.apiUsage)
      .then(function (res) {
        if (res.ok) renderUsage(res.data.remaining, res.data.limit);
      })
      .catch(function () { /* the counter is only a hint; generating still works */ });
  }

  function renderUsage(remaining, limit) {
    state.remaining = remaining;
    if (remaining === 0) {
      usageEl.textContent = isLoggedIn ? TEXT.noneLeftUser : TEXT.noneLeftGuest;
    } else if (limit != null) {
      usageEl.textContent = TEXT.remaining
        .replace("__REMAINING__", remaining)
        .replace("__LIMIT__", limit);
    }
    generateBtn.disabled = state.busy || remaining === 0;
  }

  // ── Results ───────────────────────────────────────────────────────────────

  function renderCaptions(captions) {
    resultsEl.innerHTML = "";
    (captions || []).forEach(function (text, index) {
      resultsEl.appendChild(captionCard(text, index));
    });
    resultsHint.hidden = !(captions && captions.length);
    if (resultsEl.firstChild) {
      resultsEl.firstChild.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
    }
  }

  function captionCard(text, index) {
    var card = document.createElement("article");
    card.className = "caption-card";
    if (!reduceMotion) card.style.animationDelay = (index * 80) + "ms";

    var head = document.createElement("div");
    head.className = "flex items-center justify-between gap-3";

    var label = document.createElement("p");
    label.className = "label-mono";
    label.textContent = TEXT.captionLabel + " " + (index + 1);
    var textareaId = "caption-" + Date.now() + "-" + index;
    label.id = textareaId + "-label";

    var copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "btn-secondary btn-sm shrink-0";
    setCopyButton(copyBtn, false);

    head.appendChild(label);
    head.appendChild(copyBtn);

    var textarea = document.createElement("textarea");
    textarea.className = "caption-text";
    textarea.id = textareaId;
    textarea.setAttribute("aria-labelledby", label.id);
    textarea.rows = 6;
    textarea.value = text;

    copyBtn.addEventListener("click", function () {
      copyText(textarea).then(function () {
        setCopyButton(copyBtn, true);
        window.setTimeout(function () { setCopyButton(copyBtn, false); }, 1800);
      }).catch(function () {
        textarea.focus();
        textarea.select();
        showToast(TEXT.copyFailed, "error");
      });
    });

    card.appendChild(head);
    card.appendChild(textarea);
    return card;
  }

  function setCopyButton(btn, copied) {
    btn.innerHTML = svg(copied ? ICONS.check : ICONS.copy, "h-4 w-4");
    var span = document.createElement("span");
    span.textContent = copied ? TEXT.copied : TEXT.copy;
    btn.appendChild(span);
  }

  function copyText(textarea) {
    var value = textarea.value;
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(value);
    }
    return new Promise(function (resolve, reject) {
      textarea.focus();
      textarea.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      if (ok) resolve(); else reject(new Error("copy_failed"));
    });
  }

  // ── History (logged-in only) ──────────────────────────────────────────────

  function loadHistory() {
    request("GET", root.dataset.apiHistory)
      .then(function (res) {
        if (!res.ok) { historyMessage(TEXT.historyFailed); return; }
        state.history = res.data.history || [];
        renderHistory();
      })
      .catch(function () { historyMessage(TEXT.historyFailed); });
  }

  function historyMessage(message) {
    historyEl.innerHTML = "";
    var p = document.createElement("p");
    p.className = "px-4 py-8 text-center text-[13px] text-muted";
    p.textContent = message;
    historyEl.appendChild(p);
  }

  function renderHistory() {
    if (!historyEl) return;
    if (!state.history.length) { historyMessage(TEXT.historyEmpty); return; }
    historyEl.innerHTML = "";
    var list = document.createElement("ul");
    state.history.forEach(function (item) {
      var li = document.createElement("li");
      li.className = "flex items-stretch";

      var open = document.createElement("button");
      open.type = "button";
      open.className = "history-item min-w-0 flex-1 flex-col";
      var topic = document.createElement("span");
      topic.className = "history-item-topic";
      topic.textContent = item.topic;
      var meta = document.createElement("span");
      meta.className = "history-item-meta";
      meta.textContent = platformName(item.platform) + " · " + formatDate(item.created_at);
      open.appendChild(topic);
      open.appendChild(meta);
      open.addEventListener("click", function () { showHistoryItem(item); });

      var del = document.createElement("button");
      del.type = "button";
      del.className = "history-item w-auto shrink-0 items-center text-faint transition-colors hover:text-danger";
      del.setAttribute("aria-label", TEXT.deleteLabel);
      del.innerHTML = svg(ICONS.trash, "h-4 w-4");
      del.addEventListener("click", function () { deleteHistoryItem(item); });

      li.appendChild(open);
      li.appendChild(del);
      list.appendChild(li);
    });
    historyEl.appendChild(list);
  }

  function showHistoryItem(item) {
    topicInput.value = item.topic;
    updateTopicCount();
    setPlatform(item.platform);
    formError.hidden = true;
    renderCaptions(item.captions);
  }

  function deleteHistoryItem(item) {
    if (!window.confirm(TEXT.deleteConfirm)) return;
    var url = root.dataset.apiHistoryItemTemplate.replace("__ID__", encodeURIComponent(item.id));
    request("DELETE", url)
      .then(function (res) {
        if (!res.ok && res.status !== 404) { showToast(TEXT.deleteFailed, "error"); return; }
        state.history = state.history.filter(function (h) { return h.id !== item.id; });
        renderHistory();
      })
      .catch(function () { showToast(TEXT.deleteFailed, "error"); });
  }

  function platformName(platform) {
    return platform === "linkedin" ? TEXT.linkedin : TEXT.instagram;
  }

  function formatDate(iso) {
    var date = new Date(iso);
    if (isNaN(date.getTime())) return "";
    try {
      return new Intl.DateTimeFormat(document.documentElement.lang || undefined, {
        day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
      }).format(date);
    } catch (e) {
      return date.toLocaleString();
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  function request(method, url, body) {
    var headers = { "Accept": "application/json" };
    if (method !== "GET") {
      var csrfEl = document.querySelector('meta[name="csrf-token"]');
      if (csrfEl) headers["X-CSRFToken"] = csrfEl.content;
    }
    if (body !== undefined) headers["Content-Type"] = "application/json";
    return fetch(url, {
      method: method,
      headers: headers,
      credentials: "same-origin",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }).then(function (response) {
      if (response.status === 204) return { ok: true, status: 204, data: null };
      return response.json()
        .catch(function () { return null; })
        .then(function (data) { return { ok: response.ok, status: response.status, data: data }; });
    });
  }

  function svg(paths, cls) {
    return '<svg class="' + cls + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + paths + "</svg>";
  }

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
    closeBtn.innerHTML = svg(ICONS.close, "h-3.5 w-3.5");
    closeBtn.addEventListener("click", function () { closeToast(el); });
    el.appendChild(text);
    el.appendChild(closeBtn);
    toastStack.appendChild(el);
    window.setTimeout(function () { closeToast(el); }, 4000);
  }
})();
