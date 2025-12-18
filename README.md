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

![Architecture Diagram](/README-Files/Diagram.svg)

The system operates on three core principles:

* **Speculative Streaming:** The Generator streams `<idea>` tags representing its thought process. These are not shown to the user until verified.
* **The Auditor Loop:** An independent, logic-focused model validates every `<idea>` against the user's hard constraints.
    * **Pass:** The stream continues.
    * **Fail:** The system triggers a **Takeover**.
* **Immutable Context Strategy:** When a failure occurs, the system injects a structured intervention containing the specific error and a "Re-anchoring" directive. This forces the model to acknowledge the mistake and resume the original task without losing the initial instructions.

---

## 🎥 Proof of Concept

![ThinkTwice Logic Demo](/README-Files/ThinkTwice.gif)
### Color Legend
  🟦 Blue: Generated Text (Streaming)  
  🟨 Yellow: Audit in Progress  
  🟩 Green: Validated Idea (OK)  
  🟪 Magenta: Takeover (Correction)  
  🟥 Red: Error Detected  


---
## 🧪 Stress Test Suite

The repository includes a benchmark suite (`comparisons.py`) specifically engineered to target inherent weaknesses in LLM tokenization and state tracking. These tests are designed to fail standard models.

| Test | Objective | Why It Breaks LLMs |
| :--- | :--- | :--- |
| **1. The Winter Lipogram** | **Negative Constraints** | Forces character-level filtering, which contradicts standard BPE (Byte Pair Encoding) tokenization where tokens often span multiple characters. |
| **2. The Shiritori Chain** | **Recursive State** | Requires looking back at the *previous* output's last character while planning the *next* word's length (< 5 chars). High cognitive load. |
| **3. Branchless Code** | **Algorithmic Logic** | Prohibits standard control flow (`if`/`else`), forcing the model to translate boolean logic into pure arithmetic operations. |

### ⚡ Performance Note: "Thinking Takes Time"

**ThinkTwice is NOT optimized for speed.** The system enters a recursive audit loop that may reject and regenerate thoughts dozens of times per query. Consequently, generation is significantly slower than standard LLM streaming. This latency is a feature, not a bug: it is the inherent cost of moving from System 1 (instinct) to System 2 (reasoning).

---

## 🚀 Getting Started

### Prerequisites
* **Python 3.9+**
* **API Access:** OpenRouter (Recommended for access to DeepSeek/Claude), OpenAI, or Local Inference (Ollama/LM Studio - *Note: Local models may have difficulty with strict instructions.*).

### Installation

```bash
git clone [https://github.com/zAGloth/thinktwice.git](https://github.com/zAGloth/thinktwice.git)
cd thinktwice
pip install -r requirements.txt
```

### Configuration
Copy the template configuration file:

```bash
cp config.template.py config.py
```
Edit config.py with your credentials. The system supports distinct providers for Generating and Auditing (e.g., a smart generator and a fast auditor).


```python

# config.py

# Provider Configuration (OpenRouter, OpenAI, etc.)
API_BASE_URL = "[https://openrouter.ai/api/v1](https://openrouter.ai/api/v1)"
API_KEY = "sk-..."

# Model Selection
GENERATOR_MODEL = "deepseek/deepseek-chat" # Logic Heavy
AUDITOR_MODEL = "anthropic/claude-3-haiku" # Speed Heavy
```

### Usage
1. Benchmark Mode (Head-to-Head) Run the stress suite to generate side-by-side markdown reports comparing Raw vs DeepThink vs ThinkTwice.


```python
python comparisons.py
```

#### Results are saved to /outputs/YYYY-MM-DD_HH-MM-SS/
2. Interactive Chat (Debug Mode) Test the system with your own constraints and watch the Takeover mechanism in real-time.

```python
python chat.py
```
---

## 🤝 Contributing

We are exploring the limits of reliable LLM orchestration. If you have ideas for better auditing strategies, more efficient context management, or tougher stress tests, feel free to open a Pull Request.

---

## 📄 License

This project is licensed under the **Apache 2.0 License**. See the [LICENSE](/LICENSE) file for details.

---

## 🔮 Roadmap

Although our current priority is absolute logical integrity, we are exploring future iterations focused on performance:

* **ThinkTwice Lite:** a low-latency variant designed for High-throughput applications
* **Advanced Constraint Schemas:** Researching new protocols for complex multi-step logical verification. 😈
