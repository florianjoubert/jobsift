# Private connectors

This folder lets you add **unpublished** job sources to jobsift, without touching
the main code and without risking committing sensitive data.

## How it works

Any `*.py` file dropped here is **auto-discovered** and loaded by
`app/connectors/registry.py` at pipeline startup. The folder is fully gitignored
(except this file and `example_connector.py.example`), so your connector stays local.

> ⚠️ A file placed here is **executed with the app's full privileges** at startup.
> Only put code you trust here - it's your own local plugin folder.

## Adding a connector

1. Copy the template:

   ```bash
   cp connectors_private/example_connector.py.example connectors_private/my_source.py
   ```

2. Implement the `Connector` class in `my_source.py`:

   - `name: str` attribute - unique identifier shown in the logs.
   - `fetch(self, criteria: SearchCriteria) -> list[Job]` method - returns
     `Job` objects with `source=JobSource.private`.
   - Never raise: log errors and return `[]`.

3. Run the pipeline to verify:

   ```bash
   uv run python -m app.cli
   # → logs: "Private connector loaded: my_source"
   ```

## Expected structure

```python
from app.connectors.base import SearchCriteria
from app.schemas.job import Job, JobSource

class Connector:
    name = "my_source"

    def fetch(self, criteria: SearchCriteria) -> list[Job]:
        ...
        return []
```

See `example_connector.py.example` for a complete commented skeleton.
