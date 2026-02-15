# Build & Share (macOS + Windows)

This project can be packaged into a standalone app so recipients can run it without opening source files.

## 1. Build on each target OS

Build on macOS for mac output, and on Windows for Windows output.

## 2. Install build dependency

In the project folder:

```bash
pip install -r requirements.txt
pip install pyinstaller
```

## 3. Run the build

```bash
python build_release.py
```

## 4. Output locations

- `dist/Calculus Animator.app` on macOS
- `dist/Calculus Animator/Calculus Animator.exe` on Windows

## 5. Distribute

- macOS: zip the `.app` and share the zip (or wrap in a `.dmg` if desired).
- Windows: zip the app folder from `dist/Calculus Animator/` and share the zip.

## Notes

- This hides source code for normal users, but is not strong anti-reverse-engineering protection.
- If macOS Gatekeeper blocks launch, users can right-click the app and choose **Open** once.
- If Windows SmartScreen warns, users may need to choose **More info -> Run anyway** unless you code-sign.
