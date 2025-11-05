# Development Guide

이 문서는 Local Korean TTS를 개발할 때 필요한 환경 구성, 테스트 실행, CI 정책을 정리합니다.

## 1. 환경 구성

```bash
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

- Poetry를 사용하고 싶다면 `python -m pip install poetry` 후 `poetry install --with dev`를 실행하세요.
- 모든 명령은 POSIX 경로(`/`) 기준입니다. Windows 사용자는 WSL 환경을 권장합니다.

## 2. 샘플 실행

샘플 텍스트와 아티팩트를 이용한 빠른 검증:

```bash
mkdir -p artifacts
export LK_TTS_CACHE_DIR=.cache
export LK_TTS_MODEL_PATH=/path/to/your/model  # 무거운 모델은 로컬에 위치해야 합니다.
python -m localkoreantts.cli \
  --in sample/sample.txt \
  --out artifacts/sample_out.wav
```

- 실행 후 `artifacts/sample_out.wav`와 `artifacts/sample_out.meta.json`이 생성됩니다.
- 로그에는 주민번호/카드번호와 같은 민감 정보가 마스킹되어야 합니다.
- 긴 텍스트 청크 분할을 확인하려면 `sample/long_sample.txt`를 사용하세요.

## 3. 환경 변수 요약

| 변수 | 설명 | 기본값 |
| --- | --- | --- |
| `LK_TTS_MODEL_PATH` | 로컬 모델 파일 경로. 개발 시 반드시 유효한 모델을 지정하거나 테스트에서 모킹하세요. | `~/.local/share/localkoreantts/model` |
| `LK_TTS_CACHE_DIR` | 합성 결과를 저장할 캐시 디렉터리. | `~/.cache/localkoreantts` |
| `LK_TTS_FFMPEG_BIN` | FFmpeg 실행 파일 경로. | `ffmpeg` |
| `LK_TTS_SAMPLE_RATE` | 기본 샘플 레이트(Hz). | `22050` |
| `LK_TTS_SPEED` | 기본 음성 재생 속도. | `1.0` |

## 4. 테스트 & 품질 체크

아래 명령은 CI와 동일한 기준입니다. 모든 커밋 전 반드시 실행하세요.

```bash
ruff check src tests
mypy src tests
pytest --basetemp="$(mktemp -d)"
coverage run -m pytest
coverage report --fail-under=95
```

- 무거운 모델 호출 또는 실제 FFmpeg 실행은 테스트에서 *반드시* 모킹하거나 패치해야 합니다.
- `pytest` 실행 시 샘플 데이터나 `tmp_path` 픽스처를 활용해 파일 I/O를 격리하세요.
- 커버리지 결과는 `.coverage`와 `coverage.xml`로 생성되며, 누락된 라인은 반드시 보완해야 합니다.

## 5. CI 파이프라인

- GitHub Actions 워크플로: `.github/workflows/ci.yml`
  - Python 3.11 설정 → Poetry 설치 → `ruff`, `mypy`, `pytest`(+coverage) 순으로 실행
  - `coverage report --fail-under=95`를 통해 커버리지 미달 시 실패 처리
  - `coverage xml` 결과를 `coverage-xml` 아티팩트로 업로드
- PR 전에 동일한 명령을 로컬에서 성공시켜야 CI 실패를 예방할 수 있습니다.

## 6. 개발 시 주의 사항

- **모델 경로**: `LK_TTS_MODEL_PATH`를 실제 모델 파일로 지정해야 CLI가 정상 동작합니다. 테스트에서는 `monkeypatch`로 로더 함수를 대체하여 무거운 의존성을 피하세요.
- **FFmpeg 호출**: `localkoreantts.utils`의 FFmpeg 실행 함수는 테스트에서 패치하여 파일 생성만 흉내 내도록 합니다.
- **캐시 디렉터리**: 테스트 중에는 `tmp_path`를 활용해 임시 캐시를 사용하고, 실행 종료 후 자동 정리되도록 하세요.
- **보안/프라이버시**: 로그에 민감 정보가 노출되지 않도록 `pii.scrub` 함수를 일관되게 활용하고, 샘플 데이터에도 실제 정보를 사용하지 않습니다.

행복한 개발 되세요!

## 7. 모킹/패치 가이드 (테스트 안정성)

- **모델 합성 함수**: `localkoreantts.tts.LocalVITS.generate_wav_bytes`를 `monkeypatch`로 교체해 아주 짧은 유효 WAV 바이트(예: `wave` 모듈로 생성)를 반환하세요. 이렇게 하면 무거운 모델을 로드하지 않고도 테스트가 통과합니다.
- **FFmpeg 호출**: `subprocess.run` 또는 `localkoreantts.utils._run_ffmpeg`를 패치해 성공 응답을 모사하거나, 필요한 경우 임시 WAV 파일만 만들어 반환하도록 하세요. FFmpeg가 설치돼 있지 않아도 테스트가 실패하지 않도록 합니다.
- **파일 시스템/캐시**: 모든 테스트는 `tmp_path`를 이용해 격리된 작업 디렉터리를 사용하고, `LK_TTS_CACHE_DIR` 환경 변수를 임시 경로로 지정하세요. 캐시나 출력 파일이 서로 영향을 주지 않도록 테스트마다 독립적으로 생성합니다.
