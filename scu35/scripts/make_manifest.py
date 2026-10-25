"""Create the public file-integrity manifest after final content changes."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def main():
    ignored={'manifest.json','validation.json'}
    files={}
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or any(s in p.parts for s in ['__pycache__','.venv','out','.ipynb_checkpoints']):continue
        if p.suffix in ['.pyc','.jou','.str'] or p.name.endswith('.log.bak') or p==ROOT/'config.json' or (p.parent==ROOT and p.name in ignored):continue
        files[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    record={'scope':'Delivered SCU35 public files; original dated metadata is historical and new builds are separate. Integrity checks do not authenticate captures.','created_utc':datetime.now(timezone.utc).isoformat(),'files':files}
    (ROOT/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    print('MANIFEST_FILES',len(files))
if __name__=='__main__':main()
