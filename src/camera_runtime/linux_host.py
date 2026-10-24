"""Linux USB ownership, used only by explicit camera operations."""
import os
from pathlib import Path
import subprocess


def camera_path(device):
    for entry in Path('/sys/bus/usb/devices').iterdir():
        if not (entry / 'busnum').is_file():
            continue
        try:
            identity = tuple(int((entry / name).read_text(), base) for name, base in
                             (('busnum', 10), ('devnum', 10), ('idVendor', 16), ('idProduct', 16)))
        except FileNotFoundError:
            continue
        if identity == (device.bus, device.address, 0x054c, device.idProduct):
            if device.idVendor != 0x054c or device.idProduct not in (0x0e8a, 0x0336):
                break
            return entry.resolve()
    raise RuntimeError('Camera USB identity changed; stopped before claiming its interface')


def mounted_devices(camera):
    devices = set()
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        block = Path('/sys/dev/block') / line.split()[2]
        if block.exists() and block.resolve().is_relative_to(camera):
            devices.add('/dev/' + block.resolve().name)
    return devices


def claim_camera_interface(device):
    import usb.util
    camera = camera_path(device)
    env = os.environ.copy()
    # Frozen Python's loader paths must not leak into system utilities.
    original = env.pop('LD_LIBRARY_PATH_ORIG', None)
    env.pop('LD_LIBRARY_PATH', None)
    if original:
        env['LD_LIBRARY_PATH'] = original
    remaining = mounted_devices(camera)
    for block in sorted(remaining):
        if camera_path(device) != camera or mounted_devices(camera) != remaining:
            raise RuntimeError('Camera storage changed before unmount; no USB claim attempted')
        result = subprocess.run(['udisksctl', 'unmount', '--no-user-interaction', '-b', block],
                                capture_output=True, text=True, timeout=30, env=env)
        if result.returncode:
            raise RuntimeError('Cannot unmount camera storage. Close file managers and photo applications: '
                               + result.stderr.strip())
        remaining.remove(block)
    if camera_path(device) != camera or mounted_devices(camera):
        raise RuntimeError('Camera storage changed or is still mounted; no USB claim attempted')
    detached = False
    try:
        interface = device.get_active_configuration()[(0, 0)]
        if device.idProduct == 0x0e8a and (
                interface.bInterfaceClass, interface.bInterfaceSubClass,
                interface.bInterfaceProtocol) != (8, 6, 0x50):
            raise RuntimeError('Expected camera Mass Storage interface')
        if device.is_kernel_driver_active(0):
            device.detach_kernel_driver(0)
            detached = True
        usb.util.claim_interface(device, 0)
    except BaseException:
        try:
            if detached:
                device.attach_kernel_driver(0)
        finally:
            usb.util.dispose_resources(device)
        raise
