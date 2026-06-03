# Data Analyzer Tool

Analyzes structured data files and produces statistical insights.

## Supported Formats

- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)
- JSON (`.json`, including line-delimited)

## Analysis Types

- `summary` -- row/column counts, dtypes, missing values, first 5 rows
- `describe` -- statistical summary of numeric columns, value counts for categorical
- `correlation` -- correlation matrix for numeric columns, strong-correlation highlights

## Configuration

```yaml
tool_groups:
  - name: code

tools:
  - name: data_analyzer
    group: code
    use: ideer.community.data_analyzer.tools:data_analyzer_tool
```

## Usage

The tool accepts `file_path` (required) and `analysis_type` (default `"summary"`). Output is JSON-truncated at 10 000 characters.
