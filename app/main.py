from fastapi import FastAPI

app = FastAPI(title="Semantic Fashion Recommendation System")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "API is running"}