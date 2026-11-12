#!/usr/bin/env python3
# AUTO-BUILT by RBC PIPE — 2026-10-29
# source: FRUX IND MajorLogin/GetLoginData captures | account_id=18863879512
# Updated: 64-bit device profile, region-aware CDN, version-fallback GetLoginData
# Multi-region patch: IND, BD, ME, TH, ID, VN, PK, TW, CIS, RU, SAC, BR, EU, SG, NA, US

#!/usr/bin/env python3
# Dependencies: pip install pycryptodome requests
"""
RBC GUEST GEN v2.2 — ALL REGION
  Register flow: GOP guest:register → token:grant → MajorRegister → (optional) GetLoginData

Usage:
  python gen.py                          # interactive (region/count/prefix)
  python gen.py 5 IND                    # direct: count region
  python gen.py 10                       # count only (region prompt aayega)
  python gen.py 5 ALL                    # round-robin all regions
  python gen.py jwt UID PASS REGION      # fetch JWT + AK/AIV
"""

import requests, json, random, string, warnings, hashlib, hmac, time, os, sys, threading, uuid, base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import urllib3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from google.protobuf import descriptor_pb2, symbol_database, message_factory

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")
requests.packages.urllib3.disable_warnings()

# ================= CONFIG =================
RELEASE_VERSION = "OB55"
UNITY_VERSION = "2018.4.12f1"
CLIENT_VERSION = "1.134.14"
CLIENT_VERSION_FALLBACKS = ("1.134.14", "1.134.13", "1.134.12", "1.133.1")
CLIENT_VERSION_CODE = "2019121269"
MSDK_APP_VER = "1.132.9"
MSDK_VER_CODE = "2024010012"
MSDK_UA = f"GarenaMSDK/4.0.42(NX809J ;Android 9;en;US;app {MSDK_APP_VER} {MSDK_VER_CODE};)"

HKey = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
AKey = HKey.encode()

# ═══════════════ ALL REGIONS — host + language ═══════════════
REGIONS = {
    "IND": {"host": "loginbp.ppmainecoonghj.com", "lang": "hi", "backend": "ppmainecoonghj"},
    "BD":  {"host": "loginbp.ggpolarbear.com",     "lang": "bn", "backend": "ggpolarbear"},
    "ME":  {"host": "loginbp.common.ggbluefox.com","lang": "ar", "backend": "ggbluefox"},
    "TH":  {"host": "loginbp.common.ggbluefox.com","lang": "th", "backend": "ggbluefox"},
    "ID":  {"host": "loginbp.ggpolarbear.com",     "lang": "id", "backend": "ggpolarbear"},
    "VN":  {"host": "loginbp.ggpolarbear.com",     "lang": "vi", "backend": "ggpolarbear"},
    "PK":  {"host": "loginbp.ggpolarbear.com",     "lang": "ur", "backend": "ggpolarbear"},
    "TW":  {"host": "loginbp.ggpolarbear.com",     "lang": "zh", "backend": "ggpolarbear"},
    "CIS": {"host": "loginbp.ggpolarbear.com",     "lang": "ru", "backend": "ggpolarbear"},
    "RU":  {"host": "loginbp.ggpolarbear.com",     "lang": "ru", "backend": "ggpolarbear"},
    "SAC": {"host": "loginbp.ggpolarbear.com",     "lang": "es", "backend": "ggpolarbear"},
    "BR":  {"host": "loginbp.ggpolarbear.com",     "lang": "pt", "backend": "ggpolarbear"},
    "EU":  {"host": "loginbp.ggpolarbear.com",     "lang": "en", "backend": "ggpolarbear"},
    "SG":  {"host": "loginbp.ggpolarbear.com",     "lang": "en", "backend": "ggpolarbear"},
    "NA":  {"host": "loginbp.ggpolarbear.com",     "lang": "en", "backend": "ggpolarbear"},
    "US":  {"host": "loginbp.ggpolarbear.com",     "lang": "en", "backend": "ggpolarbear"},
}

# ═══════════════ SELECTABLE REGION ORDER (picker + round-robin) ═══════════════
REGION_ORDER = ["IND", "BD", "ME", "TH", "ID", "VN", "PK", "TW",
                "CIS", "RU", "SAC", "BR", "EU", "SG", "NA", "US"]

# Round-robin mode: when user passes `ALL`, each generated account rotates through this.
ROUND_ROBIN_REGIONS = list(REGION_ORDER)

PROXIES_LIST = []
THREADS = 5
AUTO_ACTIVATE = False
NAME_PREFIX = "BSL__\u3164"
COUNTER_FILE = "name_counter.txt"
COUNTER_LOCK = threading.Lock()
STATS = {"ok": 0, "fail": 0}
STATS_LOCK = threading.Lock()
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BSL1_GENS")
os.makedirs(OUT_DIR, exist_ok=True)

# ================= PROXY =================
def load_proxies():
    if os.path.exists("proxies.txt"):
        with open("proxies.txt") as f:
            return [l.strip() for l in f if l.strip()]
    return PROXIES_LIST

def get_proxy():
    proxies = load_proxies()
    if not proxies:
        return None
    p = random.choice(proxies)
    if "@" in p:
        auth, host = p.split("@")
        return {"http": f"http://{auth}@{host}", "https": f"http://{auth}@{host}"}
    return {"http": f"http://{p}", "https": f"http://{p}"}

# ================= NAME =================
def next_name(prefix=None):
    with COUNTER_LOCK:
        n = 1
        if os.path.exists(COUNTER_FILE):
            try:
                n = int(open(COUNTER_FILE).read().strip()) + 1
            except Exception:
                n = 1
        with open(COUNTER_FILE, "w") as f:
            f.write(str(n))
    rand = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz123456789", k=5))
    return f"{prefix or NAME_PREFIX}{rand}"

def GenSig(payload):
    return hmac.new(AKey, payload.encode(), hashlib.sha256).hexdigest()

# ================= GUEST REGISTER =================
def Reg(proxy=None):
    password = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789', k=64))
    Url = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
    Data = {"app_id": 100067, "client_type": 2, "password": password, "source": 2}
    Text = json.dumps(Data, separators=(',', ':'))
    Sig = GenSig(Text)
    Hdr = {
        "User-Agent": MSDK_UA,
        "Authorization": f"Signature {Sig}",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Host": "100067.connect.garena.com",
        "Connection": "Keep-Alive",
    }
    response = requests.post(Url, headers=Hdr, data=Text, verify=False, timeout=15, proxies=proxy)
    json_data = response.json()
    if "data" in json_data and "uid" in json_data["data"]:
        return json_data["data"]["uid"], password, Sig
    raise Exception(f"Reg failed: {json_data}")

def Accs(uid, password, proxy=None):
    url = "https://100067.connect.garena.com/api/v2/oauth/guest/token:grant"
    headers = {
        "User-Agent": MSDK_UA, "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Host": "100067.connect.garena.com", "Connection": "Keep-Alive",
    }
    Prm = {"client_id": 100067, "client_secret": HKey, "client_type": 2,
           "password": password, "response_type": "token", "uid": uid}
    payload = json.dumps(Prm, separators=(',', ':'))
    response = requests.post(url, headers=headers, data=payload, verify=False, timeout=15, proxies=proxy)
    json_data = response.json()
    if "data" in json_data and "access_token" in json_data["data"]:
        return json_data["data"]["access_token"], json_data["data"]["open_id"]
    raise Exception(f"token:grant failed: {json_data}")

# ================= PROTOBUF HELPERS =================
def CrVr(N):
    if N < 0: return b''
    H = []
    while True:
        S = N & 0x7F
        N >>= 7
        if N: S |= 0x80
        H.append(S)
        if not N: break
    return bytes(H)

def CrVrnt(fn, v):
    return CrVr((fn << 3) | 0) + CrVr(v)

def CrLen(fn, v):
    enc = v.encode() if isinstance(v, str) else v
    return CrVr((fn << 3) | 2) + CrVr(len(enc)) + enc

def CrPro(fields):
    pkt = bytearray()
    for f, v in fields.items():
        if isinstance(v, int):
            pkt.extend(CrVrnt(f, v))
        elif isinstance(v, (str, bytes)):
            pkt.extend(CrLen(f, v))
    return bytes(pkt)

def EnAes(hex_data):
    # OB55 static key — same across all live regions
    key = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
    iv = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(bytes.fromhex(hex_data), 16)).hex()

def DecAes(hex_data):
    key = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
    iv = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
    raw = bytes.fromhex(hex_data)
    d = AES.new(key, AES.MODE_CBC, iv).decrypt(raw[:len(raw)//16*16])
    try: return unpad(d, 16)
    except ValueError: return d

def PbFirstVarint(data, want_field):
    off = 0
    while off < len(data):
        key = shift = 0
        while True:
            b = data[off]; off += 1
            key |= (b & 0x7F) << shift
            if not (b & 0x80): break
            shift += 7
        fn, wt = key >> 3, key & 7
        if wt == 0:
            v = shift = 0
            while True:
                b = data[off]; off += 1
                v |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
            if fn == want_field:
                return v
        elif wt == 2:
            ln = shift = 0
            while True:
                b = data[off]; off += 1
                ln |= (b & 0x7F) << shift
                if not (b & 0x80): break
                shift += 7
            off += ln
        elif wt == 1: off += 8
        elif wt == 5: off += 4
        else: break
    return None

# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------
MY_UID = "4236467494"
MY_PASSWORD = "JOBAYAR_CODX-GV1N90WCK"

AUTO_DEVICE = True
USE_REAL_IP = False
BATCH_DELAY = (8, 20)
BATCH_RETRY = 3

TOKEN_GRANT_URL = "https://100067.connect.garena.com/api/v2/oauth/guest/token:grant"
VERSION_URL = "https://version.ggwhitehawk.com/live/ver.php"
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"

# Static AES (OB55)
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'

SYMBOL = "》"
PROXIES = None
QUICK_FAIL = False

PROXY_CC = {"IND": "IN", "BD": "BD", "ME": "AE", "TH": "TH", "ID": "ID",
            "VN": "VN", "PK": "PK", "TW": "TW", "CIS": "RU", "RU": "RU",
            "SAC": "MX", "BR": "BR", "EU": "DE", "SG": "SG", "NA": "US", "US": "US"}


def fetch_free_proxies(country_code: str, limit: int = 20) -> list:
    out = []
    urls = [
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies"
        "&protocol=http&proxy_format=ipport&format=text&timeout=4000&country=%s" % country_code,
    ]
    for u in urls:
        try:
            r = requests.get(u, timeout=15)
            for line in r.text.splitlines():
                line = line.strip()
                if line.count(".") == 3 and ":" in line:
                    out.append(line)
        except Exception:
            continue
        if out:
            break
    if os.path.exists("proxies.txt"):
        try:
            out += [l.strip() for l in open("proxies.txt") if l.strip().count(".") == 3 and ":" in l]
        except Exception:
            pass
    seen = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq[:limit]


def try_activate(uid, pw, region, proxy_str):
    global PROXIES, QUICK_FAIL
    PROXIES = {"http": "http://" + proxy_str, "https": "http://" + proxy_str}
    QUICK_FAIL = True
    cfg = REGION_CFG[region]
    try:
        return run_getlogindata(uid, pw, cfg["major_login"], cfg["get_login_data"],
                                CLIENT_VERSION, next_index("rbc_GETLOGINDATA"), region, cfg)
    except Exception:
        return None
    finally:
        QUICK_FAIL = False

DOT = "¤"

# Fake client IP pool per region
IP_POOL: dict = {
    "IND": ["103.16.33.109", "106.202.108.146", "117.214.98.55", "122.176.45.12",
            "27.147.192.34", "59.152.101.77", "123.49.34.201", "49.36.128.66",
            "171.48.112.90", "223.190.56.14", "45.124.24.66", "157.38.27.201",
            "27.61.46.111"],
    "TH":  ["101.108.101.77", "118.172.184.30", "49.49.248.19", "110.169.242.66",
            "223.24.62.11", "101.51.41.202"],
    "ME":  ["185.107.236.18", "91.74.74.90", "2.50.12.44", "185.141.36.77",
            "94.203.76.111", "213.42.90.23"],
    "EU":  ["85.214.33.44", "92.198.178.19", "79.207.176.55", "178.63.66.121",
            "87.139.65.88", "93.192.224.14"],
    "VN":  ["14.177.103.65", "27.72.0.102", "113.185.32.44", "171.225.186.19",
            "118.69.190.22", "14.162.35.87"],
    "BD":  ["103.148.14.66", "118.179.62.34", "202.4.100.19", "27.147.48.22",
            "119.148.98.71", "103.205.236.11", "45.64.11.90", "182.48.74.155"],
    "TW":  ["60.251.122.45", "106.1.105.88", "114.32.118.23", "111.241.190.66",
            "118.160.181.33"],
    "RU":  ["85.95.174.22", "95.213.216.44", "178.154.244.19", "93.158.203.77",
            "62.118.245.30", "77.238.105.55"],
    "NA":  ["72.229.14.33", "98.116.254.88", "174.233.65.44", "24.144.198.77",
            "69.136.90.12", "198.255.44.201"],
    "SAC": ["190.52.14.33", "186.77.190.44", "200.112.66.77", "190.161.44.201",
            "186.67.88.12"],
    "BR":  ["177.102.44.88", "187.44.201.19", "191.32.178.33", "201.17.96.77",
            "177.83.55.102"],
    "SG":  ["138.75.128.66", "118.189.88.44", "203.117.34.201", "165.21.30.99",
            "103.254.158.12"],
    "US":  ["72.229.14.33", "98.116.254.88", "174.233.65.44", "24.144.198.77",
            "69.136.90.12", "198.255.44.201"],
}


# ============================================================
# RBC REGION CONFIG — FRUX IND sync + all regions
# ============================================================
REGION_CFG: dict = {
    "IND": {
        "major_login": "https://loginbp.ppmainecoonghj.com/MajorLogin",
        "get_login_data": "https://client.ind.freefiremobile.com/GetLoginData",
        "country_code": "IN", "telecom": "airtel",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ppmainecoonghj",
    },
    "TH": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://clientbp.ggpolarbear.com/GetLoginData",
        "country_code": "TH", "telecom": "AIS",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ggpolarbear",
    },
    "ME": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://clientbp.ggpolarbear.com/GetLoginData",
        "country_code": "AE", "telecom": "Etisalat",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ggpolarbear",
    },
    "EU": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://clientbp.ggpolarbear.com/GetLoginData",
        "country_code": "DE", "telecom": "Vodafone",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ggpolarbear",
    },
    "VN": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://clientbp.ggpolarbear.com/GetLoginData",
        "country_code": "VN", "telecom": "Viettel",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ggpolarbear",
    },
    "BD": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://clientbp.ggpolarbear.com/GetLoginData",
        "country_code": "BD", "telecom": "Grameenphone",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ggpolarbear",
    },
    "TW": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://clientbp.ggpolarbear.com/GetLoginData",
        "country_code": "TW", "telecom": "Chunghwa",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ggpolarbear",
    },
    "RU": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://clientbp.ggpolarbear.com/GetLoginData",
        "country_code": "RU", "telecom": "MTS",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ggpolarbear",
    },
    "CIS": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://clientbp.ggpolarbear.com/GetLoginData",
        "country_code": "RU", "telecom": "MTS",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ggpolarbear",
    },
    "PK": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://clientbp.ggpolarbear.com/GetLoginData",
        "country_code": "PK", "telecom": "Jazz",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ggpolarbear",
    },
    "ID": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://clientbp.ggpolarbear.com/GetLoginData",
        "country_code": "ID", "telecom": "Telkomsel",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ggpolarbear",
    },
    "NA": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://client.us.freefiremobile.com/GetLoginData",
        "country_code": "US", "telecom": "T-Mobile",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "us.freefiremobile",
    },
    "SAC": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://client.us.freefiremobile.com/GetLoginData",
        "country_code": "MX", "telecom": "Telcel",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "us.freefiremobile",
    },
    "BR": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://client.us.freefiremobile.com/GetLoginData",
        "country_code": "BR", "telecom": "Vivo",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "us.freefiremobile",
    },
    "SG": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://clientbp.ggpolarbear.com/GetLoginData",
        "country_code": "SG", "telecom": "Singtel",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "ggpolarbear",
    },
    "US": {
        "major_login": "https://loginbp.ggpolarbear.com/MajorLogin",
        "get_login_data": "https://client.us.freefiremobile.com/GetLoginData",
        "country_code": "US", "telecom": "T-Mobile",
        "network_type": "CarrierDataNetwork", "network_type_a": "4G",
        "backend": "us.freefiremobile",
    },
}


def get_real_ip():
    try:
        return requests.get("https://api.ipify.org", timeout=5).text.strip()
    except Exception:
        return random.choice(IP_POOL["IND"])


def pick_ip(region: str) -> str:
    if USE_REAL_IP:
        return get_real_ip()
    pool = IP_POOL.get(region, IP_POOL["IND"])
    return random.choice(pool)


# ---------------------------------------------------------------
# Region-aware ABHotUpdates CDN  (FIXED: now backend-aware for all 16 regions)
# ---------------------------------------------------------------
def _region_hotupdate(region: str, backend: str = ""):
    """
    Return (field_106, field_107) ABHotUpdates URLs for the region.

    Three distinct backends in REGION_CFG:
      * ppmainecoonghj  -> tata CDN     (IND)
      * ggpolarbear     -> bs CDN       (BD/ME/TH/ID/VN/PK/TW/CIS/RU/EU/SG)
      * us.freefiremobile -> us CDN     (NA/US/SAC/BR)
    """
    r = str(region or "IND").upper()
    b = (backend or (REGION_CFG.get(r, {}).get("backend") or "")).lower()

    if r == "IND" or "ppmainecoonghj" in b or "tata" in b:
        return (
            "https://dl-tata.freefireind.in/live/ABHotUpdates/|https://core-tata.freefireind.in/live/ABHotUpdates/|dff941d41e6e3a9e76f05ed71fdc8d87",
            "1.6168622e0868ddbd",
        )
    if "us.freefiremobile" in b or r in ("NA", "US", "SAC", "BR"):
        return (
            "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/|https://core-bs.ggpolarbear.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462",
            "c8e41b7a93f02d56e1a94c7b8203f5d1",
        )
    # default ggpolarbear (BD/ME/TH/ID/VN/PK/TW/CIS/RU/EU/SG)
    return (
        "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/|https://core-bs.ggpolarbear.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462",
        "c8e41b7a93f02d56e1a94c7b8203f5d1",
    )


# ---------------------------------------------------------------
# JWT version extraction
# ---------------------------------------------------------------
def _extract_jwt_versions(jwt_token):
    try:
        parts = jwt_token.split('.')
        if len(parts) != 3:
            return None, None
        payload_b64 = parts[1] + '=' * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get('client_version'), payload.get('client_version_code')
    except Exception:
        return None, None


# ---------------------------------------------------------------
# AES helpers
# ---------------------------------------------------------------
def aes_encrypt(data: bytes) -> bytes:
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(data, 16))


def aes_decrypt(data: bytes) -> bytes:
    data = data[:len(data) // 16 * 16]
    dec = AES.new(AES_KEY, AES.MODE_CBC, AES_IV).decrypt(data)
    try:
        return unpad(dec, 16)
    except ValueError:
        return dec


# ---------------------------------------------------------------
# Minimal protobuf wire parser
# ---------------------------------------------------------------
def parse_wire(data: bytes):
    fields = []
    off = 0
    while off < len(data):
        key = shift = 0
        while True:
            b = data[off]; off += 1
            key |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        fn, wt = key >> 3, key & 7
        if wt == 0:
            v = shift = 0
            while True:
                b = data[off]; off += 1
                v |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            fields.append((fn, wt, v))
        elif wt == 2:
            ln = shift = 0
            while True:
                b = data[off]; off += 1
                ln |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            fields.append((fn, wt, data[off:off + ln]))
            off += ln
        elif wt == 1:
            fields.append((fn, wt, data[off:off + 8])); off += 8
        elif wt == 5:
            fields.append((fn, wt, data[off:off + 4])); off += 4
        else:
            break
    return fields


# ---------------------------------------------------------------
# Protobuf descriptors (runtime — no pb2 dependency)
# ---------------------------------------------------------------
_sym_db = symbol_database.Default()
T = descriptor_pb2.FieldDescriptorProto


def _build_descriptors():
    req_fd = descriptor_pb2.FileDescriptorProto()
    req_fd.name = 'MLReq.proto'
    req_fd.syntax = 'proto3'
    gs = req_fd.message_type.add(); gs.name = 'GameSecurity'
    f = gs.field.add(); f.name = 'version'; f.number = 6; f.type = T.TYPE_INT32
    f = gs.field.add(); f.name = 'hidden_value'; f.number = 8; f.type = T.TYPE_UINT64

    m = req_fd.message_type.add(); m.name = 'MajorLogin'
    fields = [
        ('event_time', 3, T.TYPE_STRING), ('game_name', 4, T.TYPE_STRING),
        ('platform_id', 5, T.TYPE_INT32), ('client_version', 7, T.TYPE_STRING),
        ('system_software', 8, T.TYPE_STRING), ('system_hardware', 9, T.TYPE_STRING),
        ('telecom_operator', 10, T.TYPE_STRING), ('network_type', 11, T.TYPE_STRING),
        ('screen_width', 12, T.TYPE_UINT32), ('screen_height', 13, T.TYPE_UINT32),
        ('screen_dpi', 14, T.TYPE_STRING), ('processor_details', 15, T.TYPE_STRING),
        ('memory', 16, T.TYPE_UINT32), ('gpu_renderer', 17, T.TYPE_STRING),
        ('gpu_version', 18, T.TYPE_STRING), ('unique_device_id', 19, T.TYPE_STRING),
        ('client_ip', 20, T.TYPE_STRING), ('language', 21, T.TYPE_STRING),
        ('open_id', 22, T.TYPE_STRING), ('open_id_type', 23, T.TYPE_STRING),
        ('device_type', 24, T.TYPE_STRING), ('device_model', 25, T.TYPE_STRING),
        ('country_code', 26, T.TYPE_STRING), ('access_token', 29, T.TYPE_STRING),
        ('platform_sdk_id', 30, T.TYPE_INT32),
        ('network_operator_a', 41, T.TYPE_STRING), ('network_type_a', 42, T.TYPE_STRING),
        ('client_using_version', 57, T.TYPE_STRING),
        ('external_storage_total', 60, T.TYPE_INT32),
        ('external_storage_available', 61, T.TYPE_INT32),
        ('internal_storage_total', 62, T.TYPE_INT32),
        ('internal_storage_available', 63, T.TYPE_INT32),
        ('game_disk_storage_available', 64, T.TYPE_INT32),
        ('game_disk_storage_total', 65, T.TYPE_INT32),
        ('external_sdcard_avail_storage', 66, T.TYPE_INT32),
        ('external_sdcard_total_storage', 67, T.TYPE_INT32),
        ('field_70', 70, T.TYPE_INT32), ('login_by', 73, T.TYPE_INT32),
        ('library_path', 74, T.TYPE_STRING), ('reg_avatar', 76, T.TYPE_INT32),
        ('library_token', 77, T.TYPE_STRING), ('channel_type', 78, T.TYPE_INT32),
        ('cpu_type', 79, T.TYPE_INT32), ('cpu_architecture', 81, T.TYPE_STRING),
        ('client_version_code', 83, T.TYPE_STRING),
        ('field_85', 85, T.TYPE_INT32), ('graphics_api', 86, T.TYPE_STRING),
        ('supported_astc_bitset', 87, T.TYPE_UINT32),
        ('login_open_id_type', 88, T.TYPE_INT32),
        ('analytics_detail', 89, T.TYPE_BYTES),
        ('field_90', 90, T.TYPE_STRING), ('field_91', 91, T.TYPE_STRING),
        ('loading_time', 92, T.TYPE_UINT32), ('release_channel', 93, T.TYPE_STRING),
        ('extra_info', 94, T.TYPE_STRING),
        ('android_engine_init_flag', 95, T.TYPE_UINT32),
        ('field_96', 96, T.TYPE_STRING), ('if_push', 97, T.TYPE_INT32),
        ('is_vpn', 98, T.TYPE_INT32),
        ('origin_platform_type', 99, T.TYPE_STRING),
        ('primary_platform_type', 100, T.TYPE_STRING),
        ('field_102', 102, T.TYPE_BYTES), ('field_104', 104, T.TYPE_UINT32),
        ('field_105', 105, T.TYPE_INT32), ('field_106', 106, T.TYPE_STRING),
        ('field_107', 107, T.TYPE_STRING),
    ]
    for name, num, ftype in fields:
        f = m.field.add(); f.name = name; f.number = num; f.type = ftype
    try:
        _sym_db.pool.Add(req_fd)
    except Exception:
        pass
    ml = message_factory.GetMessageClass(_sym_db.pool.FindMessageTypeByName('MajorLogin'))

    res_fd = descriptor_pb2.FileDescriptorProto()
    res_fd.name = 'MLRes.proto'
    res_fd.syntax = 'proto3'
    bl = res_fd.message_type.add(); bl.name = 'BlacklistInfo'
    en = res_fd.enum_type.add(); en.name = 'BanReason'
    for nm, num in [('UNKNOWN', 0), ('IN_GAME_AUTO', 1), ('REFUND', 2),
                    ('OTHERS', 3), ('SKINMOD', 4), ('IN_GAME_AUTO_NEW', 1014)]:
        ev = en.value.add(); ev.name = nm; ev.number = num
    f = bl.field.add(); f.name = 'ban_reason'; f.number = 1; f.type = T.TYPE_ENUM; f.type_name = '.BanReason'
    f = bl.field.add(); f.name = 'expire_duration'; f.number = 2; f.type = T.TYPE_UINT32
    f = bl.field.add(); f.name = 'ban_time'; f.number = 3; f.type = T.TYPE_UINT32
    f = bl.field.add(); f.name = 'ban_type'; f.number = 4; f.type = T.TYPE_STRING

    q = res_fd.message_type.add(); q.name = 'QueueInfo'
    f = q.field.add(); f.name = 'allow'; f.number = 1; f.type = T.TYPE_BOOL
    f = q.field.add(); f.name = 'queue_position'; f.number = 2; f.type = T.TYPE_UINT32
    f = q.field.add(); f.name = 'need_wait_secs'; f.number = 3; f.type = T.TYPE_UINT32
    f = q.field.add(); f.name = 'queue_is_full'; f.number = 4; f.type = T.TYPE_BOOL

    r = res_fd.message_type.add(); r.name = 'MajorLoginRes'
    res_fields = [
        ('account_id', 1, T.TYPE_UINT64), ('lock_region', 2, T.TYPE_STRING),
        ('noti_region', 3, T.TYPE_STRING), ('ip_region', 4, T.TYPE_STRING),
        ('agora_environment', 5, T.TYPE_STRING), ('new_active_region', 6, T.TYPE_STRING),
        ('recommend_regions', 7, T.TYPE_STRING, T.LABEL_REPEATED),
        ('token', 8, T.TYPE_STRING), ('ttl', 9, T.TYPE_UINT32),
        ('server_url', 10, T.TYPE_STRING), ('emulator_score', 11, T.TYPE_UINT32),
        ('blacklist', 12, T.TYPE_MESSAGE, T.LABEL_OPTIONAL, '.BlacklistInfo'),
        ('queue_info', 13, T.TYPE_MESSAGE, T.LABEL_OPTIONAL, '.QueueInfo'),
        ('tp_url', 14, T.TYPE_STRING), ('app_server_id', 15, T.TYPE_UINT32),
        ('ip_city', 16, T.TYPE_STRING), ('ip_subdivision', 17, T.TYPE_STRING),
        ('kts', 21, T.TYPE_UINT32), ('ak', 22, T.TYPE_BYTES),
        ('aiv', 23, T.TYPE_BYTES), ('ffanti_url', 24, T.TYPE_STRING),
        ('connection_seed_enabled', 26, T.TYPE_BOOL),
        ('connection_seed', 27, T.TYPE_STRING),
    ]
    for entry in res_fields:
        f = r.field.add(); f.name = entry[0]; f.number = entry[1]; f.type = entry[2]
        if len(entry) > 3: f.label = entry[3]
        if len(entry) > 4: f.type_name = entry[4]
    try:
        _sym_db.pool.Add(res_fd)
    except Exception:
        pass
    mlres = message_factory.GetMessageClass(_sym_db.pool.FindMessageTypeByName('MajorLoginRes'))

    gfd = descriptor_pb2.FileDescriptorProto()
    gfd.name = 'GLDRes.proto'
    gfd.syntax = 'proto3'
    rg = gfd.message_type.add(); rg.name = 'GldRegion'
    f = rg.field.add(); f.name = 'id'; f.number = 1; f.type = T.TYPE_INT32
    f = rg.field.add(); f.name = 'code'; f.number = 2; f.type = T.TYPE_STRING
    sg = gfd.message_type.add(); sg.name = 'GldServer'
    f = sg.field.add(); f.name = 'region'; f.number = 1; f.type = T.TYPE_STRING
    f = sg.field.add(); f.name = 'name'; f.number = 2; f.type = T.TYPE_STRING
    f = sg.field.add(); f.name = 'addr'; f.number = 3; f.type = T.TYPE_STRING
    f = sg.field.add(); f.name = 'cc'; f.number = 6; f.type = T.TYPE_STRING
    gm = gfd.message_type.add(); gm.name = 'GldRes'
    g_fields = [
        ('account_id', 1, T.TYPE_UINT64), ('f2', 2, T.TYPE_UINT32),
        ('region', 3, T.TYPE_STRING), ('f4', 4, T.TYPE_STRING),
        ('network_id', 5, T.TYPE_STRING),
        ('f6', 6, T.TYPE_UINT32),
        ('f7', 7, T.TYPE_UINT32), ('f8', 8, T.TYPE_UINT32),
        ('online', 14, T.TYPE_STRING), ('f15', 15, T.TYPE_UINT32),
        ('event_url', 16, T.TYPE_STRING),
        ('regions', 19, T.TYPE_MESSAGE, T.LABEL_REPEATED, '.GldRegion'),
        ('server_time', 21, T.TYPE_UINT64),
        ('f23', 23, T.TYPE_UINT64), ('noti_region', 24, T.TYPE_STRING),
        ('f30', 30, T.TYPE_UINT64), ('chat', 32, T.TYPE_STRING),
        ('f34', 34, T.TYPE_BYTES), ('f37', 37, T.TYPE_UINT32),
        ('network_log', 39, T.TYPE_STRING), ('ip_region', 42, T.TYPE_STRING),
        ('servers', 44, T.TYPE_MESSAGE, T.LABEL_REPEATED, '.GldServer'),
        ('f45', 45, T.TYPE_UINT64), ('f48', 48, T.TYPE_BYTES),
        ('f51', 51, T.TYPE_UINT32), ('f52', 52, T.TYPE_BYTES),
        ('grtc', 62, T.TYPE_STRING), ('gin', 63, T.TYPE_BYTES),
        ('f65', 65, T.TYPE_BYTES), ('f69', 69, T.TYPE_BYTES),
        ('f70', 70, T.TYPE_BYTES), ('f75', 75, T.TYPE_UINT32),
        ('f77', 77, T.TYPE_INT64), ('gateway', 79, T.TYPE_STRING),
        ('f85', 85, T.TYPE_UINT32), ('f86', 86, T.TYPE_BYTES),
        ('f88', 88, T.TYPE_STRING), ('f89', 89, T.TYPE_UINT64),
        ('vodka', 92, T.TYPE_STRING), ('f96', 96, T.TYPE_UINT32),
        ('f97', 97, T.TYPE_UINT32), ('cs', 98, T.TYPE_STRING),
        ('f100', 100, T.TYPE_STRING),
    ]
    for entry in g_fields:
        f = gm.field.add(); f.name = entry[0]; f.number = entry[1]; f.type = entry[2]
        if len(entry) > 3: f.label = entry[3]
        if len(entry) > 4: f.type_name = entry[4]
    try:
        _sym_db.pool.Add(gfd)
    except Exception:
        pass
    gldres = message_factory.GetMessageClass(_sym_db.pool.FindMessageTypeByName('GldRes'))

    return ml, mlres, gldres


MajorLoginMsg, MajorLoginRes, GldRes = _build_descriptors()

# ---------------------------------------------------------------
# Device pools — 64-bit, FRUX IND specs
# ---------------------------------------------------------------
_BUILT_IN_32 = [
    {"model": "Xiaomi M2006C3LII", "w": 1600, "h": 720, "dpi": "320",
     "cpu": "ARMv7 VFPv3 NEON | 2001 | 8", "mem": 3790,
     "gpu": "PowerVR Rogue GE8320", "gpu_v": "OpenGL ES 3.2 build 1.11@5425693"},
]
_BUILT_IN_64 = [
    {"model": "samsung SM-A146B",
     "sw": "Android OS 14 / API-34 (UP1A.231005.007/E156BXXS6AYD4)",
     "w": 2340, "h": 1080, "dpi": "295",
     "cpu": "ARM64 FP ASIMD AES | 2200 | 8", "mem": 5586,
     "gpu": "Mali-G57 MC2", "gpu_v": "OpenGL ES 3.2 v1.r38p1"},
    {"model": "samsung SM-A155F",
     "sw": "Android OS 13 / API-33 (TP1A.220624.014/E156BXXS6BXD2)",
     "w": 2340, "h": 1080, "dpi": "295",
     "cpu": "ARM64 FP ASIMD AES | 2200 | 8", "mem": 5586,
     "gpu": "Mali-G57 MC2", "gpu_v": "OpenGL ES 3.2 v1.r38p1"},
    {"model": "samsung SM-E156B",
     "sw": "Android OS 14 / API-34 (UP1A.231005.007/E156BXXS6AYD4)",
     "w": 2340, "h": 1080, "dpi": "295",
     "cpu": "ARM64 FP ASIMD AES | 2200 | 8", "mem": 5586,
     "gpu": "Mali-G57 MC2", "gpu_v": "OpenGL ES 3.2 v1.r38p1"},
]

DEV_POOL_32 = None
DEV_POOL_64 = None


def load_device_pools():
    global DEV_POOL_32, DEV_POOL_64
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'devices.json')
        if os.path.exists(path):
            data = json.load(open(path, encoding='utf-8'))
            DEV_POOL_32 = data.get('armv7_32bit') or None
            DEV_POOL_64 = data.get('arm64') or None
    except Exception:
        pass


def pool_status():
    if DEV_POOL_32:
        return "devices.json (%d/%d)" % (len(DEV_POOL_32), len(DEV_POOL_64 or []))
    return "built-in (%d/%d)" % (len(_BUILT_IN_32), len(_BUILT_IN_64))


def pick_device_32():
    if DEV_POOL_32 and AUTO_DEVICE:
        d = random.choice(DEV_POOL_32)
        return {"model": d["model"], "w": d["screen_width"], "h": d["screen_height"],
                "dpi": d["screen_dpi"], "cpu": d["processor_details"], "mem": d["memory"],
                "gpu": d["gpu_renderer"], "gpu_v": d["gpu_version"]}
    return dict(random.choice(_BUILT_IN_32))


def pick_device_64():
    if DEV_POOL_64:
        d = random.choice(DEV_POOL_64)
        return {"model": d["model"], "sw": d.get("system_software", "Android OS 14 / API-34 (UP1A.231005.007/E156BXXS6AYD4)"),
                "w": d["screen_width"], "h": d["screen_height"], "dpi": d["screen_dpi"],
                "cpu": d["processor_details"], "mem": d["memory"],
                "gpu": d["gpu_renderer"], "gpu_v": d["gpu_version"]}
    return dict(random.choice(_BUILT_IN_64))


load_device_pools()


# ---------------------------------------------------------------
# Request builders — FRUX IND sync
# ---------------------------------------------------------------
def build_majorlogin(open_id, access_token, version, dev, region, cfg):
    """MajorLogin request — FRUX IND field set (64-bit device)."""
    r = MajorLoginMsg()
    r.event_time = time.strftime("%Y-%m-%d %H:%M:%S")
    r.game_name = "free fire"
    r.platform_id = 1
    r.client_version = version
    r.system_software = dev.get("sw", "Android OS 14 / API-34 (UP1A.231005.007/E156BXXS6AYD4)")
    r.system_hardware = "Handheld"
    r.telecom_operator = cfg["telecom"]
    r.network_type = "CarrierDataNetwork"
    r.screen_width = dev["w"]
    r.screen_height = dev["h"]
    r.screen_dpi = dev["dpi"]
    r.processor_details = dev["cpu"]
    r.memory = dev["mem"]
    r.gpu_renderer = dev["gpu"]
    r.gpu_version = dev["gpu_v"]
    r.unique_device_id = "Google|" + str(uuid.uuid4())
    r.client_ip = pick_ip(region)
    r.language = "en"
    r.open_id = open_id
    r.open_id_type = "4"
    r.device_type = "Handheld"
    r.device_model = dev["model"]
    r.country_code = cfg["country_code"]
    r.access_token = access_token
    r.platform_sdk_id = 1
    r.network_operator_a = cfg["telecom"]
    r.network_type_a = "4G"
    r.client_using_version = "7428b253defc164018c604a1ebbfebdf"
    r.external_storage_total = 108009
    r.external_storage_available = 3859
    r.internal_storage_total = 5023
    r.game_disk_storage_available = 3987
    r.game_disk_storage_total = 108009
    r.external_sdcard_avail_storage = 3987
    r.external_sdcard_total_storage = 108009
    r.field_70 = 4
    r.login_by = 3
    r.library_path = "/data/app/~~OlJmIW-Yzl-44x2WnJP4Nw==/com.garena.game.ffi-_eDk_pQQMiFk1YUeqwJBvQ==/lib/arm64"
    r.reg_avatar = 3
    r.library_token = "dd9d4c174e0472d34b7fd34bd5924bc9|/data/app/~~OlJmIW-Yzl-44x2WnJP4Nw==/com.garena.game.ffi-_eDk_pQQMiFk1YUeqwJBvQ==/base.apk"
    r.channel_type = 3
    r.cpu_type = 2
    r.cpu_architecture = "64"
    r.client_version_code = CLIENT_VERSION_CODE
    r.field_85 = 3
    r.graphics_api = "OpenGLES2"
    r.supported_astc_bitset = 8191
    r.login_open_id_type = 4
    r.field_90 = "Coimbatore"
    r.field_91 = "TN"
    r.loading_time = 9570
    r.release_channel = "android"
    r.extra_info = "KqsHT54jON6bxITmlrRyOrXWBqKqZ4BoqPzT/mhtriAfRt2dt7gC8pnAJfj11alcEUA5sD8BshSYQhxXT9RFmU6YzcI1FKK4MwxJcF4+kvelPD1H"
    r.android_engine_init_flag = 111207
    r.field_96 = '{"cur_rate":null,"support_etc2":false}'
    r.if_push = 1
    r.origin_platform_type = "4"
    r.primary_platform_type = "4"
    r.field_102 = bytes.fromhex("4503454457550c0766")
    r.field_104 = 11921
    r.field_105 = 1
    hot_106, hot_107 = _region_hotupdate(region, cfg.get("backend", ""))
    r.field_106 = hot_106
    r.field_107 = hot_107
    return r


def fetch_version_cfg(version, dev, region):
    """Version API: cdn_url, abhotupdate_cdn_url, vercfg_sign."""
    try:
        vr = requests.get(VERSION_URL, params={
            "version": version, "lang": "en", "device": "android",
            "channel": "3rd_party", "appstore": "thirdparty", "region": region,
            "release_version": RELEASE_VERSION, "whitelist_version": "1.8.0",
            "whitelist_sp_version": "1.0.0", "device_name": dev["model"],
            "device_CPU": dev["cpu"], "device_GPU": dev["gpu"],
            "device_mem": str(dev["mem"]),
        }, headers={"User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"},
            timeout=10)
        j = vr.json()
        return j.get("cdn_url", ""), j.get("abhotupdate_cdn_url", ""), j.get("vercfg_sign", "")
    except Exception:
        return "", "", ""


def build_getlogindata(open_id, access_token, version, dev, region, cfg):
    """GetLoginData request — FRUX IND field set (separate fresh device_id)."""
    hot_106, hot_107 = _region_hotupdate(region, cfg.get("backend", ""))
    gd = pick_device_64()
    r = MajorLoginMsg()
    r.event_time = time.strftime("%Y-%m-%d %H:%M:%S")
    r.game_name = "free fire"
    r.platform_id = 1
    r.client_version = version
    r.system_software = gd.get("sw", "Android OS 14 / API-34 (UP1A.231005.007/E156BXXS6AYD4)")
    r.system_hardware = "Handheld"
    r.telecom_operator = cfg["telecom"]
    r.network_type = "CarrierDataNetwork"
    r.screen_width = gd["w"]
    r.screen_height = gd["h"]
    r.screen_dpi = gd["dpi"]
    r.processor_details = gd["cpu"]
    r.memory = gd["mem"]
    r.gpu_renderer = gd["gpu"]
    r.gpu_version = gd["gpu_v"]
    r.unique_device_id = "Google|" + str(uuid.uuid4())
    r.client_ip = pick_ip(region)
    r.language = "en"
    r.open_id = open_id
    r.open_id_type = "4"
    r.device_type = "Handheld"
    r.device_model = gd["model"]
    r.country_code = cfg["country_code"]
    r.access_token = access_token
    r.platform_sdk_id = 1
    r.network_operator_a = cfg["telecom"]
    r.network_type_a = "4G"
    r.client_using_version = "7428b253defc164018c604a1ebbfebdf"
    r.external_storage_total = 108009
    r.external_storage_available = 3859
    r.internal_storage_total = 5023
    r.game_disk_storage_available = 3987
    r.game_disk_storage_total = 108009
    r.external_sdcard_avail_storage = 3987
    r.external_sdcard_total_storage = 108009
    r.field_70 = 4
    r.login_by = 3
    r.library_path = "/data/app/~~OlJmIW-Yzl-44x2WnJP4Nw==/com.garena.game.ffi-_eDk_pQQMiFk1YUeqwJBvQ==/lib/arm64"
    r.reg_avatar = 3
    r.library_token = "dd9d4c174e0472d34b7fd34bd5924bc9|/data/app/~~OlJmIW-Yzl-44x2WnJP4Nw==/com.garena.game.ffi-_eDk_pQQMiFk1YUeqwJBvQ==/base.apk"
    r.channel_type = 3
    r.cpu_type = 2
    r.cpu_architecture = "64"
    r.client_version_code = CLIENT_VERSION_CODE
    r.field_85 = 3
    r.graphics_api = "OpenGLES2"
    r.supported_astc_bitset = 8191
    r.login_open_id_type = 4
    r.field_90 = "Coimbatore"
    r.field_91 = "TN"
    r.loading_time = 9570
    r.release_channel = "android"
    r.extra_info = "KqsHT54jON6bxITmlrRyOrXWBqKqZ4BoqPzT/mhtriAfRt2dt7gC8pnAJfj11alcEUA5sD8BshSYQhxXT9RFmU6YzcI1FKK4MwxJcF4+kvelPD1H"
    r.android_engine_init_flag = 111207
    r.field_96 = '{"cur_rate":null,"support_etc2":false}'
    r.if_push = 1
    r.origin_platform_type = "0"
    r.primary_platform_type = "4"
    r.field_102 = bytes.fromhex("4503454457550c0766")
    r.field_104 = 11921
    r.field_105 = 1
    r.field_106 = hot_106
    r.field_107 = hot_107
    return r, gd


# ---------------------------------------------------------------
# Display / dump helpers
# ---------------------------------------------------------------
def hexdump(data: bytes, width: int = 16) -> str:
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hexpart = ' '.join('%02x' % b for b in chunk)
        asciipart = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append('%04x  %-47s  %s' % (i, hexpart, asciipart))
    return '\n'.join(lines)


def dumps_dir():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dumps')
    os.makedirs(d, exist_ok=True)
    return d


def next_index(prefix):
    d = dumps_dir()
    i = 1
    while os.path.exists(os.path.join(d, '%s%d.txt' % (prefix, i))):
        i += 1
    return i


def append_keys(line):
    kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'RBC_keys.txt')
    first = not os.path.exists(kp)
    with open(kp, 'a') as f:
        if first:
            f.write('# type | index | uid | account_id | region | AK | AIV\n')
        f.write(line + '\n')


# ---------------------------------------------------------------
# Network
# ---------------------------------------------------------------
def token_grant(uid, pw):
    data = None
    err = {}
    last_exc = ""
    attempts = 1 if QUICK_FAIL else BATCH_RETRY
    for attempt in range(1, attempts + 1):
        try:
            gr = requests.post(TOKEN_GRANT_URL, json={
                "client_id": 100067, "client_secret": CLIENT_SECRET, "client_type": 2,
                "password": pw, "response_type": "token", "uid": int(uid)},
                timeout=25, proxies=PROXIES)
            err = gr.json()
            data = err.get("data", {})
            if data.get("access_token"):
                break
            if err.get("code") == 1006 or "too_many" in str(err.get("error", "")):
                if QUICK_FAIL:
                    break
                wait = 15 * attempt + random.randint(0, 15)
                print('  %s rate-limit 1006, waiting %ds (retry %d/%d)' % (DOT, wait, attempt, BATCH_RETRY))
                time.sleep(wait)
            else:
                break
        except requests.exceptions.SSLError as e:
            last_exc = "SSL: %s" % str(e)[:80]
            print('  %s SSL error (attempt %d/%d): %s' % (DOT, attempt, attempts, last_exc))
            if not QUICK_FAIL:
                time.sleep(5 * attempt)
        except requests.exceptions.ConnectionError as e:
            last_exc = "CONN: %s" % str(e)[:80]
            print('  %s connection error (attempt %d/%d): retrying in %ds' % (DOT, attempt, attempts, 5 * attempt))
            if not QUICK_FAIL:
                time.sleep(5 * attempt)
        except requests.exceptions.Timeout:
            last_exc = "TIMEOUT after 25s"
            print('  %s timeout (attempt %d/%d): retrying in %ds' % (DOT, attempt, attempts, 5 * attempt))
            if not QUICK_FAIL:
                time.sleep(5 * attempt)
        except Exception as e:
            last_exc = str(e)[:100]
            print('  %s unexpected error (attempt %d/%d): %s' % (DOT, attempt, attempts, last_exc))
            if not QUICK_FAIL:
                time.sleep(3)
    if not (data or {}).get("access_token"):
        print('  %s token:grant failed: %s | last: %s' % (DOT, str(err)[:80], last_exc))
        print('  %s hint: network garena token endpoint tak nahi pahunch raha. WiFi/VPN switch karke try karo.' % DOT)
        return None, None
    return data["access_token"], data.get("open_id", "")


def _looks_random(b: bytes) -> bool:
    return len(b) == 16 and sum(1 for x in b if x in (0, 8, 10, 16, 24, 32, 40, 48)) <= 2


def _scan_ak_aiv(fields):
    if len(fields) < 5:
        return None, None
    f22 = [v for fn, wt, v in fields if fn == 22 and wt == 2]
    f23 = [v for fn, wt, v in fields if fn == 23 and wt == 2]
    best = None
    for a in f22:
        for b in f23:
            if len(a) == 16 and len(b) == 16:
                sc = int(_looks_random(a)) + int(_looks_random(b))
                if best is None or sc > best[0]:
                    best = (sc, a, b)
    return (best[1], best[2]) if best else (None, None)


def _recover_ak_aiv(raw: bytes):
    for off in range(0, 96):
        try:
            fields = parse_wire(raw[off:])
        except Exception:
            continue
        if len(fields) < 5:
            continue
        k, i = _scan_ak_aiv(fields)
        if k:
            return k, i
    return None, None


def parse_majorlogin_response(raw: bytes):
    """Skip-scan 0,4..124; AK/AIV recover if protobuf parse misses."""
    for skip in [0] + list(range(4, 128, 4)):
        try:
            m = MajorLoginRes()
            m.ParseFromString(raw[skip:])
        except Exception:
            continue
        if m.account_id or m.token:
            if not (m.ak and m.aiv):
                k, i = _recover_ak_aiv(raw)
                if k:
                    try:
                        m.ak = k
                        m.aiv = i
                    except Exception:
                        pass
            return m, skip
    msg = MajorLoginRes()
    try:
        msg.ParseFromString(raw[64:] if len(raw) > 64 else raw)
    except Exception:
        pass
    return msg, 64


GLD_BY_REGION = {r: c["get_login_data"] for r, c in REGION_CFG.items()}
GLD_DEFAULT = "https://clientbp.ggpolarbear.com/GetLoginData"


def choose_region(jwt: str, region: str, cfg: dict) -> bool:
    """ChooseRegion force-bind. Returns True on 200."""
    try:
        code = "RU" if region == "CIS" else region
        body = bytes([0x0A, len(code)]) + code.encode()
        h = dict(GLD_HEADERS)
        h["Authorization"] = "Bearer " + jwt
        h["Host"] = cfg["major_login"].split("/")[2]
        login_root = cfg["major_login"].rsplit("/", 1)[0]
        r = requests.post(login_root + "/ChooseRegion", data=aes_encrypt(body),
                          headers=h, verify=False, timeout=20, proxies=PROXIES)
        return r.status_code == 200
    except Exception:
        return False


ML_HEADERS = {
    "User-Agent": "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "Accept": "*/*", "Accept-Encoding": "deflate, gzip",
    "Content-Type": "application/x-www-form-urlencoded",
    "Expect": "100-continue", "X-Unity-Version": "2022.3.47f1",
    "X-GA": "v1 1", "ReleaseVersion": RELEASE_VERSION,
}

GLD_HEADERS = {
    "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded",
    "X-GA": "v1 1", "ReleaseVersion": RELEASE_VERSION, "X-Unity-Version": "2018.4.12f1",
}


# ---------------------------------------------------------------
# Dump writers
# ---------------------------------------------------------------
def dump_majorlogin(idx, uid, enc, plain, req_msg, resp_raw, res, skip, login_url, dev, region):
    fn = 'RBC_MAJORLOGIN%d.txt' % idx
    bar = '=' * 60
    parts = [
        bar,
        '  RBC MAJORLOGIN DUMP #%d' % idx,
        '  UID: %s   Region: %s   Server: %s' % (uid, region, login_url),
        '  Device: %s   Time: %s' % (dev['model'], time.strftime('%Y-%m-%d %H:%M:%S')),
        bar, '',
        '>> REQUEST (encrypted hex — sent to server)',
        hexdump(enc), '',
        '>> REQUEST (plaintext hex)',
        hexdump(plain), '',
        '>> REQUEST (decoded protobuf)',
        str(req_msg), '',
        '>> RESPONSE (raw hex, header included)',
        hexdump(resp_raw), '',
        '>> RESPONSE (body hex, skip %d)' % skip,
        hexdump(resp_raw[skip:]), '',
        '>> RESPONSE (decoded protobuf)',
        str(res), '',
        '>> KEYS',
        'account_id : %s' % res.account_id,
        'AK         : %s' % (res.ak.hex() if res.ak else '(empty)'),
        'AIV        : %s' % (res.aiv.hex() if res.aiv else '(empty)'),
        'token      : %s' % res.token,
        'ban_reason : %s' % res.blacklist.ban_reason,
        bar, '',
    ]
    with open(os.path.join(dumps_dir(), fn), 'w') as f:
        f.write('\n'.join(parts))
    return fn


def dump_getlogindata(idx, uid, genc, gplain, greq, resp_raw, g, login_url, dev, region):
    fn = 'RBC_GETLOGINDATA%d.txt' % idx
    bar = '=' * 60
    parts = [
        bar,
        '  RBC GETLOGINDATA DUMP #%d' % idx,
        '  UID: %s   Region: %s   Server: %s' % (uid, region, login_url),
        '  Device: %s   Time: %s' % (dev['model'], time.strftime('%Y-%m-%d %H:%M:%S')),
        bar, '',
        '>> GETLOGINDATA REQUEST (encrypted hex)',
        hexdump(genc), '',
        '>> GETLOGINDATA REQUEST (plaintext hex)',
        hexdump(gplain), '',
        '>> GETLOGINDATA REQUEST (decoded protobuf)',
        str(greq), '',
        '>> GETLOGINDATA RESPONSE (raw hex)',
        hexdump(resp_raw), '',
        '>> GETLOGINDATA RESPONSE (decoded protobuf — FULL)',
        str(g), '',
        '>> SERVER LIST',
        'online : %s' % g.online,
        'chat   : %s' % g.chat,
        'grtc   : %s' % g.grtc,
    ] + ['%s : %s' % (s.name, s.addr) for s in g.servers] + [bar, '']
    with open(os.path.join(dumps_dir(), fn), 'w') as f:
        f.write('\n'.join(parts))
    return fn


# ---------------------------------------------------------------
# Runners
# ---------------------------------------------------------------
def run_majorlogin(uid, pw, login_url, version, idx, region, cfg):
    """One MajorLogin cycle (64-bit device). Returns response message or None."""
    access_token, open_id = token_grant(uid, pw)
    if not access_token:
        return None
    dev = pick_device_64()
    print('  %s device: %s | %s | %dMB' % (DOT, dev['model'], dev['gpu'], dev['mem']))
    req = build_majorlogin(open_id, access_token, version, dev, region, cfg)
    plain = req.SerializeToString()
    enc = aes_encrypt(plain)
    hdrs = dict(ML_HEADERS)
    hdrs['X-Ga-Sv'] = str(int(time.time()))
    try:
        resp = requests.post(login_url, data=enc, headers=hdrs, verify=False, timeout=25)
    except Exception as e:
        print('  %s request error: %s' % (DOT, str(e)[:100]))
        return None
    if resp.status_code != 200:
        print('  %s MajorLogin %d: %s' % (DOT, resp.status_code,
              resp.content.decode('utf-8', 'replace').strip()[:80]))
        return None
    res, skip = parse_majorlogin_response(resp.content)
    if not res.account_id or not res.token:
        print('  %s MajorLogin returned an ERROR payload (account=0, empty token):' % DOT)
        print('  ' + str(res).replace('\n', '\n  '))
        print('  %s hint: account bahut baar login hua hai (rate/flag) — kisi aur UID se try karo' % DOT)
        return None
    fn = dump_majorlogin(idx, uid, enc, plain, req, resp.content, res, skip, login_url, dev, region)
    append_keys('MAJORLOGIN | %d | %s | %s | %s | %s | %s' % (
        idx, uid, res.account_id, region,
        res.ak.hex() if res.ak else '-', res.aiv.hex() if res.aiv else '-'))
    print('  %s MajorLogin 200 | account=%s | ban=%s' % (
        DOT, res.account_id, res.blacklist.ban_reason or 'none'))
    print('  %s AK  : %s' % (DOT, res.ak.hex() if res.ak else '(empty)'))
    print('  %s AIV : %s' % (DOT, res.aiv.hex() if res.aiv else '(empty)'))
    print('  %s saved: dumps/%s' % (DOT, fn))
    return res


def run_getlogindata(uid, pw, login_url, gld_url, version, idx, region, cfg):
    """Full chain: token:grant -> MajorLogin -> GetLoginData with version fallback."""
    access_token, open_id = token_grant(uid, pw)
    if not access_token:
        return None
    dev = pick_device_64()
    print('  %s login device: %s' % (DOT, dev['model']))
    req = build_majorlogin(open_id, access_token, version, dev, region, cfg)
    hdrs = dict(ML_HEADERS)
    hdrs['X-Ga-Sv'] = str(int(time.time()))
    try:
        resp = requests.post(login_url, data=aes_encrypt(req.SerializeToString()),
                             headers=hdrs, verify=False, timeout=25, proxies=PROXIES)
    except Exception as e:
        print('  %s MajorLogin error: %s' % (DOT, str(e)[:100]))
        return None
    if resp.status_code != 200:
        print('  %s MajorLogin %d: %s' % (DOT, resp.status_code,
              resp.content.decode('utf-8', 'replace').strip()[:80]))
        return None
    ml_res, _ = parse_majorlogin_response(resp.content)
    if not ml_res.account_id or not ml_res.token:
        print('  %s MajorLogin ERROR payload (account=0) — chain aborted:' % DOT)
        print('  ' + str(ml_res).replace('\n', '\n  '))
        return None
    print('  %s MajorLogin 200 | account=%s | lock_region=%s' % (
        DOT, ml_res.account_id, ml_res.lock_region or ml_res.noti_region or '?'))

    bound = choose_region(ml_res.token, region, cfg)
    print('  %s ChooseRegion [%s] -> %s' % (DOT, region, 'OK' if bound else 'fail'))

    # ---- Version fallback ----
    versions_to_try = [version]
    jv, _jvc = _extract_jwt_versions(ml_res.token)
    if jv and jv not in versions_to_try:
        versions_to_try.append(jv)
    for fb in CLIENT_VERSION_FALLBACKS:
        if fb not in versions_to_try:
            versions_to_try.append(fb)
    print('  %s GetLoginData will try versions: %s' % (DOT, versions_to_try))

    g = None
    gd = None
    genc = gplain = greq = gresp = None
    gld_via = region
    used_version = version
    for try_version in versions_to_try:
        greq, gd = build_getlogindata(open_id, access_token, try_version, dev, region, cfg)
        gplain = greq.SerializeToString()
        genc = aes_encrypt(gplain)
        gh = dict(GLD_HEADERS)
        gh['X-GA-SV'] = str(int(time.time()))
        gh['Authorization'] = 'Bearer ' + ml_res.token
        try:
            gresp = requests.post(gld_url, data=genc, headers=gh, verify=False,
                                  timeout=25, proxies=PROXIES)
        except Exception as e:
            print('  %s GetLoginData error (v%s): %s' % (DOT, try_version, str(e)[:80]))
            continue

        if gresp.status_code == 401:
            jwt_region = (ml_res.lock_region or ml_res.noti_region or "").upper()
            fb_url = GLD_BY_REGION.get(jwt_region, GLD_DEFAULT)
            if fb_url != gld_url:
                print('  %s gld 401 — retry via JWT region host: %s' % (DOT, fb_url))
                try:
                    gresp = requests.post(fb_url, data=genc, headers=gh, verify=False,
                                          timeout=25, proxies=PROXIES)
                    gld_via = jwt_region or "jwt-region"
                except Exception as e:
                    print('  %s fallback error: %s' % (DOT, str(e)[:80]))

        if gresp.status_code != 200:
            print('  %s GetLoginData v%s → %d: %s' % (
                DOT, try_version, gresp.status_code,
                gresp.content.decode('utf-8', 'replace').strip()[:80]))
            continue

        candidate = GldRes()
        try:
            candidate.ParseFromString(gresp.content)
        except Exception as e:
            print('  %s parse error v%s: %s' % (DOT, try_version, str(e)[:80]))
            continue
        if not candidate.account_id:
            print('  %s empty account_id v%s' % (DOT, try_version))
            continue
        g = candidate
        used_version = try_version
        if try_version != version:
            print('  %s ✅ Version corrected: %s → %s' % (DOT, version, try_version))
        break

    if g is None:
        print('  %s GetLoginData failed for all versions' % DOT)
        return None

    print('  %s gld via: %s | ChooseRegion bind [%s]: %s' % (DOT, gld_via, region, bound))
    print('  %s GetLoginData 200 | server_time=%s' % (DOT, g.server_time))
    print('  %s ONLINE: %s' % (DOT, g.online))
    print('  %s CHAT  : %s' % (DOT, g.chat))
    print('  %s GRTC  : %s' % (DOT, g.grtc[:70]))
    for s in g.servers:
        print('  %s %s: %s' % (DOT, s.name, s.addr))

    fn = dump_getlogindata(idx, uid, genc, gplain, greq, gresp.content, g, gld_url, gd, region)
    append_keys('GETLOGINDATA | %d | %s | %s | %s | %s | %s' % (
        idx, uid, g.account_id, region,
        ml_res.ak.hex() if ml_res.ak else '-', ml_res.aiv.hex() if ml_res.aiv else '-'))
    print('  %s saved: dumps/%s' % (DOT, fn))
    try:
        act_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'activated_%s.json' % region)
        data = json.load(open(act_path)) if os.path.exists(act_path) else []
        data.append({"uid": uid, "account_id": str(g.account_id), "region": region,
                     "gld_via": gld_via, "choose_region_bound": bound,
                     "online": g.online, "chat": g.chat,
                     "server_time": int(g.server_time) if g.server_time else 0,
                     "ak": ml_res.ak.hex() if ml_res.ak else "",
                     "aiv": ml_res.aiv.hex() if ml_res.aiv else "",
                     "client_version": used_version,
                     "date": time.strftime("%Y-%m-%d %H:%M:%S")})
        json.dump(data, open(act_path, "w"), indent=1)
    except Exception:
        pass
    return g


# ================= PRE-LOGIN =================
def pre_login(access_token, open_id, region, proxy=None):
    """
    Game flow pre-login step.

    Behaviour differs per backend:
      * ppmainecoonghj (IND)  -> 404 account_not_found  (expected for new guest)
      * ggpolarbear / ggbluefox / us.freefiremobile
                              -> 200 with empty body, or 403, or 404
    New guest is "ready to register" when the server acknowledges the UID.
    Only 401 (auth error) or 5xx (server broken) is a hard failure.
    """
    try:
        cfg = REGION_CFG.get(region, REGION_CFG["IND"])
        dev = pick_device_64()
        req = build_majorlogin(open_id, access_token, CLIENT_VERSION, dev, region, cfg)
        hdrs = dict(ML_HEADERS)
        hdrs["X-Ga-Sv"] = str(int(time.time()))
        r = requests.post(cfg["major_login"], data=aes_encrypt(req.SerializeToString()),
                          headers=hdrs, verify=False, timeout=20, proxies=proxy)
        if r.status_code in (200, 403, 404):
            print("  [pre-login] status %d = OK for new guest (%s)" % (r.status_code, region))
            return True
        print("  [pre-login] unexpected status %d — continuing anyway" % r.status_code)
        return True  # never block registration on pre-login alone
    except Exception as e:
        print(f"  [pre-login] error (ignored): {str(e)[:60]}")
        return True


# ================= MAJOR REGISTER =================
FIELD22_HEX = "4747524501010100820200009d283d08a36a38080deb9680c3a859eba28cc138744106dfb3776b430fd0687738de73519c350b7c95904f732e6b5dea29a5cecd8bca714180bfed617e2d861d39d0f229bbb7fc6012d28f2a49c94099195a952aca2e099092b33bf28184a96acc3a3f3dd18eab8a8630220da99164058e7e31ff68e743c834ee8cba64dd78235c30aed41a88d7e9ff79512b0d880ac821ffa6a19e5492d878d3d705328bb0d19f7d8634af88e4147bb2c5f3a8c5d5fa02c9699f42cca6486cd14bdc07265b172a2bd8aee9b5559e7085fb81a2e2feee8173bd18565984a0f0a6b14e7063f51307702bec1bbbba02b5c240513e36c61614d6175461e23bbf1105d9c893d949aa9458cb91542b3af2910633ddf7fb92b1cce1897a53c51ba6fcff8bf562e9e431e8a64deac3caad7f7fb618a5ecb51f6e08132703cb9c1255b4320b27902de3e66359e559ef38a160a99ea351688b5c2df94b5f2fff4e9275a347666c85cf0aa0e2556ecc993ebf5934a7e8791063e138ec138f152496b4ecce1306d5b67d2cb057746688f143ed54af4d348b64b8cfcb30985985ff6bce609d1274130e5e407bf93084e20062294262175addf2281812ae2a566a8a057aa90fc64d06b327eebd07e35cc27551a3321668c274dac8e55165bcb58d85c5a4b2c0fa62e0ad84e371663682452d018210727f91a16f2a68980e89c5eb6a7147f2deab47d434b26de2a291dd6ebe6234539d11e08d9be3ba1f4653bfa36826d4279feca14d6bd68042bdc506674e81caa78d43c4b2827fc54d7e4a083693904524612a94322f638f6a9e3220a5e39a1599ef0f8d19e641eaadb5087aa0eaef9830d83f1231f0813ac35514ddbf2dd7eee6d05b9b1f42f2ab310635e52af198c0540746c6011f8fcba0e7152bd443abe8d85b0fc52c938410fb9cb85fe72acf03c2bd5731d4279160493f52702b0cf0300b4aa9"

KEYSTREAM = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
             0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]

def MajReg(access_token, open_id, name, region, proxy=None):
    cfg = REGIONS[region]
    host = cfg["host"]
    url = f"https://{host}/MajorRegister"

    encoded_open_id = ""
    for i, ch in enumerate(open_id):
        encoded_open_id += chr(ord(ch) ^ KEYSTREAM[i % len(KEYSTREAM)])
    field14_enc = encoded_open_id.encode('latin1')

    payload_fields = {
        1: name,
        2: access_token,
        3: open_id,
        5: 102000007,
        6: 4,
        7: 1,
        8: 4,
        13: 1,
        14: field14_enc,
        15: cfg["lang"],
        16: 1,
        20: CLIENT_VERSION,
        21: 1,
        22: bytes.fromhex(FIELD22_HEX),
    }
    proto_bytes = CrPro(payload_fields)
    payload = bytes.fromhex(EnAes(proto_bytes.hex()))

    headers = {
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*",
        "X-GA-SV": str(int(time.time())),
        "Authorization": "Bearer",
        "X-GA": "v1 1",
        "ReleaseVersion": RELEASE_VERSION,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": UNITY_VERSION,
        "Host": host,
        "Connection": "Keep-Alive",
    }
    return requests.post(url, headers=headers, data=payload, verify=False, timeout=15, proxies=proxy)

# ================= SAVE =================
def save_account(region, entry):
    fn = os.path.join(OUT_DIR, f"accounts-{region}.json")
    try:
        data = json.load(open(fn)) if os.path.exists(fn) else []
    except Exception:
        data = []
    data.append(entry)
    tmp = fn + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, fn)

# ================= ACTIVATE =================
def activate_now(uid, password, region):
    if region not in REGION_CFG:
        region = "IND"
    cfg = REGION_CFG[region]
    try:
        g = run_getlogindata(uid, password, cfg["major_login"], cfg["get_login_data"],
                             CLIENT_VERSION, next_index("RBC_GETLOGINDATA"), region, cfg)
        if g is not None:
            print("  \u26a1 ACTIVATED | uid=%s | account=%s | online=%s | chat=%s" % (
                uid, g.account_id, g.online, g.chat))
            return True
        print("  [!] activation failed (network/region) — account saved, retry with activator")
    except Exception as e:
        print("  [!] activation error: %s" % str(e)[:80])
    return False


# ================= GENERATE ONE =================
def generate_one(region):
    proxy = get_proxy()
    name = next_name()
    uid, password, sig = Reg(proxy)
    access_token, open_id = Accs(uid, password, proxy)
    pre_login(access_token, open_id, region, proxy)
    resp = MajReg(access_token, open_id, name, region, proxy)

    account_id = "N/A"
    raw_note = ""
    if resp.status_code == 200 and resp.content:
        try:
            aid = PbFirstVarint(resp.content, 3)
            if aid:
                account_id = str(aid)
            else:
                try:
                    txt = resp.content.decode("utf-8", "ignore")
                    raw_note = txt if txt.isprintable() else resp.content.hex()[:60]
                except Exception:
                    raw_note = resp.content.hex()[:60]
        except Exception:
            pass

    if resp.status_code == 200 and account_id == "N/A":
        status = "REGISTER REJECTED (soft-fail)"
    elif resp.status_code == 200:
        status = "200 OK"
    else:
        status = f"{resp.status_code} FAIL"
    reg_ok = (resp.status_code == 200 and account_id != "N/A")
    with STATS_LOCK:
        if reg_ok:
            STATS["ok"] += 1
        else:
            STATS["fail"] += 1
        cur, ok, fail = STATS["ok"] + STATS["fail"], STATS["ok"], STATS["fail"]

    lines = [
        "=" * 52,
        f"[+] {status} | #{cur} (ok={ok} fail={fail})",
        f"[+] Region     : {region} ({REGIONS[region]['backend']})",
        f"[+] Name       : {name}",
        f"[+] UID        : {uid}",
        f"[+] Account ID : {account_id}",
        f"[+] Password   : {password}",
        f"[+] Open ID    : {open_id}",
        f"[+] Token      : {access_token}",
        "=" * 52,
    ]
    if resp.status_code == 200 and account_id != "N/A":
        save_account(region, {
            "uid": uid, "password": password, "name": name,
            "account_id": account_id, "open_id": open_id,
            "access_token": access_token, "region": region,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    if AUTO_ACTIVATE and reg_ok:
        activate_now(uid, password, region)
    elif account_id == "N/A":
        lines.append("[!] SERVER NE ACCOUNT BANAYA HI NAHI (register soft-reject)")
        lines.append("[!] resp: " + (raw_note or resp.content[:60].hex()))
        lines.append("[!] causes: (a) duplicate nickname")
        lines.append("[!]          (b) f22 flag")
        lines.append("[!]          (c) pre-login step missing")
    else:
        lines.append(f"[!] Body: {resp.content[:120]!r}")
    return "\n".join(lines)

# ================= MAIN =================
def pick_region():
    print("\n  Regions:")
    codes = REGION_ORDER
    for i in range(0, len(codes), 6):
        print("    " + "  ".join(f"{c:<4}" for c in codes[i:i+6]))
    print("    ALL   (round-robin all regions)")
    while True:
        r = input("\n  ➤ Region (Enter=IND, ALL=round-robin): ").strip().upper()
        if not r:
            r = "IND"
        if r == "ALL":
            return "ALL"
        if r in REGIONS:
            c = REGIONS[r]
            print(f"  ✓ {r} → {c['host']} (lang={c['lang']})")
            return r
        print(f"  [!] '{r}' nahi hai — list me se choose kar")

# ══════════════════ GENERATION ENGINE ══════════════════
GEN_RESULTS = []
GEN_STATE = {"target": 0, "ok": 0, "running": False, "region": "", "started": 0.0}
GEN_LOCK = threading.Lock()
_RR_LOCK = threading.Lock()
_RR_INDEX = [0]


def _next_rr_region():
    """Thread-safe round-robin region picker for ALL mode."""
    with _RR_LOCK:
        r = ROUND_ROBIN_REGIONS[_RR_INDEX[0] % len(ROUND_ROBIN_REGIONS)]
        _RR_INDEX[0] += 1
        return r


def _generate_one_quiet(region, prefix):
    if region == "ALL":
        region = _next_rr_region()
    try:
        proxy = get_proxy()
        uid, password, sig = Reg(proxy)
        access_token, open_id = Accs(uid, password, proxy)
        pre_login(access_token, open_id, region, proxy)
        name = next_name(prefix)
        resp = MajReg(access_token, open_id, name, region, proxy)
        account_id = "N/A"
        if resp.status_code == 200 and resp.content:
            try:
                aid = PbFirstVarint(resp.content, 3)
                if aid:
                    account_id = str(aid)
            except Exception:
                pass
        if resp.status_code != 200 or account_id == "N/A":
            return None
        acc = {"uid": uid, "password": password, "name": name,
               "account_id": account_id, "open_id": open_id,
               "access_token": access_token, "region": region,
               "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        try:
            save_account(region, acc)
        except Exception:
            pass
        return acc
    except Exception:
        return None

def generate_accounts(region, count, prefix="RBC", auto_activate=False):
    with GEN_LOCK:
        if GEN_STATE["running"]:
            return None
        GEN_STATE.update({"target": count, "ok": 0, "running": True,
                          "region": region, "started": time.time()})
        GEN_RESULTS.clear()
    max_attempts = count * 5 + 20
    attempts = [0]

    def worker():
        while True:
            with GEN_LOCK:
                if GEN_STATE["ok"] >= count or attempts[0] >= max_attempts:
                    break
                attempts[0] += 1
            acc = _generate_one_quiet(region, prefix)
            if acc:
                GEN_RESULTS.append(acc)
                with GEN_LOCK:
                    GEN_STATE["ok"] += 1
                    n = GEN_STATE["ok"]
                print("[+] Account #%d/%d | region=%s | uid=%s | id=%s | name=%s" %
                      (n, count, acc["region"], acc["uid"], acc["account_id"], acc["name"]),
                      flush=True)
                if auto_activate:
                    try:
                        activate_now(acc["uid"], acc["password"], acc["region"])
                    except Exception:
                        pass

    threads = []
    for _ in range(max(1, min(THREADS, count))):
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    with GEN_LOCK:
        GEN_STATE["running"] = False
    return list(GEN_RESULTS)


# ══════════════════ WEB UI ══════════════════
GENUI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RBC GUEST GENERATOR</title>
<style>
:root{--bg:#0b0f17;--bg2:#131a26;--bg3:#1b2433;--fg:#e6edf3;--fg2:#8b98a8;--on:#4ade80;--cyan:#22d3ee;--red:#f87171;--border:#243044}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--fg);font-size:14px}
header{padding:14px 18px;background:var(--bg2);border-bottom:1px solid var(--border)}
h1{font-size:16px;color:var(--on)}
.sub{color:var(--fg2);font-size:11px;margin-top:3px}
nav{display:flex;background:var(--bg2);border-bottom:1px solid var(--border)}
nav button{flex:1;padding:12px;background:none;border:none;color:var(--fg2);font-weight:600;font-size:12px;border-bottom:2px solid transparent;cursor:pointer}
nav button.active{color:var(--on);border-bottom-color:var(--on)}
main{padding:16px;max-width:820px;margin:0 auto}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:14px}
label{display:block;font-size:11px;color:var(--fg2);margin:10px 0 6px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
input,select{width:100%;padding:11px 13px;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:9px;font-size:13px;font-family:ui-monospace,monospace;outline:none}
input:focus,select:focus{border-color:var(--on)}
.btn{display:inline-block;padding:11px 20px;background:var(--on);color:#0b0f17;border:none;border-radius:9px;font-weight:700;font-size:13px;cursor:pointer;font-family:inherit}
.btn.sec{background:var(--bg3);color:var(--fg)}
.row{display:flex;gap:10px;flex-wrap:wrap}
.row>*{flex:1;min-width:140px}
.pane{display:none}.pane.active{display:block}
.bar{height:10px;background:var(--bg3);border-radius:6px;overflow:hidden;margin:12px 0 6px}
.bar>div{height:100%;background:var(--on);width:0%;transition:width .4s}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.stat{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:10px 16px;min-width:110px}
.stat .v{font-size:20px;font-weight:700;font-family:ui-monospace,monospace;color:var(--on)}
.stat .l{font-size:10px;color:var(--fg2);text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
table{width:100%;border-collapse:collapse;background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;font-size:12px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--border);font-family:ui-monospace,monospace;font-size:11.5px}
th{background:var(--bg3);color:var(--fg2);font-size:10px;text-transform:uppercase;letter-spacing:.5px}
.result{background:var(--bg);border:1px solid var(--border);border-radius:9px;padding:12px;font-family:ui-monospace,monospace;font-size:11px;white-space:pre-wrap;word-break:break-all;max-height:340px;overflow:auto;line-height:1.6;margin-top:10px}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(120px);background:var(--bg3);padding:11px 22px;border-radius:26px;font-weight:600;transition:transform .3s;border:1px solid var(--border);z-index:99}
.toast.show{transform:translateX(-50%) translateY(0)}
.empty{text-align:center;padding:30px;color:var(--fg2)}
</style>
</head>
<body>
<header>
  <h1>⚡ RBC GUEST GENERATOR v3.2 — ALL REGIONS</h1>
  <div class="sub">16 regions selectable &middot; ALL round-robin &middot; JWT fetch &middot; auto-activate</div>
</header>
<nav>
  <button data-tab="gen" class="active">Generate</button>
  <button data-tab="jwt">JWT Fetch</button>
</nav>
<main>
<section class="pane active" id="pane-gen">
  <div class="stats">
    <div class="stat"><div class="v" id="st-ok">0</div><div class="l">Generated</div></div>
    <div class="stat"><div class="v" id="st-target">0</div><div class="l">Target</div></div>
    <div class="stat"><div class="v" id="st-state">idle</div><div class="l">Status</div></div>
  </div>
  <div class="card">
    <div class="row">
      <div><label>Region</label><select id="g-region"></select></div>
      <div><label>Count</label><input id="g-count" type="number" value="1" min="1" max="500"></div>
      <div><label>Name prefix</label><input id="g-prefix" value="RBC" maxlength="12"></div>
    </div>
    <label style="display:flex;align-items:center;gap:8px;text-transform:none;font-size:13px;color:var(--fg)">
      <input type="checkbox" id="g-auto" style="width:auto"> Auto-activate after generation
    </label>
    <div style="margin-top:14px;display:flex;gap:8px">
      <button class="btn" id="g-start">▶ Generate</button>
    </div>
    <div class="bar"><div id="g-bar"></div></div>
    <div style="font-size:11px;color:var(--fg2)" id="g-note">Failures are retried automatically — only successful accounts are shown.</div>
  </div>
  <table>
    <thead><tr><th>#</th><th>Region</th><th>UID</th><th>Account ID</th><th>Name</th><th>Password</th><th>Time</th></tr></thead>
    <tbody id="g-rows"><tr><td colspan="7" class="empty">No accounts yet — set region &amp; count, then press Generate.</td></tr></tbody>
  </table>
</section>
<section class="pane" id="pane-jwt">
  <div class="card">
    <div class="row">
      <div><label>UID (garena)</label><input id="j-uid" placeholder="8000000000"></div>
      <div><label>Password</label><input id="j-pass" placeholder="password"></div>
      <div><label>Region</label><select id="j-region"></select></div>
    </div>
    <div style="margin-top:14px"><button class="btn" id="j-go">Fetch JWT</button></div>
    <div class="result" id="j-out" style="display:none"></div>
  </div>
</section>
</main>
<div class="toast" id="toast"></div>
<script>
var $=function(s){return document.querySelector(s)};
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function toast(m){var t=$('#toast');t.textContent=m;t.classList.add('show');setTimeout(function(){t.classList.remove('show')},2200)}
document.querySelectorAll('nav button').forEach(function(b){b.addEventListener('click',function(){
  document.querySelectorAll('nav button').forEach(function(x){x.classList.remove('active')});
  document.querySelectorAll('.pane').forEach(function(x){x.classList.remove('active')});
  b.classList.add('active');$('#pane-'+b.dataset.tab).classList.add('active')})});
fetch('/api/regions').then(function(r){return r.json()}).then(function(regs){
  var h=regs.map(function(r){return '<option>'+r+'</option>'}).join('');
  $('#g-region').innerHTML=h;$('#j-region').innerHTML=h});
$('#g-start').addEventListener('click',function(){
  var b=$('#g-start');b.disabled=true;
  fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    region:$('#g-region').value,count:parseInt($('#g-count').value||'1'),
    prefix:$('#g-prefix').value||'RBC',auto_activate:$('#g-auto').checked})})
  .then(function(r){return r.json()}).then(function(d){
    if(d.error){toast(d.error);}else{toast('Generation started ('+d.region+' x '+d.count+')')}
    b.disabled=false});
});
setInterval(function(){
  fetch('/api/stats').then(function(r){return r.json()}).then(function(s){
    $('#st-ok').textContent=s.ok;$('#st-target').textContent=s.target;
    $('#st-state').textContent=s.running?'RUNNING':'idle';
    $('#g-bar').style.width=(s.target?Math.min(100,s.ok/s.target*100):0)+'%'});
  fetch('/api/accounts').then(function(r){return r.json()}).then(function(list){
    var tb=$('#g-rows');
    if(!list.length){tb.innerHTML='<tr><td colspan="7" class="empty">No accounts yet.</td></tr>';return}
    tb.innerHTML=list.map(function(a,i){
      return '<tr><td>'+(i+1)+'</td><td>'+esc(a.region)+'</td><td>'+esc(a.uid)+'</td><td>'+esc(a.account_id)+'</td><td>'+esc(a.name)+'</td><td>'+esc(a.password)+'</td><td>'+esc(a.date)+'</td></tr>'}).join('')});
},1500);
$('#j-go').addEventListener('click',function(){
  var out=$('#j-out');out.style.display='block';out.textContent='Fetching...';
  fetch('/api/jwt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    uid:$('#j-uid').value.trim(),password:$('#j-pass').value.trim(),region:$('#j-region').value})})
  .then(function(r){return r.json()}).then(function(d){
    if(d.error){out.innerHTML='<span style="color:var(--red)">✗ '+esc(d.error)+'</span>';return}
    out.innerHTML='<span style="color:var(--on)">✓ account_id: '+esc(d.account_id)+' | region: '+esc(d.region)+'</span>\n\nAK  : '+esc(d.ak)+'\nAIV : '+esc(d.aiv)+'\n\nJWT :\n'+esc(d.jwt)});
});
</script>
</body>
</html>"""


class _GenUIHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, ctype="application/json"):
        if isinstance(obj, str):
            body = obj.encode()
        elif isinstance(obj, bytes):
            body = obj
        else:
            body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(GENUI_HTML, ctype="text/html; charset=utf-8")
        elif self.path == "/api/stats":
            with GEN_LOCK:
                st = dict(GEN_STATE)
            st["accounts"] = len(GEN_RESULTS)
            self._send(st)
        elif self.path == "/api/accounts":
            self._send(list(GEN_RESULTS))
        elif self.path == "/api/regions":
            # expose ALL sentinel + every real region
            self._send(["ALL"] + list(REGION_ORDER))
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0) or 0)
        try:
            data = json.loads(self.rfile.read(ln) or b"{}")
        except Exception:
            data = {}
        if self.path == "/api/generate":
            region = str(data.get("region", "IND")).upper()
            if region != "ALL" and region not in REGIONS:
                region = "IND"
            try:
                count = max(1, min(500, int(data.get("count", 1))))
            except Exception:
                count = 1
            prefix = (str(data.get("prefix", "RBC__"))[:12] or "RBC__")
            auto = bool(data.get("auto_activate"))
            with GEN_LOCK:
                if GEN_STATE["running"]:
                    self._send({"error": "generation already running"}, 400)
                    return
            threading.Thread(target=generate_accounts,
                             args=(region, count, prefix, auto), daemon=True).start()
            self._send({"ok": True, "region": region, "count": count})
        elif self.path == "/api/jwt":
            uid = str(data.get("uid", "")).strip()
            pw = str(data.get("password", "")).strip()
            region = str(data.get("region", "IND")).upper()
            if region == "ALL":
                region = "IND"   # ALL isn't meaningful for a single JWT fetch
            if not uid or not pw:
                self._send({"error": "uid and password are required"}, 400)
                return
            try:
                cfg = REGION_CFG.get(region, REGION_CFG["IND"])
                res = run_majorlogin(uid, pw, cfg["major_login"], CLIENT_VERSION,
                                     next_index("RBC_MAJORLOGIN"), region, cfg)
                if res is None:
                    self._send({"error": "login failed — check credentials / network"}, 400)
                    return
                self._send({"ok": True, "account_id": str(res.account_id),
                            "region": res.lock_region or res.noti_region or "",
                            "ak": res.ak.hex() if res.ak else "",
                            "aiv": res.aiv.hex() if res.aiv else "",
                            "jwt": res.token})
            except Exception as e:
                self._send({"error": str(e)[:120]}, 400)
        else:
            self._send({"error": "not found"}, 404)


def start_gen_web(port=8899):
    for p in range(port, port + 10):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), _GenUIHandler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return p
        except OSError:
            continue
    return None


def main(count=None, region=None, serve=True):
    print("=" * 58)
    print("  RBC GUEST GENERATOR v3.2 — ALL REGIONS")
    print("=" * 58)
    print("  Mode    : CLI — browser access via RBC AIO CAPTURE Web UI")
    print("  Devices : %s" % pool_status())
    print("  Version : %s (fallbacks: %s)" % (CLIENT_VERSION, ", ".join(CLIENT_VERSION_FALLBACKS)))
    print("  Regions : %s" % ", ".join(REGION_ORDER))
    print("  CLI     : python gen.py gen COUNT REGION [y]  (REGION may be ALL)")
    print()
    if region is not None:
        if region != "ALL" and region not in REGIONS:
            print("  [!] Unknown region %s — using IND" % region)
            region = "IND"
        if count is None:
            count = 1
        print("  Generating %d account(s) | region=%s\n" % (count, region))
        generate_accounts(region, count, "RBC__", AUTO_ACTIVATE)
        return
    try:
        region = pick_region()
        try:
            count = int(input("  Count: ").strip() or "1")
        except Exception:
            count = 1
        aa = input("  Auto-activate? [y/N]: ").strip().lower() in ("y", "yes")
        print()
        generate_accounts(region, count, "RBC__", aa)
    except (EOFError, KeyboardInterrupt):
        pass
    return

if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1].lower() == "jwt":
        uid, pw = sys.argv[2], sys.argv[3]
        region = sys.argv[4].upper() if len(sys.argv) > 4 else "IND"
        if region == "ALL":
            region = "IND"
        cfg = REGION_CFG.get(region, REGION_CFG["IND"])
        res = run_majorlogin(uid, pw, cfg["major_login"], CLIENT_VERSION,
                             next_index("RBC_MAJORLOGIN"), region, cfg)
        if res:
            print("\n======== JWT ========")
            print("account_id : %s" % res.account_id)
            print("region     : %s" % (res.lock_region or res.noti_region))
            print("ak         : %s" % (res.ak.hex() if res.ak else ""))
            print("aiv        : %s" % (res.aiv.hex() if res.aiv else ""))
            print("jwt        :\n%s" % res.token)
            try:
                with open("jwt_%s.txt" % uid, "w") as f:
                    f.write("uid=%s\npassword=%s\naccount_id=%s\njwt=%s\nak=%s\naiv=%s\n" % (
                        uid, pw, res.account_id, res.token,
                        res.ak.hex() if res.ak else "", res.aiv.hex() if res.aiv else ""))
                print("\nsaved: jwt_%s.txt" % uid)
            except Exception:
                pass
        sys.exit(0 if res else 1)
    if len(sys.argv) >= 3 and sys.argv[1].lower() == "gen":
        try:
            count = max(1, int(sys.argv[2]))
        except Exception:
            count = 1
        region = sys.argv[3].upper() if len(sys.argv) > 3 else "IND"
        AUTO_ACTIVATE = len(sys.argv) > 4 and sys.argv[4].lower() in ("y", "yes", "auto")
        main(count=count, region=region, serve=False)
        sys.exit(0)
    main()