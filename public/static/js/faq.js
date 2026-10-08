/* FAQ accordion: a click (or Enter/Space, since it is a real button) opens or closes an answer.
   The smooth opening and the + turning into − are done in CSS. */
(function () {
  "use strict";

  document.querySelectorAll("[data-faq-trigger]").forEach(function (button) {
    var item = button.closest("[data-faq-item]");

    button.addEventListener("click", function () {
      var open = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", String(open));
      item.classList.toggle("is-open", open);

      // The page got taller or shorter, so let the scroll-reveal library re-measure afterwards.
      if (window.AOS) setTimeout(window.AOS.refresh, 400);
    });
  });
})();
