# StrideForge — LLVM Affine Loop Strength Reduction

A small, auditable **LLVM New Pass Manager** compiler plugin written in **C++17**. It recognizes constant-stride integer induction variables in simple loops and replaces repeated `i * C` multiplications with an incrementally maintained scaled induction variable.

This is an independent learning and engineering project, **not an upstream LLVM contribution**. It targets the same class of loop strength reduction already implemented in production LLVM optimization pipelines. Its value is a tested, inspectable implementation of real compiler-pass mechanics, not a claim to outperform LLVM `-O2`.

## What the transformation does

```text
BEFORE                               AFTER
preheader:                           preheader:
  br loop                               initial = start * 37
                                        br loop
loop:                                loop:
  i = phi(start, i.next)                i = phi(start, i.next)
  scaled = i * 37                       scaled = phi(initial, scaled.next)
  ... use scaled ...                    ... use scaled ...
  br latch                              br latch
latch:                               latch:
  i.next = i + 3                        i.next = i + 3
                                        scaled.next = scaled + 111
  br loop/exit                          br loop/exit
```

**Correctness intuition:** for N-bit integers, `(i + step) * C == i*C + step*C (mod 2^N)`. The seed is computed exactly once before the loop. Every subsequent iteration uses integer addition at the same bitwidth. This equivalence does not rely on floating-point reassociation, alias assumptions, or `nsw`/`nuw` metadata.

## Scope and safety

Targets:
- LLVM **18–21** New PM pass plugin; `opt -load-pass-plugin`.
- 32-bit and 64-bit integer induction variables.
- Header `mul` with a compile-time constant (`mul %i, C` or `mul C, %i`).
- One loop preheader, one backedge/latch, and affine `add` or `sub` updates.
- Positive or negative constant strides; dynamic initial values; integer wraparound.
- A second, read-only `strideforge-report` pass.

Intentionally skips:
- Dynamic multipliers or non-constant steps.
- Irreducible or multi-latch loops, loops without a canonical preheader.
- Multiplications outside loop headers, non-integer multiplication, other integer widths.
- Factor `0` or `1` (not worthwhile).

Does **not** change memory access order, pointer aliasing, control flow, function calls, exception handling, or synchronization. This is not an automatic Tensor Core, Triton, SYCL, or GPU vectorization pass.

## Requirements

- Linux or macOS, CMake >= 3.20, Ninja or Make, C++17 compiler.
- LLVM development tools + headers and a matching `opt` executable (LLVM 18–21).
- Python >= 3.9 for tests and benchmark scripts; no third-party Python dependencies.

Ubuntu 24.04 example: `sudo apt-get install llvm-18-dev llvm-18-tools clang-18 cmake ninja-build python3`

## Build

```bash
cmake -S . -B build -G Ninja \
  -DLLVM_DIR=/usr/lib/llvm-18/lib/cmake/llvm \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build
find build -name '*StrideForge*.so' -o -name '*StrideForge*.dylib'
```

If you use Homebrew LLVM, set `LLVM_DIR` to the `lib/cmake/llvm` subdirectory of your LLVM installation and use its `opt` binary. **Do not** mix the `.so` from one LLVM version with the `opt` binary from another.

```bash
# LLVM 18 Ubuntu path shown; adjust to your installed version.
PLUGIN=$(find build -name '*StrideForge*.so' -o -name '*StrideForge*.dylib' | head -1)
```

Once `PLUGIN` is set, inspect the transformation:

```bash
/usr/lib/llvm-18/bin/opt -load-pass-plugin "$PLUGIN" \
  -passes='function(strideforge-report,strideforge)' \
  -S tests/ir/affine.ll -o /tmp/affine.optimized.ll
cat /tmp/affine.optimized.ll
```

Or run only the report:

```bash
/usr/lib/llvm-18/bin/opt -load-pass-plugin "$PLUGIN" \
  -passes='function(strideforge-report)' \
  -disable-output tests/ir/affine.ll
```

## Tests

Toolchain-independent algebraic property tests:

```bash
python3 -m unittest discover -s tests/python -v
```

An independent expected-IR fixture can be checked with Clang without `opt` (this does not test the C++ plugin):

```bash
python3 tools/check_reference.py --clang clang-18
```

`tools/test_ir.py` discovers a compiled plugin, invokes `opt` with the verifier, checks expected IR transforms and skip cases, and runs a **differential execution test**: it compiles the original and transformed LLVM IR into native shared libraries and compares function outputs over deterministic edge cases and randomized inputs.

```bash
python3 tools/test_ir.py \
  --opt /usr/lib/llvm-18/bin/opt \
  --clang /usr/bin/clang-18 \
  --plugin "$PLUGIN"
```

If `opt` and `clang` for the matching version are on `PATH`, those options can be omitted. Tests fail rather than silently skip when the toolchain is missing.

## Benchmarks

`tools/benchmark.py` runs a controlled microbenchmark on the same pure-integer loop with both `-O0` and `-O2`, using identical CPU, input sizes, number of trials, compiler, and process. Reports **medians** from `time.perf_counter_ns()`. Benchmarks are checked for output equality before timing.

```bash
python3 tools/benchmark.py --opt /usr/lib/llvm-18/bin/opt \
  --clang /usr/bin/clang-18 --plugin "$PLUGIN" \
  --iterations 5000000 --trials 7
```

*Interpretation:* at `-O0`, replacing a hot-loop multiply may improve performance, but LLVM's `-O2` pipeline often performs the same or better reduction without StrideForge. Hardware, inlining, code generation, CPU scheduling, and loop folding affect the numbers. **Never claim an improvement without running the benchmarks and reporting the compiler flags and hardware.**

## Design notes

Read [docs/DESIGN.md](docs/DESIGN.md) for the proof sketch, preservation/invalidation strategy, edge cases, engineering trade-offs and extension roadmap.

## Repository layout

```text
src/StrideForge.cpp          New PM optimization + analysis pass
CMakeLists.txt               Out-of-tree LLVM plugin build
tests/ir/affine.ll           Positive and differential-test IR
tests/ir/expected.ll         Hand-reviewed reference transform
tests/ir/negative.ll         Rejected unsupported patterns
tools/test_ir.py             IR inspection and native differential tests
tools/check_reference.py      Native differential check of reference IR
tests/python/               Bitvector identity property tests
tools/benchmark.py           Repeatable -O0/-O2 timing + correctness
docs/DESIGN.md               Algorithm, proof, and limitations
.github/workflows/ci.yml    LLVM 18 build and test on Ubuntu
```

## Interview discussion

1. **Why a PHI?** The loop has a recurrence; inserting a second loop-carried PHI is a natural SSA representation.
2. **Why calculate `step*C` using APInt?** LLVM integers are fixed-width bitvectors, so arithmetic must preserve truncation/wraparound semantics.
3. **Why require preheader/latch?** They provide unambiguous places for initialization and increment and avoid unsafe rewrites of general CFGs.
4. **Why report and transform separately?** Analyses should be inspectable without changing IR; transforms must correctly invalidate analyses.
5. **Why might `-O2` show no speedup?** LLVM already implements production-grade induction variable simplification/strength reduction.

## Publishing and applying

Follow [docs/PUBLISH.md](docs/PUBLISH.md) to create a public GitHub repository and verify GitHub Actions. See [docs/INTEL_APPLICATION.md](docs/INTEL_APPLICATION.md) for application-ready, non-inflated resume bullets and a project elevator pitch.

**Verification status for this bundle:** math property tests passed, both supplied LLVM IR fixtures parsed and verified using LLVM 20 bindings, and the independently written expected transformation matched baseline execution over 284 deterministic/randomized cases per function at each of `-O0` and `-O2` with Clang 17. The actual C++ plugin has **not** been compiled in this environment because LLVM development headers and `opt` are absent. Its build, emitted IR, and plugin-specific tests remain to be verified by CI or a local LLVM installation.

## License

MIT.
