# api-adapter-boundary Specification

## Purpose
TBD - created by archiving change migrate-problem-details-to-api-adapter. Update Purpose after archive.
## Requirements
### Requirement: AAB-02 — `problem_details.py` does not exist at the project root

The system MUST satisfy this requirement as specified below.

**Priority**: Medium

The root-level `problem_details.py` is removed. Its absence prevents the `RUNTIME_MODULE_FILES` exemption in the boundary test from being needed.

**Acceptance Criteria**:
1. `problem_details.py` does not exist at the project root.
2. `python -c "import problem_details"` raises `ModuleNotFoundError`.
3. `RUNTIME_MODULE_FILES` in `tests/unit/test_hexagonal_boundaries.py` contains only `"main.py"`.

#### Scenario: Root-level module absence confirmed

- Given: the project root directory listing
- When: `problem_details.py` is searched for
- Then: it is not found
