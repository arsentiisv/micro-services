import os
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

logger = logging.getLogger(__name__)

async def init_db():
    """
    Автоматически применяет SQL-миграции из папки db/migrations
    """
    logger.info("Starting database initialization...")
    
    # Создаем движок БД
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    
    migrations_dir = os.path.join(os.getcwd(), "db", "migrations")
    
    # Получаем список файлов миграций и сортируем их
    migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
    
    async with engine.begin() as conn:
        # Включаем расширение uuid-ossp (нужно для генерации UUID)
        try:
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        except Exception as e:
            logger.warning(f"Could not create extension uuid-ossp: {e}")
        
        for filename in migration_files:
            file_path = os.path.join(migrations_dir, filename)
            logger.info(f"Applying migration: {filename}")
            
            with open(file_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
                
            # Разбиваем файл на отдельные команды (по точке с запятой)
            statements = sql_content.split(";")
            
            for statement in statements:
                if statement.strip():
                    try:
                        await conn.execute(text(statement))
                    except Exception as e:
                        # Игнорируем ошибки "relation already exists", так как миграции могут запускаться повторно
                        if "already exists" in str(e) or "duplicate key" in str(e):
                            logger.warning(f"Skipping statement in {filename}: {e}")
                        else:
                            logger.error(f"Error applying migration {filename}: {e}")
                            
    logger.info("Database initialization completed.")
    await engine.dispose()
