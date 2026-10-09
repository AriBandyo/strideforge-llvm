#!/usr/bin/env python3
"""Microbenchmark StrideForge without inventing speedups; compare O0 and O2."""
import argparse
import json
import pathlib
import platform
import statistics
import subprocess
import tempfile
import time

from test_ir import ROOT, command, compile_ir, find_exe, find_plugin, typed_function


def run_trials(fn, samples, iterations, seed):
    # The function's output feeds a checksum to make unexpected changes visible.
    checksum = 0
    for _ in range(2):
        checksum ^= fn(71, iterations, seed)
    timings = []
    for _ in range(samples):
        t0 = time.perf_counter_ns()
        checksum ^= fn(71, iterations, seed)
        timings.append((time.perf_counter_ns() - t0) / 1e6)
    return statistics.median(timings), checksum


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--opt")
    ap.add_argument("--clang")
    ap.add_argument("--plugin")
    ap.add_argument("--iterations", type=int, default=5_000_000)
    ap.add_argument("--trials", type=int, default=7)
    ap.add_argument("--json", help="optional path to store raw results")
    args = ap.parse_args()
    if args.iterations < 1 or args.trials < 1:
        ap.error("--iterations and --trials must be positive")
    opt = find_exe(args.opt, "opt")
    clang = find_exe(args.clang, "clang")
    plugin = find_plugin(args.plugin)
    ir = ROOT / "tests/ir/affine.ll"
    meta = {
        "cpu": platform.processor() or platform.machine(),
        "platform": platform.platform(),
        "clang": command([clang, "--version"]).stdout.splitlines()[0],
        "opt": command([opt, "--version"]).stdout.splitlines()[0],
        "iterations": args.iterations,
        "trials": args.trials,
        "results": [],
    }
    with tempfile.TemporaryDirectory(prefix="strideforge-bench-") as td:
        tmp = pathlib.Path(td)
        transformed = tmp / "optimized.ll"
        command([opt, "-load-pass-plugin", plugin,
                 "-passes=function(strideforge)", "-S", ir, "-o", transformed])
        for level in (0, 2):
            b = tmp / f"base_O{level}.so"
            a = tmp / f"withpass_O{level}.so"
            compile_ir(clang, ir, b, level)
            compile_ir(clang, transformed, a, level)
            base_lib, base = typed_function(b, "affine", 64)
            pass_lib, ours = typed_function(a, "affine", 64)
            expected = base(71, args.iterations, 0xB00B1E)
            actual = ours(71, args.iterations, 0xB00B1E)
            if expected != actual:
                raise RuntimeError("Output differs: refuse to benchmark")
            base_ms, c1 = run_trials(base, args.trials, args.iterations, 0xB00B1E)
            pass_ms, c2 = run_trials(ours, args.trials, args.iterations, 0xB00B1E)
            speedup = base_ms / pass_ms
            print(f"O{level}: baseline={base_ms:.3f} ms  "
                  f"with-pass={pass_ms:.3f} ms  speedup={speedup:.3f}x "
                  f"(median, n={args.trials})")
            meta["results"].append({"clang_opt_level": f"O{level}",
                                    "baseline_median_ms": base_ms,
                                    "with_pass_median_ms": pass_ms,
                                    "speedup": speedup, "output": expected})
            _ = (base_lib, pass_lib, c1, c2)
    print("Note: LLVM -O2 may already perform equivalent strength reduction.")
    if args.json:
        path = pathlib.Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta, indent=2) + "\n")
        print("Saved measured results to", path)


if __name__ == "__main__":
    main()
