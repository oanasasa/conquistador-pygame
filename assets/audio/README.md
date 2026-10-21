# Game sounds

Which file plays for what is set in `SOUND_FILES` in `ui/sound.py`. Each
sound is optional: a missing or unreadable file is simply silent.

| Sound | File | When it plays |
|---|---|---|
| theme | `Woodland Fantasy.mp3` | Loops in the menus and halls; fades out when the battle starts |
| clock | `Clock Ticking.ogg` | Loops while a riddle is open, louder in the last three seconds; stops when the riddle ends |
| win | `win sound 1.wav` | When thine own answer is true (fades after 2.5 s) |
| lose | `Bad Sound 1.wav` | When thine own answer is false |
| cannon | `Cannon Hit.ogg` | When an attacker topples a castle tower (everyone hears it) |

To swap a sound, drop the new file here and change its name in `SOUND_FILES`.
Long music works best as `.ogg` or `.mp3`; short effects as `.wav`. Only use
files you have the right to use (your own, CC0, or a license that allows it).
Press `M` in the game to mute.
