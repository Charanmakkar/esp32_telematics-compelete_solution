Optional BMS firmware images

Place replacement Intel HEX (.hex) files here. On the BMS diagnostics page,
select a programming script and enter the filename in the replacement-image field.
Leave it blank to use the image named by the reference script.

Images are local only and excluded from Git. The server validates record checksums,
overlaps and 8-byte alignment and shows a SHA-256 fingerprint before confirmation.
Only use images intended for the connected BMS and selected application/calibration.
The reference project is never modified.
