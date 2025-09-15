"""
Worker main entry point
"""
import asyncio
import logging
import sys

from backend.workers.prediction_worker import PredictionWorker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main worker entry point"""
    logger.info("Starting RetainWise Prediction Worker...")
    
    worker = PredictionWorker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker failed with error: {str(e)}", exc_info=True)
        sys.exit(1)
    
    logger.info("Worker shutdown complete")

if __name__ == "__main__":
    asyncio.run(main()) 