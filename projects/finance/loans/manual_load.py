import sqlalchemy

def LoadToLocal(df, tblname, schema='public'):
    enginetxt = "postgresql://postgres:C4r0l1n3!@localhost/finance"
    engine = sqlalchemy.create_engine(enginetxt)
    with engine.connect() as con:
        df.to_sql(tblname, con, if_exists='append', index=False, schema=schema)