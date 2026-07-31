# bench4 arm A — working memory

## completed

- T01 — categories: `Item.category` (default `models.DEFAULT_CATEGORY` =
  "uncategorized", persisted), `Store.add_item(category=)`, `stock_report(...,
  by_category=True)` -> `{"categories": {name: rows}, "total_value"}`, CLI
  `add-item --category` + `report stock --by-category`, CSV `category` column
  (last in `csv_io.FIELDNAMES`; defaulted on import when absent).
- T02 — lead times: `Supplier.lead_time_days: int = 0` (persisted; missing key
  -> 0), `Store.add_supplier(..., lead_time_days=0)`, `lead_time_days` on
  `reorder_suggestions` rows (0 if no supplier); CLI `add-supplier
  --lead-time DAYS` + `report low` prints it.
- T03 — date padding: `reports._normalize_date("2026-1-5")` -> "2026-01-05"
  (else unchanged); `monthly_orders` matches/sorts on it, dates stored as typed.
- T04 — no negative stock: `Store.ship` raises ValueError ("cannot ship N x
  SKU: only M on hand") first; `main()` maps ValueError -> stderr "error: ..."
  + exit 1.
- T05 — mixed-layout CSV import: no code change.
- T06 — grouped low stock: `reports.low_stock_by_category(store, threshold=5)`
  -> `{category: [sku/name/qty rows, SKU-sorted]}` (empty categories omitted);
  CLI `report low --by-category` prints `[category]` headings.
- T07 — strict order lifecycle: `Store._require_pending(order, action)` raises
  ValueError ("cannot receive order N: it is already received") from
  `receive_order`/`cancel_order` before any mutation.
- T08 — case-insensitive SKUs: `models.normalize_sku(sku)` -> `sku.upper()` is
  canonical, applied at the entry points — `Store.add_item` (keys uppercase),
  `Store.get_item` (any case, so receive/ship/orders do too),
  `Store.place_order`, `csv_io.import_items`. Export/CLI/reports unchanged.
- T09 — search: `reports.search_items(store, query)` -> sku/name/qty rows for
  items whose name OR sku holds `query` (case-insensitive); CLI `search QUERY`.
- T10 — actor tracking: `Item.last_actor`/`Order.last_actor: str | None = None`
  (persisted) + `models.record_actor(record, actor)` (writes only when actor is
  not None); `actor=None` kwarg on every mutating `Store` method and
  `csv_io.import_items`; CLI `--actor NAME` (`cli._add_actor`).
- T11 — schema version: `store.SCHEMA_VERSION` -> top-level `"version"` key
  (first) by `save()`; `load()` ignores it.
- T12 — warehouses: `models.DEFAULT_WAREHOUSE = "main"`; `Item.quantities:
  dict[str,int]` is the truth, `Item.qty` the maintained total (`__post_init__`
  seeds `{main: qty}`, so reports/CSV are unchanged); new `Item.qty_in(name)` /
  `adjust(qty, warehouse)` / `set_stock(qty, warehouse)` (CSV import replaces
  the breakdown). `Store.receive`/`ship(sku, qty, warehouse="main",
  actor=None)` — ship checks only that warehouse; CLI `--warehouse` on both.
  `SCHEMA_VERSION = 3` stores `"qty"` per warehouse; int `qty` (v1/v2) -> main.
- T13 — transfers: `Store.transfer(sku, qty, src, dst, actor=None)` raises
  ValueError ("cannot transfer N x SKU out of SRC: only M on hand") first, else
  `adjust(-qty, src)` + `adjust(qty, dst)`; CLI `transfer SKU QTY SRC DST`
  (no save on error -> exit 1).
- T14 — per-warehouse stock report: `stock_report(store, by_category=False,
  warehouse=None)` — a warehouse name prices qty/value/total on
  `item.qty_in(warehouse)` alone and drops items holding 0 there (unknown one
  -> empty rows, 0.0); `None` unchanged. CLI `report stock --warehouse NAME`.
- T15 — reorder nets out stock on the way: `reorder_suggestions` tallies
  `models.STATUS_PENDING` order qty per SKU, `suggested_qty = max(0, threshold
  - qty - pending)`, and omits the row when that is 0. Qualifying items, other
  fields and the CLI are unchanged.

## current — none (T15 done)
