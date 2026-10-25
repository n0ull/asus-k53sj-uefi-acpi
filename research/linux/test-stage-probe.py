# SPDX-License-Identifier: MIT
"""UEFI smoke tests for skip-DUMMY and post-SVAM phase placement.

OVMF already has ACPI enabled; this does not exercise the real K53SJ SMI.
"""
from pathlib import Path
import os
import shutil
import subprocess
import time


def main():
    repo = Path(__file__).resolve().parents[2]
    dest = repo / 'build/research/stage3'
    work = dest / 'vm-tests'
    work.mkdir(parents=True, exist_ok=True)
    ovmf = Path(os.environ.get('OVMF_DIR', '/usr/share/OVMF'))
    stage_iso = dest / 'K53SJ-EFI-STAGE3.iso'
    alt = work / 'post-svam-iso'
    (alt / 'boot/grub').mkdir(parents=True, exist_ok=True)
    for name in ['vmlinuz-stage3', 'initramfs-stage3.cpio.gz']:
        shutil.copyfile(dest / name, alt / 'boot' / name)
    cfg = (repo / 'research/linux/stage-probe-grub.cfg').read_text()
    cfg = cfg.replace('set default=0', 'set default=1').replace('set timeout=15', 'set timeout=1')
    (alt / 'boot/grub/grub.cfg').write_text(cfg)
    alt_iso = work / 'post-svam-test.iso'
    with (work / 'package-post-svam.log').open('w') as out:
        subprocess.run(['grub-mkrescue', '-o', str(alt_iso), str(alt)],
                       stdout=out, stderr=out, check=True)

    def run(name, iso, expected):
        variables = work / (name + '-vars.fd')
        log = work / (name + '.log')
        log.write_text('')
        shutil.copyfile(ovmf / 'OVMF_VARS_4M.fd', variables)
        args = ['qemu-system-x86_64', '-machine', 'q35,accel=tcg', '-cpu', 'max',
                '-smbios', 'type=1,manufacturer=TestFixture,product=K53SJ',
                '-m', '1536', '-smp', '2',
                '-drive', 'if=pflash,format=raw,readonly=on,file=' + str(ovmf / 'OVMF_CODE_4M.fd'),
                '-drive', 'if=pflash,format=raw,file=' + str(variables),
                '-cdrom', str(iso), '-boot', 'd', '-nic', 'none', '-display', 'none',
                '-serial', 'file:' + str(log), '-monitor', 'none', '-no-reboot']
        with (work / (name + '-stderr.log')).open('w') as err:
            process = subprocess.Popen(args, stdout=err, stderr=err)
            try:
                deadline = time.monotonic() + 240
                while time.monotonic() < deadline:
                    text = log.read_text(errors='replace')
                    if 'K53DIAG USERSPACE READY' in text:
                        assert all(item in text for item in expected), name
                        assert 'k53diag_early_acpi ' not in text
                        assert 'REFUSED: ACPI disabled' not in text
                        if name == 'post-svam':
                            assert text.index('E05 SetVirtualAddressMap RETURN') < text.index('K53PHASE POST_SVAM ENTER')
                            assert text.index('K53PHASE POST_SVAM RETURN') < text.index('E09 delete_dummy_variable ENTER')
                        print('PASS:', name, 'UEFI runtime enabled; diagnostic userspace reached', flush=True)
                        return
                    if process.poll() is not None:
                        raise RuntimeError('QEMU exited; see ' + str(work / (name + '-stderr.log')))
                    time.sleep(1)
                raise RuntimeError('Boot test timeout: ' + str(log))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

    run('skip-dummy', stage_iso, ['K53PHASE DUMMY_DELETE SKIPPED', 'M15 acpi_subsystem_init RETURN'])
    run('post-svam', alt_iso, ['K53PHASE POST_SVAM ENTER', 'K53PHASE POST_SVAM RETURN'])


if __name__ == '__main__':
    main()
