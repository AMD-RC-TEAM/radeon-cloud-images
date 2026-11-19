#!/usr/bin/env python3
"""FROM parsing and Harbor rewrite for tools/release.py (multi-stage and single-stage)."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import release  # noqa: E402


class FromParse(unittest.TestCase):
    def test_single_from_no_as(self):
        df = "FROM docker.io/vllm/vllm-openai-rocm:v0.33.0-rocm72@sha256:" + "a" * 64 + "\n"
        got = release.from_entries(df)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["registry"], "docker.io")
        self.assertEqual(got[0]["repo"], "vllm/vllm-openai-rocm")
        self.assertTrue(got[0]["harbor_ref"].startswith(release.PULL + "/"))
        self.assertIn(got[0]["digest"], got[0]["harbor_ref"])

    def test_as_name_and_second_from(self):
        d1, d2 = "b" * 64, "c" * 64
        df = (
            f"FROM docker.io/rocm/pytorch:tag@sha256:{d1} AS dsv41-build\n"
            f"FROM ghcr.io/niko1221/strata:0.2.13-rocm-gfx110x@sha256:{d2}\n"
        )
        got = release.from_entries(df)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["registry"], "docker.io")
        self.assertEqual(got[0]["repo"], "rocm/pytorch")
        self.assertEqual(got[1]["registry"], "ghcr.io")
        self.assertEqual(got[1]["repo"], "niko1221/strata")
        rewritten = release.rewrite_froms(df, got)
        self.assertNotIn("FROM docker.io/", rewritten)
        self.assertNotIn("FROM ghcr.io/", rewritten)
        self.assertIn("AS dsv41-build", rewritten)
        self.assertIn(release.PULL + f"/rocm/pytorch@sha256:{d1}", rewritten)
        self.assertIn(release.PULL + f"/ghcr.io/niko1221/strata@sha256:{d2}", rewritten)

    def test_harbor_from_refused(self):
        df = "FROM 10.5.10.12:1808/radeon-cloud-global/rocm/pytorch:t@sha256:" + "d" * 64 + "\n"
        with self.assertRaises(SystemExit) as e:
            release.from_entries(df)
        self.assertIn("Harbor", str(e.exception))

    def test_every_image_parses(self):
        images = sorted(p.name for p in (ROOT / "images").iterdir() if (p / "Dockerfile").is_file())
        self.assertTrue(images)
        for name in images:
            m = release.parse(name)
            self.assertTrue(m["froms"], name)
            for frm in m["froms"]:
                self.assertIn(frm["harbor_ref"], m["build_dockerfile"], name)
                self.assertNotIn(frm["ref"], m["build_dockerfile"], name)


class StrataRdna3Dockerfile(unittest.TestCase):
    def test_both_froms_rewritten(self):
        m = release.parse("strata-rdna3")
        self.assertEqual(len(m["froms"]), 2)
        self.assertEqual(m["froms"][0]["registry"], "docker.io")
        self.assertEqual(m["froms"][1]["registry"], "ghcr.io")
        df = m["build_dockerfile"]
        self.assertIn("AS dsv41-build", df)
        self.assertNotIn("FROM docker.io/", df)
        self.assertNotIn("FROM ghcr.io/", df)
        self.assertIn(release.PULL + "/rocm/pytorch@", df)
        self.assertIn(release.PULL + "/ghcr.io/niko1221/strata@", df)


if __name__ == "__main__":
    unittest.main()
