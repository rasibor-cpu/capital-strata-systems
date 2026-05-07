from __future__ import annotations

import getpass
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
USERS_FILE = PROJECT_ROOT / "data" / "users.json"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SESSION_AUTH_FILE = ARTIFACTS_DIR / "css_auth_session.json"

INITIAL_ADMIN_ID = "00000"
INITIAL_ADMIN_PASSWORD = "123456"
INITIAL_DISPLAY_NAME = "CSS Administrator"
INITIAL_ROLE = "SUPER_USER"
MIN_PASSWORD_LENGTH = 6
PASSWORD_MAX_AGE_DAYS = 30
PASSWORD_HISTORY_LIMIT = 2
LOCKOUT_START_ATTEMPT = 3
LOCKOUT_SCHEDULE_SECONDS = (60, 300, 900, 1800, 3600)

CSS_AUTH_PANEL_WIDTH = 78


class AuthFailure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PasswordChangeRequired(Exception):
    def __init__(self, user_id: str) -> None:
        super().__init__("PASSWORD_CHANGE_REQUIRED")
        self.user_id = user_id


class PasswordValidationError(ValueError):
    pass


def await_login_ready_state() -> Dict[str, Any]:
    """
    Dashboard entry auth gate.

    Defaults to a Tk sign-on screen, with a policy-equivalent console screen when
    Tk is unavailable or CSS_AUTH_UI=cli/console/text.
    """
    users = load_users()
    auth_ui = os.getenv("CSS_AUTH_UI", "gui").strip().lower()

    if auth_ui in {"cli", "console", "text"}:
        return await_console_login(users)

    try:
        return await_gui_login(users)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        if os.getenv("CSS_AUTH_GUI_FAIL_CLOSED", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            raise

        print(f"[CSS AUTH UI] GUI unavailable; using console sign-on. reason={exc}")
        users = load_users()
        return await_console_login(users)


def load_users(users_file: Path = USERS_FILE) -> Dict[str, Any]:
    users_file.parent.mkdir(parents=True, exist_ok=True)

    changed = False
    if not users_file.exists():
        users = {INITIAL_ADMIN_ID: _default_admin_record()}
        save_users(users, users_file)
        return users

    try:
        raw = users_file.read_text(encoding="utf-8").strip()
        users = json.loads(raw) if raw else {}
    except Exception as exc:
        raise RuntimeError("CSS_USER_STORE_UNREADABLE") from exc

    if not isinstance(users, dict):
        raise RuntimeError("CSS_USER_STORE_INVALID")

    if INITIAL_ADMIN_ID not in users:
        users[INITIAL_ADMIN_ID] = _default_admin_record()
        changed = True

    for key, record in list(users.items()):
        if not isinstance(record, dict):
            continue

        normalized = normalize_user_id(record.get("user_id", key))
        if record.get("user_id") != normalized:
            record["user_id"] = normalized
            changed = True

        defaults = {
            "display_name": "CSS User",
            "role": "VIEWER",
            "unit_code": "CORE",
            "home_branch": "HQ",
            "must_change_password": False,
            "last_password_change": None,
            "password_history": [],
            "failed_attempts": 0,
            "locked": False,
            "locked_at": None,
            "lockout_until": None,
            "lockout_seconds": 0,
            "lockout_started_at": None,
        }
        for field, default in defaults.items():
            if field not in record:
                record[field] = default
                changed = True

        history = record.get("password_history")
        if not isinstance(history, list):
            record["password_history"] = []
            changed = True
        elif len(history) > PASSWORD_HISTORY_LIMIT:
            record["password_history"] = history[-PASSWORD_HISTORY_LIMIT:]
            changed = True

        if key != normalized:
            users[normalized] = record
            users.pop(key, None)
            changed = True

        if clear_expired_lockout(record):
            changed = True

    if changed:
        save_users(users, users_file)

    return users


def save_users(users: Dict[str, Any], users_file: Path = USERS_FILE) -> None:
    users_file.parent.mkdir(parents=True, exist_ok=True)
    users_file.write_text(json.dumps(users, indent=2), encoding="utf-8")


def authenticate_credentials(users: Dict[str, Any], user_id: str, password: str) -> Dict[str, Any]:
    normalized_user_id = normalize_user_id(user_id)
    if not normalized_user_id:
        raise AuthFailure("INVALID_USER_ID", "Enter a valid five digit user ID.")

    user_record = users.get(normalized_user_id)
    if not isinstance(user_record, dict):
        raise AuthFailure("INVALID_USER_ID", "User ID not recognized.")

    now = datetime.now()
    lockout_remaining = active_lockout_remaining_seconds(user_record, now)
    if lockout_remaining > 0:
        raise AuthFailure(
            "AUTH_LOCKOUT",
            (
                "Sequential failed sign-ons paused for "
                f"{format_duration(lockout_remaining)} for user ID {normalized_user_id}."
            ),
        )

    expected_hash = str(user_record.get("password_hash", "")).strip()
    supplied_hash = hash_password(password)

    if supplied_hash != expected_hash:
        failed_attempts = int(user_record.get("failed_attempts", 0) or 0) + 1
        user_record["failed_attempts"] = failed_attempts

        if failed_attempts >= LOCKOUT_START_ATTEMPT:
            lockout_seconds = lockout_seconds_for_attempt(failed_attempts)
            apply_timed_lockout(user_record, lockout_seconds, now)
            raise AuthFailure(
                "AUTH_LOCKOUT",
                (
                    "Sequential failed sign-ons paused for "
                    f"{format_duration(lockout_seconds)} after failed attempt {failed_attempts}."
                ),
            )

        remaining = LOCKOUT_START_ATTEMPT - failed_attempts
        raise AuthFailure(
            "AUTH_FAILED",
            f"Authentication failed. {remaining} attempt(s) remaining.",
        )

    user_record["failed_attempts"] = 0
    clear_lockout_state(user_record)

    if password_expired(user_record):
        raise PasswordChangeRequired(normalized_user_id)

    return build_user_context(user_record, normalized_user_id)


def change_password(
    users: Dict[str, Any],
    user_id: str,
    new_password: str,
    confirm_password: str,
) -> Dict[str, Any]:
    normalized_user_id = normalize_user_id(user_id)
    user_record = users.get(normalized_user_id)
    if not isinstance(user_record, dict):
        raise PasswordValidationError("User ID not recognized.")

    validate_new_password(user_record, new_password, confirm_password)

    current_hash = str(user_record.get("password_hash", "")).strip()
    history = user_record.get("password_history")
    if not isinstance(history, list):
        history = []
    if current_hash:
        history.append(current_hash)

    user_record["password_history"] = history[-PASSWORD_HISTORY_LIMIT:]
    user_record["password_hash"] = hash_password(new_password)
    user_record["must_change_password"] = False
    user_record["last_password_change"] = datetime.now().isoformat(timespec="seconds")
    user_record["failed_attempts"] = 0
    clear_lockout_state(user_record)

    return build_user_context(user_record, normalized_user_id)


def validate_new_password(
    user_record: Dict[str, Any],
    new_password: str,
    confirm_password: str,
) -> None:
    if not new_password:
        raise PasswordValidationError("Password cannot be blank.")

    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise PasswordValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )

    if new_password == INITIAL_ADMIN_PASSWORD:
        raise PasswordValidationError(
            "New password cannot remain the initial default password."
        )

    if new_password != confirm_password:
        raise PasswordValidationError("Passwords do not match.")

    new_hash = hash_password(new_password)
    current_hash = str(user_record.get("password_hash", "")).strip()
    history = user_record.get("password_history")
    if not isinstance(history, list):
        history = []

    recent_hashes = [current_hash] + [str(value) for value in history[-PASSWORD_HISTORY_LIMIT:]]
    if new_hash in recent_hashes:
        raise PasswordValidationError(
            "New password must differ from the current password and the last two passwords."
        )


def password_expired(user_record: Dict[str, Any]) -> bool:
    if bool(user_record.get("must_change_password", False)):
        return True

    last_change = user_record.get("last_password_change")
    if not last_change:
        return True

    try:
        last_dt = datetime.fromisoformat(str(last_change))
    except Exception:
        return True

    return datetime.now() - last_dt >= timedelta(days=PASSWORD_MAX_AGE_DAYS)


def lockout_seconds_for_attempt(failed_attempts: int) -> int:
    if failed_attempts < LOCKOUT_START_ATTEMPT:
        return 0

    index = failed_attempts - LOCKOUT_START_ATTEMPT
    if index >= len(LOCKOUT_SCHEDULE_SECONDS):
        return LOCKOUT_SCHEDULE_SECONDS[-1]

    return LOCKOUT_SCHEDULE_SECONDS[index]


def apply_timed_lockout(
    user_record: Dict[str, Any],
    lockout_seconds: int,
    now: Optional[datetime] = None,
) -> None:
    current_time = now or datetime.now()
    user_record["locked"] = True
    user_record["locked_at"] = current_time.isoformat(timespec="seconds")
    user_record["lockout_started_at"] = current_time.isoformat(timespec="seconds")
    user_record["lockout_seconds"] = int(lockout_seconds)
    user_record["lockout_until"] = (
        current_time + timedelta(seconds=int(lockout_seconds))
    ).isoformat(timespec="seconds")


def active_lockout_remaining_seconds(
    user_record: Dict[str, Any],
    now: Optional[datetime] = None,
) -> int:
    current_time = now or datetime.now()
    lockout_until = parse_datetime(user_record.get("lockout_until"))

    if lockout_until is None:
        if bool(user_record.get("locked", False)):
            clear_lockout_state(user_record, preserve_failed_attempts=True)
        return 0

    if lockout_until <= current_time:
        clear_lockout_state(user_record, preserve_failed_attempts=True)
        return 0

    remaining = int((lockout_until - current_time).total_seconds())
    return max(1, remaining)


def clear_expired_lockout(user_record: Dict[str, Any]) -> bool:
    before = (
        user_record.get("locked"),
        user_record.get("locked_at"),
        user_record.get("lockout_until"),
    )
    active_lockout_remaining_seconds(user_record)
    after = (
        user_record.get("locked"),
        user_record.get("locked_at"),
        user_record.get("lockout_until"),
    )
    return before != after


def clear_lockout_state(
    user_record: Dict[str, Any],
    preserve_failed_attempts: bool = False,
) -> None:
    user_record["locked"] = False
    user_record["locked_at"] = None
    user_record["lockout_until"] = None
    user_record["lockout_seconds"] = 0
    user_record["lockout_started_at"] = None
    if not preserve_failed_attempts:
        user_record["failed_attempts"] = 0


def parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def format_duration(seconds: int) -> str:
    value = max(1, int(seconds))

    if value < 60:
        unit = "second" if value == 1 else "seconds"
        return f"{value} {unit}"

    minutes = (value + 59) // 60
    if minutes < 60:
        unit = "minute" if minutes == 1 else "minutes"
        return f"{minutes} {unit}"

    hours = (minutes + 59) // 60
    unit = "hour" if hours == 1 else "hours"
    return f"{hours} {unit}"


def build_user_context(user_record: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    return {
        "user_id": normalize_user_id(user_record.get("user_id", user_id)),
        "display_name": str(user_record.get("display_name", "CSS User")),
        "role": str(user_record.get("role", "VIEWER")).upper(),
        "unit_code": str(user_record.get("unit_code", "CORE")),
        "home_branch": str(user_record.get("home_branch", "HQ")),
    }


def persist_login_session(user_ctx: Dict[str, Any]) -> None:
    SESSION_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_AUTH_FILE.write_text(
        json.dumps(
            {
                "user_id": user_ctx.get("user_id"),
                "display_name": user_ctx.get("display_name"),
                "role": user_ctx.get("role"),
                "unit_code": user_ctx.get("unit_code"),
                "home_branch": user_ctx.get("home_branch"),
                "last_login": datetime.now().isoformat(timespec="seconds"),
                "login_persistence": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def await_console_login(users: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    active_users = users if users is not None else load_users()
    render_console_sign_in_screen()

    while True:
        user_id = input("CSS AUTH | user id: ").strip()
        password = masked_password_input("CSS AUTH | password: ")

        try:
            user_ctx = authenticate_credentials(active_users, user_id, password)
            save_users(active_users)
            persist_login_session(user_ctx)
            render_console_auth_status("AUTH SUCCESS", f"{user_ctx['display_name']} | role={user_ctx['role']}")
            return user_ctx
        except PasswordChangeRequired as required:
            save_users(active_users)
            user_ctx = force_console_password_change(active_users, required.user_id)
            save_users(active_users)
            persist_login_session(user_ctx)
            render_console_auth_status("AUTH SUCCESS", f"{user_ctx['display_name']} | role={user_ctx['role']}")
            return user_ctx
        except AuthFailure as exc:
            save_users(active_users)
            render_console_auth_status(exc.code, exc.message)


def force_console_password_change(users: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    render_console_auth_status(
        "PASSWORD CHANGE REQUIRED",
        "Initial or expired password must be changed now.",
    )

    while True:
        new_password = masked_password_input("CSS AUTH | new password: ").strip()
        confirm_password = masked_password_input("CSS AUTH | confirm password: ").strip()

        try:
            user_ctx = change_password(users, user_id, new_password, confirm_password)
        except PasswordValidationError as exc:
            render_console_auth_status("PASSWORD ERROR", str(exc))
            continue

        render_console_auth_status("PASSWORD UPDATED", "Password changed successfully.")
        return user_ctx


def await_gui_login(users: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    import tkinter as tk
    from tkinter import font as tkfont

    active_users = users if users is not None else load_users()
    result: Dict[str, Any] = {"ctx": None, "cancelled": False}

    colors = {
        "ink": "#0f1720",
        "bg": "#f4f7f8",
        "panel": "#ffffff",
        "left": "#10202a",
        "muted": "#60717a",
        "line": "#d8e2e6",
        "teal": "#1d8a8a",
        "teal_dark": "#146767",
        "amber": "#c9861a",
        "danger": "#b42318",
        "success": "#166534",
        "field": "#eef4f5",
    }

    root = tk.Tk()
    root.title("Capital Strata Systems - Sign On")
    root.geometry("960x620")
    root.minsize(860, 560)
    root.configure(bg=colors["bg"])

    title_font = tkfont.Font(family="Segoe UI", size=24, weight="bold")
    subtitle_font = tkfont.Font(family="Segoe UI", size=11)
    label_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
    field_font = tkfont.Font(family="Segoe UI", size=12)
    button_font = tkfont.Font(family="Segoe UI", size=11, weight="bold")
    small_font = tkfont.Font(family="Segoe UI", size=9)

    shell = tk.Frame(root, bg=colors["bg"])
    shell.pack(fill="both", expand=True, padx=28, pady=28)
    shell.columnconfigure(0, minsize=360, weight=0)
    shell.columnconfigure(1, weight=1)
    shell.rowconfigure(0, weight=1)

    left = tk.Frame(shell, bg=colors["left"], width=360)
    left.grid(row=0, column=0, sticky="nsew")
    left.grid_propagate(False)

    canvas = tk.Canvas(left, width=250, height=250, bg=colors["left"], highlightthickness=0)
    canvas.pack(pady=(58, 24))
    canvas.create_oval(28, 28, 222, 222, outline=colors["teal"], width=4)
    canvas.create_oval(58, 58, 192, 192, outline=colors["amber"], width=2)
    canvas.create_line(54, 158, 104, 100, 145, 132, 198, 78, fill="#edf6f7", width=5, smooth=True)
    canvas.create_line(54, 158, 104, 100, 145, 132, 198, 78, fill=colors["teal"], width=2, smooth=True)
    canvas.create_text(125, 126, text="CSS", fill="#ffffff", font=("Segoe UI", 32, "bold"))

    tk.Label(
        left,
        text="CAPITAL STRATA\nSYSTEMS",
        bg=colors["left"],
        fg="#ffffff",
        justify="left",
        font=("Segoe UI", 24, "bold"),
    ).pack(anchor="w", padx=42)
    tk.Label(
        left,
        text="Governance runtime access",
        bg=colors["left"],
        fg="#b7c7cc",
        justify="left",
        font=subtitle_font,
    ).pack(anchor="w", padx=44, pady=(10, 36))

    policy = tk.Frame(left, bg=colors["left"])
    policy.pack(anchor="w", padx=42, fill="x")
    _policy_badge(policy, "AUTH REQUIRED", colors["teal"], "#e8fbfb", small_font)
    _policy_badge(policy, f"{PASSWORD_MAX_AGE_DAYS} DAY PASSWORD", colors["amber"], "#fff5df", small_font)
    _policy_badge(policy, f"LOCKOUT AFTER {LOCKOUT_START_ATTEMPT}", "#7c3aed", "#f1ebff", small_font)

    right = tk.Frame(shell, bg=colors["panel"])
    right.grid(row=0, column=1, sticky="nsew")
    right.columnconfigure(0, weight=1)
    right.rowconfigure(0, weight=1)

    content = tk.Frame(right, bg=colors["panel"])
    content.grid(row=0, column=0, sticky="nsew", padx=56, pady=46)
    content.columnconfigure(0, weight=1)

    status_var = tk.StringVar(value="Ready")
    status_color = {"fg": colors["muted"]}
    pending_user_id = {"value": None}
    status_label_ref: Dict[str, Any] = {"widget": None}

    def clear_content() -> None:
        for child in content.winfo_children():
            child.destroy()

    def set_status(message: str, kind: str = "info") -> None:
        palette = {
            "info": colors["muted"],
            "error": colors["danger"],
            "success": colors["success"],
        }
        status_color["fg"] = palette.get(kind, colors["muted"])
        status_var.set(message)
        widget = status_label_ref.get("widget")
        if widget is not None:
            widget.configure(fg=status_color["fg"])

    def attach_status(row: int) -> None:
        status_label = tk.Label(
            content,
            textvariable=status_var,
            bg=colors["panel"],
            fg=status_color["fg"],
            font=subtitle_font,
        )
        status_label.grid(row=row, column=0, sticky="w", pady=(8, 0))
        status_label_ref["widget"] = status_label

    def make_entry(parent: tk.Frame, textvariable: tk.StringVar, show: str = "") -> tk.Entry:
        entry = tk.Entry(
            parent,
            textvariable=textvariable,
            show=show,
            relief="flat",
            bg=colors["field"],
            fg=colors["ink"],
            insertbackground=colors["teal"],
            font=field_font,
            width=28,
        )
        entry.configure(highlightthickness=1, highlightbackground=colors["line"], highlightcolor=colors["teal"])
        return entry

    def primary_button(parent: tk.Frame, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=colors["teal"],
            fg="#ffffff",
            activebackground=colors["teal_dark"],
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            font=button_font,
            padx=22,
            pady=10,
        )

    def secondary_button(parent: tk.Frame, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg="#e7eef1",
            fg=colors["ink"],
            activebackground="#d8e2e6",
            activeforeground=colors["ink"],
            relief="flat",
            cursor="hand2",
            font=button_font,
            padx=22,
            pady=10,
        )

    def finish(user_ctx: Dict[str, Any]) -> None:
        persist_login_session(user_ctx)
        result["ctx"] = user_ctx
        root.destroy()

    def show_password_change(user_id: str) -> None:
        clear_content()
        pending_user_id["value"] = user_id

        tk.Label(content, text="Password Update", bg=colors["panel"], fg=colors["ink"], font=title_font).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(
            content,
            text="Initial or expired password must be changed now.",
            bg=colors["panel"],
            fg=colors["muted"],
            font=subtitle_font,
        ).grid(row=1, column=0, sticky="w", pady=(8, 30))

        new_var = tk.StringVar()
        confirm_var = tk.StringVar()
        show_var = tk.BooleanVar(value=False)

        tk.Label(content, text="New Password", bg=colors["panel"], fg=colors["ink"], font=label_font).grid(
            row=2, column=0, sticky="w"
        )
        new_entry = make_entry(content, new_var, show="*")
        new_entry.grid(row=3, column=0, sticky="ew", ipady=10, pady=(6, 18))

        tk.Label(content, text="Confirm Password", bg=colors["panel"], fg=colors["ink"], font=label_font).grid(
            row=4, column=0, sticky="w"
        )
        confirm_entry = make_entry(content, confirm_var, show="*")
        confirm_entry.grid(row=5, column=0, sticky="ew", ipady=10, pady=(6, 12))

        def toggle_passwords() -> None:
            show_char = "" if show_var.get() else "*"
            new_entry.configure(show=show_char)
            confirm_entry.configure(show=show_char)

        tk.Checkbutton(
            content,
            text="Show password",
            variable=show_var,
            command=toggle_passwords,
            bg=colors["panel"],
            fg=colors["muted"],
            activebackground=colors["panel"],
            activeforeground=colors["ink"],
            selectcolor=colors["panel"],
            font=small_font,
        ).grid(row=6, column=0, sticky="w")

        button_row = tk.Frame(content, bg=colors["panel"])
        button_row.grid(row=7, column=0, sticky="ew", pady=(28, 18))

        def submit_change() -> None:
            try:
                user_ctx = change_password(active_users, user_id, new_var.get().strip(), confirm_var.get().strip())
                save_users(active_users)
            except PasswordValidationError as exc:
                set_status(str(exc), "error")
                return

            set_status("Password updated.", "success")
            finish(user_ctx)

        primary_button(button_row, "Update Password", submit_change).pack(side="left")
        secondary_button(button_row, "Cancel", root.destroy).pack(side="left", padx=(12, 0))

        attach_status(8)
        set_status("Password change required.", "info")
        new_entry.focus_set()
        root.bind("<Return>", lambda _event: submit_change())

    def show_login() -> None:
        clear_content()
        root.bind("<Return>", lambda _event: submit_login())

        tk.Label(content, text="Sign On", bg=colors["panel"], fg=colors["ink"], font=title_font).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(
            content,
            text="Capital Strata Systems dashboard access",
            bg=colors["panel"],
            fg=colors["muted"],
            font=subtitle_font,
        ).grid(row=1, column=0, sticky="w", pady=(8, 30))

        user_var = tk.StringVar(value=INITIAL_ADMIN_ID)
        password_var = tk.StringVar()
        show_var = tk.BooleanVar(value=False)

        tk.Label(content, text="User ID", bg=colors["panel"], fg=colors["ink"], font=label_font).grid(
            row=2, column=0, sticky="w"
        )
        user_entry = make_entry(content, user_var)
        user_entry.grid(row=3, column=0, sticky="ew", ipady=10, pady=(6, 18))

        tk.Label(content, text="Password", bg=colors["panel"], fg=colors["ink"], font=label_font).grid(
            row=4, column=0, sticky="w"
        )
        password_entry = make_entry(content, password_var, show="*")
        password_entry.grid(row=5, column=0, sticky="ew", ipady=10, pady=(6, 12))

        def toggle_password() -> None:
            password_entry.configure(show="" if show_var.get() else "*")

        tk.Checkbutton(
            content,
            text="Show password",
            variable=show_var,
            command=toggle_password,
            bg=colors["panel"],
            fg=colors["muted"],
            activebackground=colors["panel"],
            activeforeground=colors["ink"],
            selectcolor=colors["panel"],
            font=small_font,
        ).grid(row=6, column=0, sticky="w")

        button_row = tk.Frame(content, bg=colors["panel"])
        button_row.grid(row=7, column=0, sticky="ew", pady=(28, 18))

        def submit_login() -> None:
            try:
                user_ctx = authenticate_credentials(active_users, user_var.get(), password_var.get())
                save_users(active_users)
            except PasswordChangeRequired as required:
                save_users(active_users)
                password_var.set("")
                show_password_change(required.user_id)
                return
            except AuthFailure as exc:
                save_users(active_users)
                password_var.set("")
                set_status(exc.message, "error")
                password_entry.focus_set()
                return

            set_status("Authentication successful.", "success")
            finish(user_ctx)

        primary_button(button_row, "Sign On", submit_login).pack(side="left")
        secondary_button(button_row, "Exit", root.destroy).pack(side="left", padx=(12, 0))

        attach_status(8)
        set_status("Ready", "info")
        password_entry.focus_set()

    def on_close() -> None:
        result["cancelled"] = True
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    show_login()
    root.mainloop()

    if result.get("ctx"):
        return result["ctx"]

    raise KeyboardInterrupt("CSS_SIGN_ON_CANCELLED")


def _policy_badge(parent, text: str, bg: str, fg: str, font) -> None:
    import tkinter as tk

    tk.Label(
        parent,
        text=text,
        bg=bg,
        fg=fg,
        padx=12,
        pady=6,
        font=font,
    ).pack(anchor="w", pady=(0, 8))


def render_console_sign_in_screen() -> None:
    print()
    print(_panel_border("="))
    print(_panel_line("CAPITAL STRATA SYSTEMS"))
    print(_panel_line("Dashboard Sign On"))
    print(_panel_border("-"))
    print(_panel_line("Authentication", "required"))
    print(_panel_line("Initial Admin ID", INITIAL_ADMIN_ID))
    print(_panel_line("Password Age", f"{PASSWORD_MAX_AGE_DAYS} calendar days"))
    print(_panel_line("Password History", f"last {PASSWORD_HISTORY_LIMIT} blocked"))
    print(_panel_line("Failed Attempts", f"timed lockouts from attempt {LOCKOUT_START_ATTEMPT}"))
    print(_panel_border("="))
    print()


def render_console_auth_status(title: str, message: str) -> None:
    print()
    print(_panel_border("-"))
    print(_panel_line(title, message))
    print(_panel_border("-"))
    print()


def masked_password_input(prompt: str = "CSS AUTH | password: ") -> str:
    try:
        import msvcrt

        print(prompt, end="", flush=True)
        password_chars = []

        while True:
            ch = msvcrt.getwch()

            if ch in ("\r", "\n"):
                print()
                break

            if ch in ("\b", "\x7f"):
                if password_chars:
                    password_chars.pop()
                    print("\b \b", end="", flush=True)
                continue

            if ch in ("\x00", "\xe0"):
                try:
                    msvcrt.getwch()
                except Exception:
                    pass
                continue

            password_chars.append(ch)
            print("*", end="", flush=True)

        return "".join(password_chars)
    except Exception:
        return getpass.getpass(prompt)


def normalize_user_id(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if not raw.isdigit():
        return ""
    if len(raw) > 5:
        return ""
    return raw.zfill(5)


def hash_password(password: str) -> str:
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def _default_admin_record() -> Dict[str, Any]:
    return {
        "user_id": INITIAL_ADMIN_ID,
        "display_name": INITIAL_DISPLAY_NAME,
        "role": INITIAL_ROLE,
        "unit_code": "CORE",
        "home_branch": "HQ",
        "password_hash": hash_password(INITIAL_ADMIN_PASSWORD),
        "must_change_password": True,
        "last_password_change": None,
        "password_history": [],
        "failed_attempts": 0,
        "locked": False,
        "locked_at": None,
        "lockout_until": None,
        "lockout_seconds": 0,
        "lockout_started_at": None,
    }


def _panel_border(char: str = "=") -> str:
    return char * CSS_AUTH_PANEL_WIDTH


def _panel_line(label: str = "", value: str = "") -> str:
    content_width = CSS_AUTH_PANEL_WIDTH - 4
    text = f"{label}: {value}" if value else label
    return f"| {text[:content_width].ljust(content_width)} |"
