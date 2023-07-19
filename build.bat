@echo off
if exist env\Scripts\python.exe (
    env\Scripts\python.exe -m build -w -C="--build-option=--plat win32"
    env\Scripts\python.exe -m build -w -C="--build-option=--plat win_amd64"
    env\Scripts\python.exe -m build -s
) else (
    echo Please run:
    echo    py -m venv env
    echo    env\Scripts\python.exe -m pip install --upgrade pip setuptools build
    echo And try again
)
