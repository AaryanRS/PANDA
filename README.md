<div align="center">

# 🐼 PANDA

### **From Open-Source Issue to Working Solution.**

**PANDA** is an AI-powered open-source contribution platform that helps developers  
**find → understand → plan → solve → verify** GitHub issues.

<br/>

**Issue Filter · Issue Analyzer · Issue Solver · Verification**

<br/>

---

> **Stop scrolling through issues. Start contributing.**

</div>

## Phase 1 Foundation (current implementation)

The repository now contains the base React/Vite frontend and FastAPI backend. The current application provides a landing page and placeholder routes for Repository, Issue Explorer, Issue Analysis, and Implementation. The frontend checks the backend through `GET /api/health`.

The feature descriptions, AI architecture, and demo flow in the original overview below describe planned product behavior; they are not proof of implemented functionality. This phase implements only the application foundation and placeholder routes. There is no GitHub API connection, repository or issue analysis, AI/model integration, solver, or verification behavior yet.

### Run locally

Requirements: Node.js with npm, and Python 3.10 or newer.

```bash
# Terminal 1: backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend

# Terminal 2: frontend
cd frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`). The header reports whether the local backend health endpoint is reachable. The Vite development server proxies `/api` to `http://127.0.0.1:8000`.

The backend accepts optional `BACKEND_CORS_ORIGINS` as a comma-separated list. Copy `.env.example` to `.env` to use the local defaults.

### Current stack

- Frontend: React, Vite, JavaScript/JSX, React Router, Framer Motion, and Lucide React.
- Backend: Python, FastAPI, and Uvicorn.
- No database, model runtime, or third-party service integration is part of Phase 1.

<br/>

## ✦ What is PANDA?

Large open-source projects can have **hundreds or even thousands of open issues**.

Finding an issue is easy.

**Understanding what the issue actually requires is the hard part.**

A contributor often has to manually:

- read the issue and discussion
- explore the repository
- find the relevant code
- understand the architecture
- locate existing tests
- figure out the actual implementation
- decide whether the issue is suitable for them
- implement the change
- verify that the solution really works

**PANDA brings that entire process into one workflow.**

```text
        GitHub Repository
               │
               ▼
        ┌───────────────┐
        │  ISSUE FILTER │
        └───────┬───────┘
                │
                ▼
        ┌────────────────┐
        │ ISSUE ANALYZER  │
        └───────┬────────┘
                │
                ▼
        ┌────────────────┐
        │  TASK / PLAN    │
        └───────┬────────┘
                │
                ▼
        ┌────────────────┐
        │  ISSUE SOLVER   │
        └───────┬────────┘
                │
                ▼
        ┌────────────────┐
        │   VERIFY FIX    │
        └────────────────┘
```

---

## 🎯 The Problem

Open-source repositories expose a huge amount of work, but contributors often don't know:

> **Which issue should I work on?**

> **What does this issue actually mean?**

> **How difficult is it really?**

> **Which part of the codebase is involved?**

> **What exactly should I change?**

> **How do I know my fix actually solves the issue?**

GitHub labels and issue descriptions provide useful information, but they don't take a contributor through the complete engineering process.

**PANDA is built around that missing layer.**

---

## 🐼 What PANDA Does

### 01 — Filter Issues

PANDA analyzes the issue backlog and organizes issues from a **contributor's perspective**.

Example categories:

| Category | Meaning |
|---|---|
| 🟢 Beginner | Suitable for someone new to the project |
| 🔵 Bug Fix | Existing behavior needs correction |
| 🟡 Small Implementation | Localized engineering change |
| 🟣 Feature | New functionality |
| 🟠 Testing | Missing or improved test coverage |
| ⚪ Documentation | Documentation-related contribution |
| 🔴 Complex | Requires deeper project knowledge |
| 🧩 Investigation | Requires further technical investigation |

The goal isn't simply to reproduce GitHub labels.

PANDA tries to answer:

> **“What kind of engineering work would I actually be doing?”**

---

### 02 — Analyze an Issue

Select an issue and PANDA investigates the repository around it.

It can use relevant:

- Issue content
- Comments
- Source code
- Repository structure
- Tests
- Documentation
- Related issues / PRs
- Relevant Git history

The result becomes an engineering-focused analysis.

#### Example

```text
Issue #482

Type
Bug Fix

Difficulty
Medium

Required knowledge
Python
Async programming
Testing

Affected area
src/network/...

Root cause
...

Current behavior
...

Expected behavior
...

Implementation direction
...

Recommended tests
...
```

---

### 03 — Turn an Issue into a Real Engineering Task

GitHub issues are often written as a description of a problem.

PANDA transforms them into a **practical implementation plan**.

```text
GOAL
Fix incorrect retry behavior.

FILES
src/retry/handler.py
tests/retry/test_handler.py

IMPLEMENTATION
1. Detect duplicate retry state.
2. Preserve existing retry behavior.
3. Handle timeout case.
4. Add regression tests.

ACCEPTANCE CRITERIA
✓ Duplicate requests do not trigger multiple retries.
✓ Existing retry tests remain unchanged.
✓ New regression test passes.
```

Instead of asking:

> “What does this issue mean?”

the contributor gets:

> **“Here is what you actually need to do.”**

---

### 04 — Solve the Issue

Once the contributor understands the task, PANDA assists with implementation.

The solver can:

- identify relevant code locations
- suggest implementation changes
- generate an implementation plan
- propose code changes
- generate/update tests
- help interpret implementation failures

PANDA is designed to work **with the repository's existing architecture**, rather than inventing a completely different solution.

---

### 05 — Verify the Solution

A proposed fix is not enough.

PANDA should help determine whether the solution actually works.

```text
Implementation
      │
      ▼
     Tests
      │
 ┌────┴────┐
 ▼         ▼
PASS      FAIL
 │          │
 ▼          ▼
Resolved   Investigate
```

Example:

```text
✓ 42 existing tests passed
✓ 3 regression tests passed
✓ Expected behavior verified

Result
Issue appears resolved.
```

---

# ✦ AI Architecture

PANDA uses **Gemma 4** as the core AI model.

The model is run locally using **Ollama**.

```text
┌───────────────────────────────┐
│           PANDA UI            │
│  Filter · Analyze · Solve     │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│         PANDA Backend          │
│                               │
│  GitHub Integration            │
│  Repository Context            │
│  Issue Processing              │
│  Agent Orchestration           │
│  Verification                  │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│            Ollama              │
│                               │
│           Gemma 4              │
└───────────────┬───────────────┘
                │
                ▼
        AI-generated reasoning
```

### Why local inference?

Running Gemma through Ollama allows PANDA to use the model locally without making the entire system dependent on a hosted model API.

It also makes the AI component easy to demonstrate during a live presentation.

---

# 🧠 Repository-Aware AI

PANDA should **not behave like a generic chatbot**.

Instead of giving the model only the GitHub issue:

```text
Issue
  +
Relevant repository context
  +
Relevant tests
  +
Relevant history
        ↓
     Gemma 4
        ↓
Engineering reasoning
```

The system should retrieve the information that is actually relevant to the selected issue.

### Evidence First

PANDA distinguishes between:

**Evidence**

> What was actually found in the repository.

**Inference**

> What the model concludes from that evidence.

This helps reduce hallucinated repository details and makes the generated analysis easier to trust.

---

# ✦ Key Features

| Feature | Description |
|---|---|
| 🗂️ Issue Filtering | Discover useful contribution opportunities |
| 🔍 Issue Analysis | Understand what an issue actually requires |
| 🧠 Repository Context | Reason using relevant project information |
| 🛠️ Engineering Plans | Convert issues into actionable tasks |
| 💻 Solution Assistance | Help implement the required changes |
| 🧪 Verification | Check whether the proposed fix works |
| 🐼 Gemma 4 | Open model powering the AI workflow |
| ⚡ Ollama | Local model runtime |

---

# 📸 Screenshots

> Screenshots will be added here as the project UI is finalized.

### Dashboard

<img src="screenshots/dashboard.png" alt="PANDA Dashboard" width="100%"/>

### Issue Explorer

<img src="screenshots/issue-explorer.png" alt="PANDA Issue Explorer" width="100%"/>

### Issue Analysis

<img src="screenshots/issue-analysis.png" alt="PANDA Issue Analysis" width="100%"/>

### Solution Workspace

<img src="screenshots/solution-workspace.png" alt="PANDA Solution Workspace" width="100%"/>

### Verification

<img src="screenshots/verification.png" alt="PANDA Verification" width="100%"/>

---

# ⚙️ How PANDA Works

```text
01
Connect Repository
       ↓
02
Fetch Issues
       ↓
03
Filter & Classify
       ↓
04
Retrieve Relevant Repository Context
       ↓
05
Analyze Selected Issue
       ↓
06
Generate Engineering Plan
       ↓
07
Assist With Implementation
       ↓
08
Run / Analyze Tests
       ↓
09
Verify Solution
```

---

# 🚀 Quick Start

## Prerequisites

Make sure you have:

- Git
- Python / Node.js depending on the project setup
- GitHub access
- Ollama
- Gemma 4 model

### Start Ollama

```bash
ollama serve
```

### Pull the Gemma model

```bash
ollama pull gemma4
```

### Start PANDA

```bash
# Clone the repository
git clone <your-repository-url>

cd PANDA

# Install dependencies
<install-command>

# Start the application
<start-command>
```

> [!IMPORTANT]
> The exact model variant and installation commands may change depending on the final PANDA architecture.

---

# 🛠️ Tech Stack

### AI

- **Gemma 4**
- **Ollama**

### Platform

- GitHub API
- Repository analysis
- Git history
- Automated testing

### Application

- Frontend: `TBD`
- Backend: `TBD`
- Database / Vector Store: `TBD`

---

# 🧩 Project Architecture

```text
PANDA
│
├── frontend/
│   ├── dashboard
│   ├── issue-explorer
│   ├── issue-analysis
│   ├── solver
│   └── verification
│
├── backend/
│   ├── github/
│   ├── repository/
│   ├── retrieval/
│   ├── agents/
│   ├── solver/
│   └── verification/
│
├── models/
│   └── gemma/
│
└── README.md
```

> The final architecture will evolve as implementation progresses.

---

# 🎥 Demo Flow

The intended PANDA demonstration is:

```text
Open PANDA
   ↓
Select an Open-Source Repository
   ↓
Browse / Filter Issues
   ↓
Select an Issue
   ↓
Analyze Repository Context
   ↓
Understand the Actual Problem
   ↓
Generate Implementation Plan
   ↓
Solve the Issue
   ↓
Run Tests
   ↓
Verify the Fix
```

### The goal of the demo

Show the transformation:

**Before PANDA**

> “There are hundreds of issues. Which one can I actually solve?”

**After PANDA**

> “I know what the issue means, what code is involved, what I need to change, and whether my solution works.”

---

# 🔐 Design Principles

### Repository First

Use actual repository information whenever possible.

### Evidence Over Guessing

Do not confidently invent implementation details.

### Contributor Focused

Optimize for helping a developer **contribute**, not just helping a maintainer label issues.

### End-to-End

PANDA should move beyond:

```text
Issue → Explanation
```

and aim for:

```text
Issue → Understanding → Implementation → Verification
```

---

# 🗺️ Roadmap

- [x] Project concept
- [x] PANDA branding
- [ ] Base application
- [ ] GitHub repository integration
- [ ] Issue filtering
- [ ] Issue analysis
- [ ] Repository-aware retrieval
- [ ] Gemma 4 + Ollama integration
- [ ] Engineering plan generation
- [ ] Solution workflow
- [ ] Test / verification system
- [ ] Final demo workflow
- [ ] Documentation
- [ ] Screenshots & showcase

---

# 🤝 Contributing

PANDA is built around the open-source ecosystem.

Contributions, ideas, issues, and feedback are welcome.

```text
Fork → Build → Test → Improve → Contribute
```

---

# 📌 Project Status

> 🚧 **PANDA is currently under active development.**

The project is being built as a hackathon prototype with a focus on demonstrating a complete AI-assisted open-source contribution workflow.

---

<div align="center">

## 🐼 PANDA

### **Find the issue. Understand the work. Ship the fix.**

Built with **Gemma 4 + Ollama + Open Source**

<br/>

**Made for developers who want to contribute — not just browse.**

</div>
