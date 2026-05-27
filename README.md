---
title: Python Docs Assistant
emoji: 📄
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
---

# Python Docs Assistant

A Retrieval-Augmented Generation (RAG) system that answers Python questions by grounding GPT-4o-mini in 22,800+ embedded documentation chunks from FastAPI, Pydantic, uvicorn, uv, LangChain, LlamaIndex, pandas, and scikit-learn. Every answer cites the source documentation.

## Run locally

```bash
python -m uvicorn app:app --reload --port 10000
```
