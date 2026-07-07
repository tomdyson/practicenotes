from ninja import NinjaAPI
from ninja.security import django_auth

from setlists.api import router as sets_router
from songs.api import router as songs_router
from workspaces.api import router as owners_router

api = NinjaAPI(
    title="Practice Notes API",
    version="1.0",
    description="Session-authenticated CRUD for songs, sets, items and uploads.",
    auth=django_auth,
    docs_url="/docs",
)

api.add_router("", owners_router)
api.add_router("", songs_router)
api.add_router("", sets_router)
