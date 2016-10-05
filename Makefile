DOCKER_COMPOSE_OPTS=--project-name tervis
DOCKER_RUN_OPTS=--rm -v`pwd`/tervis:/usr/src/app/tervis -it --network tervis_default --link kafka --link redis tervis

up:
	docker-compose $(DOCKER_COMPOSE_OPTS) up

upd:
	docker-compose $(DOCKER_COMPOSE_OPTS) up -d

down:
	docker-compose $(DOCKER_COMPOSE_OPTS) down

build:
	docker build -t tervis .

recorder:
	docker run $(DOCKER_RUN_OPTS) recorder

generator:
	docker run $(DOCKER_RUN_OPTS) generator

apiserver:
	docker run -p 8001:8000 $(DOCKER_RUN_OPTS) apiserver

shell:
	docker run $(DOCKER_RUN_OPTS) shell

.PHONY: up upd down build recorder generator shell
