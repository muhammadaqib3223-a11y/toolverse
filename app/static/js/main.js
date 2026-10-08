/* Site-wide behaviour: mobile menu, navbar border on scroll, active nav link, scroll reveal. */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function initMobileMenu() {
    var toggle = document.querySelector("[data-menu-toggle]");
    var menu = document.getElementById("mobile-menu");
    if (!toggle || !menu) return;

    var iconOpen = toggle.querySelector("[data-icon-open]");
    var iconClose = toggle.querySelector("[data-icon-close]");

    function setOpen(open) {
      toggle.setAttribute("aria-expanded", String(open));
      menu.hidden = !open;
      iconOpen.hidden = open;
      iconClose.hidden = !open;
    }

    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });
    menu.addEventListener("click", function (event) {
      if (event.target.closest("a")) setOpen(false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setOpen(false);
    });
    window.matchMedia("(min-width: 768px)").addEventListener("change", function (event) {
      if (event.matches) setOpen(false);
    });
  }

  function initHeaderBorder() {
    var header = document.querySelector("[data-site-header]");
    if (!header) return;
    function update() {
      header.classList.toggle("is-scrolled", window.scrollY > 8);
    }
    update();
    window.addEventListener("scroll", update, { passive: true });
  }

  // Highlights the navbar link of the section currently in view.
  function initScrollSpy() {
    var links = document.querySelectorAll("[data-nav-link]");
    if (!links.length || !("IntersectionObserver" in window)) return;

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        links.forEach(function (link) {
          if (link.dataset.navLink === entry.target.id) {
            link.classList.toggle("is-active", entry.isIntersecting);
          }
        });
      });
    }, { rootMargin: "-40% 0px -55% 0px" });

    links.forEach(function (link) {
      var section = document.getElementById(link.dataset.navLink);
      if (section) observer.observe(section);
    });
  }

  function initScrollReveal() {
    if (typeof window.AOS === "undefined") {
      document.documentElement.classList.add("no-aos");
      return;
    }
    window.AOS.init({
      duration: 700,
      easing: "ease-out-cubic",
      once: true,
      offset: 60,
      disable: reduceMotion,
    });
  }

  initMobileMenu();
  initHeaderBorder();
  initScrollSpy();
  initScrollReveal();
})();
