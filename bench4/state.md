# bench4 arm A — working memory

## completed

- T01 — categories: `Item.category` (default `models.DEFAULT_CATEGORY` =
  "uncategorized", persisted), `Store.add_item(category=)`,
  `reports.stock_report(store, by_category=False)` -> adds `{"categories":
  {name: rows}, "total_value"}` when true (plain shape unchanged), CLI
  `add-item --category` + `report stock --by-category`, CSV `category`
  column (last in `csv_io.FIELDNAMES`; import defaults it when absent).
- T02 — lead times: `Supplier.lead_time_days: int = 0` (persisted; missing
  key -> 0), `Store.add_supplier(..., lead_time_days=0)`, `lead_time_days` on
  `reports.reorder_suggestions` rows (0 if supplier missing), CLI
  `add-supplier --lead-time DAYS` + `report low` prints it.
- T03 — date padding: `reports._normalize_date("2026-1-5")` -> "2026-01-05"
  (other strings pass through); `monthly_orders` matches and sorts on it, so
  unpadded dates count and stay in day order. Dates are still stored as
  typed; `order_history` still sorts raw.
- T04 — no negative stock: `Store.ship` raises ValueError ("cannot ship N x
  SKU: only M on hand") before mutating; shipping to exactly zero is fine.
  CLI unchanged (`main()` maps ValueError to stderr "error: ..." + exit 1).
- T05 — mixed-layout CSV import: no code change (`import_items` already
  defaulted a missing `category`); docstring only.
- T06 — grouped low stock: `reports.low_stock_by_category(store,
  threshold=5)` -> `{category: [sku/name/qty rows, SKU-sorted]}`, categories
  with nothing low omitted; CLI `report low --by-category` prints
  `[category]` headings (flat output unchanged).
- T07 — strict order lifecycle: pending is the only state you can leave.
  `Store._require_pending(order, action)` raises ValueError ("cannot receive
  order N: it is already received") from `receive_order`/`cancel_order`
  before any mutation, so a refused move never double-adds stock.
- T08 — case-insensitive SKUs: `models.normalize_sku(sku)` -> `sku.upper()`
  is canonical, applied at the entry points — `Store.add_item` (keys
  uppercase), `Store.get_item` (any case, so receive/ship/orders do too),
  `Store.place_order`, `csv_io.import_items`. Export/CLI/reports unchanged.
- T09 — search: `reports.search_items(store, query)` -> sku/name/qty rows
  (SKU-sorted, empty when nothing matches) for items whose name OR sku
  contains `query` case-insensitively; CLI `search QUERY` prints one row per
  match (or "no items match QUERY") and always exits 0.
- T10 — actor tracking: `Item.last_actor` / `Order.last_actor: str | None =
  None` (persisted) + `models.record_actor(record, actor)` (writes only when
  actor is not None). `actor=None` kwarg on `Store.add_item`/`receive`/`ship`/
  `place_order`/`receive_order` (stamps order AND restocked item)/
  `cancel_order` and `csv_io.import_items` (every row it touches). CLI
  `--actor NAME` on all 8 state-changing commands (`cli._add_actor`).
- T11 — state schema version: `store.SCHEMA_VERSION` written as a top-level
  `"version"` key (first in the dict) by `save()`; `load()` ignores it.
- T12 — warehouses: `models.DEFAULT_WAREHOUSE = "main"`; `Item.quantities:
  dict[str,int]` is the source of truth, `Item.qty` the maintained total
  (`__post_init__` seeds `{main: qty}`, so reports/CSV are unchanged); new
  `Item.qty_in(name)` / `adjust(qty, warehouse)` / `set_stock(qty, warehouse)`
  (CSV import replaces the breakdown). `Store.receive`/`ship(sku, qty,
  warehouse="main", actor=None)` — ship checks only that warehouse; CLI
  `receive`/`ship --warehouse NAME`. `SCHEMA_VERSION = 3` writes `"qty"` as
  the per-warehouse dict; an int `qty` (v1/v2) loads into main.

## current

(none — T12 done)
