"""Command line: researchcop run | ingest | review | verify | sources | report | status | demo"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import __version__, config, ingest, report


def _log(msg: str):
    print(msg, flush=True)


def _docs(cfg, only: str | None):
    metas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((cfg.out / "docs").glob("*/meta.json"))]
    return [m for m in metas if not only or only.lower() in m["id"].lower() or only.lower() in m["source"].lower()]


def _parallel(cfg, metas, fn, label: str):
    if not metas:
        _log("  (no documents – run `researchcop ingest` first)")
        return
    errors = cfg.out / "errors.log"
    with ThreadPoolExecutor(max_workers=max(1, int(cfg["run"]["workers"]))) as ex:
        futs = {ex.submit(fn, m): m for m in metas}
        for i, fut in enumerate(as_completed(futs), 1):
            m = futs[fut]
            try:
                fut.result()
                _log(f"  [{i}/{len(metas)}] {label} {m['id']}")
            except Exception as e:
                _log(f"  [{i}/{len(metas)}] {label} {m['id']} FAILED: {e}")
                with open(errors, "a", encoding="utf-8") as f:
                    f.write(f"--- {label} {m['id']}\n{traceback.format_exc()}\n")


def _check_credentials():
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        _log("  note: no ANTHROPIC_API_KEY in the environment; the SDK will try an `ant auth login` profile.")


def cmd_ingest(cfg, args):
    _log("Ingest")
    ingest.ingest(cfg, _log)


def cmd_review(cfg, args):
    from . import review
    _check_credentials()
    metas = _docs(cfg, args.only)
    _log("Review (first)")
    _parallel(cfg, metas, lambda m: review.run_review(cfg, m, "first", args.force), "review")
    if args.second or cfg["review"]["second_review"]:
        _log("Review (blind second)")
        _parallel(cfg, metas, lambda m: review.run_review(cfg, m, "second", args.force), "second")


def cmd_verify(cfg, args):
    from . import review
    _check_credentials()
    _log(f"Verify findings with severity >= {cfg['review']['verify_min_severity']}")
    _parallel(cfg, _docs(cfg, args.only), lambda m: review.run_verify(cfg, m, args.force), "verify")


def cmd_sources(cfg, args):
    from . import review, sources

    def one(m):
        refs = json.loads(review.run_references(cfg, m, args.force).read_text(encoding="utf-8"))
        out = review.result_dir(cfg, m["id"]) / "sources.json"
        if out.exists() and not args.force:
            return
        pdir = cfg.out / "docs" / m["id"] / "pages"
        pages = [(pdir / f"p{i:03d}.txt").read_text(encoding="utf-8") for i in range(1, m["n_pages"] + 1)]
        res = sources.check(refs["references"], pages, cfg, _log)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    _check_credentials()
    _log("Sources (reference list + doi.org/Crossref)")
    _parallel(cfg, _docs(cfg, args.only), one, "sources")


def cmd_report(cfg, args):
    _log("Report")
    data = report.collect(cfg, crops=not args.no_crops, log=_log)
    out = report.write(cfg, data)
    _log(f"  {len(data['docs'])} texts -> {out}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())


def cmd_run(cfg, args):
    cmd_ingest(cfg, args)
    cmd_review(cfg, args)
    cmd_verify(cfg, args)
    if not args.skip_sources:
        cmd_sources(cfg, args)
    cmd_report(cfg, args)


def cmd_status(cfg, args):
    rows = _docs(cfg, args.only)
    _log(f"{'document':<48} {'kind':<5} {'pages':>5}  review second verify sources")
    for m in rows:
        r = cfg.out / "results" / m["id"]
        flag = lambda f: "  x   " if (r / f).exists() else "  -   "
        _log(f"{m['id']:<48} {m['kind']:<5} {m['n_pages']:>5}  {flag('review.json')}{flag('second.json')}{flag('verify.json')}{flag('sources.json')}")


def cmd_demo(cfg, args):
    from . import demo
    out = demo.build(Path(args.root or ".").resolve() / "output-demo")
    _log(f"Demo report (fictional data, no API calls) -> {out}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())


def main(argv=None):
    p = argparse.ArgumentParser(prog="researchcop", description="Evidence-backed error analysis of scientific articles with Claude.")
    p.add_argument("--version", action="version", version=f"researchcop {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="path to config.toml (default: ./config.toml)")
    common.add_argument("--root", help="project folder containing input/ and output/ (default: current folder)")
    common.add_argument("--only", help="process only documents whose id or source contains this text")
    common.add_argument("--force", action="store_true", help="redo steps that already have results")
    common.add_argument("--model", help="override the review and verify model")
    common.add_argument("--workers", type=int, help="documents processed in parallel")
    common.add_argument("--second", action="store_true", help="also run a blind second review")
    common.add_argument("--no-crops", action="store_true", help="report without evidence images")
    common.add_argument("--skip-sources", action="store_true", help="run: skip the source check")
    common.add_argument("--open", action="store_true", help="open the report in the browser")
    for name, fn, hlp in [
        ("run", cmd_run, "all steps: ingest, review, verify, sources, report"),
        ("ingest", cmd_ingest, "read input/ (files, urls.txt, manifest.csv)"),
        ("review", cmd_review, "first (and optionally blind second) review"),
        ("verify", cmd_verify, "re-check substantial findings against the source"),
        ("sources", cmd_sources, "extract references, resolve DOIs, search Crossref"),
        ("report", cmd_report, "build the HTML dashboard"),
        ("status", cmd_status, "show which steps are done per document"),
        ("demo", cmd_demo, "build a demo dashboard from fictional data (no API key needed)"),
    ]:
        sp = sub.add_parser(name, parents=[common], help=hlp)
        sp.set_defaults(fn=fn)
    args = p.parse_args(argv)
    ov = {}
    if args.model:
        ov["models"] = {"review": args.model, "verify": args.model}
    if args.workers:
        ov["run"] = {"workers": args.workers}
    cfg = config.load(args.config, args.root, ov)
    try:
        args.fn(cfg, args)
    except KeyboardInterrupt:
        sys.exit(130)
