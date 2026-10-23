import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from job_seeker.outbox import Outbox
from job_seeker.telegram import DeliveryUncertain

class OutboxTests(unittest.TestCase):
    def test_restart_receipt_deduplicates_successful_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'outbox.sqlite3';box=Outbox(path);box.enqueue('one','message')
            with patch('job_seeker.telegram.send',return_value=42) as send:
                self.assertEqual(box.deliver('one'),42)
                self.assertEqual(Outbox(path).deliver('one'),42);self.assertEqual(send.call_count,1)
    def test_definite_failure_can_retry_after_backoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            box=Outbox(Path(tmp)/'box.sqlite3');box.enqueue('one','message')
            with patch('job_seeker.telegram.send',side_effect=ValueError('rejected')):
                with self.assertRaises(ValueError):box.deliver('one')
            self.assertEqual(box.summary()[0]['status'],'pending')
            with patch('job_seeker.outbox.time.time',return_value=10**12),patch('job_seeker.telegram.send',return_value=42):box.drain()
            self.assertEqual(box.summary()[0]['status'],'sent')
    def test_uncertain_delivery_is_not_automatically_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            box=Outbox(Path(tmp)/'box.sqlite3');box.enqueue('one','message')
            with patch('job_seeker.telegram.send',side_effect=DeliveryUncertain('timeout')) as send:
                with self.assertRaises(DeliveryUncertain):box.deliver('one')
                box.drain();self.assertEqual(send.call_count,1)
            self.assertEqual(box.summary()[0]['status'],'uncertain')
    def test_checkpoint_happens_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            box=Outbox(Path(tmp)/'box.sqlite3');box.enqueue('one','message');events=[]
            with patch('job_seeker.telegram.send',side_effect=lambda **kw:events.append('network') or 42):box.deliver('one',before_send=lambda:events.append('checkpoint'))
            self.assertEqual(events,['checkpoint','network'])
