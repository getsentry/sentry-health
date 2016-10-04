Start everything up:

    docker-compose up -d zookeeper kafka redis

Build the application images:

    docker-compose build

Generate some data:

    docker-compose run --rm application generator

Record some data:

    docker-compose run --rm application recorder

Tear everything down:

    docker-compose down
