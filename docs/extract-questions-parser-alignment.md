# Extract-questions parser alignment

## Cause and observation

The question validator stripped fences only when they began the response, then
anchored on the first opening brace. The generated question HTML repeated that
logic. Consequently, a prose preamble containing `{` caused both consumers to
parse from the wrong location even when the response contained a valid fenced
JSON object. The PR-triage validator and HTML builder already prefer a fenced
JSON block and therefore do not have this asymmetry.

## Chosen approach

All three question consumers now follow the PR-triage order: parse the first
fenced JSON block (with `json` optional), otherwise extract from the first `{`
to the last `}`, and finally parse the complete response. If a fence is present
but malformed, parsing fails instead of accepting unrelated surrounding text.

## Rejected alternative

Removing all fence markers before searching for braces would still let braces
in a preamble decide the parse start. Re-parsing the raw response after a bad
fence was also rejected because it could hide a malformed model payload.

## Verification

`node tests/questions-parser-regression.mjs` creates a temporary theme within
the worktree. It verifies the executable validator, the Python `parse_json`,
and the parser emitted into `output.html` against a preamble containing `{`
followed by a fenced JSON payload. Existing benchmark output is copied before
revalidation so committed `public/` metadata and HTML remain untouched.

Revalidating the published outputs found one intended status change:
`extract-questions/gemma-4-26b-a4b-qat` changed from `valid_json: true` and
`schema_pass: true` to `valid_json: false` because its response begins with a
`ts` fence rather than a JSON fence. The aligned fence-first parser treats that
fenced payload as the model output and correctly rejects its `ts` language tag
as non-JSON. The remaining eight published model outputs retained their
`valid_json` and `schema_pass` values. Their generated `output.html` files were
regenerated so the browser parser matches the validator.
