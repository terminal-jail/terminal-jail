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
from .parser import (
    Segment,
    SegmentType,
    rebuild_command,
    segment_texts,
    structure_preserved,
)
from .rules import Rule, RuleLoader, RuleSet, inherit_override_message
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

        An overriding rule that declares no ``block_message`` inherits the
        replaced rule's message, so a downgrade to ``warn`` still tells the
        operator which policy it is deciding on (DF-TERMINAL-JAIL-25).
        """
        user_by_id = {r.id for r in user_rules.rules}

        def effective(builtins: list[Rule], layer_ids: set[str]) -> list[Rule]:
            replaced_by_id = {r.id: r for r in builtins if r.id in user_by_id}
            rules = [r for r in builtins if r.id not in user_by_id]
            rules.extend(
                inherit_override_message(r, replaced_by_id.get(r.id))
                for r in user_rules.rules
                if r.id in layer_ids
            )
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
            An InterceptResult with the final action decision. An aggregate
            MODIFY keeps the ORIGINAL command's shell structure (operators,
            redirections, whitespace) and carries the rule id that rewrote the
            first modified segment (TJ-GAP-066); see ``_rebuild_modified``.
        """
        if not segments:
            return InterceptResult(action=Action.ALLOW, command=original)

        # Check the full command against the blocklist first (catches pipe
        # chains). Same-ID user overrides apply here too: only rules whose
        # action is block take part — an allow/modify replacement must not
        # block the full command before segment evaluation.
        #
        # DF-TERMINAL-JAIL-16: this whole-command pass is also what keeps the
        # always-allow layer from APPROVING a pipeline whose sink is a raw
        # network client. The file-exfiltration rules
        # (builtin-net-file-exfil-pipe / -redirect) are BLOCK rules, so they are
        # matched HERE — before the Layer-2 allowlist can short-circuit on the
        # pipeline's reader segment and return `rule_id=allow-cat-safe` for
        # `cat <secret> | nc <host> <port>`. Segment-level allow rules are
        # unaffected for every shape these rules do not match.
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
        replacements: dict[int, str] = {}
        any_modified = False
        any_warn_reason = ""
        warn_rule_id: str | None = None
        # DF-TERMINAL-JAIL-12: the FIRST allow rule that matched a segment
        # (segment order) is carried onto the aggregate ALLOW result, so an
        # allow verdict names its provenance instead of looking identical to
        # a default-allow (no rule matched at all).
        allow_rule_id: str | None = None
        # TJ-GAP-066: the aggregate MODIFY used to drop rule_id entirely, so
        # callers had to replay the sandbox layer just to learn which rule
        # rewrote the command. It now carries the rule that rewrote the FIRST
        # segment (segment order) — for the built-in auto-sandbox layer that is
        # the first matching sandbox rule.
        modify_rule_id: str | None = None

        for index, segment in enumerate(segments):
            result = self._evaluate_segment(segment)
            if result.action == Action.BLOCK:
                return result
            if result.action in (Action.MODIFY, Action.SANDBOX):
                any_modified = True
                replacements[index] = result.modified or segment.raw
                if modify_rule_id is None:
                    modify_rule_id = result.rule_id
            elif result.action == Action.ALLOW:
                # Preserve a would-have-blocked warn reason (TJ-DF-012): a
                # same-ID user rule with action=warn replaces a builtin and
                # evaluates to ALLOW with a warn reason. Without this the
                # reason was dropped here, so the CLI printed nothing and
                # the override ran silently.
                if result.reason and not any_warn_reason:
                    any_warn_reason = result.reason
                    warn_rule_id = result.rule_id
                # DF-TERMINAL-JAIL-12: a plain allowlist match (no warn
                # reason) also carries its rule id here. Determinism: the
                # first matched allow rule in segment order wins; a warn
                # reason + its own rule_id still takes precedence at the
                # return below.
                elif result.rule_id and allow_rule_id is None:
                    allow_rule_id = result.rule_id
            else:
                # WARN / LOG — allow through
                if getattr(result, "reason", "") and not any_warn_reason:
                    any_warn_reason = result.reason
                    warn_rule_id = result.rule_id

        if any_modified:
            return InterceptResult(
                action=Action.MODIFY,
                command=original,
                modified=self._rebuild_modified(original, segments, replacements),
                rule_id=modify_rule_id,
                reason="Command modified by auto-sandbox",
            )

        if any_warn_reason:
            return InterceptResult(
                action=Action.ALLOW,
                command=original,
                rule_id=warn_rule_id,
                reason=any_warn_reason,
            )

        # DF-TERMINAL-JAIL-12: the aggregate allow carries the first matched
        # allow rule's id (segment order). rule_id stays None when NO rule
        # matched — that is default-allow (the blocklist is a deny-list), not
        # an approved decision.
        return InterceptResult(
            action=Action.ALLOW,
            command=original,
            rule_id=allow_rule_id,
        )

    def _rebuild_modified(
        self,
        original: str,
        segments: list[Segment],
        replacements: dict[int, str],
    ) -> str:
        """Rebuild the original command with the rewritten segments in place.

        TJ-GAP-066: the aggregate MODIFY path used to join the rewritten
        segments with a plain space, which DROPPED every shell operator of a
        pipeline — ``go test ./... | tee /tmp/log`` came back as
        ``unshare … bash -c 'go test ./...' tee /tmp/log``, i.e. ``tee`` became
        an argument of the sandboxed first stage and the second stage never
        ran. The rebuild now replaces each rewritten segment wholesale inside
        the ORIGINAL text, so operators, redirections and whitespace survive.

        Two guards run before the rebuilt string is trusted:

        1. the segments handed in must be the ones this command parses to
           (count and raw text), and
        2. the rebuilt string must keep the same segment count and operator
           sequence (``structure_preserved``) — the escaping of a segment that
           carries a quoted operator is not always round-trip safe.

        When either fails, the verdict degrades to a whole-command wrap: the
        original command as ONE quoted argument. That keeps the sandbox (the
        command still runs under namespace isolation) while making it
        structurally impossible to drop or re-bind an operator.
        """
        derived = segment_texts(original)
        if len(derived) == len(segments) and all(
            text == segment.raw for text, segment in zip(derived, segments)
        ):
            rebuilt = rebuild_command(original, replacements)
            if rebuilt is not None and structure_preserved(original, rebuilt):
                return rebuilt
        return f"{_UNSHARE_PREFIX}{_escape_for_shell(original.strip())}"

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
