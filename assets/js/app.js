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

// Audio player with playback-speed control (0.5–1.5×).
document.addEventListener("alpine:init", function () {
  Alpine.data("audioPlayer", function () {
    return {
      rates: [0.5, 0.75, 1, 1.25, 1.5],
      rate: 1,
      setRate(r) {
        this.rate = r;
        this.$refs.audio.playbackRate = r;
      },
      init() {
        // Keep the chosen rate across pause/seek/new source loads.
        this.$refs.audio.addEventListener("loadedmetadata", () => {
          this.$refs.audio.playbackRate = this.rate;
        });
      },
    };
  });
});

document.addEventListener("DOMContentLoaded", function () {
  initSortables(document);
  if (window.htmx) {
    htmx.onLoad(function (content) {
      initSortables(content);
    });
  }
});
