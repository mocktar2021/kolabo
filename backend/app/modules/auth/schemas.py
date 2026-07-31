"""Request and response schemas for the auth module."""
from pydantic import BaseModel, Field

ROLES = {"influencer", "business", "agency"}


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    country_code: str = Field(min_length=2, max_length=2)
    role: str


class RegisterResponse(BaseModel):
    user_id: str
    message: str


class VerifyOtpRequest(BaseModel):
    phone: str
    code: str = Field(min_length=6, max_length=6)


class LoginRequest(BaseModel):
    phone: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # The stored role rides along with every token grant. The frontend picks
    # the home experience (creator vs business vs agency) from this value;
    # while it was absent, a re-login had nothing to restore the role from —
    # which is how an agency account came back as a creator.
    role: str


class DeleteAccountRequest(BaseModel):
    # Deleting an account must cost more than a stolen session token: the
    # bearer token says who is asking, but only the current password proves
    # it is really them.
    password: str


class PasswordResetRequest(BaseModel):
    phone: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str
