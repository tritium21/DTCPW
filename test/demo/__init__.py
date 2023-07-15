import requests
import platform


def main():
    print(platform.architecture())
    print(platform.python_version())
    print(requests.__version__)
    print("Hello World")


def gui():
    import tkinter
    root = tkinter.Tk()
    root.mainloop()
