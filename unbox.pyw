# -*- coding: utf-8 -*-
"""
Unbox — tiny tray app, does nothing until you press its hotkey.

In File Explorer select one or more folders, press the hotkey (default Ctrl+Alt+U):
every file in each folder is renamed with the folder name (prefix or suffix), moved up
next to the folder, and the emptied folder is removed. All-or-nothing per folder: if any
new name already exists, that folder is skipped. Subfolders stay (folder is then kept).
Never overwrites; only deletes an empty folder (plus desktop.ini / Thumbs.db junk).

Idle cost: one sleeping thread waiting in GetMessage (0% CPU). Stdlib only.
Tray icon (right-click): hotkey (checks conflicts), prefix/suffix, separator, language, autostart.
"""
VERSION = "v1.4"
# v1.0  first version (single-file folders only)
# v1.1  language option: English / 繁體中文 (tray menu → Language); first run follows Windows
# v1.2  unboxes EVERY file in the folder; folder name as prefix or suffix (tray menu)
# v1.3  third choice "Keep names": move everything out as-is (subfolders too), no renaming
# v1.4  narrower tray menu; menu follows Windows dark/light mode, round bullets, bold header;
#       restyled Set-hotkey window (dark/light, flat buttons, icon). No idle cost.

import ctypes, json, os, subprocess, sys, threading, time
from ctypes import wintypes as W

APP = "Unbox"
CFG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP)
CFG_PATH = os.path.join(CFG_DIR, "config.json")
LOG_PATH = os.path.join(CFG_DIR, "unbox.log")
DEFAULT = {"mods": ["ctrl", "alt"], "key": "U", "sep": "_", "pos": "prefix", "enabled": True, "lang": None}
SEPS = ["_", " ", "-", ""]
POSITIONS = ["prefix", "suffix", "keep"]
JUNK = {"desktop.ini", "thumbs.db", ".ds_store"}       # system junk: removed, never renamed
LANGS = [("en", "English"), ("zh", "繁體中文")]

S = {
    "en": {
        "sep_words": ["Underscore", "Space", "Dash", "None"],
        "pos_words": ["Prefix", "Suffix", "Keep names"],
        "ex": ("Show", "Ep01", ".mp4"),
        "m_pos": "Naming",
        "not_folder": "{name}: not a folder",
        "no_files": "{name}: no files inside, skipped",
        "exists": "{name}: '{new}' already exists, nothing moved",
        "move_fail": "{name}: {err} — nothing moved",
        "moved": "{name}: {n} file{s}", "moved_items": "{name}: {n} item{s}",
        "kept_sub": " (folder kept: has subfolders)",
        "kept_err": " (folder could not be removed)",
        "start_conflict": "{hk} is already used by another program.\nRight-click the Unbox tray icon → Set hotkey…",
        "paused": "paused", "not_set": "hotkey not set",
        "not_explorer": "Select the folder(s) in File Explorer first, then press the hotkey.",
        "no_folder": "No folder selected. Click the folder(s) in the file list (not the address bar).",
        "more": "\n…and {n} more", "done": "Unboxed {n}", "skipped": ", skipped {n}",
        "off": " (off)", "m_set": "Set hotkey…", "m_pause": "Pause hotkey", "m_sep": "Separator",
        "m_lang": "Language", "m_start": "Start with Windows", "m_help": "How to use", "m_quit": "Quit",
        "pause_conflict": "{hk} is used by another program. Choose another with Set hotkey…",
        "hk_now": "Hotkey: {hk}", "hk_fail": "{hk} could not be registered (in use).",
        "error": "Error: {e}", "running": "Unbox is already running (see the tray icon).",
        "help": ("How to use\n\n"
                 "1. In File Explorer, select one or more folders.\n"
                 "2. Press {hk}.\n\n"
                 "Every file in each folder gets the folder name and moves up\n"
                 "next to where the folder was:\n"
                 "   {a}   →   {b}\n"
                 "Then the empty folder is removed.\n\n"
                 "Prefix / suffix / keep names, and the separator: tray menu.\n"
                 "Nothing is ever overwritten: if any new name already exists,\n"
                 "that folder is skipped completely.\n"
                 "Subfolders stay where they are (the folder is then kept),\n"
                 "except with Keep names, which moves everything out as it is.\n"
                 "Names that already have the folder name are not changed again.\n"
                 "desktop.ini / Thumbs.db (Windows junk) are removed with the folder.\n\n"
                 "History of moved files: {log}"),
        "d_title": "Unbox — Set hotkey", "d_prompt": "Press the key combination you want",
        "d_hint": "Current: {hk}   ·   use Ctrl or Alt + one more modifier + a key",
        "d_wait": "(waiting…)", "d_ok": "OK", "d_cancel": "Cancel",
        "d_mods": "Needs at least two modifiers incl. Ctrl or Alt (e.g. Ctrl+Alt+U).",
        "d_taken": "✗ {hk} is {what}. Pick another.",
        "d_inuse": "✗ {hk} is already registered by another program or Windows. Pick another.",
        "d_failed": "✗ {hk} failed (error {err}). Pick another.",
        "d_free": "✓ No conflict with other programs or Windows.\n"
                  "(Shortcuts that only work inside one app's window can't be detected.)",
        "font": "Segoe UI",
        "bl": {"Ctrl+Shift+C": "Explorer's 'Copy as path' (Unbox uses it)",
               "Ctrl+Shift+N": "'New folder' in Explorer / private window in browsers",
               "Ctrl+Shift+E": "Explorer's 'Expand all'",
               "Ctrl+Shift+T": "browser 'Reopen closed tab'",
               "Ctrl+Shift+V": "'Paste as plain text'",
               "Ctrl+Alt+Z": "a common screen recorder shortcut"},
        "sie": "ShortsInfoExtractor's hotkey",
    },
    "zh": {
        "sep_words": ["底線", "空格", "連字號", "不加"],
        "pos_words": ["前綴", "後綴", "保留原檔名"],
        "ex": ("片名", "第01集", ".mp4"),
        "m_pos": "命名方式",
        "not_folder": "{name}：不是資料夾",
        "no_files": "{name}：裡面沒有檔案，已略過",
        "exists": "{name}：已經有「{new}」，沒有移動任何檔案",
        "move_fail": "{name}：{err}，沒有移動任何檔案",
        "moved": "{name}：{n} 個檔案", "moved_items": "{name}：{n} 個項目",
        "kept_sub": "（資料夾保留：裡面還有子資料夾）",
        "kept_err": "（資料夾無法刪除）",
        "start_conflict": "{hk} 已被其他程式使用。\n請在工作列的 Unbox 圖示按右鍵 → 設定快捷鍵…",
        "paused": "已暫停", "not_set": "快捷鍵未啟用",
        "not_explorer": "請先在「檔案總管」選取資料夾，再按快捷鍵。",
        "no_folder": "沒有選取資料夾。請在檔案清單中點選資料夾（不要停在網址列）。",
        "more": "\n…還有 {n} 個", "done": "完成 {n} 個", "skipped": "，略過 {n} 個",
        "off": "（未啟用）", "m_set": "設定快捷鍵…", "m_pause": "暫停快捷鍵", "m_sep": "分隔符號",
        "m_lang": "語言 Language", "m_start": "開機時自動啟動", "m_help": "使用說明", "m_quit": "結束",
        "pause_conflict": "{hk} 已被其他程式使用，請用「設定快捷鍵…」換一組。",
        "hk_now": "快捷鍵：{hk}", "hk_fail": "{hk} 無法註冊（已被使用）。",
        "error": "錯誤：{e}", "running": "Unbox 已經在執行中（請看工作列右下角的圖示）。",
        "help": ("使用說明\n\n"
                 "1. 在「檔案總管」選取一個或多個資料夾。\n"
                 "2. 按 {hk}。\n\n"
                 "每個資料夾裡的所有檔案都會加上資料夾名稱，\n"
                 "並移到原本資料夾所在的位置：\n"
                 "   {a}   →   {b}\n"
                 "然後刪除已變空的資料夾。\n\n"
                 "前綴／後綴／保留原檔名與分隔符號：在工作列圖示的選單中設定。\n"
                 "絕不覆蓋任何檔案：只要有一個新檔名已存在，該資料夾就整個略過。\n"
                 "子資料夾會留在原處（此時資料夾會保留）；\n"
                 "選「保留原檔名」時則全部原樣移出，包括子資料夾。\n"
                 "檔名若已經含有資料夾名稱，就不會重複加上。\n"
                 "desktop.ini／Thumbs.db（Windows 系統檔）會隨資料夾一起刪除。\n\n"
                 "移動紀錄：{log}"),
        "d_title": "Unbox — 設定快捷鍵", "d_prompt": "請按下想使用的組合鍵",
        "d_hint": "目前：{hk}   ·   需包含 Ctrl 或 Alt，再加一個修飾鍵和一個按鍵",
        "d_wait": "（等待按鍵…）", "d_ok": "確定", "d_cancel": "取消",
        "d_mods": "需要至少兩個修飾鍵且包含 Ctrl 或 Alt（例如 Ctrl+Alt+U）。",
        "d_taken": "✗ {hk} 是{what}，請換一組。",
        "d_inuse": "✗ {hk} 已被其他程式或系統註冊為全域快捷鍵，請換一組。",
        "d_failed": "✗ {hk} 無法註冊（錯誤碼 {err}），請換一組。",
        "d_free": "✓ 目前沒有與其他程式或系統的全域快捷鍵衝突\n（無法偵測只在特定程式視窗內有效的快捷鍵）",
        "font": "Microsoft JhengHei UI",
        "bl": {"Ctrl+Shift+C": "檔案總管的「複製路徑」（Unbox 會使用它）",
               "Ctrl+Shift+N": "檔案總管／瀏覽器的「新增資料夾／無痕視窗」",
               "Ctrl+Shift+E": "檔案總管的「展開所有資料夾」",
               "Ctrl+Shift+T": "瀏覽器的「重新開啟關閉的分頁」",
               "Ctrl+Shift+V": "「貼上純文字」",
               "Ctrl+Alt+Z": "常見螢幕錄影／截圖軟體的快捷鍵"},
        "sie": "ShortsInfoExtractor 的快捷鍵",
    },
}
LANG = "en"


def T(key, **kw):
    s = S[LANG][key]
    return s.format(**kw) if kw else s


def system_lang():
    """繁體中文 if Windows display language is Chinese (Taiwan / Hong Kong / Macau), else English."""
    try:
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "zh" if lid in (0x0404, 0x0C04, 0x1404) else "en"
    except Exception:  # noqa
        return "en"


def load_cfg():
    global LANG
    cfg = dict(DEFAULT)
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:  # noqa
        pass
    if cfg.get("lang") not in S:
        cfg["lang"] = system_lang()
    LANG = cfg["lang"]
    return cfg


def save_cfg(cfg):
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False)


def log(line):
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 200_000:
            os.replace(LOG_PATH, LOG_PATH + ".old")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S  ") + line + "\n")
    except Exception:  # noqa
        pass


# ------------------------------------------------------------------ the actual job
def new_name(fname, folder, sep, pos):
    """Folder name as prefix (Show_Ep01.mp4) or suffix before the extension (Ep01_Show.mp4).
    Names that already carry the folder name are left as they are. pos "keep" = no rename."""
    if pos == "keep":
        return fname
    if pos == "suffix":
        stem, ext = os.path.splitext(fname)
        return fname if stem.endswith(folder) else stem + sep + folder + ext
    return fname if fname.startswith(folder) else folder + sep + fname


def unbox(folder, sep, pos="prefix"):
    """Move every file out of `folder` (renamed), then remove the folder. Returns (ok, message).
    All-or-nothing: checks every new name first; if a move fails midway, undoes the moves."""
    folder = os.path.normpath(folder)
    parent, name = os.path.split(folder)
    if not name or not os.path.isdir(folder):
        return False, T("not_folder", name=os.path.basename(folder) or folder)
    entries = os.listdir(folder)
    files = sorted(e for e in entries if os.path.isfile(os.path.join(folder, e)) and e.lower() not in JUNK)
    dirs = sorted(e for e in entries if os.path.isdir(os.path.join(folder, e)))
    moved_dirs = pos == "keep" and bool(dirs)  # keep-names mode moves subfolders too, as they are
    if moved_dirs:
        files += dirs
    has_dirs = bool(dirs) and not moved_dirs   # subfolders left behind -> folder is kept
    if not files:
        return False, T("no_files", name=name)
    fkey = os.path.normcase(folder)
    plan = [(os.path.join(folder, f), os.path.join(parent, new_name(f, name, sep, pos))) for f in files]
    for _, dst in plan:                        # check everything before touching anything
        takes_folder_name = os.path.normcase(dst) == fkey
        if (takes_folder_name and has_dirs) or (not takes_folder_name and os.path.lexists(dst)):
            return False, T("exists", name=name, new=os.path.basename(dst))
    moved = []                                 # (src, where it is now, final dst)
    try:
        for src, dst in plan:
            now = dst if os.path.normcase(dst) != fkey else os.path.join(parent, f".unbox_{time.time_ns()}")
            os.rename(src, now)
            moved.append((src, now, dst))
    except OSError as e:
        for src, now, _ in reversed(moved):    # undo, so the folder is exactly as before
            try:
                os.rename(now, src)
            except OSError:
                log(f"UNDO FAILED {now} -> {src}")
        return False, T("move_fail", name=name, err=e.strerror or e)
    note = ""
    if has_dirs:
        note = T("kept_sub")
    else:
        try:
            for j in os.listdir(folder):
                if j.lower() in JUNK:
                    p = os.path.join(folder, j)
                    os.chmod(p, 0o666)         # desktop.ini is often read-only/system
                    os.remove(p)
            os.rmdir(folder)
        except OSError:
            note = T("kept_err")
    for src, now, dst in moved:
        if now != dst:                         # a file that takes the folder's own name
            try:
                os.rename(now, dst if not note else src)
            except OSError:
                log(f"LEFT AS {now} (wanted {dst})")
        log(f"MOVED {src} -> {dst if now == dst or not note else src}")
    n = len(moved)
    return True, T("moved_items" if moved_dirs else "moved", name=name, n=n, s="" if n == 1 else "s") + note


# ------------------------------------------------------------------ Win32 plumbing
u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
sh32 = ctypes.WinDLL("shell32")
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
VP = ctypes.c_void_p


def fn(dll, name, res, *args):
    f = getattr(dll, name)
    f.restype, f.argtypes = res, args
    return f


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", W.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", VP), ("hIcon", VP), ("hCursor", VP),
                ("hbrBackground", VP), ("lpszMenuName", W.LPCWSTR), ("lpszClassName", W.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("hWnd", W.HWND), ("uID", W.UINT), ("uFlags", W.UINT),
                ("uCallbackMessage", W.UINT), ("hIcon", VP), ("szTip", W.WCHAR * 128),
                ("dwState", W.DWORD), ("dwStateMask", W.DWORD), ("szInfo", W.WCHAR * 256),
                ("uVersion", W.UINT), ("szInfoTitle", W.WCHAR * 64), ("dwInfoFlags", W.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", VP)]


DefWindowProc = fn(u32, "DefWindowProcW", LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
RegisterClass = fn(u32, "RegisterClassW", W.ATOM, ctypes.POINTER(WNDCLASSW))
CreateWindowEx = fn(u32, "CreateWindowExW", W.HWND, W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.HWND, VP, VP, VP)
GetMessage = fn(u32, "GetMessageW", W.BOOL, ctypes.POINTER(W.MSG), W.HWND, W.UINT, W.UINT)
TranslateMessage = fn(u32, "TranslateMessage", W.BOOL, ctypes.POINTER(W.MSG))
DispatchMessage = fn(u32, "DispatchMessageW", LRESULT, ctypes.POINTER(W.MSG))
PostMessage = fn(u32, "PostMessageW", W.BOOL, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
PostQuitMessage = fn(u32, "PostQuitMessage", None, ctypes.c_int)
RegisterHotKey = fn(u32, "RegisterHotKey", W.BOOL, W.HWND, ctypes.c_int, W.UINT, W.UINT)
UnregisterHotKey = fn(u32, "UnregisterHotKey", W.BOOL, W.HWND, ctypes.c_int)
GetForegroundWindow = fn(u32, "GetForegroundWindow", W.HWND)
SetForegroundWindow = fn(u32, "SetForegroundWindow", W.BOOL, W.HWND)
GetClassName = fn(u32, "GetClassNameW", ctypes.c_int, W.HWND, W.LPWSTR, ctypes.c_int)
OpenClipboard = fn(u32, "OpenClipboard", W.BOOL, W.HWND)
CloseClipboard = fn(u32, "CloseClipboard", W.BOOL)
EmptyClipboard = fn(u32, "EmptyClipboard", W.BOOL)
GetClipboardData = fn(u32, "GetClipboardData", VP, W.UINT)
SetClipboardData = fn(u32, "SetClipboardData", VP, W.UINT, VP)
ClipSeq = fn(u32, "GetClipboardSequenceNumber", W.DWORD)
GlobalAlloc = fn(k32, "GlobalAlloc", VP, W.UINT, ctypes.c_size_t)
GlobalLock = fn(k32, "GlobalLock", VP, VP)
GlobalUnlock = fn(k32, "GlobalUnlock", W.BOOL, VP)
GetAsyncKeyState = fn(u32, "GetAsyncKeyState", ctypes.c_short, ctypes.c_int)
keybd_event = fn(u32, "keybd_event", None, W.BYTE, W.BYTE, W.DWORD, ctypes.c_size_t)
CreatePopupMenu = fn(u32, "CreatePopupMenu", VP)
AppendMenu = fn(u32, "AppendMenuW", W.BOOL, VP, W.UINT, ctypes.c_size_t, W.LPCWSTR)
TrackPopupMenu = fn(u32, "TrackPopupMenu", ctypes.c_int, VP, W.UINT, ctypes.c_int, ctypes.c_int,
                    ctypes.c_int, W.HWND, VP)
DestroyMenu = fn(u32, "DestroyMenu", W.BOOL, VP)
CheckMenuRadioItem = fn(u32, "CheckMenuRadioItem", W.BOOL, VP, W.UINT, W.UINT, W.UINT, W.UINT)
SetMenuDefaultItem = fn(u32, "SetMenuDefaultItem", W.BOOL, VP, W.UINT, W.UINT)


def dark_mode():
    """True when Windows apps use dark mode."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def theme_menus():
    """Make popup menus match Windows dark/light mode (uxtheme ordinals 135/136, Win10 1903+).
    Checked each time the menu opens, so switching the Windows theme is followed too."""
    try:
        ux = ctypes.WinDLL("uxtheme")
        set_mode = ux[135]                     # SetPreferredAppMode
        set_mode.argtypes, set_mode.restype = [ctypes.c_int], ctypes.c_int
        set_mode(2 if dark_mode() else 3)      # 2 = force dark, 3 = force light
        ux[136]()                              # FlushMenuThemes
    except Exception:  # noqa — older Windows: plain menus
        pass
GetCursorPos = fn(u32, "GetCursorPos", W.BOOL, ctypes.POINTER(W.POINT))
RegisterWindowMessage = fn(u32, "RegisterWindowMessageW", W.UINT, W.LPCWSTR)
MessageBox = fn(u32, "MessageBoxW", ctypes.c_int, W.HWND, W.LPCWSTR, W.LPCWSTR, W.UINT)
Shell_NotifyIcon = fn(sh32, "Shell_NotifyIconW", W.BOOL, W.DWORD, ctypes.POINTER(NOTIFYICONDATAW))
ExtractIcon = fn(sh32, "ExtractIconW", VP, VP, W.LPCWSTR, W.UINT)
GetModuleHandle = fn(k32, "GetModuleHandleW", VP, W.LPCWSTR)
CreateMutex = fn(k32, "CreateMutexW", VP, VP, W.BOOL, W.LPCWSTR)

WM_DESTROY, WM_HOTKEY, WM_APP = 0x0002, 0x0312, 0x8000
WM_TRAY, WM_RELOAD = WM_APP + 1, WM_APP + 2
CF_UNICODETEXT = 13
MOD_BITS = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4}
MOD_ORDER = ("ctrl", "alt", "shift")


def combo_label(mods, key):
    return "+".join([m.capitalize() for m in MOD_ORDER if m in mods] + [key])


def key_to_vk(key):
    return ord(key) if len(key) == 1 else 0x70 + int(key[1:]) - 1


def mods_mask(mods):
    return sum(MOD_BITS[m] for m in set(mods) if m in MOD_BITS) | 0x4000   # MOD_NOREPEAT


# ---- clipboard (text only)
def _open_clip(hwnd):
    for _ in range(20):
        if OpenClipboard(hwnd):
            return True
        time.sleep(0.02)
    return False


def get_clip_text(hwnd):
    if not _open_clip(hwnd):
        return None
    try:
        h = GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else None
        finally:
            GlobalUnlock(h)
    finally:
        CloseClipboard()


def set_clip_text(hwnd, text):
    if not _open_clip(hwnd):
        return
    try:
        EmptyClipboard()
        data = ctypes.create_unicode_buffer(text)
        h = GlobalAlloc(0x0002, ctypes.sizeof(data))
        p = GlobalLock(h)
        ctypes.memmove(p, data, ctypes.sizeof(data))
        GlobalUnlock(h)
        SetClipboardData(CF_UNICODETEXT, h)
    finally:
        CloseClipboard()


def explorer_selection(hwnd):
    """Send Ctrl+Shift+C (Explorer 'Copy as path') and read the selected paths back."""
    old, seq = get_clip_text(hwnd), ClipSeq()
    end = time.time() + 1.5
    while time.time() < end and any(GetAsyncKeyState(v) & 0x8000 for v in (0x10, 0x11, 0x12, 0x5B, 0x5C)):
        time.sleep(0.02)                       # wait until the user lets go of the hotkey
    for v in (0x11, 0x10, 0x43):
        keybd_event(v, 0, 0, 0)
    for v in (0x43, 0x10, 0x11):
        keybd_event(v, 0, 2, 0)
    text, end = None, time.time() + 2.5
    while time.time() < end:
        if ClipSeq() != seq:
            time.sleep(0.05)
            text = get_clip_text(hwnd)
            break
        time.sleep(0.03)
    if old is not None and text is not None:
        set_clip_text(hwnd, old)               # put the user's text clipboard back
    if not text:
        return []
    return [p.strip().strip('"') for p in text.splitlines() if p.strip()]


# ---- start with Windows (HKCU Run key)
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


FROZEN = getattr(sys, "frozen", False)       # running as Unbox.exe


def self_cmd():
    """Command (list) that starts this program again."""
    if FROZEN:
        return [sys.executable]
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        exe = exe[:-10] + "pythonw.exe"
    return [exe, os.path.abspath(__file__)]


def autostart_cmd():
    return " ".join(f'"{p}"' for p in self_cmd())


def autostart_get():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return bool(winreg.QueryValueEx(k, APP)[0])
    except OSError:
        return False


def autostart_set(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, autostart_cmd())
        else:
            try:
                winreg.DeleteValue(k, APP)
            except OSError:
                pass


# ------------------------------------------------------------------ tray app
class Tray:
    def __init__(self):
        self.cfg = load_cfg()
        self.hk_ok, self.hwnd, self.ready = False, None, False
        self.msg_taskbar = RegisterWindowMessage("TaskbarCreated")
        self._proc = WNDPROC(self.wndproc)     # keep a reference
        hinst = GetModuleHandle(None)
        wc = WNDCLASSW(lpfnWndProc=self._proc, hInstance=hinst, lpszClassName="UnboxTrayWnd")
        RegisterClass(ctypes.byref(wc))
        self.hwnd = CreateWindowEx(0, "UnboxTrayWnd", APP, 0, 0, 0, 0, 0, None, None, hinst, None)
        self.icon = (ExtractIcon(hinst, sys.executable, 0) if FROZEN else None) or ExtractIcon(
            hinst, os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "imageres.dll"), 4) or None
        self.add_icon()
        self.register()
        self.ready = True
        if not self.hk_ok and self.cfg["enabled"]:
            self.notify(T("start_conflict", hk=self.hk()), 2)

    def hk(self):
        return combo_label(self.cfg["mods"], self.cfg["key"])

    # tray icon / balloons
    def _nid(self, flags):
        n = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=self.hwnd, uID=1,
                            uFlags=flags, uCallbackMessage=WM_TRAY, hIcon=self.icon)
        state = self.hk() if self.hk_ok else (T("paused") if not self.cfg["enabled"] else T("not_set"))
        n.szTip = f"{APP} {VERSION} — {state}"
        return n

    def add_icon(self):
        Shell_NotifyIcon(0, ctypes.byref(self._nid(0x1 | 0x2 | 0x4)))

    def update_tip(self):
        Shell_NotifyIcon(1, ctypes.byref(self._nid(0x4)))

    def notify(self, text, level=1, title=APP):
        n = self._nid(0x10)
        n.szInfo, n.szInfoTitle, n.dwInfoFlags = text[:255], title[:63], level
        Shell_NotifyIcon(1, ctypes.byref(n))

    # hotkey
    def register(self):
        UnregisterHotKey(self.hwnd, 1)
        self.hk_ok = bool(self.cfg["enabled"] and RegisterHotKey(
            self.hwnd, 1, mods_mask(self.cfg["mods"]), key_to_vk(self.cfg["key"])))
        self.update_tip()

    def on_hotkey(self):
        fg = GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(64)
        GetClassName(fg, buf, 64)
        if buf.value not in ("CabinetWClass", "ExploreWClass"):
            self.notify(T("not_explorer"), 2)
            return
        paths = explorer_selection(self.hwnd)
        folders = [p for p in paths if os.path.isdir(p)]
        if not folders:
            self.notify(T("no_folder"), 2)
            return
        done, fail = [], []
        for f in folders:
            ok, msg = unbox(f, self.cfg["sep"], self.cfg["pos"])
            (done if ok else fail).append(msg)
            if not ok:
                log("SKIP " + msg)
        lines = ([f"✓ {m}" for m in done] + [f"✗ {m}" for m in fail])
        text = "\n".join(lines[:6]) + (T("more", n=len(lines) - 6) if len(lines) > 6 else "")
        title = T("done", n=len(done)) + (T("skipped", n=len(fail)) if fail else "")
        self.notify(text, 1 if not fail else 2, title)

    def example(self, sep=None, pos=None):
        fo, fi, ext = T("ex")
        return new_name(fi + ext, fo, self.cfg["sep"] if sep is None else sep,
                        self.cfg["pos"] if pos is None else pos)

    # menu
    def menu(self):
        global LANG
        m, sub, lang, posm = CreatePopupMenu(), CreatePopupMenu(), CreatePopupMenu(), CreatePopupMenu()
        theme_menus()
        keep = self.cfg["pos"] == "keep"
        for i, s in enumerate(SEPS):
            AppendMenu(sub, 0, 20 + i, f"{T('sep_words')[i]}\t{self.example(sep=s, pos='prefix' if keep else None)}")
        for i, p in enumerate(POSITIONS):
            AppendMenu(posm, 0, 30 + i, f"{T('pos_words')[i]}\t{self.example(pos=p)}")
        for i, (code, label) in enumerate(LANGS):
            AppendMenu(lang, 0, 40 + i, label)
        # round bullets for the either-or choices
        pick = lambda seq, v: seq.index(v) if v in seq else 0
        CheckMenuRadioItem(sub, 20, 20 + len(SEPS) - 1, 20 + pick(SEPS, self.cfg["sep"]), 0)
        CheckMenuRadioItem(posm, 30, 30 + len(POSITIONS) - 1, 30 + pick(POSITIONS, self.cfg["pos"]), 0)
        CheckMenuRadioItem(lang, 40, 40 + len(LANGS) - 1, 40 + [c for c, _ in LANGS].index(LANG), 0)
        AppendMenu(m, 0, 4, f"{APP} {VERSION}\t{self.hk()}" + ("" if self.hk_ok else T("off")))
        SetMenuDefaultItem(m, 4, 0)            # bold header; clicking it shows How to use
        AppendMenu(m, 0x800, 0, None)
        AppendMenu(m, 0x10, posm, T("m_pos"))
        AppendMenu(m, 0x10 | (0x1 if keep else 0), sub, T("m_sep"))   # no separator when names are kept
        AppendMenu(m, 0x10, lang, T("m_lang"))
        AppendMenu(m, 0x800, 0, None)
        AppendMenu(m, 0, 1, T("m_set"))
        AppendMenu(m, 0x8 if not self.cfg["enabled"] else 0, 2, T("m_pause"))
        AppendMenu(m, 0x8 if autostart_get() else 0, 3, T("m_start"))
        AppendMenu(m, 0x800, 0, None)
        AppendMenu(m, 0, 5, T("m_help"))
        AppendMenu(m, 0, 9, T("m_quit"))
        pt = W.POINT()
        GetCursorPos(ctypes.byref(pt))
        SetForegroundWindow(self.hwnd)
        cmd = TrackPopupMenu(m, 0x100 | 0x80 | 0x2, pt.x, pt.y, 0, self.hwnd, None)
        DestroyMenu(m)                         # also destroys the submenus
        if cmd == 1:
            self.set_hotkey()
        elif cmd == 2:
            self.cfg["enabled"] = not self.cfg["enabled"]
            save_cfg(self.cfg)
            self.register()
            if self.cfg["enabled"] and not self.hk_ok:
                self.notify(T("pause_conflict", hk=self.hk()), 2)
        elif cmd == 3:
            autostart_set(not autostart_get())
        elif cmd in (4, 5):
            fo, fi, ext = T("ex")
            MessageBox(self.hwnd, T("help", hk=self.hk(), a=f"{fo}\\{fi}{ext}", b=self.example(),
                                    log=LOG_PATH), APP, 0x40)
        elif 20 <= cmd < 20 + len(SEPS):
            self.cfg["sep"] = SEPS[cmd - 20]
            save_cfg(self.cfg)
        elif 30 <= cmd < 30 + len(POSITIONS):
            self.cfg["pos"] = POSITIONS[cmd - 30]
            save_cfg(self.cfg)
        elif 40 <= cmd < 40 + len(LANGS):
            LANG = self.cfg["lang"] = LANGS[cmd - 40][0]
            save_cfg(self.cfg)
            self.update_tip()
        elif cmd == 9:
            PostMessage(self.hwnd, WM_DESTROY, 0, 0)

    def set_hotkey(self):
        UnregisterHotKey(self.hwnd, 1)         # free it so the dialog can test the same combo
        self.hk_ok = False
        p = subprocess.Popen(self_cmd() + ["--set-hotkey"])
        threading.Thread(target=lambda: (p.wait(), PostMessage(self.hwnd, WM_RELOAD, 0, 0)),
                         daemon=True).start()

    def wndproc(self, hwnd, msg, wp, lp):
        if not self.ready:                     # window-creation messages: let Windows handle them
            return DefWindowProc(hwnd, msg, wp, lp)
        try:
            if msg == WM_HOTKEY:
                self.on_hotkey()
            elif msg == WM_TRAY and (lp & 0xFFFF) in (0x0202, 0x0205):   # left / right button up
                self.menu()
            elif msg == WM_RELOAD:
                self.cfg = load_cfg()
                self.register()
                if self.hk_ok:
                    self.notify(T("hk_now", hk=self.hk()))
                elif self.cfg["enabled"]:
                    self.notify(T("hk_fail", hk=self.hk()), 2)
            elif msg == self.msg_taskbar:      # Explorer restarted: put the icon back
                self.add_icon()
            elif msg == WM_DESTROY:
                UnregisterHotKey(hwnd, 1)
                Shell_NotifyIcon(2, ctypes.byref(self._nid(0)))
                PostQuitMessage(0)
                return 0
        except Exception as e:  # noqa — never let the tray app die from one bad call
            log(f"ERROR {e!r}")
            self.notify(T("error", e=e), 3)
        return DefWindowProc(hwnd, msg, wp, lp)

    def run(self):
        msg = W.MSG()
        while GetMessage(ctypes.byref(msg), None, 0, 0) > 0:
            TranslateMessage(ctypes.byref(msg))
            DispatchMessage(ctypes.byref(msg))


# ------------------------------------------------------------------ hotkey dialog (separate process)
def other_app_hotkeys():
    """Hotkeys of companion tools (e.g. ShortsInfoExtractor), even when they are not running right now."""
    out = {}
    try:
        p = os.path.join(os.environ.get("APPDATA", ""), "ShortsInfoExtractor", "config.json")
        with open(p, encoding="utf-8") as f:
            h = json.load(f).get("hotkey")
        if h:
            out[combo_label(h["mods"], h["key"])] = T("sie")
    except Exception:  # noqa
        pass
    return out




def hotkey_dialog():
    import tkinter as tk
    cfg = load_cfg()
    taken = {**T("bl"), **other_app_hotkeys()}
    dark = dark_mode()
    C = (dict(bg="#202020", card="#2b2b2b", fg="#f3f3f3", muted="#a3a3a3", line="#3d3d3d",
              accent="#4c8dff", accent2="#3b78e7", red="#ff8a80", green="#6ee7a0", off="#3d3d3d", offfg="#8a8a8a")
         if dark else
         dict(bg="#f3f3f3", card="#ffffff", fg="#1f2937", muted="#6b7280", line="#d9dce1",
              accent="#2563eb", accent2="#1d4ed8", red="#b91c1c", green="#15803d", off="#e5e7eb", offfg="#9ca3af"))
    root = tk.Tk()
    root.withdraw()
    root.title(T("d_title"))
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.configure(bg=C["bg"])
    try:                                       # Unbox icon on the window
        root.iconbitmap(sys.executable if FROZEN else os.path.join(os.path.dirname(os.path.abspath(__file__)), "unbox.ico"))
    except Exception:  # noqa
        pass
    font = T("font")
    f = tk.Frame(root, bg=C["bg"], padx=24, pady=20)
    f.pack()
    tk.Label(f, text=T("d_prompt"), font=(font, 13, "bold"), bg=C["bg"], fg=C["fg"]).pack(anchor="w")
    tk.Label(f, text=T("d_hint", hk=combo_label(cfg['mods'], cfg['key'])), font=(font, 9),
             bg=C["bg"], fg=C["muted"]).pack(anchor="w", pady=(4, 14))
    combo = tk.StringVar(value=T("d_wait"))
    tk.Label(f, textvariable=combo, font=("Consolas", 18, "bold"), bg=C["card"], fg=C["accent"], width=22,
             pady=14, highlightthickness=1, highlightbackground=C["line"]).pack(fill="x")
    msg = tk.Label(f, text=" ", wraplength=380, justify="left", font=(font, 9), bg=C["bg"], fg=C["muted"])
    msg.pack(anchor="w", pady=(10, 16))
    row = tk.Frame(f, bg=C["bg"])
    row.pack(fill="x")
    chosen = {}

    def ok():
        if chosen:
            cfg.update(chosen, enabled=True)
            save_cfg(cfg)
            root.destroy()

    def flat(text, cmd, primary):
        b = tk.Button(row, text=text, command=cmd, font=(font, 10), relief="flat", bd=0, padx=18, pady=5,
                      cursor="hand2", bg=C["accent"] if primary else C["card"],
                      fg="#ffffff" if primary else C["fg"],
                      activebackground=C["accent2"] if primary else C["line"],
                      activeforeground="#ffffff" if primary else C["fg"],
                      disabledforeground=C["offfg"], highlightthickness=0 if primary else 1,
                      highlightbackground=C["line"])
        b.pack(side="right", padx=(8, 0))
        return b

    b_ok = flat(T("d_ok"), ok, True)
    flat(T("d_cancel"), root.destroy, False)

    def set_ok(on):
        b_ok.config(state="normal" if on else "disabled", bg=C["accent"] if on else C["off"],
                    cursor="hand2" if on else "arrow")

    set_ok(False)

    def on_key(e):
        chosen.clear()
        set_ok(False)
        vk = e.keycode
        key = chr(vk) if (65 <= vk <= 90 or 48 <= vk <= 57) else (f"F{vk - 111}" if 112 <= vk <= 123 else None)
        if key is None:
            return "break"                     # modifier alone or unsupported key
        mods = [m for m, bit in (("ctrl", 0x4), ("alt", 0x20000), ("shift", 0x1)) if e.state & bit]
        label = combo_label(mods, key)
        combo.set(label)
        if len(mods) < 2 or not {"ctrl", "alt"} & set(mods):
            msg.config(text=T("d_mods"), fg=C["red"])
        elif label in taken:
            msg.config(text=T("d_taken", hk=label, what=taken[label]), fg=C["red"])
        elif not RegisterHotKey(None, 0x5A5B, mods_mask(mods), key_to_vk(key)):
            err = ctypes.get_last_error()
            msg.config(text=T("d_inuse", hk=label) if err == 1409 else T("d_failed", hk=label, err=err),
                       fg=C["red"])
        else:
            UnregisterHotKey(None, 0x5A5B)
            chosen.update(mods=mods, key=key)
            set_ok(True)
            msg.config(text=T("d_free"), fg=C["green"])
        return "break"

    root.bind("<KeyPress>", on_key)
    root.bind("<Return>", lambda e: ok())
    root.bind("<Escape>", lambda e: root.destroy())
    root.update_idletasks()
    root.geometry(f"+{(root.winfo_screenwidth() - root.winfo_reqwidth()) // 2}+"
                  f"{(root.winfo_screenheight() - root.winfo_reqheight()) // 3}")
    if dark:                                   # dark title bar to match (Windows 10 2004+ / 11)
        try:
            root.update()                      # window must exist first (still hidden)
            hwnd = W.HWND(int(root.wm_frame(), 16))
            on = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), ctypes.sizeof(on))
        except Exception:  # noqa
            pass
    root.deiconify()
    root.focus_force()
    root.mainloop()


if __name__ == "__main__":
    if "--set-hotkey" in sys.argv:
        hotkey_dialog()
        sys.exit(0)
    CreateMutex(None, False, "Local\\UnboxTrayApp")
    if ctypes.get_last_error() == 183:         # ERROR_ALREADY_EXISTS
        MessageBox(None, T("running"), APP, 0x40)
        sys.exit(0)
    Tray().run()
