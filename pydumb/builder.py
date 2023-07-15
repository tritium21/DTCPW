# Copyright 2023 Alex Walters, all rights reserved
# I intend to make this open source, eventually... but its
# still kinda janky (and needs a UI yet), and I hope the
# copyright will scare you into not using it
import pathlib
import shutil
import subprocess
import sys
import tomllib
import urllib.parse
import urllib.request
import zipfile

import distlib.scripts

import pydumb.util


def _get_launcher(self, kind):
    # Needed to override the internals to allow control over arch
    if self._machine == 'amd64':
        bits = '64'
    else:
        bits = '32'
    kind = 't'
    if self.executable == 'pythonw.exe':
        kind = 'w'
    platform_suffix = ''
    name = '%s%s%s.exe' % (kind, bits, platform_suffix)
    distlib_package = distlib.scripts.__name__.rsplit('.', 1)[0]
    resource = distlib.scripts.finder(distlib_package).find(name)
    if not resource:
        msg = ('Unable to find resource %s in package %s' % (name, distlib_package))
        raise ValueError(msg)
    return resource.bytes


distlib.scripts.ScriptMaker._get_launcher = _get_launcher


class Builder:
    def __init__(
        self,
        name,
        root,
        files,
        version=None,
        dependencies=None,
        entrypoints=None,
        machine=pydumb.util.this_machine()[0],
        py_version=pydumb.util.this_machine()[1],
        need_tkinter=False,
    ):
        self.name = name
        self.entrypoints = entrypoints
        self.machine = machine
        self.version = version
        self.py_version = py_version
        self.need_tkinter = need_tkinter
        self.root = pathlib.Path(root).resolve()
        self._build_path = self.root / 'build'
        self._cache_path = self.root / '__cache__'
        self._output_path = self._build_path / self.name
        self._final_path = self.root / 'dist' / f"{self.name}{'' if self.version is None else '-' + self.version}"
        self.dependencies = [] if dependencies is None else dependencies
        self.files = files
        self._rh_path = self._cache_path / 'resourcehacker'
        self._wix_path = self._cache_path / 'wix'

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
        opts['dependencies'] = project.get('dependencies', [])
        opts['files'] = data['tool']['pydumb'].get('src', [])
        opts['need_tkinter'] = data['tool']['pydumb'].get('need_tkinter', False)
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
            pydumb.util.fetch(url, file_path)
        return file_path

    def _download_python(self):
        url = f"https://www.python.org/ftp/python/{self.py_version}/python-{self.py_version}-embed-{self.machine}.zip"
        return self._download_item(url)

    def _download_wix(self):
        url = "https://github.com/wixtoolset/wix3/releases/download/wix3112rtm/wix311-binaries.zip"
        return self._download_item(url)

    def _download_python_installer(self):
        url = (
            f"https://www.python.org/ftp/python/{self.py_version}/python-{self.py_version}"
            f"{'-' + self.machine if self.machine != 'win32' else ''}.exe"
        )
        return self._download_item(url)

    def _download_resource_hacker(self):
        url = "http://www.angusj.com/resourcehacker/resource_hacker.zip"
        return self._download_item(url)

    def _extract_wix(self, path):
        with zipfile.ZipFile(path) as zf:
            zf.extractall(self._wix_path)

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
            shutil.copytree(entry, self._output_path / entry.name)

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
            sp, icon = pydumb.util.split_icon(spec)
            exes = sm.make(sp)
            self._add_icon(exes, icon)
            files.extend(exes)
        return files

    def _install_tkinter(self):
        if not self._wix_path.is_dir():
            wix = self._download_wix()
            self._extract_wix(wix)
            self._has_wix = True
        installer = self._download_python_installer()
        dark = self._wix_path / 'dark.exe'
        extract_build = self._cache_path / 'installer_extract'
        tcltk_build = self._cache_path / 'tcltk'
        tcltk_msi = extract_build / 'AttachedContainer' / 'tcltk.msi'
        subprocess.run([dark, installer, '-x', extract_build])
        subprocess.run(['msiexec', '/a', tcltk_msi, '/qn', f'TARGETDIR={tcltk_build}'])
        for path in (tcltk_build / 'DLLs').iterdir():
            shutil.copy(path, self._output_path)
        shutil.copytree((tcltk_build / 'Lib' / 'tkinter'), (self._output_path / 'tkinter'))
        shutil.copytree((tcltk_build / 'Lib' / 'idlelib'), (self._output_path / 'idlelib'))
        shutil.copytree((tcltk_build / 'tcl'), (self._output_path / 'tcl'))

    def _add_icon(self, exes, icon):
        if not icon:
            return
        if not self._rh_path.is_dir():
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
        if self.machine != pydumb.util.this_machine()[0]:
            only_bin = True
            arch = 'win-amd64' if self.machine == 'amd64' else 'win32'
            args.extend(['--platform', arch])
        if self.py_version != pydumb.util.this_machine()[1]:
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
        torm.extend(self._output_path.rglob('__pycache__'))
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

    def _clear_build(self):
        if self._build_path.exists():
            shutil.rmtree(self._build_path)

    def make_bundle(self, compile=True, optimize=1, release=True, make_zip=True):
        self._clear_build()
        python = self._download_python()
        self._extract_python(python)
        self._install_dependencies()
        if self.need_tkinter:
            self._install_tkinter()
        self._copy_source()
        self._make_entrypoints()
        if compile:
            self._compile(optimize=optimize)
        self._clean_output(source_too=compile)
        if release:
            self._release(make_zip=make_zip)
