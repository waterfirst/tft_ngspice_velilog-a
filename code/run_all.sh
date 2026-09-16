#!/usr/bin/env bash
# Rebuild every result in this repo except data/dataset.npz (see textbook ch06 for gen_dataset.py).
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python}
command -v ngspice >/dev/null || { echo "ngspice not on PATH (textbook ch01)"; exit 1; }
command -v openvaf >/dev/null || { echo "openvaf not on PATH (textbook ch01)"; exit 1; }

echo "== ch01 smoke";   (cd smoke && openvaf va_res.va && ngspice -b smoke.cir | grep -i "i(v1)")
echo "== ch02 warmup";  (cd 01_tft_aging && openvaf tft_aging.va && ngspice -b transfer.cir >/dev/null && ngspice -b pixel_2t1c.cir >/dev/null && $PY plot.py)
cd 02_pipeline
echo "== ch03 models";  (cd models && openvaf ptft_true.va && openvaf ptft_fit.va)
$PY check_twin.py | tail -1
echo "== ch03 measure"; $PY gen_meas.py | tail -7
echo "== ch03 extract"; $PY extract.py > /dev/null
echo "== ch04 aging";   $PY aging.py | tail -7
echo "== ch05 pixels";  $PY run_pixels.py && $PY grade.py
echo "== ch06 ML";      $PY ml_compare.py && $PY ml_grade.py
echo "== ch07 8T1C";    (cd ../03_extension_8t1c && $PY pixel_8t1c.py)
