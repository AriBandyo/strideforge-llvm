# Turning StrideForge into application evidence

**Do not submit an unbuilt/unverified project as a finished compiler optimization.** The bundled GitHub Action is designed to build with LLVM 18, verify transformed IR and differential-test native execution; check its green status first. The checked-in expected IR is an independently reviewed reference, not proof that the C++ plugin produced it.

## Suggested resume bullets (use only after CI passes)

- Implemented a C++ LLVM New Pass Manager optimization that strength-reduces affine integer multiplications into loop-carried SSA recurrences, using LoopInfo, PHI construction, and fixed-width APInt arithmetic.
- Built compiler regression coverage for 32-bit and 64-bit induction variables, negative strides, dynamic loop starts, overflow edges, and unsupported patterns, with a randomized native differential-execution harness.
- Developed a reproducible `-O0` and `-O2` microbenchmark framework with equal-output validation and median timing, separating teaching-pass effects from LLVM's native loop optimizations.

If you run and publish actual benchmarks, replace the third bullet with **real hardware, flags, baseline and measured result**. Never invent a percentage or describe this as a contribution merged into LLVM, Triton, or another upstream codebase.

## Elevator pitch (30 seconds)

"StrideForge is an out-of-tree LLVM loop optimization plugin written in C++. I used LLVM's loop analysis to identify a deliberately constrained induction variable, then replaced a constant multiply in the loop header with a scaled SSA recurrence initialized in the preheader and updated in the latch. The interesting parts were getting PHI placement right, preserving modulo integer semantics including wraparound, rejecting unsupported loops conservatively, and differential-testing baseline versus transformed LLVM IR. LLVM already has production strength reduction, so I compare both `-O0` and `-O2` honestly rather than claiming I invented the optimization."

## Next iteration worth building

A small project alone doesn't replace professional compiler experience. After the initial pass is green, improve the engineering depth by adding ScalarEvolution-based recognition and TargetTransformInfo-based profitability checks, plus optimization remarks for misses. This provides more challenging work for an Intel/compiler interview and addresses the main limitations of v0.1.
