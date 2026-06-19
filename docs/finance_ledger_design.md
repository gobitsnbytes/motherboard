# Design Document: Virtual Ledger & Card Transaction Simulation System

## Overview

This specification details the design for the internal virtual ledger and simulated transaction card system for the GOBITSNBYTES FOUNDATION. All transactions and balances are managed on paper; a single current account underpins the actual foundation operations.

---

## 1. Database Schema Extensions

### 1.1 `VirtualTransaction` (New Model)
A ledger of all debits and credits between virtual accounts or from the treasury pool.

```python
class VirtualTransaction(Base):
    __tablename__ = "virtual_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Null represents the main treasury pool
    source_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("virtual_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    destination_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("virtual_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'money_request' | 'card_charge' | 'manual_adjustment'
    reference_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

### 1.2 `VirtualCard` (Modified Model)
We add columns to track daily and monthly spending limits for card simulation checks:

* `daily_limit_paise`: `Mapped[int | None]` (default `None`, meaning unlimited)
* `monthly_limit_paise`: `Mapped[int | None]` (default `None`, meaning unlimited)

---

## 2. API Endpoints

### 2.1 Get Account Transaction Ledger
* **Route**: `GET /api/finance/accounts/{account_id}/transactions`
* **Permission**: `finance.accounts.read`
* **Response**: List of transactions where the account is either the source or destination.
* **Pagination**: Supports query params `limit` and `offset`.

### 2.2 Card Charge Simulation
* **Route**: `POST /api/finance/cards/{card_id}/simulate-charge`
* **Permission**: `finance.cards.manage` (or matching card holder user-id check)
* **Payload**:
  ```json
  {
    "amount_paise": 150000,
    "merchant": "Amazon Web Services",
    "description": "Virtual cloud hosting fees"
  }
  ```
* **Validation & Execution**:
  1. Fetch `VirtualCard` and check `is_active` status.
  2. Fetch parent `VirtualAccount` and check balance: `balance_paise >= amount_paise`.
  3. Validate card limits:
     - Sum existing card charges in the last 24 hours plus new charge must not exceed `daily_limit_paise`.
     - Sum existing card charges in the current calendar month plus new charge must not exceed `monthly_limit_paise`.
  4. Perform atomic update in DB transaction block:
     - Create a `VirtualTransaction` entry with type `'card_charge'`.
     - Decrement parent `VirtualAccount.balance_paise` by `amount_paise`.
     - Return status `200 OK` with simulated transaction details.

### 2.3 Modify Money Request Approval
* When a money request is approved:
  - Create a corresponding `VirtualTransaction` entry.
  - Increment/decrement the respective account balances atomically.

---

## 3. Frontend Portal Upgrades

### 3.1 Account Details (`/finance/accounts/[id]`)
- Render a paginated **Transaction Ledger** showing historical debits/credits.
- Credits highlighted in green (`+₹X.XX`); debits highlighted in red/white (`-₹X.XX`).

### 3.2 Cards Dashboard (`/finance/cards`)
- Display daily and monthly limits on the card face.
- Add a **Simulate Card Charge** button/modal opening a slide-out drawer form.
- Form fields: Amount (in Rupees), Merchant Name, and Description.
- Shows instant feedback: success receipt or limit/balance decline error message.

### 3.3 Dashboard Feed (`/finance/dashboard`)
- List the most recent transactions foundation-wide (for finance admins) or user-owned accounts.
