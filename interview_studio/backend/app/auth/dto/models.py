from app.shared.http.dto import ResponseDTO


class UserResponse(ResponseDTO):
    id: int
    email: str
    name: str
    is_active: bool
