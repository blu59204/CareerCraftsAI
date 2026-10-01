"""Every tone the UI offers changes the request the model sees."""

from app.agents.prompts.cover_letter_prompt import TONE_GUIDE, VALID_TONES, build_user_prompt


def test_each_tone_produces_a_different_instruction():
    prompts = {tone: build_user_prompt({"tone": tone, "jd_text": "x"}) for tone in VALID_TONES}
    assert len(set(prompts.values())) == len(VALID_TONES)


def test_concise_overrides_the_default_length_and_story_asks_for_a_moment():
    assert "180 words" in TONE_GUIDE["concise"]
    assert "concrete moment" in TONE_GUIDE["story"]


def test_unknown_tone_falls_back_to_formal():
    assert TONE_GUIDE["formal"] in build_user_prompt({"tone": "sarcastic", "jd_text": "x"})
