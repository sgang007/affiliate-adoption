"""Azure Functions entrypoint.

Wraps the FastAPI ASGI app so the whole API runs as a single HTTP-triggered
function. Stateless by design: all state lives in the database, so the app
scales horizontally on the Consumption / Flex Consumption plan.
"""
import azure.functions as func

from app.main import app as fastapi_app

app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
