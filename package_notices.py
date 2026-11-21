"""Copy copyright notices for distributions used by the frozen application."""
import ast
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys

root=Path(__file__).resolve().parent
for p in (root/'.vendor',root/'.vendor/audio_compat',root/'.vendor/sense_runtime'):
    if p.exists():sys.path.insert(0,str(p))
target=root/'output/windows/dist/StudyDesk'
notices=target/'third-party-licenses';notices.mkdir(parents=True,exist_ok=True)
toc=ast.literal_eval((root/'output/windows/build/StudyDesk/Analysis-00.toc').read_text(encoding='utf-8'))
modules=set()
def visit(value):
    if isinstance(value,(tuple,list)):
        if len(value)==3 and isinstance(value[2],str) and value[2] in ('PYMODULE','EXTENSION'):
            modules.add(str(value[0]).split('.')[0])
        for item in value:visit(item)
visit(toc)
mapping=metadata.packages_distributions();names=set()
for module in modules:names.update(mapping.get(module,[]))
inventory=[]
for name in sorted(names):
    dist=metadata.distribution(name)
    inventory.append({'name':dist.metadata['Name'],'version':dist.version,
                      'license':dist.metadata.get('License-Expression') or dist.metadata.get('License',''),
                      'sources':dist.metadata.get_all('Project-URL',[])})
    folder=notices/name;folder.mkdir(exist_ok=True)
    (folder/'METADATA.txt').write_text(dist.read_text('METADATA') or '',encoding='utf-8')
    for f in dist.files or []:
        if any(word in str(f).lower() for word in ('license','copying','notice','authors')) and str(f).lower().endswith(('.txt','.rst','.md','.html','license','copying','notice')):
            source=Path(dist.locate_file(f))
            if source.is_file():
                dest=folder/Path(str(f)).name
                if dest.exists():dest=folder/(str(f).replace('/','_').replace('\\','_'))
                shutil.copyfile(source,dest)
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():shutil.copyfile(python_license,notices/'Python-LICENSE.txt')
(notices/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Collected notices for {len(inventory)} distributions')
