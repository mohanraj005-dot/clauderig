import contextlib
import io
import json
import os
import tempfile
import unittest

import first_call_context as fcc


def assistant(day, tokens, model="claude-haiku-5-5", version="2.1.293"):
    return {
        "type": "assistant",
        "timestamp": f"{day}T08:00:00Z",
        "version": version,
        "message": {
            "model": model,
            "content": "PRIVATE-PROMPT-TEXT",
            "usage": {
                "input_tokens": 2,
                "cache_creation_input_tokens": tokens - 12,
                "cache_read_input_tokens": 10,
            },
        },
    }


class FirstCallContextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def log(self, relative, *rows):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            for row in rows:
                handle.write((row if isinstance(row, str) else json.dumps(row)) + "\n")

    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = fcc.main(["--root", self.root, *args])
        return code, out.getvalue()

    def test_uses_only_first_call_and_all_three_fields(self):
        self.log("p/a.jsonl", {"type": "user"}, "not json",
                 assistant("2026-10-08", 1000), assistant("2026-10-08", 9999))
        self.assertEqual([s["tokens"] for s in fcc.load_sessions(self.root)], [1000])

    def test_subagents_excluded_unless_requested(self):
        self.log("p/a.jsonl", assistant("2026-10-08", 1000))
        self.log("p/a/subagents/b.jsonl", assistant("2026-10-08", 2000))
        self.assertEqual(len(fcc.load_sessions(self.root)), 1)
        self.assertEqual(len(fcc.load_sessions(self.root, include_subagents=True)), 2)

    def test_filters(self):
        self.log("job/a.jsonl", assistant("2026-10-08", 1000))
        self.log("other/b.jsonl", assistant("2026-10-08", 2000, model="claude-opus-5-5"))
        self.log("other/c.jsonl", assistant("2026-10-08", 3000, version="2.1.300"))
        self.log("other/d.jsonl", assistant("2026-10-08", 4000, model="<synthetic>"))
        self.assertEqual(len(fcc.load_sessions(self.root)), 3)
        self.assertEqual(len(fcc.load_sessions(self.root, model="haiku")), 2)
        self.assertEqual(len(fcc.load_sessions(self.root, version="2.1.293")), 2)
        self.assertEqual(len(fcc.load_sessions(self.root, path_contains="job")), 1)

    def test_compare_reports_median_change_and_no_content(self):
        self.log("p/a.jsonl", assistant("2026-10-08", 1000))
        self.log("p/b.jsonl", assistant("2026-10-13", 700))
        code, output = self.run_cli("--before", "2026-10-08:2026-10-11",
                                    "--after", "2026-10-13:2026-10-21")
        self.assertEqual(code, 0)
        self.assertIn("-300 tokens (-30.0%)", output)
        self.assertNotIn("PRIVATE-PROMPT-TEXT", output)
        self.assertNotIn(self.root, output)

    def test_empty_window_is_reported(self):
        self.log("p/a.jsonl", assistant("2026-10-08", 1000))
        code, output = self.run_cli("--before", "2026-10-08:2026-10-11",
                                    "--after", "2026-10-13:2026-10-21")
        self.assertEqual(code, 1)
        self.assertIn("after window", output)


if __name__ == "__main__":
    unittest.main()
