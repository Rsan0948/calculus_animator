---
name: Parser Bug Report
about: Report LaTeX parsing issues
labels: ["bug", "parser"]
---

## Parser Bug

**Describe the issue**
A clear description of the LaTeX expression that failed to parse.

**Input Expression**
```latex
\frac{d}{dx} \cos(x)
```

**Expected Behavior**
Should parse `\cos(x)` as the cosine function applied to x.

**Actual Behavior**
Parsed as `c * o * s(x)` — three separate variables.

**Error Message (if any)**
```
Sampling failed for (x**2 + 1)/((c*(o*s(x)))): name 's' is not defined
```

**Environment**
- OS: [e.g. macOS 14.2]
- Python version: [e.g. 3.12]
- App version: [e.g. 1.0.0]

**Additional Context**
Add any other context about the problem here.
