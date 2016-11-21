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

develop:
	pip install --editable ./libtervis
	TERVIS_SKIP_LIBTERVIS_DEP=1 pip install --editable .

recorder:
	docker run $(DOCKER_RUN_OPTS) recorder

generator:
	docker run $(DOCKER_RUN_OPTS) generator

apiserver:
	docker run -p 8001:8000 $(DOCKER_RUN_OPTS) apiserver

shell:
	docker run $(DOCKER_RUN_OPTS) shell

clean-db:
	@psql -c "drop database sentry_health_test" > /dev/null
	@psql -c "create database sentry_health_test" > /dev/null

test-light:
	py.test --tb=short tests -vv

test: clean-db test-light

lint:
	@flake8 tervis

.PHONY: up upd down build recorder generator shell clean-db test-light test lint develop
