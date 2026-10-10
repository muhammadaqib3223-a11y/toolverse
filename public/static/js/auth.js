/* Auth pages: show/hide password, and a spinner on the submit button (also stops double submits). */
(function () {
  "use strict";

  function initPasswordToggles() {
    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
      var input = document.getElementById(button.getAttribute("aria-controls"));
      if (!input) return;
      var label = button.querySelector("[data-toggle-label]");
      var iconShow = button.querySelector("[data-icon-show]");
      var iconHide = button.querySelector("[data-icon-hide]");

      button.hidden = false;
      button.addEventListener("click", function () {
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        button.setAttribute("aria-pressed", String(show));
        label.textContent = show ? button.dataset.labelHide : button.dataset.labelShow;
        iconShow.hidden = show;
        iconHide.hidden = !show;
      });
    });
  }

  function setBusy(form, busy) {
    var button = form.querySelector("[data-submit]");
    if (!button) return;
    button.disabled = busy;
    button.setAttribute("aria-busy", String(busy));
    var spinner = button.querySelector("[data-submit-spinner]");
    if (spinner) spinner.hidden = !busy;
  }

  function initSubmitSpinners() {
    document.querySelectorAll("[data-auth-form]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (form.dataset.submitting === "true") {
          event.preventDefault();
          return;
        }
        form.dataset.submitting = "true";
        setBusy(form, true);
      });
    });
    // Coming back with the browser's Back button can restore a "busy" page; reset it.
    window.addEventListener("pageshow", function () {
      document.querySelectorAll("[data-auth-form]").forEach(function (form) {
        form.dataset.submitting = "false";
        setBusy(form, false);
      });
    });
  }

  initPasswordToggles();
  initSubmitSpinners();
})();
