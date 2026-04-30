# Trinethra Analyzer — Task Breakdown

## 🎯 Goal
Build a simple web app that:
- Takes a transcript
- Sends it to Ollama
- Returns structured analysis (evidence, score, KPIs, gaps, questions)

---

## 🔥 Phase 1: Get Basic System Working (DO THIS FIRST)

### Task 1: Setup Project
- [ ] Create project folder
- [ ] Create FastAPI structure (app/, routes/, services/)
- [ ] Create virtual environment
- [ ] Install dependencies (fastapi, uvicorn, requests)

---

### Task 2: Setup Ollama
- [ ] Install Ollama
- [ ] Pull model (llama3.2 or phi3)
- [ ] Test in terminal:
```bash
ollama run llama3.2 "Hello"
```
