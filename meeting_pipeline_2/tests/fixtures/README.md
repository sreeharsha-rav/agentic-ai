# Test fixtures

Small, static, offline test inputs -- no real video/audio and no
model-download dependency. Port reference:
`../../../meeting_pipeline/tests/fixtures/` (a sample VTT, sample
`hybrid_enriched_log.json`, sample `meeting_context.json`, a small reference
markdown doc). Mirror the same fixture set here as the corresponding stage's
tests are written, so both packages' test suites can share the same
recorded expected values where the algorithm is unchanged.
