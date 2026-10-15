import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import main as agent


class SkillTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.project = Path(self.temp_dir.name)
        self.skills_dir = self.project / ".claude" / "skills"

    def write_skill(self, folder, content):
        path = self.skills_dir / folder / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_agent(self, messages, responses, prompt="Which skill deploys the service?"):
        client = Mock()

        def complete(**kwargs):
            messages.append([dict(message) for message in kwargs["messages"]])
            return SimpleNamespace(choices=[SimpleNamespace(message=responses.pop(0))])

        client.chat.completions.create.side_effect = complete
        with (
            contextlib.chdir(self.project),
            patch.object(agent, "API_KEY", "test-key"),
            patch.object(agent, "OpenAI", return_value=client),
            patch("sys.argv", ["agent", "-p", prompt]),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            agent.main()
        return output.getvalue()


class SkillAdvertisingTests(SkillTestCase):
    def test_missing_or_empty_skills_directory(self):
        self.assertEqual(agent.build_skill_system_prompt(self.skills_dir), "")
        self.skills_dir.mkdir(parents=True)
        self.assertEqual(agent.build_skill_system_prompt(self.skills_dir), "")

    def test_advertises_all_metadata_in_order_without_bodies(self):
        self.write_skill("grape", "---\nname: grape\ndescription: Runs tests.\n---\nSECRET_GRAPE_BODY")
        self.write_skill("apple", "---\nname: apple\ndescription: Deploys a service.\n---\nSECRET_APPLE_BODY")
        self.assertEqual(
            agent.build_skill_system_prompt(self.skills_dir),
            "You have access to the following skills:\n\n"
            "- apple: Deploys a service.\n- grape: Runs tests.",
        )

    def test_yaml_quotes_colons_and_multiline_descriptions(self):
        self.write_skill("quoted", '---\nname: quoted\ndescription: "Review: code and tests."\n---\nBody')
        self.write_skill("folded", "---\nname: folded\ndescription: >-\n  Run the tests\n  and report failures.\n---\nBody")
        self.write_skill("literal", "---\nname: literal\ndescription: |\n  First line.\n  Second line.\n---\nBody")
        prompt = agent.build_skill_system_prompt(self.skills_dir)
        self.assertIn("- quoted: Review: code and tests.", prompt)
        self.assertIn("- folded: Run the tests and report failures.", prompt)
        self.assertIn("- literal: First line. Second line.", prompt)

    def test_invalid_skills_do_not_hide_valid_skills(self):
        invalid_skills = [
            "No frontmatter",
            "---\nname: unclosed\ndescription: Missing closing marker",
            "---\nname: [invalid\n---\nBody",
            "---\n- a list\n---\nBody",
            "---\nname: missing-description\n---\nBody",
            "---\nname: wrong-type\ndescription: 123\n---\nBody",
            "---\nname: empty\ndescription: ''\n---\nBody",
        ]
        for index, content in enumerate(invalid_skills):
            self.write_skill(f"invalid-{index}", content)
        self.write_skill("valid", "---\nname: valid\ndescription: Valid skill.\n---\nBody")
        self.assertEqual(
            agent.build_skill_system_prompt(self.skills_dir),
            "You have access to the following skills:\n\n- valid: Valid skill.",
        )

    def test_folder_name_fallback_and_utf8_bom(self):
        self.write_skill("fallback", "\ufeff---\r\ndescription: Folder name fallback.\r\n---\r\nBody")
        self.assertIn("- fallback: Folder name fallback.", agent.build_skill_system_prompt(self.skills_dir))

    def test_discovers_only_immediate_skill_directories(self):
        self.write_skill("nested/hidden", "---\nname: hidden\ndescription: Nested skill.\n---\nBody")
        self.skills_dir.joinpath("SKILL.md").write_text("---\nname: root\ndescription: Root file.\n---", encoding="utf-8")
        self.skills_dir.joinpath("incomplete").mkdir()
        self.assertEqual(agent.build_skill_system_prompt(self.skills_dir), "")

    def test_system_message_precedes_user_and_survives_agent_loop(self):
        self.write_skill("apple", "---\nname: apple\ndescription: Deploys the service.\n---\nSECRET_BODY")
        target = self.project / "context.txt"
        target.write_text("Tool context", encoding="utf-8")
        tool_call = SimpleNamespace(id="read-1", function=SimpleNamespace(name="Read", arguments='{"file_path": "context.txt"}'))
        tool_message = Mock(tool_calls=[tool_call])
        tool_message.model_dump.return_value = {"role": "assistant", "tool_calls": [{"id": "read-1", "type": "function", "function": {"name": "Read", "arguments": tool_call.function.arguments}}]}
        final_message = Mock(tool_calls=None, content="apple")
        final_message.model_dump.return_value = {"role": "assistant", "content": "apple"}
        requests = []
        self.assertEqual(self.run_agent(requests, [tool_message, final_message]), "apple\n")
        self.assertEqual([item["role"] for item in requests[0]], ["system", "user"])
        self.assertIn("- apple: Deploys the service.", requests[0][0]["content"])
        self.assertNotIn("SECRET_BODY", requests[0][0]["content"])
        self.assertEqual(requests[1][0], requests[0][0])
        self.assertEqual(requests[1][-1], {"role": "tool", "tool_call_id": "read-1", "content": "Tool context"})

    def test_no_skills_preserves_user_only_request(self):
        final_message = Mock(tool_calls=None, content="No skills available")
        final_message.model_dump.return_value = {"role": "assistant", "content": final_message.content}
        requests = []
        self.run_agent(requests, [final_message])
        self.assertEqual([item["role"] for item in requests[0]], ["user"])


class SkillInvocationTests(SkillTestCase):
    def test_plain_prompt_is_unchanged(self):
        for prompt in ["Explain this code", "Use /apple", "", "  /apple"]:
            with self.subTest(prompt=prompt):
                self.assertEqual(agent.resolve_skill_prompt(prompt, self.skills_dir), prompt)

    def test_invocation_loads_only_selected_body(self):
        body = "Respond with exactly one word: blueberry\n\nDo not add formatting."
        self.write_skill("apple", f"---\nname: apple\ndescription: Deploys apple.\n---\n\n{body}\n")
        self.write_skill("grape", "---\nname: grape\ndescription: Runs tests.\n---\nRespond with raspberry.")
        self.assertEqual(agent.resolve_skill_prompt("/apple", self.skills_dir), body)

    def test_body_keeps_markdown_separators_and_placeholders(self):
        body = "# Instructions\n\n---\n\nUse $ARGUMENTS and $1."
        self.write_skill("review-code", f"\ufeff---\r\nname: review-code\r\ndescription: Reviews code.\r\n---\r\n{body}")
        self.assertEqual(agent.resolve_skill_prompt("/review-code", self.skills_dir), body)

    def test_unknown_or_invalid_skill_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown skill.*missing"):
            agent.resolve_skill_prompt("/missing", self.skills_dir)
        for prompt in ["/", "/..", "/../secret", "/nested/skill", "/nested\\skill", "/C:secret"]:
            with self.subTest(prompt=prompt), self.assertRaisesRegex(ValueError, "Invalid skill name"):
                agent.resolve_skill_prompt(prompt, self.skills_dir)

    def test_missing_frontmatter_markers_are_rejected(self):
        for content in ["No frontmatter", "---\nname: apple\nBody without closing marker"]:
            with self.subTest(content=content):
                self.write_skill("apple", content)
                with self.assertRaisesRegex(ValueError, "frontmatter"):
                    agent.resolve_skill_prompt("/apple", self.skills_dir)

    def test_main_sends_selected_body_and_retains_catalog(self):
        self.write_skill("apple", "---\nname: apple\ndescription: Deploys apple.\n---\nRespond with blueberry.")
        self.write_skill("grape", "---\nname: grape\ndescription: Runs tests.\n---\nRespond with raspberry.")
        final_message = Mock(tool_calls=None, content="blueberry")
        final_message.model_dump.return_value = {"role": "assistant", "content": "blueberry"}
        requests = []
        self.assertEqual(self.run_agent(requests, [final_message], prompt="/apple"), "blueberry\n")
        self.assertEqual([item["role"] for item in requests[0]], ["system", "user"])
        self.assertIn("- apple: Deploys apple.", requests[0][0]["content"])
        self.assertIn("- grape: Runs tests.", requests[0][0]["content"])
        self.assertEqual(requests[0][1]["content"], "Respond with blueberry.")
        self.assertNotIn("raspberry", str(requests[0]))

    def test_main_rejects_unknown_skill_before_creating_client(self):
        with (
            contextlib.chdir(self.project),
            patch("sys.argv", ["agent", "-p", "/missing"]),
            patch.object(agent, "OpenAI") as client,
            contextlib.redirect_stderr(io.StringIO()) as error_output,
            self.assertRaises(SystemExit) as error,
        ):
            agent.main()
        self.assertEqual(error.exception.code, 2)
        self.assertIn("Unknown skill", error_output.getvalue())
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
