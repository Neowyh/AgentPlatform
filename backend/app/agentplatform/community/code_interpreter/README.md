# Code Interpreter Tool

Executes Python or JavaScript code in an isolated sandbox and returns stdout/stderr.

## Capabilities

- Python execution (python3) -- pandas, matplotlib, numpy pre-installed
- JavaScript execution (node)
- Automatic output truncation (middle-truncate, 20 000 char limit)
- Configurable timeout (default 60 s, max 300 s)

## Configuration

```yaml
tool_groups:
  - name: code

tools:
  - name: code_interpreter
    group: code
    use: ideer.community.code_interpreter.tools:code_interpreter_tool
```

## Usage

The tool accepts `code` (required), `language` (`"python"` or `"javascript"`, default `"python"`), and `timeout` (seconds). Returns a JSON object with `stdout`, `stderr`, and `exit_code`.
