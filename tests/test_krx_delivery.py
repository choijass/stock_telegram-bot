import unittest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
from scripts.krx_delivery import KST, window, chunks, send_report

class DeliveryTests(unittest.TestCase):
    def test_windows(self):
        for mode, minute in [('1400', 15), ('1530', 0)]:
            start, end, _ = window(mode, '2026-10-08')
            self.assertEqual(start.hour, int(mode[:2]))
            self.assertEqual(end.minute, minute)
        start, end, _ = window('1400', '2026-10-08')
        self.assertGreater(datetime(2026,10,8,20,51,tzinfo=KST), end)
    def test_chunks(self):
        parts=list(chunks('🚀'*5000))
        self.assertTrue(all(len(p.encode('utf-16-le'))//2 <=4096 for p in parts))
    @patch('scripts.krx_delivery.window')
    @patch('scripts.krx_delivery.Ledger')
    @patch('scripts.krx_delivery.requests.post')
    def test_uncertain_blocks_resend(self, post, ledger, window_mock):
        now=datetime.now(KST); window_mock.return_value=(now,now,now)
        ledger.return_value.data={'status':'pending','parts':[{'status':'sending'}]}
        with self.assertRaises(RuntimeError):send_report('text','token','chat','1400')
        post.assert_not_called()
    @patch('scripts.krx_delivery.window')
    @patch('scripts.krx_delivery.Ledger')
    @patch('scripts.krx_delivery.requests.post')
    def test_delivered_blocks_resend(self, post, ledger, window_mock):
        now=datetime.now(KST); window_mock.return_value=(now,now,now)
        ledger.return_value.data={'status':'delivered','parts':[]}
        send_report('text','token','chat','1400');post.assert_not_called()

    def run_sender(self, payload=None, error=None, save_error=None):
        now = datetime.now(KST)
        ledger = Mock()
        ledger.data = {'status': 'pending', 'parts': []}
        ledger.save.side_effect = save_error
        with patch('scripts.krx_delivery.window', return_value=(now, now+timedelta(minutes=5), now)), patch('scripts.krx_delivery.Ledger', return_value=ledger), patch('scripts.krx_delivery.time.sleep'), patch('scripts.krx_delivery.requests.post') as post:
            post.side_effect = error
            post.return_value.json.return_value = payload
            if error or save_error or not payload.get('ok'):
                with self.assertRaises(RuntimeError): send_report('hello', 'token', 'chat', '1400')
            else:
                send_report('hello', 'token', 'chat', '1400')
            return ledger, post
    def test_receipt_required(self):
        ledger, post = self.run_sender({'ok': True, 'result': {'message_id': 42, 'chat': {'id': -123}}})
        self.assertEqual(ledger.data['status'], 'delivered')
        self.assertEqual(ledger.data['parts'][0]['message_id'], 42)
    def test_api_rejection_not_success(self):
        ledger, post = self.run_sender({'ok': False, 'error_code': 429})
        self.assertEqual(ledger.data['parts'][0]['status'], 'rejected')
    def test_timeout_leaves_uncertain_intent(self):
        ledger, post = self.run_sender(error=TimeoutError())
        self.assertEqual(ledger.data['parts'][0]['status'], 'sending')
    def test_failed_intent_write_never_sends(self):
        ledger, post = self.run_sender(save_error=RuntimeError('CAS conflict'))
        post.assert_not_called()

if __name__=='__main__':unittest.main()
