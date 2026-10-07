# Disposable PostgreSQL erasure ordering proof

This is a database ordering proof requested during the full audit. It does not execute application code or prove the endpoint call path by itself; combine it with the reviewed source order before classifying a production finding.

Executed against a newly created PostgreSQL 16 Docker container `careercraft-erasure-race-proof`, exposed only at 127.0.0.1:57532, with disposable credentials. Minimal tables: owners(id primary key), documents(id primary key, owner_id references owners(id) on delete cascade, path text). Simulated files existed only under a temporary OS directory. Container and temporary directory were removed afterward.

Existing-document ordering:

1. Updater locks document 1 FOR UPDATE.
2. Reaper locks owner 1 FOR UPDATE and sweeps the simulated storage directory.
3. Updater writes new.pdf and changes documents.path without modifying its owner FK, then commits.
4. Reaper deletes owner 1, which cascades to the document, then commits.

Observed result: `{"replacement_files_after_erasure": ["new.pdf"], "document_rows": 0}`. A parent-row lock does not serialize replacement of an existing child's non-FK columns/file creation with an earlier external storage sweep.

Control for new-document creation:

1. Reaper locks owner 2 FOR UPDATE.
2. Another connection attempts a new document INSERT referencing owner 2.
3. After 300 ms the INSERT is still blocked.
4. Reaper deletes owner 2 and commits; the INSERT fails with ForeignKeyViolation. Simulated failure compensation removes its prewritten file.

Observed result: `{"new_insert_blocked_on_parent": true, "error": ["ForeignKeyViolation"], "compensated_new_file_exists": false}`. This control prevents extending the replacement-order finding to properly compensated new inserts without separate evidence.
