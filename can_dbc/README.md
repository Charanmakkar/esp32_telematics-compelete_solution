# Place your CAN databases here

Copy all your `.dbc` files directly into this folder (no restart needed).
The CAN dashboard reloads additions, edits and removals within about 2–3 seconds.
All devices use this shared project library. Files are not sent to an external service.

The page lists loaded files and parse errors. Distinct CAN IDs are decoded using
their matching file. If multiple files define the same ID and standard/extended
format, that ID is marked **DBC conflict** instead of guessing. Move the unused
definition out of this folder to resolve it. Other IDs continue decoding.

Limits: 128 files, 2 MiB per file, 32 MiB total, classic CAN only. UTF-8 and
Windows-1252 text are supported. Subfolders and linked files are not loaded.

The admin dashboard can also save multiple uploaded files here. Uploading the
same filename replaces that file; raw frame history is never changed.
DBC files are ignored by Git to avoid publishing proprietary bus definitions.
If the folder is empty, a previously uploaded database-backed DBC remains a
compatibility fallback until files are placed here.
