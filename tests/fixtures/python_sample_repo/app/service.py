from app.helpers import normalize_name


class GreetingService:
    def greet(self, name: str) -> str:
        return f"hello {normalize_name(name)}"
