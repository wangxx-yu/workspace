from app.service import GreetingService


def run() -> str:
    service = GreetingService()
    return service.greet("World")
