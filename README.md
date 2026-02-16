# ForensicValue AI 🕵️‍♂️📈

**Automated Forensic Accounting & Management Integrity Analysis System**

ForensicValue AI is a multi-agent system designed to detect accounting irregularities, governance risks, and "value traps" in Indian listed companies (NSE/BSE).

![Dashboard](https://raw.githubusercontent.com/sanjibani/forensic-value-ai/main/assets/dashboard_screenshot.png)

## 🚀 Features

- **Multi-Agent Architecture**:
    - **Forensic Agent**: Analyzes 10-year financials & annual report text for anomalies.
    - **Management Agent**: Investigates promoter pledging, board independence, and related parties.
    - **RPT Agent**: Scrutinizes Related Party Transactions for fund siphoning.
    - **Market Intelligence Agent**: Searches web/social media for fraud allegations & sentiment.
    - **Narrative Agent**: Synthesizes all findings into a "Forensic Detective Story".
- **Deep Document Analysis**: Downloads and parses Annual Reports & Concall Transcripts for rare insights.
- **Self-Healing Pipeline**: Robust error handling with `json_repair` and auto-retries.
- **Interactive Dashboard**: Streamlit-based UI for reports and batch processing.

## 🛠️ Installation (Local)

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/sanjibani/forensic-value-ai.git
    cd forensic-value-ai
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up environment**:
    Create a `.env` file (see `.env.example`):
    ```env
    # Required
    GOOGLE_API_KEY=your_gemini_key
    # Optional
    ANTHROPIC_API_KEY=your_claude_key
    OPENAI_API_KEY=your_openai_key
    ```

4.  **Run the Dashboard**:
    ```bash
    streamlit run dashboard.py
    ```

## ☁️ Deployment on Streamlit Cloud

1.  Push this code to your GitHub repository.
2.  Go to [share.streamlit.io](https://share.streamlit.io).
3.  Connect your GitHub account.
4.  Select the `forensic-value-ai` repo.
5.  Set "Main file path" to `dashboard.py`.
6.  Add your API keys (`GOOGLE_API_KEY`, etc.) in the **Advanced Settings -> Secrets** section.
7.  Click **Deploy**.

## 🐳 Docker Deployment

1.  **Build & Run**:
    ```bash
    docker-compose up --build
    ```
2.  Access at `http://localhost:8501`.

## 🧠 System Architecture

The system uses **LangGraph** to orchestrate agents:
`Fetcher` -> `Forensic/Mgmt/RPT/Market` (Parallel) -> `Aggregator` -> `Critic` -> `Narrative` -> `Report`.

## 📜 License

MIT License.
