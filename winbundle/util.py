import pathlib
import platform
import re
import urllib.request


def split_icon(spec):
    result = re.split(r"\s*\[([^\]]+)\]", spec)
    if len(result) == 1:
        return spec, None
    cmd = result[0]
    flags = dict(x.partition('=')[::2] for x in re.split(r",\s*", result[1]))
    icon = flags.pop('icon', None)
    if not icon:
        return spec, None
    if flags:
        newflags = [f"{k}={v}" if v else k for k, v in flags.items()]
        return f"{cmd} [{','.join(newflags)}]", icon
    return cmd, icon


def this_machine():
    return ('amd64' if platform.architecture()[0] == '64bit' else 'win32'), platform.python_version()


def fetch(url, target):
    target = pathlib.Path(target).resolve()
    if target.is_file():
        return
    with urllib.request.urlopen(url) as s:
        if s.code != 200:
            raise s
        target.write_bytes(s.read())
