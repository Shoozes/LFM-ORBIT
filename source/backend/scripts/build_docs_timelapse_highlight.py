"""Build README-safe timelapse highlight media from a cached Sentinel replay."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = BACKEND_ROOT / "assets" / "seeded_data" / "sh_cc0e95b7.webm"
DEFAULT_GIF = REPO_ROOT / "docs" / "media" / "timelapse" / "highlight-greenland-ice-timelapse.gif"
DEFAULT_WEBM = REPO_ROOT / "docs" / "media" / "timelapse" / "highlight-greenland-ice-timelapse.webm"
GITHUB_FREE_INLINE_LIMIT_BYTES = 10 * 1024 * 1024


def _run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise SystemExit("ffmpeg is required to build docs timelapse highlight media.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"ffmpeg failed with exit code {exc.returncode}") from exc


def build_highlight(
    source: Path,
    gif_path: Path,
    webm_path: Path,
    *,
    trim_start_seconds: float,
    gif_width: int,
    webm_width: int,
    max_gif_bytes: int,
) -> None:
    if not source.exists():
        raise SystemExit(f"Source timelapse does not exist: {source}")
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required to build docs timelapse highlight media.")

    gif_path.parent.mkdir(parents=True, exist_ok=True)
    webm_path.parent.mkdir(parents=True, exist_ok=True)

    source_text = str(source)
    trim_text = f"{trim_start_seconds:.2f}"
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            trim_text,
            "-i",
            source_text,
            "-vf",
            (
                f"fps=1.5,scale={gif_width}:-1:flags=lanczos,"
                "split[s0][s1];[s0]palettegen=max_colors=96[p];"
                "[s1][p]paletteuse=dither=bayer:bayer_scale=5"
            ),
            str(gif_path),
        ]
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            trim_text,
            "-i",
            source_text,
            "-vf",
            f"scale={webm_width}:-2:flags=lanczos",
            "-c:v",
            "libvpx-vp9",
            "-b:v",
            "0",
            "-crf",
            "34",
            "-an",
            str(webm_path),
        ]
    )

    gif_size = gif_path.stat().st_size
    if gif_size > max_gif_bytes:
        raise SystemExit(
            f"GIF is too large for GitHub inline README use: {gif_size} bytes > {max_gif_bytes} bytes"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build docs timelapse GIF/WebM highlight media.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--gif", type=Path, default=DEFAULT_GIF)
    parser.add_argument("--webm", type=Path, default=DEFAULT_WEBM)
    parser.add_argument("--trim-start-seconds", type=float, default=0.67)
    parser.add_argument("--gif-width", type=int, default=560)
    parser.add_argument("--webm-width", type=int, default=800)
    parser.add_argument("--max-gif-mb", type=float, default=10.0)
    args = parser.parse_args()

    build_highlight(
        args.source,
        args.gif,
        args.webm,
        trim_start_seconds=args.trim_start_seconds,
        gif_width=args.gif_width,
        webm_width=args.webm_width,
        max_gif_bytes=int(args.max_gif_mb * 1024 * 1024),
    )
    print(f"Wrote {args.gif} ({args.gif.stat().st_size} bytes)")
    print(f"Wrote {args.webm} ({args.webm.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
