# bench4 arm A — working memory

## completed

- T01 — `Item.category` (`DEFAULT_CATEGORY`="uncategorized"), `add_item(category=)`, `stock_report(by_category=True)` -> `{"categories", "total_value"}`; CLI `--category`/`--by-category`.
- T02 — `Supplier.lead_time_days: int = 0` (missing -> 0), on `add_supplier`/`reorder_suggestions` rows; CLI `add-supplier --lead-time`.
- T03 — `reports._normalize_date` pads "2026-1-5" -> "2026-01-05"; `monthly_orders` matches/sorts on it, dates stored as typed.
- T04 — `ship` raises ValueError "cannot ship N x SKU: only M on hand" before mutating; `main()` maps ValueError -> stderr "error: ..." + exit 1.
- T06 — `reports.low_stock_by_category(store, threshold=5)` -> `{category: sku/name/qty rows}`, empty omitted; CLI `report low --by-category`.
- T07 — `Store._require_pending(order, action)` -> ValueError "cannot ACTION order N: it is already STATUS"; receive/cancel/ship_order, pre-mutation.
- T08 — SKUs case-insensitive: `models.normalize_sku` (upper) in `add_item`, `get_item` (so receive/ship/orders too), `place_order`, `csv_io.import_items`.
- T09 — `reports.search_items(store, query)` -> sku/name/qty rows matching name OR sku (case-insensitive substring); CLI `search QUERY`.
- T10 — `Item.last_actor`/`Order.last_actor` + `models.record_actor(rec, actor)` (writes only when not None); `actor=None` on mutators; CLI `--actor`.
- T11 — `store.SCHEMA_VERSION` -> top-level `"version"` key (first) by `save()`.
- T12 — warehouses (`DEFAULT_WAREHOUSE`="main"): `Item.quantities` is the truth, `qty` its total; `qty_in`/`adjust`/`set_stock`/`receive`/`ship` take one room.
- T13 — `Store.transfer(sku, qty, src, dst, actor=None)`: ValueError "cannot transfer N x SKU out of SRC: only M on hand" first; CLI `transfer`.
- T14 — `stock_report(store, by_category=False, warehouse=None)`: a warehouse prices on `qty_in(wh)` alone, dropping 0s (`None` unchanged); CLI `--warehouse`.
- T15 — reorder nets out stock: `max(0, threshold - qty - pending)` over that SKU's pending orders (omission rule: T27).
- T16 — `Store._write(path)` split out of `save()`; `backup()` -> `<state>.bak-<stamp>`, `list_backups()` sorted, `restore(name)` (ValueError unless listed).
- T17 — `Order.shipped_qty` (older -> `qty` when received) + `outstanding`; `ship_order(id, qty)` pending-only, 1..outstanding; `receive_order` = the rest.
- T18 — `Supplier.skus` (older -> []), `add_supplier_sku`/`catalog_skus`/`suppliers_for`; `place_order(supplier_id=)`: named > sole match > item's.
- T19 — CSV v3: `warehouse` last in `csv_io.FIELDNAMES`, one row per stocked warehouse; import is header-name driven, no column -> main.
- T20 — `models.Shipment` (sku/qty/warehouse/date) in `"shipments"`; `ship(..., date=None)` appends one; `turnover(store)` -> `{category: {"YYYY-MM": units}}`.
- T21/T22/T23 — whole cents (v4): `models.to_cents`/`to_dollars`, `Item.unit_price_cents` the truth + `unit_price` property, exact `stock_report`;
  `Item.price_history` `{"date","old","new"}` dollars in memory, `old_cents`/`new_cents` saved; `set_price(sku, price, date=None, actor=None)`, `reports.price_changes`, CLI `set-price`.
- T24 — `stockroom.money.format_money(amount)` -> `"$X.XX"` (`int` = cents, `float` = dollars, negatives `-$X.XX`); every CLI money figure goes through it.
- T25 — `Store.discounts` category -> percent (`"discounts"`, missing -> `{}`): `set_discount` (ValueError outside 0..100), `get_discount` -> percent or 0.0, `list_discounts`, `remove_discount` (ValueError when no rule); CLI for each.
- T26 — `Store.tax_rate` (`"tax_rate"`, missing -> 0.0) + `set_tax_rate` (ValueError when negative); `models.percent_of(cents, percent)` -> cents, half up;
  `reports.order_total(store, order_id)` -> dollars `subtotal`/`discount`/`tax`/`total` (qty x price, discount off, tax on rest); CLI `set-tax-rate PCT`/`invoice ID`.
- T27 — `reorder_suggestions` flags on `qty <= threshold` (same test as `low_stock`) and keeps `suggested_qty == 0` rows; only an item whose pending orders cover the top-up is still omitted (T15). CLI/report shape unchanged.
- T28 — `invoice ID --output PATH` also writes the invoice as text via `cli._invoice_text(store, order_id, breakdown)`: order id/sku/qty/date then the four breakdown lines, `\n`, no timestamps -> byte-identical re-runs; composed after pricing, so an unknown id exits 1 writing nothing.
- T29 — `reports.monthly_revenue(store, month)` -> `{"rows": [{id, sku, total}] oldest first, "total"}` over *received* orders dated in that month, priced by `reports._order_total_cents` (the cents half of `order_total`, split out so sums stay exact); CLI `report revenue YYYY-MM`, last line `Total revenue: $X.XX`.
- T30 — `money.format_amount` (`format_money` sans `$`, now built on it) and `money.parse_money(text)` -> dollars (` 3.5 `/`$3.50`, else ValueError -> exit 1); CSV export prices via the first, import via the second.
- T31 — `Order.received_date` (None on older orders), stamped by `_book_delivery` when an order tips to received: `receive_order(id, actor=, date=)` -> today when omitted; CLI `receive-order --date`.
  `reports.supplier_on_time(store)` -> `[{supplier_id, total, on_time, pct}]` sorted by id, over received orders *with* a date, grouped by the **item's** supplier, on time when arrival <= placed + lead time (`_as_date` parses via `_normalize_date`); no countable orders -> supplier omitted. CLI `report on-time`.
- T32 — every stored date is ISO `YYYY-MM-DD` (v5): `stockroom.dates` = `parse_date` (accepts `YYYY-M-D`, ValueError -> exit 1 on anything not a real day),
  `normalize_date` -> ISO str, `normalize_stored` (tolerant, unparseable/None kept) used by `Order`/`Shipment`/price-history `from_dict` so legacy dates normalize on load and save back padded;
  `place_order`/`ship`/`set_price`/`receive_order` normalize before mutating. `reports._in_month(date, month)` (parsed, not prefix) drives `monthly_orders`/`monthly_revenue`; `_normalize_date`/`_as_date` now delegate to `dates`.
- T33 — `reports.AGING_BUCKETS` = `("0-7", "8-30", "31+")` and `order_aging(store, as_of)` (ISO str or `date`):
  pending orders only, age = whole days from order date to as-of -> `<=7`/`<=30`/rest; every bucket key always
  present, rows (id/sku/qty/date) oldest first. CLI `report aging [--as-of YYYY-MM-DD]` (default today) prints
  all three headings, "(none)" under an empty one; bad date -> exit 1.
- T34 — audit trail: `store.events` (`"events"`, missing -> []) is a list of dicts
  `{"op", "args", "actor", "timestamp"}`, oldest first, appended by `store.log_event(op, args, actor)`.
  Every `Store` mutator calls it once, last (so a refused op logs nothing and library calls log too), with
  `op` spelled as the CLI command ("add-item", "place-order", ...); `csv_io.import_items` logs one
  "import-csv" per file. `add_supplier`/`set_discount`/`remove_discount`/`set_tax_rate`/`add_supplier_sku`
  gained `actor=` (audit only) + `--actor` on their CLI commands. Reports/exports/backup/restore log nothing.
- T35 — `Store.undo()` reverses the newest change and pops it off `store.events` (the trail
  *is* the undo history, so undo repeats step by step and reaches earlier sessions):
  `Store._UNDO` maps op -> inverse handler working from the logged args + current state —
  add-item/add-supplier delete, receive/ship/transfer adjust back (ship drops its shipment
  too), place-order removes the order, cancel-order -> pending, set-price pops the last
  `price_history` entry and restores `old`. Undo logs nothing itself, leaves `last_actor`
  alone, and raises before mutating: "nothing to undo" (empty trail) or "cannot undo OP"
  (op not in `_UNDO`: set-discount/set-tax-rate/receive-order/import-csv/catalog-add ...).
  CLI `undo` (no args), saving only on success.

## current — none (T35 done)
