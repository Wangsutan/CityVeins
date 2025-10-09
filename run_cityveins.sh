#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/cityveins_env/bin/activate"
python "$DIR/cityveins_env/sources/run_gui.py" "$@"
