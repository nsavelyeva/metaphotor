## Deploy MetaPhotor with docker-compose

- Clone metaphotor app - e.g. run below command in a terminal window:
    ```
    git clone https://github.com/nsavelyeva/metaphotor
    ```
- Navigate to the folder _metaphotor/deploy/variant-docker_
- Adjust values for environment variables in _.env_ file
- Run the following command:
    ```
    docker-compose up -d --build
    ```

_Note:_ in case of the following error, remove _~/.docker/config.json_ file
(`docker logout` is not enough):
```
docker.credentials.errors.InitializationError: docker-credential-gcloud not installed or not available in PATH
```

