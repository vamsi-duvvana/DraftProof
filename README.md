# DraftProof

DraftProof is a Python application for rule-based document rewriting, code comment editing, citation generation, pairwise similarity analysis, and text/Word metadata inspection. It includes a Streamlit web interface and a command-line pipeline. Text transformations run locally without a generative AI API key.

## Requirements

- Python 3.9 or newer (Python 3.11+ recommended)
- Git
- Run commands from the cloned repository folder. Keep `rules/` alongside the source: the application loads these JSON files at runtime.

## Install

1. Clone the public repository and enter its directory:

   ```bash
   git clone https://github.com/vamsi-duvvana/DraftProof.git
   cd DraftProof
   ```

2. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows PowerShell, use `python -m venv .venv`, then `.venv\Scripts\Activate.ps1`.

3. Install the application and its runtime dependencies:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -e .
   ```

   No `.env` file or API key is required for local use. The editable install makes the `draftproof` package and command available while retaining access to the repository's rule files.

## Run the web application

```bash
python -m streamlit run streamlit_app.py --server.port 8501
```

Open [localhost:8501](http://localhost:8501) in your browser. Stop the server with `Ctrl+C` in the terminal.

### Rewrite a document

1. Select **Plagiarism & AI Remover** in the sidebar.
2. Choose the format, style preset, and intensity. Leave citation insertion off unless needed.
3. Paste text into **Original Text Area**, or use the file upload section for `.tex`, `.docx`, `.md`, `.txt`, or `.zip` documents.
4. Click **Humanize Text** for pasted text, or **Process & Humanize Uploaded Files** for uploads.
5. Review the output and change statistics, then copy the text or download the available output package.

### Other pages

- **Code Comment Humanizer:** choose a language and developer persona, paste or upload source files, process them, and review/download the result.
- **Citation Inserter & BIB/JSON:** paste text or upload a Word file, choose a discipline, style, and count, then generate citations and download BibTeX, LaTeX, or JSON references.
- **Pairwise Document Similarity:** enter the source and target documents (or upload Word files), then run the similarity audit. The page also offers a heuristic AI signal audit.
- **Voice Matcher & Watermark Lab:** inspect text for Unicode/hash signals and activate a writing profile from a sample. Word metadata cleanup is also available in document processing.
- **Feature Request & Bug Reporter:** generate an issue package and follow the GitHub issue link to submit it.

## Use the CLI

After activating the virtual environment and installing the app, preview the built-in sample:

```bash
draftproof --dry-run --verbose
```

Process one UTF-8 text, Markdown, or LaTeX file and write a separate output file:

```bash
draftproof --input paper_input/manuscript.tex --output paper_output/manuscript.tex --preset academic --intensity 60
```

Create `paper_input/manuscript.tex` yourself before running that example. The CLI currently processes a single text file; use the web interface for Word documents, ZIP archives, and batch uploads. A missing input path currently falls back to the built-in sample, so check the console's loaded-input message.

Preview your file without saving changes:

```bash
draftproof --input paper_input/manuscript.tex --preset academic --intensity 60 --dry-run --verbose
```

Show all options:

```bash
draftproof --help
```

You can also run the same CLI with `python run.py`. Available options include `--config path/to/config.json`, `--citations IEEE`, and `--disable-stages voice,fusion,transition`. The CLI writes transformed text; use the citation web page for companion bibliography downloads.

## Deploy on Vercel

Import this GitHub repository into your Vercel account, select `master` as the production branch, and deploy from the repository root. Vercel detects `Dockerfile.vercel`, builds the Python container, and routes traffic to Streamlit on port 80. Leave build and output directory overrides unset. No AI SDK or API key is required.

The container runtime is a Vercel beta feature. Sessions live in container memory and can reset when an instance restarts or scales down. Vercel's function connection duration and upload size limits also apply; keep local copies of documents and downloaded results. Local secrets, test files, and input/output folders are excluded from the container build context.

## Configuration

- `rules/global_config.json`: global defaults, stage settings, and traffic routing.
- `configs/global_config.json`: fallback global configuration.
- `rules/academic/`, `rules/conversational/`, and `rules/code/`: dictionaries and presets.
- `.streamlit/config.toml`: web server behavior and appearance.
- `ARCHITECTURE_RULES.md`: source organization and rule maintenance guidelines.

The CLI accepts a custom JSON file through `--config`. Supported environment overrides are defined in `src/draftproof/config.py`, including `DRAFTPROOF_SEED` and `DRAFTPROOF_STYLE_PRESET`; CLI flags override their corresponding settings. The application does not automatically load `.env` files. If the web app shows a worker-routing card, remove `?test_card=1` from the URL and check that `traffic_balancing.enable_offload` is `false` in the global configuration for local use.

## Branches and tests

- **`master`**: default application branch; test files are omitted.
- **`dev`**: application source plus the automated test suite.

To develop and run tests:

```bash
git switch dev
python -m pip install -e '.[dev]'
python -m pytest -v tests/
```

Return to the application branch with `git switch master`. Keep test changes on `dev`; when promoting application changes, review the diff so test files are not copied to `master`.

## Limitations

AI and watermark scores are local heuristics, not validated detector results or guarantees about external services. Citation entries are generated from local topic/author pools rather than retrieved from a verified scholarly database; verify every reference and DOI before using it. Review rewritten text and code before relying on the output, and keep original documents. The optional GitHub profile check contacts GitHub; external links open third-party services.

Local `.env` files, Streamlit secrets, virtual environments, caches, and input/output folders are excluded from Git.
