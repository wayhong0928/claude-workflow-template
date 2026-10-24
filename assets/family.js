/* 門面頁流程圖：捲到時各站依序出現。要求減少動態效果或瀏覽器不支援時不動，直接顯示完成狀態。
   權威源在 Obsidian vault 的 門面頁\family.js，由 sync_family.py 複製到各站。 */
(function () {
  var flows = document.querySelectorAll(".fam-flow");
  if (!flows.length || !("IntersectionObserver" in window)) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  Array.prototype.forEach.call(flows, function (el) {
    el.classList.add("fam-ready");
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          el.classList.add("fam-go");
          io.disconnect();
        }
      });
    }, { threshold: 0.25 });
    io.observe(el);
  });
})();
