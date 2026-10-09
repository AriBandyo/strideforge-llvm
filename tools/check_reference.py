#!/usr/bin/env python3
"""Independently exercise hand-reviewed expected LLVM IR, not the C++ plugin.

This confirms the documented recurrence is valid, and can be run without `opt`.
It is NOT evidence that the plugin compiled or performed the transformation.
"""
import argparse
import pathlib
import tempfile
from test_ir import ROOT, differential, find_exe


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--clang')
    args = ap.parse_args()
    clang = find_exe(args.clang, 'clang')
    with tempfile.TemporaryDirectory(prefix='sf-reference-') as tmp:
        differential(ROOT / 'tests/ir/affine.ll',
                     ROOT / 'tests/ir/expected.ll', clang, pathlib.Path(tmp))
    print('PASS: hand-reviewed reference IR (separate from plugin test)')


if __name__ == '__main__':
    main()
