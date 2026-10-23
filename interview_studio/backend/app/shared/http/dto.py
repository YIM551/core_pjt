from pydantic import BaseModel, ConfigDict


class RequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
