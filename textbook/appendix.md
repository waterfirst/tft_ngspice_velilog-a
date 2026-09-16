# 부록 — 함정 모음 · 용어 · HSPICE 차이

---

## A. 막혔을 때 먼저 볼 표

| 증상 | 가장 흔한 원인 | 해결 | 본문 |
|---|---|---|---|
| `unknown model type` | `pre_osdi`를 안 했거나 `.osdi` 경로가 틀림 | `.control` 안에 `pre_osdi 절대경로.osdi` | 1장 |
| `.va`를 고쳤는데 결과 그대로 | `openvaf` 재컴파일 안 함 | 고칠 때마다 `openvaf x.va` | 1장 |
| 인스턴스 `unknown device` | Verilog-A 소자 접두어가 `N`이 아님 | `N1 d g s model` | 1장 |
| 전류가 어느 오버드라이브에서 딱 멈춤 | `ln(1+limexp(x))` | `x > 30`에서 `veff = vgs − vth` 분기 | 2장 |
| `wrdata`가 열을 하나만 씀 | `-i(V1) -i(V2)`가 뺄셈 하나로 해석 | 부호 없이 쓰고 후처리 | 2장 |
| `.control` 파일명이 비어 있음 | `$vd.txt`를 변수 이름으로 읽음 | 확장자 없이 `name_$vd` | 2장 |
| 서브문턱 pA 전류가 들쭉날쭉 | 기본 `abstol` 1 pA | `.options abstol=1e-16 reltol=1e-6 vntol=1e-9` | 5장 |
| 병렬 실행이 비정상적으로 느림 | ngspice 기본 `num_threads=8` | `set num_threads=1` + `OMP_NUM_THREADS=1` | 5장 |
| NMOS 스위치가 안 켜짐 | PMOS용 active-low 신호 연결 | 반전 신호 추가, `POL=-1` | 5장 |
| 저계조 전류만 크게 틀림 | 측정 바닥 아래 점 삭제 → 누설 발산 | 상한(censored) 잔차 | 3장 |
| 추출값이 시간에 따라 들쭉날쭉 | 모든 파라미터를 매 시간 자유롭게 풂 | 모양 파라미터 고정, Vth·μ만 | 4장 |
| 피팅 계수가 경계에 붙음 (`BETAM=1.00`) | 식 모양·경계가 데이터와 안 맞음 | 식 재검토, 식별 가능성 확인 | 4장 |
| ML R²는 높은데 새 소자에서 틀림 | TFT 단위 행 + 행 단위 무작위 분할 = 누수 | wide 형식 + `GroupKFold(cell_id)` | 7장 |
| GBM이 범위 밖에서 한 값만 냄 | 트리 모델은 외삽 불가 | Hybrid 잔차 학습 | 6장 |

---

## B. 용어

| 용어 | 이 교재에서의 뜻 |
|---|---|
| **애노드 전류** | OLED 애노드로 들어가는 전류. 넷리스트의 `Vsense`(0 V 전압원)로 잰다 |
| **모델카드** | 한 TFT의 compact model 파라미터 묶음 (`.model mT1 ptft_fit VT0=… U0=…`) |
| **TSTRESS** | Verilog-A 모델 파라미터로 넣은 누적 스트레스 시간 [h]. 열화식이 이 값으로 Vth·μ를 바꾼다 |
| **stretched exponential** | `A·[1 − exp(−(t/τ)^β)]`. β<1이면 초반이 가파르고 점점 느려진다 |
| **OSDI / OpenVAF** | Verilog-A를 컴파일해 ngspice 등에 붙이는 인터페이스 / 컴파일러 |
| **LTPS / IGZO / LTPO** | 저온 다결정 실리콘(주로 PMOS, 이동도 높음) / 산화물 반도체(NMOS, 누설 매우 낮음) / 둘을 한 화소에 섞은 구조 |
| **POL** | 교재 모델의 극성 파라미터. +1 PMOS, −1 NMOS |
| **softplus** | `n·Vt·ln(1+e^x)`. 서브문턱 지수와 문턱 위 선형을 하나로 잇는 함수 |
| **상한 처리 (censored)** | 측정 바닥 아래 값을 "이보다 작다"는 부등식으로만 쓰는 피팅 |
| **numpy 쌍둥이** | Verilog-A와 같은 식을 Python으로 다시 쓴 것. 빠른 추출용, `check_twin.py`로 일치 확인 |
| **블라인드** | 피팅·학습에 한 번도 안 쓰고 채점에만 쓰는 데이터 |
| **민감도 (여기서)** | 한 TFT만 열화시켰을 때 애노드 전류 변화율 |
| **MAPE / P95** | 평균 절대 백분율 오차 / 오차 상위 5% 경계값 |
| **잔차 학습 (Hybrid)** | 물리 모델 예측과 정답의 차이(`log I_정답 − log I_기존`)만 ML로 학습 |
| **누수 (leakage)** | 시험 데이터의 정보가 학습에 섞여 성능이 부풀려지는 것 |

---

## C. HSPICE ↔ ngspice + OpenVAF

| 항목 | HSPICE | ngspice + OpenVAF |
|---|---|---|
| Verilog-A 불러오기 | `.hdl "tft.va"` (자동 컴파일) | `openvaf tft.va`로 미리 컴파일 → `.control` 안 `pre_osdi tft.osdi` |
| 인스턴스 접두어 | `X1 d g s tftm` | `N1 d g s tftm` |
| 파형 저장 | `.option post=2` | `wrdata 파일 벡터…` (+ `set wr_singlescale`, `set wr_vecnames`) |
| 측정 | `.measure tran iavg AVG i(Vsense) FROM=… TO=…` | `.control` 안 `meas tran iavg AVG i(Vsense) from=… to=…` |
| 파라미터 스윕 | `.alter`, `.data` | `.control`의 `foreach` + `alter` |
| 라이선스 | 상용 (기관 계약) | 오픈소스 — 개인 설치 가능 |

옮길 때 순서: ① `.hdl` 제거 후 `openvaf` 컴파일 ② `X`→`N` ③ `.measure`를 `.control`로 ④ 연기 시험(1장) ⑤ 같은 회로 한 점을 두 시뮬레이터로 돌려 전류 비교.

> ngspice·OpenVAF 라이선스 세부는 각 프로젝트 저장소의 LICENSE를 확인할 것.

---

## D. 이 교재 결과를 재현했을 때 같아야 하는 숫자

| 파일 | 확인할 값 |
|---|---|
| `smoke` | `-i(v1) = 1.000000e-03` |
| `check_twin.py` | `WORST 1.04e-04 PASS` |
| `gen_meas.py` | `rows 37212`, T1 스트레스 0.341 |
| `aging.py` | `T1: AVT=1.108V TAUV=1371h BETAV=0.46` |
| `run_pixels.py` | `runs 189 / 189` |
| `ml_compare.py` | `Hybrid 기본 MAPE 0.99%` |
| `pixel_8t1c.py` | 8T1C 중계조 0 h 237.5 nA |

버전이 다르면 마지막 자리가 달라질 수 있다. **한두 자리 차이는 정상, 부호나 자릿수가 다르면 설치 문제**를 의심한다.

[← 8장](ch08_ai_agents.md) · [처음으로](../README.md)
