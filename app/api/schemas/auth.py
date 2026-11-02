from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=120, examples=["paul.fischer500@example.com"])
    password: str = Field(min_length=1, max_length=128, examples=["NilePearl@2026"])


class AccountInfo(BaseModel):
    account_id: int
    role: str
    full_name: str
    email: str
    customer_id: str | None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    account: AccountInfo


class CurrentAccount(BaseModel):
    """Who is calling, read from the login token."""
    account_id: int
    role: str
    customer_id: str | None
