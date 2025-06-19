# Your request: Add sound (beep) when an object is counted, and ensure everything integrates into the existing system.

import cv2
from ultralytics import YOLO
import threading
import requests
import sqlite3
from datetime import datetime, date
import pygame

# — Telegram sozlamalar —
TOKEN = "7936599193:AAGX6e90p_3LAtIXQRDpSfqIsVCkFwxtwWg"
CHAT_ID = "6820821027"
URL_SEND = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
URL_EDIT = f"https://api.telegram.org/bot{TOKEN}/editMessageText"

last_msg_id = None
msg_lock = threading.Lock()

def send_msg_thread(text):
    global last_msg_id
    with msg_lock:
        try:
            if last_msg_id:
                r = requests.post(URL_EDIT, data={
                    "chat_id": CHAT_ID,
                    "message_id": last_msg_id,
                    "text": text
                })
                if not r.ok:
                    last_msg_id = None
            if not last_msg_id:
                r = requests.post(URL_SEND, data={"chat_id":CHAT_ID,"text":text})
                if r.ok:
                    last_msg_id = r.json()['result']['message_id']
        except:
            pass

def send_new_msg_thread(text):
    global last_msg_id
    with msg_lock:
        try:
            r = requests.post(URL_SEND, data={"chat_id":CHAT_ID,"text":text})
            if r.ok:
                last_msg_id = r.json()['result']['message_id']
        except:
            pass

# — DB sozlamalar —
conn = sqlite3.connect('hisob.db', check_same_thread=False)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS hisob (id INTEGER PRIMARY KEY, ts TEXT, cnt INTEGER)""")
conn.commit()

def bazaga_qosh(cnt):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT INTO hisob (ts,cnt) VALUES (?,?)", (ts,cnt))
    conn.commit()

def bugun_hisob():
    d = date.today().strftime("%Y-%m-%d")
    cur.execute("SELECT ts,cnt FROM hisob WHERE ts LIKE ?", (f"{d}%",))
    r = cur.fetchall()
    if not r:
        return "📊 Bugun hech nima yo‘q."
    o = "📊 Bugungi hisob:\n"
    for t,c in r:
        o += f"{t} — {c}\n"
    return o

# — Ovoz (beep) sozlamasi —
pygame.mixer.init()
sound = pygame.mixer.Sound("beep.mp3")  # Make sure beep.mp3 is in the same directory

# — GUI kichik settings —
CAM_W, CAM_H = 640, 360
WIN_W, WIN_H = 640, 420
BTN_H = 50
START = (10,WIN_H-BTN_H,200,WIN_H)
STOP  = (220,WIN_H-BTN_H,410,WIN_H)
STAT  = (430,WIN_H-BTN_H,620,WIN_H)

klik=None
def on_click(e,x,y,flags,param):
    global klik
    if e==cv2.EVENT_LBUTTONDOWN:
        if START[0]<=x<=START[2] and START[1]<=y<=START[3]: klik='start'
        elif STOP[0]<=x<=STOP[2] and STOP[1]<=y<=STOP[3]:   klik='stop'
        elif STAT[0]<=x<=STAT[2] and STAT[1]<=y<=STAT[3]:   klik='stat'

# — Asosiy kod vatsiyasi —
cv2.namedWindow("Hisoblash")
cv2.setMouseCallback("Hisoblash", on_click)

model = YOLO("yolo11s.pt")  # YOLOv11 model, replace with path or model name as needed
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)

tracking=False
count=0
ids=set()
pos={}

print("Press ESC to exit")

while True:
    ret,fr = cap.read()
    if not ret: break

    if klik=='start' and not tracking:
        tracking=True; count=0; ids.clear(); pos.clear()
        threading.Thread(target=send_new_msg_thread,
                         args=(f"🟢 Hisob boshlandi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",),
                         daemon=True).start()
    elif klik=='stop' and tracking:
        tracking=False
        threading.Thread(target=send_new_msg_thread,
                         args=(f"🔴 Hisob to‘xtadi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. Jami: {count}",),
                         daemon=True).start()
    elif klik=='stat':
        threading.Thread(target=send_new_msg_thread,
                         args=(bugun_hisob(),), daemon=True).start()
    klik=None

    vis = cv2.resize(fr, (WIN_W, WIN_H-BTN_H))
    bar = 30
    vis = cv2.copyMakeBorder(vis,0,BTN_H,0,0,cv2.BORDER_CONSTANT,value=(50,50,50))
    cv2.line(vis,(CAM_W//2,0),(CAM_W//2,CAM_H),(0,255,0),2)

    if tracking:
        res = model.track(source=fr, persist=True, verbose=False)
        boxes = res[0].boxes
        if boxes and boxes.id is not None:
            ids_list = boxes.id.int().tolist()
            centers = boxes.xywh[:,:2].tolist()
            classes = boxes.cls.int().tolist()
            names = res[0].names  # список всех классов
            for oid, ctr, cls in zip(ids_list, centers, classes):
                label = names[cls]
                print(f"🧾 Object ID: {oid}, Class: {cls} — {label}")
            for oid,ctr,cls in zip(ids_list,centers,classes):
                if cls==0: continue
                x=ctr[0]; prev = pos.get(oid); pos[oid]=x
                if prev and oid not in ids and prev<CAM_W//2<=x:
                    count+=1; ids.add(oid); bazaga_qosh(count)
                    sound.play()  # <-- Beep sound here
                    if boxes.xyxy is not None and len(boxes.xyxy) > 0:
                        b = boxes.xyxy[ids_list.index(oid)]
                        x1,y1,x2,y2=map(int,b)
                        cv2.rectangle(vis,(x1,y1),(x2,y2),(0,0,255),2)
                    threading.Thread(target=send_msg_thread,
                                     args=(f"📦 Hisob: {count}",), daemon=True).start()

    # tugmalar
    def draw(btx,txt,act):
        clr=(0,120,0) if act else (80,80,80)
        cv2.rectangle(vis,(btx[0],btx[1]),(btx[2],btx[3]),clr,-1)
        cv2.putText(vis,txt,(btx[0]+10,btx[3]-10),
                    cv2.FONT_HERSHEY_SIMPLEX,0.7,(255,255,255),2)
    draw(START,"BOSHLASH",not tracking)
    draw(STOP,"TUGATISH",tracking)
    draw(STAT,"STATISTIKA",True)
    cv2.putText(vis,f"PHONE Test count: {count}",(10,30),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
    cv2.imshow("Hisoblash",vis)
    if cv2.waitKey(1)==27: break

cap.release()
conn.close()
cv2.destroyAllWindows()
