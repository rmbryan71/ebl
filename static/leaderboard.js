const weekSelect = document.getElementById("week-select");
if (weekSelect) {
  weekSelect.addEventListener("change", () => {
    const weekStart = weekSelect.value;
    window.location.href = `/week?week_start=${weekStart}`;
  });
}
