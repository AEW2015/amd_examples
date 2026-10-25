"""Execute replay-only notebooks, using the selected Python and a temporary kernel."""
from pathlib import Path
import json,os,sys,tempfile
import nbformat
from nbclient import NotebookClient
ROOT=Path(__file__).resolve().parents[1]
def main():
    # Keep kernel registration out of the user's Jupyter installation.
    with tempfile.TemporaryDirectory(prefix='s35kern_') as temporary:
        directory=Path(temporary)/'kernels/scu35-ci';directory.mkdir(parents=True)
        (directory/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'SCU35 verification','language':'python'}))
        old=os.environ.get('JUPYTER_PATH');os.environ['JUPYTER_PATH']=temporary+(os.pathsep+old if old else '')
        try:
            for path in sorted((ROOT/'notebooks').glob('*.ipynb')):
                nb=nbformat.read(path,as_version=4)
                NotebookClient(nb,timeout=180,kernel_name='scu35-ci',resources={'metadata':{'path':str(path.parent)}}).execute()
                nbformat.write(nb,path)
                print('NOTEBOOK_PASS',path.name,flush=True)
        finally:
            if old is None:os.environ.pop('JUPYTER_PATH',None)
            else:os.environ['JUPYTER_PATH']=old
if __name__=='__main__':main()
