# Development workflow

- This Git working tree is the sole maintained source directory. Do not mirror changes into historical download copies.
- The project is distributed as source and launched with `start.bat` after installing Python and dependencies. Do not build or upload exe/portable packages as a normal development or release step.
- Historical packaging scripts and provenance documents remain for reference; they are not the current release workflow.
- Include a ready-to-copy Summary and Description with every version update. Record meaningful changes and the actual validation performed.
- Keep user settings, keys, browser profiles, certificates, models, local environments and machine-specific notes out of Git. Do not overwrite them with example defaults.
- Use checks appropriate to the change. Documentation-only changes need publication/link checks, not a complete game or packaging test run.

See `docs/WORKSPACE.md`, `docs/INSTALL.md` and `docs/PUBLISHING.md` for the current workflow.
