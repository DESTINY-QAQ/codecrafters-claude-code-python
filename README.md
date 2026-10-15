[![progress-banner](https://backend.codecrafters.io/progress/claude-code/21244232-1ee2-4e58-a2eb-c6d97d895a2a)](https://app.codecrafters.io/users/DESTINY-QAQ?r=2qF)

This is a starting point for Python solutions to the
["Build Your own Claude Code" Challenge](https://codecrafters.io/challenges/claude-code).

Claude Code is an AI coding assistant that uses Large Language Models (LLMs) to
understand code and perform actions through tool calls. In this challenge,
you'll build your own Claude Code from scratch by implementing an LLM-powered
coding assistant.

Along the way you'll learn about HTTP RESTful APIs, OpenAI-compatible tool
calling, agent loop, and how to integrate multiple tools into an AI assistant.

**Note**: If you're viewing this repo on GitHub, head over to
[codecrafters.io](https://codecrafters.io) to try the challenge.

# Passing the first stage

The entry point for your `claude-code` implementation is in `app/main.py`. Study
and uncomment the relevant code, and submit to pass the first stage:

```sh
codecrafters submit
```

# Stage 2 & beyond

Note: This section is for stages 2 and beyond.

1. Ensure you have `uv` installed locally.
2. Run `./your_program.sh` to run your program, which is implemented in
   `app/main.py`.
3. Run `codecrafters submit` to submit your solution to CodeCrafters. Test
   output will be streamed to your terminal.

# Skills 扩展：vh1

本关在现有 `app/main.py` 中实现，无需另外创建一个项目文件夹。
程序启动时会扫描**当前工作目录**下的 `.claude/skills/*/SKILL.md`，
使用 PyYAML 解析 frontmatter，把各技能的名称和描述放进第一条 system 消息。
本关只公布技能信息，不把技能正文放进提示词，也尚未实现 `/技能名` 调用。

CodeCrafters 测试会自动创建技能目录；本地体验时，可以在本项目中新建：

```text
.claude/
└── skills/
    └── apple/
        └── SKILL.md
```

`SKILL.md` 示例（目录名与 `name` 一致）：

```markdown
---
name: apple
description: Deploys the apple service to production.
---

Run the deploy script and report the version that was deployed.
```

在项目目录中安装依赖并运行（需已安装 uv 和 Python 3.14）：

```powershell
uv sync --locked
$env:OPENROUTER_API_KEY = "你的 API key"
uv run -m app.main -p "Which skill would help me deploy the apple service? Respond with only the skill name."
```

本地回归测试不需要 API key，也不调用外部模型：

```powershell
uv run -m unittest discover -s tests -v
```

本目录已准备好 `.venv` 时，也可以直接使用项目的 Python，无需激活环境：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

本地目录的 `origin` 已连接到
`https://github.com/DESTINY-QAQ/codecrafters-claude-code-python.git`，修改尚未推送。
提交平台测试还需要关卡页面提供的 CodeCrafters 专用仓库地址，
GitHub 地址不能替代该提交地址。连接平台仓库并安装 CodeCrafters CLI 后，
可按页面指引运行 `codecrafters submit`。
