# StrideForge Performance Analysis

## Environment
- Compiler: Clang 21.1.8
- LLVM: 21.1.8
- Platform: Linux x86-64 (WSL)
- Benchmark iterations: 5,000,000
- Timing: Median of repeated trials

## Results

| Configuration | Baseline | StrideForge | Speedup |
|---|---:|---:|---:|
| O0 (7 trials) | 4.388 ms | 5.370 ms | 0.817x |
| O2 (7 trials) | 1.350 ms | 0.729 ms | 1.851x |
| O0 (15 trials) | 4.462 ms | 5.303 ms | 0.842x |
| O2 (15 trials) | 1.362 ms | 0.760 ms | 1.792x |

## Assembly Analysis

The baseline vectorized loop contains packed integer
multiplication instructions (pmuludq).

After StrideForge, the vectorized loop uses packed integer
additions (paddq) to maintain the scaled induction value.

An integer multiplication remains outside the main vector
loop for initialization or loop-boundary calculations.

## Interpretation

StrideForge achieves approximately 1.8x speedup on the
tested affine-loop workload under O2.

At O0, StrideForge produces slower execution.

The result demonstrates how an LLVM IR transformation can
influence downstream optimization and machine-code generation.

## Limitations

- Results are specific to the tested workload and CPU.
- CPU frequency and system load were not explicitly controlled.
- Additional benchmark workloads are needed.
- LLVM already performs related strength-reduction optimizations.
- These measurements do not establish universal speedup.
