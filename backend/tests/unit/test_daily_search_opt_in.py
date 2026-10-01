"""The scheduled daily search is opt-in and searches only what members saved."""

import inspect

from sqlalchemy.dialects import postgresql

from app.services import scheduled_jobs


def test_only_opted_in_members_with_saved_roles_are_eligible():
    sql = str(scheduled_jobs._daily_search_eligible_ids().compile(dialect=postgresql.dialect()))
    assert "user_preferences.daily_search_enabled" in sql
    assert "user_model_settings.is_active" in sql
    assert "user_preferences.target_roles IS NOT NULL" in sql
    assert "deletion_scheduled_for IS NULL" in sql


def test_daily_search_never_invents_a_role_or_location():
    src = inspect.getsource(scheduled_jobs.daily_search)
    assert "Bangalore" not in src
    assert "software engineer" not in src


def test_preferences_accept_the_opt_in():
    from app.models.schemas import UserPreferencesSchema

    assert UserPreferencesSchema(daily_search_enabled=True).daily_search_enabled is True
    assert "daily_search_enabled" not in UserPreferencesSchema().model_dump(exclude_none=True)
