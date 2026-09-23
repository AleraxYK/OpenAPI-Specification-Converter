# OpenAPI Specification Converter

A small Python tool that converts an OpenAPI specification (YAML or JSON) into a clean, Swagger UI-style PDF document.

It parses the spec and renders a formatted PDF including:

- A cover page with the API title, version, description, and servers list
- Endpoints grouped by tags, each on its own page
- Request parameters, request bodies, and responses (with status code badges)
- Recursively rendered schemas, including resolved `$ref` references, required fields, enums, and examples
- A dedicated "Schemas" section listing all reusable component schemas

## Requirements

- Python 3
- Dependencies listed in `requirements.txt`:
  - [WeasyPrint](https://weasyprint.org/) (HTML to PDF rendering)
  - [Markdown](https://python-markdown.org/) (renders Markdown descriptions in the spec)
  - [PyYAML](https://pyyaml.org/) (YAML parsing)

> **Note:** WeasyPrint depends on system libraries (Pango, Cairo, GDK-PixBuf, etc.). See the [WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation) if you run into issues installing it on your OS.

## Installation

```bash
git clone https://github.com/AleraxYK/OpenAPI-Specification-Converter.git
cd OpenAPI-Specification-Converter
pip install -r requirements.txt
```

## Usage

Run the converter:

```bash
python main.py
```

You'll be prompted to choose the input format and the path to your file:

```
Welcome to OpenAPI Specification Converter

PRESS:
0 = EXIT
1 = YAML to PDF
2 = JSON to PDF
1
ENTER THE PATH OF THE FILE TO CONVERT
./openapi.yaml
```

The generated PDF is saved in the current directory, named after the input file (e.g. `openapi.yaml` → `openapi.pdf`).

## Project structure

- [main.py](main.py) — CLI entry point, handles user input and file loading
- [pdf_generator.py](pdf_generator.py) — builds the HTML representation of the spec and renders it to PDF via WeasyPrint

