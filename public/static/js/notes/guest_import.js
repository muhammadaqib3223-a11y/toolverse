/* After login, on any dashboard page: if this browser still has guest notes, offer to move
 * them into the account. Moving posts to /api/notes/import, which skips any note already
 * moved (same client id), so this is safe to retry and safe if the prompt is shown twice. */
(function () {
  "use strict";

  var prompt = document.querySelector("[data-guest-import-prompt]");
  if (!prompt) return;
  if (document.body.dataset.loggedIn !== "true") return; // guest notes only matter once logged in

  var GUEST_KEY = window.ToolverseNotes ? window.ToolverseNotes.GUEST_KEY : "toolverse_guest_notes";
  var DISMISSED_KEY = "toolverse_guest_import_dismissed";

  function readGuestNotes() {
    try {
      var raw = window.localStorage.getItem(GUEST_KEY);
      var notes = raw ? JSON.parse(raw) : [];
      return Array.isArray(notes) ? notes : [];
    } catch (error) {
      return [];
    }
  }

  var notes = readGuestNotes();
  if (!notes.length) return;
  try {
    if (window.sessionStorage.getItem(DISMISSED_KEY) === "1") return;
  } catch (error) {
    // No sessionStorage access: just show the prompt every time, which is harmless.
  }

  var messageEl = prompt.querySelector("[data-guest-import-message]");
  var moveBtn = prompt.querySelector('[data-action="move"]');
  var dismissBtn = prompt.querySelector('[data-action="dismiss"]');

  messageEl.textContent = prompt.dataset.textMessage;
  prompt.hidden = false;

  dismissBtn.addEventListener("click", function () {
    try { window.sessionStorage.setItem(DISMISSED_KEY, "1"); } catch (error) { /* ignore */ }
    prompt.hidden = true;
  });

  moveBtn.addEventListener("click", function () {
    var current = readGuestNotes();
    if (!current.length) { prompt.hidden = true; return; }

    moveBtn.disabled = true;
    dismissBtn.disabled = true;
    messageEl.textContent = prompt.dataset.textMoving;

    var headers = { "Content-Type": "application/json", Accept: "application/json" };
    var csrf = document.querySelector('meta[name="csrf-token"]');
    if (csrf) headers["X-CSRFToken"] = csrf.content;

    window.fetch(prompt.dataset.apiImport, {
      method: "POST",
      credentials: "same-origin",
      headers: headers,
      body: JSON.stringify({ notes: current }),
    })
      .then(function (response) {
        if (!response.ok) throw new Error("import_failed");
        try { window.localStorage.removeItem(GUEST_KEY); } catch (error) { /* ignore */ }
        messageEl.textContent = prompt.dataset.textMoved;
        window.setTimeout(function () { prompt.hidden = true; }, 2500);
      })
      .catch(function () {
        messageEl.textContent = prompt.dataset.textMoveFailed;
        moveBtn.disabled = false;
        dismissBtn.disabled = false;
      });
  });
})();
