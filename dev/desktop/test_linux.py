"""Linux host boundaries and packaged CLI; no physical USB or system changes."""
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src/camera_runtime'), str(ROOT / 'dev/desktop')]
import linux_host
import linux_packages


def test_claim_unmounts_before_detach_and_never_uses_sudo(monkeypatch):
    events = []
    device = SimpleNamespace(idProduct=0x0e8a,
        get_active_configuration=lambda: {(0, 0): SimpleNamespace(
            bInterfaceClass=8, bInterfaceSubClass=6, bInterfaceProtocol=0x50)},
        is_kernel_driver_active=lambda _: True,
        detach_kernel_driver=lambda _: events.append('detach'))
    monkeypatch.setattr(linux_host, 'camera_path', lambda _: Path('/camera'))
    mounted = iter([{'/dev/sdc1'}, {'/dev/sdc1'}, set()])
    monkeypatch.setattr(linux_host, 'mounted_devices', lambda _: next(mounted))
    monkeypatch.setenv('LD_LIBRARY_PATH', '/frozen')
    def unmount(command, **kwargs):
        assert command == ['udisksctl', 'unmount', '--no-user-interaction', '-b', '/dev/sdc1']
        assert '/frozen' not in kwargs['env'].get('LD_LIBRARY_PATH', '')
        events.append('unmount')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(linux_host.subprocess, 'run', unmount)
    import usb.util
    monkeypatch.setattr(usb.util, 'claim_interface', lambda *_: events.append('claim'))
    linux_host.claim_camera_interface(device)
    assert events == ['unmount', 'detach', 'claim']


@pytest.mark.parametrize('failure', ['busy', 'changed', 'remounted'])
def test_unsafe_storage_stops_before_claim(monkeypatch, failure):
    paths = iter([Path('/camera'), Path('/other') if failure == 'changed' else Path('/camera'), Path('/camera')])
    monkeypatch.setattr(linux_host, 'camera_path', lambda _: next(paths))
    monkeypatch.setattr(linux_host, 'mounted_devices', lambda _: {'/dev/sdc1'})
    calls = []
    monkeypatch.setattr(linux_host.subprocess, 'run', lambda command, **kwargs:
                        calls.append(command) or SimpleNamespace(returncode=int(failure == 'busy'), stderr='busy'))
    with pytest.raises(RuntimeError):
        linux_host.claim_camera_interface(object())
    assert len(calls) == (0 if failure == 'changed' else 1)


def test_mount_filter_uses_sysfs_ancestry(tmp_path, monkeypatch):
    camera = tmp_path / 'camera'
    camera.mkdir()
    own = camera / 'block/sdc/sdc1'
    own.mkdir(parents=True)
    unrelated = tmp_path / 'host/sda1'
    unrelated.mkdir(parents=True)
    devices = tmp_path / 'dev-block'
    devices.mkdir()
    (devices / '8:33').symlink_to(own)
    (devices / '8:1').symlink_to(unrelated)
    mounts = tmp_path / 'mountinfo'
    mounts.write_text('1 2 8:33 / /media/card rw - vfat /dev/sdc1 rw\n'
                      '2 3 8:1 / / rw - ext4 /dev/sda1 rw\n')
    real_path = Path
    monkeypatch.setattr(linux_host, 'Path', lambda p:
                        mounts if p == '/proc/self/mountinfo' else devices if p == '/sys/dev/block' else real_path(p))
    assert linux_host.mounted_devices(camera) == {'/dev/sdc1'}


@pytest.mark.parametrize('machine,expected', [('x86_64', ('amd64', 'x86_64')), ('aarch64', ('arm64', 'aarch64'))])
def test_package_architectures(monkeypatch, machine, expected):
    monkeypatch.setattr(linux_packages.platform, 'machine', lambda: machine)
    assert linux_packages.architecture() == expected


def test_release_rejects_newer_glibc_before_packaging(monkeypatch, tmp_path):
    monkeypatch.setattr(linux_packages, 'architecture', lambda: ('amd64', 'x86_64'))
    monkeypatch.setattr(linux_packages.shutil, 'which', lambda tool: tool)
    monkeypatch.setattr(linux_packages, 'required_glibc', lambda _: (2, 43))
    monkeypatch.setattr(linux_packages.subprocess, 'run', lambda *_args, **_kwargs: pytest.fail('must not build'))
    with pytest.raises(ValueError, match='release builds must use Ubuntu 22.04'):
        linux_packages.build(tmp_path)


def test_glibc_scan_reads_version_requirements_not_embedded_text(tmp_path):
    (tmp_path / 'not-elf').write_bytes(b'GLIBC_999.0')
    assert linux_packages.required_glibc(tmp_path) == (2, 35)


def test_relr_abi_requires_glibc_236(monkeypatch, tmp_path):
    import elftools.elf.elffile
    (tmp_path / 'library.so').write_bytes(b'\x7fELF')
    section = SimpleNamespace(iter_versions=lambda: [(None, [SimpleNamespace(name='GLIBC_ABI_DT_RELR')])])
    monkeypatch.setattr(elftools.elf.elffile, 'ELFFile', lambda _: SimpleNamespace(get_section_by_name=lambda _: section))
    assert linux_packages.required_glibc(tmp_path) == (2, 36)


def test_one_click_rejects_linux_plugin_before_device_work(monkeypatch, tmp_path):
    from desktopapp import allinone
    monkeypatch.setattr(sys, 'platform', 'linux')
    with pytest.raises(ValueError, match='Lightroom'):
        allinone.run(dict(workspace=str(tmp_path), firmware='2.01', power_confirmed=True,
                         options={'plugin': True}), dispatch=lambda *_: pytest.fail('must not open USB'))
    assert not (tmp_path / 'setup.private.json').exists()


def test_package_stage_excludes_diagnostics(tmp_path):
    source = tmp_path / 'source'
    (source / '_internal').mkdir(parents=True)
    (source / 'A7C2Tools').write_bytes(b'executable')
    (source / '_internal/runtime').write_bytes(b'runtime')
    (source / 'private-diagnostics.zip').write_bytes(b'private')
    tree = tmp_path / 'package'
    linux_packages.stage(source, tree)
    assert (tree / 'usr/bin/A7C2Tools').resolve().read_bytes() == b'executable'
    assert not list(tree.rglob('*diagnostics*'))
    assert not (tree / 'etc').exists()


def test_linux_rejects_plugin_before_helper_download(monkeypatch):
    from desktopapp import plugins, exiftool
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr(exiftool, 'ensure', lambda *_: pytest.fail('must not download'))
    with pytest.raises(ValueError, match='Lightroom'):
        plugins.install({})


def test_linux_cli_plugin_install_has_no_partial_files(monkeypatch, tmp_path):
    from looktool import rawauto
    monkeypatch.setattr(sys, 'platform', 'linux')
    with pytest.raises(ValueError, match='no native Linux host'):
        rawauto.install(tmp_path / 'exiftool', root=tmp_path / 'settings', modules=tmp_path / 'modules')
    assert not list(tmp_path.iterdir())


def test_xdg_data_directory(monkeypatch, tmp_path):
    from desktopapp.paths import data_root
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.delenv('A7C2_DESKTOP_DATA', raising=False)
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path))
    assert data_root() == tmp_path / 'a7c2-tools'


@pytest.mark.parametrize('tool', ['fl23', 'lut', 'recovery', 'shutter', 'vertical',
                                 'a7look_compile', 'a7look_write', 'raw_auto', 'raw_import'])
def test_cli_help_outside_source_tree(tmp_path, tool):
    result = subprocess.run([sys.executable, str(ROOT / 'desktop.py'), '--cli', tool, '--help'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'usage:' in result.stdout
