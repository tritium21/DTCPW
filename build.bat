@echo off
env\Scripts\python -m build -w -C="--build-option=--plat win32"
env\Scripts\python -m build -w -C="--build-option=--plat win_amd64"
env\Scripts\python -m build -s
