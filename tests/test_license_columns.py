import unittest
from unittest.mock import MagicMock, patch
import app

class LicenseColumnTests(unittest.TestCase):
    def test_load_licenses_reads_max_account(self):
        response = MagicMock()
        response.json.return_value = [{'license_key': 'TEST-LICENSE', 'client': 'Prueba', 'created': '2026-10-16', 'expires': '2026-11-16', 'max_account': 5, 'active': True}]
        response.raise_for_status.return_value = None
        with patch.object(app.requests, 'get', return_value=response) as mock_get:
            with patch.object(app, 'supabase_headers', return_value={}):
                result = app.load_licenses()
        self.assertEqual(result['TEST-LICENSE']['max_accounts'], 5)
        self.assertIn('max_account', mock_get.call_args.kwargs['params']['select'])
        self.assertNotIn('max_accounts', mock_get.call_args.kwargs['params']['select'])

    def test_save_licenses_writes_max_account(self):
        response = MagicMock()
        response.raise_for_status.return_value = None
        data = {'TEST-LICENSE': {'client': 'Prueba', 'created': '2026-10-16', 'expires': '2026-11-16', 'max_accounts': 5, 'active': True}}
        with patch.object(app.requests, 'post', return_value=response) as mock_post:
            with patch.object(app, 'supabase_headers', return_value={}):
                app.save_licenses(data)
        payload = mock_post.call_args.kwargs['json'][0]
        self.assertEqual(payload['max_account'], 5)
        self.assertNotIn('max_accounts', payload)

if __name__ == '__main__':
    unittest.main()
