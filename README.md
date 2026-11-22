# Unbox

A tiny Windows tray tool. Select folders in File Explorer, press a hotkey, and everything inside
moves up next to where the folder was (renamed with the folder name, if you like). The emptied
folder is then removed.

It sits idle in the tray (0% CPU) and only does something when you press its hotkey.
English and 繁體中文 interface.

## Download

Get `Unbox.exe` from [Releases](../../releases), double-click it, and a box icon appears in the tray.
No install, no window.

## Use

1. In File Explorer select one or more folders.
2. Press the hotkey (default **Ctrl+Alt+U**).

| Naming | `Show\Ep01.mp4`, `Show\Ep02.mp4` become |
|---|---|
| Prefix | `Show_Ep01.mp4`, `Show_Ep02.mp4` |
| Suffix | `Ep01_Show.mp4`, `Ep02_Show.mp4` |
| Keep names | `Ep01.mp4`, `Ep02.mp4` (subfolders move out too, unchanged) |

## Safety

- **All or nothing per folder:** every new name is checked first. If any already exists, that
  folder is skipped and nothing in it moves. If a move fails midway (file in use), the files
  already moved are put back.
- Never overwrites. Only removes a folder once it is empty.
- With Prefix/Suffix, subfolders stay where they are (the folder is then kept).
- Names that already contain the folder name are not changed again.
- `desktop.ini` / `Thumbs.db` (Windows junk) are deleted with the folder, not renamed.
- Every move is logged in `%APPDATA%\Unbox\unbox.log`.

## Tray menu (right-click)

- **Naming:** Prefix / Suffix / Keep names
- **Separator:** `_` / space / `-` / none
- **Language:** English / 繁體中文 (first run follows the Windows display language)
- **Set hotkey…:** press a combination; it checks Windows and other programs for conflicts
- Pause hotkey, Start with Windows, How to use, Quit

The menu and the hotkey window follow Windows dark/light mode.

## Notes

- Reads the Explorer selection with Explorer's own *Copy as path* (Ctrl+Shift+C). Your text
  clipboard is restored afterwards (a copied image would be replaced).
- Settings: `%APPDATA%\Unbox\config.json`

## Build from source

Python 3.8+ on Windows, standard library only (`unbox.pyw` runs directly with `pythonw`).

```
pip install pyinstaller
build_exe.bat
```

`make_icon.py` (needs Pillow) redraws `unbox.ico`.
