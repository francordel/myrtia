# Console fonts

`standalone.html` carries its three typefaces inline, as base64 `@font-face` sources, so the
console makes no request to Google Fonts and renders the same offline or opened directly
from disk (issue #44).

| Family | Weights used | Source file (latin subset, variable `wght`) |
|---|---|---|
| Roboto | 400–700 | `https://fonts.gstatic.com/s/roboto/v51/KFO7CnqEu92Fr1ME7kSn66aGLdTylUAMa3yUBA.woff2` |
| Roboto Mono | 400–500 | `https://fonts.gstatic.com/s/robotomono/v31/L0x5DF4xlVMF-BfR8bXMIjhLq38.woff2` |
| Montserrat | 300–400 | `https://fonts.gstatic.com/s/montserrat/v31/JTUSjIg1_i6t8kCHKm459Wlhyw.woff2` |

These are the latin files the old Google Fonts stylesheet
(`css2?family=Roboto:wght@400;500;700&family=Roboto+Mono:wght@400;500&family=Montserrat:wght@300;400`)
pointed to. Text outside the latin range falls back to the system fonts already listed in
each `font-family` stack.

To refresh one, download its `.woff2`, base64-encode it (`base64 -w0 file.woff2`) and
replace the `data:font/woff2;base64,...` value of the matching `@font-face` at the top of
`standalone.html`.

All three families are licensed under the SIL Open Font License 1.1; the copyright notices
and the licence text are in [`OFL.txt`](OFL.txt).
