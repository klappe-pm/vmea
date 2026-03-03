"""Tests for VMEA CLI helpers."""

from vmea.cli import parse_ollama_model_list


def test_parse_ollama_model_list_reads_model_names() -> None:
    output = """NAME                    ID              SIZE      MODIFIED
llama3.2:3b             abc123          2.0 GB    2 days ago
nomic-embed-text:latest def456          274 MB    3 days ago
"""

    assert parse_ollama_model_list(output) == [
        "llama3.2:3b",
        "nomic-embed-text:latest",
    ]


def test_parse_ollama_model_list_skips_blank_lines() -> None:
    output = "\n\nNAME ID SIZE MODIFIED\n\nllama3.2:3b abc 2GB now\n"

    assert parse_ollama_model_list(output) == ["llama3.2:3b"]
