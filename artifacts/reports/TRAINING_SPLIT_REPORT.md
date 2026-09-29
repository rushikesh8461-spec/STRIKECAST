# Training split report

Status: **NOT CREATED**. No valid paired samples exist to split. Configured split fractions are not applied to source granules or dates; doing so would misrepresent partial satellite passes as continuous samples.

| Split | Total samples | Valid samples | Positive | Negative | Unknown |
|---|---:|---:|---:|---:|---:|
| train | 0 | 0 | NOT ENUMERATED | NOT ENUMERATED | NOT ENUMERATED |
| validation | 0 | 0 | NOT ENUMERATED | NOT ENUMERATED | NOT ENUMERATED |
| test | 0 | 0 | NOT ENUMERATED | NOT ENUMERATED | NOT ENUMERATED |

No train, validation, or test timestamps were allocated. Chronological boundaries and embargo are therefore not computable. The existing whole-window chronological splitter remains the intended implementation once a valid paired dataset is available; it assigns a complete input+target window to one split and drops boundary-crossing windows.
