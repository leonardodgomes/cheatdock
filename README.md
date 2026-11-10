# CheatDock

A cheat sheet that lives on the edge of your screen.

CheatDock stays out of the way as a thin strip on the side of your monitor. Touch it with the mouse (or press **Ctrl+Alt+Space** from any app) and it slides open with tabs for **PowerShell, SQL, Python and Pandas**. Click a command to copy it, then go back to work.

## Features

- **Docked to the screen edge** (right or left), always on top, never in your taskbar
- **Opens on hover or with a global hotkey**, and closes when you move away or press `Esc`
- **Search across every tab at once.** Each tab shows how many matches it has, and `Enter` copies the first result
- **Click to copy** any command
- **Pin** the panel open while you work through something
- **Plain YAML files**: add a tab or a command by editing a text file, and the app reloads on its own
- System tray icon, dark theme, no admin rights needed

## Quick start

### Option 1: download the .exe
Grab `CheatDock-windows.zip` from the [Releases](../../releases) page, unzip it anywhere and run `CheatDock.exe`.

### Option 2: run from source
Requires Python 3.10+.

```powershell
git clone https://github.com/leonardodgomes/cheatdock.git
cd cheatdock
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m cheatdock
```

To start it without a console window, double-click `run_cheatdock.pyw`.

### Start with Windows
Press `Win+R`, type `shell:startup` and put a shortcut to `CheatDock.exe` (or `run_cheatdock.pyw`) in that folder.

## Keyboard shortcuts

| Keys | Action |
|---|---|
| `Ctrl+Alt+Space` | Show / hide from anywhere (configurable) |
| `Ctrl+F` | Focus search |
| `Enter` (in search) | Copy the first match |
| `Ctrl+1` … `Ctrl+9` | Switch tab |
| `Ctrl+P` | Pin / unpin |
| `F5` | Reload cheat sheets |
| `Esc` | Clear search, then hide |

## Adding your own commands

Every file in [`cheatsheets/`](cheatsheets) becomes a tab, and the app reloads as soon as you save one. To add a new tab, for example Git, create `cheatsheets/05-git.yaml`:

```yaml
name: Git          # tab title
order: 5           # tab position
sections:
  - name: Basics
    items:
      - title: Undo last commit but keep changes
        code: |-
          git reset --soft HEAD~1
        note: Optional one-line explanation.
```

Use `code: |-` followed by an indented block. That way you never have to escape quotes, colons or `#`.

## Settings

Edit [`config.yaml`](config.yaml) and restart the app:

```yaml
edge: right               # right | left
width: 440
handle_width: 6
expand_on_hover: true
collapse_delay_ms: 500
hotkey: ctrl+alt+space    # e.g. ctrl+shift+k, win+alt+c, f9 ("" to disable)
opacity: 0.97
```

## Building the .exe yourself

```powershell
.\build.ps1
```

This creates `dist\CheatDock\CheatDock.exe` with `config.yaml` and `cheatsheets\` next to it (so they stay editable), plus `dist\CheatDock-windows.zip`.

Pushing a tag such as `v1.0.0` makes GitHub Actions build the zip and publish it as a Release automatically (see `.github/workflows/release.yml`).

## Contributing

Pull requests that add useful commands or new cheat sheets are welcome. Keep each item short: one task, one snippet.

## License

[MIT](LICENSE)
