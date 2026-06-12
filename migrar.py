import os
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://calcada190ml_user:jlHeIvkzjfdh0PQ0RKlDY5ykWCDEpCTK@dpg-d8gu5q77f7vs739n2cf0-a.oregon-postgres.render.com/calcada190ml"

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE pedido ADD COLUMN IF NOT EXISTS fora_estoque BOOLEAN DEFAULT FALSE"))
    conn.commit()

print("Coluna adicionada com sucesso!")