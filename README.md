# LIFT MACRO 12.0

A dark desktop automation workspace for recording, editing, organizing, and replaying workflows on your own Windows PC.

## New in 12.0
- Added reusable timing templates: quick pause, three-step timing, short cooldown, and long wait.
- Continued Macro Studio improvements with template insertion directly into the timeline.
- Added a GitHub Actions Windows build workflow.
- **You can obtain the Windows EXE without installing Python on your PC** by using the GitHub Actions workflow. See `GET-EXE-WITHOUT-PYTHON.md`.

## Get the EXE without Python
Follow `GET-EXE-WITHOUT-PYTHON.md`. GitHub builds the Windows application on its own runner and provides a ZIP artifact containing the EXE and runtime files. The workflow is included but has not yet been run, so the Windows artifact still needs its first build/test.

## Build locally (optional)
On Windows with Python 3.11+, run `build_exe.bat`.

## Core features
- Mouse movement, click, and scroll recording.
- Optional keyboard recording (off by default; it can capture typed text).
- Timeline editing, action duplication, reordering, deletion, delay insertion, timestamp editing, search, and CSV export.
- Reusable timing templates.
- Playback speed, repeat count, pause, stop, and looping.
- `.liftmacro` files, profiles, recovery snapshots, local macro library, and SoundCloud player.
- Custom LIFT Windows application icon.

## Safety and privacy
Playback sends real input to the active desktop. Review a macro and save your work before playing it. Use automation only on your own device and in software where it is permitted. Keyboard recording can capture private text, so it remains disabled by default. LIFT does not provide stealth, anti-detection, credential capture, or remote-control features.

## Testing
Python syntax and ZIP integrity are checked for this source package. The Windows EXE must be built and tested by running the included GitHub Actions workflow. SoundCloud behavior depends on SoundCloud and Qt WebEngine.
