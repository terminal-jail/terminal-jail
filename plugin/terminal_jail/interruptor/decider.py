"""Rule evaluation engine for the interruptor.

Evaluates parsed command segments against built-in and user-defined rules
in priority order. Algorithm:

1. Check against CRITICAL blocklist (always first)
2. Check against ALLOW list (skip further eval if matched)
3. Check against AUTO-SANDBOX patterns (wrap in unshare)
4. Evaluate user-defined rules in priority order
"""

from __future__ import annotations

from .allowlist import BUILTIN_ALLOWLIST
from .blocklist import BUILTIN_BLOCKLIST
from .config import Config
from .matcher import Matcher
from .parser import Segment, SegmentType
from .rules import Rule, RuleLoader, RuleSet
from .sandbox import BUILTIN_SANDBOX
from .types import Action, InterceptResult
from .userns import unshare_prefix

# The unshare namespace prefix used by both the built-in auto-sandbox
# layer and user-defined modify rules (identical wrap semantics). Built
# once per process by userns.unshare_prefix(): a MAPPED user namespace
# (real filesystem isolation) when the host permits it, the legacy
# mapping-less flags otherwise — see plugin/terminal_jail/interruptor/
# userns.py and scripts/fs-isolation-probe.py (TJ-DF-015).
_UNSHARE_PREFIX = unshare_prefix()


class Decider:
    """Evaluates commands against the full rule set.

    Applies rules in the correct precedence order:
    1. Critical blocklist (always evaluated first)
    2. Allowlist (skip further evaluation if matched)
    3. Auto-sandbox (wrap in unshare)
    4. User-defined rules

    User rules are loaded once per Decider via RuleLoader (system then
    user rules.d directories; missing directories pass through). A user
    rule whose id matches a built-in rule id REPLACES that built-in entry
    in its layer (same-ID override, per blocklist.py's contract and spec
    T-I38); user rules with brand-new ids are evaluated in Layer 4 after
    auto-sandbox, highest priority first, first match wins (spec §4(d)).
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.matcher = Matcher()
        user_rules = RuleLoader(
            system_dir=config.system_rules_dir,
            user_dir=config.user_rules_dir,
        ).load_all()
        self._user_rules = user_rules
        (
            self._blocklist,
            self._allowlist,
            self._sandbox,
            self._layer4,
        ) = self._build_layers(user_rules)

    def _build_layers(
        self, user_rules: RuleSet
    ) -> tuple[list[Rule], list[Rule], list[Rule], list[Rule]]:
        """Build the per-layer effective rule lists once.

        Same-ID override semantics: any user rule whose id matches a
        built-in rule id replaces that built-in entry in its layer (the
        built-in is removed and the user rule is evaluated in its place).
        User rules with new ids are collected into the Layer 4 list,
        already sorted by priority descending (RuleSet order is preserved).
        """
        user_by_id = {r.id for r in user_rules.rules}

        def effective(builtins: list[Rule], layer_ids: set[str]) -> list[Rule]:
            rules = [r for r in builtins if r.id not in user_by_id]
            rules.extend(r for r in user_rules.rules if r.id in layer_ids)
            rules.sort(key=lambda r: r.priority, reverse=True)
            return rules

        block_ids = {r.id for r in BUILTIN_BLOCKLIST}
        allow_ids = {r.id for r in BUILTIN_ALLOWLIST}
        sandbox_ids = {r.id for r in BUILTIN_SANDBOX}
        blocklist = effective(BUILTIN_BLOCKLIST, block_ids)
        allowlist = effective(BUILTIN_ALLOWLIST, allow_ids)
        sandbox = effective(BUILTIN_SANDBOX, sandbox_ids)
        layer4 = [
            r for r in user_rules.rules if r.id not in block_ids | allow_ids | sandbox_ids
        ]
        return blocklist, allowlist, sandbox, layer4

    def evaluate(self, segments: list[Segment], original: str) -> InterceptResult:
        """Evaluate all segments of a command through the rule engine.

        Args:
            segments: Parsed command segments.
            original: The original command string.

        Returns:
            An InterceptResult with the final action decision.
        """
        if not segments:
            return InterceptResult(action=Action.ALLOW, command=original)

        # Check the full command against the blocklist first (catches pipe
        # chains). Same-ID user overrides apply here too: only rules whose
        # action is block take part — an allow/modify replacement must not
        # block the full command before segment evaluation.
        full_segment = Segment(
            type=SegmentType.SIMPLE,
            tokens=[],
            raw=original,
            pos=0,
        )
        for rule in self._blocklist:
            if rule.action != Action.BLOCK:
                continue
            match_result = self.matcher.match_segment(full_segment, rule.match)
            if match_result:
                return InterceptResult(
                    action=Action.BLOCK,
                    command=original,
                    rule_id=rule.id,
                    reason=rule.block_message,
                )

        # Then check each segment individually
        modified_segments: list[str] = []
        any_modified = False
        any_warn_reason = ""
        warn_rule_id: str | None = None

        for segment in segments:
            result = self._evaluate_segment(segment)
            if result.action == Action.BLOCK:
                return result
            if result.action in (Action.MODIFY, Action.SANDBOX):
                any_modified = True
                modified_segments.append(result.modified or segment.raw)
            elif result.action == Action.ALLOW:
                modified_segments.append(segment.raw)
                # Preserve a would-have-blocked warn reason (TJ-DF-012): a
                # same-ID user rule with action=warn replaces a builtin and
                # evaluates to ALLOW with a warn reason. Without this the
                # reason was dropped here, so the CLI printed nothing and
                # the override ran silently.
                if result.reason and not any_warn_reason:
                    any_warn_reason = result.reason
                    warn_rule_id = result.rule_id
            else:
                # WARN / LOG — allow through
                modified_segments.append(segment.raw)
                if getattr(result, "reason", "") and not any_warn_reason:
                    any_warn_reason = result.reason
                    warn_rule_id = result.rule_id

        if any_modified:
            modified_cmd = " ".join(modified_segments)
            return InterceptResult(
                action=Action.MODIFY,
                command=original,
                modified=modified_cmd,
                reason="Command modified by auto-sandbox",
            )

        if any_warn_reason:
            return InterceptResult(
                action=Action.ALLOW,
                command=original,
                rule_id=warn_rule_id,
                reason=any_warn_reason,
            )

        return InterceptResult(action=Action.ALLOW, command=original)

    def _evaluate_segment(self, segment: Segment) -> InterceptResult:
        """Evaluate a single command segment against all rule layers."""
        raw = segment.raw

        # Layer 1: Critical blocklist (builtins + same-ID user overrides)
        for rule in self._blocklist:
            match_result = self.matcher.match_segment(segment, rule.match)
            if match_result:
                return self._rule_result(rule, raw)

        # Layer 2: Allowlist — if matched, skip further evaluation
        for rule in self._allowlist:
            match_result = self.matcher.match_segment(segment, rule.match)
            if match_result:
                return self._rule_result(rule, raw)

        # Layer 3: Auto-sandbox — wrap in unshare
        for rule in self._sandbox:
            match_result = self.matcher.match_segment(segment, rule.match)
            if match_result:
                return self._rule_result(rule, raw)

        # Layer 4: User-defined rules (new ids) — priority order, first match wins
        for rule in self._layer4:
            match_result = self.matcher.match_segment(segment, rule.match)
            if match_result:
                return self._rule_result(rule, raw)

        return InterceptResult(action=Action.ALLOW, command=raw)

    def _rule_result(self, rule: Rule, raw: str) -> InterceptResult:
        """Build the InterceptResult for a matched rule (any layer).

        Dispatch by the rule's action:
        - block: BLOCK with the rule's id and block_message
        - modify/sandbox: MODIFY wrapping the command in the unshare
          namespace (the same prefix the built-in auto-sandbox layer uses)
        - warn: ALLOW carrying a would-have-blocked reason (TJ-DF-012) —
          the command runs, but the wrapper surfaces the warning on stderr.
          Same-ID user rules may override a builtin to warn (blocklist.py
          contract: builtins "cannot be removed — only overridden to warn
          level by user rules"); previously this fell into the unknown-
          action branch with a misleading "unknown action 'warn'" reason
          and the reason was dropped, so the override ran silently.
        - allow: ALLOW (rule id retained for traceability)
        - anything else: fail-safe ALLOW with a warning reason (never block
          on an unknown action value)
        """
        if rule.action == Action.BLOCK:
            return InterceptResult(
                action=Action.BLOCK,
                command=raw,
                rule_id=rule.id,
                reason=rule.block_message,
            )
        if rule.action in (Action.MODIFY, Action.SANDBOX):
            modified = f"{_UNSHARE_PREFIX}{_escape_for_shell(raw)}"
            return InterceptResult(
                action=Action.MODIFY,
                command=raw,
                modified=modified,
                rule_id=rule.id,
                reason="Auto-sandbox: wrapped command in namespace isolation",
            )
        if rule.action == Action.WARN:
            return InterceptResult(
                action=Action.ALLOW,
                command=raw,
                rule_id=rule.id,
                reason=f"would have blocked: {rule.block_message}",
            )
        if rule.action == Action.ALLOW:
            return InterceptResult(action=Action.ALLOW, command=raw, rule_id=rule.id)
        return InterceptResult(
            action=Action.ALLOW,
            command=raw,
            reason=(
                f"User rule {rule.id!r} has unknown action {rule.action!r} "
                "— allowing (fail-safe)"
            ),
        )


def _escape_for_shell(cmd: str) -> str:
    """Escape a command string for shell embedding.

    Uses single-quote wrapping with proper handling of embedded quotes.
    """
    # Replace single quotes with '\'' sequence
    escaped = cmd.replace("'", "'\\''")
    return f"'{escaped}'"
