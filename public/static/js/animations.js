/* Landing-page animations: hero word blur-in and the looping "how it works" demo. */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var DEMO_STEP_MS = 3400;

  // Wraps each word of the heading in a span so CSS can blur them in one by one.
  // Elements inside the heading (like the purple highlighted word) count as one word.
  function splitWords(heading) {
    var index = 0;
    function markWord(element) {
      element.classList.add("word");
      element.style.setProperty("--i", index++);
    }

    Array.prototype.slice.call(heading.childNodes).forEach(function (node) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        markWord(node);
        return;
      }
      if (node.nodeType !== Node.TEXT_NODE) return;

      var fragment = document.createDocumentFragment();
      node.textContent.split(/(\s+)/).forEach(function (part) {
        if (!part) return;
        if (/^\s+$/.test(part)) {
          fragment.appendChild(document.createTextNode(" "));
          return;
        }
        var span = document.createElement("span");
        span.textContent = part;
        markWord(span);
        fragment.appendChild(span);
      });
      node.replaceWith(fragment);
    });
  }

  function initHeroHeading() {
    var heading = document.querySelector("[data-blur-words]");
    if (!heading) return;
    if (!reduceMotion) splitWords(heading);
    heading.classList.add("is-ready");
  }

  function initDemo(root) {
    var tabs = Array.prototype.slice.call(root.querySelectorAll("[data-demo-tab]"));
    var panels = Array.prototype.slice.call(root.querySelectorAll("[data-demo-panel]"));
    if (!tabs.length || tabs.length !== panels.length) return;

    var current = 0;
    var timer = null;
    var visible = false;

    function show(index) {
      current = index;
      tabs.forEach(function (tab, i) {
        var active = i === index;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
      });
      panels.forEach(function (panel, i) {
        panel.classList.toggle("is-active", i === index);
      });
    }

    function schedule() {
      clearTimeout(timer);
      if (reduceMotion || !visible) return;
      timer = setTimeout(function () {
        show((current + 1) % panels.length);
        schedule();
      }, DEMO_STEP_MS);
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () {
        show(i);
        schedule();
      });
      tab.addEventListener("keydown", function (event) {
        var step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
        if (!step) return;
        if (document.documentElement.dir === "rtl") step = -step;
        var next = (i + step + tabs.length) % tabs.length;
        tabs[next].focus();
        show(next);
        schedule();
      });
    });

    // Only loop while the demo is on screen.
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        schedule();
      }).observe(root);
    }

    // With reduced motion, show the final result instead of a moving demo.
    show(reduceMotion ? panels.length - 1 : 0);
  }

  initHeroHeading();
  document.querySelectorAll("[data-demo]").forEach(initDemo);
})();
