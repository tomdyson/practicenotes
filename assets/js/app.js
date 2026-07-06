// Site-wide behaviours. Loaded deferred after htmx/Alpine/Sortable.

// Drag-to-reorder lists: any .js-sortable container becomes a SortableJS
// list; an htmx hx-trigger="end" on the same element posts the new order
// (Sortable's "end" event bubbles into htmx).
function initSortables(root) {
  root.querySelectorAll(".js-sortable").forEach(function (el) {
    if (el._sortable) return;
    el._sortable = new Sortable(el, {
      animation: 150,
      handle: ".js-drag-handle",
      ghostClass: "opacity-40",
    });
  });
}

document.addEventListener("DOMContentLoaded", function () {
  initSortables(document);
  if (window.htmx) {
    htmx.onLoad(function (content) {
      initSortables(content);
    });
  }
});
