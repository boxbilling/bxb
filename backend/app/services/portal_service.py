from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.portal import PortalUrlResponse


class PortalService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_token(self, customer_id: UUID, organization_id: UUID) -> str:
        """Generate a portal JWT token valid for 12 hours."""
        payload = {
            "customer_id": str(customer_id),
            "organization_id": str(organization_id),
            "type": "portal",
            "exp": datetime.now(UTC) + timedelta(hours=12),
        }
        return jwt.encode(payload, settings.PORTAL_JWT_SECRET, algorithm="HS256")

    def generate_portal_url(
        self, customer_id: UUID, organization_id: UUID
    ) -> PortalUrlResponse:
        """Generate a portal URL with a JWT token valid for 12 hours."""
        token = self.generate_token(customer_id, organization_id)
        url = f"https://{settings.APP_DOMAIN}/portal?token={token}"
        return PortalUrlResponse(portal_url=url)

    @staticmethod
    def verify_portal_token(token: str) -> tuple[UUID, UUID]:
        """Decode and validate a portal JWT token.

        Returns (customer_id, organization_id).
        Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
        """
        payload = jwt.decode(token, settings.PORTAL_JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "portal":
            raise jwt.InvalidTokenError("Invalid token type")
        return UUID(payload["customer_id"]), UUID(payload["organization_id"])
