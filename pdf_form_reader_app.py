"""
Pinky - Form Reader: the desktop app.

The same reader as pdf_form_reader.py, with a window styled like GalloScript
(egallo8/YesLaw): an HTML page (ui/) shown in a native window by pywebview,
the way GalloScript's desktop app is built. The page calls the methods of
`Api` below; it never touches a file itself and makes no network request.
No local web server is started either: pywebview hands the page `Api`
directly.

Runs only on this computer; nothing is sent anywhere.

Settings are remembered between uses in a small text file:
  Windows: %LOCALAPPDATA%\\Pinky\\settings.txt
  other:   ~/.pinky/settings.txt
It holds folder paths and file names only, never anything read from a PDF.

`Pinky.exe --selftest` checks that a built copy carries its page
and can read a PDF; the build runs it before offering the .exe for download.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

import pdf_form_reader as core

APP_NAME = "Pinky"
WINDOW_TITLE = "Pinky - Form Reader"

WINDOW = {"width": 1180, "height": 780, "min_size": (980, 640)}

# The title bar, as GalloScript paints it on Windows 11: its dark card
# colour with white writing (galloscript_web/desktop.py, TITLE_BAR).
TITLE_BAR = "#2B2729"
TITLE_TEXT = "#FFFFFF"


def ui_dir() -> Path:
    """Where the page is: beside this file, or inside the built .exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "ui"


def settings_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / APP_NAME / "settings.txt"
    return Path.home() / ".pinky" / "settings.txt"


def default_results_parent() -> str:
    docs = Path.home() / "Documents"
    return str(docs if docs.is_dir() else Path.home())


def _settings_from(data: dict, strict: bool = False) -> core.Settings:
    """Settings from what the page sends, checked rather than trusted.
    strict: a file type that is not one raises ValueError instead of being dropped."""
    def pick(key, allowed, default):
        value = str(data.get(key) or "")
        return value if value in allowed else default

    names, seen = [], set()
    for raw in data.get("names") or []:
        name = " ".join(str(raw).split())
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            names.append(name)
    types = []
    for raw in data.get("types") or []:
        try:
            types.extend(core.clean_types([raw]))
        except ValueError:
            if strict:
                raise
    return core.Settings(
        types=list(dict.fromkeys(types)),
        folder=str(data.get("folder") or "").strip().strip('"'),
        start=pick("start", {"year", "month", "job"}, "year"),
        look_in=pick("look_in", {"main", "all"}, "main"),
        zips=bool(data.get("zips")),
        names=names,
        match=pick("match", {"partial", "complete"}, "partial"),
        form=pick("form", {"any", "pink"}, "any"),
        out=str(data.get("out") or "").strip().strip('"'),
    )


def _as_dict(s: core.Settings) -> dict:
    return {"folder": s.folder, "start": s.start, "look_in": s.look_in, "zips": s.zips,
            "names": list(s.names), "match": s.match, "out": s.out, "types": list(s.types),
            "form": s.form}


class Api:
    """What the page may ask for. Every public method is callable from it.

    State is kept in underscore names: pywebview offers the page every
    public attribute, and a window object among them would be walked into.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._state = {"state": "idle", "files_read": 0, "now": ""}
        self._window = None

    # ---- settings
    def load(self) -> dict:
        try:
            s = core.load_settings(settings_path())
        except core.SettingsError:
            s = core.Settings()  # first run, or the file was edited badly: start fresh
        if not s.out:
            s.out = default_results_parent()
        return _as_dict(s)

    def save(self, data: dict) -> bool:
        try:
            core.save_settings(_settings_from(data), settings_path())
            return True
        except OSError:
            return False  # remembering is a convenience; never block on it

    # ---- choosing folders
    def pick_folder(self, start: str = "", title: str = "Choose a folder") -> str | None:
        if sys.platform == "win32":
            try:
                return windows_folder_dialog(start, title, self._owner()) or None
            except Exception:
                pass
        if self._window is not None:
            import webview
            picked = self._window.create_file_dialog(webview.FOLDER_DIALOG, directory=start or "")
            return picked[0] if picked else None
        return None

    def _owner(self) -> int:
        try:
            return int(self._window.native.Handle.ToInt64())
        except Exception:
            return 0

    # ---- reading
    def start(self, data: dict) -> dict:
        if self._worker and self._worker.is_alive():
            return {"ok": False, "error": "Already reading."}
        try:
            settings = _settings_from(data, strict=True)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if not settings.folder:
            return {"ok": False, "error": "Choose the folder to read first (step 1)."}
        root = Path(settings.folder).expanduser()
        if not root.is_dir():
            return {"ok": False, "error": f"That folder was not found: {root}"}
        parent = Path(settings.out or default_results_parent()).expanduser()
        if not parent.is_dir():
            return {"ok": False, "error": f"The folder to save results in was not found: {parent}"}
        root = root.resolve()
        out_dir = parent.resolve() / core.dated_folder_name()
        problem = core.results_folder_problem(root, out_dir)
        if problem:
            return {"ok": False, "error": problem}

        self.save(_as_dict(settings))
        self._stop.clear()
        with self._lock:
            self._state = {"state": "running", "files_read": 0, "now": ""}
        self._worker = threading.Thread(target=self._work, args=(settings, root, out_dir), daemon=True)
        self._worker.start()
        return {"ok": True}

    def _work(self, settings: core.Settings, root: Path, out_dir: Path):
        report = None

        def progress(n, shown):
            with self._lock:
                self._state["files_read"] = n
                self._state["now"] = shown

        try:
            report = core.Report(out_dir, settings.start, root.name, settings.form, root)
            (out_dir / "settings-used.txt").write_text(settings.describe(), encoding="utf-8")
            stopped = False
            try:
                core.scan(root, report, settings, on_progress=progress, should_stop=self._stop.is_set)
            except core.Cancelled:
                stopped = True
            report.close()
            with self._lock:
                self._state = {
                    "state": "stopped" if stopped else "done",
                    "counts": dict(report.counts),
                    "lines": core.summary_lines(report, settings),
                    "main_only": settings.look_in == "main",
                    "types": [t.upper() for t in settings.types],
                    "form": settings.form,
                    "results": str(out_dir),
                    "can_open": hasattr(os, "startfile"),
                    "files_read": self._state.get("files_read", 0),
                }
        except Exception as exc:
            if report is not None:
                report.close()
            with self._lock:
                self._state = {"state": "error", "error": f"Something went wrong: {type(exc).__name__}: {exc}"}

    def status(self) -> dict:
        with self._lock:
            return dict(self._state)

    def check_type(self, raw: str) -> dict:
        """For the page's Add button: the tidy type, or why it is not one."""
        try:
            t = core.normal_type(raw)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if t == "pdf":
            return {"ok": False, "error": "PDFs are always read."}
        return {"ok": True, "type": t}

    def stop(self) -> bool:
        self._stop.set()
        return True

    def open_results(self) -> bool:
        results = self.status().get("results")
        if results and hasattr(os, "startfile"):
            os.startfile(results)  # Windows: opens the folder in File Explorer
            return True
        return False

    def wait(self, timeout: float = 60) -> dict:
        """For tests and the self-check: wait for a run to end."""
        if self._worker:
            self._worker.join(timeout)
        return self.status()


# --------------------------------------------------------------------------
# Windows-only window touches, after GalloScript's galloscript_web/desktop.py
# --------------------------------------------------------------------------

def windows_folder_dialog(start: str, title: str, owner: int = 0) -> str:
    """Windows' own folder chooser, asked for directly. -> the path, or ''."""
    import ctypes
    from ctypes import wintypes

    class BROWSEINFOW(ctypes.Structure):
        _fields_ = [("hwndOwner", wintypes.HWND),
                    ("pidlRoot", ctypes.c_void_p),
                    ("pszDisplayName", wintypes.LPWSTR),
                    ("lpszTitle", wintypes.LPCWSTR),
                    ("ulFlags", wintypes.UINT),
                    ("lpfn", ctypes.c_void_p),
                    ("lParam", wintypes.LPARAM),
                    ("iImage", ctypes.c_int)]

    BIF_RETURNONLYFSDIRS, BIF_NEWDIALOGSTYLE = 0x00000001, 0x00000040
    BFFM_INITIALIZED, BFFM_SETSELECTIONW = 1, 0x467

    ctypes.windll.ole32.CoInitialize(None)
    callback = ctypes.c_void_p()
    if start and os.path.isdir(start):
        proto = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.UINT,
                                   wintypes.LPARAM, wintypes.LPARAM)

        def on_message(hwnd, message, param, data):
            if message == BFFM_INITIALIZED:
                ctypes.windll.user32.SendMessageW(hwnd, BFFM_SETSELECTIONW, 1, start)
            return 0

        on_message = proto(on_message)
        windows_folder_dialog._keep = on_message  # not collected mid-call
        callback = ctypes.cast(on_message, ctypes.c_void_p)

    info = BROWSEINFOW()
    info.hwndOwner = owner
    info.pszDisplayName = ctypes.cast(ctypes.create_unicode_buffer(260), wintypes.LPWSTR)
    info.lpszTitle = title
    info.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE
    info.lpfn = callback
    item = ctypes.windll.shell32.SHBrowseForFolderW(ctypes.byref(info))
    if not item:
        return ""
    path = ctypes.create_unicode_buffer(32768)
    ok = ctypes.windll.shell32.SHGetPathFromIDListW(ctypes.c_void_p(item), path)
    ctypes.windll.ole32.CoTaskMemFree(ctypes.c_void_p(item))
    return path.value if ok else ""


def _colorref(hex_colour: str) -> int:
    r, g, b = (int(hex_colour.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return (b << 16) | (g << 8) | r


def paint_title_bar(title: str) -> bool:
    """Colour this app's title bar like GalloScript's (Windows 11; dark on 10)."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes
    user32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid() and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value == title:
                found.append(hwnd)
        return True

    user32.EnumWindows(each, 0)

    def put(hwnd, attribute, value):
        v = ctypes.c_int(value)
        return dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(v), ctypes.sizeof(v)) == 0

    ok = False
    for hwnd in found:
        put(hwnd, 20, 1)                                   # dark mode
        ok = put(hwnd, 35, _colorref(TITLE_BAR)) or ok     # caption
        put(hwnd, 36, _colorref(TITLE_TEXT))               # its text
        put(hwnd, 34, _colorref(TITLE_BAR))                # the border
    return ok


# --------------------------------------------------------------------------
# Starting
# --------------------------------------------------------------------------

def open_the_streams():
    """A windowed build has no console streams; give it harmless ones."""
    for name, mode in (("stdin", "r"), ("stdout", "w"), ("stderr", "w")):
        if getattr(sys, name, None) is None:
            setattr(sys, name, open(os.devnull, mode))


def selftest() -> int:
    """For the build check: the page is carried, the window library loads,
    and a run started the way the page starts one reads a PDF."""
    from pypdf import PdfWriter

    problems = []
    for name in ("index.html", "style.css", "app.js", "fonts/PlayfairDisplay-Bold.woff2"):
        if not (ui_dir() / name).is_file():
            problems.append(f"missing ui/{name}")
    try:
        import webview  # noqa: F401
    except Exception as exc:
        problems.append(f"window library will not load: {exc!r}")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        os.environ["LOCALAPPDATA"] = str(base / "appdata")
        job = base / "2026" / "March" / "Job 1"
        job.mkdir(parents=True)
        (base / "results").mkdir()
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(job / "Worksheet.pdf", "wb") as fh:
            writer.write(fh)
        api = Api()
        answer = api.start({"folder": str(base / "2026"), "names": ["worksheet"],
                            "out": str(base / "results")})
        if not answer.get("ok"):
            problems.append(f"run refused: {answer}")
        else:
            st = api.wait(60)
            if st.get("state") != "done" or st["counts"]["pdfs"] != 1:
                problems.append(f"run did not read the PDF: {st}")

    if problems:
        with open(Path(tempfile.gettempdir()) / "pinky-selftest.txt", "w") as fh:
            fh.write("\n".join(problems))
        print("\n".join(problems))
    return 1 if problems else 0


def main():
    open_the_streams()
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    import webview

    api = Api()
    window = webview.create_window(WINDOW_TITLE, str(ui_dir() / "index.html"), js_api=api,
                                   background_color="#D9D9DB", **WINDOW)
    api._window = window
    window.events.shown += lambda: paint_title_bar(WINDOW_TITLE)
    webview.start()


if __name__ == "__main__":
    main()
