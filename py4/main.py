from fastapi import FastAPI, Form, HTTPException, Response
from starlette.requests import Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
import aiohttp
import asyncio
import csv
import logging

app = FastAPI()
templates = Jinja2Templates(directory="templates")
logging.basicConfig(level=logging.INFO)

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

class CityWeather(BaseModel):
    country: str
    capital: str
    latitude: float
    longitude: float
    temperature: float = None

city_list = []

def read_cities(filename: str):
    global city_list
    city_list = []
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            city_list.append(CityWeather(**row))

read_cities('europe.csv')

async def get_weather_data(session: aiohttp.ClientSession, city: CityWeather) -> CityWeather:
    url = f"https://api.open-meteo.com/v1/forecast?latitude={city.latitude}&longitude={city.longitude}&current_weather=true"
    max_retries = 3
    retries = 0

    while retries < max_retries:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'current_weather' in data:
                        city.temperature = data['current_weather']['temperature']
                        return city
                    else:
                        raise HTTPException(status_code=400, detail="Invalid weather data format")
                else:
                    raise HTTPException(status_code=response.status, detail="Failed to fetch weather data")
        except Exception as e:
            logging.error(f"Error fetching weather data for {city.capital}: {str(e)}")
            retries += 1
            await asyncio.sleep(1)  # Wait for 1 second before retrying

    raise HTTPException(status_code=500, detail=f"Failed to fetch weather data after {max_retries} retries")

@app.get("/weather")
async def get_weather() -> List[CityWeather]:
    async with aiohttp.ClientSession() as session:
        tasks = [get_weather_data(session, city) for city in city_list]
        weather_data_tuple = await asyncio.gather(*tasks, return_exceptions=True)
        weather_data = [city for city in weather_data_tuple if isinstance(city, CityWeather)]
    weather_data.sort(key=lambda x: x.temperature)
    return weather_data

@app.post("/add_city")
async def add_city(country: str = Form(...), capital: str = Form(...), latitude: float = Form(...), longitude: float = Form(...)):
    new_city = CityWeather(country=country, capital=capital, latitude=latitude, longitude=longitude)
    city_list.append(new_city)
    return {"message": "City added"}

@app.delete("/remove_city/{city_name}")
async def remove_city(city_name: str):
    global city_list
    city_list = [city for city in city_list if city.capital != city_name]
    return {"message": "City removed"}

@app.post("/reset_cities")
async def reset_cities():
    global city_list
    read_cities('data/europe.csv')
    return {"message": "Cities list reset"}

@app.get("/", response_class=Response)
async def get_index(request: Request):
    weather_data = await get_weather()
    return templates.TemplateResponse("index.html", {"request": request, "weather_data": weather_data})