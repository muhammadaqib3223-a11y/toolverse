"""Fake services with the same methods as the real ones (auth, notes). No network, fully predictable."""
import itertools
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.blueprints.auth.errors import AuthError, AuthUnavailable, SessionEnded, TokenExpired
from app.blueprints.auth.services import EMAIL_LINK_TYPES, AuthSession, AuthUser, GoogleLogin
from app.blueprints.tools.notes.errors import NotesUnavailable

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
        return AuthUser(id=user.id, email=user.email, name=user.name)


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
