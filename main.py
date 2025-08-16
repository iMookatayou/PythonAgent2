import tray_icon
import threading
import time
import os
import base64
from flask import Flask, request, Response, jsonify
from flask_cors import CORS
from ThaiCIDHelper import *
from DataThaiCID import *
import json
import re
from datetime import datetime
from smartcard.System import readers
from smartcard.Exceptions import CardConnectionException, NoCardException

# === Flask Setup ===
app = Flask(__name__)
CORS(app)
stop_flag = False

# === Utils ===
def calculate_age(thai_date_str: str):
    try:
        day, month, year_th = map(int, thai_date_str.split('/'))
        year = year_th - 543 if year_th > 2400 else year_th
        birth_date = datetime(year, month, day)
        today = datetime.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except:
        return None

def convert_birth_for_input(thai_date_str: str):
    try:
        day, month, year_th = map(int, thai_date_str.split('/'))
        year = year_th - 543 if year_th > 2400 else year_th
        return f"{year:04d}-{month:02d}-{day:02d}"
    except:
        return ""

def parse_address(raw_str: str):
    """ตัดที่อยู่เป็นส่วนๆ จากสตริงเต็ม"""
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
        # บ้านเลขที่
        m = re.search(r"^\s*([\d/]+)", raw_str)
        if m:
            addr["HouseNo"] = m.group(1)
        # หมู่ (หมู่ที่ หรือ หมู่)
        m = re.search(r"หมู่(?:ที่)?\s*(\d+)", raw_str)
        if m:
            addr["Moo"] = m.group(1)
        # ตำบล
        m = re.search(r"ตำบล([\u0E00-\u0E7Fa-zA-Z0-9]+)", raw_str)
        if m:
            addr["Tumbol"] = m.group(1)
        # อำเภอ
        m = re.search(r"อำเภอ([\u0E00-\u0E7Fa-zA-Z0-9]+)", raw_str)
        if m:
            addr["Amphur"] = m.group(1)
        # จังหวัด
        m = re.search(r"จังหวัด([\u0E00-\u0E7Fa-zA-Z0-9]+)", raw_str)
        if m:
            addr["Province"] = m.group(1)
    except Exception as e:
        print("parse_address error:", e)
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

# === JSONP Endpoint ===
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

        # ชื่อไทย
        full_th = raw.get("FULLNAME-TH", "").strip()
        parts_th = full_th.split(" ")
        title_name_th, first_name_th, last_name_th = "", "", ""
        if len(parts_th) == 3:
            title_name_th, first_name_th, last_name_th = parts_th
        elif len(parts_th) == 2:
            if parts_th[0].startswith("นาย"):
                title_name_th = "นาย"
                first_name_th = parts_th[0].replace("นาย", "", 1)
            elif parts_th[0].startswith("นางสาว"):
                title_name_th = "นางสาว"
                first_name_th = parts_th[0].replace("นางสาว", "", 1)
            elif parts_th[0].startswith("นาง"):
                title_name_th = "นาง"
                first_name_th = parts_th[0].replace("นาง", "", 1)
            else:
                first_name_th = parts_th[0]
            last_name_th = parts_th[1]
        else:
            first_name_th = full_th

        # ภาษาอังกฤษ
        full_en = raw.get("FULLNAME-EN", "").strip()
        parts_en = full_en.split(" ")
        title_name_en = parts_en[0] if len(parts_en) > 0 else ""
        first_name_en = parts_en[1] if len(parts_en) > 1 else ""
        middle_name_en = parts_en[2] if len(parts_en) > 2 else ""
        last_name_en = parts_en[3] if len(parts_en) > 3 else ""

        # วันเกิด
        birth_raw = raw.get("BIRTH", "")
        age = calculate_age(birth_raw)
        birth_for_input = convert_birth_for_input(birth_raw)

        # ที่อยู่
        addr = parse_address(raw.get("ADDRESS", ""))

        if section1:
            result.update({
                "CitizenID": raw.get("CID"),
                "Gender": "1" if raw.get("GENDER") == "ชาย" else "2" if raw.get("GENDER") == "หญิง" else "0",
                "BirthDate": birth_for_input,
                "Age": age,
                "IssueDate": raw.get("ISSUE"),
                "ExpireDate": raw.get("EXPIRE"),
                "Issuer": raw.get("ISSUER"),
                "CardNumber": raw.get("DOCNO")
            })
        if section2a:
            result.update(addr)
        if section2c:
            result.update({
                "TitleNameTh": title_name_th,
                "FirstNameTh": first_name_th,
                "LastNameTh": last_name_th,
                "TitleNameEn": title_name_en,
                "FirstNameEn": first_name_en,
                "MiddleNameEn": middle_name_en,
                "LastNameEn": last_name_en
            })

        if "PHOTO" in raw and raw["PHOTO"]:
            try:
                photo_b64 = base64.b64encode(raw["PHOTO"]).decode('utf-8')
                result["PhotoBase64"] = f"data:image/jpeg;base64,{photo_b64}"
            except Exception as e:
                print("⚠️ Error converting photo:", e)
                result["PhotoBase64"] = ""

        json_str = json.dumps(result, ensure_ascii=False)
        return Response(f"/**/{callback}({json_str});", mimetype='application/javascript; charset=utf-8')

    except Exception as e:
        return Response(f"/**/{callback}({json.dumps({'error': str(e)})});", mimetype='application/javascript')

# === JSON API (ใหม่) ===
@app.route('/get_cid_data_json', methods=['GET'])
def get_cid_data_json():
    present, err = is_card_present()
    if not present:
        return jsonify({'card_present': False, 'error': err or 'no_card'})

    try:
        reader = ThaiCIDHelper(APDU_SELECT, APDU_THAI_CARD)
        res = reader.connectReader(0)
        if not res[1]:
            return jsonify({'error': reader.lastError})

        reader.readData()
        raw = reader.cardData

        # ชื่อไทย
        full_th = raw.get("FULLNAME-TH", "").strip()
        parts_th = full_th.split(" ")
        title_name_th, first_name_th, last_name_th = "", "", ""
        if len(parts_th) == 3:
            title_name_th, first_name_th, last_name_th = parts_th
        elif len(parts_th) == 2:
            if parts_th[0].startswith("นาย"):
                title_name_th = "นาย"
                first_name_th = parts_th[0].replace("นาย", "", 1)
            elif parts_th[0].startswith("นางสาว"):
                title_name_th = "นางสาว"
                first_name_th = parts_th[0].replace("นางสาว", "", 1)
            elif parts_th[0].startswith("นาง"):
                title_name_th = "นาง"
                first_name_th = parts_th[0].replace("นาง", "", 1)
            else:
                first_name_th = parts_th[0]
            last_name_th = parts_th[1]
        else:
            first_name_th = full_th

        # ภาษาอังกฤษ
        full_en = raw.get("FULLNAME-EN", "").strip()
        parts_en = full_en.split(" ")
        title_name_en = parts_en[0] if len(parts_en) > 0 else ""
        first_name_en = parts_en[1] if len(parts_en) > 1 else ""
        middle_name_en = parts_en[2] if len(parts_en) > 2 else ""
        last_name_en = parts_en[3] if len(parts_en) > 3 else ""

        # วันเกิด
        birth_raw = raw.get("BIRTH", "")
        age = calculate_age(birth_raw)
        birth_for_input = convert_birth_for_input(birth_raw)

        # ที่อยู่
        addr = parse_address(raw.get("ADDRESS", ""))

        result = {
            "card_present": True,
            "CitizenID": raw.get("CID"),
            "Gender": "1" if raw.get("GENDER") == "ชาย" else "2" if raw.get("GENDER") == "หญิง" else "0",
            "BirthDate": birth_for_input,
            "Age": age,
            "IssueDate": raw.get("ISSUE"),
            "ExpireDate": raw.get("EXPIRE"),
            "Issuer": raw.get("ISSUER"),
            "CardNumber": raw.get("DOCNO"),
            "TitleNameTh": title_name_th,
            "FirstNameTh": first_name_th,
            "LastNameTh": last_name_th,
            "TitleNameEn": title_name_en,
            "FirstNameEn": first_name_en,
            "MiddleNameEn": middle_name_en,
            "LastNameEn": last_name_en,
            "HouseNo": addr.get("HouseNo"),
            "Moo": addr.get("Moo"),
            "Tumbol": addr.get("Tumbol"),
            "Amphur": addr.get("Amphur"),
            "Province": addr.get("Province")
        }

        if "PHOTO" in raw and raw["PHOTO"]:
            try:
                photo_b64 = base64.b64encode(raw["PHOTO"]).decode('utf-8')
                result["PhotoBase64"] = f"data:image/jpeg;base64,{photo_b64}"
            except Exception as e:
                print("⚠️ Error converting photo:", e)
                result["PhotoBase64"] = ""

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'ไม่สามารถอ่านบัตร: {str(e)}'})

# === Main Run ===
def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)

def clean_exit():
    print("🔴 หยุดระบบแล้ว กำลังปิด...")
    time.sleep(1)
    os._exit(0)

def main_logic():
    print("🟢 ระบบกำลังทำงานครั้งเดียว...")
    time.sleep(1)
    print("✅ ทำงานเสร็จแล้ว main_logic จบ")

if __name__ == "__main__":
    tray_icon.start_tray(on_exit_callback=clean_exit)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    main_logic()
