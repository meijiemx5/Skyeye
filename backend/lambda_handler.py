"""AWS Lambda handler for FastAPI app using Mangum."""
from mangum import Mangum
from app.main import app

handler = Mangum(app, lifespan="off")
