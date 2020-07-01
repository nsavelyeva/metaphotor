To get a docker image ready to be used in Kubernetes cluster, follow the steps:
- Navigate to the repository root
- Run: docker build -t metaphotor_src -f deploy/variant-kubernetes/dockerize/Dockerfile .
- Tag the image: docker tag metaphotor_src nsavelyeva/metaphotor
- Login to docker registry: docker login docker.io
- Push the image: docker push nsavelyeva/metaphotor