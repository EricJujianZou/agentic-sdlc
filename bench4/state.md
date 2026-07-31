# bench4 arm A — working memory

## completed

- T01 — `Item.category` (`models.DEFAULT_CATEGORY`="uncategorized"), `add_item(
  category=)`, `stock_report(by_category=True)` -> `{"categories": {name: rows},
  "total_value"}`; CLI `--category`/`--by-category`.
- T02 — `Supplier.lead_time_days: int = 0` (missing -> 0), on `add_supplier`/
  `reorder_suggestions` rows; CLI `add-supplier --lead-time`.
- T03 — `reports._normalize_date` pads "2026-1-5" -> "2026-01-05";
  `monthly_orders` matches/sorts on it, dates stored as typed.
- T04 — `ship` raises ValueError "cannot ship N x SKU: only M on hand" before
  mutating; `main()` maps ValueError -> stderr "error: ..." + exit 1.
- T06 — `reports.low_stock_by_category(store, threshold=5)` -> `{category:
  sku/name/qty rows}`, empty omitted; CLI `report low --by-category`.
- T07 — `Store._require_pending(order, action)` -> ValueError "cannot ACTION
  order N: it is already STATUS"; receive/cancel/ship_order, pre-mutation.
- T08 — SKUs case-insensitive: `models.normalize_sku` (upper) in `add_item`,
  `get_item` (so receive/ship/orders too), `place_order`, `csv_io.import_items`.
- T09 — `reports.search_items(store, query)` -> sku/name/qty rows matching name OR sku (case-insensitive substring); CLI `search QUERY`.
- T10 — `Item.last_actor`/`Order.last_actor` + `models.record_actor(rec, actor)`
  (writes only when not None); `actor=None` on mutators; CLI `--actor`.
- T11 — `store.SCHEMA_VERSION` -> top-level `"version"` key (first) by `save()`.
- T12 — warehouses (`DEFAULT_WAREHOUSE`="main"): `Item.quantities` is the truth,
  `qty` its total; `qty_in`/`adjust`/`set_stock`/`receive`/`ship` take one room.
- T13 — `Store.transfer(sku, qty, src, dst, actor=None)`: ValueError "cannot
  transfer N x SKU out of SRC: only M on hand" first; CLI `transfer`.
- T14 — `stock_report(store, by_category=False, warehouse=None)`: a warehouse
  prices on `qty_in(wh)` alone, dropping 0s (`None` unchanged); CLI `--warehouse`.
- T15 — reorder nets out stock: `max(0, threshold - qty - pending)` over that SKU's pending orders (omission rule: T27).
- T16 — `Store._write(path)` split out of `save()`; `backup()` -> `<state>.bak-
  <stamp>`, `list_backups()` sorted, `restore(name)` (ValueError unless listed).
- T17 — `Order.shipped_qty` (older -> `qty` when received) + `outstanding`;
  `ship_order(id, qty)` pending-only, 1..outstanding; `receive_order` = the rest.
- T18 — `Supplier.skus` (older -> []), `add_supplier_sku`/`catalog_skus`/
  `suppliers_for`; `place_order(supplier_id=)`: named > sole match > item's.
- T19 — CSV v3: `warehouse` last in `csv_io.FIELDNAMES`, one row per stocked
  warehouse; import is header-name driven, no column -> main.
- T20 — `models.Shipment` (sku/qty/warehouse/date) in `"shipments"`; `ship(...,
  date=None)` appends one; `turnover(store)` -> `{category: {"YYYY-MM": units}}`.
- T21/T22/T23 — whole cents (v4): `models.to_cents`/`to_dollars`,
  `Item.unit_price_cents` the truth + `unit_price` property, exact `stock_report`;
  `Item.price_history` `{"date","old","new"}` dollars in memory, `old_cents`/`new_cents` saved; `set_price(sku, price, date=None, actor=None)`, `reports.price_changes`, CLI `set-price`.
- T24 — `stockroom.money.format_money(amount)` -> `"$X.XX"` (`int` = cents,
  `float` = dollars, negatives `-$X.XX`); every CLI money figure goes through it.
- T25 — `Store.discounts` category -> percent (`"discounts"`, missing -> `{}`):
  `set_discount` (ValueError outside 0..100), `get_discount` -> percent or 0.0, `list_discounts`, `remove_discount` (ValueError when no rule); CLI for each.
- T26 — `Store.tax_rate` (`"tax_rate"`, missing -> 0.0) + `set_tax_rate` (ValueError when negative); `models.percent_of(cents, percent)` -> cents, half up;
  `reports.order_total(store, order_id)` -> dollars `subtotal`/`discount`/`tax`/`total` (qty x price, discount off, tax on rest); CLI `set-tax-rate PCT`/`invoice ID`.
- T27 — `reorder_suggestions` flags on `qty <= threshold` (same test as `low_stock`) and keeps `suggested_qty == 0` rows; only an item whose pending orders cover the top-up is still omitted (T15). CLI/report shape unchanged.
- T28 — `invoice ID --output PATH` also writes the invoice as text via
  `cli._invoice_text(store, order_id, breakdown)`: order id/sku/qty/date then the four breakdown lines, `\n`, no timestamps -> byte-identical re-runs; composed after pricing, so an unknown id exits 1 writing nothing. Screen output unchanged.
- T29 — `reports.monthly_revenue(store, month)` -> `{"rows": [{id, sku, total}]
  oldest first, "total"}` over *received* orders dated in the month; priced by
  `reports._order_total_cents(store, order)` (the cents half of `order_total`,
  split out so sums stay exact). CLI `report revenue YYYY-MM`, last line always
  `Total revenue: $X.XX`.

## current — none (T29 done)
