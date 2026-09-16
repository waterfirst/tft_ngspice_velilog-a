# 8T1C full pipeline summary (synthetic, not a manufacturer circuit)

Gates: 8/8 PASS (`gates.csv`).

## Grade (`grade_6t1c_vs_8t1c.csv`)
circuit gray  I0_nA  I1000_nA  I3000_nA  retention_3000_pct  cards_err_0h_pct  cards_err_3000h_pct  law_err_0h_pct  law_err_3000h_pct
   6T1C  고계조 525.49    479.99    463.94               88.29             -4.41                -2.59           -3.93              -1.17
   6T1C  중계조 237.32    211.35    202.51               85.33             -5.75                -3.13           -5.32              -1.74
   6T1C  저계조  84.25     71.12     66.82               79.32             -8.99                -5.28           -8.67              -3.98
   8T1C  고계조 525.68    480.16    464.09               88.28             -4.42                -2.59           -3.94              -1.17
   8T1C  중계조 237.46    211.47    202.62               85.33             -5.77                -3.14           -5.34              -1.75
   8T1C  저계조  84.33     71.19     66.89               79.32             -9.02                -5.31           -8.70              -4.01

## Single-TFT 3000 h sensitivity, % (`sensitivity_8t1c.csv`)
        고계조    저계조    중계조
only                     
T1   -10.35 -19.99 -13.71
T2     0.00   0.00  -0.00
T3    -0.13  -0.33  -0.20
T4     0.00  -0.00  -0.00
T5    -1.13  -0.44  -0.76
T6    -0.37  -0.14  -0.24
T7     0.00  -0.00  -0.00
T8     0.00   0.00  -0.00

## ML MAPE, % (`ml_8t1c.csv`)
test          gray_extrap  in_range  time_extrap
method                                          
AI-GBM             127.52      1.91         4.14
AI-MLP              79.86     11.22        21.89
Hybrid               2.57      1.02         6.20
conventional         6.98      3.70         7.26

## T7/T8 stress from the 60 Hz waveform (`stress_probe.csv`)
TFT  assumed_duty  assumed_vgs_V  probed_duty  probed_vgs_V  stress_assumed  stress_probed  dvt_1000_V  dmu_1000_pct
 T7         0.012             10       0.0126        3.4164           0.048         0.0059      0.0146        0.0584
 T8         0.012             10       0.0126       11.8469           0.048         0.0706      0.1649        0.6596
