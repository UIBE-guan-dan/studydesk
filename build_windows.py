"""Build Windows onedir app; run in an environment with requirements installed."""
from pathlib import Path
import os
import subprocess
import sys

root=Path(__file__).resolve().parent
output=root/'output/windows'
output.mkdir(parents=True,exist_ok=True)
env=os.environ.copy()
vendors=[root/'.vendor/sense_runtime',root/'.vendor/audio_compat',root/'.vendor']
env['PYTHONPATH']=os.pathsep.join(str(p) for p in vendors if p.exists())
args=[sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--name','StudyDesk',
      '--icon',str(root/'study.ico'),'--add-data',str(root/'study.ico')+';.',
      '--distpath',str(output/'dist'),'--workpath',str(output/'build'),
      '--specpath',str(output),'--copy-metadata','huggingface_hub']
for module in ('faster_whisper','sherpa_onnx','av','sounddevice','fsrs'):
    args += ['--collect-all',module]
args += ['--collect-binaries','ctranslate2','--collect-data','ctranslate2']
for module in ('torch','torchvision','torchaudio','transformers','tensorflow','IPython','pytest','pandas','scipy','pyarrow','numba','llvmlite','sympy','cv2','sklearn','pygame','notebook','jupyter','bokeh','plotly'):
    args += ['--exclude-module',module]
args.append(str(root/'app.py'))
subprocess.run(args,cwd=root,env=env,check=True)
