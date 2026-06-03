# Document Reader Tool

Extracts text from office documents and converts them to Markdown for agent consumption.

## Supported Formats

- PDF (`.pdf`) -- with optional page-range selection via pymupdf4llm
- Word (`.docx`, `.doc`)
- Excel (`.xlsx`, `.xls`)
- PowerPoint (`.pptx`, `.ppt`)

## Configuration

```yaml
tool_groups:
  - name: document

tools:
  - name: read_document
    group: document
    use: ideer.community.doc_reader.tools:read_document_tool
```

## Usage

The tool accepts a `file_path` argument and an optional `page_range` (PDF only, e.g. `"1-5"` or `"1-3,7"`). Output is truncated to 50 000 characters by default.
