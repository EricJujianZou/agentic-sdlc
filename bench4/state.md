# bench4 arm A — working memory

## completed

- T01 — categories: `Item.category` (persisted, `models.DEFAULT_CATEGORY` =
  "uncategorized"), `add_item(category=)`, `stock_report(by_category=True)` ->
  `{"categories": {name: rows}, "total_value"}`; CLI `add-item --category`,
  `report stock --by-category`; `category` last in `csv_io.FIELDNAMES`.
- T02 — `Supplier.lead_time_days: int = 0` (persisted; missing -> 0),
  `add_supplier(..., lead_time_days=0)`, on `reorder_suggestions` rows; CLI
  `add-supplier --lead-time DAYS`, shown by `report low`.
- T03 — date padding: `reports._normalize_date("2026-1-5")` -> "2026-01-05"
  (else unchanged); `monthly_orders` matches/sorts on it, dates stored as typed.
- T04 — no negative stock: `ship` raises ValueError ("cannot ship N x SKU: only
  M on hand") first; `main()` maps ValueError -> stderr "error: ..." + exit 1.
- T06 — `reports.low_stock_by_category(store, threshold=5)` -> `{category:
  sku/name/qty rows}`, empty ones omitted; CLI `report low --by-category`.
- T07 — `Store._require_pending(order, action)` raises ValueError ("cannot
  receive order N: it is already received") from `receive_order`/`cancel_order`/
  `ship_order` before any mutation.
- T08 — SKUs are case-insensitive: `models.normalize_sku` (upper) in `add_item`,
  `get_item` (so receive/ship/orders too), `place_order`, `csv_io.import_items`.
- T09 — `reports.search_items(store, query)` -> sku/name/qty rows for items whose
  name OR sku holds `query` (case-insensitive); CLI `search QUERY`.
- T10 — actors: `Item.last_actor`/`Order.last_actor: str | None = None`
  (persisted) + `models.record_actor(record, actor)` (writes only when not None);
  `actor=None` on every mutating `Store` method and `csv_io.import_items`; CLI
  `--actor NAME` (`cli._add_actor`).
- T11 — `store.SCHEMA_VERSION` -> top-level `"version"` key (first) by `save()`.
- T12 — warehouses: `models.DEFAULT_WAREHOUSE = "main"`; `Item.quantities:
  dict[str,int]` is the truth, `Item.qty` the maintained total (`__post_init__`
  seeds `{main: qty}`); `qty_in(wh)`/`adjust(qty, wh)`/`set_stock(qty, wh)`;
  `receive`/`ship(sku, qty, warehouse="main", actor=None)` — ship checks only
  that warehouse; CLI `--warehouse`. v3 `"qty"` per warehouse, int (v1/v2)->main.
- T13 — `Store.transfer(sku, qty, src, dst, actor=None)` raises ValueError
  ("cannot transfer N x SKU out of SRC: only M on hand") before moving anything,
  else `adjust` both; CLI `transfer SKU QTY SRC DST`.
- T14 — `stock_report(store, by_category=False, warehouse=None)`: a warehouse
  name prices qty/value/total on `item.qty_in(wh)` alone, dropping 0s there
  (unknown -> empty, 0.0); `None` unchanged. CLI `--warehouse NAME`.
- T15 — reorder nets out stock: `suggested_qty = max(0, threshold - qty -
  pending)`, pending summing that SKU's pending orders; 0 rows omitted.
- T16 — backups: `Store._write(path)` split out of `save()`; `backup()` ->
  `<state-file>.bak-<colon-free stamp>` beside it, `list_backups()` -> sorted
  names, `restore(name)` -> ValueError unless listed, else copies over the state
  file + reloads; CLI `backup`/`list-backups`/`restore N` (no save after).
- T17 — partial deliveries: `Order.shipped_qty: int = 0` (persisted; older files
  default it to `qty` when received) + `outstanding`; `Store.ship_order(id, qty,
  actor=None)` — pending-only, `1 <= qty <= outstanding` or ValueError first,
  else `_book_delivery` (-> received at 0 outstanding), as does `receive_order`
  for the remainder. CLI `ship-order ID --qty N`.
- T18 — catalogues on `Supplier.skus: list[str]` (persisted, older -> []):
  `Store.add_supplier_sku(sid, sku)` (normalizes, dedupes), `catalog_skus(sid)`,
  `suppliers_for(sku)` -> sorted ids. `Order.supplier_id` (persisted) set by
  `place_order(sku, qty, date, supplier_id=None, actor=None)`: a named supplier
  is validated + wins, else sole catalogue match, several -> ValueError, none ->
  `item.supplier_id`. CLI `catalog-add S SKU`/`catalog-list S`, `--supplier ID`.

## current — none (T18 done)
