<template>
  <span></span>
</template>

<script>
// 掛到頁面上之後，觸發幾次「視窗尺寸改變」事件，
// 讓 Plotly 圖重新量容器寬度（第一次畫時量不到，會先用 700 px）。
// 觸發三次是因為手機比較慢，不確定圖何時才畫好。
module.exports = {
  mounted() {
    [300, 1000, 2500].forEach((ms) =>
      setTimeout(() => window.dispatchEvent(new Event("resize")), ms)
    );
  },
};
</script>
