from pydantic import BaseModel


class PortalUrlResponse(BaseModel):
    portal_url: str
