# bench4 arm A — working memory

## completed

- T01 — categories: `Item.category` (default `models.DEFAULT_CATEGORY` =
  "uncategorized", persisted in to_dict/from_dict), `Store.add_item(category=)`,
  `reports.stock_report(store, by_category=False)` -> adds `{"categories":
  {name: rows}, "total_value"}` when true (plain shape unchanged), CLI
  `add-item --category` + `report stock --by-category`, CSV `category` column
  (last in `csv_io.FIELDNAMES`, import defaults it when absent).
- T02 — lead times: `Supplier.lead_time_days: int = 0` (persisted; missing key
  in legacy state -> 0), `Store.add_supplier(..., lead_time_days=0)`,
  `reports.reorder_suggestions` rows gain `lead_time_days` (0 if supplier
  missing), CLI `add-supplier --lead-time DAYS` + `report low` prints it.
- T03 — date padding: new `reports._normalize_date("2026-1-5")` ->
  "2026-01-05" (non-YYYY-M-D strings pass through); `monthly_orders` matches
  the month and sorts on it, so unpadded dates count and stay in day order.
  Dates are still stored as typed; `order_history` still sorts raw.

- T04 — no negative stock: `Store.ship` raises ValueError ("cannot ship N x
  SKU: only M on hand") before mutating when qty > item.qty; shipping down to
  exactly zero still allowed. CLI unchanged — `main()` already maps ValueError
  to stderr "error: ..." + exit 1, and `cmd_ship` saves only after success.

- T05 — mixed-layout CSV import: no code change needed. `import_items`
  already reads `category` with `row.get(...) or DEFAULT_CATEGORY`, so
  old (5-column) files import as "uncategorized" and new files keep their
  category; `export_items`/`FIELDNAMES` unchanged. Only the module
  docstring was updated to state that `category` is optional on import.

- T06 — grouped low stock: new `reports.low_stock_by_category(store,
  threshold=5)` -> `{category: [sku/name/qty rows, SKU-sorted]}`, categories
  with nothing low omitted (empty dict when none); CLI `report low
  --by-category` prints `[category]` headings (flat `report low` and the
  reorder-suggestions block unchanged).

- T07 — strict order lifecycle: pending is the only state you can leave
  (-> received / cancelled). New `Store._require_pending(order, action)`
  raises ValueError ("cannot receive order N: it is already received")
  from `receive_order`/`cancel_order` before any mutation, so a refused
  move never double-adds stock. CLI unchanged (ValueError -> exit 1).

## current

(none — T07 done)
