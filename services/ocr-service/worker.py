import os
from redis import Redis
from rq import Worker, Queue

# Define queues to listen to
listen = ['default']

# Redis connection URL (default to redis://redis:6379)
redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')

# Create Redis connection
conn = Redis.from_url(redis_url)

if __name__ == '__main__':
    # Create worker and start processing jobs
    worker = Worker([Queue(name, connection=conn) for name in listen])
    worker.work()
