import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from bot.api.mini_app import router as mini_app_router
from admin.main import app as admin_app

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for mini app
app.mount("/static", StaticFiles(directory="webapp"), name="static")

# Mini App routes
@app.get("/")
async def root():
    from fastapi.responses import FileResponse
    return FileResponse("webapp/index.html")

@app.get("/game")
async def game_page():
    from fastapi.responses import FileResponse
    return FileResponse("webapp/game.html")

app.include_router(mini_app_router)

# Admin routes under /admin
app.mount("/admin", admin_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
