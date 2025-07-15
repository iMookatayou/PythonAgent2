from pystray import Icon, MenuItem as item, Menu
from PIL import Image
import threading
import os
import sys

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def start_tray(on_exit_callback=None):
    def on_exit(icon, item):
        icon.stop()
        if on_exit_callback:
            on_exit_callback()
        # ปิดโปรแกรมจริง (หยุด main thread ด้วย)
        os._exit(0)  # ← หายจาก Task Manager ทันที

    icon = Icon("MyTrayApp")

    icon_path = resource_path('credit-card.ico')
    icon.icon = Image.open(icon_path)

    icon.title = "My Tray App"
    icon.menu = Menu(
        item("ออก", on_exit)
    )
    icon.run_detached()
