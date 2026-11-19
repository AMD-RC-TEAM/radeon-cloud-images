#!/usr/bin/env python3
"""Offline tests for catalog_sync's "move first, then cover" rule (a2 11-19).

A fake Admin enforces the real duplicate rule: two catalog rows may not carry the same digest (adopt answers
"remote digest is already used by another catalog image", create answers "image name or source_ref already exists").
Run: python3 -I tools/test_catalog_sync.py
"""
import importlib.util, json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("catalog_sync", os.path.join(HERE, "catalog_sync.py"))
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

REPO = "reg/rc/base"
OLD, PREV, NEW = REPO + "@sha256:" + "a" * 64, REPO + "@sha256:" + "b" * 64, REPO + "@sha256:" + "c" * 64


class FakeAdmin:
    def __init__(self, images, templates, remote):
        self.images = {r["id"]: dict(r) for r in images}
        self.templates = templates
        self.remote = remote        # source_ref -> digest ref the alias resolves to now
        self.next_id = 900
        self.calls = []

    def _dup(self, image, skip):
        return any(r["image"] == image for i, r in self.images.items() if i != skip)

    def call(self, method, path, body=None):
        self.calls.append((method, path))
        if method == "GET" and path == "/api/admin/images":
            return 200, {"images": [dict(r) for r in self.images.values()]}
        if method == "GET" and path == "/api/admin/templates":
            return 200, {"templates": self.templates}
        if method == "POST" and path == "/api/admin/images":
            if self._dup(body["source_ref"], None) or any(r["name"].lower() == body["name"].lower() for r in self.images.values()):
                return 409, {"detail": "image name or source_ref already exists"}
            self.next_id += 1
            row = {"id": self.next_id, "name": body["name"], "image": body["source_ref"], "source_ref": body["source_ref"],
                   "enabled": body["enabled"], "picker_visible": body["picker_visible"], "harbor_status": "ready"}
            self.images[row["id"]] = row
            return 201, row
        parts = path.split("/")
        if method == "POST" and len(parts) >= 6 and parts[5] == "harbor":
            rid = int(parts[4]); row = self.images[rid]
            want = self.remote.get(row["source_ref"], row["image"])
            if len(parts) == 6:
                row["harbor_status"] = "drift" if want != row["image"] else "ready"
                row["harbor_remote_digest"] = want
                return 200, dict(row)
            if self._dup(want, rid):
                return 409, {"detail": "remote digest is already used by another catalog image"}
            row["image"] = want; row["harbor_status"] = "ready"
            return 200, dict(row)
        return 404, {"detail": "not found"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for name in ("STATUS", "GT_PASSED", "PROD_HOLD", "PROD_ADOPTED", "MANUAL_SEEN"):
            setattr(cs, name, os.path.join(self.tmp, name))
        json.dump({"base": {"digest": NEW.split("@", 1)[1]}}, open(cs.GT_PASSED, "w"))
        self.stable = {"id": 238, "name": "Base", "image": OLD, "source_ref": REPO + ":rc-current", "enabled": True,
                       "picker_visible": True, "harbor_status": "ready"}
        self.prev = {"id": 249, "name": "Base (previous)", "image": PREV, "source_ref": REPO + ":rc-prev", "enabled": True,
                     "picker_visible": False, "harbor_status": "ready"}

    def run_sync(self, admin):
        cs.Session = lambda site: type("S", (), {"expires": None, "call": staticmethod(admin.call)})()
        return cs.sync_site("china", {"base": 238}, False)

    def covering(self, admin, image):
        return [r["id"] for r in admin.images.values() if r["image"] == image and r["enabled"]]


class MoveFirstThenCover(Base):
    def test_disabled_templates_only_moves_then_pins(self):
        # rc-prev already points at an older digest, so the previous row cannot take OLD; all pinning templates disabled
        admin = FakeAdmin([self.stable, self.prev], [{"id": 5810, "image": OLD, "enabled": False}],
                          {REPO + ":rc-current": NEW, REPO + ":rc-prev": PREV})
        self.run_sync(admin)
        self.assertEqual(admin.images[238]["image"], NEW, "stable row moved to the new digest")
        pinned = [r for r in admin.images.values() if r["image"] == OLD]
        self.assertEqual(len(pinned), 1, "exactly one row carries the old digest afterwards")
        self.assertTrue(pinned[0]["enabled"]); self.assertFalse(pinned[0]["picker_visible"])
        self.assertIn("(pinned ", pinned[0]["name"])

    def test_enabled_template_keeps_the_old_rule(self):
        admin = FakeAdmin([self.stable, self.prev], [{"id": 5810, "image": OLD, "enabled": False},
                                                     {"id": 6000, "image": OLD, "enabled": True}],
                          {REPO + ":rc-current": NEW, REPO + ":rc-prev": PREV})
        rc = self.run_sync(admin)
        self.assertEqual(rc, 1)
        self.assertEqual(admin.images[238]["image"], OLD, "stable row must not move")
        self.assertEqual(len(admin.images), 2, "no row created")

    def test_previous_row_takes_the_freed_digest(self):
        # rc-prev resolves to OLD (the base case on China): after the move the previous row adopts OLD; no pinned row
        admin = FakeAdmin([self.stable, self.prev], [{"id": 5810, "image": OLD, "enabled": False}],
                          {REPO + ":rc-current": NEW, REPO + ":rc-prev": OLD})
        self.run_sync(admin)
        self.assertEqual(admin.images[238]["image"], NEW)
        self.assertEqual(self.covering(admin, OLD), [249], "the previous row covers the old digest")
        self.assertFalse(any("(pinned " in r["name"] for r in admin.images.values()))

    def test_covered_digest_moves_without_new_rows(self):
        other = {"id": 300, "name": "Base copy", "image": OLD, "source_ref": "x", "enabled": True, "picker_visible": False}
        # the fake allows this pre-existing duplicate only to model "another row already covers it"
        admin = FakeAdmin([self.stable, self.prev, other], [{"id": 6000, "image": OLD, "enabled": True}],
                          {REPO + ":rc-current": NEW, REPO + ":rc-prev": PREV})
        self.run_sync(admin)
        self.assertEqual(admin.images[238]["image"], NEW)
        self.assertEqual(len(admin.images), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
