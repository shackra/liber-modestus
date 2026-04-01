import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from .schema import Query

schema = strawberry.Schema(query=Query)

app = FastAPI()

graphql_router = GraphQLRouter(schema, path="/graphql")
app.include_router(graphql_router)
