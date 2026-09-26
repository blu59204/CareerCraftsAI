# Self-hosted Laya decision server

The CareerCraft extension asks small typed questions while filling forms
(which option matches, which button advances, did the submit succeed). The
backend answers them with a "System One" decision model:

- **Jev** (TypeSafe, hosted) — set `TYPESAFE_API_KEY`, or
- **Laya** (open source, self-hosted) — run this server and set `LAYA_URL`,
- neither — built-in heuristics.

## Run

```bash
docker build -t careercraft-laya deploy/laya
docker run -p 8088:8088 -e LAYA_API_KEY=change-me \
  -v laya-cache:/root/.cache/huggingface careercraft-laya
```

Then in `backend/.env`:

```bash
DECISION_ENGINE_PROVIDER=auto      # or laya
LAYA_URL=http://laya:8088          # as the backend container sees it
LAYA_API_KEY=change-me
```

A GPU is not required but keeps latency in the tens of milliseconds; on CPU
expect a few hundred. The first start downloads the model weights.

## Notes

- The endpoint mirrors Jev's `POST /v1/systemone` (`state` + `questions`
  with `choice` / `score` / `noul`), so the backend treats both the same.
- Laya's authors report weak zero-shot accuracy on some decision benchmarks
  and recommend fine-tuning; choice questions degrade past ~20 options.
  CareerCraft only acts above `DECISION_ENGINE_MIN_CONFIDENCE` (0.6) and
  otherwise leaves the question to the user.
- This wrapper was not run in CI (the `laya` package pulls PyTorch); check
  `curl localhost:8088/health` and one request after deploying.
