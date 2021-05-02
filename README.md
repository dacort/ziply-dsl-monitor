# Stupid DSL

Thanks to [danopstech's awesome repo(s)](https://github.com/danopstech/starlink).

## Grafana

https://grafana.com/docs/grafana/latest/administration/configure-docker/

```shell
docker volume create grafana-storage

docker run -d -p 3000:3000 --name=grafana -v grafana-storage:/var/lib/grafana grafana/grafana
```
