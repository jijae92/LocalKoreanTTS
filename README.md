# Local Korean TTS

로컬 환경에서 한국어 텍스트를 음성으로 변환하기 위한 파이썬 기반 파이프라인의 참고 구현입니다. CLI, 캐싱, PII 마스킹, 테스트 및 CI 예제가 포함되어 있어 자체 프로젝트를 빠르게 시작할 수 있습니다.

## 설치

```bash
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> Poetry를 선호하는 경우 `python -m pip install poetry` 후 `poetry install --with dev`로 동일한 환경을 구성할 수 있습니다.

## 빠른 시작

샘플 텍스트를 이용한 CLI 실행:

```bash
mkdir -p artifacts
LK_TTS_CACHE_DIR=.cache \
LK_TTS_MODEL_PATH=/path/to/your/model \
python -m localkoreantts.cli \
  --in sample/sample.txt \
  --out artifacts/sample_out.wav
```

- 첫 실행 시 `artifacts/sample_out.wav`와 `artifacts/sample_out.meta.json`이 생성됩니다.
- 로그에는 주민번호/카드번호 등 민감 정보가 마스킹되어 출력됩니다.
- 실제 모델이 없는 경우 `LK_TTS_MODEL_PATH`를 더미 경로로 설정한 뒤 테스트에서는 모킹으로 대체하세요. (`tests/` 참고)

긴 텍스트로 청크 분할을 확인하려면 `sample/long_sample.txt`를 `--in` 인자로 지정하세요.

## GUI 실행

데스크톱 GUI를 사용하려면 GUI 익스트라를 설치한 뒤 아래 명령을 실행하세요.

```bash
pip install .[gui]
localkoreantts-gui
```

GUI는 텍스트 입력, 파일 선택, 설정 탭을 제공하며 설정이 완료되고 텍스트가 입력되면 합성 버튼이 활성화됩니다. 진행 상황과 로그는 하단 패널에서 확인할 수 있습니다.

## 환경 변수

| 이름 | 기본값 | 설명 |
| --- | --- | --- |
| `LK_TTS_MODEL_PATH` | `~/.local/share/localkoreantts/model` | 로컬 VITS/Coqui 모델 경로 |
| `LK_TTS_CACHE_DIR` | `~/.cache/localkoreantts` | 합성 산출물 캐시 저장소 |
| `LK_TTS_FFMPEG_BIN` | `ffmpeg` | FFmpeg 실행 파일 경로 |
| `LK_TTS_SAMPLE_RATE` | `22050` | 기본 샘플 레이트 (Hz) |
| `LK_TTS_SPEED` | `1.0` | 기본 재생 속도 |

필요 시 `.env` 또는 CI 설정에서 값을 주입하고, 로그에는 민감 정보를 기록하지 않도록 주의하세요.

## 테스트 및 품질 점검

| 명령 | 설명 |
| --- | --- |
| `ruff check src tests` | 코드 스타일 검사 |
| `mypy --strict src` | 정적 타입 검사 |
| `xvfb-run -a pytest -q` | GUI 포함 테스트 (headless) |
| `coverage run -m pytest` <br>`coverage report --fail-under=95` | 커버리지 수집 및 검증 |

- `pytest` 실행 시 무거운 모델/ffmpeg 호출은 모두 모킹되어야 합니다.
- 커버리지가 95% 미만이면 CI가 실패합니다.
- GitHub Actions 워크플로(`.github/workflows/ci.yml`)가 동일한 명령을 수행하며, `coverage.xml` 아티팩트를 업로드합니다.

## 패키징 및 배포

```bash
python -m build  # sdist + wheel 생성 (dist/)
python -m PyInstaller app.spec  # PyInstaller 번들(dist/localkoreantts-gui)
```

- `app.spec`은 기본 아이콘/리소스를 포함하도록 설정되어 있으며 `--noconsole` 모드로 빌드합니다.
- `PyInstaller` 실행 전에 `pip install .[gui]` 로 필요한 Qt 종속성을 설치하세요.
- 생성된 실행 파일은 `dist/localkoreantts-gui` 아래에서 확인할 수 있습니다.

## 추가 자료

- [DEVELOPMENT.md](DEVELOPMENT.md): 개발자용 워크플로, 테스트 규칙, CI 연동 지침.
- `sample/`: PII 마스킹 및 청크 분할을 검증할 수 있는 샘플 데이터.

## 라이선스

이 프로젝트는 예제 목적이며, 필요 시 조직 정책에 맞는 라이선스를 추가하세요.
