import argparse
import json
import os
import subprocess
from pathlib import Path

import yaml
from openai import OpenAI

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")


def build_skill_system_prompt(skills_dir=Path(".claude/skills")):
    """Advertise skill metadata from the working directory, without the bodies."""
    skills = []
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            with skill_file.open(encoding="utf-8-sig") as file:
                if file.readline().strip() != "---":
                    continue
                frontmatter = []
                for line in file:
                    if line.strip() == "---":
                        break
                    frontmatter.append(line)
                else:
                    continue

            metadata = yaml.safe_load("".join(frontmatter))
        except (OSError, UnicodeError, yaml.YAMLError):
            continue

        if not isinstance(metadata, dict):
            continue
        name = metadata.get("name", skill_file.parent.name)
        description = metadata.get("description")
        if not isinstance(name, str) or not isinstance(description, str):
            continue
        name = name.strip()
        description = " ".join(description.split())
        if name and description:
            skills.append(f"- {name}: {description}")

    if not skills:
        return ""
    return "You have access to the following skills:\n\n" + "\n".join(skills)


def resolve_skill_prompt(prompt, skills_dir=Path(".claude/skills")):
    """Replace a leading /skill-name command with that skill's body."""
    if not prompt.startswith("/"):
        return prompt

    skill_name = prompt.split(maxsplit=1)[0][1:]
    if (
        not skill_name
        or skill_name in {".", ".."}
        or any(character in skill_name for character in "/\\:")
    ):
        raise ValueError(f"Invalid skill name: {skill_name!r}")

    skill_file = skills_dir / skill_name / "SKILL.md"
    if not skill_file.is_file():
        raise ValueError(f"Unknown skill {skill_name!r}: expected {skill_file}")

    with skill_file.open(encoding="utf-8-sig") as file:
        if file.readline().strip() != "---":
            raise ValueError(f"Skill {skill_name!r} is missing YAML frontmatter")
        for line in file:
            if line.strip() == "---":
                return file.read().strip()

    raise ValueError(f"Skill {skill_name!r} has no closing frontmatter marker")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-p", required=True)
    args = p.parse_args()

    try:
        user_prompt = resolve_skill_prompt(args.p)
    except (ValueError, OSError, UnicodeError) as error:
        p.error(str(error))

    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    messages = []
    skill_system_prompt = build_skill_system_prompt()
    if skill_system_prompt:
        messages.append({"role": "system", "content": skill_system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    tools = [
        {
            "type": "function",
            "function": {
                "name": "Read",
                "description": "Read and return the contents of a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path to the file to read",
                        }
                    },
                    "required": ["file_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "Write",
                "description": "Write content to a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path of the file to write to",
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write to the file",
                        },
                    },
                    "required": ["file_path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "Bash",
                "description": "Execute a shell command",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The command to execute",
                        }
                    },
                    "required": ["command"],
                },
            },
        },
    ]

    while True:
        chat = client.chat.completions.create(
            model="anthropic/claude-haiku-4.5",
            messages=messages,
            tools=tools,
        )
        if not chat.choices:
            raise RuntimeError("no choices in response")

        message = chat.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            print(message.content or "")
            return

        for tool_call in message.tool_calls:
            arguments = json.loads(tool_call.function.arguments)
            if tool_call.function.name == "Read":
                with open(arguments["file_path"], "r", encoding="utf-8") as file:
                    result = file.read()
            elif tool_call.function.name == "Write":
                with open(arguments["file_path"], "w", encoding="utf-8", newline="") as file:
                    file.write(arguments["content"])
                result = "File written successfully"
            elif tool_call.function.name == "Bash":
                try:
                    completed = subprocess.run(
                        arguments["command"],
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        errors="replace",
                    )
                    result = completed.stdout
                    if completed.returncode != 0:
                        result = f"Command exited with code {completed.returncode}\n{result}"
                except OSError as error:
                    result = f"Failed to execute command: {error}"
            else:
                raise RuntimeError(f"Unknown tool: {tool_call.function.name}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )


if __name__ == "__main__":
    main()
