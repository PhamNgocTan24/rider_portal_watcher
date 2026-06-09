/**
 * table_controls.js
 * Lightweight client-side filter + sort for dashboard tables.
 * No dependencies.
 */
(function () {
  "use strict";

  // -----------------------------------------------------------------------
  // Utility
  // -----------------------------------------------------------------------
  function norm(str) {
    return (str || "").toLowerCase().trim();
  }

  function cellText(row, colIndex) {
    const cell = row.cells[colIndex];
    return cell ? norm(cell.innerText) : "";
  }

  // -----------------------------------------------------------------------
  // Core filter: hide rows that don't match all active filters
  // -----------------------------------------------------------------------
  function applyFilters(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const rows = Array.from(table.querySelectorAll("tbody tr"));
    const controls = document.querySelectorAll(`[data-table="${tableId}"]`);

    // Gather active filter specs
    const filters = [];
    controls.forEach((ctrl) => {
      const col = parseInt(ctrl.dataset.col, 10);
      const type = ctrl.dataset.type || "text";
      const val = ctrl.value;
      if (val === "" || val === "all") return;
      filters.push({ col, type, val: norm(val), raw: val });
    });

    // Range pair grouping (min/max share same col)
    const rangeFilters = {};
    document.querySelectorAll(`[data-table="${tableId}"][data-type="range-min"]`).forEach((el) => {
      const col = parseInt(el.dataset.col, 10);
      if (!rangeFilters[col]) rangeFilters[col] = {};
      rangeFilters[col].min = parseFloat(el.value) || null;
    });
    document.querySelectorAll(`[data-table="${tableId}"][data-type="range-max"]`).forEach((el) => {
      const col = parseInt(el.dataset.col, 10);
      if (!rangeFilters[col]) rangeFilters[col] = {};
      rangeFilters[col].max = parseFloat(el.value) || null;
    });

    let visibleCount = 0;
    rows.forEach((row) => {
      let show = true;

      // Text / select filters
      filters.forEach(({ col, type, val }) => {
        if (type === "range-min" || type === "range-max") return;
        if (type === "fullrow") {
          const rowText = norm(row.innerText);
          if (!rowText.includes(val)) show = false;
          return;
        }
        const cell = cellText(row, col);
        if (!cell.includes(val)) show = false;
      });

      // Range filters
      Object.entries(rangeFilters).forEach(([col, { min, max }]) => {
        const raw = cellText(row, parseInt(col, 10)).replace(/[^0-9.]/g, "");
        const num = parseFloat(raw);
        if (isNaN(num)) return;
        if (min !== null && num < min) show = false;
        if (max !== null && num > max) show = false;
      });

      row.style.display = show ? "" : "none";
      if (show) visibleCount++;
    });

    // Update row count badge
    const badge = document.querySelector(`[data-count="${tableId}"]`);
    if (badge) badge.textContent = visibleCount;
  }

  // -----------------------------------------------------------------------
  // Sort
  // -----------------------------------------------------------------------
  let sortState = {}; // tableId -> { col, dir }

  function sortTable(tableId, col) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const prev = sortState[tableId] || {};
    const dir = prev.col === col && prev.dir === "asc" ? "desc" : "asc";
    sortState[tableId] = { col, dir };

    // Update header icons
    table.querySelectorAll("th[data-sort-col]").forEach((th) => {
      th.classList.remove("sort-asc", "sort-desc");
      if (parseInt(th.dataset.sortCol, 10) === col) {
        th.classList.add(dir === "asc" ? "sort-asc" : "sort-desc");
      }
    });

    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));

    rows.sort((a, b) => {
      const av = cellText(a, col).replace(/[^0-9.\-]/g, "") || cellText(a, col);
      const bv = cellText(b, col).replace(/[^0-9.\-]/g, "") || cellText(b, col);
      const an = parseFloat(av);
      const bn = parseFloat(bv);
      let cmp;
      if (!isNaN(an) && !isNaN(bn)) {
        cmp = an - bn;
      } else {
        cmp = av.localeCompare(bv);
      }
      return dir === "asc" ? cmp : -cmp;
    });

    rows.forEach((r) => tbody.appendChild(r));
  }

  // -----------------------------------------------------------------------
  // Reset all filters on a table
  // -----------------------------------------------------------------------
  function resetFilters(tableId) {
    document.querySelectorAll(`[data-table="${tableId}"]`).forEach((ctrl) => {
      ctrl.value = ctrl.tagName === "SELECT" ? "all" : "";
    });
    applyFilters(tableId);
  }

  // -----------------------------------------------------------------------
  // Auto-wire on DOMContentLoaded
  // -----------------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", function () {
    // Wire filter inputs
    document.querySelectorAll("[data-table]").forEach((ctrl) => {
      const tableId = ctrl.dataset.table;
      ctrl.addEventListener("input", () => applyFilters(tableId));
      ctrl.addEventListener("change", () => applyFilters(tableId));
    });

    // Wire sort headers
    document.querySelectorAll("th[data-sort-col]").forEach((th) => {
      th.style.cursor = "pointer";
      th.addEventListener("click", () => {
        const tableId = th.closest("table").id;
        sortTable(tableId, parseInt(th.dataset.sortCol, 10));
      });
    });

    // Wire reset buttons
    document.querySelectorAll("[data-reset-table]").forEach((btn) => {
      btn.addEventListener("click", () => resetFilters(btn.dataset.resetTable));
    });

    // Run initial filter (handles pre-filled URL params in future)
    document.querySelectorAll("table[id]").forEach((t) => applyFilters(t.id));
  });
})();
