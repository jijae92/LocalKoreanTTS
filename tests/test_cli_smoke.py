# tests/test_cli_smoke.py
import math
import struct
import wave
from io import BytesIO


class DummyVITS:
    sample_rate = 22050
    def generate_wav_bytes(self, text: str, speed: float = 1.0) -> bytes:
        # 0.5초짜리 440Hz 사인파
        sr = 22050
        buf = BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            for n in range(int(sr * 0.5)):
                s = int(32767 * math.sin(2*math.pi*440*n/sr))
                wf.writeframes(struct.pack("<h", s))
        return buf.getvalue()

def test_cli_runs(monkeypatch, tmp_path):
    import localkoreantts.cli as cli
    monkeypatch.setattr(cli, "create_local_vits", lambda *a, **k: DummyVITS())
    inp = tmp_path/"in.txt"
    inp.write_text("테스트")
    out = tmp_path/"out.wav"
    assert cli._run_cli(["--in", str(inp), "--out", str(out)]) == 0
    assert out.exists() and out.stat().st_size > 44
