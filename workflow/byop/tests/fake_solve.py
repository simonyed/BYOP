"""Zero-solver stand-in for linopy.Model.solve (NEXT-07 W6 tests): writes a synthetic solution and zero duals onto the model, sets
status ok / optimal and returns like linopy, so PyPSA's own post-solve path (assign_solution, assign_duals, post_processing) and
every downstream output run exactly as after a real solve. No solver is touched; the numbers are meaningless by design."""
from __future__ import annotations

import numpy as np

CALLS = []


def fake_solve(self, *a, **k):
    CALLS.append(dict(nvars=int(self.nvars), ncons=int(self.ncons)))
    for name in self.variables:
        v = self.variables[name]
        val = 1.0 if name in ('Generator-p', 'Line-loss') else 0.0          # shed units and losses get visible, non-zero values
        v.solution = (v.labels * 0.0 + val).where(v.labels >= 0)
    for name in self.constraints:
        c = self.constraints[name]
        c.dual = (c.labels * 0.0).where(c.labels >= 0)
    self.status, self.termination_condition = 'ok', 'optimal'
    self.objective._value = 0.0
    return 'ok', 'optimal'
