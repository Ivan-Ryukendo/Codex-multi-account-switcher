# Codex multi-account switcher

Keep several Codex logins, such as work and personal, and switch the main one with a few keystrokes. The ChatGPT app and the Codex CLI read the main login, so after a switch they use the account you picked.

The program only copies login files. It does not change your Codex settings, proxy setup or history.

## Requirements

- Python 3.8 or newer (standard library only, nothing to install with pip)
- The Codex CLI on your PATH as `codex`
- Optional: the ChatGPT desktop app, which the switcher closes and reopens

## Quick start

- **Windows:** double-click `Codex Account Manager.bat`.
- **macOS and Linux:** run `python3 codex_switch.py` in a terminal.

The first time, the program saves the login that is already in your main Codex folder. It asks for a name for it, for example `work`.

Then the menu appears:

```
========================================
What would you like to do?
  1. Switch account
  2. Add an account
  3. Remove a saved account
  4. Log out the current account
  q. Quit
========================================
```

- **Add an account:** choose 2 and type a name. A code and a link appear. Open the link in a browser that is signed in to the **new** account (sign out of ChatGPT there first, or use a private window). The new login is saved. Your current login is not changed.
- **Switch account:** choose 1 and pick a number. The program closes ChatGPT and Codex, saves the latest login of the account you are leaving, installs the chosen login, and reopens ChatGPT.
- **Remove a saved account:** choose 3. The active account cannot be removed. Switch first.
- **Log out the current account:** choose 4. This closes the apps, runs `codex logout`, and deletes the saved login of the active account.

## Command line

Use these for scripts or shortcuts:

```bash
python3 codex_switch.py status        # show saved accounts and the active one
python3 codex_switch.py use work      # switch the main login to "work"
python3 codex_switch.py add personal  # sign in and save a new account
python3 codex_switch.py remove old    # delete a saved account
python3 codex_switch.py logout        # log out the active account
```

Each command exits with 0 on success and 1 on failure.

## How it works

| Location | Contents |
|----------|----------|
| `$CODEX_HOME`, or `~/.codex` if unset | The main login that the ChatGPT app and Codex read |
| `accounts/<name>/auth.json` | The saved login for one account |
| `accounts/active.txt` | The name of the account currently in the main folder |
| `codex_switch_config.json` | Settings, created on first run |

When you switch, the program first copies the main login back into the account you are leaving. Tokens refresh over time, so this keeps the saved login current. If the main login belongs to a different email than the saved account, the program warns you and offers to save it under a new name before replacing it.

When you add an account and its email matches a saved account, you get a warning.

## Settings

Edit `codex_switch_config.json` to change these:

| Key | Meaning |
|-----|---------|
| `accounts_dir` | Where saved logins are stored. Relative to the project folder, or an absolute path. |
| `main_codex_home` | The main Codex folder. Empty means `$CODEX_HOME`, otherwise `~/.codex`. |
| `codex_command` | The Codex CLI command, if it is not `codex` on your PATH. |
| `process_names` | Processes closed before a switch. |
| `chatgpt_app_id` | Windows only. Filled in automatically. |
| `open_chatgpt_command` | Command that reopens ChatGPT. Empty means the platform default. |

## Project layout

```
codex_switch.py              the program (run this on macOS and Linux)
Codex Account Manager.bat    Windows double-click launcher
functions/codex_functions.py all program logic
README.md
.gitignore
```

Your `accounts/` folder and `codex_switch_config.json` stay on your computer. They are ignored by git.

## Security

- Saved logins are credentials. Do not share, sync or commit the `accounts/` folder.
- On macOS and Linux, login files are set to owner-only (`600`). On Windows, rely on your user-folder permissions.
- The program never prints tokens. The email shown in the menu is decoded locally from the login.

## Status

- **Windows:** tested with stand-in Codex and app commands. Switch, add, remove, logout, the same-account warning, a failed sign-in and the command-line commands all work.
- **macOS and Linux:** not tested yet. The default process names (`ChatGPT`, `codex`) and the macOS `open -a ChatGPT` command are unverified. Check them in `codex_switch_config.json` the first time you switch.

## Troubleshooting

- **Sign-in never completes:** the browser must be signed in to the account you are adding. Sign out first or use a private window.
- **"Cannot find the Codex command":** install the Codex CLI or set `codex_command` to its full path.
- **A switch does not seem to take effect:** make sure ChatGPT and Codex are fully closed. The program closes them, but another instance started by hand can restart them.
