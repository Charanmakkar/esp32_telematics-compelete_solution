"""Generate read-only API/schema references; no database or device operations."""
from pathlib import Path
import json
import sys
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects.mysql import dialect

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.main import app
from app.database.models import Base

if __name__=='__main__':
    (ROOT/'docs/api/openapi.json').write_text(json.dumps(app.openapi(),indent=2)+'\n',encoding='utf-8')
    parts=['-- Current MySQL schema reference generated from SQLAlchemy models.',
           '-- Use alembic upgrade head for deployment; this file does not replace migration history.',
           '-- No credentials are included.']
    for table in Base.metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=dialect())).strip()+';')
        for index in sorted(table.indexes,key=lambda x:x.name):
            parts.append(str(CreateIndex(index).compile(dialect=dialect())).strip()+';')
    sql='\n'.join(line.rstrip() for line in '\n\n'.join(parts).splitlines())+'\n'
    (ROOT/'database/schema.sql').write_text(sql,encoding='utf-8')
    print(f'Exported {len(app.openapi()["paths"])} paths and {len(Base.metadata.tables)} tables.')
