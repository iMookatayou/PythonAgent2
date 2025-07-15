import tray_icon
import threading
import time
import os
import sys
from flask import Flask, request, Response
from ThaiCIDHelper import *
from DataThaiCID import *
import json
import re
from datetime import datetime
from smartcard.System import readers
from smartcard.Exceptions import CardConnectionException, NoCardException

# === Flask Setup ===
app = Flask(__name__)
stop_flag = False  # สำหรับควบคุมการทำงาน loop หลัก

def calculate_age(thai_date_str):
    try:
        day, month, year_th = map(int, thai_date_str.split('/'))
        year = year_th - 543 if year_th > 2400 else year_th
        birth_date = datetime(year, month, day)
        today = datetime.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except:
        return None

def parse_address(raw_str):
    addr = {
        "Full": raw_str,
        "HouseNo": "",
        "Moo": "",
        "Tumbol": "",
        "Amphur": "",
        "Province": ""
    }

    if not raw_str:
        return addr

    try:
        if match := re.search(r"^\s*(\S+)", raw_str):
            addr["HouseNo"] = match.group(1)
        if match := re.search(r"หมู่\s*(\d+)", raw_str):
            addr["Moo"] = match.group(1)
        if match := re.search(r"ต\.(\S+)", raw_str):
            addr["Tumbol"] = match.group(1)
        if match := re.search(r"อ\.(\S+)", raw_str):
            addr["Amphur"] = match.group(1)
        if match := re.search(r"จ\.(\S+)", raw_str):
            addr["Province"] = match.group(1)
    except:
        pass

    return addr

def is_card_present():
    try:
        reader_list = readers()
        if len(reader_list) == 0:
            return False, "ไม่พบเครื่องอ่านบัตร"

        reader_hw = reader_list[0]
        connection = reader_hw.createConnection()
        connection.connect()
        connection.disconnect()
        return True, None
    except (CardConnectionException, NoCardException):
        return False, None
    except Exception as e:
        return False, str(e)

@app.route('/get_cid_data', methods=['GET'])
def get_cid_data():
    callback = request.args.get('callback', 'callback')
    section1 = request.args.get('section1') == 'true'
    section2a = request.args.get('section2a') == 'true'
    section2c = request.args.get('section2c') == 'true'

    present, err = is_card_present()
    if not present:
        if err:
            return Response(f"/**/{callback}({json.dumps({'error': err})});", mimetype='application/javascript')
        else:
            return Response(f"/**/{callback}({json.dumps({'card_present': False})});", mimetype='application/javascript')

    try:
        reader = ThaiCIDHelper(APDU_SELECT, APDU_THAI_CARD)
        res = reader.connectReader(0)
        if not res[1]:
            return Response(f"/**/{callback}({json.dumps({'error': reader.lastError})});", mimetype='application/javascript')

        reader.readData()
        raw = reader.cardData

        result = {"card_present": True}
        name_th = raw.get("FULLNAME-TH", "").strip().split(" ", 2)
        name_en = raw.get("FULLNAME-EN", "").strip().split(" ", 3)

        birth = raw.get("BIRTH", "")
        age = calculate_age(birth)
        addr = parse_address(raw.get("ADDRESS", ""))

        if section1:
            result.update({
                "CitizenID": raw.get("CID"),
                "Gender": "1" if raw.get("GENDER") == "ชาย" else "2" if raw.get("GENDER") == "หญิง" else "0",
                "BirthDate": birth,
                "Age": age,
                "IssueDate": raw.get("ISSUE"),
                "ExpireDate": raw.get("EXPIRE"),
                "Issuer": raw.get("ISSUER"),
                "CardNumber": raw.get("DOCNO")
            })

        if section2a:
            result["Address"] = addr

        if section2c:
            result.update({
                "TitleNameTh": name_th[0] if len(name_th) > 0 else "",
                "FirstNameTh": name_th[1] if len(name_th) > 1 else "",
                "LastNameTh": name_th[2] if len(name_th) > 2 else "",
                "TitleNameEn": name_en[0] if len(name_en) > 0 else "",
                "FirstNameEn": name_en[1] if len(name_en) > 1 else "",
                "MiddleNameEn": name_en[2] if len(name_en) > 2 else "",
                "LastNameEn": name_en[3] if len(name_en) > 3 else ""
            })

        json_str = json.dumps(result, ensure_ascii=True)
        return Response(f"/**/{callback}({json_str});", mimetype='application/javascript; charset=utf-8')

    except Exception as e:
        error_msg = {'error': f'ไม่สามารถอ่านบัตร: {str(e)}'}
        return Response(f"/**/{callback}({json.dumps(error_msg)});", mimetype='application/javascript')

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)

def clean_exit():
    print("🔴 หยุดระบบแล้ว กำลังปิด...")
    time.sleep(1)
    os._exit(0)  # ปิด process ทั้งหมดทันที

def main_logic():
    print("🟢 ระบบกำลังทำงานครั้งเดียว...")
    # ✅ เพิ่ม logic ที่ต้องทำตรงนี้ เช่น โหลด config, เตรียมตัวอ่านบัตร ฯลฯ
    # ไม่วน loop แล้ว
    time.sleep(1)  # รอเล็กน้อยเพื่อแสดงผล
    print("✅ ทำงานเสร็จแล้ว main_logic จบ")

if __name__ == "__main__":
    tray_icon.start_tray(on_exit_callback=clean_exit)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    main_logic()  # 🔁 ทำงานครั้งเดียว ไม่วน
