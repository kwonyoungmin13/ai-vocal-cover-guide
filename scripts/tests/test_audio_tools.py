"""Synthetic tests only; no project audio/model is read or changed."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "audio_tools.py"
SPEC = importlib.util.spec_from_file_location("audio_tools", MODULE)
audio = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audio)
audio.configure_runtime()

import numpy as np
import soundfile as sf


class AudioToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="tests-", dir=audio.workspace_path(".tmp"))
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def make_wav(self, name, values, rate=16000):
        path = self.directory / name
        sf.write(path, values, rate, subtype="FLOAT")
        return path

    def test_full_decode_detects_nonfinite_tail(self):
        values = np.zeros((audio.BLOCK_FRAMES + 13, 1), dtype=np.float32)
        values[-1] = np.nan
        report = audio.inspect_audio(self.make_wav("nonfinite.wav", values))
        self.assertEqual(report["decoded_frames"], len(values))
        self.assertEqual(report["nonfinite_samples"], 1)
        self.assertFalse(report["technical_ok"])

    def test_mix_peak_ceiling_and_no_overwrite(self):
        vocals = self.make_wav("vocals.wav", np.full((1600, 1), 0.8))
        music = self.make_wav("music.wav", np.full((1600, 2), 0.8))
        destination = self.directory / "mixed.wav"
        report = audio.mix_audio(vocals, music, destination, mono_vocals_to_stereo=True)
        self.assertEqual(report["subtype"], "PCM_24")
        self.assertEqual(report["channels"], 2)
        self.assertEqual(report["decoded_frames"], 1600)
        self.assertLessEqual(report["peak_linear"], 10 ** (-1 / 20) + 2 ** -23)
        self.assertLess(report["mix"]["applied_attenuation_db"], 0)
        before = destination.read_bytes()
        with self.assertRaises(FileExistsError):
            audio.mix_audio(vocals, music, destination, mono_vocals_to_stereo=True)
        self.assertEqual(destination.read_bytes(), before)

    def test_boundary_and_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            audio.workspace_path(audio.PROJECT_ROOT.parent / "outside.wav")
        vocals = self.make_wav("voice.wav", np.zeros((1600, 1)))
        wrong_rate = self.make_wav("wrong-rate.wav", np.zeros((1600, 1)), rate=8000)
        with self.assertRaisesRegex(ValueError, "Sample rates differ"):
            audio.mix_audio(vocals, wrong_rate, self.directory / "rate-rejected.wav")
        wrong_length = self.make_wav("wrong-length.wav", np.zeros((1500, 1)))
        with self.assertRaisesRegex(ValueError, "Frame lengths differ"):
            audio.mix_audio(vocals, wrong_length, self.directory / "length-rejected.wav")
        stereo = self.make_wav("stereo.wav", np.zeros((1600, 2)))
        with self.assertRaisesRegex(ValueError, "Channels differ"):
            audio.mix_audio(vocals, stereo, self.directory / "channel-rejected.wav")


if __name__ == "__main__":
    unittest.main()
