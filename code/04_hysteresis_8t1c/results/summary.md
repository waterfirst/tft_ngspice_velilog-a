# 8T1C hysteresis summary (synthetic example, not a manufacturer circuit)

Gates: 9/9 PASS (`gates.csv`: G1 KH=0 reproduces ch07, G2 trap tau, G3 step 20 us vs 2 us).
E1 = |I1(from low gray) - I1(from high gray)| / I_ss, in %. Real 60 Hz unless noted. Runtime: `runtime.txt`.

Representative (KH=0.05 V/V, tau=1 ms, 0 h, VOBS=5 V): 6T1C E1=7.82%, 8T1C E1=5.84%
(-25.4% relative). I_ss 6T1C=256.2 nA, 8T1C=270.5 nA.

E1 vs KH (tau=1 ms, 0 h)
circuit   6T1C   8T1C  8T1C_no_T7  8T1C_no_T8
KH                                           
0.00      0.00   0.00        0.00        0.00
0.02      3.14   2.38        2.38        3.14
0.05      7.82   5.84        5.84        7.82
0.10     15.55  11.32       11.32       15.55

E1 vs tau [s] (KH=0.05, 0 h)
circuit  6T1C  8T1C  8T1C_no_T7  8T1C_no_T8
TAUH_s                                     
0.0001   7.62  0.93        0.93        7.62
0.0010   7.82  5.84        5.84        7.82
0.0100   3.69  3.55        3.56        3.69

R_ss = I_ss(t)/I_ss(0) (KH=0.05, tau=1 ms), in %
circuit    6T1C    8T1C  8T1C_no_T7  8T1C_no_T8
age_h                                          
0        100.00  100.00      100.00      100.00
1000      88.99   88.62       88.62       88.99
3000      85.22   84.73       84.74       85.22

Accelerated 1 ms frame (KH=0.05, tau=1 ms): 6T1C E1=2.13%, 8T1C E1=0.75%.
T7/T8 probed stress (`stress_probe.csv`): duty=0.0061 (assumed 0.012),
|Vgs| T7=3.49 V, T8=11.96 V (assumed 10 V).
