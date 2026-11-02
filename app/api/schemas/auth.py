import re
from datetime import date

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, field_validator

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=120, examples=["paul.fischer500@example.com"])
    password: str = Field(min_length=1, max_length=128, examples=["NilePearl@2026"])


class AccountInfo(BaseModel):
    account_id: int
    role: str
    full_name: str
    email: str
    customer_id: str | None
    email_verified: bool


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
    email_verified: bool = False


def strong_enough(password: str) -> str:
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        raise ValueError("the password needs at least one letter and one number")
    return password


# 8+ characters with a letter and a number (bcrypt reads at most 72 bytes)
Password = Annotated[str, Field(min_length=8, max_length=72, examples=["Pearl2026x"]), AfterValidator(strong_enough)]


class SignupRequest(BaseModel):
    first_name: str = Field(min_length=2, max_length=40, examples=["Mona"])
    last_name: str = Field(min_length=2, max_length=40, examples=["Hassan"])
    email: str = Field(max_length=120, pattern=EMAIL_PATTERN, examples=["mona.hassan@example.com"])
    phone: str = Field(pattern=r"^\+?[0-9 -]{8,20}$", examples=["+201001234567"])
    password: Password
    nationality: str | None = Field(default=None, max_length=30, examples=["Egyptian"])
    date_of_birth: date | None = Field(default=None, examples=[None])   # or later, before the first booking

    @field_validator("first_name", "last_name", "email", "nationality", mode="before")
    @classmethod
    def trimmed(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone")
    @classmethod
    def digits_only(cls, value):
        return re.sub(r"[ -]", "", value)


class CodeRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$", examples=["123456"])


class CodeSent(BaseModel):
    sent: bool = True
    expires_in_minutes: int


class ForgotPasswordRequest(BaseModel):
    email: str = Field(max_length=120, pattern=EMAIL_PATTERN, examples=["mona.hassan@example.com"])


class ResetPasswordRequest(BaseModel):
    email: str = Field(max_length=120, pattern=EMAIL_PATTERN, examples=["mona.hassan@example.com"])
    code: str = Field(pattern=r"^\d{6}$", examples=["123456"])
    new_password: Password
