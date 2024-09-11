docker context use default && \
docker compose -f docker-compose-prod.yml build && \
docker push damascus.flicker-lionfish.ts.net/argus:latest && \
scp docker-compose-prod.yml dflood@damascus.flicker-lionfish.ts.net:/home/dflood/argus/docker-compose-prod.yml
# scp django/db.sqlite3 dflood@damascus.flicker-lionfish.ts.net:/home/dflood/argus/db.sqlite3