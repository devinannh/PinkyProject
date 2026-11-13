"""
PDF Form Reader - the window version.

The same reader as pdf_form_reader.py, with a window instead of typed
commands: pick the folder, choose where to look and which file names to find,
press Read PDFs. Runs only on this computer; nothing is sent anywhere.

Settings are remembered between uses in a small text file:
  Windows: %LOCALAPPDATA%\\PDF Form Reader\\settings.txt
  other:   ~/.pdf-form-reader/settings.txt
It holds folder paths and file names only, never anything read from a PDF.

Build the Windows .exe with PyInstaller (see .github/workflows/build-windows-exe.yml).
`PDF Form Reader.exe --selftest` checks that a built copy starts and can read a PDF.
"""

from __future__ import annotations

import os
import queue
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pdf_form_reader as core

APP_NAME = "PDF Form Reader"
APP_VERSION = "1.0"


def settings_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / APP_NAME / "settings.txt"
    return Path.home() / ".pdf-form-reader" / "settings.txt"


def default_results_parent() -> str:
    docs = Path.home() / "Documents"
    return str(docs if docs.is_dir() else Path.home())


def load_remembered() -> core.Settings:
    try:
        return core.load_settings(settings_path())
    except core.SettingsError:
        return core.Settings()  # first run, or the file was edited badly: start fresh


class App:
    PAD = 10

    def __init__(self, root: tk.Tk):
        self.root = root
        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.stop_flag = threading.Event()
        self.last_results: Path | None = None

        root.title(APP_NAME)
        root.minsize(760, 520)
        self._style()

        s = load_remembered()
        self.folder = tk.StringVar(value=s.folder)
        self.start = tk.StringVar(value=s.start)
        self.look_in = tk.StringVar(value=s.look_in)
        self.zips = tk.BooleanVar(value=s.zips)
        self.match = tk.StringVar(value=s.match)
        self.results_parent = tk.StringVar(value=s.out or default_results_parent())
        self.new_name = tk.StringVar()
        self.status = tk.StringVar(value="Ready.")

        self._build(s.names)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(100, self._poll)

    # ---------------------------------------------------------------- layout
    def _style(self):
        style = ttk.Style(self.root)
        if "vista" not in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Hint.TLabel", foreground="#5f5a55")
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Run.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 6))

    def _section(self, parent, row, title, column=0, columnspan=2, padx=(0, 0)):
        frame = ttk.LabelFrame(parent, text=title, style="Section.TLabelframe", padding=self.PAD)
        frame.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", pady=(0, self.PAD), padx=padx)
        frame.columnconfigure(0, weight=1)
        return frame

    def _build(self, names):
        outer = ttk.Frame(self.root, padding=14)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=2)
        outer.columnconfigure(1, weight=3)

        ttk.Label(outer, text=APP_NAME, style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            outer,
            text="Lists the answers typed or ticked in fillable PDF forms. "
                 "Runs only on this computer; nothing is sent anywhere.",
            style="Hint.TLabel", wraplength=780,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        # 1. Folder to read
        f1 = self._section(outer, 2, "1.  Folder to read")
        ttk.Entry(f1, textvariable=self.folder).grid(row=0, column=0, sticky="ew")
        ttk.Button(f1, text="Browse…", command=self.pick_folder).grid(row=0, column=1, padx=(8, 0))
        r = ttk.Frame(f1)
        r.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(r, text="This folder is:").pack(side="left", padx=(0, 8))
        for value, text in (("year", "a year folder"), ("month", "a month folder"), ("job", "one job folder")):
            ttk.Radiobutton(r, text=text, value=value, variable=self.start).pack(side="left", padx=(0, 12))

        # 2. Where to look
        f2 = self._section(outer, 3, "2.  Where to look in each job folder", column=0, columnspan=1, padx=(0, 8))
        ttk.Radiobutton(f2, text="Main job folder only",
                        value="main", variable=self.look_in).grid(row=0, column=0, sticky="w")
        ttk.Label(f2, text="Subfolders are not opened.", style="Hint.TLabel").grid(row=1, column=0, sticky="w", padx=(22, 0))
        ttk.Radiobutton(f2, text="Main job folder and all its subfolders",
                        value="all", variable=self.look_in).grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Separator(f2).grid(row=3, column=0, sticky="ew", pady=10)
        ttk.Checkbutton(f2, text="Also read PDFs inside zip files",
                        variable=self.zips).grid(row=4, column=0, sticky="w")

        # 3. File names
        f3 = self._section(outer, 3, "3.  File names to look for", column=1, columnspan=1)
        lb_frame = ttk.Frame(f3)
        lb_frame.grid(row=0, column=0, sticky="ew")
        lb_frame.columnconfigure(0, weight=1)
        self.names = tk.Listbox(lb_frame, height=4, activestyle="none", exportselection=False)
        self.names.grid(row=0, column=0, sticky="ew")
        sb = ttk.Scrollbar(lb_frame, orient="vertical", command=self.names.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.names.configure(yscrollcommand=sb.set)
        for n in names:
            self.names.insert("end", n)
        side = ttk.Frame(f3)
        side.grid(row=0, column=1, sticky="n", padx=(8, 0))
        ttk.Button(side, text="Remove", command=self.remove_name).pack(fill="x")

        add = ttk.Frame(f3)
        add.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        add.columnconfigure(0, weight=1)
        entry = ttk.Entry(add, textvariable=self.new_name)
        entry.grid(row=0, column=0, sticky="ew")
        entry.bind("<Return>", lambda _e: self.add_name())
        ttk.Button(add, text="Add name", command=self.add_name).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(
            f3,
            text="Empty list = read every PDF. Capitals, extra spaces and “.pdf” never matter.",
            style="Hint.TLabel", wraplength=420,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 6))
        ttk.Radiobutton(f3, text="Partial: the file name contains it",
                        value="partial", variable=self.match).grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(f3, text="Complete: the file name is exactly it",
                        value="complete", variable=self.match).grid(row=4, column=0, columnspan=2, sticky="w")
        ttk.Label(
            f3,
            text="“worksheet” finds “Smith Worksheet FINAL.pdf” with Partial, "
                 "but only “Worksheet.pdf” with Complete.",
            style="Hint.TLabel", wraplength=420,
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=(22, 0))

        # 4. Results
        f4 = self._section(outer, 5, "4.  Save results in")
        ttk.Entry(f4, textvariable=self.results_parent).grid(row=0, column=0, sticky="ew")
        ttk.Button(f4, text="Browse…", command=self.pick_results).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(
            f4,
            text="A new dated folder is made here each time. Do not choose a OneDrive, iCloud, "
                 "Dropbox, Google Drive or Box folder: those copy files to the cloud.",
            style="Hint.TLabel", wraplength=760,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # Run
        run = ttk.Frame(outer)
        run.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(2, 6))
        run.columnconfigure(3, weight=1)
        self.run_btn = ttk.Button(run, text="Read PDFs", style="Run.TButton", command=self.start_run)
        self.run_btn.grid(row=0, column=0)
        self.stop_btn = ttk.Button(run, text="Stop", command=self.stop_run, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=(8, 0))
        self.open_btn = ttk.Button(run, text="Open results folder", command=self.open_results, state="disabled")
        self.open_btn.grid(row=0, column=2, padx=(8, 0))
        self.bar = ttk.Progressbar(run, mode="indeterminate")
        self.bar.grid(row=0, column=3, sticky="ew", padx=(12, 0))

        ttk.Label(outer, textvariable=self.status, wraplength=780).grid(row=7, column=0, columnspan=2, sticky="w")
        self.summary = tk.Text(outer, height=6, wrap="word", relief="flat", borderwidth=1,
                               background="#f6f4f1", padx=8, pady=6, state="disabled",
                               font=("Segoe UI", 9))
        self.summary.grid(row=8, column=0, columnspan=2, sticky="nsew", pady=(6, 6))
        summary_sb = ttk.Scrollbar(outer, orient="vertical", command=self.summary.yview)
        summary_sb.grid(row=8, column=2, sticky="ns", pady=(6, 6))
        self.summary.configure(yscrollcommand=summary_sb.set)
        outer.rowconfigure(8, weight=1)
        ttk.Label(
            outer,
            text="The results contain real client data. Keep them on this computer and delete them when done.",
            style="Hint.TLabel", wraplength=780,
        ).grid(row=9, column=0, columnspan=2, sticky="w")

        # Fit short screens: if the window would be taller than the screen,
        # start it shorter; the results box gives up the space.
        self.root.update_idletasks()
        want_h = self.root.winfo_reqheight()
        room_h = self.root.winfo_screenheight() - 90
        if want_h > room_h:
            self.root.geometry(f"{self.root.winfo_reqwidth()}x{room_h}+20+10")

    # --------------------------------------------------------------- actions
    def pick_folder(self):
        chosen = filedialog.askdirectory(title="Choose the folder to read", initialdir=self.folder.get() or None)
        if chosen:
            self.folder.set(os.path.normpath(chosen))

    def pick_results(self):
        chosen = filedialog.askdirectory(title="Choose where to save results",
                                         initialdir=self.results_parent.get() or None)
        if chosen:
            self.results_parent.set(os.path.normpath(chosen))

    def add_name(self):
        name = " ".join(self.new_name.get().split())
        if not name:
            return
        if name.casefold() not in (n.casefold() for n in self.names.get(0, "end")):
            self.names.insert("end", name)
        self.new_name.set("")

    def remove_name(self):
        for index in reversed(self.names.curselection()):
            self.names.delete(index)

    def current_settings(self) -> core.Settings:
        return core.Settings(
            folder=self.folder.get().strip().strip('"'),
            start=self.start.get(),
            look_in=self.look_in.get(),
            zips=bool(self.zips.get()),
            names=list(self.names.get(0, "end")),
            match=self.match.get(),
            out=self.results_parent.get().strip().strip('"'),
        )

    def remember(self):
        try:
            core.save_settings(self.current_settings(), settings_path())
        except OSError:
            pass  # remembering settings is a convenience; never block a run on it

    def _show_summary(self, text: str):
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")

    def start_run(self):
        settings = self.current_settings()
        if not settings.folder:
            messagebox.showwarning(APP_NAME, "Choose the folder to read first (step 1).")
            return
        root = Path(settings.folder).expanduser()
        if not root.is_dir():
            messagebox.showwarning(APP_NAME, f"That folder was not found:\n{root}")
            return
        parent = Path(settings.out or default_results_parent()).expanduser()
        if not parent.is_dir():
            messagebox.showwarning(APP_NAME, f"The folder to save results in was not found:\n{parent}")
            return
        root = root.resolve()
        out_dir = parent.resolve() / core.dated_folder_name()
        problem = core.results_folder_problem(root, out_dir)
        if problem:
            messagebox.showwarning(APP_NAME, problem)
            return
        if self.new_name.get().strip():
            if messagebox.askyesno(APP_NAME, f"Add “{self.new_name.get().strip()}” to the file names first?"):
                self.add_name()
                settings = self.current_settings()

        self.remember()
        self.stop_flag.clear()
        self.last_results = None
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.open_btn.configure(state="disabled")
        self.bar.start(12)
        self.status.set("Reading…")
        self._show_summary(settings.describe())
        self.worker = threading.Thread(target=self._work, args=(settings, root, out_dir), daemon=True)
        self.worker.start()

    def _work(self, settings: core.Settings, root: Path, out_dir: Path):
        """Runs in the background so the window stays responsive."""
        report = None
        try:
            report = core.Report(out_dir, settings.start, root.name)
            (out_dir / "settings-used.txt").write_text(settings.describe(), encoding="utf-8")
            core.scan(
                root, report, settings,
                on_progress=lambda n, shown: self.events.put(("progress", f"{n} files read. Now: {shown}")),
                should_stop=self.stop_flag.is_set,
            )
            report.close()
            self.events.put(("done", (report, settings, out_dir, False)))
        except core.Cancelled:
            report.close()
            self.events.put(("done", (report, settings, out_dir, True)))
        except Exception as exc:
            if report is not None:
                report.close()
            self.events.put(("error", f"{type(exc).__name__}: {exc}"))

    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress":
                    self.status.set(payload)
                elif kind == "done":
                    self._finished(*payload)
                elif kind == "error":
                    self._idle()
                    self.status.set("Something went wrong.")
                    messagebox.showerror(APP_NAME, f"Something went wrong:\n{payload}")
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _idle(self):
        self.bar.stop()
        self.bar["value"] = 0
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _finished(self, report, settings, out_dir, stopped):
        self._idle()
        self.last_results = out_dir
        if hasattr(os, "startfile"):
            self.open_btn.configure(state="normal")
        head = "Stopped. The results below cover only what was read before Stop." if stopped else "Finished."
        self.status.set(head)
        self._show_summary(
            "\n".join(core.summary_lines(report, settings))
            + f"\n\nResults saved in:\n{out_dir}\n  fields.csv  - one row per form field\n"
              "  files.csv   - one row per PDF, and any problems\n"
              "  settings-used.txt - the choices that made these results"
        )

    def stop_run(self):
        self.stop_flag.set()
        self.status.set("Stopping after the current file…")

    def open_results(self):
        if self.last_results and hasattr(os, "startfile"):
            os.startfile(self.last_results)  # Windows: opens the folder in File Explorer

    def on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP_NAME, "Still reading. Stop and close?"):
                return
            self.stop_flag.set()
            self.worker.join(timeout=10)
        self.remember()
        self.root.destroy()


def selftest() -> int:
    """For the build check: the window opens, and a PDF can be read and reported."""
    from pypdf import PdfWriter

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        job = base / "2026" / "March" / "Job 1"
        job.mkdir(parents=True)
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(job / "worksheet.pdf", "wb") as fh:
            writer.write(fh)
        settings = core.Settings(folder=str(base / "2026"), names=["worksheet"])
        report = core.Report(base / "results", "year", "2026")
        core.scan(base / "2026", report, settings, quiet=True)
        report.close()
        ok = report.counts["pdfs"] == 1 and (base / "results" / "files.csv").read_text(encoding="utf-8-sig").count("\n") == 2

        root = tk.Tk()
        App(root)
        root.update()
        root.after(300, root.destroy)
        root.mainloop()
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if sys.platform == "win32":
        try:  # sharp text on high-resolution screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
