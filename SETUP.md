# PANDA setup

This guide takes you from a fresh clone to a local PANDA demo on Windows PowerShell. PANDA's backend and Ollama should run locally; GitHub requests use the GitHub REST API.

## Prerequisites

- Git
- Python 3.10 or newer (the existing project setup documents Python 3.10+)
- Node.js 20.19+ or 22.12+ and npm (required by the project's Vite version)
- Ollama
- Internet access for package installation and GitHub API requests

## 1. Clone PANDA

```powershell
git clone https://github.com/AaryanRS/PANDA.git
cd PANDA
```

## 2. Set up the backend

From the repository root, create and activate a virtual environment, then install the root requirements file:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The root `requirements.txt` references `backend/requirements.txt`. To install the backend dependencies directly without the root file, run:

```powershell
pip install -r backend/requirements.txt
```

If PowerShell blocks virtual-environment activation, you can skip activation and invoke the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Set up the frontend

From the repository root:

```powershell
cd frontend
npm install
cd ..
```

## 4. Install and verify Ollama and Gemma 4

Install Ollama using the instructions for your operating system at [ollama.com/download](https://ollama.com/download). Verify the command is available, download PANDA's model, and start an interactive model session:

```powershell
ollama --version
ollama pull gemma4:12b
ollama run gemma4:12b
```

At the Ollama prompt, type a question directly, for example:

```text
Explain REST APIs in simple terms.
```

This directly tests Gemma 4 through Ollama. Type `/bye` or press `Ctrl+C` to leave the interactive session. Ollama normally exposes its local API at `http://127.0.0.1:11434`; this is the default address PANDA uses programmatically. It remains the default unless you change Ollama's configuration.

## 5. Configure a GitHub token

PANDA uses a GitHub Personal Access Token for authenticated GitHub API access and higher API rate limits. Public repository access may work without a token, but a fine-grained token is recommended for reliable demos.

Create a fine-grained token in your GitHub account. Grant only read access for repositories PANDA will inspect: **Metadata: Read-only**, **Issues: Read-only**, and **Contents: Read-only**. Do not grant write permissions for PANDA's current workflow.

Copy the example file in the repository root:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and configure:

```dotenv
GITHUB_TOKEN=YOUR_TOKEN
OLLAMA_BASE_URL=server Link
OLLAMA_MODEL=gemma4:12b
```

The token is read by the backend and is never sent to the browser. `.env` is local configuration, is already ignored by `.gitignore`, and must never be committed or shared. Restart the backend after changing `.env` so it reloads the settings.

## 6. Start PANDA

Open three PowerShell terminals. Leave Ollama running in the background or in its own terminal.

**Terminal 1: backend**, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

The backend listens on `http://127.0.0.1:8000` by default.

**Terminal 2: frontend**, from the repository root:

```powershell
cd frontend
npm.cmd run dev
```

Open the local URL printed by Vite. It is normally [http://localhost:5173](http://localhost:5173).

## 7. Verify the backend

Open this URL or request it from PowerShell:

```text
GET http://127.0.0.1:8000/api/health
```

The expected response is **200 OK** with a JSON status of `ok`.

## 8. Try the complete PANDA flow

1. Connect a GitHub repository using its URL, such as `https://github.com/pandas-dev/pandas`.
2. Browse real open issues. Use PANDA Difficulty, Skill, and Effort estimates to filter the available issues.
3. Select an issue to open its analysis view.
4. PANDA retrieves relevant repository files and tests as evidence.
5. Gemma 4 through Ollama produces the structured engineering recommendation: file to change, why, what to change, proposed fix, and test to run or add.

Gemma 4 is the only AI model used for PANDA's runtime AI output. PANDA displays recommendations; it does not automatically modify source files, run tests, create pull requests, or verify a fix.

## Troubleshooting

- **`ollama` is not recognized:** Install Ollama, then close and reopen PowerShell so its PATH is refreshed.
- **`gemma4:12b` is missing:** Run `ollama pull gemma4:12b`, then check `ollama list`.
- **Port 11434 is unavailable:** Check that Ollama is running. If it is not running as a service/app, start it with `ollama serve`; do not start a second server if one is already active.
- **Port 8000 is already in use:** Stop the previous Uvicorn process with `Ctrl+C` in its terminal, then start PANDA again. The frontend proxy expects the backend at port 8000 by default.
- **Vite prints a port other than 5173:** Another Vite process is using the default port. Use the URL printed by Vite, or stop the other process with `Ctrl+C` and restart PANDA's frontend.
- **Python dependencies are missing:** Activate `.venv` and run `pip install -r requirements.txt` from the repository root.
- **GitHub rate limit:** Configure a fine-grained `GITHUB_TOKEN` with read-only repository permissions, restart the backend, and retry. If the limit has already been reached, wait for GitHub's reset time.
- **Missing or invalid `GITHUB_TOKEN`:** Check that the local root `.env` contains `GITHUB_TOKEN=...` with no surrounding quotes or spaces, and that the token has read access to the repository. Never paste the value into logs or public reports.
- **Backend cannot reach GitHub:** Confirm outbound HTTPS access and token settings. Check the backend's safe `[PANDA] GitHub request failed` log for the request URL and exception; it does not log the token. If running in a restricted shell or sandbox, start the backend from a normal shell with outbound network access.
- **The environment file is named `.env.txt`:** In File Explorer, enable **View > Show > File name extensions**, or rename it in PowerShell with `Rename-Item .env.txt .env`. The backend loads `.env`, not `.env.txt`.

For product details and a short overview, see [README.md](README.md).
