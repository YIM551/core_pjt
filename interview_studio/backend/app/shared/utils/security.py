from itsdangerous import URLSafeSerializer

from app.core.config import get_settings


def session_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().session_secret, salt="careerfit-session")
