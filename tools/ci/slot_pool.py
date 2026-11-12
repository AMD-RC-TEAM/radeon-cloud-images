#!/usr/bin/env python3
# Vendored from AMD-RC-TEAM/Radeon-Cloud-Internal ops/ci/slot_pool.py @ 499f6b60 (same lease protocol as RCI CI). Keep in sync.
"""CAS-protected CI slot leases. Never steal an expired or abandoned slot."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time

CONFIG = Path(__file__).with_name("slots.json")
POOL_LABEL = "amd-oneclick/ci-slot"
PHASE = "amd-oneclick/ci-phase"
PREFIX = "radeon-ci-"
CONTRACT_ANNOTATION = "amd-oneclick/ci-release-contract"


class SlotError(RuntimeError):
    pass


def config():
    document = json.loads(CONFIG.read_text(encoding="utf-8"))
    slots = document["slots"]
    if len({s["control_namespace"] for s in slots}) != len(slots):
        raise SlotError("duplicate slot namespace")
    for slot in slots:
        if (
            slot["control_namespace"] != "oneclick-" + slot["stack_id"]
            or slot["runtime_namespace"] != slot["control_namespace"] + "-runtime"
            or not slot["stack_id"].startswith("j")
        ):
            raise SlotError("invalid slot identity")
    return document


def owner():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if not repo or not run.isdigit() or not attempt.isdigit():
        raise SlotError("GitHub repository, run ID and attempt are required")
    return f"{repo}:{run}:{attempt}"


class Pool:
    def __init__(self, kubeconfig=None):
        self.config = config()
        self.prefix = ["kubectl"]
        if kubeconfig:
            self.prefix += ["--kubeconfig", kubeconfig]

    def run(self, *args, data=None, check=True):
        # Retrying a CAS patch is safe: patch() leads with `test` operations on
        # resourceVersion and holderIdentity, so a retry after a lost reply
        # fails its own test rather than overwriting a newer owner. Callers
        # treat a False return as "claim uncertain" and re-read before acting.
        # A bare kubectl timeout used to escape this loop entirely, which is
        # the most likely apiserver failure and the one worth retrying most.
        attempts = 3 if args[0] in ("get", "patch") else 1
        p, timeout = None, None
        for attempt in range(attempts):
            try:
                p, timeout = subprocess.run(
                    [*self.prefix, "-n", self.config["lease_namespace"], *args],
                    input=json.dumps(data) if data is not None else None,
                    text=True, capture_output=True, timeout=60,
                ), None
            except subprocess.TimeoutExpired as exc:
                p, timeout = None, exc
            if p is not None and p.returncode == 0:
                break
            if attempt == attempts - 1:
                break
            time.sleep(attempt + 1)
        if timeout is not None:
            raise SlotError(f"slot API call timed out after {attempts} attempt(s): {timeout}")
        if check and p.returncode:
            raise SlotError(p.stderr.strip() or "slot API operation failed")
        return p

    def get(self, slot):
        return json.loads(self.run("get", "lease", PREFIX + slot["id"], "-o", "json").stdout)

    def patch(self, slot, document, holder, phase):
        operations = [
            {"op": "test", "path": "/metadata/resourceVersion", "value": document["metadata"]["resourceVersion"]},
            {"op": "test", "path": "/spec/holderIdentity", "value": document["spec"]["holderIdentity"]},
            {"op": "replace", "path": "/spec/holderIdentity", "value": holder},
            {"op": "add", "path": "/metadata/annotations/amd-oneclick~1ci-phase", "value": phase},
        ]
        return self.run(
            "patch", "lease", PREFIX + slot["id"], "--type=json", "-p",
            json.dumps(operations), check=False,
        ).returncode == 0

    def acquire(self, identity, namespace="", wait_seconds=7200):
        slots = self.config["slots"]
        if namespace:
            slots = [s for s in slots if s["control_namespace"] == namespace]
            if not slots:
                raise SlotError("requested namespace is not in the CI pool")
        deadline = time.monotonic() + wait_seconds
        while True:
            # Find existing ownership before an earlier slot can be reused.
            if self.find(identity):
                return self.require(identity, namespace, phases=("allocated",))
            for slot in slots:
                live = self.get(slot)
                held = live["spec"].get("holderIdentity", "")
                phase = live["metadata"].get("annotations", {}).get(PHASE)
                if held == identity:
                    if phase == "allocated":
                        return slot
                    raise SlotError(f"run already owns an unsafe/in-use slot ({phase})")
                if not held and phase == "available":
                    if self.patch(slot, live, identity, "allocated"):
                        return slot
                    # A lost HTTP response is not proof the patch failed.
                    # Never claim another slot while this claim is ambiguous.
                    after = self.get(slot)
                    observed = after["spec"].get("holderIdentity", "")
                    if observed == identity:
                        return slot
                    if not observed:
                        raise SlotError("claim result uncertain; refusing to claim a second slot")
            if time.monotonic() >= deadline:
                raise SlotError("no CI slot became available; no existing lease was stolen")
            print("All CI slots busy or quarantined; waiting.", flush=True)
            time.sleep(min(20, max(0, deadline - time.monotonic())))

    def find(self, identity):
        matches = [s for s in self.config["slots"] if self.get(s)["spec"].get("holderIdentity") == identity]
        if len(matches) > 1:
            raise SlotError("run owns multiple slots")
        return matches[0] if matches else None

    def transition(self, identity, phase):
        slot = self.find(identity)
        if slot is None:
            if phase == "release":
                return
            raise SlotError("run has no slot lease")
        live = self.get(slot)
        if live["spec"].get("holderIdentity") != identity:
            raise SlotError("slot owner changed")
        previous = live["metadata"]["annotations"][PHASE]
        if phase == "release":
            if previous not in ("allocated", "ready"):
                raise SlotError(f"slot remains quarantined/unsafe ({previous}); refusing release")
            holder, phase = "", "available"
        else:
            holder = identity
        if not self.patch(slot, live, holder, phase):
            # The first CAS may have committed before its reply was lost.
            # Retrying that exact CAS then fails the resourceVersion test.
            # Confirm the requested state, without repeating the write using
            # a newer version or accidentally overwriting a different owner.
            after = self.get(slot)
            if (after["spec"].get("holderIdentity") != holder
                    or after["metadata"].get("annotations", {}).get(PHASE) != phase):
                raise SlotError("slot changed concurrently; refusing state update")

    def require(self, identity, namespace="", phases=("allocated", "ready", "deploying")):
        slot = self.find(identity)
        if not slot or (namespace and slot["control_namespace"] != namespace):
            raise SlotError("this run attempt does not own the selected slot; rerun ALL jobs to reacquire capacity")
        live = self.get(slot)
        if live["spec"].get("holderIdentity") != identity or live["metadata"]["annotations"][PHASE] not in phases:
            raise SlotError("run owns an unsafe/in-use slot; refusing live work")
        return slot

    def finish(self, identity, cleanup_result, rollback_result, expect_namespace=""):
        slot = self.find(identity)
        if slot and expect_namespace and slot["control_namespace"] != expect_namespace:
            raise SlotError(f"this attempt does not own the allocated namespace {expect_namespace}")
        if not slot:
            # A run that never claimed anything has nothing to release. But when
            # the caller knows this run was allocated a slot, holding no lease
            # means a partial re-run bumped GITHUB_RUN_ATTEMPT past the holder:
            # cleanup skipped its real work and this release would have reported
            # success while instances and the lease leak. Fail loudly instead.
            if expect_namespace:
                raise SlotError(
                    f"this run was allocated {expect_namespace} but this attempt holds no "
                    "lease, so cleanup could not have run; instances may still be live. "
                    "Re-run ALL jobs to reacquire capacity, or recover the slot with "
                    "ops/ci/reap_slot.py once the older attempt is confirmed finished."
                )
            return
        phase = self.get(slot)["metadata"]["annotations"][PHASE]
        if cleanup_result == "success" and rollback_result in ("success", "skipped") and phase in ("allocated", "ready"):
            self.transition(identity, "release")
            print(f"Released {slot['id']} after confirmed cleanup.")
        else:
            self.transition(identity, "quarantined")
            raise SlotError(f"{slot['id']} quarantined: cleanup/deployment/rollback not proven safe")


def emit(slot):
    values = {"acquired": "true" if slot else "false", "namespace": ""}
    if slot:
        values.update(slot)
        values["namespace"] = slot["control_namespace"]
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.writelines(f"{key}={value}\n" for key, value in values.items())
    print(json.dumps(values))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kubeconfig", default=os.environ.get("KUBECONFIG"))
    sub = p.add_subparsers(dest="command", required=True)
    acquire = sub.add_parser("acquire")
    acquire.add_argument("--namespace", default="")
    acquire.add_argument("--wait-seconds", type=int, default=7200)
    # --expect-namespace is this run's allocated namespace. Job outputs survive
    # across attempts, so it is set even when the lease is held by an earlier
    # attempt -- which is exactly the partial-re-run case that must not pass.
    find = sub.add_parser("find")
    find.add_argument("--expect-namespace", default="")
    verify = sub.add_parser("assert")
    verify.add_argument("--namespace", default=os.environ.get("SLOT_NAMESPACE", ""))
    finish = sub.add_parser("finish")
    finish.add_argument("--cleanup-result", required=True)
    finish.add_argument("--rollback-result", default="skipped")
    finish.add_argument("--expect-namespace", default="")
    for name in ("deploying", "ready", "quarantined", "release"):
        sub.add_parser(name)
    args = p.parse_args()
    try:
        pool, identity = Pool(args.kubeconfig), owner()
        if args.command == "acquire":
            emit(pool.acquire(identity, args.namespace, args.wait_seconds))
        elif args.command == "find":
            slot = pool.find(identity)
            # Emit first so downstream `if:` guards and logs still see the
            # result, then fail: a cleanup job that finds no lease for a run
            # that was allocated one has skipped its real work.
            emit(slot)
            if not slot and args.expect_namespace:
                print(
                    f"::error::this run was allocated {args.expect_namespace} but this "
                    "attempt holds no lease; cleanup cannot reclaim instances. Re-run "
                    "ALL jobs to reacquire capacity."
                )
                return 1
        elif args.command == "assert":
            pool.require(identity, args.namespace)
        elif args.command == "finish":
            pool.finish(
                identity, args.cleanup_result, args.rollback_result, args.expect_namespace
            )
        else:
            pool.transition(identity, args.command)
    except (SlotError, subprocess.SubprocessError) as exc:
        print(f"::error::{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
