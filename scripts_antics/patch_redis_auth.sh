# Update .env
echo "REDIS_PASSWORD=sevalor_dev_redis" >> backend/.env

# Restart docker-compose with this password
export REDIS_PASSWORD=sevalor_dev_redis
docker compose down redis celery_worker celery_beat Bot
docker compose up -d redis celery_worker celery_beat Bot

# Update pytest configs
sed -i 's/redis:\/\/:@127.0.0.1:6380\/0/redis:\/\/:sevalor_dev_redis@127.0.0.1:6380\/0/g' backend/tests/conftest.py
sed -i 's/redis:\/\/:@127.0.0.1:6380\/0/redis:\/\/:sevalor_dev_redis@127.0.0.1:6380\/0/g' backend/app/workers/celery_app.py
sed -i 's/redis:\/\/127.0.0.1:6380\/0/redis:\/\/:sevalor_dev_redis@127.0.0.1:6380\/0/g' backend/app/workers/celery_app.py
