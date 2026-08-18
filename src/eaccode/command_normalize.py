"""Command normalization + parser-limit (Phase 1, H4+H6+H5).

Provides:
  - ``normalize_command_for_detection(command)`` — collapse whitespace,
    unwrap leading quotes, fold ``~`` to absolute home path. Hermes does
    these steps BEFORE running pattern detection so that
    `  rm   -rf  /` matches regex like `\\brm\\s+...` reliably.
  - ``_command_parser_limit_exceeded(command, max_len)`` — return ``True``
    when the command is too complex to safely analyze. Hermes returns a
    "block + save-blocked-payload" verdict in that case.
  - ``_home_prefix_fold_regex`` + ``_rewrite_resolved_user_home`` —
    rewrite ``~/...`` and ``~user/...`` paths to canonical absolute paths
    so dangerous-pattern detection matches against ``r"\b/home/.*""`.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path


COMMAND_PARSER_LIMIT = 4096  # chars (Hermes-Verbatim default)


def normalize_command_for_detection(command: str) -> str:
    """Collapse whitespace, unwrap leading quotes, fold home expansion.

    Designed so that a dangerous command hits the same danger patterns
    regardless of how the model writes it (``rm   -rf /`` →
    ``rm -rf /``).
    """
    if not command:
        return ""
    text = command.strip()
    # Drop outer quotes that wrap the entire command (shell-style)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1]
    # Collapse whitespace into single spaces
    text = re.sub(r"\s+", " ", text)
    # ~-expand to home (avoid running into catastrophic patterns via
    # un-expanded tildes which our home-fold pattern needs)
    text = _rewrite_resolved_user_home(text)
    return text


def _rewrite_resolved_user_home(command: str) -> str:
    r"""Replace ``~/path`` and ``~user/path`` with ``/home/user/path``.

    Hermes-Verbatim: this rewrite helps dangerous-pattern detectors match
    against canonical absolute paths. For example "rm -rf ~/" becomes
    "rm -rf /home/<user>/" which matches the home-directory prefix pattern.
    """
    # Bare ~ at start of word -> home (use lambda to escape Path.home()
    # which contains backslashes on Windows)
    home = str(Path.home())
    command = re.sub(
        r"(\s|^)~(?=\s|$|;|\|)",
        lambda m: m.group(1) + home,
        command,
    )
    # ~/foo at start
    command = re.sub(
        r"(\s|^)~/(?=\S)",
        lambda m: m.group(1) + home + "/",
        command,
    )
    # ~user/foo (POSIX pattern; on Windows we ignore)
    import os

    if os.name != "nt":
        try:
            import pwd

            for match in re.finditer(
                r"(\s|^)(~([A-Za-z0-9_]+))(?=/|\s|$)", command
            ):
                try:
                    pw = pwd.getpwnam(match.group(3))
                    command = (
                        command[: match.start(2)] + pw.pw_dir + command[match.end(2) :]
                    )
                except KeyError:
                    continue
        except ImportError:
            pass
    return command


def _home_prefix_fold_regex(home: str | Path) -> re.Pattern[str]:
    """Return compiled regex matching ``/home/<user>/...`` prefix.

    Used by dangerous-pattern builders so they can match any user's home
    (e.g. ``r"/home|/home/\\*|/root|/root/\\*"``).
    """
    home = str(Path(home))
    return re.compile(rf"(\bhome/|\bhome$|\\b{re.escape(home)})")


def _command_parser_limit_exceeded(command: str, max_len: int = COMMAND_PARSER_LIMIT) -> bool:
    """Return True when command is too complex to safely analyze.

    Hermes-Verbatim: at this point we save the command as a script file
    and ask the user to run it manually. We don't execute it ourselves.
    """
    if not command:
        return False
    if len(command) > max_len:
        return True
    # Detect embedded scripts via large substitutions or backtick blocks
    if command.count("$(") > 5 or command.count("`") > 5:
        return True
    # Shlex-parsing depth (best-effort - some commands aren't shlex-parseable)
    try:
        tokens = shlex.split(command)
        if len(tokens) > 200:
            return True
    except ValueError:
        return True
    return False
