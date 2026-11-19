# Documentation export and review

These helpers are documentation tools and do not flash hardware, alter the
running database, or change application source/version. Run from project root.

1. Review docs/RELEASE_STATUS.md and all source guides against actual code/results.
   Historical test files remain unchanged; describe superseded results explicitly.
2. Run `backend/.venv/Scripts/python.exe docs/tools/export_api_schema.py` to refresh
   docs/api/openapi.json and database/schema.sql from the current routes/models.
   It uses SQLAlchemy's MySQL dialect in the backend environment;
   these are references, not database operations. The current migration head is 0004.
3. Audit both project chats using complete paginated turn records. Store only
   counts/timing metadata in output/reports/interaction-time.json, not message
   text or credentials. Exclude unfinished turns from timing and label the cutoff.
   Update docs/reports/PROJECT_AND_AI_USAGE.md; never infer project credits.
4. Use the bundled document Python runtime, or install the measured dependency
   set in `docs/tools/requirements.txt` into a separate documentation environment.
   Run `python docs/tools/export_current_documents.py`.
   This reuses the existing layout exporter with current version/date footers,
   regenerates four engineering PDFs, and adds the updated AI report/screenshots.
   Use this command instead of the older export script's fixed-date footer.
5. Update the existing five-slide stakeholder PPTX with the same metric cutoff,
   current feature/status wording and genuine dated screenshots. Preserve its
   editable text, theme and slide size. The revision helper is
   docs/tools/update_stakeholder.mjs; it uses the bundled Artifact Tool runtime.
   Set RUNTIME_NODE_MODULES, RUNTIME_PYTHON and PRESENTATIONS_SKILL_DIR to the
   bundled package/Python/skill paths, then run it with the bundled Node executable.
   Its fixed slide wording is for this review; revise text/evidence when metrics
   or release status change. It validates a temporary copy before replacing the deck.
6. Render every PDF page and slide; inspect for clipping, table overflow, missing
   glyphs, unreadable screenshots and inconsistent dates. Verify local links,
   API paths, schema tables, binary hash and version identity.
   Run `python docs/tools/verify_documentation.py` for the structural checks.
   It expects the presentation validation receipt from step 5. The recorded manual
   visual-review statement belongs to this revision and must be renewed after edits.
7. Run `backend/.venv/Scripts/python.exe scripts/sync_version.py --check`.
   A documentation-only edit must not advance firmware/GUI version. Package using
   scripts/package_release.py --build-directory build (without --hardware-flashed
   while v1.1.8 remains unverified), then refresh the documentation additions to
   the manifest/ZIP with docs/tools/finalize_docs_package.py.
8. Update docs/testing/documentation-review.json with the audit, stage all
   documentation/artifacts and reviewed temporary work, commit and push the
   current branch. Verify remote commit equality and a clean working tree.

The original build/test evidence includes failures. A documentation export is
not a hardware test. Never change hardware_flashed or timing acceptance to true
without new evidence for the exact packaged firmware.
