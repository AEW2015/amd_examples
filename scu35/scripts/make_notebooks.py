"""Generate the small replay-first notebook set; executes no notebook or hardware."""
from pathlib import Path
import nbformat as n
ROOT=Path(__file__).resolve().parents[1]
START='''from pathlib import Path
import hashlib, json, sys, time
import pandas as pd
# Works from the notebook directory, lab root, or parent repository.
candidates = [Path.cwd(), *Path.cwd().parents]
ROOT = next((p for base in candidates for p in (base, base / "scu35") if (p / "lab.py").is_file()), None)
assert ROOT is not None, "Launch Jupyter inside this checkout or its scu35 directory"
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "host"))
from compare import parse_capture
from lab import config
capture = parse_capture(ROOT / "evidence/timer/uart.txt", "7d1bf77bc454dd1f")
rows = pd.DataFrame(capture["rows"])
print("Recorded board capture: 31 complete rows; current Python:", sys.version.split()[0])
'''
SETUP='''These cells use **recorded hardware evidence** by default. They do not program a board.
Use the configured Python (SCU35 PMC) kernel. Fresh hardware commands are shown in Markdown and must be invoked explicitly after configuring your exact SCU35 and recovery image.
Current PL timing uses AXI Timer; native PMC timing uses `mcycle`. JTAG/UART are outside operation timing.
'''
topics=[
('00_start','Start here: shared IPI and platform',
'''Follow IPI → XSA → BSP → application ELF → PDI. The PL MicroBlaze V runs the application; the dedicated PMC processor runs PLM. No eFUSE/flash writes.

From the lab directory: `python lab.py doctor`, then `python lab.py build`. Inspect `hw/sys.bd`, `hw/sec_top.xdc`, `<build_dir>/hw.xsa` and the generated BSP before running hardware.''',
'''print("Root:", ROOT)
print("Build directory:", config()["build_dir"])
print("Firmware ID:", capture["metadata"]["build_id"])
display(rows[["algorithm", "case", "size_bytes", "scu35_operation_mean_us"]])'''),
('01_sha','SHA3-256 and SHAKE-256 user payloads',
'''Compare exact digests before discussing timing. SHA3-256 has a fixed 32-byte digest; SHAKE-256 is extendable and this example requests 32 bytes. Runtime hashes are not by themselves sender authentication.''',
'''from compare import payload, digest
for (algorithm, size), actual in capture["hashes"].items():
    expected = digest(algorithm, payload(size)).hex()
    assert actual.lower() == expected.lower()
    print(algorithm, size, actual)
display(rows[rows.algorithm.isin(["SHA3-256", "SHAKE-256"])])
data = payload(2048)
for name, function in [("SHA3-256", lambda: hashlib.sha3_256(data).digest()), ("SHAKE-256", lambda: hashlib.shake_256(data).digest(32))]:
    start = time.perf_counter_ns()
    for _ in range(1000): result = function()
    print(name, "fresh Python mean us:", (time.perf_counter_ns()-start)/1000/1000)'''),
('02_aes','AES-GCM payload encryption and authentication',
'''The public diagnostic key is bytes `00..1f` in volatile key storage. Exact captured ciphertext/tag and modified-tag rejection are checked by the strict parser. Compare setup + operation time with Python; do not compare transport time to engine throughput.''',
'''from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
key = bytes(range(32)); nonce = bytes(range(12)); message = b"SCU35 public demo payload"
ciphertext_tag = AESGCM(key).encrypt(nonce, message, None)
assert AESGCM(key).decrypt(nonce, ciphertext_tag, None) == message
try:
    AESGCM(key).decrypt(nonce, ciphertext_tag[:-1] + bytes([ciphertext_tag[-1] ^ 1]), None)
    raise AssertionError("Modified tag accepted")
except InvalidTag:
    print("Python modified-tag rejection: PASS")
display(rows[rows.algorithm.str.startswith("AES")])
print("Captured hardware AES cases independently checked:", len(capture["aes"]))'''),
('03_pq','Post-quantum LMS/HSS user authentication',
'''Hardened SHAKE plus software verification checks hash-based signatures. This addresses quantum-computer attacks on signature algorithms, not electromagnetic or quantum interference. Runtime vectors use H5/W2; their HSS wrapper has one level. Boot signing is a separate two-level H15 demonstration.''',
'''from hss_ref import load_vectors, verify_lms, verify_hss
vectors = load_vectors(ROOT / "host/inputs/hss.c")
for name, verifier in [("Lms", verify_lms), ("Hss", verify_hss)]:
    v = vectors[name]; message, signature, public_key = v["message"], v["signature"], v["public_key"]
    assert verifier(message, signature, public_key)
    changed = signature[:32] + bytes([signature[32] ^ 1]) + signature[33:]
    assert not verifier(message, changed, public_key)
    start = time.perf_counter_ns()
    for _ in range(20): assert verifier(message, signature, public_key)
    print(name, "Python mean us:", (time.perf_counter_ns()-start)/20/1000)
display(rows[rows.algorithm.isin(["LMS-SHAKE256", "HSS-SHAKE256"])])'''),
('04_puf','PUF helper data, key regeneration and AES',
'''A PUF has no physical Python equivalent. We check registration, volatile key clear, same-helper regeneration and five AES decrypt round trips. No key/helper data is exported. This is not permanent enrollment and does not write eFUSE. Run the shared runtime image explicitly for another board measurement.''',
'''features = {key: value for key, value in capture["features"].items() if key.startswith("PUF")}
assert {"PUF-REGISTER", "PUF-REGENERATE", "PUF-AES-ENC", "PUF-AES-DEC", "PUF-KEY-CLEAR"}.issubset(features)
display(pd.DataFrame(features).T)
print("PUF lifecycle and same-helper decrypt checks: passed by the strict capture parser")'''),
('05_rng','TRNG HRNG / DRNG / PTRNG',
'''The PMC peripheral name is PMCL_TRNG; the public driver is XTrngpsx. Driver setup includes self-tests and instantiation. Public-seeded DRNG is diagnostic, not production entropy. Python OS randomness is a different service; bytes must not match and smoke tests are not entropy certification.''',
'''import os
display(rows[rows.algorithm.str.contains("RNG")])
display(pd.DataFrame({k:v for k,v in capture["features"].items() if k.startswith("TRNG")}).T)
start = time.perf_counter_ns()
for _ in range(1000): random_bytes = os.urandom(32)
print("Python OS RNG mean us:", (time.perf_counter_ns()-start)/1000/1000)
assert len(random_bytes) == 32'''),
('06_boot','Real signed PDI and post-quantum boot',
'''`python lab.py boot` packages your new real design and uses fresh signing state. The following cells verify the retained H15 PDI signatures without private keys. Positive and tampered hardware captures remain separate from offline verification. No owner-pinned authentication policy was established; unsigned images were also accepted.''',
'''sys.path.insert(0, str(ROOT / "scripts"))
from pdi import verify_signed
signed = ROOT / "reference/boot/signed.pdi"
result, _ = verify_signed(signed.read_bytes(), ROOT / "evidence/boot/bundle")
assert all(result[k] for k in ["spk_signature_valid", "hash_block_signature_valid", "boot_header_hash_valid"])
display(result)
print("PDI SHA-256:", hashlib.sha256(signed.read_bytes()).hexdigest())'''),
('07_efuse_rolling','Read-only eFUSE and rolling-key architecture',
'''eFUSE key storage is persistent; this notebook performs no MMIO and no eFUSE access. The stock AMD XilNvm example main calls a writer and must not be run as a read-only demonstration. A visible register window is not a readable AES key.

The retained combined image uses a **public all-zero root** with AES-GCM key rolling and HSS authentication. Existing eFUSE selection is not provisioning or proof another board has the same state. Fresh packaging uses `python lab.py boot`; keys/private signing state remain local and excluded from Git.''',
'''inspection = json.loads((ROOT / "evidence/boot/bundle/inspection.json").read_text())
display(inspection["combined_signed_encrypted"])
assert inspection["combined_signed_encrypted"]["payloads_match_plain"]
print("Saved independent rolling-chain verification; no new hardware execution")
links = json.loads((ROOT / "docs/presenter/register_links.json").read_text())
display(links["subsections"]["PMCL_EFUSE"])'''),
('08_highspeed','High-speed native PMC post-configuration payloads',
'''Build with `python lab.py native`. Run explicitly with `python lab.py hardware --mode native --pdi /path/to/native/build/pmc_independent.pdi` after hardware setup. The native loader is experimental and separate from stock PLM secure boot.

Firmware `mcycle` timing includes setup/DMA/control, excluding JTAG/preload. Logical messages repeat resident chunks. Streamed AES validates the final chunk and whole-message tag. Rates are payload throughput, not measured link or HyperRAM bandwidth. PUF/RNG remain supported in the shared runtime path.''',
'''sys.path.insert(0, str(ROOT / "native"))
import analyze
native = analyze.validate(ROOT / "evidence/native/results.txt")
assert len(native["rows"]) == 66 and len(native["pq_rows"]) == 24
display(pd.DataFrame(native["rows"]))
display(pd.DataFrame(native["pq_rows"]))
print("Native frequency estimate:", native["clock_hz"], "Hz;", native["clock_reference"])
print("Fresh Python SHA3 8 KiB batches:")
display(pd.DataFrame(analyze.python_measure(1, 8192, 100)))'''),
('09_pdi','PLM ELF, CDO/RCDO and PDI audit',
'''The PDI contains loadable PLM bytes, configuration data and headers/hash framing. An ELF container can be much larger than its loadable segments. The retained normal PDI breakdown is from the older boot-design revision, not the new timer build.

Using the installed binaries from your configuration, run `bootgen -arch spartanup -read /path/to/demo.pdi` and `riscv64-unknown-elf-readelf -h -l /path/to/plm.elf`. These are offline inspections. Neither a readable PDI nor DONE status alone proves authentication.''',
'''breakdown = json.loads((ROOT / "evidence/pdi/breakdown.json").read_text())
display(breakdown)
bd = json.loads((ROOT / "hw/sys.bd").read_text())
segments = bd["design"]["addressing"]["/mb"]["address_spaces"]["Data"]["segments"]
display(pd.DataFrame(segments).T[["address_block", "offset", "range"]])
assert any(s["offset"].lower() == "0x40000000" for s in segments.values())''')]

def main():
    dest=ROOT/'notebooks';dest.mkdir(exist_ok=True)
    for name,title,description,body in topics:
        nb=n.v4.new_notebook(cells=[n.v4.new_markdown_cell('# '+title+'\n\n'+SETUP+'\n'+description),n.v4.new_code_cell(START),n.v4.new_code_cell(body),n.v4.new_markdown_cell('## Fresh hardware: explicit step\n\nConfigure `config.json` first. Run `python lab.py hardware --pdi /path/to/build/demo.pdi` from the lab directory for the full runtime suite, or the native/boot command above for that path. Save logs, verify recovery and compare results before discussing speed. See [audit checkpoints](../docs/audit.md).')])
        nb.metadata={'kernelspec':{'display_name':'Python (SCU35 PMC)','language':'python','name':'scu35-pmc'},'language_info':{'name':'python','version':'3.11'}}
        n.write(nb,dest/(name+'.ipynb'))
    print('Generated',len(topics),'replay-first notebooks')
if __name__=='__main__':main()
