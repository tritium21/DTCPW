import requests
import platform
import importlib.resources


def main():
    fs = importlib.resources.files(__package__)
    print((fs / 'data.txt').read_text())
    print(platform.architecture())
    print(platform.python_version())
    print(requests.__version__)
    print("Hello World")


def gui():
    import tkinter
    root = tkinter.Tk()
    root.mainloop()
