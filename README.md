# JobAgent AI

Multi-agent job search automation platform. Users bring their own AI API keys.

## Quick Start

```bash
cp .env.example .env
# Fill in .env values
make dev
```

Frontend: http://localhost:3000
Backend API docs: http://localhost:8000/docs

## Development

```bash
make test       # unit tests
make lint       # lint check
make format     # auto-format
```

See `docs/` for architecture decisions and implementation plans.
