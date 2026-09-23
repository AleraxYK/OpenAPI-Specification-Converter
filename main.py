import os

import yaml
import json

from pdf_generator import generate_pdf


def get_pdf(file_path, json_conversion=False):
    print("CONVERTING...")

    with open(file_path, encoding="utf-8") as stream:
        if not json_conversion:
            spec = yaml.safe_load(stream)
        else:
            spec = json.load(stream)

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    pdf_path = f"{base_name}.pdf"

    generate_pdf(spec, pdf_path)

    print("CONVERSION COMPLETE")
    print(f"Output: {pdf_path}")

    return


def main():
    print("Welcome to OpenAPI Specification Converter")
    print()
    print("PRESS:")
    print("0 = EXIT")
    print("1 = YAML to PDF")
    print("2 = JSON to PDF")
    n = input()
    print("ENTER THE PATH OF THE FILE TO CONVERT")
    file_path = input()
    match n:
        case "0":
            exit()
        case "1":
            get_pdf(file_path, json_conversion=False)
        case "2":
            get_pdf(file_path, json_conversion=True)

    return

if __name__ == "__main__":
    main()
