# DWG performance implementation

Approved scope: user's 2026-10-02 instruction to implement ASTRA's recommended sequence. Preserve 13-template selection, rigid transforms, invalid/blank/N/A distinction, owned batch CAD and original files. Source baseline f55f7b7; released source is identical and held at ../dwg-pdf-github-release/publish.

## Global constraints

- Work only in antigravity-created agy/dwg-pdf-performance.
- Preserve registration bbox and bounded structural geometry checks.
- No cross-document cache, no parallel CAD, no timeout/safety removal.
- Measure each optimization separately. Cache only if repeated definitions justify it.
- Deliver locally built EXE and evidence; no new publication/merge is required by this request.
- Old design's valid-scale structural gate was superseded in the existing source; this performance change does not expand or tighten matching semantics.

## Task 1: Reproducible detailed baseline

Add diagnostic-only stage/COM property/definition-visit instrumentation. Run current unit suite and representative templates in one owned CAD. Expected: original identities unchanged, session cleaned, timings and candidate decisions persisted. No production mutation.

## Task 2: Remove redundant COM reads

Write counting-entity regression tests for repeated kind/name/coordinate reads. Run RED, implement local value reuse, then full non-CAD suite GREEN. Compare one real template to baseline; preserve all snapshot output and failure checks.

## Task 3: Conversion-only lightweight text extraction

Add an explicit conversion-only document view/API while preserving general registration/geometry methods. Retain all texts including invalid/empty values, handles, paths, attribute suppression and transforms. Write tests for unchanged detection and bounded traversal. Run RED/GREEN. Measure against Task 2. Prefer conservative geometry validation reuse if skipping geometry would change rejection behavior.

## Task 4: Conditional cache and A4 lookup

Assess definition visit counts; if repetition is not meaningful, defer cache with measured rationale. Preserve preferred-media ambiguity and actual size verification while skipping unrelated media once unique preferred A4 is established. RED/GREEN tests for selection and installed preferred ambiguity. Measure independently.

## Task 5: End-to-end validation and package

Run full test suite, baseline/improved representative conversion comparisons, all13 template conversions and rotation/translation/blank/N/A regression cases as feasible with installed CAD. Verify output decision, rendered PDF, original hashes/mtimes, user CAD retention and owned session cleanup. Build portable validation bundle and run self-check plus real frozen-EXE conversion. Report missing real customer source data explicitly.

## Task 6: Final independent review

One ASTRA fresh-context whole-change review covering registration bbox, malformed/duplicate text, transforms, attribute coordinates, cache lifecycle if any, cycle/budget and media ambiguity. Fix Important/Critical issues with regression tests. Preserve local deliverables and provide path with measured improvement and limits.
