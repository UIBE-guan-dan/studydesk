import sys, tempfile, unittest, wave
from pathlib import Path
from unittest.mock import patch
import app  # Load the same isolated audio dependency paths as the desktop launcher.
from core import ROOT
from source_range import extract_pdf_range,validate_range

class FakeText:
    def __init__(self,text):self.text=text
    def get_text_range(self):return self.text
    def close(self):pass
class FakePage:
    def __init__(self,text):self.text=text
    def get_textpage(self):return FakeText(self.text)
    def close(self):pass
class FakePDF:
    texts=['第一个页面的内容。'*20,'第二个页面的内容。'*20,'']
    def __init__(self,*args):pass
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def __len__(self):return len(self.texts)
    def __getitem__(self,i):return FakePage(self.texts[i])

class AudioRangeTests(unittest.TestCase):
    def test_real_whisper_decoder_resamples_stereo_wav(self):
        from faster_whisper.audio import decode_audio
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            p=Path(td)/'录音.wav'
            with wave.open(str(p),'wb') as w:
                w.setnchannels(2);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0'*8000)
            audio=decode_audio(str(p))
            self.assertEqual(len(audio),4000); self.assertEqual(str(audio.dtype),'float32')
    def test_ranges_reject_out_of_bounds_and_oversized(self):
        for start,end,total in [('x','3',10),(0,2,10),(4,2,10),(1,11,10),(1,51,100)]:
            with self.assertRaises(ValueError):validate_range(start,end,total)
        self.assertEqual(validate_range('2','3',10),(2,3))
    @patch('source_range.pdfium.PdfDocument',FakePDF)
    def test_inclusive_range_citations_and_missing_page_notice(self):
        result=extract_pdf_range('unused','教材',7,2,3)
        self.assertNotIn('第一个页面',result['evidence']); self.assertIn('第二个页面',result['evidence'])
        self.assertIn('PDF 第 2 页',result['evidence']); self.assertIn('PDF 第 3 页',result['evidence'])
        self.assertEqual(result['empty_pages'],[3])
    @patch('source_range.pdfium.PdfDocument',FakePDF)
    def test_empty_and_long_ranges_do_not_silently_truncate(self):
        with self.assertRaises(ValueError):extract_pdf_range('unused','教材',7,3,3)
        with self.assertRaises(ValueError):extract_pdf_range('unused','教材',7,1,2,max_chars=100)

if __name__=='__main__':unittest.main()
