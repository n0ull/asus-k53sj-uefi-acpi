# SPDX-License-Identifier: MIT
"""Run inventory with isolated FAT images, never attach a host disk."""
from pathlib import Path
import os
import shutil
import subprocess
import time


repo = Path(__file__).resolve().parents[1]
dest = repo / 'build/research/runtime-inventory'
work = dest / 'vm-tests'
work.mkdir(parents=True, exist_ok=True)
ovmf = Path(os.environ.get('OVMF_DIR', '/usr/share/OVMF'))


def disk(name, boot=False, marked=False, existing=False):
    path = work / (name + '.img')
    with path.open('wb') as f:
        f.truncate(64 * 1024 * 1024)
    subprocess.run(['mformat', '-i', str(path), '-F', '::'], check=True)
    if boot:
        subprocess.run(['mmd', '-i', str(path), '::/EFI', '::/EFI/BOOT'], check=True)
        subprocess.run(['mcopy', '-i', str(path), str(dest / 'RuntimeInventory.efi'),
                        '::/EFI/BOOT/BOOTX64.EFI'], check=True)
    if marked:
        subprocess.run(['mcopy', '-i', str(path), str(dest / 'K53PROBE.TAG'), '::/K53PROBE.TAG'], check=True)
    if existing:
        fixture = work / 'existing.txt'
        fixture.write_bytes(b'KEEP-EXISTING-REPORT\r\n')
        subprocess.run(['mcopy', '-i', str(path), str(fixture), '::/K53SVAM-00.TXT'], check=True)
    return path


def run(name, disks, expected, iso=None):
    log = work / (name + '.log')
    log.write_text('')
    variables = work / (name + '-vars.fd')
    shutil.copyfile(ovmf / 'OVMF_VARS_4M.fd', variables)
    args = ['qemu-system-x86_64', '-machine', 'q35,accel=tcg', '-m', '512',
            '-drive', 'if=pflash,format=raw,readonly=on,file=' + str(ovmf / 'OVMF_CODE_4M.fd'),
            '-drive', 'if=pflash,format=raw,file=' + str(variables), '-nic', 'none',
            '-display', 'none', '-serial', 'file:' + str(log), '-monitor', 'none', '-no-reboot']
    for image in disks:
        args += ['-drive', 'format=raw,file=' + str(image)]
    if iso:
        args += ['-cdrom', str(iso), '-boot', 'd']
    with (work / (name + '-stderr.log')).open('w') as errors:
        process = subprocess.Popen(args, stdout=errors, stderr=errors)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                text = log.read_text(errors='replace')
                if expected in text:
                    print('PASS:', name, flush=True)
                    return
                if process.poll() is not None:
                    raise RuntimeError('QEMU exited: ' + name)
                time.sleep(1)
            raise RuntimeError('Timeout: ' + str(log))
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def read(image, name):
    return subprocess.check_output(['mtype', '-i', str(image), '::/' + name])


single = disk('single', boot=True, marked=True, existing=True)
run('one-marker', [single], 'K53SVAM inventory finished: Success')
assert read(single, 'K53SVAM-00.TXT') == b'KEEP-EXISTING-REPORT\r\n'
report = read(single, 'K53SVAM-01.TXT').decode('ascii')
(work / 'sample-report.txt').write_text(report)
assert 'RuntimeArch status=Success' in report
assert 'IMAGE 0 ' in report and 'EVENT 0 ' in report
assert 'SVAM=' in report and 'CONVERT=' in report
assert 'INVALID' not in report and 'incomplete/capped' not in report
assert 'END inventory' in report
print('PASS: parsed OVMF runtime image/event lists; existing report preserved', flush=True)

none = disk('none', boot=True)
run('no-marker', [none], 'found 0')
listing = subprocess.check_output(['mdir', '-i', str(none), '::/']).decode()
assert 'K53SVAM' not in listing

first = disk('first', boot=True, marked=True)
second = disk('second', marked=True)
run('two-markers', [first, second], 'found 2')
for image in (first, second):
    listing = subprocess.check_output(['mdir', '-i', str(image), '::/']).decode()
    assert 'K53SVAM' not in listing
print('PASS: absent/ambiguous marker refuses report writes', flush=True)

iso_target = disk('iso-target', marked=True)
run('iso-entry', [iso_target], 'K53SVAM inventory finished: Success',
    dest / 'K53SJ-RUNTIME-INVENTORY.iso')
assert b'RuntimeArch status=Success' in read(iso_target, 'K53SVAM-00.TXT')
print('PASS: distributed GRUB ISO starts inventory and saves report', flush=True)
