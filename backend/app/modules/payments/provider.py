"""Mobile Money provider abstraction.

No real provider is contracted yet (see Part 18 and docs/ARCHITECTURE.md open
items), so all provider calls go through this interface with a mock provider.
The mock records collections and payouts so tests can assert on them and moves
no real money. A real provider (MTN MoMo, Moov Money, Orange Money, Wave, and so
on) drops in behind the same interface per country without touching escrow logic.
Raw Mobile Money PINs are never handled or stored.
"""
import uuid
from typing import Protocol


class MobileMoneyProvider(Protocol):
    def collect(self, target: str, amount: int, currency: str) -> str:
        ...

    def payout(self, target: str, amount: int, currency: str) -> str:
        ...


class MockProvider:
    def __init__(self) -> None:
        self.collections: list[dict] = []
        self.payouts: list[dict] = []

    def collect(self, target: str, amount: int, currency: str) -> str:
        ref = f"collect_{uuid.uuid4().hex[:12]}"
        self.collections.append({"target": target, "amount": amount, "currency": currency, "ref": ref})
        return ref

    def payout(self, target: str, amount: int, currency: str) -> str:
        ref = f"payout_{uuid.uuid4().hex[:12]}"
        self.payouts.append({"target": target, "amount": amount, "currency": currency, "ref": ref})
        return ref


default_provider: MobileMoneyProvider = MockProvider()
