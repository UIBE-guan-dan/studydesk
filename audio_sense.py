"""Local SenseVoice inference via sherpa-onnx; VAD limits each speech segment."""
from pathlib import Path

MODEL_DIR=Path(__file__).resolve().parent/'data/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17'

def transcribe_sensevoice(path,language='zh'):
    import sherpa_onnx
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import get_speech_timestamps,VadOptions
    if language not in ('zh','en','auto'):raise ValueError('录音语言请选择 zh、en 或 auto')
    if not (MODEL_DIR/'model.int8.onnx').exists():raise ValueError('未找到 SenseVoice 本地模型，请查看使用说明安装模型，或切换到 Whisper small。')
    audio=decode_audio(str(path),sampling_rate=16000)
    if len(audio)==0:raise ValueError('录音中没有可解码的声音')
    spans=get_speech_timestamps(audio,VadOptions(max_speech_duration_s=25,min_silence_duration_ms=500,speech_pad_ms=300))
    if not spans:return ''
    recognizer=sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=str(MODEL_DIR/'model.int8.onnx'),tokens=str(MODEL_DIR/'tokens.txt'),
        num_threads=4,use_itn=True,language=language,provider='cpu')
    lines=[]
    for span in spans:
        stream=recognizer.create_stream(); stream.accept_waveform(16000,audio[span['start']:span['end']])
        recognizer.decode_stream(stream); text=stream.result.text.strip()
        if text:lines.append(f"[{span['start']/16000:.1f}s–{span['end']/16000:.1f}s] {text}")
    return '\n'.join(lines)
