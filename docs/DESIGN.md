# Design and correctness notes

## Algebraic transformation

Given a loop induction variable `i0` and constant step `d`, assume on iteration `k`, `i(k) = i0 + k*d (mod 2^W)`. For constant multiplier `c`, define `s0 = i0*c` and `s(k+1) = s(k) + c*d (mod 2^W)`.

By induction, `s(k) = c*i(k) (mod 2^W)` for all iterations. In LLVM IR, `mul` and `add` with no extra wrap flags implement this modular arithmetic on finite-width integers. The pass deliberately does **not** copy `nsw` or `nuw` flags onto newly created operations. This creates no new poison from overflow. It also avoids unsafe reassociation of floating-point arithmetic.

## SSA placement

- Original IV PHI exists in the loop header, with incoming values from preheader and latch.
- New `%sf.scaled` PHI is inserted at the start of the header.
- `%sf.init = mul IV.initial, constant` is inserted before the preheader terminator.
- `%sf.next = add %sf.scaled, (constant*step)` is inserted before the latch terminator.
- All uses of the original header multiplication are replaced with `%sf.scaled`, then the `mul` is erased.

The original IV continues to exist, potentially serving exit conditions and other calculations.

## Preconditions

| Invariant | Reason |
|---|---|
| Single preheader, unconditional branch to loop header | Seed computed once and dominates the header |
| Unique latch / one backedge | A single new PHI incoming update is sufficient |
| Induction PHI has exactly two incoming values | There is no unhandled predecessor |
| Latch updates via `add IV, constant` or `sub IV, constant` | Constant affine recurrence |
| Header multiplication of this IV by nontrivial constant | Observable repeated operation to transform |
| 32 or 64-bit integer bitwidth | Intentional and auditable initial implementation |

Loops with zero iterations are safe: the seed may be computed (a pure, nontrapping integer multiplication), but the new header PHI is never reached.

## Conservatism, not all possible correctness conditions

A more advanced implementation could support multiple latches, nested recurrence forms, non-unit PHI edges, ScalarEvolution AddRec expressions, multiple updates, symbolic (loop-invariant) scale factors, and profitability heuristics. These require more complex dominance and SSA handling. We deliberately reject them in v0.1 rather than assume they are safe.

## Analysis invalidation

Adding and removing non-terminator instructions leaves the control flow graph and LoopInfo structure intact, but may invalidate ScalarEvolution and other analyses. The optimization conservatively returns `PreservedAnalyses::none()` after any change. The report pass returns `all()` because it does not modify IR.

## Why LLVM already does this

LLVM has induction-variable canonicalization and loop strength-reduction passes. This project is a targeted reimplementation to demonstrate understanding of LLVM's pass manager, loop analysis, PHI construction, integer semantics, regression tests, and measurement. A fair comparison is `plain -O2` vs `plugin -O2`, **not** `plain -O0` vs `plugin -O2`.

## Future extensions (not implemented)

1. Integrate `ScalarEvolution`/`LoopStandardAnalysisResults` to recognize more affine recurrence forms.
2. Use TargetTransformInfo to model the cost of new PHIs, adds and preheader multiplication, and reject unprofitable conversions.
3. Use `OptimizationRemarkEmitter` to emit accepted/rejected optimization remarks in LLVM's remark format.
4. Add FileCheck/lit based tests, fuzz generation, LLVM sanitizers, and CI across multiple LLVM versions.
5. Investigate typed pointer arithmetic and address-computation recurrence with an alias-safe legality model; never assume any transformation here optimizes GPU Tensor Core pipelines.
