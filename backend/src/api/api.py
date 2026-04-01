import sys
from pathlib import Path

# Ensure src/ is on sys.path so sibling packages (sacrum, horae, scriptura)
# are importable when the app is loaded via "src.api:app"
# __file__ is .../backend/src/api/api.py
# parent.parent gives .../backend/src/ which is where sacrum, horae, scriptura live
_src = Path(__file__).resolve().parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from .schema import Query

schema = strawberry.Schema(query=Query)

app = FastAPI()

graphql_router = GraphQLRouter(schema, path="/graphql")
app.include_router(graphql_router)
