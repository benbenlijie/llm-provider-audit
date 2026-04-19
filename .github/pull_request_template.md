## Summary

- What changed?
- Why was this change needed?

## Validation

- [ ] `python3 -m py_compile $(find "src" -name '*.py' | sort) $(find "tests" -name '*.py' | sort)`
- [ ] `uv run python -m unittest discover -s "tests" -v`
- [ ] I verified no secrets, local paths, or private endpoints were introduced

## Scope

- [ ] CLI behavior
- [ ] Public config templates
- [ ] Prompt suites
- [ ] Reporting
- [ ] Documentation only

## Notes

- Anything reviewers should focus on
- Follow-up work or known limitations
