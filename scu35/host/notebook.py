"""Notebook orchestration: explicit fresh sessions, streamed UART and host timing.

Replay is always labelled. A failed live run never falls back to saved evidence.
Uses the same repository IPI image and lab.py hardware runner as the CLI.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, os, subprocess, sys, time, uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import config, sha
from compare import parse_capture, run as compare_run


def command(*args, c=None, on_line=None):
    """Stream the CLI in this kernel's interpreter; preserve the CLI's recovery."""
    c = c or config()
    out = Path(c['build_dir']).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cfg = out / ('notebook_' + uuid.uuid4().hex[:8] + '.json')
    cfg.write_text(json.dumps(c, indent=2))
    env = os.environ.copy()
    env['SCU35_CONFIG'] = str(cfg)
    started = time.perf_counter()
    print('RUN:', ' '.join(map(str, args)), flush=True)
    try:
        with subprocess.Popen([sys.executable, '-u', str(ROOT/'lab.py'), *map(str, args)],
                              cwd=ROOT, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, errors='replace',
                              bufsize=1) as process:
            for line in process.stdout:
                print(line.rstrip(), flush=True)
                if on_line is not None:
                    on_line(line)
            status = process.wait()
        if status:
            raise RuntimeError('Lab command failed; inspect session logs. No replay fallback.')
    finally:
        cfg.unlink(missing_ok=True)
    return time.perf_counter() - started


def check_build(c):
    out = Path(c['build_dir']).resolve()
    manifest = json.loads((out/'build_manifest.json').read_text())['files']
    for name in ['hw.xsa', 'bench.elf', 'plm.elf', 'demo.pdi']:
        if sha(out/name) != manifest[name]:
            raise ValueError('Build artifact differs: ' + name)
    fw = json.loads((out/'firmware.json').read_text())
    if sha(out/'bench.elf') != fw['elf_sha256'] or sha(ROOT/'fw/bench.c') != fw['source_sha256']:
        raise ValueError('Firmware source/ELF differs from the selected build')
    checks = json.loads((out/'implementation_checks.json').read_text())
    if checks['setup_slack_ns'] < 0 or checks['hold_slack_ns'] < 0:
        raise ValueError('Implementation timing failed')
    return out/'demo.pdi'


def hardware(pdi, mode='runtime', c=None, on_line=None):
    c = c or config()
    # Also respect the workstation's shared reservation convention.
    cable = c.get('cable', '')
    shared = Path.home()/'codex/hardware-coordination'/('scu35-'+cable+'.lock')
    if shared.exists():
        raise RuntimeError('Board already reserved: ' + str(shared))
    runs = Path(c['build_dir']).resolve()/'runs'
    before = set(runs.glob('*/session.json'))
    wall = command('hardware', '--mode', mode, '--pdi', Path(pdi).resolve(),
                   c=c, on_line=on_line)
    new = set(runs.glob('*/session.json')) - before
    if len(new) != 1:
        raise RuntimeError('Expected exactly one new session: ' + str(new))
    session = new.pop().parent
    meta = json.loads((session/'session.json').read_text())
    if not meta.get('demo_pass') or not meta.get('recovery_pass'):
        raise RuntimeError('Demo or recovery failed: ' + str(session))
    if meta['pdi_sha256'] != sha(pdi):
        raise ValueError('Session PDI identity differs')
    print('Fresh hardware and recovery PASS:', session, flush=True)
    print('Host session wall time (program/capture/recovery, NOT crypto latency):', wall, 's')
    return session, wall


class LiveRows:
    """Provisional table updated as UART timing rows arrive; validated at completion."""
    def __init__(self, algorithms=None):
        from IPython.display import display
        self.algorithms = algorithms
        self.rows = []
        self.handle = display('Waiting for fresh UART timing rows…', display_id=True)

    def __call__(self, line):
        import pandas as pd
        if 'CMP_ROW,' not in line:
            return
        fields = line[line.index('CMP_ROW,'):].strip().split(',')
        if len(fields) != 12:
            return
        _, algorithm, case, *values = fields
        if self.algorithms and algorithm not in self.algorithms:
            return
        size, repeats, copy, setup, api, check, lo, hi, status = map(int, values)
        us = (api + (setup if algorithm in ('SHA3-256','SHAKE-256','AES-GCM-ENC','AES-GCM-DEC') else 0))/repeats/100
        self.rows.append({'algorithm':algorithm, 'case':case, 'bytes':size,
                          'SCU35 us (provisional)':us, 'status':status})
        self.handle.update(pd.DataFrame(self.rows))


def runtime(live=False, repeats=1, samples=1000, pq_samples=50, on_line=None, c=None):
    c = c or config()
    if repeats < 1:
        raise ValueError('repeats must be positive')
    reports = []
    for index in range(repeats):
        session = None
        if live:
            pdi = check_build(c)
            print('FRESH HARDWARE run', index+1, 'of', repeats, flush=True)
            session, wall = hardware(pdi, c=c, on_line=on_line)
            capture = session/'uart.txt'
        else:
            capture = ROOT/'evidence/timer/uart.txt'
            print('RECORDED HARDWARE + FRESH PYTHON; no board access', flush=True)
        parsed = parse_capture(capture, '7d1bf77bc454dd1f')
        if session:
            folder = session
        else:
            folder = Path(c['build_dir']).resolve()/'notebook_replay'/uuid.uuid4().hex[:8]
            folder.mkdir(parents=True)
        print('Measuring fresh Python references…', flush=True)
        report = compare_run(capture, folder/'comparison.html', samples, pq_samples)
        report['notebook'] = {'hardware_fresh':bool(session), 'capture':str(capture),
                              'session':str(session) if session else None,
                              'measured_utc':datetime.now(timezone.utc).isoformat(),
                              'session_wall_s':wall if session else None}
        (folder/'notebook_report.json').write_text(json.dumps(report, indent=2))
        report['parsed'] = parsed
        report['report_path'] = str(folder/'comparison.html')
        reports.append(report)
    return reports


def show_runtime(reports, algorithms=None, feature_prefix=None):
    import pandas as pd
    import matplotlib.pyplot as plt
    from IPython.display import display
    combined = []
    for number, report in enumerate(reports, 1):
        for row in report['comparisons']:
            if algorithms and row['algorithm'] not in algorithms:
                continue
            r = dict(row, run=number)
            r['SCU35 MB/s'] = r['size_bytes']/r['scu35_operation_mean_us']
            r['Python MB/s'] = r['size_bytes']/r['python_mean_us']
            r['SCU35 operations/s'] = 1e6/r['scu35_operation_mean_us']
            r['Python operations/s'] = 1e6/r['python_mean_us']
            combined.append(r)
    frame = pd.DataFrame(combined)
    if feature_prefix is None:
        columns = ['run','algorithm','case','size_bytes','scu35_operation_mean_us',
                   'python_mean_us','SCU35 MB/s','Python MB/s',
                   'SCU35 operations/s','Python operations/s','results_match']
        display(frame[columns])
        valid = frame[frame['case']=='valid'].copy()
        if not valid.empty:
            valid['label'] = valid['algorithm']+' / '+valid['size_bytes'].astype(str)+' B / run '+valid['run'].astype(str)
            fig, axes = plt.subplots(1,2,figsize=(14,max(3,len(valid)*.25)))
            valid.set_index('label')[['scu35_operation_mean_us','python_mean_us']].plot.barh(ax=axes[0],logx=True)
            axes[0].set_xlabel('Processing latency (us, log scale)')
            valid.set_index('label')[['SCU35 MB/s','Python MB/s']].plot.barh(ax=axes[1])
            axes[1].set_xlabel('Effective payload throughput (decimal MB/s)')
            fig.tight_layout(); display(fig); plt.close(fig)
    if feature_prefix:
        features = []
        for number, report in enumerate(reports, 1):
            for name, row in report['parsed']['features'].items():
                if name.startswith(feature_prefix):
                    features.append({'run':number,'feature':name,**row})
        features = pd.DataFrame(features)
        display(features)
        if not features.empty:
            fig, ax = plt.subplots(figsize=(10,4))
            features.assign(label=features.feature+' / run '+features.run.astype(str)).set_index('label')['mean_us'].plot.barh(ax=ax,logx=True)
            ax.set_xlabel('Hardware lifecycle latency (us, log scale)')
            fig.tight_layout(); display(fig); plt.close(fig)
        if feature_prefix == 'TRNG':
            rng = []
            for number, report in enumerate(reports, 1):
                for row in report['parsed']['rows']:
                    if row['algorithm'].startswith('TRNG'):
                        rng.append({'run':number,'method':row['algorithm'],
                                    'SCU35 generate32 us':row['scu35_api_mean_us'],
                                    'Python os.urandom32 us':report['host_random']['python_mean_us'],
                                    'comparison':'Different RNG services; output bytes must not match'})
            display(pd.DataFrame(rng))
        else:
            print('PUF has no physical Python equivalent. No synthetic PUF timing is reported.')
    for report in reports:
        print('FRESH HARDWARE' if report['notebook']['hardware_fresh'] else 'RECORDED HARDWARE',
              '+ FRESH PYTHON:', report['report_path'])
    if algorithms is None and feature_prefix is None:
        lifecycle = []
        for number, report in enumerate(reports, 1):
            lifecycle.extend(dict(row, run=number) for row in report['special_features'])
        print('PUF and RNG lifecycle/generation results (different Python comparability):')
        display(pd.DataFrame(lifecycle))
    print('Device processing rates exclude programming/UART/JTAG. They are not physical bus bandwidth measurements.')
    return frame
