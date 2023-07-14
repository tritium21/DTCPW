# Copyright 2023 Alex Walters, all rights reserved
# I intend to make this open source, eventually... but its
# still kinda janky (and needs a UI yet), and I hope the
# copyright will scare you into not using it
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.parse
import urllib.request
import zipfile

import distlib.scripts


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


def _get_launcher(self, kind):
    # Needed to override the internals to allow control over arch
    if self._machine == 'amd64':
        bits = '64'
    else:
        bits = '32'
    platform_suffix = ''
    name = '%s%s%s.exe' % (kind, bits, platform_suffix)
    distlib_package = distlib.scripts.__name__.rsplit('.', 1)[0]
    resource = distlib.scripts.finder(distlib_package).find(name)
    if not resource:
        msg = ('Unable to find resource %s in package %s' % (name, distlib_package))
        raise ValueError(msg)
    return resource.bytes


distlib.scripts.ScriptMaker._get_launcher = _get_launcher


def this_machine():
    return 'amd64' if platform.architecture()[0] == '64bit' else 'win32'


def fetch(url, target):
    target = pathlib.Path(target).resolve()
    if target.is_file():
        return
    with urllib.request.urlopen(url) as s:
        if s.code != 200:
            raise s
        target.write_bytes(s.read())


class Builder:
    def __init__(
        self,
        name,
        root,
        files,
        version=None,
        dependencies=None,
        entrypoints=None,
        machine=this_machine(),
        py_version=platform.python_version()
    ):
        self.name = name
        self.entrypoints = entrypoints
        self.machine = machine
        self.version = version
        self.py_version = py_version
        self.root = pathlib.Path(root).resolve()
        self._build_path = self.root / 'build'
        self._cache_path = self._build_path / 'cache'
        self._rh_path = self._cache_path / 'resourcehacker'
        self._output_path = self._build_path / self.name
        self._final_path = self.root / 'release' / f"{self.name}{'' if self.version is None else '-' + self.version}"
        self.dependencies = [] if dependencies is None else dependencies
        self.files = files
        self._has_rh = False

    @classmethod
    def from_path(cls, path):
        path = pathlib.Path(path).resolve()
        if not path.is_file():
            raise ValueError
        data = tomllib.loads(path.read_text(encoding='utf-8'))
        project = data['project']
        opts = {}
        opts['root'] = path.parent
        opts['name'] = project['name']
        opts['entrypoints'] = {
            'con': [f"{k} = {v}" for k, v in project.get('scripts', {}).items()],
            'gui': [f"{k} = {v}" for k, v in project.get('gui-scripts', {}).items()],
        }
        opts['dependencies'] = project['dependencies']
        opts['files'] = data['tool']['pydumb']['src']
        version = project['version']
        if version:
            opts['version'] = version
        machine = data['tool']['pydumb'].get('machine', None)
        if machine:
            opts['machine'] = machine
        py_version = data['tool']['pydumb'].get('py_version', None)
        if py_version:
            opts['py_version'] = py_version
        return cls(**opts)

    def _download_item(self, url):
        file_name = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name
        file_path = self._cache_path / file_name
        if not file_path.exists():
            self._cache_path.mkdir(parents=True, exist_ok=True)
            fetch(url, file_path)
        return file_path

    def _download_python(self):
        url = f"https://www.python.org/ftp/python/{self.py_version}/python-{self.py_version}-embed-{self.machine}.zip"
        return self._download_item(url)

    def _download_resource_hacker(self):
        url = "http://www.angusj.com/resourcehacker/resource_hacker.zip"
        return self._download_item(url)

    def _extract_resource_hacker(self, path):
        with zipfile.ZipFile(path) as zf:
            zf.extractall(self._rh_path)

    def _extract_python(self, path):
        if not self._output_path.exists():
            self._output_path.mkdir(exist_ok=True, parents=True)
            with zipfile.ZipFile(path) as zf:
                zf.extractall(self._output_path)

    def _copy_source(self):
        for entry in self.files:
            entry = (self.root / entry).resolve()
            if entry.is_file():
                shutil.copy2(entry, self._output_path)
                continue
            shutil.copytree(entry, self._output_path)

    def _make_entrypoints(self):
        sm = distlib.scripts.ScriptMaker(self.root, self._output_path, add_launchers=True)
        sm._machine = self.machine
        sm.variants = {''}
        specs = []
        specs.extend((x, 'python.exe') for x in self.entrypoints.get('con', []))
        specs.extend((x, 'pythonw.exe') for x in self.entrypoints.get('gui', []))
        files = []
        for spec, executable in specs:
            sm.executable = executable
            sp, icon = split_icon(spec)
            exes = sm.make(sp)
            self._add_icon(exes, icon)
            files.extend(exes)
        return files

    def _add_icon(self, exes, icon):
        if not icon:
            return
        if not self._has_rh:
            rh = self._download_resource_hacker()
            self._extract_resource_hacker(rh)
            self._has_rh = True
        icon = self.root / icon
        exes = [pathlib.Path(x).resolve() for x in exes]
        for exe in exes:
            subprocess.run([
                str(self._rh_path / 'ResourceHacker.exe'), '-open', str(exe), '-save', str(exe), '-action',
                'delete', '-mask', 'ICONGROUP,101,'
            ])
            subprocess.run([
                str(self._rh_path / 'ResourceHacker.exe'), '-open', str(exe), '-save', str(exe), '-action',
                'addoverwrite', '-res', str(icon), '-mask', 'ICONGROUP,MAINICON,'
            ])

    def _install_dependencies(self):
        args = [sys.executable, '-m', 'pip', 'install', '--target', str(self._output_path)]
        only_bin = False
        if self.machine != this_machine():
            only_bin = True
            arch = 'win-amd64' if self.machine == 'amd64' else 'win32'
            args.extend(['--platform', arch])
        if self.py_version != platform.version:
            only_bin = True
            args.extend(['--python-version', self.py_version])
        if only_bin:
            args.extend(['--only-binary=:all:'])
        args.extend(self.dependencies)
        subprocess.run(args)

    def _compile(self, optimize=-1):
        optimize = min(max(-1, optimize), 2)
        args = [
            str(self._output_path / 'python.exe'),
            '-m',
            'compileall',
            '-b',
            '-o',
            str(optimize),
            str(self._output_path)
        ]
        subprocess.run(args)

    def _clean_output(self, source_too=False):
        torm = []
        torm.extend(self._output_path.rglob('__pychache__'))
        if source_too:
            torm.extend(self._output_path.rglob('*.py'))
        torm.extend(self._output_path.glob('*.dist-info'))
        torm.append(self._output_path / 'bin')
        for path in torm:
            if not path.exists():
                continue
            if path.is_file():
                path.unlink()
                continue
            shutil.rmtree(path)

    def _release(self, make_zip=True):
        self._final_path.parent.mkdir(exist_ok=True, parents=True)
        if self._final_path.exists():
            shutil.rmtree(self._final_path, ignore_errors=True)
            self._final_path.with_suffix('.zip').unlink(missing_ok=True)
        shutil.copytree(self._output_path, self._final_path)
        if not make_zip:
            return
        shutil.make_archive(
            str(self._final_path),
            'zip',
            root_dir=str(self._final_path.parent),
            base_dir=str(self._final_path.name),
        )

    def make_bundle(self, compile=True, optimize=1, release=True, make_zip=True):
        python = self._download_python()
        self._extract_python(python)
        self._install_dependencies()
        self._copy_source()
        self._make_entrypoints()
        if compile:
            self._compile(optimize=optimize)
        self._clean_output(source_too=compile)
        if release:
            self._release(make_zip=make_zip)
