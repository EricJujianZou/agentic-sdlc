"""argparse CLI for ledgerlite."""

import argparse
import os

from . import report, storage
from .ledger import Entry, Ledger


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ledgerlite")
    p.add_argument("--file", default="ledger.json", help="path to the ledger JSON file")
    p.add_argument("--ledger", default=None, help="name of the ledger inside the file")
    sub = p.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="add an entry")
    add.add_argument("--date", required=True)
    add.add_argument("--amount", type=float, required=True)
    add.add_argument("--note", default="")
    add.add_argument("--category", default="uncategorized")

    sub.add_parser("list", help="list entries")
    sub.add_parser("total", help="print the grand total")

    rep = sub.add_parser("report", help="monthly summary")
    rep.add_argument("--year", type=int, required=True)
    rep.add_argument("--month", type=int, required=True)

    return p


def _load(path: str, name: str | None = None) -> Ledger:
    if os.path.exists(path):
        try:
            return storage.load(path, name)
        except KeyError:
            return Ledger()
    return Ledger()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    ledger = _load(args.file, args.ledger)

    if args.command == "add":
        ledger.add(Entry(args.date, args.amount, args.note, category=args.category))
        storage.save(ledger, args.file, args.ledger)
        print("added")
    elif args.command == "list":
        for e in ledger.entries():
            print(f"{e.date}\t{e.amount:.2f}\t{e.category}\t{e.note}")
    elif args.command == "total":
        print(f"{ledger.total():.2f}")
    elif args.command == "report":
        print(report.format_month(ledger, args.year, args.month))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
