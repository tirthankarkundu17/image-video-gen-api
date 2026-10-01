#!/usr/bin/env python3
"""
Utility script to decode a base64 string and save it to an output file (video, image, etc.).

Usage:
    # 1. From an input file containing base64 data:
    python base64-to-file.py -i video_base64.txt -o generated_video.mp4

    # 2. From standard input (pipe):
    cat video_base64.txt | python base64-to-file.py -o generated_video.mp4

    # 3. From command-line argument:
    python base64-to-file.py -d "AAAAHGZ0eXBtcDQy..." -o output.mp4

    # 4. Interactive prompt (if no flags are provided):
    python base64-to-file.py
"""

import argparse
import base64
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple


def strip_data_uri_prefix(b64_data: str) -> Tuple[str, Optional[str]]:
    """
    Strips data URI prefix if present (e.g. 'data:video/mp4;base64,....')
    and returns (cleaned_base64_string, mime_type_or_none).
    """
    b64_data = b64_data.strip()
    data_uri_match = re.match(r"^data:([^;]+);base64,(.*)$", b64_data, re.DOTALL | re.IGNORECASE)
    if data_uri_match:
        mime_type = data_uri_match.group(1).lower()
        clean_b64 = data_uri_match.group(2)
        return clean_b64, mime_type
    return b64_data, None


def infer_extension_from_mime(mime_type: Optional[str]) -> str:
    """Infers file extension from MIME type."""
    mime_map = {
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "application/pdf": ".pdf",
    }
    return mime_map.get(mime_type or "", "")


def base64_to_file(b64_input: str, output_path: str | Path) -> Path:
    """
    Decodes a base64 string and writes the raw binary content to the target file.

    Args:
        b64_input: The base64-encoded string (with or without 'data:...;base64,' prefix).
        output_path: Destination file path.

    Returns:
        Path: The absolute path of the written file.
    """
    cleaned_b64, mime = strip_data_uri_prefix(b64_input)

    # Clean whitespace and newlines
    cleaned_b64 = re.sub(r"\s+", "", cleaned_b64)

    # Fix base64 padding if needed
    missing_padding = len(cleaned_b64) % 4
    if missing_padding:
        cleaned_b64 += "=" * (4 - missing_padding)

    try:
        raw_bytes = base64.b64decode(cleaned_b64, validate=False)
    except Exception as exc:
        raise ValueError(f"Failed to decode base64 data: {exc}") from exc

    dest = Path(output_path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    dest.write_bytes(raw_bytes)
    return dest


def parse_args():
    parser = argparse.ArgumentParser(
        description="Decode a Base64 string into a binary file (MP4, PNG, JPG, etc.)."
    )
    parser.add_argument(
        "-i",
        "--input-file",
        type=str,
        help="Path to a text file containing the base64 string.",
    )
    parser.add_argument(
        "-d",
        "--data",
        type=str,
        help="Direct base64 string passed as a CLI argument.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="output.mp4",
        help="Output destination path (default: 'output.mp4').",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    b64_text = None

    # Priority 1: Direct command-line argument
    if args.data:
        b64_text = args.data

    # Priority 2: Input text file
    elif args.input_file:
        input_path = Path(args.input_file)
        if not input_path.is_file():
            print(f"Error: Input file not found at '{args.input_file}'", file=sys.stderr)
            sys.exit(1)
        b64_text = input_path.read_text(encoding="utf-8")

    # Priority 3: Standard input (piped or redirected)
    elif not sys.stdin.isatty():
        b64_text = sys.stdin.read()

    # Priority 4: Interactive prompt
    else:
        print("=== Base64 to File Converter ===")
        print("Enter or paste the base64 string (or press Enter to specify an input file):")
        user_input = input("> ").strip()

        if not user_input:
            file_prompt = input("Enter path to base64 text file: ").strip()
            if not file_prompt or not os.path.isfile(file_prompt):
                print("Error: Valid file path was not provided.", file=sys.stderr)
                sys.exit(1)
            b64_text = Path(file_prompt).read_text(encoding="utf-8")
        else:
            b64_text = user_input

        out_prompt = input(f"Enter output file path [default: {args.output}]: ").strip()
        if out_prompt:
            args.output = out_prompt

    if not b64_text or not b64_text.strip():
        print("Error: No base64 content provided.", file=sys.stderr)
        sys.exit(1)

    try:
        saved_path = base64_to_file(b64_text, args.output)
        file_size_kb = saved_path.stat().st_size / 1024
        print(f"Successfully decoded and wrote {file_size_kb:.2f} KB to:\n  {saved_path}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
