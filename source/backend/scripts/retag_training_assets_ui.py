"""Optional Tkinter launcher for the Orbit training-asset retagger.

The CLI in retag_training_assets.py remains the source of truth. This module is
only a small desktop convenience wrapper around that script.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path


PROVIDERS = ("heuristic", "queue", "ollama", "openai")
DEFAULT_DATASET_DIR = Path(__file__).resolve().parents[3] / "runtime-data" / "modeling" / "orbit-export"


def build_retag_command(
    *,
    dataset_dir: Path,
    output_dir: Path | None,
    provider: str,
    model: str,
    video_frame_count: int,
    min_video_frames: int,
    scan_loose_assets: bool,
    temporal_sequences: bool,
) -> list[str]:
    """Build the subprocess command used by the Tkinter wrapper."""
    if provider not in PROVIDERS:
        raise ValueError(f"unsupported provider: {provider}")

    command = [
        sys.executable,
        str(Path(__file__).with_name("retag_training_assets.py")),
        "--dataset-dir",
        str(dataset_dir),
        "--provider",
        provider,
        "--video-frame-count",
        str(max(1, int(video_frame_count))),
        "--min-video-frames",
        str(max(2, int(min_video_frames))),
    ]
    if output_dir is not None:
        command.extend(["--output-dir", str(output_dir)])
    if model.strip():
        command.extend(["--model", model.strip()])
    if not scan_loose_assets:
        command.append("--no-loose-scan")
    if not temporal_sequences:
        command.append("--no-temporal-sequences")
    return command


def read_manifest_summary(output_dir: Path) -> str:
    """Return a compact manifest summary for UI display after a run."""
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        return "No manifest.json was written."
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return (
        f"Unique assets: {manifest.get('unique_training_assets', 0)}\n"
        f"Temporal sequences: {manifest.get('unique_temporal_sequences', 0)}\n"
        f"Duplicates removed: {manifest.get('duplicate_assets_removed', 0)}\n"
        f"Skipped assets: {manifest.get('skipped_assets', 0)}\n"
        f"Tagger failures: {manifest.get('tagger_failures', 0)}"
    )


def _default_output_dir(dataset_dir: Path) -> Path:
    return dataset_dir / "retagged_training"


def main() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:
        print(f"Tkinter is not available in this Python install: {exc}", file=sys.stderr)
        return 2

    root = tk.Tk()
    root.title("Orbit Training Asset Retagger")
    root.geometry("820x620")

    dataset_var = tk.StringVar(value=str(DEFAULT_DATASET_DIR))
    output_var = tk.StringVar(value=str(_default_output_dir(DEFAULT_DATASET_DIR)))
    last_auto_output = {"value": output_var.get()}
    provider_var = tk.StringVar(value="heuristic")
    model_var = tk.StringVar(value="")
    frame_count_var = tk.StringVar(value="4")
    min_frames_var = tk.StringVar(value="2")
    loose_scan_var = tk.BooleanVar(value=True)
    sequence_var = tk.BooleanVar(value=True)
    status_var = tk.StringVar(value="Ready.")

    def browse_dataset() -> None:
        path = filedialog.askdirectory(title="Select Orbit dataset export")
        if path:
            output_text = output_var.get().strip()
            next_auto_output = str(_default_output_dir(Path(path).resolve()))
            dataset_var.set(path)
            if not output_text or output_text == last_auto_output["value"]:
                output_var.set(next_auto_output)
            last_auto_output["value"] = next_auto_output

    def browse_output() -> None:
        path = filedialog.askdirectory(title="Select retag output directory")
        if path:
            output_var.set(path)

    frame = ttk.Frame(root, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text="Dataset directory").grid(row=0, column=0, sticky=tk.W, pady=4)
    ttk.Entry(frame, textvariable=dataset_var).grid(row=0, column=1, sticky=tk.EW, pady=4)
    ttk.Button(frame, text="Browse", command=browse_dataset).grid(row=0, column=2, padx=(8, 0), pady=4)

    ttk.Label(frame, text="Output directory").grid(row=1, column=0, sticky=tk.W, pady=4)
    ttk.Entry(frame, textvariable=output_var).grid(row=1, column=1, sticky=tk.EW, pady=4)
    ttk.Button(frame, text="Browse", command=browse_output).grid(row=1, column=2, padx=(8, 0), pady=4)

    ttk.Label(frame, text="Provider").grid(row=2, column=0, sticky=tk.W, pady=4)
    ttk.Combobox(frame, textvariable=provider_var, values=PROVIDERS, state="readonly").grid(row=2, column=1, sticky=tk.W, pady=4)

    ttk.Label(frame, text="Model").grid(row=3, column=0, sticky=tk.W, pady=4)
    ttk.Entry(frame, textvariable=model_var).grid(row=3, column=1, sticky=tk.EW, pady=4)

    ttk.Label(frame, text="Video frame count").grid(row=4, column=0, sticky=tk.W, pady=4)
    ttk.Entry(frame, textvariable=frame_count_var, width=10).grid(row=4, column=1, sticky=tk.W, pady=4)

    ttk.Label(frame, text="Minimum video frames").grid(row=5, column=0, sticky=tk.W, pady=4)
    ttk.Entry(frame, textvariable=min_frames_var, width=10).grid(row=5, column=1, sticky=tk.W, pady=4)

    ttk.Checkbutton(frame, text="Scan loose images/videos under dataset directory", variable=loose_scan_var).grid(row=6, column=1, sticky=tk.W, pady=4)
    ttk.Checkbutton(frame, text="Write ordered temporal sequence rows", variable=sequence_var).grid(row=7, column=1, sticky=tk.W, pady=4)

    log = tk.Text(frame, height=18, wrap=tk.WORD)
    log.grid(row=9, column=0, columnspan=3, sticky=tk.NSEW, pady=(12, 4))
    frame.rowconfigure(9, weight=1)

    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=log.yview)
    scrollbar.grid(row=9, column=3, sticky=tk.NS, pady=(12, 4))
    log.configure(yscrollcommand=scrollbar.set)

    run_button = ttk.Button(frame, text="Run Retag")
    run_button.grid(row=8, column=1, sticky=tk.W, pady=(8, 0))
    ttk.Label(frame, textvariable=status_var).grid(row=10, column=0, columnspan=3, sticky=tk.W, pady=4)

    def append_log(text: str) -> None:
        log.insert(tk.END, text)
        log.see(tk.END)

    def run_retag() -> None:
        try:
            dataset_dir = Path(dataset_var.get().strip()).resolve()
            output_dir = Path(output_var.get().strip()).resolve() if output_var.get().strip() else _default_output_dir(dataset_dir)
            command = build_retag_command(
                dataset_dir=dataset_dir,
                output_dir=output_dir,
                provider=provider_var.get(),
                model=model_var.get(),
                video_frame_count=int(frame_count_var.get()),
                min_video_frames=int(min_frames_var.get()),
                scan_loose_assets=loose_scan_var.get(),
                temporal_sequences=sequence_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        run_button.configure(state=tk.DISABLED)
        status_var.set("Running retag process...")
        append_log("\n$ " + " ".join(command) + "\n")

        def worker() -> None:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            for line in process.stdout:
                root.after(0, append_log, line)
            return_code = process.wait()
            def finish() -> None:
                run_button.configure(state=tk.NORMAL)
                if return_code == 0:
                    status_var.set("Done.")
                    append_log("\n" + read_manifest_summary(output_dir) + "\n")
                else:
                    status_var.set(f"Failed with exit code {return_code}.")
            root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    run_button.configure(command=run_retag)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
