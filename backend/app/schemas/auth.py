from uuid import UUID

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str
    org_slug: str | None = None


class _LoginUser(BaseModel):
    id: UUID
    email: str
    name: str


class _LoginOrganization(BaseModel):
    id: UUID
    name: str
    slug: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: _LoginUser
    organization: _LoginOrganization
    role: str


class _MeUser(BaseModel):
    id: UUID
    email: str
    name: str
    is_active: bool


class _MeOrganization(BaseModel):
    id: UUID
    name: str
    slug: str


class MeResponse(BaseModel):
    user: _MeUser
    organization: _MeOrganization
    role: str
