from fastapi import FastAPI

app = FastAPI()

# 기본 루트 엔드포인트
@app.get("/")
async def read_root():
    return {"message": "Welcome to AutoVizio API!"}

# 샘플 엔드포인트
@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}
