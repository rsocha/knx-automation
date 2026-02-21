import asyncio
import logging
import collections
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

# ============ LOGGING SETUP ============
# In-memory log buffer for web UI
log_buffer = collections.deque(maxlen=500)

class BufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = {
            'time': record.created,
            'level': record.levelname,
            'name': record.name,
            'message': self.format(record)
        }
        log_buffer.append(log_entry)

# Configure logging BEFORE importing other modules
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Add buffer handler to root logger
buffer_handler = BufferHandler()
buffer_handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
buffer_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(buffer_handler)
logging.getLogger().setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
logger.info("=== KNX Automation Starting ===")

# Now import other modules
from api import router
from knx import knx_manager
from utils import db_manager
from logic import logic_manager


async def on_telegram_received(data):
    """Forward telegram to logic manager"""
    address = data.get('destination')
    value = data.get('payload')
    if address and value:
        await logic_manager.on_address_changed(address, value)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting KNX Automation System...")
    
    # Auto-clear Python cache on startup
    try:
        from scripts.auto_cache_clear import clear_python_cache
        logger.info("Clearing Python cache...")
        cleared = clear_python_cache('.')
        if cleared > 0:
            logger.info(f"✓ Cache cleared: {cleared} items")
        else:
            logger.info("ℹ No cache found")
    except Exception as e:
        logger.warning(f"Could not clear cache: {e}")
    
    await db_manager.init_db()
    await knx_manager.connect()
    
    # Initialize logic manager
    await logic_manager.initialize(db_manager, knx_manager)
    
    # Register callback to forward telegrams to logic
    knx_manager.register_telegram_callback(on_telegram_received)
    
    yield
    
    logger.info("Shutting down...")
    await logic_manager.shutdown()
    await knx_manager.disconnect()

app = FastAPI(title="KNX Automation System", version="3.0.7", lifespan=lifespan)
app.include_router(router, prefix="/api/v1")

dashboard_path = Path(__file__).parent / "static"
if dashboard_path.exists():
    app.mount("/static", StaticFiles(directory=str(dashboard_path)), name="static")

@app.get("/")
async def root():
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "KNX Automation API", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
