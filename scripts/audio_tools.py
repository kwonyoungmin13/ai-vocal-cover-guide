"""Small audio helpers; no vocal separation, RVC training, or voice conversion.

Relative paths are resolved from the project directory, not the working directory.
Inputs are read only; every output, temporary file, and cache stays in this project.
Dependencies: numpy, soundfile. Preview and MP3 export also require FFmpeg on PATH.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(os.path.abspath(__file__)).parent.parent
BLOCK_FRAMES = 65536


def assert_plain_path(path: Path) -> None:
    """Reject symlinks/reparse points, including existing parent directories."""
    for item in (path, *path.parents):
        try:
            details = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(details.st_mode) or (
            getattr(details, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError(f"Links and junctions are not allowed for writes: {item}")


def workspace_path(value: str | Path) -> Path:
    """Return a project-contained, non-linked path suitable for a new write."""
    raw = Path(value)
    path = Path(os.path.abspath(raw if raw.is_absolute() else PROJECT_ROOT / raw))
    try:
        path.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError(f"Output must be inside project: {PROJECT_ROOT}") from error
    if path == PROJECT_ROOT:
        raise ValueError("A file or subdirectory is required, not the project root")
    assert_plain_path(path)
    return path


def configure_runtime() -> None:
    assert_plain_path(PROJECT_ROOT)
    local_environment = {
        "TEMP": ".tmp", "TMP": ".tmp", "PIP_CACHE_DIR": ".cache/pip",
        "PYTHONPYCACHEPREFIX": ".cache/pycache", "PYTHONUSERBASE": ".cache/python_userbase",
        "XDG_CACHE_HOME": ".cache",
        "HF_HOME": ".cache/huggingface", "TORCH_HOME": ".cache/torch",
        "CUDA_CACHE_PATH": ".cache/cuda", "NUMBA_CACHE_DIR": ".cache/numba",
        "MPLCONFIGDIR": ".cache/matplotlib",
    }
    for name, relative in local_environment.items():
        target = workspace_path(relative)
        target.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(target)
    sys.pycache_prefix = os.environ["PYTHONPYCACHEPREFIX"]
    tempfile.tempdir = os.environ["TEMP"]


def input_path(value: str | Path) -> Path:
    raw = Path(value)
    path = (raw if raw.is_absolute() else PROJECT_ROOT / raw).resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"Input is not a regular file: {path}")
    return path


def new_output(value: str | Path, extensions: tuple[str, ...] | None = None) -> Path:
    path = workspace_path(value)
    if extensions and path.suffix.lower() not in extensions:
        raise ValueError(f"Output extension must be one of: {', '.join(extensions)}")
    if os.path.lexists(path):
        raise FileExistsError(f"Refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_new_json(value: str | Path, payload: dict) -> None:
    path = new_output(value, (".json",))
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def publish_file(staged: Path, destination: Path) -> None:
    """Exclusive create also prevents overwriting if another process wins a race."""
    destination = new_output(destination)
    created = False
    try:
        with destination.open("xb") as target:
            created = True
            with staged.open("rb") as source:
                shutil.copyfileobj(source, target, length=1024 * 1024)
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise


def dbfs(value: float) -> float | None:
    return 20.0 * math.log10(value) if value > 0 else None


def inspect_audio(path: Path) -> dict:
    """Decode every frame; metadata-only inspection cannot detect corrupt tails."""
    import numpy as np
    import soundfile as sf

    decoded = samples = nonfinite = full_scale = near_full_scale = 0
    peak = energy = 0.0
    with sf.SoundFile(path) as source:
        header = {
            "sample_rate": source.samplerate, "channels": source.channels,
            "expected_frames": source.frames, "format": source.format,
            "subtype": source.subtype,
        }
        for block in source.blocks(BLOCK_FRAMES, dtype="float64", always_2d=True):
            decoded += len(block)
            samples += block.size
            valid_mask = np.isfinite(block)
            nonfinite += int(block.size - np.count_nonzero(valid_mask))
            finite = block[valid_mask]
            if finite.size:
                absolute = np.abs(finite)
                peak = max(peak, float(absolute.max()))
                energy += float(np.sum(finite * finite, dtype=np.float64))
                full_scale += int(np.count_nonzero(absolute >= 1.0))
                near_full_scale += int(np.count_nonzero(absolute >= 0.9999))
    rms = math.sqrt(energy / (samples - nonfinite)) if samples > nonfinite else 0.0
    warnings = []
    if near_full_scale:
        warnings.append("Samples near full scale; listen for clipping. This count is not an audio-quality verdict.")
    return {
        "file": str(path), **header, "decoded_frames": decoded,
        "duration_seconds": decoded / header["sample_rate"], "decoded_samples": samples,
        "nonfinite_samples": nonfinite, "peak_linear": peak, "peak_dbfs": dbfs(peak),
        "rms_linear": rms, "rms_dbfs": dbfs(rms),
        "samples_at_or_above_full_scale": full_scale,
        "near_full_scale_samples": near_full_scale,
        "near_full_scale_threshold": 0.9999,
        "technical_ok": decoded > 0 and decoded == header["expected_frames"] and nonfinite == 0,
        "warnings": warnings,
        "scope": "Full-decode numeric checks only. Voice similarity and listening quality require human review.",
    }


def ffmpeg_program() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise ValueError("FFmpeg was not found on PATH. Install it separately and reopen this shell.")
    return executable


def run_ffmpeg(arguments: list[str]) -> None:
    result = subprocess.run(
        [ffmpeg_program(), "-nostdin", "-hide_banner", "-loglevel", "error", "-n", *arguments],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", env=os.environ.copy(),
    )
    if result.returncode:
        raise RuntimeError(f"FFmpeg failed ({result.returncode}): {result.stderr.strip()}")


def audio_encoder(extension: str) -> list[str]:
    return ["-c:a", "pcm_s24le"] if extension == ".wav" else ["-c:a", "libmp3lame", "-b:a", "320k"]


def check_render(report: dict, rate: int, channels: int, frames: int, extension: str) -> None:
    tolerance = 1152 if extension == ".mp3" else 1
    if (
        not report["technical_ok"] or report["sample_rate"] != rate
        or report["channels"] != channels
        or abs(report["decoded_frames"] - frames) > tolerance
    ):
        raise ValueError(f"Rendered audio failed rate/channel/length/full-decode checks: {report}")


def preview_audio(source: Path, destination: Path, start: float, duration: float) -> dict:
    import soundfile as sf

    if not math.isfinite(start) or start < 0 or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Start must be finite and >= 0; duration must be finite and > 0")
    info = sf.info(source)
    if start + duration > info.frames / info.samplerate + 1 / info.samplerate:
        raise ValueError("Requested preview extends beyond the input")
    destination = new_output(destination, (".wav", ".mp3"))
    with tempfile.TemporaryDirectory(prefix="preview-", dir=workspace_path(".tmp")) as working:
        staged = Path(working) / ("preview" + destination.suffix.lower())
        run_ffmpeg([
            "-i", str(source), "-ss", str(start), "-t", str(duration),
            "-map", "0:a:0", "-vn", *audio_encoder(destination.suffix.lower()), str(staged),
        ])
        report = inspect_audio(staged)
        check_render(report, info.samplerate, info.channels, round(duration * info.samplerate), destination.suffix.lower())
        publish_file(staged, destination)
    report["file"] = str(destination)
    report["preview"] = {"source": str(source), "start_seconds": start, "duration_seconds": duration}
    return report


def mix_audio(
    vocals: Path, instrumental: Path, destination: Path,
    vocal_gain_db: float = 0, instrumental_gain_db: float = 0,
    peak_dbfs: float = -1, mono_vocals_to_stereo: bool = False,
    length_policy: str = "strict",
) -> dict:
    import numpy as np
    import soundfile as sf

    for gain in (vocal_gain_db, instrumental_gain_db):
        if not math.isfinite(gain) or not -120 <= gain <= 60:
            raise ValueError("Gain must be finite and between -120 and +60 dB")
    if not math.isfinite(peak_dbfs) or not -60 <= peak_dbfs <= -0.1:
        raise ValueError("Peak ceiling must be between -60 and -0.1 dBFS")
    if length_policy not in ("strict", "trim-to-shorter"):
        raise ValueError("Unknown length policy")
    destination = new_output(destination, (".wav", ".mp3"))
    with sf.SoundFile(vocals) as voice, sf.SoundFile(instrumental) as music:
        if voice.samplerate != music.samplerate:
            raise ValueError("Sample rates differ. Resample an explicit new copy with FFmpeg first.")
        duplicate_mono = mono_vocals_to_stereo and voice.channels == 1 and music.channels == 2
        if voice.channels != music.channels and not duplicate_mono:
            raise ValueError("Channels differ. For mono vocals + stereo music, pass --mono-vocals-to-stereo.")
        if voice.frames != music.frames and length_policy == "strict":
            raise ValueError("Frame lengths differ. Align the tracks, or explicitly choose --length-policy trim-to-shorter.")
        frames, rate, channels = min(voice.frames, music.frames), music.samplerate, music.channels
        if frames <= 0:
            raise ValueError("Inputs must contain audio frames")
        gains = (10 ** (vocal_gain_db / 20), 10 ** (instrumental_gain_db / 20))
        peak = 0.0
        with tempfile.TemporaryDirectory(prefix="mix-", dir=workspace_path(".tmp")) as working:
            float_mix = Path(working) / "mix-float.wav"
            pcm_mix = Path(working) / "mix-pcm24.wav"
            with sf.SoundFile(float_mix, "w", samplerate=rate, channels=channels, subtype="DOUBLE") as raw:
                remaining = frames
                while remaining:
                    count = min(BLOCK_FRAMES, remaining)
                    vocal_block = voice.read(count, dtype="float64", always_2d=True)
                    music_block = music.read(count, dtype="float64", always_2d=True)
                    if len(vocal_block) != count or len(music_block) != count:
                        raise ValueError("Input decode ended before its declared frame count")
                    if duplicate_mono:
                        vocal_block = np.repeat(vocal_block, 2, axis=1)
                    combined = vocal_block * gains[0] + music_block * gains[1]
                    if not np.isfinite(vocal_block).all() or not np.isfinite(music_block).all() or not np.isfinite(combined).all():
                        raise ValueError("Input contains nonfinite samples")
                    peak = max(peak, float(np.max(np.abs(combined))))
                    raw.write(combined)
                    remaining -= count
            target_peak = 10 ** (peak_dbfs / 20)
            attenuation = min(1.0, target_peak / peak) if peak else 1.0
            with sf.SoundFile(float_mix) as raw, sf.SoundFile(
                pcm_mix, "w", samplerate=rate, channels=channels, subtype="PCM_24",
            ) as pcm:
                for block in raw.blocks(BLOCK_FRAMES, dtype="float64", always_2d=True):
                    pcm.write(block * attenuation)
            if destination.suffix.lower() == ".mp3":
                staged = Path(working) / "mix.mp3"
                run_ffmpeg(["-i", str(pcm_mix), "-map", "0:a:0", "-vn", *audio_encoder(".mp3"), str(staged)])
            else:
                staged = pcm_mix
            report = inspect_audio(staged)
            check_render(report, rate, channels, frames, destination.suffix.lower())
            publish_file(staged, destination)
        report["file"] = str(destination)
        report["mix"] = {
            "vocals": str(vocals), "instrumental": str(instrumental),
            "vocal_gain_db": vocal_gain_db, "instrumental_gain_db": instrumental_gain_db,
            "peak_ceiling_dbfs": peak_dbfs, "applied_attenuation_db": dbfs(attenuation),
            "length_policy": length_policy, "mono_vocals_duplicated_to_stereo": duplicate_mono,
            "vocal_frames_discarded": voice.frames - frames,
            "instrumental_frames_discarded": music.frames - frames,
            "note": "Static gain and optional attenuation only; no mastering, timing correction, or pitch shift.",
        }
        return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Fully decode one input and report numeric metrics")
    inspect.add_argument("--input", required=True)
    preview = commands.add_parser("preview", help="Extract a timed preview with FFmpeg")
    preview.add_argument("--input", required=True)
    preview.add_argument("--start", required=True, type=float)
    preview.add_argument("--duration", required=True, type=float)
    preview.add_argument("--output", required=True, help="New project-local .wav (PCM24) or .mp3 (320 kbps)")
    mix = commands.add_parser("mix", help="Mix already prepared, aligned vocal and instrumental tracks")
    mix.add_argument("--vocals", required=True)
    mix.add_argument("--instrumental", required=True)
    mix.add_argument("--output", required=True, help="New project-local .wav (PCM24) or .mp3 (320 kbps)")
    mix.add_argument("--vocal-gain-db", type=float, default=0)
    mix.add_argument("--instrumental-gain-db", type=float, default=0)
    mix.add_argument("--peak-dbfs", type=float, default=-1)
    mix.add_argument("--mono-vocals-to-stereo", action="store_true")
    mix.add_argument("--length-policy", choices=("strict", "trim-to-shorter"), default="strict")
    for command in (inspect, preview, mix):
        command.add_argument("--json-output", help="Optional new project-local .json report; never overwritten")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        configure_runtime()
        if args.json_output:
            new_output(args.json_output, (".json",))
        if args.command == "inspect":
            report = inspect_audio(input_path(args.input))
        elif args.command == "preview":
            report = preview_audio(input_path(args.input), workspace_path(args.output), args.start, args.duration)
        else:
            report = mix_audio(
                input_path(args.vocals), input_path(args.instrumental), workspace_path(args.output),
                args.vocal_gain_db, args.instrumental_gain_db, args.peak_dbfs,
                args.mono_vocals_to_stereo, args.length_policy,
            )
        if args.json_output:
            write_new_json(args.json_output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if report["technical_ok"] else 2
    except (OSError, RuntimeError, ValueError, ImportError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
