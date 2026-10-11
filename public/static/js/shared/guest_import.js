/* After login, show a prompt for each tool that still has guest data in this browser,
 * and move it to the account on request. Reads all [data-guest-import-prompt] elements,
 * so Notes and Expenses (and any future tool) are handled by this single file.
 * Each prompt element carries its own data-guest-key and data-dismissed-key attributes. */
(function () {
  "use strict";

  if (document.body.dataset.loggedIn !== "true") return;

  var prompts = document.querySelectorAll("[data-guest-import-prompt]");
  if (!prompts.length) return;

  prompts.forEach(function (prompt) {
    var guestKey = prompt.dataset.guestKey;
    var dismissedKey = prompt.dataset.dismissedKey;
    if (!guestKey) return;

    var items = readGuest(guestKey);
    if (!items.length) return;

    try {
      if (window.sessionStorage.getItem(dismissedKey) === "1") return;
    } catch (e) { /* show the prompt if sessionStorage is blocked */ }

    var messageEl = prompt.querySelector("[data-guest-import-message]");
    var moveBtn = prompt.querySelector('[data-action="move"]');
    var dismissBtn = prompt.querySelector('[data-action="dismiss"]');

    messageEl.textContent = prompt.dataset.textMessage;
    prompt.hidden = false;

    dismissBtn.addEventListener("click", function () {
      try { window.sessionStorage.setItem(dismissedKey, "1"); } catch (e) { /* ignore */ }
      prompt.hidden = true;
    });

    moveBtn.addEventListener("click", function () {
      var current = readGuest(guestKey);
      if (!current.length) { prompt.hidden = true; return; }

      moveBtn.disabled = true;
      dismissBtn.disabled = true;
      messageEl.textContent = prompt.dataset.textMoving;

      var headers = { "Content-Type": "application/json", Accept: "application/json" };
      var csrfEl = document.querySelector('meta[name="csrf-token"]');
      if (csrfEl) headers["X-CSRFToken"] = csrfEl.content;

      // The payload key matches what each tool's import endpoint expects.
      var payloadKey = prompt.dataset.payloadKey || "items";
      var body = {};
      body[payloadKey] = current;

      window.fetch(prompt.dataset.apiImport, {
        method: "POST",
        credentials: "same-origin",
        headers: headers,
        body: JSON.stringify(body),
      })
        .then(function (response) {
          if (!response.ok) throw new Error("import_failed");
          try { window.localStorage.removeItem(guestKey); } catch (e) { /* ignore */ }
          // Lets an open tool (e.g. the CV Generator) reload its list to show the moved items.
          document.dispatchEvent(new CustomEvent("toolverse:guest-imported", { detail: { key: guestKey } }));
          messageEl.textContent = prompt.dataset.textMoved;
          window.setTimeout(function () { prompt.hidden = true; }, 2500);
        })
        .catch(function () {
          messageEl.textContent = prompt.dataset.textMoveFailed;
          moveBtn.disabled = false;
          dismissBtn.disabled = false;
        });
    });
  });

  function readGuest(key) {
    try {
      var raw = window.localStorage.getItem(key);
      var items = raw ? JSON.parse(raw) : [];
      return Array.isArray(items) ? items : [];
    } catch (e) {
      return [];
    }
  }
})();
