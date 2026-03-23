# Setting Up VSCode to Run the Task Extraction Notebook

A step-by-step guide for someone who has never run a Jupyter notebook in VSCode before.
Covers Python installation, virtual environment, all package installs, kernel selection,
and common problems you'll hit on the first run.

---

## What you're installing

| Layer | What it is | Why it's needed |
|-------|-----------|-----------------|
| Python 3.10+ | The language | Everything runs on this |
| VSCode | The editor | Where you open and run the notebook |
| Python extension | VSCode add-on | Adds Python language support |
| Jupyter extension | VSCode add-on | Lets `.ipynb` files run inside VSCode |
| Virtual environment | Isolated folder of packages | Keeps this project's packages separate from everything else on your machine |
| spaCy | NLP library | Named entity recognition (finds names, dates, orgs) |
| KeyBERT | NLP library | Keyphrase extraction using transformers |
| YAKE | NLP library | Statistical keyword extraction (fallback) |
| sentence-transformers | ML library | Powers KeyBERT's semantic embeddings |
| NLTK | NLP library | Sentence tokenisation, stopwords |
| dateparser | Utility library | Parses natural-language date strings |
| en_core_web_trf | spaCy model | Transformer-based NER model (preferred) |
| en_core_web_sm | spaCy model | Smaller statistical model (fallback) |
| NLTK data | Corpus data | punkt, punkt_tab, stopwords — downloaded separately from the library |

---

## Step 1 — Install Python

1. Go to **https://www.python.org/downloads/**
2. Download the latest **Python 3.11** or **3.12** installer (either works; avoid 3.13 for now — some ML packages lag behind).
3. Run the installer.
   - **Windows:** tick **"Add Python to PATH"** before clicking Install. This is the most common setup mistake — if you skip it, nothing works from the terminal.
   - **macOS / Linux:** the installer handles PATH automatically.
4. Verify the install worked. Open a terminal (PowerShell on Windows, Terminal on macOS/Linux) and run:

```bash
python --version
```

You should see something like `Python 3.11.9`. If you get `command not found`, Python is not on your PATH — re-run the installer and tick the PATH option.

---

## Step 2 — Install VSCode

1. Go to **https://code.visualstudio.com/**
2. Download and install the version for your OS.
3. Open VSCode.

---

## Step 3 — Install the two required VSCode extensions

In VSCode, click the **Extensions** icon in the left sidebar (or press `Ctrl+Shift+X` / `Cmd+Shift+X`).

Search for and install both of these:

| Extension name | Publisher | What it does |
|---------------|-----------|--------------|
| **Python** | Microsoft | Python language support, linting, virtual env management |
| **Jupyter** | Microsoft | Opens and runs `.ipynb` notebook files |

After installing, VSCode may ask you to reload — click **Reload**.

---

## Step 4 — Open your project folder

1. In VSCode: **File → Open Folder**
2. Select (or create) a folder where you want to keep the project, e.g. `task-extraction/`
3. Put `task_extraction_final.ipynb` in that folder.

---

## Step 5 — Create a virtual environment

A virtual environment is an isolated copy of Python just for this project.
It means you can install heavyweight ML packages here without affecting anything else on your machine.

Open the integrated terminal in VSCode: **Terminal → New Terminal** (or `` Ctrl+` ``).

**Windows:**
```bash
python -m venv .venv
```

**macOS / Linux:**
```bash
python3 -m venv .venv
```

This creates a hidden `.venv` folder inside your project folder.

> **VSCode tip:** After creating the venv, VSCode usually shows a pop-up asking
> *"We noticed a new virtual environment was created. Do you want to select it for the workspace?"*
> Click **Yes**. This means VSCode will automatically use it.

---

## Step 6 — Activate the virtual environment

You need to activate the venv so that `pip install` puts packages inside it.

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

If you get a red error about *"running scripts is disabled on this system"*, run this once to allow it:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then try activating again.

**macOS / Linux:**
```bash
source .venv/bin/activate
```

When activated, your terminal prompt will show `(.venv)` at the start. That's how you know it's working.

---

## Step 7 — Install all packages

With the venv activated, run each of these commands in the terminal. They will take a few minutes total because `sentence-transformers` and `spacy` are large.

```bash
pip install spacy keybert yake sentence-transformers nltk dateparser
```

Then install the spaCy language model. The transformer model is more accurate for this pipeline:

```bash
python -m spacy download en_core_web_trf
```

If that fails (sometimes it does on older machines or slow connections), install the smaller fallback model instead:

```bash
python -m spacy download en_core_web_sm
```

Then download the NLTK data the notebook needs. Run Python and paste these three lines:

```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"
```

You should see:
```
[nltk_data] Downloading package punkt...
[nltk_data] Downloading package punkt_tab...
[nltk_data] Downloading package stopwords...
```

---

## Step 8 — Select the correct kernel in VSCode

This is the step most people get stuck on. The "kernel" is the Python environment that actually runs the notebook cells. You need to point it at the `.venv` you just created.

1. Open `task_extraction_final.ipynb` in VSCode (click it in the file explorer).
2. Look at the **top-right corner** of the notebook. You'll see a button that says something like **"Select Kernel"** or shows a Python version.
3. Click it.
4. A dropdown appears at the top of the screen. Choose **"Python Environments..."**
5. You should see your `.venv` listed — it will say something like:
   ```
   Python 3.11.9 ('.venv': venv)
   ```
6. Click it.

The kernel selector in the top-right should now show `.venv`.

> **If you don't see `.venv` in the list:**
> - Make sure you created the venv inside the project folder (not somewhere else).
> - Try: `Ctrl+Shift+P` → type `Python: Select Interpreter` → choose the `.venv` option.
> - If it still doesn't appear, close and reopen VSCode with the project folder open.

---

## Step 9 — Run the notebook

1. The notebook has a **"Run All"** button at the top (looks like `▶▶`). Don't use it on the first run.
2. Instead, run **Cell 1 (the install cell)** first by clicking the `▶` button on the left of that cell.
   - This cell runs `pip install` via subprocess. On the very first run it can take 2–5 minutes.
   - When it finishes you'll see: `All deps ready.  spaCy model: en_core_web_trf`
3. Then run **Cell 2 (imports)** — this loads spaCy, KeyBERT, YAKE. It prints confirmation lines when ready.
4. Then you can run the remaining cells one by one, or use **Run All** for the rest.

> **Why not Run All from the start?** The install cell sometimes causes a kernel restart which interrupts the run. Running cells 1 and 2 manually first avoids this.

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'spacy'" (or any other package)

The notebook is using a different Python than the one where you installed packages.
**Fix:** Check the kernel selector (top-right corner). Make sure it shows `.venv`, not the system Python.

### "No module named 'en_core_web_trf'"

The spaCy model download didn't finish or was installed in a different Python.
**Fix:** With your `.venv` activated in the terminal, run:
```bash
python -m spacy download en_core_web_trf
```
Or the smaller model:
```bash
python -m spacy download en_core_web_sm
```

### Kernel keeps dying / restarting

Usually caused by running out of memory. The transformer model (`en_core_web_trf`) is large (~500 MB).
**Fix (option A):** Close other applications to free RAM.
**Fix (option B):** Use the smaller model. In the terminal:
```bash
python -m spacy download en_core_web_sm
```
The notebook automatically falls back to `en_core_web_sm` if `en_core_web_trf` fails to load.

### "Executing script is disabled" (Windows PowerShell)

Run this once in PowerShell as your regular user (not as administrator):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### pip installs succeed but packages still not found

You probably ran `pip install` without the venv activated (missing the `(.venv)` prefix in the terminal).
**Fix:**
```bash
# Activate first
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\Activate.ps1    # Windows

# Then reinstall
pip install spacy keybert yake sentence-transformers nltk dateparser
```

### "NLTK punkt not found" error

Run this in the terminal with the venv activated:
```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"
```

### VSCode doesn't show the `.venv` kernel option

- Make sure you opened the **folder** in VSCode (File → Open Folder), not just the notebook file.
- The `.venv` folder must be inside that opened folder.
- Try `Ctrl+Shift+P` → `Developer: Reload Window` and check the kernel list again.

---

## Quick reference — all terminal commands in order

```bash
# 1. Create venv (do this once)
python -m venv .venv                        # Windows
python3 -m venv .venv                       # macOS/Linux

# 2. Activate venv (do this every new terminal session)
.venv\Scripts\Activate.ps1                  # Windows
source .venv/bin/activate                   # macOS/Linux

# 3. Install Python packages (do this once)
pip install spacy keybert yake sentence-transformers nltk dateparser

# 4. Download spaCy model (do this once)
python -m spacy download en_core_web_trf    # preferred
python -m spacy download en_core_web_sm     # fallback if above fails

# 5. Download NLTK data (do this once)
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"
```

After these five steps: open the notebook in VSCode, select the `.venv` kernel, and run the cells.
