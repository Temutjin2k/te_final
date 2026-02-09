from pydantic import BaseModel as PydBaseModel


class NamePayload(PydBaseModel):
    """Payload-модель для санкционных эндпоинтов."""
    name: str

