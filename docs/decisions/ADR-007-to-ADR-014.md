# Initial Architecture Decision Records

These are initial V1 engineering defaults for a research prototype. They are not claims of psychometric validity and must be revisited if simulation or research evidence contradicts them.

## ADR-007: Ability representation
**Decision:** Represent overall ability as one scalar `theta` in V1.
**Reason:** Small, interpretable baseline.
**Status:** Accepted for V1; multidimensional ability deferred.

## ADR-008: Ability update
**Decision:** Use a Rasch/1PL response model and grid-based Bayesian EAP update from correctness and item difficulty.
**Reason:** Supports uncertainty estimates and cold-start priors without a trained neural model.
**Trade-off:** Numerical grid is an approximation; item difficulties in the sample bank are synthetic.
**Status:** Accepted for prototype; requires simulation validation.

## ADR-009: Calibration
**Decision:** Use an adaptive item selector with 4–6 calibration items. The current implementation uses a simple bounded phase; the posterior SD threshold is a provisional target, not yet used as a verified stop guarantee.
**Reason:** Avoid an unbounded calibration phase and permit cold-start evaluation.
**Status:** Provisional implementation.

## ADR-010: Item selection
**Decision:** Select the eligible unattempted item with maximum Fisher information at current EAP theta.
**Reason:** Deterministic and explainable.
**Trade-off:** Content balancing and exposure control are not yet implemented.
**Status:** Accepted for prototype.

## ADR-011: Stopping
**Decision:** Stop at 15 responses, exhaustion of eligible items, or explicit user exit in the demo.
**Reason:** Predictable demo behaviour.
**Status:** Accepted for prototype; revisit with evaluation.

## ADR-012: Data storage
**Decision:** Begin with in-memory synthetic items; SQLite is the next persistence milestone.
**Reason:** Validate the core before persistence.
**Status:** Accepted.

## ADR-013: UI
**Decision:** Start with a local command-line demonstration, then build a local web UI with separate student and examiner/trace views.
**Reason:** Verify engine behaviour before UI complexity.
**Status:** Accepted.

## ADR-014: Local AI
**Decision:** Start QIE with transparent handcrafted text features and a documented baseline; no external model or dataset download until a specific evaluation requires it.
**Reason:** Lightweight, inspectable, reproducible development.
**Status:** Accepted for initial prototype.
