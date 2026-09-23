"""Finance ledger subsystem — chart of accounts, journal, vouchers, donations,
vendors/bills, budgets, reports, bank reconciliation, and the RazorpayX payout
provider seam.

Kept as its own package (rather than growing app/db/models.py or
app/routers/finance.py further) so it can be reviewed, tested, and migrated
independently. See docs/finance_ledger_design.md for the design.
"""
