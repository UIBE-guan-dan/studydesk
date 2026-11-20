import unittest
from unittest.mock import patch,MagicMock
from types import SimpleNamespace
import app
class RecordingPermissionTests(unittest.TestCase):
 def test_cancel_does_not_open_microphone_or_create_file(self):
  owner=SimpleNamespace(stream=None)
  with patch('app.messagebox.askokcancel',return_value=False) as confirm,patch('app.wave.open') as wav:
   app.LegacyApp.start_record(owner)
   wav.assert_not_called();self.assertIsNone(owner.stream)
   self.assertIn('老师允许',confirm.call_args.args[1]);self.assertEqual(confirm.call_args.kwargs['default'],'cancel')
 def test_already_recording_does_not_prompt(self):
  with patch('app.messagebox.askokcancel') as confirm:
   with self.assertRaises(ValueError):app.LegacyApp.start_record(SimpleNamespace(stream=object()))
   confirm.assert_not_called()
if __name__=='__main__':unittest.main()
