# SPDX-License-Identifier: MIT
"""OVMF smoke test: scan without EC module must stop safely, then reach shell."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import time

repo = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--slot38', action='store_true', help='Test intervention refusal on OVMF without an EC match')
options = parser.parse_args()
dest = repo / ('build/research/ec-slot38' if options.slot38 else 'build/research/ec-watch')
results = dest / 'vm-tests'
results.mkdir(parents=True, exist_ok=True)
# Keep frequently-written serial output on Linux storage, not a mounted NTFS path.
work = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / ('acpifirst-slot38-vm' if options.slot38 else 'acpifirst-ec-watch-vm')
work.mkdir(parents=True, exist_ok=True)
ovmf = Path(os.environ.get('OVMF_DIR', '/usr/share/OVMF'))
variables = work / 'vars.fd'
shutil.copyfile(ovmf / 'OVMF_VARS_4M.fd', variables)
log = work / 'serial.log'
log.write_text('')
iso = work / 'K53SJ-EC-WATCH.iso'
if options.slot38:
    fixture_root = work / 'iso'
    shutil.copytree(dest / 'iso', fixture_root, dirs_exist_ok=True)
    cfg_path = fixture_root / 'boot/grub/grub.cfg'
    cfg = cfg_path.read_text().replace('set default=0', 'set default=1').replace('set timeout=-1', 'set timeout=1')
    cfg_path.write_text(cfg)
    with (work / 'package.log').open('w') as package_log:
        subprocess.run(['grub-mkrescue', '-o', str(iso), str(fixture_root)], stdout=package_log,
                       stderr=package_log, check=True)
else:
    shutil.copyfile(dest / iso.name, iso)
args = ['qemu-system-x86_64', '-machine', 'q35,accel=tcg', '-cpu', 'max',
        '-smbios', 'type=1,manufacturer=TestFixture,product=K53SJ', '-m', '1536', '-smp', '2',
        '-drive', 'if=pflash,format=raw,readonly=on,file=' + str(ovmf / 'OVMF_CODE_4M.fd'),
        '-drive', 'if=pflash,format=raw,file=' + str(variables),
        '-cdrom', str(iso), '-boot', 'd', '-nic', 'none',
        '-display', 'none', '-serial', 'file:' + str(log), '-monitor', 'none', '-no-reboot']
with (work / 'stderr.log').open('w') as errors:
    process = subprocess.Popen(args, stdout=errors, stderr=errors)
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            text = log.read_text(errors='replace')
            if 'K53DIAG USERSPACE READY' in text:
                assert 'K53EC PRE candidates=0' in text
                assert 'K53EC STOP: require one exact physical EC table match' in text
                assert 'K53EC POST physical_table=' not in text
                assert 'K53PHASE POST_SVAM RETURN' in text
                assert text.index('K53EC PRE') < text.index('E05 SetVirtualAddressMap ENTER')
                if options.slot38:
                    assert 'k53diag_ec_restore38' in text
                    assert 'K53SLOT38 REFUSED: prerequisites not met' in text
                    assert 'K53SLOT38 APPLY ENTER' not in text
                print('PASS: OVMF no-match scan stops safely; POST_SVAM probe and shell reached', flush=True)
                break
            if process.poll() is not None:
                raise RuntimeError('QEMU exited')
            time.sleep(1)
        else:
            raise RuntimeError('Timeout: ' + str(log))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        shutil.copyfile(log, results / 'serial.log')
