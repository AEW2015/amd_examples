"""Configure once in the parent lab config; run an Ethernet test or dashboard."""
from pathlib import Path
from datetime import datetime
import argparse, hashlib, subprocess, sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from lab import config, tool


def arguments(c, mode, out=None, count=50, port=None):
    for key in ['hardware_vivado', 'server', 'cable', 'serial_port']:
        if not c.get(key):
            raise ValueError('Set lab config.json ' + key)
    pdi = Path(c.get('ethernet_pdi', HERE/'reference/ethernet.pdi')).resolve()
    restore = Path(c.get('ethernet_restore_pdi', c.get('restore_pdi', ''))).resolve()
    expected = c.get('ethernet_restore_sha256', c.get('restore_sha256', ''))
    if not pdi.is_file() or not restore.is_file():
        raise FileNotFoundError('Ethernet PDI or configured recovery PDI is missing')
    if hashlib.sha256(restore.read_bytes()).hexdigest() != expected:
        raise ValueError('Configured Ethernet recovery SHA256 differs')
    lock = Path.home()/'codex/hardware-coordination'/('scu35-'+c['cable']+'.lock')
    if lock.exists():
        raise RuntimeError('SCU35 already reserved; restore/stop its active session first: '+str(lock))
    out = Path(out) if out else Path(c['build_dir'])/'ethernet_runs'/(mode+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    args = [sys.executable, '-u', str(HERE/('dashboard.py' if mode=='dashboard' else 'run_hardware.py')),
            '--vivado', str(tool(c, 'hardware_vivado')), '--pdi', str(pdi),
            '--restore', str(restore), '--restore-sha256', expected,
            '--cable', c['cable'], '--serial', c['serial_port'], '--server', c['server'],
            '--bind', c.get('ethernet_bind', '192.168.10.1'),
            '--board', c.get('ethernet_board', '192.168.10.2'), '--out', str(out.resolve())]
    if mode == 'dashboard':
        args += ['--port', str(port or c.get('ethernet_dashboard_port', 8035))]
    else:
        args += ['--count', str(count)]
        marker = c.get('ethernet_restore_completion_marker')
        if marker:
            args += ['--restore-completion-marker', marker]
    return args, out.resolve()


def test(c=None, out=None, count=50):
    args, folder = arguments(c or config(), 'test', out=out, count=count)
    print('Programming Ethernet PDI, testing payloads, then verifying recovery.', flush=True)
    print('Evidence:', folder, flush=True)
    with subprocess.Popen(args, cwd=HERE, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, errors='replace', bufsize=1) as process:
        for line in process.stdout:
            print(line.rstrip(), flush=True)
        status = process.wait()
    if status:
        raise RuntimeError('Ethernet test failed; inspect '+str(folder))
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['test', 'dashboard'])
    parser.add_argument('--out', type=Path)
    parser.add_argument('--count', type=int, default=50)
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.mode == 'test':
        test(out=args.out, count=args.count)
    else:
        command, folder = arguments(config(), 'dashboard', args.out, port=args.port)
        print('Dashboard evidence:', folder, flush=True)
        subprocess.run(command, cwd=HERE, check=True)


if __name__ == '__main__':
    main()
