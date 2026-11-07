# Screenshots, video and animations

## Desktop workflow

- `antigravity-in-action.gif`: embedded README animation (960 × 600, 23 seconds).
- `antigravity-in-action.mp4`: the same sequence in video (1280 × 800, no audio).
- `usage-poster.png`: still image of the result.

The recording shows a chat instruction in Antigravity, indicator activation, Windows Calculator receiving focus, the calculation 17 × 23 = 391 and indicator shutdown. Waiting periods were cut between steps. English captions, an initial closeup and a blurred region unrelated to the task were added. Chat responses and application results are from the recorded session.

The recording predates the thicker border and heartbeat. The animation at the top of the main README shows the current indicator.

## Animated indicator

`overlay-preview.gif` is rendered using `EdgeAnimation` and `CursorAnimation`, the same drawing components used by the desktop indicator. The background is an illustration; this animation is not an agent session recording.

Regenerate it on Windows from the project root:

```powershell
.\.venv\Scripts\python.exe scripts/render_preview.py docs/media/overlay-preview.gif
```

## Record a workflow

Recording support is an optional dependency:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[demo]"
.\.venv\Scripts\python.exe scripts/record_demo.py .local/workflow.mp4 --size 1920x1080 --seconds 240 --stop-file .local/stop.recording
```

The stop file must be absent when recording starts. Create it from another terminal to stop before the time limit. The recorder temporarily includes the indicator in captures using an expiring local marker, which is removed when recording ends. During normal use, the indicator requests exclusion from captures. Review footage before sharing and keep unedited recordings in `.local/`, outside the repository.
