"""Packaged entry points for the existing command-line tools."""
from pathlib import Path
import runpy
import sys

COMMANDS = ('fl23', 'lut', 'recovery', 'shutter', 'vertical',
            'a7look_compile', 'a7look_write', 'raw_auto', 'raw_import')


def main(arguments):
    import argparse
    parser = argparse.ArgumentParser(prog='A7C2Tools --cli')
    parser.add_argument('tool', choices=COMMANDS)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(arguments)
    root = Path(__file__).resolve().parents[2]
    if args.tool == 'fl23':
        source = root / 'src/fl23/app.py'
        sys.path[:0] = [str(source.parent), str(root / 'src/camera_runtime/vendor')]
    else:
        source = root / (args.tool + '.py')
    sys.argv = [str(source), *args.arguments]
    if args.tool == 'fl23' and args.arguments and args.arguments[0] in ('check', 'backup', 'install', 'restore', 'verify'):
        sys.path.append(str(root / 'src/looks'))
        from looktool.devicelock import DeviceLock
        with DeviceLock():
            runpy.run_path(str(source), run_name='__main__')
    else:
        runpy.run_path(str(source), run_name='__main__')
    return 0
