"""Fake services with the same methods as the real ones (auth, notes, expenses, captions, CVs, AI). No network."""
import itertools
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.blueprints.auth.errors import AuthError, AuthUnavailable, SessionEnded, TokenExpired
from app.blueprints.auth.services import EMAIL_LINK_TYPES, AuthSession, AuthUser, GoogleLogin
from app.blueprints.tools.captions.errors import CaptionsUnavailable
from app.blueprints.tools.cv_generator.errors import CVError, CVsUnavailable
from app.blueprints.tools.expenses.errors import ExpensesUnavailable
from app.blueprints.tools.notes.errors import NotesUnavailable
from app.services.ai.base import AIProvider
from app.services.ai_quota_repository import QuotaUnavailable

GOOGLE_URL = "https://test-project.supabase.co/auth/v1/authorize?provider=google"
GOOGLE_VERIFIER = "test-code-verifier"
GOOGLE_CODE = "good-google-code"
GOOGLE_EMAIL = "google.user@example.com"


@dataclass
class FakeUser:
    id: str
    email: str
    password: str
    name: str = ""
    confirmed: bool = True
    metadata: dict = field(default_factory=dict)


@dataclass
class FakeAuthService:
    confirm_email: bool = True       # like "Confirm email" in Supabase
    unavailable: bool = False        # pretend Supabase is down
    fail_next: AuthError = None      # raise this once from the next call
    users: dict = field(default_factory=dict)            # email -> FakeUser
    access_tokens: dict = field(default_factory=dict)    # token -> email
    refresh_tokens: dict = field(default_factory=dict)   # token -> email
    expired_tokens: set = field(default_factory=set)
    calls: list = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    # --- helpers for tests ---

    def add_user(self, email="sara@example.com", password="correct-horse", name="", confirmed=True):
        user = FakeUser(id=f"user-{next(self._ids)}", email=email, password=password, name=name, confirmed=confirmed)
        self.users[email] = user
        return user

    def new_session(self, email, expires_in=3600):
        n = next(self._ids)
        access, refresh = f"access-{n}", f"refresh-{n}"
        self.access_tokens[access] = email
        self.refresh_tokens[refresh] = email
        return AuthSession(access_token=access, refresh_token=refresh, expires_at=int(time.time()) + expires_in)

    def called(self, name):
        return [args for call, args in self.calls if call == name]

    def _record(self, name, *args):
        self.calls.append((name, args))
        if self.unavailable:
            raise AuthUnavailable()
        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error

    # --- the AuthService interface ---

    def sign_up(self, email, password, confirm_url):
        self._record("sign_up", email, password, confirm_url)
        if email in self.users:
            return None
        self.add_user(email, password, confirmed=not self.confirm_email)
        return None if self.confirm_email else self.new_session(email)

    def sign_in(self, email, password):
        self._record("sign_in", email, password)
        user = self.users.get(email)
        if user is None or user.password != password:
            raise AuthError("invalid_credentials")
        if not user.confirmed:
            raise AuthError("email_not_confirmed")
        return self.new_session(email)

    def send_password_reset(self, email, reset_url):
        self._record("send_password_reset", email, reset_url)

    def verify_email_link(self, token_hash, link_type):
        self._record("verify_email_link", token_hash, link_type)
        prefix = "good-token-for-"
        if link_type not in EMAIL_LINK_TYPES or not token_hash.startswith(prefix):
            raise AuthError("link_invalid")
        email = token_hash[len(prefix):]
        self.users[email].confirmed = True
        return self.new_session(email)

    def update_password(self, auth_session, new_password):
        self._record("update_password", auth_session.access_token, new_password)
        email = self.access_tokens.get(auth_session.access_token)
        if email is None:
            raise SessionEnded()
        if self.users[email].password == new_password:
            raise AuthError("same_password")
        self.users[email].password = new_password

    def update_user_metadata(self, auth_session, updates):
        self._record("update_user_metadata", auth_session.access_token, updates)
        email = self.access_tokens.get(auth_session.access_token)
        if email is None:
            raise SessionEnded()
        self.users[email].metadata.update(updates)

    def start_google_login(self, callback_url):
        self._record("start_google_login", callback_url)
        return GoogleLogin(url=f"{GOOGLE_URL}&redirect_to={callback_url}", code_verifier=GOOGLE_VERIFIER)

    def finish_google_login(self, code, code_verifier):
        self._record("finish_google_login", code, code_verifier)
        if code != GOOGLE_CODE or code_verifier != GOOGLE_VERIFIER:
            raise AuthError("google_failed")
        if GOOGLE_EMAIL not in self.users:
            self.add_user(GOOGLE_EMAIL, password=None, name="Google User")
        return self.new_session(GOOGLE_EMAIL)

    def refresh(self, refresh_token):
        self._record("refresh", refresh_token)
        email = self.refresh_tokens.pop(refresh_token, None)
        if email is None:
            raise AuthError("session_ended")
        return self.new_session(email)

    def sign_out(self, access_token):
        self.calls.append(("sign_out", (access_token,)))
        self.access_tokens.pop(access_token, None)

    def get_user(self, access_token):
        self.calls.append(("get_user", (access_token,)))
        if self.unavailable:
            raise AuthUnavailable()
        if access_token in self.expired_tokens:
            raise TokenExpired()
        email = self.access_tokens.get(access_token)
        if email is None:
            raise SessionEnded()
        user = self.users[email]
        return AuthUser(id=user.id, email=user.email, name=user.name, metadata=user.metadata)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FakeNotesRepository:
    """In-memory notes store with the same methods as SupabaseNotesRepository. No network.

    Notes are kept per access_token, the same way the real repository keeps them per user
    (RLS keys off the token's user) — two different tokens never see each other's notes.
    """
    unavailable: bool = False
    notes: dict = field(default_factory=dict)  # access_token -> {note_id: full note dict}

    def _bucket(self, access_token):
        return self.notes.setdefault(access_token, {})

    def _check(self):
        if self.unavailable:
            raise NotesUnavailable()

    def _public(self, note):
        return {key: note[key] for key in ("id", "title", "content", "created_at", "updated_at")}

    def list_notes(self, access_token, limit, offset):
        self._check()
        rows = sorted(self._bucket(access_token).values(), key=lambda note: note["updated_at"], reverse=True)
        return [self._public(note) for note in rows[offset:offset + limit]]

    def insert_note(self, access_token, title, content, client_id=None):
        self._check()
        bucket = self._bucket(access_token)
        if client_id:
            existing = next((note for note in bucket.values() if note.get("client_id") == client_id), None)
            if existing is not None:
                return self._public(existing)
        now = _now_iso()
        note = {
            "id": str(uuid.uuid4()),  # looks like a real Supabase id, so the id-format check passes
            "title": title,
            "content": content,
            "client_id": client_id,
            "created_at": now,
            "updated_at": now,
        }
        bucket[note["id"]] = note
        return self._public(note)

    def update_note(self, access_token, note_id, title, content):
        self._check()
        note = self._bucket(access_token).get(note_id)
        if note is None:
            return None
        note["title"], note["content"], note["updated_at"] = title, content, _now_iso()
        return self._public(note)

    def delete_note(self, access_token, note_id):
        self._check()
        return self._bucket(access_token).pop(note_id, None) is not None

    def import_notes(self, access_token, notes):
        self._check()
        imported = []
        for note in notes:
            bucket = self._bucket(access_token)
            already = any(existing.get("client_id") == note.get("client_id") for existing in bucket.values())
            if already:
                continue
            imported.append(self.insert_note(access_token, note["title"], note["content"], note.get("client_id")))
        return imported


@dataclass
class FakeExpensesRepository:
    """In-memory expenses store with the same methods as SupabaseExpensesRepository. No network."""
    unavailable: bool = False
    expenses: dict = field(default_factory=dict)  # access_token -> {expense_id: full expense dict}

    def _bucket(self, access_token):
        return self.expenses.setdefault(access_token, {})

    def _check(self):
        if self.unavailable:
            raise ExpensesUnavailable()

    def _public(self, exp):
        return {key: exp[key] for key in ("id", "amount", "description", "currency", "spent_at", "created_at", "updated_at")}

    def list_month(self, access_token, year, month):
        self._check()
        prefix = f"{year:04d}-{month:02d}"
        rows = [
            exp for exp in self._bucket(access_token).values()
            if exp["spent_at"].startswith(prefix)
        ]
        rows.sort(key=lambda e: (e["spent_at"], e["created_at"]), reverse=True)
        return [self._public(exp) for exp in rows]

    def insert_expense(self, access_token, amount, description, currency, spent_at, client_id=None):
        self._check()
        bucket = self._bucket(access_token)
        if client_id:
            existing = next((e for e in bucket.values() if e.get("client_id") == client_id), None)
            if existing is not None:
                return self._public(existing)
        now = _now_iso()
        exp = {
            "id": str(uuid.uuid4()),
            "amount": str(amount),
            "description": description,
            "currency": currency,
            "spent_at": spent_at,
            "client_id": client_id,
            "created_at": now,
            "updated_at": now,
        }
        bucket[exp["id"]] = exp
        return self._public(exp)

    def update_expense(self, access_token, expense_id, amount, description, currency, spent_at):
        self._check()
        exp = self._bucket(access_token).get(expense_id)
        if exp is None:
            return None
        exp["amount"] = str(amount)
        exp["description"] = description
        exp["currency"] = currency
        exp["spent_at"] = spent_at
        exp["updated_at"] = _now_iso()
        return self._public(exp)

    def delete_expense(self, access_token, expense_id):
        self._check()
        return self._bucket(access_token).pop(expense_id, None) is not None

    def import_expenses(self, access_token, expenses):
        self._check()
        imported = []
        for exp in expenses:
            bucket = self._bucket(access_token)
            already = any(e.get("client_id") == exp.get("client_id") for e in bucket.values())
            if already:
                continue
            imported.append(self.insert_expense(
                access_token,
                exp["amount"], exp["description"], exp["currency"], exp["spent_at"],
                exp.get("client_id"),
            ))
        return imported


@dataclass
class FakeAIQuotaRepository:
    """In-memory version of SupabaseAIQuotaRepository, with the same rules as the Postgres
    functions in supabase/migrations/20261014_ai_tries.sql (per-tool limit, one site limit for
    all tools). No network."""
    unavailable: bool = False
    tries: dict = field(default_factory=dict)  # try_id -> (tool, subject), all "today"
    calls: list = field(default_factory=list)

    def _check(self):
        if self.unavailable:
            raise QuotaUnavailable()

    @staticmethod
    def subject(access_token, ip_hash):
        return f"user:{access_token}" if access_token else f"ip:{ip_hash}"

    def used(self, tool, access_token=None, ip_hash=None):
        key = (tool, self.subject(access_token, ip_hash))
        return sum(1 for value in self.tries.values() if value == key)

    def consume_try(self, access_token, tool, ip_hash, limit, site_limit):
        self._check()
        self.calls.append(("consume_try", access_token, tool, ip_hash, limit, site_limit))
        used = self.used(tool, access_token, ip_hash)
        if used >= limit:
            return {"status": "limit", "try_id": None, "used": used}
        if len(self.tries) >= site_limit:
            return {"status": "site_limit", "try_id": None, "used": used}
        try_id = str(uuid.uuid4())
        self.tries[try_id] = (tool, self.subject(access_token, ip_hash))
        return {"status": "ok", "try_id": try_id, "used": used + 1}

    def refund_try(self, access_token, try_id):
        self._check()
        self.calls.append(("refund_try", access_token, try_id))
        self.tries.pop(try_id, None)

    def tries_used(self, access_token, tool, ip_hash):
        self._check()
        return self.used(tool, access_token, ip_hash)


@dataclass
class FakeCaptionsRepository:
    """In-memory version of SupabaseCaptionsRepository (history only). No network."""
    unavailable: bool = False
    history_unavailable: bool = False   # only saving/reading history fails
    history: dict = field(default_factory=dict)  # access_token -> {id: row}

    def _check(self):
        if self.unavailable:
            raise CaptionsUnavailable()

    def _check_history(self):
        self._check()
        if self.history_unavailable:
            raise CaptionsUnavailable()

    def insert_history(self, access_token, topic, platform, captions):
        self._check_history()
        row = {
            "id": str(uuid.uuid4()),
            "topic": topic,
            "platform": platform,
            "captions": list(captions),
            "created_at": _now_iso(),
        }
        self.history.setdefault(access_token, {})[row["id"]] = row
        return dict(row)

    def list_history(self, access_token, limit):
        self._check_history()
        rows = sorted(self.history.get(access_token, {}).values(), key=lambda r: r["created_at"], reverse=True)
        return [dict(row) for row in rows[:limit]]

    def delete_history(self, access_token, caption_id):
        self._check_history()
        return self.history.get(access_token, {}).pop(caption_id, None) is not None


@dataclass
class FakeCVsRepository:
    """In-memory saved CVs with the same methods as SupabaseCVsRepository. No network.
    CVs are kept per access_token (like RLS keys off the token's user), and the 20-CV limit
    behaves like the database trigger."""
    unavailable: bool = False
    max_cvs: int = 20
    cvs: dict = field(default_factory=dict)  # access_token -> {cv_id: row}

    def _bucket(self, access_token):
        return self.cvs.setdefault(access_token, {})

    def _check(self):
        if self.unavailable:
            raise CVsUnavailable()

    @staticmethod
    def _summary(row):
        return {key: row[key] for key in ("id", "title", "template", "accent", "language", "created_at", "updated_at")}

    def _full(self, row):
        return {**self._summary(row), "data": row["data"]}

    def _new_row(self, access_token, row):
        bucket = self._bucket(access_token)
        if len(bucket) >= self.max_cvs:
            raise CVError("cv_limit")
        now = _now_iso()
        stored = {"id": str(uuid.uuid4()), "client_id": None, "created_at": now, "updated_at": now, **row}
        bucket[stored["id"]] = stored
        return stored

    def list_cvs(self, access_token, limit):
        self._check()
        rows = sorted(self._bucket(access_token).values(), key=lambda row: row["updated_at"], reverse=True)
        return [self._summary(row) for row in rows[:limit]]

    def get_cv(self, access_token, cv_id):
        self._check()
        row = self._bucket(access_token).get(cv_id)
        return self._full(row) if row else None

    def insert_cv(self, access_token, row):
        self._check()
        return self._full(self._new_row(access_token, row))

    def update_cv(self, access_token, cv_id, row):
        self._check()
        stored = self._bucket(access_token).get(cv_id)
        if stored is None:
            return None
        stored.update(row, updated_at=_now_iso())
        return self._full(stored)

    def delete_cv(self, access_token, cv_id):
        self._check()
        return self._bucket(access_token).pop(cv_id, None) is not None

    def import_cvs(self, access_token, rows):
        self._check()
        bucket = self._bucket(access_token)
        imported = []
        for row in rows:
            if any(existing["client_id"] == row["client_id"] for existing in bucket.values()):
                continue
            imported.append(self._summary(self._new_row(access_token, row)))
        return imported


class FakeAIProvider(AIProvider):
    """Returns `result` (or raises `error`) instead of calling a real AI. Records every call."""
    name = "fake"

    def __init__(self, result=None, error=None):
        self.result = result if result is not None else {
            "captions": ["Caption one #new", "Caption two", "Caption three"],
        }
        self.error = error
        self.calls = []

    @classmethod
    def from_config(cls, config):
        return cls()

    def generate_json(self, *, system, prompt, schema, temperature=0.9, max_output_tokens=2048):
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        if self.error is not None:
            raise self.error
        return self.result
