"""The member's auto-apply rule: threshold, per-action dispatch, no re-fire,
and the user-triggered outreach endpoint (ownership + action_log)."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import auto_apply_queue as q


def _app(score, **kw):
    return SimpleNamespace(
        id=uuid.uuid4(),
        match_score=score,
        job_url="https://boards.greenhouse.io/acme/jobs/1",
        company="Acme",
        role="Dev",
        jd_text="",
        resume_id=None,
        **kw,
    )


def test_threshold_is_the_members_not_the_fixed_setting():
    jobs = [_app(55), _app(65), _app(90)]
    out = q.plan(jobs, set(), set(), "notify", 60, 3)
    assert [a.match_score for a in out["notify"]] == [90, 65]


def test_apply_never_goes_below_the_reservation_floor():
    jobs = [_app(55), _app(90)]
    out = q.plan(jobs, set(), set(), "apply", 40, 3)
    assert [a.match_score for a in out["auto_apply"]] == [90]


def test_steps_per_action():
    assert list(q.plan([], set(), set(), "apply", 70, 3)) == ["auto_apply"]
    assert list(q.plan([], set(), set(), "outreach", 70, 3)) == ["outreach_queued"]
    assert list(q.plan([], set(), set(), "both", 70, 3)) == ["auto_apply", "outreach_queued"]
    assert list(q.plan([], set(), set(), "notify", 70, 3)) == ["notify"]


def test_logged_or_attempted_jobs_do_not_fire_again():
    done, attempted, fresh = _app(90), _app(90), _app(90)
    logged = {(done.id, "outreach_queued"), (done.id, "notify")}
    out = q.plan([done, attempted, fresh], logged, {attempted.id}, "both", 70, 5)
    assert {a.id for a in out["outreach_queued"]} == {attempted.id, fresh.id}
    assert {a.id for a in out["auto_apply"]} == {done.id, fresh.id}
    # a different action's log row does not suppress this one
    assert {a.id for a in q.plan([done], logged, set(), "apply", 70, 5)["auto_apply"]} == {done.id}
    assert q.plan([done], logged, set(), "notify", 70, 5)["notify"] == []


@pytest.fixture
def wired(monkeypatch):
    calls = SimpleNamespace(apply=[], outreach=[], notify=[], log=[])
    rule = {"min_match": 80, "action": "both", "template": "classic", "page_target": 1,
            "tailor": True, "tone": "concise"}
    state = SimpleNamespace(rule=rule, jobs={}, outreach_state="draft")

    async def load_rule(_):
        return state.rule

    async def candidates(*_):
        return state.jobs

    async def apply_one(owner, application, r):
        calls.apply.append((application.id, r["template"]))
        return True

    async def draft(user_id, application):
        calls.outreach.append(application.id)
        return state.outreach_state

    async def notify(owner, jobs, minimum):
        calls.notify.append((len(jobs), minimum))

    async def log(owner, app_id, action, detail):
        calls.log.append((app_id, action))

    for name, fn in [("load_rule", load_rule), ("_candidates", candidates),
                     ("_apply_one", apply_one), ("draft_outreach", draft),
                     ("_notify", notify), ("_log", log)]:
        monkeypatch.setattr(q, name, fn)
    return state, calls


async def test_both_dispatches_apply_and_outreach_and_logs_each(wired):
    state, calls = wired
    job = _app(95)
    state.jobs = {"auto_apply": [job], "outreach_queued": [job]}
    result = await q.queue_for_member(str(uuid.uuid4()))
    assert result == {"queued": 2, "skipped": 0}
    assert calls.apply == [(job.id, "classic")] and calls.outreach == [job.id]
    assert calls.log == [(job.id, "auto_apply"), (job.id, "outreach_queued")]
    assert calls.notify == []


async def test_notify_sends_one_notification_and_logs_every_job(wired):
    state, calls = wired
    jobs = [_app(90), _app(85)]
    state.jobs = {"notify": jobs}
    await q.queue_for_member(str(uuid.uuid4()))
    assert calls.notify == [(2, 80)] and calls.apply == [] and calls.outreach == []
    assert calls.log == [(j.id, "notify") for j in jobs]


async def test_outreach_without_contact_is_skipped_but_logged_once(wired):
    state, calls = wired
    job = _app(90)
    state.outreach_state = None
    state.jobs = {"outreach_queued": [job]}
    assert await q.queue_for_member(str(uuid.uuid4())) == {"queued": 0, "skipped": 1}
    assert calls.log == [(job.id, "outreach_queued")]


async def test_paused_rule_does_nothing(wired):
    state, calls = wired
    state.rule = None
    state.jobs = {"auto_apply": [_app(99)]}
    assert await q.queue_for_member(str(uuid.uuid4())) == {"queued": 0, "skipped": 0}
    assert calls.apply == [] and calls.log == []


async def test_failed_apply_is_not_logged_and_does_not_stop_others(wired, monkeypatch):
    state, calls = wired
    a, b = _app(95), _app(90)
    state.jobs = {"auto_apply": [a, b]}

    async def flaky(owner, application, r):
        if application is a:
            raise RuntimeError("boom")
        return True

    monkeypatch.setattr(q, "_apply_one", flaky)
    assert await q.queue_for_member(str(uuid.uuid4())) == {"queued": 1, "skipped": 1}
    assert calls.log == [(b.id, "auto_apply")]


async def test_outreach_endpoint_only_touches_owned_jobs_and_logs_user_source(monkeypatch):
    from app.api.v1 import jobs

    owner = SimpleNamespace(id=uuid.uuid4())
    mine, no_contact = _app(90), _app(90)
    foreign_id = uuid.uuid4()
    seen = {}

    async def owned(db, user_id, ids, **kw):
        seen["user_id"], seen["ids"] = user_id, ids
        return [a for a in (mine, no_contact) if a.id in ids]  # foreign id is filtered out

    async def draft(user_id, application):
        return "draft" if application is mine else None

    monkeypatch.setattr(jobs, "_owned_applications", owned)
    monkeypatch.setattr("app.services.auto_apply_queue.draft_outreach", draft)
    db = MagicMock()
    db.commit = AsyncMock()
    body = jobs.OutreachBody(ids=[mine.id, no_contact.id, foreign_id])

    result = await jobs.queue_applications_outreach.__wrapped__(body, None, db, owner)

    assert seen["user_id"] == owner.id
    assert result == {"queued": [str(mine.id)], "skipped": [str(no_contact.id)]}
    logs = [c.args[0] for c in db.add.call_args_list]
    assert [(x.job_application_id, x.source, x.action) for x in logs] == [
        (mine.id, "user", "outreach_queued"),
        (no_contact.id, "user", "outreach_queued"),
    ]
