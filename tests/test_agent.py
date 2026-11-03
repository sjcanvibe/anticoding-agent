#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Zero-dependency unit test suite for AntiCoding Agent."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import anticoding_agent as agent


class TestAntiCodingAgent(unittest.TestCase):
    def test_sandbox_path_jail(self):
        safe, _, _ = agent.is_safe_path("README.md")
        self.assertTrue(safe)
        unsafe, _, _ = agent.is_safe_path("../../etc/passwd")
        self.assertFalse(unsafe)

    def test_sandbox_command_filter(self):
        self.assertTrue(agent.is_safe_command("ls -la")[0])
        self.assertFalse(agent.is_safe_command("sudo rm -rf /")[0])
        self.assertFalse(agent.is_safe_command("rm -r -f /")[0])
        self.assertFalse(agent.is_safe_command("rm --no-preserve-root -rf /")[0])

    def test_fallback_tool_call_parser(self):
        raw = 'Thinking...\n<tool_call>{"name": "list_dir", "arguments": {"path": "."}}</tool_call>'
        cleaned, tcs = agent.extract_fallback_tool_calls(raw)
        self.assertEqual(cleaned, "Thinking...")
        self.assertEqual(len(tcs), 1)
        self.assertEqual(tcs[0]["function"]["name"], "list_dir")

    def test_cli_arg_parser(self):
        args = agent.parse_cli_args(["-p", "fix bug", "--model", "gpt-4.1", "--ask"])
        self.assertEqual(args.prompt, "fix bug")
        self.assertEqual(args.model, "gpt-4.1")
        self.assertTrue(args.ask)

    def test_repo_map_generation(self):
        rmap = agent.generate_repo_map()
        self.assertIn("def run_agent", rmap)


if __name__ == "__main__":
    unittest.main()
