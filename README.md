# vce2flashquiz

A conversion utility designed to bridge the gap between VCE (Visual CertExam) exports and [obsidian-cbt-exam](https://github.com/nazdridoy/obsidian-cbt-exam). This tool transforms PDF source files into professional, human-readable [FlashQuiz](https://github.com/nazdridoy/obsidian-cbt-exam/blob/main/FLASHQUIZ_SPEC.md) markdown format compatible with the Obsidian CBT Exam Simulator.

## Workflow

1.  **Extract**: Export your VCE exam as a PDF.
2.  **Convert**: Run `vce2flashquiz` to generate a structured markdown file.
3.  **Simulate**: Drop the generated file into your Obsidian vault and start your exam using the [CBT Exam Simulator](https://github.com/nazdridoy/obsidian-cbt-exam).

## Features

- **Automated PDF Parsing**: Extracts questions, options, and correct answers directly from PDF exports.
- **Self-Contained Exhibits**: Automatically identifies "Exhibits," extracts the images, and embeds them as Base64 strings for maximum portability.
- **Type Intelligence**: 
    - Automatically detects Multiple Choice (`@mc`), Select All That Apply (`@sata`), and True/False (`@tf`) formats.
    - Handles concatenated answer strings (e.g., `ABCD` → `a, b, c, d`).
- **Obsidian Ready**: Generates required YAML frontmatter with optimized defaults (shuffling, pass scores, and timers).

## Setup

### Using uv (Recommended)

This project uses `uv` for lightning-fast dependency management.

```bash
# Clone the repository
git clone https://github.com/nazdridoy/vce2flashquiz.git
cd vce2flashquiz

# Install dependencies
uv sync
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/nazdridoy/vce2flashquiz.git
cd vce2flashquiz

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Show Help

```bash
uv run vce2flashquiz.py -h
```

### Single File (output to stdout)

```bash
# Using uv
uv run vce2flashquiz.py source.pdf > quiz.md

# Using python
python vce2flashquiz.py source.pdf > quiz.md
```

### Batch Convert Directory

Process all PDFs in a directory at once. Creates a `.md` file alongside each PDF:

```bash
# Using uv
uv run vce2flashquiz.py /path/to/pdfs/

# Using python
python vce2flashquiz.py /path/to/pdfs/
```

This will convert `exam1.pdf`, `exam2.pdf`, etc. into `exam1.md`, `exam2.md`, etc.

Place the resulting `.md` files in your Obsidian vault and open them with the **CBT Exam Simulator** plugin.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
