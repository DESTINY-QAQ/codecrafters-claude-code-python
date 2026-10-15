import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import main as agent


class SkillAdvertisingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.project = Path(self.temp_dir.name)
        self.skills_dir = self.project / ".claude" / "skills"

    def write_skill(self, folder, content):
        path = self.skills_dir / folder / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

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

    def run_agent(self, messages, responses):
        client = Mock()

        def complete(**kwargs):
            messages.append([dict(message) for message in kwargs["messages"]])
            return SimpleNamespace(choices=[SimpleNamespace(message=responses.pop(0))])

        client.chat.completions.create.side_effect = complete
        previous_dir = Path.cwd()
        try:
            os.chdir(self.project)
            with patch.object(agent, "API_KEY", "test-key"), patch.object(agent, "OpenAI", return_value=client), patch("sys.argv", ["agent", "-p", "Which skill deploys the service?"]), contextlib.redirect_stdout(io.StringIO()) as output:
                agent.main()
            return output.getvalue()
        finally:
            os.chdir(previous_dir)

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


if __name__ == "__main__":
    unittest.main()
