#!/usr/bin/env python3
"""Fail-fast LLVM plugin smoke, IR verifier, negative-case and differential tests.

Only stdlib dependencies. All native output is built in a temporary directory.
"""
import argparse
import ctypes
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def command(argv, *, capture=True):
    result = subprocess.run(
        [str(arg) for arg in argv], text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(map(str, argv))}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def find_exe(exe, prefix):
    if exe:
        return exe
    for candidate in (f"{prefix}-21", f"{prefix}-20", f"{prefix}-19",
                      f"{prefix}-18", prefix):
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError(f"Could not find {prefix}; specify --{prefix}")


def find_plugin(explicit):
    if explicit:
        p = pathlib.Path(explicit).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Missing plugin: {p}")
        return p
    matches = [p for ext in ("so", "dylib")
               for p in (ROOT / "build").rglob(f"*StrideForge*.{ext}")]
    if not matches:
        raise FileNotFoundError("Missing compiled plugin; run cmake build or pass --plugin")
    return matches[0]


def target_function(ir, name):
    match = re.search(r"^define\s+\w+\s+@" + re.escape(name)
                      + r"\([^)]*\)\s*\{(.*?)^\}", ir, re.M | re.S)
    if not match:
        raise AssertionError(f"Can't find function @{name}")
    return match.group(1)


def compile_ir(clang, path, out, level):
    command([clang, "-x", "ir", f"-O{level}", "-fPIC", "-shared",
             str(path), "-o", str(out)])


def typed_function(library_path, name, bits):
    library = ctypes.CDLL(str(library_path))
    fn = getattr(library, name)
    typ = ctypes.c_uint64 if bits == 64 else ctypes.c_uint32
    fn.argtypes = [typ, typ, typ]
    fn.restype = typ
    return library, fn


def differential(original, optimized, clang, temp):
    for level in (0, 2):
        lib_before = temp / f"baseline_O{level}.so"
        lib_after = temp / f"strideforge_O{level}.so"
        compile_ir(clang, original, lib_before, level)
        compile_ir(clang, optimized, lib_after, level)
        for name, bits in (("affine", 64), ("affine32", 32)):
            l1, base = typed_function(lib_before, name, bits)
            l2, transformed = typed_function(lib_after, name, bits)
            rng = random.Random(0xBEEF + bits)
            limits = [0, 1, 2, 17, (1 << (bits - 1)) - 1,
                      1 << (bits - 1), (1 << bits) - 1]
            cases = [(start, n, seed) for start in limits
                     for seed in (0, 1, (1 << bits) - 1)
                     for n in (0, 1, 2, 37)]
            cases += [(rng.getrandbits(bits), rng.randrange(0, 501),
                       rng.getrandbits(bits)) for _ in range(200)]
            for inp in cases:
                lhs = base(*inp)
                rhs = transformed(*inp)
                if lhs != rhs:
                    raise AssertionError(
                        f"O{level} @{name}{inp}: baseline={lhs}, plugin={rhs}")
            print(f"PASS: differential @{name} O{level}: {len(cases)} cases")
            _ = (l1, l2)  # keep library objects alive while functions run


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--opt", help="matching LLVM opt executable")
    ap.add_argument("--clang", help="matching clang executable")
    ap.add_argument("--plugin", help="compiled LLVM pass plugin path")
    args = ap.parse_args()
    opt = find_exe(args.opt, "opt")
    clang = find_exe(args.clang, "clang")
    plugin = find_plugin(args.plugin)
    print("opt:", command([opt, "--version"]).stdout.splitlines()[0])
    print("clang:", command([clang, "--version"]).stdout.splitlines()[0])
    print("plugin:", plugin)

    pos = ROOT / "tests/ir/affine.ll"
    neg = ROOT / "tests/ir/negative.ll"
    with tempfile.TemporaryDirectory(prefix="strideforge-tests-") as td:
        tmp = pathlib.Path(td)
        out = tmp / "optimized.ll"
        command([opt, "-load-pass-plugin", plugin, "-verify-each",
                 "-passes=function(strideforge)", "-S", pos, "-o", out])
        result = out.read_text()
        for name, width in (("affine", 64), ("affine32", 32)):
            ir = target_function(result, name)
            assert "sf.scaled" in ir and "sf.next" in ir, name
            assert not re.search(r"\bmul\s+i%d\s+(?:%%iv,\s*37|-7,\s*%%iv)" % width,
                                 ir), f"Original multiply in @{name}"
        print("PASS: positive transforms have replacement PHIs and latch updates")

        nochange = tmp / "negative.optimized.ll"
        command([opt, "-load-pass-plugin", plugin, "-verify-each",
                 "-passes=function(strideforge)", "-S", neg, "-o", nochange])
        text = nochange.read_text()
        for name in ("dynamic_stride", "dynamic_factor", "mul_outside_header"):
            ir = target_function(text, name)
            assert "sf.scaled" not in ir, f"Unexpected transformation in @{name}"
            assert re.search(r"\bmul\s+i64", ir), f"Mul unexpectedly eliminated in @{name}"
        print("PASS: unsupported negative cases remain unchanged")

        report = command([opt, "-load-pass-plugin", plugin,
                          "-passes=function(strideforge-report)",
                          "-disable-output", pos])
        assert "[strideforge] function=affine " in report.stderr
        assert "eligible_mul=1" in report.stderr
        print("PASS: reporting pass is registered and detects candidates")
        differential(pos, out, clang, tmp)
    print("SUCCESS: StrideForge validation complete")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, AssertionError, FileNotFoundError) as error:
        print("FAIL:", error, file=sys.stderr)
        sys.exit(1)
