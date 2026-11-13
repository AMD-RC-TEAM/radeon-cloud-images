#!/bin/bash
# hk-readme-smoke.sh -- the hk-dsl README's vLLM quick start, as a smoke test for an image.
#
# Runs exactly what the README tells a user to type, in the image's own environment:
#     pip install hk-dsl && vllm serve Qwen/Qwen3-8B
# then sends one completion and checks the server log. Fails (exit 1) when:
#   - the server does not reach "Application startup complete" within $TIMEOUT s, or the completion fails;
#   - the log shows aiter being JIT-built ("[aiter] start build") or the clang error of 2026-11-13
#     ("Unknown command line argument") -- hk must not pull aiter into an RDNA engine;
#   - hk said nothing: the log has neither hk's startup summary ("[hk] =====") nor its
#     "not supported" line (an image whose stack hk does not support passes, if hk says so and
#     the engine serves as stock).
# Environment (optional): HK_VERSION (pin, e.g. 0.9.21; default: whatever pip picks), MODEL
# (default Qwen/Qwen3-8B), PORT (18080), TIMEOUT (900). Mirrors (HF_ENDPOINT, PIP_INDEX_URL) are
# taken from the environment as the image's smoke job sets them. Writes the full log to
# ./hk-readme-smoke.log.
set -u
MODEL=${MODEL:-Qwen/Qwen3-8B}
PORT=${PORT:-18080}
TIMEOUT=${TIMEOUT:-900}
LOG=${LOG:-./hk-readme-smoke.log}
ulimit -c 0 2>/dev/null || true
export HSA_DISABLE_COREDUMP_ON_EXCEPTION=1

pkg=hk-dsl; [ -n "${HK_VERSION:-}" ] && pkg="hk-dsl==$HK_VERSION"
echo "== pip install $pkg"
pip install "$pkg" || { echo "FAIL: pip install $pkg"; exit 1; }
python3 -c "import hk; print('hk-dsl', hk.__version__)" || { echo "FAIL: import hk"; exit 1; }

echo "== vllm serve $MODEL (log: $LOG)"
vllm serve "$MODEL" --port "$PORT" > "$LOG" 2>&1 &
pid=$!
ok=0
for _ in $(seq 1 $((TIMEOUT / 5))); do
    sleep 5
    grep -q "Application startup complete" "$LOG" && { ok=1; break; }
    kill -0 $pid 2>/dev/null || break
done
reply=""
if [ $ok = 1 ]; then
    reply=$(curl -s -m 120 "localhost:$PORT/v1/completions" -H 'Content-Type: application/json' \
            -d "{\"model\":\"$MODEL\",\"prompt\":\"2+2=\",\"max_tokens\":8}")
fi
kill $pid 2>/dev/null; sleep 5; kill -9 $pid 2>/dev/null; wait $pid 2>/dev/null

fail=0
[ $ok = 1 ] || { echo "FAIL: server did not start (tail of the log below)"; tail -30 "$LOG"; fail=1; }
[ $ok = 1 ] && ! echo "$reply" | grep -q '"choices"' && { echo "FAIL: completion: ${reply:0:300}"; fail=1; }
if grep -qE '\[aiter\] start build|Unknown command line argument' "$LOG"; then
    echo "FAIL: aiter was JIT-built in the engine:"; grep -E '\[aiter\] start build|Unknown command line' "$LOG" | head -3
    fail=1
fi
if ! grep -qE '\[hk\] =====|\[hk\] vLLM: hk is OFF, this stack is not supported|\[hk\] vLLM: off \(HK_DISABLE' "$LOG"; then
    echo "FAIL: no hk startup line in the log (plugin not loaded?)"; fail=1
fi
echo "== hk lines:"; grep -E '\[hk\]' "$LOG" | sed -E 's/^\(EngineCore[^)]*\) //' | sort -u | head -8
[ $fail = 0 ] && echo "PASS: README quick start ($pkg, $MODEL)"
exit $fail
