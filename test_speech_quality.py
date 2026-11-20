import unittest
from unittest.mock import patch
from types import SimpleNamespace
import app
from core import DEFAULTS,transcribe
from compare_transcription import normalize,edits

class SpeechQualityTests(unittest.TestCase):
    def test_sensevoice_routes_locally_without_prompting_expected_text(self):
        with patch('audio_sense.transcribe_sensevoice',return_value='原始识别') as recognize:
            result=transcribe('sample.wav',dict(DEFAULTS,local_model='sensevoice',speech_language='zh',speech_hotwords='不应传入的提示'),'unused',True)
            self.assertEqual(result,'原始识别'); recognize.assert_called_once_with('sample.wav','zh')
    def test_whisper_passes_language_and_hotwords_and_marks_low_score(self):
        segment=SimpleNamespace(start=0,end=1,text=' 课堂内容 ',avg_logprob=-1.2)
        with patch('faster_whisper.WhisperModel') as factory:
            factory.return_value.transcribe.return_value=([segment],None)
            result=transcribe('sample.wav',dict(DEFAULTS,local_model='small',speech_language='auto',speech_hotwords='回归，自变量'),'',True)
            kwargs=factory.return_value.transcribe.call_args.kwargs
            self.assertIsNone(kwargs['language']); self.assertEqual(kwargs['hotwords'],'回归，自变量')
            self.assertFalse(kwargs['condition_on_previous_text']); self.assertIn('建议回听',result)
    def test_reference_metric(self):
        self.assertEqual(normalize('[1.0s–2.0s] 一元回归，所以后面不统计'),'一元回归')
        self.assertEqual(edits('一元回归','议员回归'),2)

if __name__=='__main__':unittest.main()
