# 1장. 설치와 연기 시험 — Verilog-A가 내 컴퓨터에서 도는가

`L3` · 30분 · 코드 `code/smoke/`

---

## 한 문장

Verilog-A 소스(`.va`)를 **OpenVAF가 기계어 라이브러리(`.osdi`)로 컴파일**하고, **ngspice가 그 라이브러리를 불러** 회로 안의 소자로 쓴다. 1 kΩ 저항에 1 V를 걸어 1 mA가 나오면 이 연결이 살아 있는 것이다.

## 큰 그림

```
 tft.va  ──(openvaf)──▶  tft.osdi  ──(ngspice: pre_osdi)──▶  .model m1 tft …  ──▶  N1 d g s m1
 소스 코드              컴파일된 모델              회로가 불러옴               인스턴스 (접두어 N)
```

| 단계 | 명령 | 실패하면 보이는 것 |
|---|---|---|
| 컴파일 | `openvaf va_res.va` | `error: …` 와 줄 번호 |
| 불러오기 | `.control` 안 `pre_osdi va_res.osdi` | `unknown model type` |
| 사용 | `N1 in 0 r1k` | `unknown device` (접두어가 N이 아닐 때) |

## 비유: 번역가와 극장

Verilog-A 파일은 **외국어 대본**, OpenVAF는 **번역가**, ngspice는 **극장**이다. 극장은 번역된 대본(`.osdi`)만 무대에 올릴 수 있다. 대본을 고치면 **반드시 다시 번역**해야 한다. 번역을 안 하고 극장에 가면 어제 대본으로 공연한다.

## 그래서 뭐

- `.va`를 고쳤는데 결과가 안 바뀐다 → 90%는 `openvaf`를 다시 안 돌린 것이다.
- HSPICE는 `.hdl "x.va"`로 컴파일을 알아서 한다. ngspice는 이 단계가 분리돼 있어서, 연구실 HSPICE 넷리스트를 가져오면 **이 줄부터 바꿔야** 한다 (부록 C).

## 비유가 깨지는 곳

1. 번역은 말만 옮기지만 OpenVAF는 **미분까지 계산해 넣는다.** 회로 해석기는 뉴턴 반복에 도함수가 필요하고, OpenVAF가 자동 미분으로 만든다. 그래서 `if`로 식을 갈라 쓰면 경계에서 도함수가 튀어 수렴이 나빠질 수 있다 (2장 `limexp` 함정).
2. `.osdi`는 **운영체제·CPU에 묶인 바이너리**다. 친구 컴퓨터에서 만든 `.osdi`를 복사해 오지 말고 각자 컴파일한다. 이 저장소에도 `.osdi`는 넣지 않았다.

---

## 직접 해보기

### 1) 설치

**권장: Linux 또는 Windows의 WSL2 (Ubuntu 22.04/24.04).** macOS도 되지만 이 교재는 Linux에서만 검증했다.

| 도구 | 필요 버전 | 설치 |
|---|---|---|
| ngspice | **39 이상** (OSDI 지원 시작) · 검증 45.2 | `sudo apt install ngspice` 또는 [ngspice.sourceforge.io](https://ngspice.sourceforge.io) 소스 빌드 |
| OpenVAF | OpenVAF-Reloaded | [github.com/OpenVAF/OpenVAF-Reloaded](https://github.com/OpenVAF/OpenVAF-Reloaded) 릴리스에서 `openvaf` 바이너리를 받아 PATH에 둔다 |
| Python | 3.10 이상 · 검증 3.12 | `code/requirements.txt` |

```bash
ngspice --version | head -2     # ngspice-39 이상인지
openvaf --version               # 명령이 잡히는지
cd code && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
```

> 배포판 패키지 ngspice가 OSDI 없이 빌드된 경우가 있다. 버전만 보지 말고 아래 연기 시험으로 확인한다.
> sudo 권한이 없으면 ngspice를 `~/.local`에 소스 빌드하고 `export NGSPICE=~/.local/bin/ngspice`로 지정할 수 있다 (`common.py`가 이 변수를 먼저 본다).

### 2) 연기 시험

`code/smoke/va_res.va` — 저항 하나짜리 Verilog-A:

```verilog
module va_res(p, n);
  inout p, n;
  electrical p, n;
  parameter real R = 1e3 from (0:inf);
  analog I(p, n) <+ V(p, n) / R;      // 기여 연산자 <+ : "이 가지에 이 전류를 더하라"
endmodule
```

`code/smoke/smoke.cir`:

```spice
.model r1k va_res R=1e3
V1 in 0 1
N1 in 0 r1k
.control
pre_osdi va_res.osdi
op
print -i(V1)
.endc
.end
```

```bash
cd code/smoke
openvaf va_res.va
ngspice -b smoke.cir | grep "i(v1)"
# -i(v1) = 1.000000e-03   ← 이게 나오면 통과
```

### 3) 합격 기준

- `1.000000e-03`이 정확히 나온다 (전압원 전류는 들어가는 방향이 +라서 `-i(V1)`로 부호를 뒤집었다)
- 경고 없이 끝난다

---

> **적용 질문**
> 여러분 연구실의 HSPICE 넷리스트에 `.hdl "a.va"`와 `X1 d g s tftm`이 있다면, ngspice로 옮길 때 최소 몇 곳을 바꿔야 하는가? (답은 부록 C 표에 있다)

[← 0장](ch00_big_picture.md) · [다음: 2장 Verilog-A로 늙는 TFT →](ch02_verilog_a_tft.md)
