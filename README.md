# ThinkTwice 🧠
### System 2 Reasoning Engine via Speculative Auditing

![License](https://img.shields.io/badge/license-Apache_2.0-blue.svg) ![Python](https://img.shields.io/badge/python-3.9%2B-green) ![Status](https://img.shields.io/badge/status-experimental-orange)

**ThinkTwice** is a high-fidelity orchestration engine designed to impose deterministic logic constraints on stochastic Large Language Models (LLMs).

It introduces a **Speculative Auditing Layer** that validates the model's reasoning stream in real-time, forcing it to correct errors before they are finalized. By treating the generation process as a verified draft rather than a final output, ThinkTwice aims to bridge the gap between probabilistic generation and strict logical execution.

---

## ⚡ Amnesia Is All You Need

Standard LLMs prioritize fluency over correctness. When a model realizes it has made a logical error mid-sentence, it often "hallucinates" to maintain grammatical coherence or collapses into generic training patterns due to context drift.

**ThinkTwice addresses this via:**
1.  **Asynchronous Oversight:** A secondary "Auditor" agent watches the generation stream.
2.  **Non-Destructive Correction:** Instead of silently editing the context (which confuses the model), the system **appends** explicit intervention messages, preserving the full causal history of the error and the correction.

---

## 🏗️ Architecture

![Architecture Diagram](/Multimedia/Diagram.svg)

The system operates on three core principles:

* **Speculative Streaming:** The Generator streams `<idea>` tags representing its thought process. These are not shown to the user until verified.
* **The Auditor Loop:** An independent, logic-focused model validates every `<idea>` against the user's hard constraints.
    * **Pass:** The stream continues.
    * **Fail:** The system triggers a **Takeover**.
* **Immutable Context Strategy:** When a failure occurs, the system injects a structured intervention containing the specific error and a "Re-anchoring" directive. This forces the model to acknowledge the mistake and resume the original task without losing the initial instructions.

---

## 🎥 Proof of Concept

![ThinkTwice Logic Demo](/Multimedia/ThinkTwice.gif)
### Color Legend
  🟦 Blue: Generated Text (Streaming)  
  🟨 Yellow: Audit in Progress  
  🟩 Green: Validated Idea (OK)  
  🟪 Magenta: Takeover (Correction)  
  🟥 Red: Error Detected  


---

## 🧪 Stress Test Suite

The repository includes a benchmark suite (`comparisons.py`) specifically engineered to target weaknesses in LLM tokenization and state tracking.

### 1. The Winter Lipogram (Token Blindness)
Forces the model to perform character-level filtering, which contradicts standard BPE tokenization.
> **Prompt:** "Write a 3-sentence description of a snowy winter scene. HARD CONSTRAINT: You are **STRICTLY FORBIDDEN** from using the letter 'a' (case-insensitive)..."

### 2. The Shiritori Chain (Recursive State)
A high-difficulty constraint combining state tracking (last letter = first letter) with a restrictive length limit.
> **Prompt:** "Write a coherent sentence of exactly 7 words... Last Letter of Word N must be the First Letter of Word N+1... HARD CONSTRAINTS: No word can exceed 5 letters in length."

### 3. Branchless Code (Algorithmic Logic)
Requires translating boolean logic into arithmetic, prohibiting standard control flow.
> **Prompt:** "Write a Python function... HARD CONSTRAINTS: 100% BRANCHLESS. NO `if`, `else`, `while`... NO `min()`, `max()`, or `abs()`..."

---

## 🚀 Getting Started

### Prerequisites
* Python 3.9+
* API Key Of Open Router / OpenAI / Locale (Not Recomended)

### Installation

```bash
git clone https://github.com/zAGloth/thinktwice.git
cd thinktwice
pip install -r requirements.txt

```

### Configuration

Rename `config_example.py` to `config.py` and set your API keys.

```python
# config.py
API_KEY = "
.."  # Your primary reasoning model
```

### Usage

**1. Run the Benchmarks**
Compare the raw model output vs. the ThinkTwice engine.

```bash
python comparisons.py

```

**2. Interactive Chat**
Test the system with your own constraints.

```bash
python chat.py

```

---

## 🤝 Contributing

We are exploring the limits of reliable LLM orchestration. If you have ideas for better auditing strategies, more efficient context management, or tougher stress tests, feel free to open a Pull Request.

---

## 📄 License

This project is licensed under the **Apache 2.0 License**. See the [LICENSE](/LICENSE) file for details.
