# Commit Style

Use the local repository history as the first authority. The default pattern is:

```text
<optional gitmoji> <type>: <한글 요약>
```

- Use lowercase English types followed by `: `.
- Write a concrete one-line Korean summary of the change's purpose.
- Keep each commit small and independently reviewable.

Core patterns:

- `:sparkles: feat:` new behavior or API
- `:bug: fix:` bug fix
- `:recycle: refactor:` behavior-preserving restructuring
- `:white_check_mark: test:` test-only change
- `:fire: remove:` removal-only change
- `:memo: docs:` documentation
- `:card_file_box: db:` schema, index, or migration
