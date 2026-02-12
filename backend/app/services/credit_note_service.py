"""Credit note service for managing credit notes against invoices."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.credit_note import CreditNote, CreditNoteStatus, CreditStatus
from app.models.invoice import InvoiceStatus
from app.models.invoice_settlement import SettlementType
from app.repositories.credit_note_item_repository import CreditNoteItemRepository
from app.repositories.credit_note_repository import CreditNoteRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.invoice_settlement_repository import InvoiceSettlementRepository
from app.schemas.credit_note import CreditNoteCreate, CreditNoteItemCreate
from app.schemas.invoice_settlement import InvoiceSettlementCreate


class CreditNoteService:
    """Service for credit note lifecycle management."""

    def __init__(self, db: Session):
        self.db = db
        self.credit_note_repo = CreditNoteRepository(db)
        self.credit_note_item_repo = CreditNoteItemRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.fee_repo = FeeRepository(db)

    def create_credit_note(
        self,
        invoice_id: UUID,
        items: list[CreditNoteItemCreate],
        reason: str,
        description: str | None = None,
        credit_note_type: str = "credit",
    ) -> CreditNote:
        """Create a credit note for a finalized invoice.

        Validates the invoice is finalized, verifies fee references, calculates
        amounts from items, and creates the CreditNote with CreditNoteItems.

        Args:
            invoice_id: The invoice to create a credit note against.
            items: List of CreditNoteItemCreate with fee_id and amount_cents.
            reason: The reason for the credit note.
            description: Optional description.
            credit_note_type: Type of credit note (credit, refund, offset).

        Returns:
            The created CreditNote.

        Raises:
            ValueError: If validation fails.
        """
        # Validate invoice exists and is finalized
        invoice = self.invoice_repo.get_by_id(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        if invoice.status != InvoiceStatus.FINALIZED.value:
            raise ValueError("Credit notes can only be created for finalized invoices")

        if not items:
            raise ValueError("Credit note must have at least one item")

        # Validate all fee references belong to the invoice
        invoice_fees = self.fee_repo.get_by_invoice_id(invoice_id)
        invoice_fee_ids = {UUID(str(f.id)) for f in invoice_fees}

        total_amount = Decimal("0")
        for item in items:
            if item.fee_id not in invoice_fee_ids:
                raise ValueError(f"Fee {item.fee_id} does not belong to invoice {invoice_id}")
            total_amount += item.amount_cents

        # Generate a unique credit note number
        number = self._generate_credit_note_number()

        customer_id = UUID(str(invoice.customer_id))
        currency = str(invoice.currency)

        # Import enum values
        from app.models.credit_note import CreditNoteReason, CreditNoteType

        # Create the credit note
        credit_note_data = CreditNoteCreate(
            number=number,
            invoice_id=invoice_id,
            customer_id=customer_id,
            credit_note_type=CreditNoteType(credit_note_type),
            reason=CreditNoteReason(reason),
            description=description,
            credit_amount_cents=total_amount,
            total_amount_cents=total_amount,
            currency=currency,
            items=[],  # items are created separately
        )
        credit_note = self.credit_note_repo.create(credit_note_data)

        # Create CreditNoteItems
        credit_note_id = UUID(str(credit_note.id))
        items_data = [
            {
                "credit_note_id": credit_note_id,
                "fee_id": item.fee_id,
                "amount_cents": item.amount_cents,
            }
            for item in items
        ]
        self.credit_note_item_repo.create_bulk(items_data)

        return credit_note

    def finalize_credit_note(self, credit_note_id: UUID) -> CreditNote:
        """Finalize a credit note, setting status=finalized and balance.

        Args:
            credit_note_id: The credit note to finalize.

        Returns:
            The finalized CreditNote.

        Raises:
            ValueError: If credit note not found or not in draft status.
        """
        credit_note = self.credit_note_repo.get_by_id(credit_note_id)
        if not credit_note:
            raise ValueError(f"Credit note {credit_note_id} not found")

        if credit_note.status != CreditNoteStatus.DRAFT.value:
            raise ValueError("Only draft credit notes can be finalized")

        # We already validated the credit note exists and is in draft status,
        # so finalize() will always return a result here.
        return self.credit_note_repo.finalize(credit_note_id)  # type: ignore[return-value]

    def void_credit_note(self, credit_note_id: UUID) -> CreditNote:
        """Void a credit note, setting credit_status=voided.

        Args:
            credit_note_id: The credit note to void.

        Returns:
            The voided CreditNote.

        Raises:
            ValueError: If credit note not found or not finalized.
        """
        credit_note = self.credit_note_repo.get_by_id(credit_note_id)
        if not credit_note:
            raise ValueError(f"Credit note {credit_note_id} not found")

        if credit_note.status != CreditNoteStatus.FINALIZED.value:
            raise ValueError("Only finalized credit notes can be voided")

        # We already validated the credit note exists and is finalized,
        # so void() will always return a result here.
        return self.credit_note_repo.void(credit_note_id)  # type: ignore[return-value]

    def apply_credit_to_invoice(
        self,
        credit_note_id: UUID,
        invoice_id: UUID,
        amount: Decimal,
    ) -> CreditNote:
        """Apply credit from a credit note to an invoice.

        Deducts the specified amount from the credit note's balance.

        Args:
            credit_note_id: The credit note to consume credit from.
            invoice_id: The invoice to apply credit to.
            amount: The amount to apply.

        Returns:
            The updated CreditNote.

        Raises:
            ValueError: If validation fails.
        """
        credit_note = self.credit_note_repo.get_by_id(credit_note_id)
        if not credit_note:
            raise ValueError(f"Credit note {credit_note_id} not found")

        if credit_note.status != CreditNoteStatus.FINALIZED.value:
            raise ValueError("Credit note must be finalized to apply credit")

        if credit_note.credit_status != CreditStatus.AVAILABLE.value:
            raise ValueError("Credit note has no available credit")

        # Validate invoice exists
        invoice = self.invoice_repo.get_by_id(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Validate amount does not exceed available balance
        balance = Decimal(str(credit_note.balance_amount_cents))
        if amount > balance:
            raise ValueError(
                f"Amount {amount} exceeds available balance {balance}"
            )

        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Record settlement for the credit note application
        settlement_repo = InvoiceSettlementRepository(self.db)
        settlement_repo.create(
            InvoiceSettlementCreate(
                invoice_id=invoice_id,
                settlement_type=SettlementType.CREDIT_NOTE,
                source_id=credit_note_id,
                amount_cents=amount,
            )
        )

        # Auto-mark invoice as paid if fully settled
        total_settled = settlement_repo.get_total_settled(invoice_id)
        if total_settled >= Decimal(str(invoice.total)):
            self.invoice_repo.mark_paid(invoice_id)

        # We already validated the credit note exists and has available credit,
        # so consume_credit() will always return a result here.
        return self.credit_note_repo.consume_credit(credit_note_id, amount)  # type: ignore[return-value]

    def _generate_credit_note_number(self) -> str:
        """Generate a unique credit note number."""
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"CN-{today}-"

        # Find existing credit notes with today's prefix
        existing = self.credit_note_repo.get_all(limit=1000)
        max_num = 0
        for cn in existing:
            number = str(cn.number)
            if number.startswith(prefix):
                try:
                    num = int(number.split("-")[-1])
                    if num > max_num:
                        max_num = num
                except (ValueError, IndexError):
                    pass

        return f"{prefix}{max_num + 1:04d}"
