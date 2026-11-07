"""Record an explicitly requested desktop demo; stop with a file or a time limit."""

import argparse
import json
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg

from windows_computer_use.demo_capture import marker_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--size", required=True, help="Capture width x height")
    parser.add_argument("--offset", default="0,0")
    parser.add_argument("--seconds", type=int, default=240)
    parser.add_argument("--stop-file", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    offset_x, offset_y = args.offset.split(",")
    marker = marker_path()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps({"include_indicator": True, "expires_at": time.time() + args.seconds + 15}),
        encoding="utf-8",
    )
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner",
        "-y",
        "-f",
        "gdigrab",
        "-framerate",
        "20",
        "-draw_mouse",
        "1",
        "-offset_x",
        offset_x,
        "-offset_y",
        offset_y,
        "-video_size",
        args.size,
        "-i",
        "desktop",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "19",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(args.output),
    ]
    metadata = {"started_at": time.time(), "size": args.size, "offset": args.offset}
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    process = None
    try:
        with args.output.with_suffix(".log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            deadline = time.monotonic() + args.seconds
            while (
                process.poll() is None
                and time.monotonic() < deadline
                and not args.stop_file.exists()
            ):
                time.sleep(0.2)
            if process.poll() is None:
                process.communicate(b"q\n", timeout=15)
            if process.returncode:
                raise RuntimeError(f"Recorder failed: {args.output.with_suffix('.log')}")
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        marker.unlink(missing_ok=True)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
