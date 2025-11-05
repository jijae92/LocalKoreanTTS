#!/bin/bash
source /mnt/c/Users/User/Downloads/LocalKoreanTTS/.venv/bin/activate
export QT_QPA_PLATFORM=offscreen
export QT_OPENGL=software
export QTWEBENGINE_DISABLE_SANDBOX=1
export SDL_AUDIODRIVER=dummy
export PULSE_SERVER=127.0.0.1:0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES=
export PYTHONFAULTHANDLER=1
xvfb-run -a -s "-screen 0 1280x1024x24 -ac +extension GLX +render -noreset" python -m pytest -s tests/gui
