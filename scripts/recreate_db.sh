#! /bin/sh
cd "${0%/*}/.."
docker-compse down -v
docker volume rm muistot-db-data
docker volume rm muistot-file-data
docker volume create --name muistot-db-data
docker volume create --name muistot-file-data
docker-compose up -d db