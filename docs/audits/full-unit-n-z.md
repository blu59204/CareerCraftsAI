# Complete read: backend unit tests n–z

Scope: 37 tracked test files, 6,773 lines, fully read. Temporal and workflow-prefixed tests are excluded from this partition because the main audit owns them. `coverage-unit-n-z.csv` records each file's SHA-256 and line count. This is a static review; this partition did not execute pytest or exercise live providers or PostgreSQL.

## Actionable test weaknesses

- **P2: Background ownership regression test cannot fail its final assertion.** `backend/tests/unit/test_rls_isolation.py:83` uses `assert len(captured_queries) >= 1 or True`. It neither requires a query to execute nor verifies its user filter. A regression removing the ownership predicate can pass this test. Capture the statement and assert the document and owner predicates independently; keep database failures visible in a unit test using a mock session.
- **P2: Policy test does not establish that every write policy checks ownership.** `backend/tests/unit/test_rls_policies.py:184` selects only the last policy body for each table. PostgreSQL policies with distinct names coexist, and permissive policies combine; a newer safe policy does not supersede an older unsafe policy with another name. The parser also searches concatenated historical SQL, including comments, without applying DROP POLICY statements. Track effective policies by table and policy name, inspect every applicable write policy, and supplement static checks with actual two-user database tests under the deployed application role.
- **P2: TypedDict schema tests prove ordinary dict behavior rather than schema requirements.** `backend/tests/unit/test_state_schema.py:27` builds a complete dict and asserts its supplied keys; analogous token and message tests simply write and read dictionary values. They would still pass if the TypedDict required keys or annotations regressed. Assert `__required_keys__` and resolved annotations, or run a type checker with negative fixtures. Actual checkpoint serialization requires an integration test.

## Verification boundaries

- Encryption tests cover round trips, randomized ciphertext, wrong-key rejection and key derivation. `test_model_settings_mask_api_key` tests ciphertext encoding only; it does not inspect an authenticated model-settings HTTP response or prove that API responses mask secrets. Auth tests allow either 401 or 422, so they do not independently establish the intended authentication error contract.
- `test_run_choice.py` supplies predetermined mock query results for owner and foreign IDs. It tests error handling and choice reset, but does not inspect ownership predicates or use two users in a database.
- Notifications API tests in this partition check unauthenticated access only. Notification-service and activity tests mock database/transport boundaries; they cannot prove real cross-user isolation or delivery behavior.
- Agent tests validate checkpoints and failures with model/network/persistence boundaries patched. Mocked salary searches do not establish the correctness or freshness of real salary evidence. Recruiter tests meaningfully verify verdict mapping, spending caps and secret-free logging with mock HTTP; live address validation and email delivery are outside this read.
- RAG tests meaningfully exercise collection namespaces, selected chunk ordering, provider/key selection, dimensions and query instructions. Namespace string tests and source-text ownership assertions do not independently establish deployed PostgreSQL isolation or HNSW use.

## Stronger existing checks

Resume tests include meaningful deterministic parser/date/contact regression cases and PDF/DOCX text/structure checks. The fix API harness honors owner/id predicates, asserts optimistic version rejection before storage, checks pending-approval pinning, and validates storage cleanup/commit ordering. Facts tests inspect row locking and savepoint conflict recovery. These are useful unit guarantees; transaction races and database policy effectiveness still depend on the separately reviewed PostgreSQL integration coverage.

No source changes were made by this audit partition.
