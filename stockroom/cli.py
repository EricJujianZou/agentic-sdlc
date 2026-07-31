"""Command line interface for the stockroom.

Usage::

    python -m stockroom.cli --data <dir> <command> [args...]

``--data`` names a directory; state is kept in ``<dir>/state.json``.

Exit codes: 0 on success, 1 on a user error (unknown SKU, bad order id,
missing file, ...), 2 when the state file cannot be parsed.
"""

import argparse
import datetime
import json
import os
import sys

from . import __version__, csv_io, reports
from .models import DEFAULT_CATEGORY
from .store import Store


# ----------------------------------------------------------------------
# command handlers -- each takes (store, args) and returns an exit code
# ----------------------------------------------------------------------

def cmd_add_item(store: Store, args) -> int:
    """Handle ``add-item``: create a new item in the catalogue."""
    item = store.add_item(
        args.sku,
        args.name,
        qty=args.qty,
        unit_price=args.price,
        supplier_id=args.supplier,
        category=args.category,
    )
    store.save()
    print(f"added item {item.sku} ({item.name})")
    return 0


def cmd_add_supplier(store: Store, args) -> int:
    """Handle ``add-supplier``: register a new supplier."""
    supplier = store.add_supplier(args.id, args.name, args.email)
    store.save()
    print(f"added supplier {supplier.id} ({supplier.name})")
    return 0


def cmd_receive(store: Store, args) -> int:
    """Handle ``receive``: goods arrived outside of an order."""
    item = store.receive(args.sku, args.qty)
    store.save()
    print(f"received {args.qty} x {item.sku}, now {item.qty} on hand")
    return 0


def cmd_ship(store: Store, args) -> int:
    """Handle ``ship``: send units out of the stockroom."""
    item = store.ship(args.sku, args.qty)
    store.save()
    print(f"shipped {args.qty} x {item.sku}, now {item.qty} on hand")
    return 0


def cmd_place_order(store: Store, args) -> int:
    """Handle ``place-order``: record a pending purchase order."""
    date = args.date
    if date is None:
        date = datetime.date.today().isoformat()
    order = store.place_order(args.sku, args.qty, date)
    store.save()
    print(f"placed order {order.id}: {order.qty} x {order.sku} on {order.date}")
    return 0


def cmd_receive_order(store: Store, args) -> int:
    """Handle ``receive-order``: an order arrived; stock it."""
    order = store.receive_order(args.id)
    store.save()
    print(f"order {order.id} received, {order.qty} x {order.sku} added to stock")
    return 0


def cmd_cancel_order(store: Store, args) -> int:
    """Handle ``cancel-order``: mark an order cancelled."""
    order = store.cancel_order(args.id)
    store.save()
    print(f"order {order.id} cancelled")
    return 0


def _print_stock_header() -> None:
    print(f"{'SKU':<12} {'NAME':<24} {'QTY':>6} {'PRICE':>10} {'VALUE':>10}")


def _print_stock_rows(rows: list[dict]) -> None:
    for row in rows:
        print(f"{row['sku']:<12} {row['name']:<24} {row['qty']:>6} "
              f"{row['unit_price']:>10.2f} {row['value']:>10.2f}")


def cmd_report_stock(store: Store, args) -> int:
    """Handle ``report stock``: print the full stock listing, optionally
    grouped under one heading per shelf area."""
    report = reports.stock_report(store, by_category=args.by_category)
    if args.by_category:
        for category in sorted(report["categories"]):
            print(f"[{category}]")
            _print_stock_header()
            _print_stock_rows(report["categories"][category])
            print()
    else:
        _print_stock_header()
        _print_stock_rows(report["rows"])
    print(f"Total value: {report['total_value']:.2f}")
    return 0


def cmd_report_low(store: Store, args) -> int:
    """Handle ``report low``: print items running low, plus
    reorder suggestions for the ones we can actually reorder."""
    rows = reports.low_stock(store, threshold=args.threshold)
    if not rows:
        print("no items at or below threshold")
        return 0
    for row in rows:
        print(f"{row['sku']:<12} {row['name']:<24} {row['qty']:>6}")
    suggestions = reports.reorder_suggestions(store, threshold=args.threshold)
    if suggestions:
        print()
        print("reorder suggestions:")
        for row in suggestions:
            print(f"  {row['sku']}: order {row['suggested_qty']} "
                  f"from {row['supplier_id']}")
    return 0


def cmd_report_monthly(store: Store, args) -> int:
    """Handle ``report monthly``: print orders for one month."""
    rows = reports.monthly_orders(store, args.month)
    if not rows:
        print(f"no orders in {args.month}")
        return 0
    for row in rows:
        print(f"{row['date']:<12} order {row['id']:>4}  "
              f"{row['qty']:>4} x {row['sku']:<12} {row['status']}")
    print(f"{len(rows)} orders in {args.month}")
    return 0


def cmd_report_history(store: Store, args) -> int:
    """Handle ``report history``: print all orders for a SKU."""
    store.get_item(args.sku)  # complain early about unknown SKUs
    rows = reports.order_history(store, args.sku)
    if not rows:
        print(f"no orders for {args.sku}")
        return 0
    for row in rows:
        print(f"{row['date']:<12} order {row['id']:>4}  "
              f"{row['qty']:>4}  {row['status']}")
    return 0


def cmd_export_csv(store: Store, args) -> int:
    """Handle ``export-csv``: write the item list to a file."""
    count = csv_io.export_items(store, args.path)
    print(f"exported {count} items to {args.path}")
    return 0


def cmd_import_csv(store: Store, args) -> int:
    """Handle ``import-csv``: merge items from a CSV file."""
    if not os.path.exists(args.path):
        raise ValueError(f"no such file: {args.path}")
    count = csv_io.import_items(store, args.path)
    store.save()
    print(f"imported {count} rows from {args.path}")
    return 0


# ----------------------------------------------------------------------
# argument parsing
# ----------------------------------------------------------------------

EXAMPLES = """\
examples:
  stockroom --data ./data add-supplier acme "Acme Supply" orders@acme.example
  stockroom --data ./data add-item WID-1 "Widget" --qty 10 --price 19.99 --supplier acme
  stockroom --data ./data ship WID-1 3
  stockroom --data ./data place-order WID-1 20 --date 2026-07-01
  stockroom --data ./data receive-order 1
  stockroom --data ./data report stock
  stockroom --data ./data report monthly 2026-07
  stockroom --data ./data export-csv items.csv
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stockroom",
        description="Track stockroom inventory, suppliers and orders.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version",
                        version=f"stockroom {__version__}")
    parser.add_argument("--data", required=True,
                        help="directory holding state.json")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add-item", help="create a new item")
    p.add_argument("sku")
    p.add_argument("name")
    p.add_argument("--qty", type=int, default=0)
    p.add_argument("--price", type=float, default=0.0)
    p.add_argument("--supplier", default=None)
    p.add_argument("--category", default=DEFAULT_CATEGORY,
                   help=f"shelf area (default: {DEFAULT_CATEGORY})")
    p.set_defaults(func=cmd_add_item)

    p = sub.add_parser("add-supplier", help="create a new supplier")
    p.add_argument("id")
    p.add_argument("name")
    p.add_argument("email")
    p.set_defaults(func=cmd_add_supplier)

    p = sub.add_parser("receive", help="add units of an item to stock")
    p.add_argument("sku")
    p.add_argument("qty", type=int)
    p.set_defaults(func=cmd_receive)

    p = sub.add_parser("ship", help="remove units of an item from stock")
    p.add_argument("sku")
    p.add_argument("qty", type=int)
    p.set_defaults(func=cmd_ship)

    p = sub.add_parser("place-order", help="record a purchase order")
    p.add_argument("sku")
    p.add_argument("qty", type=int)
    p.add_argument("--date", default=None,
                   help="order date (default: today)")
    p.set_defaults(func=cmd_place_order)

    p = sub.add_parser("receive-order",
                       help="mark an order received and stock the goods")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_receive_order)

    p = sub.add_parser("cancel-order", help="cancel an order")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_cancel_order)

    report = sub.add_parser("report", help="print a report")
    report_sub = report.add_subparsers(dest="report_kind", required=True)

    p = report_sub.add_parser("stock", help="full stock listing with values")
    p.add_argument("--by-category", action="store_true",
                   help="group the listing by shelf area")
    p.set_defaults(func=cmd_report_stock)

    p = report_sub.add_parser("low", help="items running low")
    p.add_argument("--threshold", type=int, default=reports.DEFAULT_THRESHOLD)
    p.set_defaults(func=cmd_report_low)

    p = report_sub.add_parser("monthly", help="orders placed in a month")
    p.add_argument("month", help="month prefix, e.g. 2026-01")
    p.set_defaults(func=cmd_report_monthly)

    p = report_sub.add_parser("history", help="order history for one SKU")
    p.add_argument("sku")
    p.set_defaults(func=cmd_report_history)

    p = sub.add_parser("export-csv", help="write items to a CSV file")
    p.add_argument("path")
    p.set_defaults(func=cmd_export_csv)

    p = sub.add_parser("import-csv", help="read items from a CSV file")
    p.add_argument("path")
    p.set_defaults(func=cmd_import_csv)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    state_path = os.path.join(args.data, "state.json")
    store = Store(state_path)
    try:
        store.load()
    except json.JSONDecodeError as exc:
        print(f"error: state file {state_path} is corrupt: {exc}",
              file=sys.stderr)
        return 2

    try:
        return args.func(store, args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
