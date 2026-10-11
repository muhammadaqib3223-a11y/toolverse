"""CV Generator "Improve with AI": suggestions, honesty checks, privacy and daily limits.
Uses the fake AI provider and fake limits only (tests/fakes.py), never Gemini or Supabase."""
import pytest

from app.services.ai.base import AIBlocked, AIQuotaExceeded, AIUnavailable

GUEST_IP = "203.0.113.20"


def _cv(**overrides):
    cv = {
        "personal": {"full_name": "Sara Khan", "email": "sara@example.com", "phone": "+92 300 1234567",
                     "website": "sara.dev", "headline": "sales wali job", "location": "Lahore"},
        "summary": "main 2 saal se sales mein kaam kar rahi hoon",
        "experience": [
            {"job_title": "Sales girl", "company": "Khaadi", "start": "2023", "current": True,
             "description": "customers ko handle kiya, daily 30 customers, cash counter bhi chalaya"},
            {"job_title": "", "company": "", "description": ""},
            {"job_title": "Intern", "company": "Daraz", "start": "2022", "end": "2022", "description": ""},
        ],
        "skills": ["ms excel", "baat cheet achi hai"],
    }
    cv.update(overrides)
    return cv


def _improve(client, section, cv=None, index=None, ip=GUEST_IP, url="/api/cv-generator/improve"):
    body = {"section": section, "cv": cv if cv is not None else _cv()}
    if index is not None:
        body["index"] = index
    return client.post(url, json=body, environ_base={"REMOTE_ADDR": ip})


# ── Suggestions per section ─────────────────────────────────────────────────

def test_summary_suggestion(client, ai_provider):
    ai_provider.result = {"summary": "Sales associate with 2 years of retail experience. Calm and friendly with customers."}
    response = _improve(client, "summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["suggestion"] == {"summary": "Sales associate with 2 years of retail experience. Calm and friendly with customers."}
    assert data["removed"] == 0
    assert data["limit"] == 3 and data["remaining"] == 2


def test_experience_suggestion_is_bullets_for_that_job(client, ai_provider):
    ai_provider.result = {"bullets": ["Served around 30 customers daily", "• Operated the cash counter", "  "]}
    response = _improve(client, "experience", index=0)
    assert response.status_code == 200
    assert response.get_json()["suggestion"] == {
        "index": 0,
        "description": "- Served around 30 customers daily\n- Operated the cash counter",
    }
    prompt = ai_provider.calls[0]["prompt"]
    assert "<job_to_improve>" in prompt and "customers ko handle kiya" in prompt


def test_skills_must_quote_the_cv(client, ai_provider):
    ai_provider.result = {"skills": [
        {"name": "MS Excel", "source": "ms excel"},
        {"name": "Communication", "source": "baat cheet achi hai"},
        {"name": "Cash handling", "source": "cash counter bhi chalaya"},
        {"name": "Python", "source": "python"},             # not in the CV: invented
        {"name": "Leadership", "source": ""},               # no proof
        {"name": "ms excel", "source": "ms excel"},         # duplicate
    ]}
    response = _improve(client, "skills")
    assert response.get_json()["suggestion"] == {"skills": ["MS Excel", "Communication", "Cash handling"]}


def test_whole_cv_suggestion(client, ai_provider):
    ai_provider.result = {
        "headline": "Sales Associate",
        "summary": "Friendly sales associate. Increased sales by 40% in one month.",
        "experience": [
            {"bullets": ["Handled about 30 customers daily", "Ran the cash counter"]},
            {"bullets": ["Supported the operations team on 5 projects"]},  # job had no description
        ],
        "skills": [{"name": "MS Excel", "source": "ms excel"}],
    }
    response = _improve(client, "all")
    assert response.status_code == 200
    data = response.get_json()
    suggestion = data["suggestion"]
    assert suggestion["headline"] == "Sales Associate"
    # "40%" was never written by the user: that sentence is removed and counted.
    assert suggestion["summary"] == "Friendly sales associate."
    # Form positions are kept (the empty job in the middle is skipped); the Daraz job had no notes.
    assert suggestion["experience"] == [{"index": 0, "description": "- Handled about 30 customers daily\n- Ran the cash counter"}]
    assert suggestion["skills"] == ["MS Excel"]
    assert data["removed"] == 1


def test_whole_cv_with_mismatched_jobs_keeps_the_rest(client, ai_provider):
    ai_provider.result = {"headline": "Sales Associate", "summary": "Friendly.", "experience": [], "skills": []}
    suggestion = _improve(client, "all").get_json()["suggestion"]
    assert suggestion["experience"] == [] and suggestion["headline"] == "Sales Associate"


# ── Honesty checks ──────────────────────────────────────────────────────────

def test_new_numbers_are_removed_from_bullets(client, ai_provider):
    ai_provider.result = {"bullets": ["Served 30 customers a day", "Grew sales by 25%", "Saved Rs 10,000 a month"]}
    data = _improve(client, "experience", index=0).get_json()
    assert data["suggestion"]["description"] == "- Served 30 customers a day"
    assert data["removed"] == 2


def test_number_words_from_the_user_are_allowed(client, ai_provider):
    cv = _cv(summary="two years in sales")
    ai_provider.result = {"summary": "Sales associate with 2 years of experience."}
    assert _improve(client, "summary", cv=cv).get_json()["suggestion"]["summary"] == "Sales associate with 2 years of experience."


def test_answer_with_nothing_usable_is_an_error_and_refunded(client, ai_provider, ai_quota_repository):
    ai_provider.result = {"summary": "Boosted revenue by 300%."}
    response = _improve(client, "summary")
    assert response.status_code == 503
    assert response.get_json()["code"] == "ai_unavailable"
    assert ai_quota_repository.tries == {}


def test_contact_details_and_name_never_reach_the_ai(client, ai_provider):
    ai_provider.result = {"summary": "Sales associate."}
    _improve(client, "summary")
    sent = ai_provider.calls[0]["prompt"] + ai_provider.calls[0]["system"]
    for private in ("Sara Khan", "sara@example.com", "1234567", "sara.dev"):
        assert private not in sent


def test_invalid_email_does_not_block_ai_help(client, ai_provider):
    cv = _cv()
    cv["personal"]["email"] = "not-an-email"
    ai_provider.result = {"summary": "Sales associate."}
    assert _improve(client, "summary", cv=cv).status_code == 200


# ── Bad requests ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("section, cv, index, code", [
    ("poem", None, None, "section_invalid"),
    ("experience", None, 9, "invalid_data"),
    ("experience", None, "0", "invalid_data"),
    ("experience", None, 2, "nothing_to_improve"),          # Daraz job has no description
    ("summary", {"personal": {"full_name": "Sara"}}, None, "nothing_to_improve"),
    ("skills", {"personal": {}}, None, "nothing_to_improve"),
    ("summary", "text", None, "invalid_data"),
])
def test_bad_requests_use_no_try(client, ai_provider, ai_quota_repository, section, cv, index, code):
    response = _improve(client, section, cv=cv, index=index)
    assert response.status_code == 400
    assert response.get_json()["code"] == code
    assert ai_provider.calls == [] and ai_quota_repository.tries == {}


# ── Limits ──────────────────────────────────────────────────────────────────

def test_guest_limit(client, ai_provider):
    ai_provider.result = {"summary": "Sales associate."}
    for _ in range(3):
        assert _improve(client, "summary").status_code == 200
    response = _improve(client, "summary")
    assert response.status_code == 429
    assert response.get_json()["code"] == "limit_guest"


def test_user_limit_comes_from_config(client, app, log_in, ai_provider):
    app.config["CV_AI_USER_DAILY_LIMIT"] = 1
    log_in()
    ai_provider.result = {"summary": "Sales associate."}
    assert _improve(client, "summary").get_json()["limit"] == 1
    assert _improve(client, "summary").get_json()["code"] == "limit_user"


def test_cv_tries_are_separate_from_captions_but_share_the_site_limit(client, app, ai_provider, ai_quota_repository):
    ai_quota_repository.tries["x"] = ("captions", f"ip:{GUEST_IP}")
    ai_provider.result = {"summary": "Sales associate."}
    assert _improve(client, "summary").get_json()["remaining"] == 2  # captions tries don't count here
    app.config["AI_SITE_DAILY_LIMIT"] = 2
    assert _improve(client, "summary").get_json()["code"] == "site_limit"


@pytest.mark.parametrize("error, code, status", [
    (AIQuotaExceeded(), "ai_quota", 503),
    (AIUnavailable(), "ai_unavailable", 503),
    (AIBlocked(), "ai_blocked", 422),
])
def test_ai_failure_refunds_the_try(client, ai_provider, ai_quota_repository, error, code, status):
    ai_provider.error = error
    response = _improve(client, "summary")
    assert response.status_code == status
    assert response.get_json()["code"] == code
    assert ai_quota_repository.tries == {}


def test_limits_down_means_no_ai_call(client, ai_provider, ai_quota_repository):
    ai_quota_repository.unavailable = True
    response = _improve(client, "summary")
    assert response.status_code == 503
    assert ai_provider.calls == []


def test_usage(client, ai_provider):
    ai_provider.result = {"summary": "Sales associate."}
    _improve(client, "summary")
    response = client.get("/api/cv-generator/ai-usage", environ_base={"REMOTE_ADDR": GUEST_IP})
    assert response.get_json() == {"limit": 3, "used": 1, "remaining": 2}


def test_errors_are_translated(client, ai_provider):
    response = _improve(client, "poem", url="/ur/api/cv-generator/improve")
    assert response.get_json()["message"] != "Please choose what the AI should improve."


def test_improve_needs_csrf_token(client, app, ai_provider):
    app.config["WTF_CSRF_ENABLED"] = True
    assert _improve(client, "summary").status_code == 400
    assert ai_provider.calls == []
