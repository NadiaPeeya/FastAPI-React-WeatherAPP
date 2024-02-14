from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from databases import Database
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import requests
import logging
from datetime import datetime, date
from config import DATABASE_URL  

Base = declarative_base()

class WeatherLog(Base):
    __tablename__ = "weather_logs"
    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(255), index=True)
    temperature = Column(Integer)
    humidity = Column(Integer)
    weather_description = Column(String(255))
    recorded_at = Column(DateTime, server_default=func.now())

logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

database_url = DATABASE_URL
database = Database(database_url)

engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

async def get_database():
    if not database.is_connected:
        await database.connect()
    return database

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI Weather App!"}

@app.post("/weather{city}")
async def get_weather(city: str, db: Database = Depends(get_database)):
    api_key = "635ce85c9428185f7a3cb18532e01b1f"
    units = "metric"

    try:
        response = requests.get(
            f"http://api.openweathermap.org/data/2.5/weather?q={city}&units={units}&appid={api_key}"
        )
        response.raise_for_status()
        data = response.json()
        logger.info(f"Weather data received for {city}: {data}")
        
        # Save weather data to the database
        async with db.transaction():
            await db.execute(WeatherLog.__table__.insert().values(
                city=data["name"],
                temperature=int(data["main"]["temp"]),
                humidity=int(data["main"]["humidity"]),
                weather_description=data["weather"][0]["description"],
            ))
        return data
    except requests.RequestException as e:
        logger.error(f"Failed to get weather data for {city}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get weather data: {str(e)}")

# Additional endpoint to retrieve weather logs for the same region on the same day
@app.get("/weather_logs")
async def get_weather_logs(city: str, db=Depends(get_db)):
    # Fetch weather logs for the same region (city) on the same day
    today = date.today()
    today_datetime = datetime(today.year, today.month, today.day)
    query = WeatherLog.__table__.select().where(
        WeatherLog.city == city,
        func.DATE(WeatherLog.recorded_at) == today_datetime.date()
    )
    result = await db.execute(query)
    return result.fetchall()

