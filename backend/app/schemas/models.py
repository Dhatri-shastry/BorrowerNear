from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator
from typing import Annotated

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Phone = Annotated[str, StringConstraints(pattern=r"^\+?[0-9]{10,15}$", max_length=20)]
Password = Annotated[str, StringConstraints(min_length=10, max_length=128)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterIn(InputModel):
    name: Name
    email: EmailStr
    phone: Phone
    password: Password
    location_id: int = Field(gt=0)
    role: str = Field(default="BORROWER", pattern="^(LENDER|BORROWER)$")


class RoleIn(InputModel):
    role: str = Field(pattern="^(LENDER|BORROWER)$")


class LoginIn(InputModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    name: str
    location_id: int
    locality: str
    city: str
    trust_score: float
    created_at: object


class RequestIn(InputModel):
    item_id: int = Field(gt=0)
    start_date: date
    end_date: date


class DecisionIn(InputModel):
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")


class HandoverIn(InputModel):
    borrow_date: date
    due_date: date
    condition_before: str = Field(min_length=1, max_length=10000)


class ReturnIn(InputModel):
    return_date: date
    condition_after: str = Field(min_length=1, max_length=10000)


class ReviewIn(InputModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=5000)


class ItemCreate(InputModel):
    category_id: int = Field(gt=0)
    item_name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=10000)
    condition: str | None = Field(default=None, max_length=100)
    estimated_value: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    deposit_amount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=10, decimal_places=2)

    @field_validator("item_name")
    @classmethod
    def item_name_not_blank(cls, value: str) -> str:
        value=value.strip()
        if not value:
            raise ValueError("Item name cannot be blank")
        return value


class ItemUpdate(InputModel):
    category_id: int | None = Field(default=None, gt=0)
    item_name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=10000)
    condition: str | None = Field(default=None, max_length=100)
    estimated_value: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    deposit_amount: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    status: str | None = Field(default=None, pattern="^(AVAILABLE|UNAVAILABLE)$")

    @field_validator("item_name")
    @classmethod
    def updated_item_name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value=value.strip()
        if not value:
            raise ValueError("Item name cannot be blank")
        return value


class ConversationCreate(InputModel):
    request_id: int = Field(gt=0)


class MessageCreate(InputModel):
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value=value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value
