from sqlmodel import SQLModel

from app.lib.hooks import PluginCollectionHook

# SQLModel classes contributed by plugins, discovered by Alembic autogenerate.
MODELS: PluginCollectionHook[type[SQLModel]] = PluginCollectionHook()
