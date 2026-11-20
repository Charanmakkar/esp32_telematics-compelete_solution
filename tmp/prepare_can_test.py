from pathlib import Path
text=Path('.runtime/test_can_tx_live.py').read_text()
text=text.replace('import serial', "import sys\nsys.path.append(r'C:\\Espressif\\tools\\python\\v6.0.2\\venv\\Lib\\site-packages')\nimport serial\nfrom dotenv import dotenv_values\ncredentials = dotenv_values('.runtime/ota-test.env')")
text=text.replace("'username': 'admin', 'password': os.environ['NAV_TEST_PASSWORD']", "'username': credentials['NAV_TEST_USERNAME'], 'password': credentials['NAV_TEST_PASSWORD']")
text=text.replace('output/testing/can-tx-live.json','output/testing/ota-live-can-tx.json').replace('.runtime/can-tx-live-serial.log','.runtime/ota-can-tx-serial.log')
text=text.replace("        toggle(True)\n", """        toggle(True)
        upload = client.post('/api/v1/ota/image?device_id=ESP32_001&filename=busy-test.bin', content=Path('.runtime/ota-test-images/v1.1.15.bin').read_bytes())
        upload.raise_for_status()
        begun = client.post('/api/v1/ota/start', json={'device_id':'ESP32_001','upload_id':upload.json()['upload_id']})
        begun.raise_for_status()
        for _ in range(40):
            ota = get('/api/v1/ota')
            if ota['job']['state'] == 'failed': break
            time.sleep(.25)
        assert ota['job']['state'] == 'failed' and 'Turn GPIO controls' in ota['job']['message'], ota
        assert get('/api/v1/can/tx')['state']['enabled']
        report['ota_while_can_active'] = {'rejected':True, 'message':ota['job']['message'], 'can_remained_enabled':True}
""")
Path('tmp/ota_can_tx_test.py').write_text(text)
