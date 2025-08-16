from pystray import Icon, MenuItem as item, Menu
from PIL import Image
import os
import sys

# ฟังก์ชันช่วยหา path ของไฟล์ ico ที่ถูกต้อง (รองรับทั้งตอน run ปกติและตอน build exe)
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def start_tray(on_exit_callback=None):
    def on_exit(icon, menu_item):
        icon.stop()
        if on_exit_callback:
            on_exit_callback()
        os._exit(0)  # ปิดโปรแกรมทันที

    # กำหนด path ไฟล์ ico
    icon_path = resource_path("Card-Reader-Api-Icon.ico")
    # โหลด icon ด้วย PIL.Image
    image = Image.open(icon_path)

    # สร้าง tray icon โดยใช้ pystray.Icon
    tray = Icon(
        "Python Agent",
        image,  # ภาพ icon
        "Python Agent",  # title
        menu=Menu(
            item("ออก", on_exit)
        )
    )

    tray.run_detached()  # รันแบบไม่บล็อค thread หลัก
