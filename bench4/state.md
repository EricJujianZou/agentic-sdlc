# bench4 arm A — working memory

## completed

- T01 — `Item.category` (persisted, `models.DEFAULT_CATEGORY`="uncategorized"),
  `add_item(category=)`, `stock_report(by_category=True)` -> `{"categories":
  {name: rows}, "total_value"}`; CLI `--category`/`--by-category`.
- T02 — `Supplier.lead_time_days: int = 0` (persisted; missing -> 0), on
  `add_supplier`/`reorder_suggestions` rows; CLI `add-supplier --lead-time`.
- T03 — `reports._normalize_date("2026-1-5")` -> "2026-01-05" (else unchanged);
  `monthly_orders` matches/sorts on it, dates stored as typed.
- T04 — `ship` raises ValueError "cannot ship N x SKU: only M on hand" before
  mutating; `main()` maps ValueError -> stderr "error: ..." + exit 1.
- T06 — `reports.low_stock_by_category(store, threshold=5)` -> `{category:
  sku/name/qty rows}`, empty omitted; CLI `report low --by-category`.
- T07 — `Store._require_pending(order, action)` -> ValueError "cannot receive
  order N: it is already received"; in receive/cancel/ship_order, pre-mutation.
- T08 — SKUs case-insensitive: `models.normalize_sku` (upper) in `add_item`,
  `get_item` (so receive/ship/orders too), `place_order`, `csv_io.import_items`.
- T09 — `reports.search_items(store, query)` -> sku/name/qty rows matching name
  OR sku (case-insensitive substring); CLI `search QUERY`.
- T10 — `Item.last_actor`/`Order.last_actor` + `models.record_actor(record,
  actor)` (writes only when not None); `actor=None` on mutators; CLI `--actor`.
- T11 — `store.SCHEMA_VERSION` -> top-level `"version"` key (first) by `save()`.
- T12 — warehouses: `DEFAULT_WAREHOUSE`="main"; `Item.quantities` is the truth,
  `qty` its total; `qty_in(wh)`/`adjust(qty,wh)`/`set_stock(qty,wh)`; `receive`/
  `ship` hit one room; CLI `--warehouse`; stored `"qty"` = dict or int.
- T13 — `Store.transfer(sku, qty, src, dst, actor=None)`: ValueError "cannot
  transfer N x SKU out of SRC: only M on hand" before moving, else `adjust`
  both; CLI `transfer SKU QTY SRC DST`.
- T14 — `stock_report(store, by_category=False, warehouse=None)`: a warehouse
  name prices qty/value/total on `qty_in(wh)` alone, dropping 0s there (unknown
  -> empty, 0.0); `None` unchanged. CLI `--warehouse NAME`.
- T15 — reorder nets out stock: `suggested_qty = max(0, threshold - qty -
  pending)`, pending summing that SKU's pending orders; 0 rows omitted.
- T16 — `Store._write(path)` split out of `save()`; `backup()` ->
  `<state-file>.bak-<colon-free stamp>` beside it, `list_backups()` sorted,
  `restore(name)` -> ValueError unless listed, else copy over + reload.
- T17 — `Order.shipped_qty` (older -> `qty` when received) + `outstanding`;
  `ship_order(id, qty)` pending-only, 1..outstanding; `receive_order` = the rest.
- T18 — `Supplier.skus` (older -> []), `add_supplier_sku`/`catalog_skus`/
  `suppliers_for`; `place_order(...,supplier_id=)`: named > sole match > item's.
- T19 — CSV v3: `warehouse` last in `csv_io.FIELDNAMES`, one row per stocked
  warehouse; import is header-name driven, no column -> main.
- T20 — `models.Shipment` (sku/qty/warehouse/date) in `"shipments"`; `ship(...,
  date=None)` appends one; `turnover(store)` -> `{category: {"YYYY-MM": units}}`.
- T21 — `Item.price_history` of `{"date","old","new"}` (dollars); `set_price(sku,
  price, date=None, actor=None)`; `reports.price_changes`; CLI `set-price`.
- T22 — `stock_report` values exact (no float drift in line values or total).
  API/CLI unchanged.
- T23 — money is whole cents: `models.to_cents`/`to_dollars`,
  `Item.unit_price_cents` is the truth and `unit_price` a dollars property over
  it; schema v4 stores `unit_price_cents` + history `old_cents`/`new_cents`
  (v1-v3 float keys still read); `stock_report` sums in cents. API/CLI same.
- T24 — `stockroom.money.format_money(amount)` -> `"$X.XX"` (`int` = cents,
  `float` = dollars, negatives `-$X.XX`); every money figure the CLI prints
  (stock price/value/total, price-changes, `set-price`) goes through it.

## current — none (T24 done)
