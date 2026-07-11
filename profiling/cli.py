"""Command-line entry point for the profiling suite.

Commands: ``quick``, ``full``, ``diagnose WORKLOAD_ID``, and
``baseline update``. Exit codes are truthful about *correctness*, never about
performance: ``0`` clean, ``1`` when any sample errored, ``2`` for argument or
infrastructure failures. Performance warnings never change the exit code.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .report import update_baseline, write_report
from .runner import RunConfig, run_suite


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="profile_suite",
                                     description="Deterministic profiling suite")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--backend", default=None,
                       help="cpu | gpu | all | auto (default depends on command)")
        p.add_argument("--repeat", type=int, default=None,
                       help="override the per-workload repeat count")
        p.add_argument("--category", action="append", default=[], dest="categories")
        p.add_argument("--exclude-category", action="append", default=[],
                       dest="excluded_categories")
        p.add_argument("--output", default="artifacts/profiling")
        p.add_argument("--baseline", default=None)
        p.add_argument("--playwright", default=None,
                       help="ingest pre-existing Playwright JSONL rows")

    quick = sub.add_parser("quick", help="fast CPU sanity profile")
    add_common(quick)

    full = sub.add_parser("full", help="every workload across available backends")
    add_common(full)

    diagnose = sub.add_parser("diagnose", help="deep profile one workload")
    diagnose.add_argument("workload")
    add_common(diagnose)

    baseline = sub.add_parser("baseline", help="manage named baselines")
    baseline_sub = baseline.add_subparsers(dest="baseline_command", required=True)
    update = baseline_sub.add_parser("update", help="promote a results file to a baseline")
    update.add_argument("--from", dest="from_path", required=True)
    update.add_argument("--name", required=True)
    update.add_argument("--output", default="profiling/baselines")

    return parser


def _default_backend(command: str, requested: str | None) -> str:
    if requested:
        return requested
    return "all" if command == "full" else "cpu"


def _run_profile(args) -> int:
    from .workload import get_workload, reset_registry_for_tests
    from .workloads import register_all

    reset_registry_for_tests()
    register_all()

    workload_ids: tuple[str, ...] = ()
    if args.command == "diagnose":
        try:
            get_workload(args.workload)
        except KeyError:
            print(f"Unknown workload: {args.workload}", file=sys.stderr)
            return 2
        workload_ids = (args.workload,)

    config = RunConfig(
        mode=args.command,
        backend=_default_backend(args.command, args.backend),
        repeat=args.repeat,
        categories=tuple(args.categories),
        excluded_categories=tuple(args.excluded_categories),
        output_dir=Path(args.output),
    )

    run = run_suite(workload_ids, config)

    if args.playwright:
        run = _ingest_browser_rows(run, Path(args.playwright))
    elif args.command == "full" and _browser_selected(config):
        run = _run_and_ingest_browser(run, config)

    baseline = Path(args.baseline) if args.baseline else None
    try:
        write_report(run, Path(args.output), baseline=baseline)
    except (ValueError, OSError) as exc:
        print(f"Baseline/report error: {exc}", file=sys.stderr)
        return 2

    return 1 if any(sample.outcome == "error" for sample in run.samples) else 0


def _browser_selected(config: RunConfig) -> bool:
    if "browser" in config.excluded_categories:
        return False
    return not config.categories or "browser" in config.categories


def _browser_environment():
    from .model import Environment

    return Environment(
        os_name="", os_version="", machine="", processor="", python="",
        commit="", requested_backend="browser", actual_backend="chromium",
        torch_version=None, device="Chromium", runtime="browser",
        dtype="none", problem_size="playwright", tile=0,
    )


def _ingest_browser_rows(run, path: Path):
    from dataclasses import replace

    from .playwright import ingest_playwright

    samples = ingest_playwright(path, _browser_environment())
    return replace(run, samples=list(run.samples) + samples)


def _run_and_ingest_browser(run, config: RunConfig):
    from .playwright import run_playwright

    output = Path(config.output_dir) / "playwright-results.jsonl"
    run_playwright(output, full=True)
    return _ingest_browser_rows(run, output)


def _run_baseline(args) -> int:
    results = Path(args.from_path)
    destination = Path(args.output) / f"{args.name}.json"
    try:
        update_baseline(results, destination)
    except (ValueError, OSError) as exc:
        print(f"Baseline update rejected: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote baseline {destination}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "baseline":
        return _run_baseline(args)
    return _run_profile(args)


if __name__ == "__main__":
    raise SystemExit(main())
