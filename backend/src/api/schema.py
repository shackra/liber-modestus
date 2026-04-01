import strawberry

from sacrum.captator.options import get_mass_options


@strawberry.type
class Greetings:
    greeting: str


def say_hello() -> Greetings:
    return Greetings(greeting="Hello, World!")


@strawberry.type
class MassOption:
    value: str
    label: str
    description: str


@strawberry.type
class MassOptions:
    rubrics: list[MassOption]
    mass_types: list[MassOption]
    orders: list[MassOption]
    languages: list[MassOption]
    votives: list[MassOption]
    communes: list[MassOption]
    ordines: list[MassOption]


def _resolve_mass_options() -> MassOptions:
    opts = get_mass_options()
    return MassOptions(
        rubrics=[
            MassOption(value=o.value, label=o.label, description=o.description)
            for o in opts.rubrics
        ],
        mass_types=[
            MassOption(value=o.value, label=o.label, description=o.description)
            for o in opts.mass_types
        ],
        orders=[
            MassOption(value=o.value, label=o.label, description=o.description)
            for o in opts.orders
        ],
        languages=[
            MassOption(value=o.value, label=o.label, description=o.description)
            for o in opts.languages
        ],
        votives=[
            MassOption(value=o.value, label=o.label, description=o.description)
            for o in opts.votives
        ],
        communes=[
            MassOption(value=o.value, label=o.label, description=o.description)
            for o in opts.communes
        ],
        ordines=[
            MassOption(value=o.value, label=o.label, description=o.description)
            for o in opts.ordines
        ],
    )


@strawberry.type
class Query:
    greet: Greetings = strawberry.field(resolver=say_hello)
    mass_options: MassOptions = strawberry.field(resolver=_resolve_mass_options)
