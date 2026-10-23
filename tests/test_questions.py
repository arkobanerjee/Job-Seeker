import tempfile
import unittest
from pathlib import Path
from job_seeker.questions import Questions,accept_reply,send_question
from unittest.mock import patch

class QuestionTests(unittest.TestCase):
    def test_restart_duplicates_and_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"questions.sqlite3"; store=Questions(path)
            q=store.ask("run","revision","Remote only?","Changes geography")
            self.assertEqual(q["id"],store.ask("run","revision","Remote only?","Changes geography")["id"])
            store=Questions(path)
            with self.assertRaises(ValueError): store.answer(q["id"],"old","yes")
            self.assertTrue(store.answer(q["id"],"revision","yes"))
            self.assertFalse(store.answer(q["id"],"revision","yes"))
            with self.assertRaises(ValueError): store.answer(q["id"],"revision","no")
            self.assertEqual(store.pending(),[])
    def test_owner_and_explicit_question_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Questions(Path(tmp)/"questions.sqlite3");q=store.ask("run","rev","Question?","Reason")
            message={"chat":{"id":123,"type":"private"},"from":{"id":999},"text":"/answer "+q["id"]+" yes"}
            with self.assertRaises(ValueError): accept_reply(store,message,"123")
            message["from"]["id"]=123
            self.assertEqual(accept_reply(store,message,"123"),"run")
    def test_notification_failure_remains_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Questions(Path(tmp)/"questions.sqlite3");q=store.ask("run","rev","Question?","Reason")
            with patch("job_seeker.telegram.send",side_effect=ValueError("offline")):
                with self.assertRaises(ValueError): send_question(store,q)
            self.assertFalse(store.get(q["id"])["delivered"])

    def test_plain_reply_uses_saved_message_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Questions(Path(tmp)/"q.sqlite3");q=store.ask("run","rev","Question?","Reason")
            with patch("job_seeker.telegram.send",return_value=42) as send:
                send_question(store,q)
                self.assertTrue(send.call_args.kwargs['force_reply'])
                self.assertNotIn(q['id'],send.call_args.kwargs['text'])
            message={"chat":{"id":123,"type":"private"},"from":{"id":123},"text":"Yes","reply_to_message":{"message_id":42,"from":{"is_bot":True}}}
            self.assertEqual(accept_reply(store,message,123),'run')
            self.assertEqual(store.get(q['id'])['answer'],'Yes')
