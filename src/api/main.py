from fastapi import FastAPI

app = FastAPI(title="ibid")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
