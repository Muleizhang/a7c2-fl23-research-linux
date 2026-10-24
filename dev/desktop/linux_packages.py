"""Native Linux deb, rpm and AppImage packaging; never installs packages."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).with_name('linux')
APP_ID = 'io.github.QAQLeonard.A7C2Tools'
ARCHITECTURES = {'x86_64': ('amd64', 'x86_64'), 'aarch64': ('arm64', 'aarch64')}


def architecture():
    machine = platform.machine()
    if machine not in ARCHITECTURES:
        raise ValueError('Linux packaging requires native x86_64 or aarch64')
    return ARCHITECTURES[machine]


def required_glibc(source):
    from elftools.elf.elffile import ELFFile
    versions = [(2, 35)]
    for path in source.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                continue
            stream.seek(0)
            section = ELFFile(stream).get_section_by_name('.gnu.version_r')
            if section is not None:
                for _, auxiliaries in section.iter_versions():
                    for entry in auxiliaries:
                        if re.fullmatch(r'GLIBC_[0-9.]+', entry.name):
                            versions.append(tuple(map(int, entry.name[6:].split('.'))))
                        elif entry.name == 'GLIBC_ABI_DT_RELR':
                            versions.append((2, 36))
    return max(versions)


def stage(source, destination):
    """Allow only the frozen payload, never nearby user diagnostics."""
    app = destination / 'usr/lib/a7c2-tools'
    app.mkdir(parents=True)
    shutil.copy2(source / 'A7C2Tools', app / 'A7C2Tools')
    shutil.copytree(source / '_internal', app / '_internal', symlinks=True)
    for name in ('README.md', 'README.zh-CN.md', 'LICENSE'):
        shutil.copy2(ROOT / name, app / name)
    for source_path, target in (
        (ASSETS / (APP_ID + '.desktop'), destination / 'usr/share/applications' / (APP_ID + '.desktop')),
        (ASSETS / (APP_ID + '.svg'), destination / 'usr/share/icons/hicolor/scalable/apps' / (APP_ID + '.svg')),
        (ASSETS / '70-a7c2-tools.rules', destination / 'usr/share/a7c2-tools/70-a7c2-tools.rules'),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
    launch = destination / 'usr/bin/A7C2Tools'
    launch.parent.mkdir(parents=True)
    launch.symlink_to('../lib/a7c2-tools/A7C2Tools')


def build(output, *, appimagetool='appimagetool', revision='1', local=False):
    deb_arch, rpm_arch = architecture()
    if not re.fullmatch(r'[1-9][0-9]*', revision):
        raise ValueError('Package revision must be a positive integer')
    for tool in ('dpkg-deb', 'rpmbuild', appimagetool):
        if not shutil.which(tool):
            raise FileNotFoundError('Required packaging tool: ' + tool)
    version = {}
    exec((ROOT / 'src/desktopapp/__init__.py').read_text(), version)
    version = version['VERSION']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('Linux release packaging requires a numeric major.minor.patch version')
    output = Path(output).resolve()
    glibc = required_glibc(output / 'A7C2Tools')
    if glibc > (2, 35) and not local:
        raise ValueError('Bundled libraries require glibc ' + '.'.join(map(str, glibc))
                         + '; release builds must use Ubuntu 22.04. Use --local-linux-build only for local testing.')
    glibc_version = '.'.join(map(str, glibc))
    if local:
        revision += '.local'
    targets = []
    with tempfile.TemporaryDirectory(prefix='linux-package-', dir=output) as temporary:
        work = Path(temporary)
        tree = work / 'root'
        stage(output / 'A7C2Tools', tree)
        (tree / 'usr/lib/a7c2-tools/BUILD-INFO.json').write_text(json.dumps(dict(
            version=version, revision=revision, architecture=rpm_arch,
            minimum_glibc=glibc_version, local_test_build=local), indent=2) + '\n')
        control = tree / 'DEBIAN'
        control.mkdir()
        (control / 'control').write_text(
            f'Package: a7c2-tools\nVersion: {version}-{revision}\nArchitecture: {deb_arch}\n'
            'Maintainer: A7C II Tools contributors\nSection: graphics\nPriority: optional\n'
            f'Depends: libc6 (>= {glibc_version}), libgl1, libegl1, libxkbcommon0, libxkbcommon-x11-0, '
            'libxcb1, libxcb-cursor0, libxcb-icccm4, libxcb-keysyms1, libxcb-image0, '
            'libxcb-render-util0, libxcb-xinerama0, libxcb-randr0, libxcb-shape0, '
            'libxcb-xfixes0, libfontconfig1, libdbus-1-3, udisks2, perl\n'
            'Description: Sony A7C II desktop and command-line tools\n'
            ' Linux adaptation for ILCE-7CM2 firmware 2.01.\n')
        deb = output / f'A7C2Tools-{version}-{revision}-Linux-{deb_arch}.deb'
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(tree), str(deb)], check=True)
        targets.append(deb)
        shutil.rmtree(control)
        spec = work / 'a7c2-tools.spec'
        spec.write_text(f'''Name: a7c2-tools
Version: {version}
Release: {revision}
Summary: Sony A7C II desktop and command-line tools
License: MIT
URL: https://github.com/QAQLeonard/a7c2-fl23-research
BuildArch: {rpm_arch}
AutoReqProv: no
Requires: glibc >= {glibc_version}, libglvnd-glx, libglvnd-egl, libxkbcommon, libxkbcommon-x11
Requires: libxcb, xcb-util-cursor, xcb-util-wm, xcb-util-keysyms, xcb-util-image, xcb-util-renderutil
Requires: fontconfig, dbus-libs, udisks2, perl
%description
Linux adaptation for ILCE-7CM2 firmware 2.01, including desktop and CLI.
%prep
%build
%install
mkdir -p "%{{buildroot}}"
cp -a "{tree}/usr" "%{{buildroot}}/"
%files
/usr/lib/a7c2-tools
/usr/bin/A7C2Tools
/usr/share/applications/{APP_ID}.desktop
/usr/share/icons/hicolor/scalable/apps/{APP_ID}.svg
/usr/share/a7c2-tools
''')
        subprocess.run(['rpmbuild', '-bb', '--define', '_topdir ' + str(work / 'rpm'),
                        '--define', '_tmppath ' + str(work), '--define', '_build_id_links none', '--define', '__os_install_post %{nil}',
                        '--define', 'debug_package %{nil}', '--define', '_binary_payload w6.zstdio', str(spec)], check=True)
        rpm = output / f'A7C2Tools-{version}-{revision}-Linux-{rpm_arch}.rpm'
        built, = (work / 'rpm/RPMS').rglob('*.rpm')
        shutil.copy2(built, rpm)
        targets.append(rpm)
        shutil.copy2(ASSETS / (APP_ID + '.desktop'), tree / (APP_ID + '.desktop'))
        shutil.copy2(ASSETS / (APP_ID + '.svg'), tree / (APP_ID + '.svg'))
        launcher = tree / 'AppRun'
        launcher.write_text('#!/bin/sh\nappdir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
                            'exec "$appdir/usr/lib/a7c2-tools/A7C2Tools" "$@"\n')
        launcher.chmod(0o755)
        appimage = output / f'A7C2Tools-{version}-{revision}-Linux-{rpm_arch}.AppImage'
        env = dict(os.environ, ARCH=rpm_arch, APPIMAGE_EXTRACT_AND_RUN='1')
        subprocess.run([appimagetool, str(tree), str(appimage)], env=env, check=True)
        targets.append(appimage)
    sums = output / f'A7C2Tools-{version}-{revision}-Linux-{rpm_arch}.sha256'
    lines = []
    for path in targets:
        with path.open('rb') as stream:
            lines.append(hashlib.file_digest(stream, 'sha256').hexdigest() + '  ' + path.name + '\n')
    sums.write_text(''.join(lines))
    return targets
