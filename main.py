#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import sys, json, time, asyncio, subprocess, uuid, signal, shutil
import urllib.parse, urllib.request, urllib.error
from typing import List, Dict, Optional
from aiohttp import web

# ═══════════════ CONFIG & CONSTANTS ═══════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GUILD_INFO_API_IND = "https://star-guild-info.lovable.app/api/public/info"
GUILD_INFO_API_OTHER = "https://danger-guild-management-web.vercel.app/guild"
GUILD_JOIN_API = "https://danger-guild-management-web.vercel.app/join"
GUILD_MEMBERS_API = "https://danger-guild-management-web.vercel.app/members"
BIO_API = "https://star-bio-api.lovable.app/api/public/bio-upload"

GEN_FILE = os.path.join(BASE_DIR, "gen.py")
MAIN_FILE = os.path.join(BASE_DIR, "app.py")
GEN_OUT_DIR = os.path.join(BASE_DIR, "RBC1_GENS")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates") # NEW
DB_FILE = os.path.join(BASE_DIR, "glory_groups.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
USERS_FILE = os.path.join(BASE_DIR, "users.json")
MANUAL_ACCS_FILE = os.path.join(BASE_DIR, "manual_accounts.json")
COUPONS_FILE = os.path.join(BASE_DIR, "coupons.json")
os.makedirs(RUNTIME_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

VALID_REGIONS = ["IND","BD","ME","TH","ID","VN","PK","TW","CIS","RU","SAC","BR","EU","SG","NA","US"]
ADMIN_SECRET_PATH = "/admin-Uok7971Yy2"

WEB_HOST = os.environ.get("RBC_WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("PORT", os.environ.get("RBC_WEB_PORT", "26215")))
DEFAULT_REGION = os.environ.get("RBC_GEN_REGION", "IND").upper()
DEFAULT_PASSWORD = "RBC__"

SETTINGS = {
    "goal_hours": 8,
    "bot_count": 4,
    "bot_name_prefix": "BSL_",
    "bio_text": "Ｂ Ｉ Ｓ Ｈ Ａ Ｌ Ｇ Ｌ Ｏ Ｒ Ｙ",
    "max_launches": 10,
    "auto_restart_mins": 15,
    "join_retry_rounds": 5,
    "approval_wait_secs": 120,
    "member_check_secs": 8,
    "glory_refresh_secs": 60,
    "credit_per_launch": 1
}

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: return default
    return default

def save_json(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp, path)
    except Exception as e:
        print(f"save error {path}: {e}")

# Load initial data
SETTINGS.update(load_json(SETTINGS_FILE, {}))
GROUPS_DB = load_json(DB_FILE, {})
USERS_DB = load_json(USERS_FILE, {})
MANUAL_ACCOUNTS = load_json(MANUAL_ACCS_FILE, {})
COUPONS_DB = load_json(COUPONS_FILE, {})

# Default Admin Account
if not USERS_DB:
    USERS_DB["admin"] = {"username": "admin", "password": "admin", "is_admin": True, "credits": 9999, "groups": []}
    save_json(USERS_FILE, USERS_DB)

GLOBAL_STATS = {
    "bots_total": 0, "bots_online": 0, "matches_started": 0,
    "total_gained_exp": 0, "total_glory_pushed": 0, "started_at": time.time(),
}

def group_dir(gid): d = os.path.join(RUNTIME_DIR, gid); os.makedirs(d, exist_ok=True); return d
def group_accounts_path(gid): return os.path.join(group_dir(gid), "accounts.json")
def group_log_path(gid): return os.path.join(group_dir(gid), "engine.log")
def group_accounts_meta_path(gid): return os.path.join(group_dir(gid), "accounts_meta.json")

# ═══════════════ HTTP & APIS ═══════════════
def _http_get_json(url, timeout=20, no_cache=False):
    hdrs = {"User-Agent": "RBC-GLORY/30", "Accept": "application/json"}
    if no_cache:
        hdrs["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try: return resp.status, json.loads(body), body
            except Exception: return resp.status, None, body
    except urllib.error.HTTPError as e:
        try: body = e.read().decode("utf-8", errors="replace")
        except Exception: body = ""
        return e.code, None, body
    except Exception as e:
        return 0, None, str(e)

def fetch_guild_info(guild_id, region="IND"):
    if region.upper() == "IND":
        url = f"{GUILD_INFO_API_IND}?clan_id={guild_id}&region={region}"
        code, js, _ = _http_get_json(url, timeout=15, no_cache=True)
        if code == 200 and isinstance(js, dict) and js.get("status") == "success" and not js.get("error_code"):
            return _parse_old_guild_api(js, guild_id, region)
        
        url2 = f"{GUILD_INFO_API_OTHER}?guild_id={guild_id}&region={region}"
        code2, js2, _ = _http_get_json(url2, timeout=15, no_cache=True)
        if code2 == 200 and isinstance(js2, dict) and js2.get("status") == "success":
            return _parse_new_guild_api(js2)
        return None
    else:
        url = f"{GUILD_INFO_API_OTHER}?guild_id={guild_id}&region={region}"
        code, js, _ = _http_get_json(url, timeout=15, no_cache=True)
        if code == 200 and isinstance(js, dict) and js.get("status") == "success":
            return _parse_new_guild_api(js)
        return None

def _parse_old_guild_api(js, guild_id, region):
    return {
        "guild_name": js.get("clan_name") or f"Guild {guild_id}",
        "guild_id": str(js.get("clan_id") or guild_id),
        "guild_level": int(js.get("guild_level") or 1),
        "region": region,
        "leader_id": str(js.get("guild_leader_id") or ""),
        "leader_name": "",
        "slogan": str(js.get("guild_bio") or ""),
        "bio": str(js.get("guild_bio") or ""),
        "current_members": int(js.get("current_members") or 0),
        "max_members": int(js.get("total_members") or 35),
        "members_online": int(js.get("members_online") or 0),
        "total_glory": int(js.get("glory_points") or js.get("score") or 0),
        "weekly_glory": 0,
        "activity_points": int(js.get("guild_activity_points") or 0),
        "rank": int(js.get("rank") or 0),
        "auto_approval": True, 
    }

def _parse_new_guild_api(js):
    leader = js.get("GuildLeader") or {}
    auto_app = str(js.get("AutoApprovalStatus", "ON")).upper() == "ON"
    return {
        "guild_name": js.get("GuildName") or "Unknown",
        "guild_id": str(js.get("GuildId") or ""),
        "guild_level": int(js.get("GuildLevel") or 1),
        "region": js.get("GuildRegion") or "",
        "leader_id": str(leader.get("Uid") or ""),
        "leader_name": str(leader.get("Name") or "Unknown"),
        "slogan": str(js.get("GuildSlogan") or ""),
        "bio": str(js.get("GuildSlogan") or ""),
        "current_members": int(js.get("CurrentMembers") or 0),
        "max_members": int(js.get("MaxMembers") or 35),
        "members_online": 0,
        "total_glory": int(js.get("TotalActivityPoints") or 0),
        "weekly_glory": int(js.get("WeeklyActivityPoints") or 0),
        "activity_points": int(js.get("TotalActivityPoints") or 0),
        "rank": 0,
        "auto_approval": auto_app,
    }

def get_member_count(guild_id, region):
    info = fetch_guild_info(guild_id, region)
    return info["current_members"] if info else -1

def fetch_guild_members(guild_id, uid, password):
    params = urllib.parse.urlencode({"guild_id": guild_id, "uid": uid, "password": password})
    url = f"{GUILD_MEMBERS_API}?{params}"
    code, js, body = _http_get_json(url, timeout=20, no_cache=True)
    if code != 200 or not isinstance(js, dict) or not js.get("success"):
        return None
    
    members = js.get("members") or []
    out = {}
    for m in members:
        try:
            u = str(m.get("uid") or "")
            if not u: continue
            total_glory = int(m.get("totalGlory") or 0)
            weekly_glory = int(m.get("weeklyGlory") or 0)
            out[u] = {
                "nickname": m.get("nickname", ""),
                "uid": u,
                "totalGlory": total_glory,
                "weeklyGlory": weekly_glory,
                "level": int(m.get("level") or 1),
                "role": m.get("role", "Member"),
            }
        except Exception:
            continue
    return out

def _fetch_members_for_group(gid: str) -> Optional[dict]:
    g = GROUPS_DB.get(gid)
    if not g: return None
    accounts = g.get("accounts") or []
    if not accounts: return None
    reader = accounts[0]
    guild_id = g.get("guild_id")
    uid = reader.get("uid")
    pw = reader.get("password")
    if not (guild_id and uid and pw): return None
    return fetch_guild_members(guild_id, uid, pw)

def send_join(guild_id, uid, password, region):
    params = urllib.parse.urlencode({"guild_id": guild_id, "uid": uid, "password": password, "region": region})
    req = urllib.request.Request(f"{GUILD_JOIN_API}?{params}", headers={"User-Agent": "RBC-GLORY/30"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                js = json.loads(body)
                msg = str(js.get("message") or js.get("error") or "OK")
                ml = msg.lower(); st = str(js.get("status", "")).lower()
                if js.get("success") is False or "error" in ml: return False, msg[:140]
                if st in ("failed","failure","error","invalid"): return False, f"{st}: {msg}"[:140]
                if "already" in ml or "pending" in ml or "request" in ml: return True, f"request_sent: {msg}"[:140]
                if js.get("success") is True or st in ("ok","success","joined"): return True, msg[:140]
                return 200 <= resp.status < 300, msg[:140]
            except Exception:
                return 200 <= resp.status < 300, "OK"
    except Exception as e:
        return False, str(e)[:140]

def send_bio(uid, password):
    params = urllib.parse.urlencode({"bio": SETTINGS["bio_text"], "uid": uid, "password": password})
    req = urllib.request.Request(f"{BIO_API}?{params}", headers={"User-Agent": "RBC-GLORY/30"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False

def run_gen(count, region):
    if not os.path.exists(GEN_FILE): return False
    env = os.environ.copy()
    env["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
    args = [sys.executable, GEN_FILE, "gen", str(count), region, "y"]
    try:
        proc = subprocess.run(args, cwd=BASE_DIR, env=env, timeout=60, capture_output=True, text=True)
        for line in proc.stdout.split("\n"):
            if line.strip(): print(f"    │ {line}")
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  [GEN] ❌ Timeout after 60s. Killing process...")
        return False
    except Exception as e:
        print(f"gen error: {e}"); return False

def load_generated(region):
    path = os.path.join(GEN_OUT_DIR, f"accounts-{region.upper()}.json")
    if not os.path.exists(path): return []
    try:
        with open(path) as f: raw = json.load(f)
    except Exception: return []
    out = []
    for a in raw if isinstance(raw, list) else []:
        if isinstance(a, dict):
            u = str(a.get("uid") or a.get("account_id") or "").strip()
            p = str(a.get("password") or "").strip()
            if u and p:
                out.append({"uid": u, "password": p, "name": str(a.get("name") or "").strip(), "account_id": str(a.get("account_id") or "").strip()})
    return out

def write_group_accounts(gid, accounts):
    path = group_accounts_path(gid)
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([{"uid": a["uid"], "password": a["password"]} for a in accounts], f, indent=1)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[{gid}] accounts write error: {e}"); return False
    try:
        meta_tmp = group_accounts_meta_path(gid) + ".tmp"
        with open(meta_tmp, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=1)
        os.replace(meta_tmp, group_accounts_meta_path(gid))
    except Exception as e:
        print(f"[{gid}] meta write error: {e}")
    return True

def start_engine_for_group(gid):
    if not os.path.exists(MAIN_FILE): return None, "app.py not found"
    env = os.environ.copy()
    env["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
    env["RBC_SKIP_WEB"] = "1"
    env["RBC_ACCOUNTS_FILE"] = group_accounts_path(gid)
    env["RBC_GROUP_ID"] = gid
    try:
        log_fh = open(group_log_path(gid), "ab", buffering=0)
        kwargs = {"cwd": group_dir(gid), "env": env, "stdout": log_fh, "stderr": subprocess.STDOUT}
        if sys.platform != "win32":
            try: kwargs["preexec_fn"] = os.setsid
            except Exception: pass
        proc = subprocess.Popen([sys.executable, MAIN_FILE], **kwargs)
        return proc, None
    except Exception as e:
        return None, str(e)

def stop_engine_process(proc):
    if not proc: return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill","/F","/T","/PID",str(proc.pid)], capture_output=True)
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                time.sleep(1)
                try: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception: pass
            except Exception: proc.kill()
    except Exception:
        try: proc.kill()
        except Exception: pass

# ═══════════════ WORKERS ═══════════════
async def _auto_restart_loop():
    while True:
        try:
            auto_mins = SETTINGS.get("auto_restart_mins", 15)
            if auto_mins > 0:
                await asyncio.sleep(auto_mins * 60)
                for gid, g in list(GROUPS_DB.items()):
                    if g.get("status") == "RUNNING":
                        proc = g.get("engine_proc")
                        if proc: 
                            stop_engine_process(proc)
                            g["engine_proc"] = None
                            g["engine_pid"] = None
                            await asyncio.sleep(2)
                        
                        saved = [{"uid":a["uid"],"password":a.get("password",DEFAULT_PASSWORD),"name":a.get("name",""),"account_id":a.get("account_id","")} for a in g.get("accounts", []) if a.get("uid")]
                        if not saved: continue
                        
                        write_group_accounts(gid, saved)
                        new_proc, err = start_engine_for_group(gid)
                        if not err:
                            g["engine_proc"] = new_proc
                            g["engine_pid"] = new_proc.pid
                            g["stage_note"] = f"Auto-restarted ({auto_mins}m)"
                            save_json(DB_FILE, GROUPS_DB)
            else:
                await asyncio.sleep(60)
        except Exception as e:
            print(f"Auto-restart error: {e}")
            await asyncio.sleep(60)

async def create_and_join(region, guild_id, count, group):
    log = lambda m: print(f"  [RBC-GLORY] [{group.get('group_id','?')}] {m}", flush=True)
    region = region.upper() if region in VALID_REGIONS else DEFAULT_REGION
    gid = group["group_id"]
    start_time = time.time()

    def check_timeout():
        if time.time() - start_time > 600: # 10 min global timeout
            raise TimeoutError("Global task timeout (10m)")

    def set_stage(stage, note=""):
        group["stage"] = stage
        group["stage_note"] = note
        group["stage_at"] = int(time.time())
        if stage in ("GENERATING", "JOINING", "WAITING_APPROVAL", "STARTING_ENGINE"):
            group["status"] = "GENERATING"
        elif stage == "RUNNING":
            group["status"] = "RUNNING"
        elif stage == "FAILED":
            group["status"] = "FAILED"
        save_json(DB_FILE, GROUPS_DB)

    try:
        set_stage("GENERATING", f"spawning {count} guests")
        log(f"🚀 Starting generation for {count} bots...")
        
        info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_info, guild_id, region)
        if not info:
            group["error"] = "Guild API down"; set_stage("FAILED"); log("❌ Guild API down"); return
            
        initial_count = info["current_members"]
        auto_app = info.get("auto_approval", True)
        group["initial_member_count"] = initial_count
        save_json(DB_FILE, GROUPS_DB)
        log(f"ℹ️ Initial Members: {initial_count} | Auto Approval: {'ON' if auto_app else 'OFF'}")

        accs = []
        global MANUAL_ACCOUNTS
        manual_pool = MANUAL_ACCOUNTS.get(region, [])
        
        if len(manual_pool) >= count:
            log(f"📦 Using {count} accounts from Manual Store ({region})...")
            accs = manual_pool[:count]
            MANUAL_ACCOUNTS[region] = manual_pool[count:]
            save_json(MANUAL_ACCS_FILE, MANUAL_ACCOUNTS)
        else:
            log(f"⚠️ Not enough manual accounts in {region} (Found {len(manual_pool)}/{count}). Falling back to Auto-Gen...")
            retries = SETTINGS.get("join_retry_rounds", 5)
            for attempt in range(1, retries + 1):
                check_timeout()
                if GROUPS_DB.get(gid, {}).get("status") not in ("GENERATING", "RUNNING"):
                    return
                set_stage("GENERATING", f"gen attempt {attempt}/{retries}")
                log(f"⚙️ Generating guests (Attempt {attempt}/{retries})...")
                await asyncio.get_event_loop().run_in_executor(None, run_gen, count, region)
                await asyncio.sleep(1)
                accs = load_generated(region)
                if len(accs) >= count: break
                await asyncio.sleep(2)

        if not accs:
            group["error"] = "Gen failed"; set_stage("FAILED"); log("❌ Generation failed"); return
        log(f"✅ Loaded {len(accs)} accounts successfully.")

        pool = accs[-count:]
        group["pending_accounts"] = [{"uid":a["uid"],"password":a["password"],"name":a.get("name",""),"account_id":a.get("account_id",""),"status":"READY"} for a in pool]
        save_json(DB_FILE, GROUPS_DB)

        set_stage("JOINING", f"sending {len(pool)} join requests")
        log(f"📤 Sending join requests to guild {guild_id}...")
        sent_ok = 0
        for acc in pool:
            check_timeout()
            ok, msg = await asyncio.get_event_loop().run_in_executor(None, send_join, guild_id, acc["uid"], acc["password"], region)
            if ok: sent_ok += 1
            for pa in group["pending_accounts"]:
                if pa["uid"] == acc["uid"]:
                    pa["status"] = "REQUESTED" if ok else "JOIN_FAILED"
            save_json(DB_FILE, GROUPS_DB)
            await asyncio.sleep(1.5)

        set_stage("WAITING_APPROVAL", f"{sent_ok} requests sent")
        log(f"⏳ Waiting for approval ({sent_ok}/{len(pool)} sent)...")
        
        wait_start = time.time()
        joined_count = 0
        max_wait = SETTINGS.get("approval_wait_secs", 120)
        check_int = SETTINGS.get("member_check_secs", 8)
        
        if auto_app:
            await asyncio.sleep(5) 
            log(f"⚡ Auto Approval is ON. Skipping wait.")
            joined = pool
        else:
            target_count = initial_count + count
            while time.time() - wait_start < max_wait:
                check_timeout()
                if GROUPS_DB.get(gid, {}).get("status") not in ("GENERATING", "RUNNING"): return
                await asyncio.sleep(check_int)
                
                cur_info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_info, guild_id, region)
                if cur_info:
                    curr_m = cur_info["current_members"]
                    log(f"🔎 Live Check: Members {curr_m}/{target_count}")
                    if curr_m >= target_count:
                        log(f"✅ Target reached! All bots joined.")
                        break
                        
            members = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_members, guild_id, pool[0]["uid"], pool[0]["password"])
            if members:
                our_uids = set(a["uid"] for a in pool)
                joined_count = len([u for u in members.keys() if u in our_uids])
            
            joined = pool[:max(1, joined_count)] if joined_count > 0 else pool

        log(f"📝 Updating Bio for {len(joined)} bots...")
        for acc in joined:
            check_timeout()
            await asyncio.get_event_loop().run_in_executor(None, send_bio, acc["uid"], acc["password"])
            await asyncio.sleep(1)

        if not write_group_accounts(gid, joined):
            group["error"] = "Write failed"; set_stage("FAILED"); log("❌ Failed to write accounts"); return

        set_stage("STARTING_ENGINE", f"spawning engine for {len(joined)} bots")
        log(f"⚡ Starting Engine for {len(joined)} bots...")
        
        proc, err = start_engine_for_group(gid)
        if err:
            group["error"] = f"Engine: {err}"; set_stage("FAILED"); log(f"❌ Engine Error: {err}"); return

        group["engine_pid"] = proc.pid; group["engine_proc"] = proc
        group["started_at"] = time.time()
        group["initial_glory"] = group["total_glory"]
        group["accounts"] = [{"uid":a["uid"],"password":a["password"],"auth_uid":a["uid"],"name":a.get("name","") or f"Bot_{a['uid'][:6]}","account_id":a.get("account_id",""),"nickname":a.get("name","") or f"Bot_{a['uid'][:6]}","level":1,"gained_exp":0,"glory_gained":0,"matches":0,"status":"ONLINE"} for a in joined]
        group["auth_uids"] = [a["uid"] for a in joined]
        group["live_members"] = {}
        group["members_fetched_at"] = 0
        set_stage("RUNNING", f"{len(joined)} bots online · {SETTINGS['goal_hours']}h timer started")
        log(f"🚀 ALL SYSTEMS GO! {len(joined)} bots running (PID: {proc.pid}). 8h Timer started.")
        
        GLOBAL_STATS["bots_total"] += len(joined)
        save_json(DB_FILE, GROUPS_DB)
        await _glory_worker(gid)

    except TimeoutError as e:
        log(f"❌ {e}")
        group["error"] = str(e)
        set_stage("FAILED")
    except Exception as e:
        log(f"❌ Error: {e}")
        group["error"] = str(e)
        set_stage("FAILED")

async def _glory_worker(gid):
    group = GROUPS_DB.get(gid)
    if not group: return
    start_ts = group["started_at"]
    tick = 0
    last_members_fetch = 0
    goal_secs = SETTINGS.get("goal_hours", 8) * 3600

    while True:
        g = GROUPS_DB.get(gid)
        if not g or g.get("status") != "RUNNING": break
        elapsed = time.time() - start_ts
        if elapsed >= goal_secs:
            proc = g.get("engine_proc")
            if proc: stop_engine_process(proc)
            g["status"]="COMPLETED"; g["stage"]="COMPLETED"; g["stage_note"]="Goal reached"
            g["engine_pid"]=None; g["engine_proc"]=None
            print(f"  [RBC-GLORY] [{gid}] 🏁 8-Hour Goal Reached. Engine stopped.")
            save_json(DB_FILE, GROUPS_DB); return
        proc = g.get("engine_proc")
        if proc and proc.poll() is not None:
            new_proc, err = start_engine_for_group(gid)
            if not err:
                g["engine_proc"]=new_proc; g["engine_pid"]=new_proc.pid; save_json(DB_FILE, GROUPS_DB)

        tick += 1
        try:
            info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_info, g["guild_id"], g["region"])
            if info:
                g["total_glory"] = info["total_glory"]
                g["glory_gained"] = max(0, info["total_glory"] - g["initial_glory"])
                g["current_members"] = info["current_members"]
                g["members_online"] = info.get("members_online", 0)
                g["rank"] = info.get("rank", 0)
                g["activity_points"] = info.get("activity_points", 0)
                g["elapsed_seconds"] = int(elapsed)
                g["remaining_seconds"] = int(max(0, goal_secs - elapsed))
                save_json(DB_FILE, GROUPS_DB)
        except Exception: pass

        if time.time() - last_members_fetch >= SETTINGS.get("glory_refresh_secs", 60):
            last_members_fetch = time.time()
            try:
                members = await asyncio.get_event_loop().run_in_executor(None, _fetch_members_for_group, gid)
                if members:
                    g = GROUPS_DB.get(gid)
                    if g is not None:
                        g["live_members"] = members
                        g["members_fetched_at"] = int(time.time())
                        for a in g.get("accounts", []):
                            u = a.get("uid", "")
                            if u in members:
                                m = members[u]
                                a["nickname"] = m.get("nickname") or a.get("nickname") or a.get("name")
                                a["name"] = a.get("name") or m.get("nickname")
                                a["total_glory"] = m.get("totalGlory", 0)
                                a["weekly_glory"] = m.get("weeklyGlory", 0)
                                a["glory_gained"] = m.get("totalGlory", 0)
                                a["level"] = m.get("level", 1)
                                a["role"] = m.get("role", "Member")
                        save_json(DB_FILE, GROUPS_DB)
            except Exception: pass

        await asyncio.sleep(45 if tick > 2 else 20)

# ═══════════════ HELPERS ═══════════════
def _wants_json(r): return str(r.query.get("format", "")).lower() == "json"
def _err(r, msg, code=400):
    if _wants_json(r): return web.json_response({"error": msg}, status=code)
    return web.Response(text=f"❌ {msg}", content_type="text/plain", status=code)

def _group_summary(gid, g):
    accounts = []
    meta = group_accounts_meta_path(gid)
    try:
        if os.path.exists(meta):
            with open(meta) as f:
                for a in json.load(f):
                    accounts.append({"name":a.get("name",""),"uid":a.get("uid",""),"password":a.get("password",""),"account_id":a.get("account_id","")})
    except Exception: pass
    if not accounts:
        for a in g.get("accounts", []):
            accounts.append({"name":a.get("name") or a.get("nickname") or "","uid":a.get("uid",""),"password":a.get("password",""),"account_id":a.get("account_id","")})

    live = g.get("live_members") or {}
    for a in accounts:
        u = a.get("uid", "")
        if u in live:
            m = live[u]
            a["nickname"] = m.get("nickname") or a.get("name")
            a["name"] = m.get("nickname") or a.get("name")
            a["total_glory"] = m.get("totalGlory", 0)
            a["weekly_glory"] = m.get("weeklyGlory", 0)
            a["glory_gained"] = m.get("totalGlory", 0)
            a["level"] = m.get("level", 1)
            a["role"] = m.get("role", "Member")
            a["status"] = "ONLINE" if g.get("status") == "RUNNING" else "OFFLINE"
        else:
            a["nickname"] = a.get("nickname") or a.get("name") or "Bot"
            a["name"] = a.get("name") or a.get("nickname") or "Bot"
            a["total_glory"] = a.get("total_glory", 0)
            a["weekly_glory"] = a.get("weekly_glory", 0)
            a["glory_gained"] = a.get("glory_gained", 0)
            a["level"] = a.get("level", 1)
            a["role"] = a.get("role", "Member")
            a["status"] = "ONLINE" if g.get("status") == "RUNNING" else "OFFLINE"

    elapsed = int(time.time() - g["started_at"]) if g.get("started_at") else g.get("elapsed_seconds",0)
    goal_secs = SETTINGS.get("goal_hours", 8) * 3600
    remaining = max(0, goal_secs - elapsed) if g.get("started_at") else g.get("remaining_seconds", goal_secs)
    
    return {
        "group_id": gid, "guild_id": g.get("guild_id"),
        "guild_name": g.get("guild_name"), "guild_level": g.get("guild_level"),
        "region": g.get("region"), "leader_name": g.get("leader_name"),
        "leader_id": g.get("leader_id"), "bio": g.get("bio") or g.get("slogan"),
        "rank": g.get("rank", 0), "activity_points": g.get("activity_points", 0),
        "status": g.get("status"), "stage": g.get("stage"),
        "stage_note": g.get("stage_note"), "stage_at": g.get("stage_at"),
        "created_at": g.get("created_at"),
        "initial_member_count": g.get("initial_member_count", 0),
        "current_members": g.get("current_members", 0),
        "max_members": g.get("max_members", 35),
        "members_online": g.get("members_online", 0),
        "approved_count": g.get("approved_count", 0),
        "total_glory": g.get("total_glory", 0), "initial_glory": g.get("initial_glory", 0),
        "glory_gained": g.get("glory_gained", 0),
        "engine_pid": g.get("engine_pid"), "elapsed": elapsed, "remaining": remaining,
        "online_bots": g.get("online_bots", len(accounts) if g.get("status") == "RUNNING" else 0),
        "target_bots": SETTINGS.get("bot_count", 4),
        "members_fetched_at": g.get("members_fetched_at", 0),
        "accounts": accounts, "error": g.get("error"), "owner": g.get("owner", "admin")
    }

# ═══════════════ AUTH HANDLERS ═══════════════
async def api_login(request):
    try:
        data = await request.json()
        user = data.get("username")
        pwd = data.get("password")
        u = USERS_DB.get(user)
        if u and u.get("password") == pwd:
            return web.json_response({"ok": True, "user": u})
        return web.json_response({"ok": False, "error": "Invalid credentials"}, status=401)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_redeem(request):
    try:
        data = await request.json()
        user = data.get("username")
        code = data.get("code")
        u = USERS_DB.get(user)
        if not u: return web.json_response({"error": "User not found"}, status=404)
        
        coupon = COUPONS_DB.get(code)
        if not coupon or coupon.get("used"):
            return web.json_response({"error": "Invalid or used coupon"}, status=400)
            
        credits = coupon.get("credits", 1)
        u["credits"] = u.get("credits", 0) + credits
        coupon["used"] = True
        coupon["used_by"] = user
        coupon["used_at"] = time.time()
        
        save_json(USERS_FILE, USERS_DB)
        save_json(COUPONS_FILE, COUPONS_DB)
        return web.json_response({"ok": True, "credits": u["credits"]})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

# ═══════════════ API HANDLERS ═══════════════
async def api_home(request):
    try:
        with open(os.path.join(TEMPLATES_DIR, "index.html"), "r", encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html", charset="utf-8")
    except Exception:
        return web.Response(text="index.html not found in templates/", status=404)

async def api_admin_page(request):
    try:
        with open(os.path.join(TEMPLATES_DIR, "admin.html"), "r", encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html", charset="utf-8")
    except Exception:
        return web.Response(text="admin.html not found in templates/", status=404)

async def api_stats(request):
    username = str(request.query.get("user", "")).strip()
    user = USERS_DB.get(username)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    
    user_groups = []
    for gid, g in GROUPS_DB.items():
        if user["is_admin"] or g.get("owner") == username:
            user_groups.append(g)
            
    online = 0
    for g in user_groups:
        if g.get("status") == "RUNNING": online += len(g.get("accounts", []))
    glory_sum = sum(g.get("glory_gained", 0) for g in user_groups)
    
    return web.json_response({
        "total_accounts": sum(len(g.get("accounts", [])) for g in user_groups),
        "online_bots": online,
        "matches_started": 0, "total_gained_exp": 0,
        "total_glory_pushed": glory_sum, "uptime": int(time.time() - GLOBAL_STATS["started_at"]),
        "groups_total": len(user_groups), "groups_running": sum(1 for g in user_groups if g.get("status") == "RUNNING"),
        "credits": user.get("credits", 0)
    })

async def api_groups(request):
    username = str(request.query.get("user", "")).strip()
    user = USERS_DB.get(username)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    
    out = []
    for gid, g in GROUPS_DB.items():
        if user["is_admin"] or g.get("owner") == username:
            out.append(_group_summary(gid, g))
    return web.json_response({"groups": out})

async def api_guild_info(request):
    gid = str(request.query.get("guild_id","")).strip()
    region = str(request.query.get("region", DEFAULT_REGION)).upper()
    if region not in VALID_REGIONS: region = DEFAULT_REGION
    if not gid.isdigit(): return web.json_response({"ok": False, "error": "Invalid guild_id"}, status=400)
    info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_info, gid, region)
    if not info: return web.json_response({"ok": False, "error": f"Guild {gid} not found in {region}"}, status=404)
    return web.json_response({"ok": True, "info": {
        "clan_name": info["guild_name"], "guild_id": info["guild_id"], "region": info["region"],
        "guild_level": info["guild_level"], "leader_id": info["leader_id"],
        "current_members": info["current_members"], "max_members": info["max_members"],
        "slogan": info["slogan"], "score": info["total_glory"], "weekly_activity": info["weekly_glory"],
        "rank": info["rank"], "members_online": info["members_online"], "auto_approval": info.get("auto_approval", True),
    }})

async def api_group_log(request):
    gid = str(request.query.get("group_id","")).strip()
    if gid not in GROUPS_DB: return web.json_response({"ok": False, "error": "not found"}, status=404)
    
    g = _group_summary(gid, GROUPS_DB[gid])
    bots = g["accounts"]
    total_glory = sum(b.get("total_glory", 0) for b in bots)
    
    return web.json_response({
        "ok": True, 
        "bots": bots, 
        "total_bot_glory": total_glory
    })

async def api_glory(request):
    guild_id = str(request.query.get("guild_id","")).strip()
    region = str(request.query.get("region", DEFAULT_REGION)).upper()
    username = str(request.query.get("user", "")).strip()
    
    user = USERS_DB.get(username)
    if not user: return _err(request, "Unauthorized", 401)
    if not user["is_admin"] and user.get("credits", 0) < SETTINGS.get("credit_per_launch", 1):
        return _err(request, "Not enough credits", 402)

    if region not in VALID_REGIONS: region = DEFAULT_REGION
    if not guild_id.isdigit(): return _err(request, "Invalid guild_id", 400)

    running_for_guild = [gid for gid, g in GROUPS_DB.items() if g.get("guild_id") == guild_id and g.get("status") in ("GENERATING","RUNNING")]
    if len(running_for_guild) >= SETTINGS.get("max_launches", 10):
        return _err(request, f"Limit reached ({SETTINGS.get('max_launches', 10)})", 409)

    info = await asyncio.get_event_loop().run_in_executor(None, fetch_guild_info, guild_id, region)
    if not info: return _err(request, f"Guild {guild_id} not found in region {region}", 404)

    group_id = f"GRP-{uuid.uuid4().hex[:6].upper()}"
    GROUPS_DB[group_id] = {
        "group_id":group_id,"guild_id":guild_id,"region":region,
        "guild_name":info["guild_name"],"guild_level":info["guild_level"],
        "leader_id":info["leader_id"],"leader_name":info["leader_name"],
        "slogan":info["slogan"],"bio":info.get("bio",""),
        "rank":info.get("rank",0),"activity_points":info.get("activity_points",0),
        "current_members":info["current_members"],"max_members":info["max_members"],
        "members_online":info.get("members_online",0),
        "initial_member_count":info["current_members"],"approved_count":0,
        "initial_glory":info["total_glory"],"total_glory":info["total_glory"],
        "glory_gained":0, "elapsed_seconds":0,"remaining_seconds":SETTINGS.get("goal_hours",8)*3600,
        "status":"GENERATING","stage":"GENERATING","stage_note":"queued",
        "stage_at":int(time.time()),"created_at":time.strftime("%Y-%m-%d %H:%M:%S"),
        "auth_uids":[],"accounts":[],"pending_accounts":[],
        "engine_pid":None,"engine_proc":None, "engine_log":group_log_path(group_id),
        "live_members":{}, "members_fetched_at":0, "owner": username
    }
    save_json(DB_FILE, GROUPS_DB)
    
    if not user["is_admin"]:
        user["credits"] = user.get("credits", 0) - SETTINGS.get("credit_per_launch", 1)
        user.setdefault("groups", []).append(group_id)
        save_json(USERS_FILE, USERS_DB)
        
    asyncio.create_task(create_and_join(region, guild_id, SETTINGS.get("bot_count", 4), GROUPS_DB[group_id]))

    return web.json_response({
        "ok": True, "group_id": group_id, "group_key": group_id, "region": region,
        "guild_id": guild_id, "guild_name": info["guild_name"],
        "guild_info": {"clan_name": info["guild_name"], "guild_id": info["guild_id"], "region": info["region"], "guild_level": info["guild_level"], "leader_id": info["leader_id"], "slogan": info["slogan"], "current_members": info["current_members"], "max_members": info["max_members"], "score": info["total_glory"], "weekly_activity": info["weekly_glory"]},
        "bots": SETTINGS.get("bot_count", 4), "launched_for_guild": len(running_for_guild) + 1,
    })

async def api_stop(request):
    username = str(request.query.get("user", "")).strip()
    user = USERS_DB.get(username)
    if not user: return _err(request, "Unauthorized", 401)
    
    gid = str(request.query.get("group_id","")).strip() or str(request.query.get("group_key","")).strip()
    g = GROUPS_DB.get(gid)
    if not g: return _err(request, f"{gid} not found", 404)
    if not user["is_admin"] and g.get("owner") != username: return _err(request, "Forbidden", 403)
    
    g["status"]="STOPPED"; g["stage"]="STOPPED"; g["stage_note"]="stopped by user"
    proc = g.get("engine_proc")
    if proc: await asyncio.get_event_loop().run_in_executor(None, stop_engine_process, proc)
    g["engine_pid"]=None; g["engine_proc"]=None
    for acc in g.get("accounts", []): acc["status"]="OFFLINE"
    save_json(DB_FILE, GROUPS_DB)
    return web.json_response({"ok":True,"group_id":gid,"status":"STOPPED"})

async def api_restart(request):
    username = str(request.query.get("user", "")).strip()
    user = USERS_DB.get(username)
    if not user: return _err(request, "Unauthorized", 401)
    
    gid = str(request.query.get("group_id","")).strip() or str(request.query.get("group_key","")).strip()
    g = GROUPS_DB.get(gid)
    if not g: return _err(request, f"{gid} not found", 404)
    if not user["is_admin"] and g.get("owner") != username: return _err(request, "Forbidden", 403)
    if g.get("status") == "RUNNING": return _err(request, f"{gid} already running", 409)

    proc = g.get("engine_proc")
    if proc: 
        await asyncio.get_event_loop().run_in_executor(None, stop_engine_process, proc)
        g["engine_proc"] = None; g["engine_pid"] = None
        await asyncio.sleep(2)

    saved = [{"uid":a["uid"],"password":a.get("password",DEFAULT_PASSWORD),"name":a.get("name",""),"account_id":a.get("account_id","")} for a in g.get("accounts", []) if a.get("uid")]
             
    if saved:
        if not write_group_accounts(gid, saved): return _err(request, "Cannot write accounts.json", 500)
        proc, err = start_engine_for_group(gid)
        if err: return _err(request, err, 500)
        
        g["status"]="RUNNING"; g["stage"]="RUNNING"; g["stage_note"]="restarted with same bots"
        g["engine_pid"]=proc.pid; g["engine_proc"]=proc
        save_json(DB_FILE, GROUPS_DB)
        asyncio.create_task(_glory_worker(gid))
        return web.json_response({"ok":True,"group_id":gid,"restarted_with_same":len(saved)})
    else:
        g["status"]="GENERATING"; g["stage"]="GENERATING"
        g["auth_uids"]=[]; g["accounts"]=[]; save_json(DB_FILE, GROUPS_DB)
        asyncio.create_task(create_and_join(g["region"], g["guild_id"], SETTINGS.get("bot_count",4), g))
        return web.json_response({"ok":True,"group_id":gid,"restarted_with_fresh":True})

async def api_delete(request):
    username = str(request.query.get("user", "")).strip()
    user = USERS_DB.get(username)
    if not user: return _err(request, "Unauthorized", 401)
    
    gid = str(request.query.get("group_id","")).strip()
    g = GROUPS_DB.get(gid)
    if not g: return _err(request, f"{gid} not found", 404)
    if not user["is_admin"] and g.get("owner") != username: return _err(request, "Forbidden", 403)
    
    proc = g.get("engine_proc")
    if proc: await asyncio.get_event_loop().run_in_executor(None, stop_engine_process, proc)
    
    gdir = group_dir(gid)
    if os.path.exists(gdir):
        try: shutil.rmtree(gdir)
        except Exception: pass
            
    del GROUPS_DB[gid]
    save_json(DB_FILE, GROUPS_DB)
    return web.json_response({"ok": True, "group_id": gid, "deleted": True})

async def api_settings_get(request):
    return web.json_response(SETTINGS)

async def api_settings_save(request):
    try:
        data = await request.json()
        SETTINGS.update(data)
        save_json(SETTINGS_FILE, SETTINGS)
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_admin_users(request):
    if request.method == "GET":
        return web.json_response({"users": list(USERS_DB.values())})
    elif request.method == "POST":
        try:
            data = await request.json()
            user = data.get("username")
            pwd = data.get("password")
            credits = data.get("credits", 0)
            if not user or not pwd: return web.json_response({"error": "Empty"}, status=400)
            if user in USERS_DB: return web.json_response({"error": "User exists"}, status=409)
            USERS_DB[user] = {"username": user, "password": pwd, "is_admin": False, "credits": credits, "groups": []}
            save_json(USERS_FILE, USERS_DB)
            return web.json_response({"ok": True})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

async def api_admin_add_credits(request):
    try:
        data = await request.json()
        user = data.get("username")
        amt = int(data.get("amount", 0))
        u = USERS_DB.get(user)
        if not u: return web.json_response({"error": "User not found"}, status=404)
        u["credits"] = max(0, u.get("credits", 0) + amt)
        save_json(USERS_FILE, USERS_DB)
        return web.json_response({"ok": True, "credits": u["credits"]})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_admin_gen_coupon(request):
    try:
        data = await request.json()
        credits = int(data.get("credits", 1))
        count = int(data.get("quantity", 1))
        
        codes = []
        for _ in range(count):
            code = f"RBC-{uuid.uuid4().hex[:6].upper()}-{credits}"
            COUPONS_DB[code] = {"code": code, "credits": credits, "used": False, "created_at": time.time()}
            codes.append(code)
            
        save_json(COUPONS_FILE, COUPONS_DB)
        return web.json_response({"ok": True, "codes": codes})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def api_admin_coupons(request):
    return web.json_response({"coupons": list(COUPONS_DB.values())})

async def api_admin_get_accounts(request):
    return web.json_response({"accounts": MANUAL_ACCOUNTS})

async def api_admin_save_accounts(request):
    try:
        data = await request.json()
        region = str(data.get("region", "")).upper()
        accs = data.get("accounts", [])
        
        if region not in VALID_REGIONS: return web.json_response({"error": "Invalid region"}, status=400)
        
        MANUAL_ACCOUNTS[region] = accs
        save_json(MANUAL_ACCS_FILE, MANUAL_ACCOUNTS)
        return web.json_response({"ok": True, "count": len(accs)})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


# ═══════════════ APP ENTRYPOINT ═══════════════
async def main():
    print(f"""
\x1b[38;5;220m
 ██████╗ ██████╗  ██████╗    ██████╗ ██╗      ██████╗ ██████╗ ██╗   ██╗
 ██╔══██╗██╔══██╗██╔════╝   ██╔════╝ ██║     ██╔═══██╗██╔══██╗╚██╗ ██╔╝
 ██████╔╝██████╔╝██║        ██║  ███╗██║     ██║   ██║██████╔╝ ╚████╔╝ 
 ██╔══██╗██╔══██╗██║        ██║   ██║██║     ██║   ██║██╔══██╗  ╚██╔╝  
 ██║  ██║██████╔╝╚██████╗   ╚██████╔╝███████╗╚██████╔╝██║  ██║   ██║   
 ╚═╝  ╚═╝╚═════╝  ╚═════╝    ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   
\x1b[0m
  \x1b[1m\x1b[36mRBC ENGINE v7 — ADVANCED UI\x1b[0m
  \x1b[90mPort: {WEB_PORT} | Admin URL: http://{WEB_HOST}:{WEB_PORT}{ADMIN_SECRET_PATH}\x1b[0m
  \x1b[90m════════════════════════════════════════════════════════════════════\x1b[0m
""", flush=True)

    app = web.Application()
    app.router.add_get("/", api_home)
    app.router.add_get(ADMIN_SECRET_PATH, api_admin_page)
    
    # Auth APIs
    app.router.add_post("/api/login", api_login)
    app.router.add_post("/api/redeem", api_redeem)
    
    # Core APIs
    app.router.add_get("/api/stats", api_stats)
    app.router.add_get("/api/groups", api_groups)
    app.router.add_get("/api/guild_info", api_guild_info)
    app.router.add_get("/api/groups/log", api_group_log)
    app.router.add_get("/glory", api_glory)
    app.router.add_get("/stop", api_stop)
    app.router.add_get("/restart", api_restart)
    app.router.add_get("/delete", api_delete)
    app.router.add_get("/api/settings/get", api_settings_get)
    app.router.add_post("/api/settings/save", api_settings_save)
    
    # Admin APIs
    app.router.add_get("/api/admin/users", api_admin_users)
    app.router.add_post("/api/admin/users", api_admin_users)
    app.router.add_post("/api/admin/add_credits", api_admin_add_credits)
    app.router.add_post("/api/admin/gen_coupon", api_admin_gen_coupon)
    app.router.add_get("/api/admin/coupons", api_admin_coupons)
    app.router.add_get("/api/admin/get_accounts", api_admin_get_accounts)
    app.router.add_post("/api/admin/save_accounts", api_admin_save_accounts)

    asyncio.create_task(_auto_restart_loop())

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_HOST, WEB_PORT)
    await site.start()
    print(f"✅ Ready → http://{WEB_HOST}:{WEB_PORT}\n", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠ Stopped")