import asyncio
import os
import sys
import asyncpg

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

async def run_migrations():
    print("Checking database connection...")
    
    # Parse DATABASE_URL to get connection params
    # Example: postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/marketplace
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    try:
        conn = await asyncpg.connect(url)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        print("Make sure PostgreSQL is running and the database 'marketplace' exists.")
        return

    print("Connected to database. Running migrations...")
    
    # Get absolute path to migrations directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    migration_dir = os.path.join(base_dir, "../db/migrations")
    
    if not os.path.exists(migration_dir):
        print(f"Migration directory not found: {migration_dir}")
        return

    migration_files = sorted([f for f in os.listdir(migration_dir) if f.endswith(".sql")])
    
    for filename in migration_files:
        print(f"Applying migration: {filename}")
        file_path = os.path.join(migration_dir, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            sql = f.read()
            try:
                # asyncpg execute can handle multiple statements usually.
                await conn.execute(sql)
                print(f"  -> Success: {filename}")
            except asyncpg.exceptions.DuplicateTableError:
                print(f"  -> Table already exists, skipping.")
            except asyncpg.exceptions.DuplicateObjectError:
                print(f"  -> Object already exists, skipping.")
            except Exception as e:
                # Ignore errors if objects already exist (naive approach for this homework)
                if "already exists" in str(e):
                    print(f"  -> Object already exists, skipping.")
                else:
                    print(f"  -> Error applying {filename}: {e}")
    
    await conn.close()
    print("Migrations completed.")

if __name__ == "__main__":
    asyncio.run(run_migrations())
