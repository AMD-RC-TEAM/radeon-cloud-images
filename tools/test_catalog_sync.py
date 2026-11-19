#!/usr/bin/env python3
"""Offline tests: catalog_sync never moves a catalog row that a template references or pins (11-19 incident).

The fake Admin behaves like the real one where it matters:
  - two rows may not carry the same digest (adopt: "remote digest is already used by another catalog image");
  - adopt rewrites every template that pinned the row's old digest or source_ref to "production-<row>".
Every test checks that no template changed.
Run: python3 -I tools/test_catalog_sync.py
"""
import copy, importlib.util, json, os, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("catalog_sync", os.path.join(HERE, "catalog_sync.py"))
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

REPO = "reg/rc/base"
OLD, PREV, NEW = (REPO + "@sha256:" + c * 64 for c in "abc")


class FakeAdmin:
    def __init__(self, images, templates, remote):
        self.images = {r["id"]: dict(r) for r in images}
        self.templates = [dict(t) for t in templates]
        self.remote = remote        # source_ref -> digest ref the alias resolves to now

    def call(self, method, path, body=None):
        if method == "GET" and path == "/api/admin/images":
            return 200, {"images": [dict(r) for r in self.images.values()]}
        if method == "GET" and path == "/api/admin/templates":
            return 200, {"templates": [dict(t) for t in self.templates]}
        if method == "POST" and path == "/api/admin/images":
            return 409, {"detail": "image name or source_ref already exists"}
        parts = path.split("/")
        if method == "POST" and len(parts) >= 6 and parts[5] == "harbor":
            rid = int(parts[4]); row = self.images[rid]
            want = self.remote.get(row["source_ref"], row["image"])
            if len(parts) == 6:
                row["harbor_status"] = "drift" if want != row["image"] else "ready"
                row["harbor_remote_digest"] = want
                return 200, dict(row)
            if any(r["image"] == want for i, r in self.images.items() if i != rid):
                return 409, {"detail": "remote digest is already used by another catalog image"}
            old = {row["image"], row["source_ref"]}
            row["image"] = want; row["harbor_status"] = "ready"
            for t in self.templates:          # what Admin's adopt does (previous_references)
                if t["image"] in old:
                    t["image"] = f"production-{rid}"
            return 200, dict(row)
        return 404, {"detail": "not found"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for name in ("STATUS", "GT_PASSED", "PROD_HOLD", "PROD_ADOPTED", "MANUAL_SEEN"):
            setattr(cs, name, os.path.join(self.tmp, name))
        with open(cs.GT_PASSED, "w") as f:
            json.dump({"base": {"digest": NEW.split("@", 1)[1]}}, f)
        self.stable = {"id": 238, "name": "Base", "image": OLD, "source_ref": REPO + ":rc-current", "enabled": True,
                       "picker_visible": True, "harbor_status": "ready"}
        self.prev = {"id": 249, "name": "Base (previous)", "image": PREV, "source_ref": REPO + ":rc-prev", "enabled": True,
                     "picker_visible": False, "harbor_status": "ready"}

    def run_sync(self, admin):
        self.templates_before = copy.deepcopy(admin.templates)
        cs.Session = lambda site: type("S", (), {"expires": None, "call": staticmethod(admin.call)})()
        rc = cs.sync_site("china", {"base": 238}, False)
        self.assertEqual(admin.templates, self.templates_before, "no template may change")
        return rc


class RefuseAnyPin(Base):
    def test_disabled_template_pinning_the_digest_refuses(self):
        admin = FakeAdmin([self.stable, self.prev], [{"id": 5810, "image": OLD, "enabled": False}],
                          {REPO + ":rc-current": NEW, REPO + ":rc-prev": OLD})
        self.assertEqual(self.run_sync(admin), 1)
        self.assertEqual(admin.images[238]["image"], OLD)

    def test_enabled_template_pinning_the_digest_refuses(self):
        admin = FakeAdmin([self.stable, self.prev], [{"id": 6000, "image": OLD, "enabled": True}],
                          {REPO + ":rc-current": NEW, REPO + ":rc-prev": PREV})
        self.assertEqual(self.run_sync(admin), 1)
        self.assertEqual(admin.images[238]["image"], OLD)

    def test_covered_digest_still_refuses(self):
        other = {"id": 300, "name": "Base copy", "image": OLD, "source_ref": "x", "enabled": True, "picker_visible": False}
        admin = FakeAdmin([self.stable, self.prev, other], [{"id": 6000, "image": OLD, "enabled": True}],
                          {REPO + ":rc-current": NEW, REPO + ":rc-prev": PREV})
        self.assertEqual(self.run_sync(admin), 1)
        self.assertEqual(admin.images[238]["image"], OLD)

    def test_template_on_the_row_itself_refuses(self):
        admin = FakeAdmin([self.stable, self.prev], [{"id": 7000, "image": "production-238", "enabled": True}],
                          {REPO + ":rc-current": NEW, REPO + ":rc-prev": PREV})
        self.assertEqual(self.run_sync(admin), 1)
        self.assertEqual(admin.images[238]["image"], OLD)

    def test_no_template_moves_and_previous_row_follows(self):
        admin = FakeAdmin([self.stable, self.prev], [{"id": 8000, "image": "reg/other@sha256:" + "d" * 64, "enabled": True}],
                          {REPO + ":rc-current": NEW, REPO + ":rc-prev": OLD})
        self.run_sync(admin)
        self.assertEqual(admin.images[238]["image"], NEW)
        self.assertEqual(admin.images[249]["image"], OLD, "the previous row follows rc-prev once the digest is free")

    def test_previous_row_pinned_by_a_template_is_left_alone(self):
        admin = FakeAdmin([self.stable, self.prev], [{"id": 9000, "image": PREV, "enabled": False}],
                          {REPO + ":rc-current": NEW, REPO + ":rc-prev": OLD})
        self.run_sync(admin)
        self.assertEqual(admin.images[238]["image"], NEW)
        self.assertEqual(admin.images[249]["image"], PREV, "adopting it would rewrite template 9000")


if __name__ == "__main__":
    unittest.main(verbosity=2)
