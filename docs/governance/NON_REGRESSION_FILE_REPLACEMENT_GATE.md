Non-Regression File Replacement Gate

Purpose

This document establishes mandatory controls governing file replacement operations within CSS.

Core Rule

No replacement operation may:

* introduce regression
* silently remove functionality
* corrupt governance logic
* damage stable runtime behavior

Preferred Workflow

Default preferred workflow:

* complete file replacements
* explicit compile validation
* immediate smoke testing
* explicit git verification

Partial patching should be minimized unless operationally necessary.

Required Pre-Replacement Checks

Before replacing files:

1. Verify current branch
2. Verify rollback availability
3. Verify baseline stability
4. Verify git clean state where possible
5. Verify target file path correctness

Required Post-Replacement Checks

After replacement:

1. py_compile validation
2. import validation
3. smoke testing
4. runtime startup verification
5. governance verification
6. git status review

Protected Areas

Extra caution required for:

* governance modules
* orchestrator logic
* execution routing
* persistence systems
* accounting systems
* broker adapters
* dashboard runtime state

Failure Handling

If replacement causes instability:

* stop immediately
* revert safely
* restore protected baseline
* validate recovered state

PCNRASS Enforcement

Please Confirm:

* No Regression
* All Stable States preserved

No merge should proceed without explicit PCNRASS confirmation.

Institutional Objective

The purpose of this gate is to preserve:

* deterministic stability
* audit integrity
* recoverability
* institutional governance quality
* safe iterative development
