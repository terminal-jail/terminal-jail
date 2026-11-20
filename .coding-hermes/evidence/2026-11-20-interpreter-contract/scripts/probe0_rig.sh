#!/bin/bash
# Rig construction for /tmp/tj-df-1120 — hostile interpreter dir, bad pin, makefile, perf fixture.
ROOT=/tmp/tj-df-1120
mkdir -p "$ROOT/hostile/dark/bin" "$ROOT/pin" "$ROOT/mk" "$ROOT/arms"
ln -sfn /usr/bin/python3 "$ROOT/hostile/dark/bin/python3"
printf '#!/bin/sh\necho should-never-run\n' > "$ROOT/pin/bad-python"
chmod 0644 "$ROOT/pin/bad-python"          # exists, NOT executable -> fault reason 'not executable'
chmod 0700 "$ROOT/hostile/dark"            # kara-owned; mapped payload uid 65534 cannot traverse
cat > "$ROOT/mk/Makefile" <<'EOF'
ok:
	@echo MODIFY-PAYLOAD-RAN
EOF
ls -la "$ROOT/hostile/dark" "$ROOT/pin" "$ROOT/mk"; cat "$ROOT/mk/Makefile"; echo RIG-READY
