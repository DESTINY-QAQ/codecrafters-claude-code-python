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
VH1 只公布技能信息，不把技能正文放进提示词；JD8 在此基础上增加 `/技能名` 调用。

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

本地目录的 `origin` 连接到 GitHub 仓库，`codecrafters` 连接到平台专用仓库。
平台提交分支为 `master`。本机已安装官方 CLI，可以在项目目录运行：

```powershell
& "$env:LOCALAPPDATA\Programs\codecrafters\codecrafters.exe" submit
```

# Skills 扩展：JD8

JD8 新增 `resolve_skill_prompt()`，在第一次请求模型之前处理用户输入：

1. 普通提示词直接保留。
2. 输入以 `/` 开头时，取第一个单词作为技能命令，例如 `/apple` 对应 `apple`。
3. 读取 `.claude/skills/apple/SKILL.md`，跳过 frontmatter，只保留结束标记之后的正文。
4. 用正文替换原始 `/apple`，作为 `role=user` 的消息发送给模型。
5. 继续使用原来的 Agent 循环；所有技能的名称和描述仍在 system 消息中。

例如，将 `apple/SKILL.md` 的正文写为：

```text
Respond with exactly one word: blueberry
```

设置好 `OPENROUTER_API_KEY` 后，在项目目录执行：

```powershell
.\.venv\Scripts\python.exe -m app.main -p "/apple"
```

模型应输出 `blueberry`。这里的对应关系是“文件夹名称 → 技能正文”，
输出单词来自正文，程序没有写死答案。

只加载被点名技能的正文，其他技能保持名称和描述级别，避免冲突指令。
未知技能、非法名称或缺失 frontmatter 标记会在请求模型前报错。
正文内部的 Markdown 分隔线会被保留。
本关尚不替换 `$ARGUMENTS` 或 `$1`，参数替换属于下一关 WD2。
