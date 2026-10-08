/* Category filter on the /tools page: shows only the chosen category's cards, without reloading.
   Without JavaScript every card simply stays visible. */
(function () {
  "use strict";

  function initFilter(root) {
    var buttons = Array.prototype.slice.call(root.querySelectorAll("[data-filter]"));
    var items = Array.prototype.slice.call(root.querySelectorAll("[data-filter-item]"));
    var empty = root.querySelector("[data-filter-empty]");

    function apply(category) {
      var shown = 0;

      buttons.forEach(function (button) {
        button.setAttribute("aria-pressed", String(button.dataset.filter === category));
      });

      items.forEach(function (item) {
        var match = category === "all" || item.dataset.category === category;
        item.hidden = !match;
        if (!match) return;
        shown++;
        // Restart the small fade-in so the change is easy to follow.
        item.classList.remove("is-filtered-in");
        void item.offsetWidth;
        item.classList.add("is-filtered-in");
      });

      if (empty) empty.hidden = shown > 0;
      // Card positions changed, so let the scroll-reveal library re-measure.
      if (window.AOS) window.AOS.refresh();
    }

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        apply(button.dataset.filter);
      });
    });
  }

  document.querySelectorAll("[data-tool-filter]").forEach(initFilter);
})();
