# Workflow: Production Release & Verification (`release.md`)

## Purpose
End-to-end verification workflow prior to deploying video pipeline builds to production.

## Steps
1. **Quality Gate Checks:** Role: `Release Manager Model`. Verify Quality Gates pass cleanly.
2. **End-to-End Test:** Execute full pipeline test locally for problem #143 (Reorder List).
3. **Security Audit:** Role: `Security Auditor Model`. Ensure API keys, cookies, and OAuth secrets are secure.
4. **YouTube Integration Check:** Confirm private upload and metadata generation succeed without errors.
