# SPDX-License-Identifier: MIT
from pathlib import Path
import shutil
import subprocess
import time
import argparse
import os



def main():
    parser = argparse.ArgumentParser(description='Isolated OVMF discovery/entry tests; no host disks attached.')
    parser.add_argument('--build-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'build')
    args = parser.parse_args()
    src = args.build_dir.resolve()
    work = src / 'vm-tests'
    work.mkdir(parents=True, exist_ok=True)
    results = src / 'test-results'
    results.mkdir(parents=True, exist_ok=True)
    ovmf = Path(os.environ.get('OVMF_DIR', '/usr/share/OVMF'))

    def fat_disk(name, executable=None, installer=False, dual_arch=False):
        disk = work / (name + '.img')
        with disk.open('wb') as f:
            f.truncate(64 * 1024 * 1024)
        subprocess.run(['mformat', '-i', str(disk), '-F', '::'], check=True)
        subprocess.run(['mmd', '-i', str(disk), '::/EFI', '::/EFI/BOOT'], check=True)
        if executable:
            subprocess.run(['mcopy', '-i', str(disk), str(executable), '::/EFI/BOOT/BOOTX64.EFI'], check=True)
        if installer:
            # Test fixtures only: these are not executable Windows images.
            fixture = work / 'fixture.bin'
            fixture.write_bytes(b'READ_ONLY_DISCOVERY_TEST_FIXTURE')
            if dual_arch:
                subprocess.run(['mmd', '-i', str(disk), '::/x64', '::/x64/sources', '::/x86', '::/x86/sources'], check=True)
                wim = '::/x64/sources/boot.wim'
            else:
                subprocess.run(['mmd', '-i', str(disk), '::/sources'], check=True)
                wim = '::/sources/boot.wim'
            for target in [wim, '::/EFI/BOOT/BOOTX64.EFI']:
                subprocess.run(['mcopy', '-i', str(disk), str(fixture), target], check=True)
        return disk

    boot = fat_disk('discovery-boot', src / 'test-only/DiscoveryTest.efi')
    one = fat_disk('installer-one', installer=True)
    two = fat_disk('installer-two', installer=True)
    dual = fat_disk('installer-dual-arch', installer=True, dual_arch=True)

    def run(name, expected, disks=(), iso=None):
        log = work / (name + '.log')
        log.write_text('')
        variables = work / (name + '-vars.fd')
        shutil.copyfile(ovmf / 'OVMF_VARS_4M.fd', variables)
        args = ['qemu-system-x86_64', '-machine', 'q35,smbios-entry-point-type=32,accel=tcg',
                '-m', '512', '-smp', '1',
                '-drive', 'if=pflash,format=raw,readonly=on,file=' + str(ovmf / 'OVMF_CODE_4M.fd'),
                '-drive', 'if=pflash,format=raw,file=' + str(variables),
                '-snapshot', '-nic', 'none', '-display', 'none',
                '-serial', 'file:' + str(log), '-monitor', 'none', '-no-reboot']
        if iso:
            args += ['-cdrom', str(iso), '-boot', 'd']
        for disk in disks:
            args += ['-drive', 'format=raw,file=' + str(disk)]
        with (work / (name + '-stderr.log')).open('w') as err:
            process = subprocess.Popen(args, stdout=err, stderr=err)
            try:
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    text = log.read_text(errors='replace')
                    if expected in text:
                        assert 'SMI outb ENTER' not in text
                        (results / (name + '.log')).write_text(text)
                        print('PASS:', name, expected, flush=True)
                        return
                    if process.poll() is not None:
                        raise RuntimeError((work / (name + '-stderr.log')).read_text())
                    time.sleep(1)
                raise RuntimeError('Timeout: ' + str(log))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

    run('iso-direct-guard', 'REFUSED: SMBIOS product is not the supported K53SJ.',
        iso=src / 'dist/AcpiFirst-Direct-v3-UEFI.iso')
    run('discovery-none', 'STOP: no visible Windows installer filesystem.', [boot])
    run('discovery-one', 'K53_DISCOVERY_TEST result=Success', [boot, one])
    run('discovery-multiple', 'STOP: more than one Windows installer found;', [boot, one, two])
    run('discovery-dual-arch', 'K53_DISCOVERY_TEST result=Success', [boot, dual])


if __name__ == "__main__":
    main()
