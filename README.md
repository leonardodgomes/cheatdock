# CheatDock

A cheat sheet that lives on the edge of your screen.

CheatDock stays out of the way as a small `>_` icon on the edge of your monitor. Rest the mouse on it, click it, or press **Ctrl+Alt+Space** from any app, and it slides open with the cheat sheets **you** picked. Click a command to copy it, then go back to work.

## Features

- **Pick your cheat sheets**: on first launch a setup screen lets you choose from a library of **17 cheat sheets (480 commands)** and set the tab order. Change it any time with the ⚙ button
- **★ Favorites**: star the commands you use most and they appear together in the first tab. Commands you copy often also show up there under **Most used**
- **A small icon docked to the screen edge**, always on top, never in your taskbar
- **Works with multiple monitors**: drag the icon, or the panel's title bar, to any side of any screen. It snaps to the nearest edge and remembers where you left it
- **Opens on hover, click or a global hotkey**, and closes when you move away or press `Esc`
- **Search across every tab at once.** Each tab shows how many matches it has, and `Enter` copies the first result
- **Click to copy** any command
- **Pin** the panel open while you work through something
- **Plain YAML files**: add a tab or a command by editing a text file, and the app reloads on its own
- **Light and dark themes**: the ☀ / ☾ button in the panel switches them, and your choice is remembered
- System tray icon, no admin rights needed

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

## Cheat sheet library

| Category | Cheat sheets |
|---|---|
| Shell & OS | PowerShell, Bash / Linux, CMD, Windows shortcuts |
| Data | SQL, Pandas, NumPy, Excel, Power BI DAX, R |
| Programming | Python, JavaScript, Regex |
| Tools | Git, Docker, VS Code, Jupyter & envs |

## Keyboard shortcuts

| Keys | Action |
|---|---|
| `Ctrl+Alt+Space` | Show / hide from anywhere (configurable) |
| `Ctrl+F` | Focus search |
| `Enter` (in search) | Copy the first match |
| `Ctrl+1` … `Ctrl+9` | Switch tab |
| `Ctrl+P` | Pin / unpin |
| `Ctrl+,` or ⚙ | Choose cheat sheets |
| `Ctrl+T` | Switch light / dark theme |
| `Ctrl+Q` or ✕ | Close CheatDock |
| `F5` | Reload cheat sheets |
| `Esc` or – | Clear search, then hide |

## Adding your own commands

Every file in [`cheatsheets/`](cheatsheets) appears in the setup library, and the app reloads as soon as you save one. To add a new one, for example Kubernetes, create `cheatsheets/18-kubernetes.yaml`, then tick it with the ⚙ button:

```yaml
name: Kubernetes          # tab title
order: 18                 # position in the library
category: Tools           # group in the setup screen
description: Pods, deployments and logs with kubectl.
sections:
  - name: Basics
    items:
      - title: List pods
        code: |-
          kubectl get pods -A
        note: Optional one-line explanation.
```

Use `code: |-` followed by an indented block. That way you never have to escape quotes, colons or `#`.

## Settings

Edit [`config.yaml`](config.yaml) and restart the app:

```yaml
theme: dark               # dark | light | system
edge: right               # starting side before you drag it
width: 440
icon_size: 40
icon_position: 0.5        # starting height: 0 top, 1 bottom
expand_on_hover: true
hover_delay_ms: 250
collapse_delay_ms: 500
hotkey: ctrl+alt+space    # e.g. ctrl+shift+k, win+alt+c, f9 ("" to disable)
opacity: 0.97
```

The position you drag it to (screen, side and height), your theme, chosen cheat sheets, favorites and copy counts are saved in `%LOCALAPPDATA%\CheatDock\state.json`. The tray menu also has **Move to next screen**.

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
