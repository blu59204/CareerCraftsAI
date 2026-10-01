from types import SimpleNamespace

from app.services.auto_apply_queue import pick_candidates


def _app(score, url="https://boards.greenhouse.io/acme/jobs/1"):
    return SimpleNamespace(match_score=score, job_url=url)


def test_best_scores_first_and_only_above_the_threshold():
    apps = [_app(60), _app(95), _app(70), _app(None), _app(80)]
    assert [a.match_score for a in pick_candidates(apps, 3, 70)] == [95, 80, 70]


def test_jobs_without_a_real_url_are_never_queued():
    apps = [_app(99, None), _app(99, "https://example.com/mock"), _app(90)]
    assert [a.match_score for a in pick_candidates(apps, 5, 70)] == [90]


def test_no_room_means_nothing_is_queued():
    assert pick_candidates([_app(99)], 0, 70) == []
