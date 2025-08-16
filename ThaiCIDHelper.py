import time, codecs , subprocess, os   # 👈 เพิ่ม import os ไว้ใช้ลบไฟล์ชั่วคราว

# pyscard 2.0.7
from smartcard.System import readers
from smartcard.util import toHexString

from DataThaiCID  import *  # ต้องมีการนำเข้า APDU_DATA ที่ใช้ใน searchDATAValue
from imgToClipboard  import copyImageToClipboard

####- --------------------------------------------------
# Thai CID Smartcard Helper
####- --------------------------------------------------
class ThaiCIDHelper():
    
    def __init__(self,
                 apduSELECT = [0x00, 0xA4, 0x04, 0x00, 0x08],
                 apduTHCard = [0xA0, 0x00, 0x00, 0x00, 0x54, 0x48, 0x00, 0x01], 
                 showThaiDate=True):
        
        # Initialize
        self.cardReaderList = readers()  # PC/SC
        self.cardReader = None
        self.cardReaderIndex = -1
        self.apduSELECT  = apduSELECT
        self.apduTHCard = apduTHCard
        self.apduRequest = []
        self.ATR = ""
        self.showThaiDate = showThaiDate
        self.lastError = ""
        self.cardData = {}   # 👈 เพิ่มการกำหนดเริ่มต้นให้แน่ใจว่ามี cardData

        print(f'Reader: Available Count = {len(self.cardReaderList)}')

    def connectReader(self,index):
        """
            connectReader ติดต่อเครื่องอ่านบัตร \n
            พารามิเตอร์ : 
            index ลำดับของเครื่องอ่านบัตร \n
            Default 0 (ตัวที่ 1) ** ถ้ามี ** \n
            return >> Reader-connection , Connected Status
        """
        
        print(f'Reader: Select ... [{index}] = [{self.cardReaderList[index]}]')
        _HWcardReader = self.cardReaderList[index]
        _connected = False
        
        try: 
            # Create Connection
            self.cardReader = _HWcardReader.createConnection()
            self.cardReader.connect()                 
            self.cardReaderIndex = index
            
            _connected = True
            print(f'Reader: Connected ... [{self.cardReaderList[index]}]')
        
        except Exception as err:
            self.lastError = f'{err}'
            print(f'Connection : Error = {err}')
        
        if _connected == True:
            atr = self.cardReader.getATR()
            self.ATR = toHexString(atr)
            print(f"Reader: ATR = {self.ATR}")
            if (atr[0] == 0x3B & atr[1] == 0x67):
                self.apduRequest = [0x00, 0xc0, 0x00, 0x01]
            else:
                self.apduRequest = [0x00, 0xc0, 0x00, 0x00]
            return self.cardReader ,_connected

        return None, False
    
    def readData(self,readPhoto=True,
                 saveText = SaveType.FILE,
                 savePhoto: SaveType = SaveType.FILE):
        """
            readData อ่านข้อมูลจากบัตร ตาม apdu ที่กำหนด
        """
        start_time = time.time()
       
        data, sw1, sw2 = self.cardReader.transmit(self.apduSELECT + self.apduTHCard)
        print(f"Reader: Send `SELECT` Response = %02X %02X" % (sw1, sw2))

        responseJson = []
        _jsonThaiDesc, _Json4Dev, _JsonRawData = {}, {}, {}
        _textThaiDesc, _textJson = "", ""

        print("Reader: อ่านข้อมูล เริ่มแล้ว...")
        apduCount = len(APDU_DATA)
        for index, data in enumerate(APDU_DATA):
            _apdu = searchDATAValue('key', data['key'], 'apdu')
            print('Reader: อ่าน ', data['desc'])
            response = self.getValue(_apdu, data['type'])
            _jsonThaiDesc[data['desc']] = response[0]
            _Json4Dev[data['id']] = response[0]
            if index == (apduCount - 1):
                _textThaiDesc += f'"{index}":"{data["desc"]}={response[0]}"\n'
                _textJson += f'"{data["id"]}":"{response[0]}"\n'
            else:
                _textThaiDesc += f'"{index}":"{data["desc"]}={response[0]}",\n'
                _textJson += f'"{data["id"]}":"{response[0]}",\n'

        self.cardData = {
            'CID': _Json4Dev.get('CID'),
            'FULLNAME-TH': _Json4Dev.get('FULLNAME-TH'),
            'FULLNAME-EN': _Json4Dev.get('FULLNAME-EN'),
            'BIRTH': _Json4Dev.get('BIRTH'),
            'GENDER': _Json4Dev.get('GENDER'),
            'ISSUER': _Json4Dev.get('ISSUER'),
            'ISSUE': _Json4Dev.get('ISSUE'),
            'EXPIRE': _Json4Dev.get('EXPIRE'),
            'ADDRESS': _Json4Dev.get('ADDRESS'),
            'DOCNO': _Json4Dev.get('DOCNO'),
        }

        responseJson.append(_jsonThaiDesc)
        responseJson.append(_Json4Dev)

        if saveText == SaveType.CLIPBOARD:
            print("Reader: บันทึกข้อมูลข้อความ [ไปคลิปบอร์ด] ...")
            copyTextToClipboard(f'{_textThaiDesc}\n{_textJson}')

        if readPhoto:
            print("Reader: อ่าน  รูปภาพ...")
            photoBytes = bytearray()
            for data in APDU_PHOTO:
                _apdu = searchAPDUPhoto(data['key'])
                photoBytes += bytearray(self.getPhoto(_apdu))

            self.cardData['PHOTO'] = bytes(photoBytes)

            if savePhoto == SaveType.CLIPBOARD:
                print("Reader: บันทึกข้อมูลรูป [ไปคลิปบอร์ด] ...")
              
                temp_filename = "temp_photo.jpg" 
                with open(temp_filename, "wb") as f: 
                    f.write(self.cardData['PHOTO'])
                copyImageToClipboard(temp_filename) 
                os.remove(temp_filename)

        end_time = time.time()
        elapsed_time = end_time - start_time
        elapsed_str = time.strftime("%S.{}".format(str(elapsed_time % 1)[2:])[:6], time.gmtime(elapsed_time))
        print(f"Reader: อ่านข้อมูล เสร็จแล้ว... [{elapsed_str} ms]")

    # … ส่วนอื่น ๆ (getValue, getPhoto, encodeTextThai, textToThaiDate, ฯลฯ) ไม่ได้แก้ไข …

####- --------------------------------------------------    
#### getValue
####- --------------------------------------------------   

    def getValue(self,apdu,dataType):
        """
            getValue อ่านข้อมูลจากบัตร ตาม APDU ที่กำหนด \n
            พารามิเตอร์ : \n
            apdu คำสั่ง APDU ของฟิลด์ที่ต้องการอ่าน \n
            dataType ประเภทของข้อมูล เพื่อจัดรูปแบบตามต้องการ
        """
        
        #print(f"Reader: Send Command")
        _data, _sw1, sw2 = self.cardReader.transmit(apdu)
        #print(f"Reader: Card Response1 >> Size= {sw2} ")
        #ขอข้อมูล ขนาดที่บอกมา Size == sw2
        rawdata, _sw1 , _sw2 = self.cardReader.transmit(self.apduRequest + [sw2])
        #print(f"Reader: Card Response2 >> data")
        
        text = self.encodeTextThai(rawdata)
              
        if dataType == ThaiCIDDataType.ADDRESS:
            # ข้อมูลที่อยู่
            text = text.replace('#######',' ')
            text = text.replace('######',' ')
            text = text.replace('#####',' ')
            text = text.replace('####',' ')
            text = text.replace('###',' ')
            text = text.replace('##',' ')
            text = text.replace('#',' ')
            data = text
            
        elif dataType == ThaiCIDDataType.NAME:
            # ข้อมูลชื่อ-นามสกุล ไทย และ อังกฤษ
            text = text.replace('##',' ')
            text = text.replace('#','')
            data = text
            
        elif dataType == ThaiCIDDataType.DATE:
            # ปีพ.ศ. + เดือน + ปี  ระวังข้อมูลที่มีแต่ พ.ศ.
            if self.showThaiDate == True:
                # dd/mm/2567
                _date = textToThaiDate(text)
            else:    
                # 2024-mm-dd
                _date = textToEngDate(text)
            data = _date
            
        elif dataType == ThaiCIDDataType.GENDER:
            # '-' , 'ชาย' ,'หญิง'
            data = GENDER[int(text)]

        elif dataType == ThaiCIDDataType.RELIGION:
            # '-' , 'พุทธ' ,'อิสลาม'
            data = RELIGION[int(text)]
            
        elif dataType == ThaiCIDDataType.DOCNUMBER:
            # เลขใต้รูปภาพ
            data = setformatDocNumber(text)

        else:
            data = text
        
        return [data, rawdata]


    def getPhoto(self,apdu):
        """
            getPhoto อ่านข้อมูลรูปภาพจากบัตร ตาม APDU ที่กำหนด \n
            พารามิเตอร์ : \n
            apdu คำสั่ง APDU ของฟิลด์ที่ต้องการอ่าน \n
        """
                
        _ , _ , sw2 = self.cardReader.transmit(apdu)        
        #ขอข้อมูล ขนาดที่บอกมา Size == sw2        
        rawdata, _ , _ = self.cardReader.transmit(self.apduRequest + [sw2])

        return rawdata


    def encodeTextThai(self,data):

        # แปลงเป็นตัวอักษรไทย TIS-620
        result = bytes(data).decode('tis-620')

        # ตัดช่องว่าง trim
        return result.strip();

## External Method ##
def textToThaiDate(txt:str):
    # ปีพ.ศ. + เดือน + ปี 
    # บัตร คนมีปัญหา มีแต่ปีเกิด
    # บัตร ตลอดชีพ มีแต่ปีเกิด
    if len(txt) == 8:
        _year   = txt[:4]   # 1-4
        _month  = txt[4:6]  # 5-6
        _day    = txt[6:8]  # 7-8
        # แปลงเป็น วัน/เดือน/ปี
        return f"{_day}/{_month}/{_year}"
    else:
        return txt


def textToEngDate(txt:str):
    # ปีพ.ศ. + เดือน + ปี 
    if len(txt) == 8:
        _year   = txt[:4]   # 1-4
        _month  = txt[4:6]  # 5-6
        _day    = txt[6:8]  # 7-8
        _yearEN = int(_year) - 543
        # แปลงเป็น ปี - เดือน - วัน
        return f"{_yearEN}-{_month}-{_day}"
    else:
        return txt
        
    
def setformatDocNumber(txt:str):
    # 0000-00-00000000    
    t1 = txt[:4]   # 1-4
    t2 = txt[4:6]  # 5-6
    t3 = txt[6:]   # 6+
    
    return f"{t1}-{t2}-{t3}"
    
    
def searchDATAValue(type,value,response):    
    for data in APDU_DATA:
        if data[type] == value:
           return data[response]

    return None

def searchAPDUPhoto(value):
    
    for data in APDU_PHOTO:
        if data['key'] == value:
           return data['apdu']

    return None

def copyTextToClipboard(txt):

    return subprocess.run("clip", input=txt, check=True, encoding="tis-620")