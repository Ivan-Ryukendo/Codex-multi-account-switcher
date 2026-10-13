"""All logic for the Codex multi-account switcher.

Run the program with codex_switch.py in the project root. This file holds the
functions it calls, in these sections:

  configuration    settings file, folder locations
  saved accounts   list, read and save logins
  processes        close Codex/ChatGPT, open ChatGPT
  codex cli        login, logout
  prompts          questions asked in the terminal
  operations       switch, add, remove, log out, status
  menu and CLI     the interactive menu and command-line commands

Files used (next to codex_switch.py unless changed in codex_switch_config.json):
  accounts/<name>/auth.json   saved login for one account
  accounts/active.txt         name of the account now in the main folder
  codex_switch_config.json    settings, created on first run
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("CODEX_SWITCH_CONFIG") or ROOT / "codex_switch_config.json")
AUTH_FILE = "auth.json"
ACTIVE_FILE = "active.txt"
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
IS_WINDOWS = os.name == "nt"


# ---------- configuration ----------

def default_config():
    if sys.platform == "win32":
        processes = ["ChatGPT.exe", "codex.exe", "codex-computer-use-swift.exe"]
    elif sys.platform == "darwin":
        processes = ["ChatGPT", "codex", "codex-computer-use-swift"]
    else:
        processes = ["codex"]
    return {
        "accounts_dir": "accounts",        # relative to the project root, or an absolute path
        "main_codex_home": "",             # empty = $CODEX_HOME, else ~/.codex
        "codex_command": "codex",          # the Codex CLI command
        "process_names": processes,        # processes closed before a switch
        "chatgpt_app_id": "",              # Windows only; detected automatically
        "open_chatgpt_command": [],        # empty = platform default
    }


def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def load_config():
    config = default_config()
    if CONFIG_PATH.exists():
        config.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    else:
        save_config(config)
    return config


def accounts_root(config):
    path = Path(os.path.expanduser(config["accounts_dir"]))
    return path if path.is_absolute() else ROOT / path


def main_home(config):
    if config["main_codex_home"]:
        return Path(os.path.expanduser(config["main_codex_home"]))
    if os.environ.get("CODEX_HOME"):
        return Path(os.environ["CODEX_HOME"])
    return Path.home() / ".codex"


# ---------- saved accounts ----------

def account_dir(config, name):
    return accounts_root(config) / name


def saved_login(config, name):
    return account_dir(config, name) / AUTH_FILE


def has_login(config, name):
    return saved_login(config, name).is_file()


def list_accounts(config):
    root = accounts_root(config)
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and NAME_RE.match(p.name))


def active_account(config):
    marker = accounts_root(config) / ACTIVE_FILE
    if not marker.is_file():
        return None
    name = marker.read_text(encoding="utf-8").strip()
    return name if NAME_RE.match(name) else None


def set_active(config, name):
    root = accounts_root(config)
    root.mkdir(parents=True, exist_ok=True)
    marker = root / ACTIVE_FILE
    if name:
        marker.write_text(name + "\n", encoding="utf-8")
    else:
        marker.unlink(missing_ok=True)


def copy_login(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if not IS_WINDOWS:
        os.chmod(destination, 0o600)  # the file holds a live login: owner-only


def find_string_key(data, key):
    if isinstance(data, dict):
        if isinstance(data.get(key), str):
            return data[key]
        for value in data.values():
            found = find_string_key(value, key)
            if found:
                return found
    return None


def login_email(auth_file):
    """Best effort: read the email from the saved id_token. Decoded locally, never printed."""
    try:
        data = json.loads(auth_file.read_text(encoding="utf-8"))
        token = data["tokens"]["id_token"]
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return None
    return find_string_key(claims, "email")


# ---------- processes and the ChatGPT app ----------

def run_quietly(args, **kwargs):
    try:
        return subprocess.run(args, capture_output=True, text=True, **kwargs)
    except FileNotFoundError:
        return None


def is_running(name):
    if IS_WINDOWS:
        result = run_quietly(["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"])
        return bool(result) and name.lower() in result.stdout.lower()
    result = run_quietly(["pgrep", "-x", name])
    return bool(result) and result.returncode == 0


def stop_apps(config):
    names = config["process_names"]
    if sys.platform == "darwin":
        run_quietly(["osascript", "-e", 'tell application "ChatGPT" to quit'])
        time.sleep(2)
    for name in names:
        if IS_WINDOWS:
            run_quietly(["taskkill", "/F", "/IM", name])
        else:
            run_quietly(["pkill", "-x", name])
    deadline = time.time() + 10
    while time.time() < deadline and any(is_running(n) for n in names):
        time.sleep(0.5)


def detect_windows_app_id():
    script = ("Get-StartApps | Where-Object { $_.Name -like 'ChatGPT*' } "
              "| Select-Object -First 1 -ExpandProperty AppID")
    result = run_quietly(["powershell", "-NoProfile", "-Command", script])
    return result.stdout.strip() if result else ""


def open_chatgpt(config):
    command = config["open_chatgpt_command"]
    if not command:
        if sys.platform == "darwin":
            command = ["open", "-a", "ChatGPT"]
        elif IS_WINDOWS:
            if not config["chatgpt_app_id"]:
                config["chatgpt_app_id"] = detect_windows_app_id()
                save_config(config)
            if config["chatgpt_app_id"]:
                command = ["explorer.exe", "shell:AppsFolder\\" + config["chatgpt_app_id"]]
    if not command:
        print("Open the ChatGPT app yourself.")
        return
    subprocess.Popen(command)


# ---------- Codex CLI ----------

def codex_executable(config):
    path = shutil.which(config["codex_command"])
    if not path:
        print(f"Cannot find the Codex command '{config['codex_command']}'. "
              f"Set codex_command in {CONFIG_PATH.name}.")
    return path


def codex_env(home):
    env = dict(os.environ)
    env["CODEX_HOME"] = str(home)
    return env


def login_account(config, name):
    codex = codex_executable(config)
    if not codex:
        return False
    home = account_dir(config, name)
    home.mkdir(parents=True, exist_ok=True)
    print(f"\nSigning in for '{name}'. A code and a link will appear below.")
    print("Open the link in a browser that is signed in to the NEW account:")
    print("sign out of ChatGPT there first, or use a private window.")
    print("Your current login is not changed. Waiting for sign-in to finish...\n")
    result = subprocess.run([codex, "login", "--device-auth"], env=codex_env(home))
    if result.returncode != 0:
        print(f"\nCodex sign-in ended with exit code {result.returncode}.")
    if has_login(config, name) and not IS_WINDOWS:
        os.chmod(saved_login(config, name), 0o600)
    return has_login(config, name)


def logout_codex(config):
    codex = codex_executable(config)
    if codex:
        subprocess.run([codex, "logout"], env=codex_env(main_home(config)))


# ---------- prompts ----------

def confirm(question):
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def ask_name(prompt):
    while True:
        name = input(f"{prompt} (letters, numbers, - or _; Enter to cancel): ").strip()
        if not name:
            return None
        if NAME_RE.match(name):
            return name
        print("Use letters, numbers, - or _ only (up to 40 characters).")


def pause():
    input("\nPress Enter to return to the menu...")


# ---------- operations ----------

def ensure_current_saved(config):
    """Save the login already in the main folder before anything replaces it."""
    live = main_home(config) / AUTH_FILE
    if active_account(config) or not live.is_file():
        return True
    print("\nThe login in the main Codex folder is not saved yet.")
    name = ask_name("Name for this account")
    if not name:
        print("Cancelled. Nothing was changed.")
        return False
    copy_login(live, saved_login(config, name))
    set_active(config, name)
    print(f"Saved the current login as '{name}'.")
    return True


def save_back_active(config):
    """Keep the active account's saved login up to date (tokens refresh over time)."""
    current = active_account(config)
    live = main_home(config) / AUTH_FILE
    if not current or not live.is_file() or not account_dir(config, current).is_dir():
        return
    saved = saved_login(config, current)
    live_email = login_email(live)
    saved_email = login_email(saved) if saved.is_file() else None
    if saved_email and live_email and saved_email != live_email:
        print(f"\nThe main login is for {live_email}, but '{current}' is saved for {saved_email}.")
        new_name = ask_name("Save the main login as a new account first")
        if new_name and has_login(config, new_name):
            print(f"'{new_name}' already exists. Nothing was saved.")
        elif new_name:
            copy_login(live, saved_login(config, new_name))
            print(f"Saved the main login as '{new_name}'.")
        else:
            print("Skipped. The main login will be replaced.")
        return
    copy_login(live, saved)


def switch_account(config, target):
    if not has_login(config, target):
        print(f"'{target}' is not logged in yet. Use 'Add an account' first.")
        return False
    if active_account(config) == target:
        print(f"'{target}' is already the active account.")
        return True
    if not ensure_current_saved(config):
        return False
    print("\nSwitching closes ChatGPT and every Codex process, including open Codex CLI sessions.")
    if not confirm("Continue?"):
        return False
    stop_apps(config)
    save_back_active(config)
    copy_login(saved_login(config, target), main_home(config) / AUTH_FILE)
    set_active(config, target)
    print(f"Switched to '{target}'.")
    open_chatgpt(config)
    return True


def add_account(config, name=None):
    name = name or ask_name("New account name")
    if not name:
        return False
    if not NAME_RE.match(name):
        print("Use letters, numbers, - or _ only (up to 40 characters).")
        return False
    if has_login(config, name):
        print(f"'{name}' is already saved.")
        return False
    created = not account_dir(config, name).exists()
    if not login_account(config, name):
        print("Sign-in was not completed. Nothing was saved.")
        if created:
            shutil.rmtree(account_dir(config, name), ignore_errors=True)
        return False
    email = login_email(saved_login(config, name))
    if email:
        for other in list_accounts(config):
            if other != name and has_login(config, other) and login_email(saved_login(config, other)) == email:
                print(f"Warning: this login is for {email}, the same account as '{other}'.")
    print(f"Saved '{name}'. The main login was not changed. Use 'Switch account' to use it.")
    return True


def remove_account(config, name):
    if name not in list_accounts(config):
        print(f"No saved account named '{name}'.")
        return False
    if name == active_account(config):
        print(f"'{name}' is the active account. Switch to another account first.")
        return False
    if not confirm(f"Delete the saved login and the whole folder for '{name}'?"):
        return False
    folder = account_dir(config, name).resolve()
    if folder.parent != accounts_root(config).resolve():
        print("Refusing to delete: the folder is outside the accounts folder.")
        return False
    shutil.rmtree(folder)
    print(f"Removed '{name}'.")
    return True


def logout_current(config):
    current = active_account(config)
    live = main_home(config) / AUTH_FILE
    if not current and not live.is_file():
        print("No account is active.")
        return False
    label = current or "the main login"
    if not confirm(f"Log out {label}? This closes ChatGPT and Codex and deletes its saved login."):
        return False
    stop_apps(config)
    logout_codex(config)
    if live.is_file():
        live.unlink()
    if current and has_login(config, current):
        saved_login(config, current).unlink()
    set_active(config, None)
    print(f"Logged out of {label}.")
    return True


def show_status(config):
    current = active_account(config)
    names = list_accounts(config)
    print("\nCodex account manager")
    print("-" * 21)
    print(f"Main folder:    {main_home(config)}")
    print(f"Active account: {current or 'none'}")
    print("Saved accounts:")
    if not names:
        print("  none yet - choose 'Add an account'")
    for index, name in enumerate(names, 1):
        if has_login(config, name):
            status = login_email(saved_login(config, name)) or "logged in"
        else:
            status = "not logged in"
        marker = "  *active" if name == current else ""
        print(f"  {index}. {name}  ({status}){marker}")
    return names


# ---------- menu and command line ----------

def menu(config):
    while True:
        names = show_status(config)
        print("\n" + "=" * 40)
        print("What would you like to do?")
        print("  1. Switch account")
        print("  2. Add an account")
        print("  3. Remove a saved account")
        print("  4. Log out the current account")
        print("  q. Quit")
        print("=" * 40)
        choice = input("Choose: ").strip().lower()
        if choice in ("q", "quit", "exit"):
            return
        if choice == "1":
            pick = input("Account number (Enter to cancel): ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(names):
                switch_account(config, names[int(pick) - 1])
        elif choice == "2":
            add_account(config)
        elif choice == "3":
            pick = input("Account number to remove (Enter to cancel): ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(names):
                remove_account(config, names[int(pick) - 1])
        elif choice == "4":
            logout_current(config)
        else:
            print(f"'{choice}' is not an option. Choose 1, 2, 3, 4 or q.")
            continue
        pause()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Switch between saved Codex logins.")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("status", help="show accounts and the active one")
    use = commands.add_parser("use", help="switch the main login to a saved account")
    use.add_argument("name")
    add = commands.add_parser("add", help="log in and save a new account")
    add.add_argument("name", nargs="?")
    remove = commands.add_parser("remove", help="delete a saved account")
    remove.add_argument("name")
    commands.add_parser("logout", help="log out the active account")
    args = parser.parse_args(argv)

    config = load_config()
    try:
        if args.command is None:
            if ensure_current_saved(config):
                menu(config)
        elif args.command == "status":
            show_status(config)
        elif args.command == "use":
            return 0 if switch_account(config, args.name) else 1
        elif args.command == "add":
            return 0 if add_account(config, args.name) else 1
        elif args.command == "remove":
            return 0 if remove_account(config, args.name) else 1
        elif args.command == "logout":
            return 0 if logout_current(config) else 1
    except (EOFError, KeyboardInterrupt):
        print()
        return 130
    return 0
