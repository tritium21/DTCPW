import pathlib

from construct import Struct, Int16sl, Int8sl, Int32sl
from win32ctypes.pywin32 import win32api

RT_ICON = 3
RT_GROUP_ICON = 14

ICONDIRHEADER = Struct(
    "idReserved" / Int16sl,
    "idType" / Int16sl,
    "idCount" / Int16sl,
)

ICONDIRENTRY = Struct(
    "bWidth" / Int8sl,
    "bHeight" / Int8sl,
    "bColorCount" / Int8sl,
    "bReserved" / Int8sl,
    "wPlanes" / Int16sl,
    "wBitCount" / Int16sl,
    "dwBytesInRes" / Int32sl,
    "dwImageOffset" / Int32sl,
)

GRPICONDIRENTRY = Struct(
    "bWidth" / Int8sl,
    "bHeight" / Int8sl,
    "bColorCount" / Int8sl,
    "bReserved" / Int8sl,
    "wPlanes" / Int16sl,
    "wBitCount" / Int16sl,
    "dwBytesInRes" / Int32sl,
    "nID" / Int16sl,
)


class IconFile:
    def __init__(self, path):
        path = pathlib.Path(path).resolve()
        file = path.open("rb")
        self.entries = []
        self.images = []
        with file:
            self.header = ICONDIRHEADER.parse(file.read(ICONDIRHEADER.sizeof()))
            self.entries.extend(
                ICONDIRENTRY.parse(file.read(ICONDIRENTRY.sizeof()))
                for _ in range(self.header.idCount)
            )
            for e in self.entries:
                file.seek(e.dwImageOffset, 0)
                self.images.append(file.read(e.dwBytesInRes))

    def group_icon_header(self):
        return ICONDIRHEADER.build(self.header)

    def group_icon_header_entires(self, id=1):
        return b''.join(
            GRPICONDIRENTRY.build(dict((*entry.items(), ('nID', id))))
            for entry in self.entries
        )


def apply_icon(dstpath, srcpath):
    icon = IconFile(srcpath)
    hdst = win32api.BeginUpdateResource(str(dstpath), 0)
    data = icon.group_icon_header()
    data = data + icon.group_icon_header_entires(1)
    win32api.UpdateResource(hdst, RT_GROUP_ICON, 0, data)
    for data in icon.images:
        win32api.UpdateResource(hdst, RT_ICON, 1, data)
    win32api.EndUpdateResource(hdst, 0)


if __name__ == "__main__":
    import sys

    dstpath = sys.argv[1]
    srcpath = sys.argv[2]
    apply_icon(dstpath, srcpath)
