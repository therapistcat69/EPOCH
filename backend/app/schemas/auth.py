from pydantic import BaseModel


class AuthUser(BaseModel):
    name: str | None = None
    email: str | None = None
    image: str | None = None


class AuthChannel(BaseModel):
    id: str
    title: str
    thumbnail_url: str | None = None


class MeResponse(BaseModel):
    """Never contains tokens."""

    authenticated: bool
    user: AuthUser | None = None
    channel: AuthChannel | None = None
