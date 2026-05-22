"""PyInstaller runtime hook: 确保 torch DLL 优先搜索。

避免 WinError 1114 — torch 的 c10.dll 与 PyQt5 Qt DLL 冲突。
将 torch/lib 加入 DLL 搜索路径，确保 torch 初始化时找到正确的依赖。
"""
import sys
import os

if getattr(sys, 'frozen', False):
    torch_lib = os.path.join(sys._MEIPASS, 'torch', 'lib')
    if os.path.isdir(torch_lib):
        os.environ['PATH'] = torch_lib + os.pathsep + os.environ.get('PATH', '')
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(torch_lib)
            except OSError:
                pass
