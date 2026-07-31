# bench4 arm A — working memory

## completed

- T01 — categories: `Item.category` (persisted, `models.DEFAULT_CATEGORY` =
  "uncategorized"), `add_item(category=)`, `stock_report(by_category=True)` ->
  `{"categories": {name: rows}, "total_value"}`; CLI `--category`/`--by-category`.
- T02 — `Supplier.lead_time_days: int = 0` (persisted; missing -> 0), on
  `add_supplier`/`reorder_suggestions` rows; CLI `add-supplier --lead-time`.
- T03 — date padding: `reports._normalize_date("2026-1-5")` -> "2026-01-05"
  (else unchanged); `monthly_orders` matches/sorts on it, dates stored as typed.
- T04 — no negative stock: `ship` raises ValueError ("cannot ship N x SKU: only
  M on hand") first; `main()` maps ValueError -> stderr "error: ..." + exit 1.
- T06 — `reports.low_stock_by_category(store, threshold=5)` -> `{category:
  sku/name/qty rows}`, empty ones omitted; CLI `report low --by-category`.
- T07 — `Store._require_pending(order, action)` -> ValueError ("cannot receive
  order N: it is already received") in receive/cancel/ship_order, pre-mutation.
- T08 — SKUs are case-insensitive: `models.normalize_sku` (upper) in `add_item`,
  `get_item` (so receive/ship/orders too), `place_order`, `csv_io.import_items`.
- T09 — `reports.search_items(store, query)` -> sku/name/qty rows matching name
  OR sku (case-insensitive substring); CLI `search QUERY`.
- T10 — actors: `Item.last_actor`/`Order.last_actor` (persisted) +
  `models.record_actor(record, actor)` (writes only when not None); `actor=None`
  on every mutating `Store` method + `csv_io.import_items`; CLI `--actor NAME`.
- T11 — `store.SCHEMA_VERSION` -> top-level `"version"` key (first) by `save()`.
- T12 — warehouses: `models.DEFAULT_WAREHOUSE = "main"`; `Item.quantities` is
  the truth, `qty` the maintained total; `qty_in(wh)`/`adjust(qty, wh)`/
  `set_stock(qty, wh)` (replaces all stock); `receive`/`ship` hit the named room
  only; CLI `--warehouse`. Stored `"qty"`: a dict, or an int meaning main.
- T13 — `Store.transfer(sku, qty, src, dst, actor=None)` raises ValueError
  ("cannot transfer N x SKU out of SRC: only M on hand") before moving
  anything, else `adjust` both; CLI `transfer SKU QTY SRC DST`.
- T14 — `stock_report(store, by_category=False, warehouse=None)`: a warehouse
  name prices qty/value/total on `item.qty_in(wh)` alone, dropping 0s there
  (unknown -> empty, 0.0); `None` unchanged. CLI `--warehouse NAME`.
- T15 — reorder nets out stock: `suggested_qty = max(0, threshold - qty -
  pending)`, pending summing that SKU's pending orders; 0 rows omitted.
- T16 — backups: `Store._write(path)` split out of `save()`; `backup()` ->
  `<state-file>.bak-<colon-free stamp>` beside it, `list_backups()` sorted,
  `restore(name)` -> ValueError unless listed, else copy over + reload.
- T17 — partial deliveries: `Order.shipped_qty` (persisted; older files -> `qty`
  when received) + `outstanding`; `Store.ship_order(id, qty, actor=None)` is
  pending-only, `1 <= qty <= outstanding` or ValueError, else `_book_delivery`
  (received at 0 outstanding), as `receive_order` does for the rest.
- T18 — catalogues: `Supplier.skus` (persisted, older -> []),
  `add_supplier_sku(sid, sku)`/`catalog_skus(sid)`/`suppliers_for(sku)`;
  `Order.supplier_id` set by `place_order(..., supplier_id=None)`: named wins,
  else sole catalogue match, several -> ValueError, none -> item's own.
- T19 — CSV v3: `warehouse` last in `csv_io.FIELDNAMES`; export writes one row
  per warehouse holding stock (sorted, `qty` = that room's), stockless -> one
  `main`/0 row. Import is header-name driven (any column order); a `warehouse`
  column sets that room alone via `Item.set_warehouse_stock` (rows accumulate
  per SKU), no column -> `set_stock(qty)` into `main`.
- T20 — shipment log: `models.Shipment` (sku/qty/warehouse/date) in top-level
  `"shipments"` (missing -> []); `Store.ship(..., date=None)` -> today appends
  one (only `ship` — not transfer/receive/orders); `reports.turnover(store)` ->
  `{category: {"YYYY-MM": units}}` off it. CLI `ship --date`/`report turnover`.

## current — none (T20 done)
