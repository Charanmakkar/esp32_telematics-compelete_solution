from pathlib import Path
p=Path('tmp/finalize_ota_hardware_docs.py');s=p.read_text()
for old,new in [
    ("'backend_full_tests':111", "'backend_full_tests':116"),
    ("'ota_backend_tests':21", "'ota_backend_tests':26"),
    ('- 111 backend tests', '- 116 backend tests'),
    ('The 21 targeted OTA tests', 'The 26 targeted OTA tests'),
    ('was exercised in v{version}', 'was exercised in v{evidence["can-tx"]["release"]["sw_version"]}'),
    ('Current bench result, 20 November 2026 (v{version})', 'Current bench result, 20 November 2026 (v{evidence["can-tx"]["release"]["sw_version"]})'),
    ("'Disable Wi-Fi modem sleep during OTA only, restoring policy on abort']", "'Disable Wi-Fi modem sleep during OTA only, restoring policy on abort','Negotiate 2048-byte chunks with 768-byte fallback for older firmware']"),
]:
    assert old in s,old;s=s.replace(old,new)
s=s.replace("evidence={name:","final_state=json.loads((root/'output/testing/ota-final-hardware-state.json').read_text())\nassert final_state['passed'] and final_state['chip']['image_sha256']==info['image_sha256']\nevidence={name:",1)
s=s.replace("'nvs_preserved':True", "'nvs_preserved':final_state['nvs_byte_identical'],'max_chunk_bytes':2048")
s=s.replace('The first upload test exposed', 'Transfers use the chip-advertised 2048-byte capacity, with a 768-byte fallback for\nearlier OTA builds. Final USB restoration after the deliberate rollback test kept\nthe original NVS bytes identical and restored the packaged build.\n\nThe first upload test exposed')
p.write_text(s)
print('Updated final report generator for the negotiated-chunk release.')
