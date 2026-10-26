# PANDA

**From GitHub issue to evidence-grounded engineering recommendation.**

PANDA helps open-source contributors find a suitable issue, inspect relevant repository evidence, and understand a practical next step. Connect a GitHub repository, browse real open issues, filter them with PANDA estimates, and ask the local model to analyze a selected issue.


UI ---- UX



https://github.com/user-attachments/assets/4af6e037-0abc-4db8-9636-641d57bbd533


---

<img width="2541" height="1597" alt="Screenshot 2026-10-26 143756" src="https://github.com/user-attachments/assets/a0603dc3-6b83-416f-ae66-6fe1cc13cd82" />

<img width="2557" height="1597" alt="Screenshot 2026-10-26 143802" src="https://github.com/user-attachments/assets/b5d37836-0fee-4ec9-83c2-a901cb5afc2d" />


## The problem

Large repositories can have thousands of open issues. A contributor must often judge whether an issue is appropriate, understand its context, locate relevant source and tests, and determine what work is involved before making a contribution.

## What PANDA does

```text
GitHub Repository
  -> Real Open Issues
  -> PANDA Difficulty / Skill / Effort Filters
  -> Select an Issue
  -> Repository Evidence Retrieval
  -> Gemma 4 through Ollama
  -> Structured Engineering Recommendation
```

PANDA connects to public GitHub repositories, retrieves real issue data, and provides deterministic estimates for difficulty, primary skill, and effort. When a contributor selects an issue for analysis, PANDA retrieves relevant repository files and tests and asks Gemma for five concise fields: file to change, why, what to change, proposed fix, and test to run or add.

PANDA presents a recommendation only. It does not modify source files, run tests, create pull requests, or verify a fix.

## Key differentiator

PANDA combines contributor-focused issue estimates with evidence from the selected repository. Difficulty, skill, and effort estimates are deterministic and do not depend on GitHub labels or an LLM. Deep analysis is grounded in retrieved repository evidence rather than only the issue text.

## Architecture

```text
React + Vite browser app
      | /api requests
      v
FastAPI backend
      |-- GitHub REST API: repository metadata, issues, labels, source evidence
      |-- deterministic PANDA issue estimates
      |-- focused repository-context retrieval
      `-- Ollama local API
              `-- Gemma 4 12B
```

PANDA uses **Gemma 4 locally through Ollama as its AI model**. The GitHub token stays in the backend environment and is never sent to the frontend.

## Tech stack

- **Frontend:** React, Vite, React Router, Framer Motion, Lucide React
- **Backend:** Python, FastAPI, Uvicorn, HTTPX, python-dotenv
- **AI runtime and model:** Ollama and Gemma 4 12B
- **Repository data:** GitHub REST API

## Quick start

Prerequisites: Git, Python 3.10 or newer, Node.js 20.19+ or 22.12+, npm, and Ollama.

```powershell
git clone https://github.com/AaryanRS/PANDA.git
cd PANDA

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd frontend
npm install
cd ..

Copy-Item .env.example .env
```

Edit `.env` with your GitHub token and the local Ollama settings. Install Ollama, then download and test the model:

```powershell
ollama --version
ollama pull gemma4:12b
ollama run gemma4:12b
```

In a second terminal from the repository root, start the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

In another terminal, start the frontend:

```powershell
cd frontend
npm.cmd run dev
```

Open [http://localhost:5173](http://localhost:5173). For token creation, full setup steps, and troubleshooting, see [SETUP.md](SETUP.md).

## Ollama and Gemma 4

Install Ollama from [ollama.com/download](https://ollama.com/download). Verify the CLI, download `gemma4:12b`, and run it directly with the commands above. At the Ollama prompt, type a normal question such as:

```text
Explain REST APIs in simple terms.
```

Ollama normally exposes its local API at `http://127.0.0.1:11434`. PANDA uses this default programmatically; it remains the default unless Ollama is configured otherwise. Configure `OLLAMA_BASE_URL` and `OLLAMA_MODEL` in the repository-root `.env` if you use a different local configuration.

## GitHub token

PANDA uses a GitHub Personal Access Token for authenticated API requests and improved rate limits. Public repository browsing can work without a token, but an optional fine-grained token is recommended. Grant read-only **Metadata**, **Issues**, and **Contents** permissions for the repositories PANDA will access. Never place the token in source code, share it, or commit `.env`.

The local `.env` should include:

```dotenv
GITHUB_TOKEN=YOUR_TOKEN
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma4:12b
```

`.env` is ignored by Git. Keep the real value only in your local `.env` file.

## Demo workflow

1. Connect a GitHub repository URL.
2. Browse its real open issues and use PANDA Difficulty, Skill, and Effort filters.
3. Select an issue to open the analysis view.
4. PANDA retrieves focused repository source and test evidence.
5. Gemma 4 through Ollama returns a structured engineering recommendation.

## Repository

[github.com/AaryanRS/PANDA](https://github.com/AaryanRS/PANDA)
