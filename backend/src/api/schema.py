import strawberry


@strawberry.type
class Greetings:
    greeting: str


def say_hello() -> Greetings:
    return Greetings(greeting="Hello, World!")


@strawberry.type
class Query:
    greet: Greetings = strawberry.field(resolver=say_hello)
