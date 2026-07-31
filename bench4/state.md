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
- T05 — mixed-layout CSV import: no code change (`import_items` already
  defaults a missing `category` to "uncategorized"); docstring only.
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
- T08 — case-insensitive SKUs: new `models.normalize_sku(sku)` -> `sku.upper()`
  is the canonical spelling, applied at the SKU entry points —
  `Store.add_item` (stores/keys uppercase), `Store.get_item` (accepts any
  case, so receive/ship/orders do too), `Store.place_order` (records the
  canonical sku) and `csv_io.import_items`. A supplier file spelling `wid-1`
  now updates `WID-1` instead of a second row. Export/CLI/reports unchanged;
  keys written to disk before T08 stay as they are.
- T09 — search: new `reports.search_items(store, query)` -> sku/name/qty rows
  (SKU-sorted, empty list when nothing matches) for items whose name OR sku
  contains `query` case-insensitively; CLI `search QUERY` prints one row per
  match (or "no items match QUERY") and always exits 0.

- T10 — actor tracking: `Item.last_actor` / `Order.last_actor: str | None =
  None` (persisted; absent in legacy state -> None) + new
  `models.record_actor(record, actor)` (writes only when actor is not None, so
  each named change overwrites). `actor=None` kwarg added to `Store.add_item`,
  `receive`, `ship`, `place_order`, `receive_order` (stamps order AND restocked
  item), `cancel_order`, and `csv_io.import_items` (stamps every row it
  touches). CLI `--actor NAME` on all 8 state-changing commands via
  `cli._add_actor(parser)`; `add-supplier` accepts it but suppliers carry no
  actor. CSV `FIELDNAMES` unchanged.

## current

(none — T10 done)
