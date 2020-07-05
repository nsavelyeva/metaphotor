#!/bin/bash
echo "Creating namespace 'metaphotor'..."
kubectl create namespace metaphotor
kubectl config set-context --current --namespace=metaphotor

echo "Removing previous deployments, services and pods..."
kubectl delete service/postgresql deployment/postgresql service/flask deployment/flask  service/nginx deployment/nginx
kubectl delete pod --all

echo "Applying volumes for postgres data and uwsgi socket..."
kubectl apply -f ./postgres-pv.yml
kubectl apply -f ./postgres-pvc.yml
kubectl apply -f ./flask-pv-uwsgi-socket.yml
kubectl apply -f ./flask-pv-persist.yml
kubectl apply -f ./flask-pvc-uwsgi-socket.yml
kubectl apply -f ./flask-pvc-persist.yml

echo "Applying postgres deployment and service..."
kubectl apply -f ./postgres-secrets.yml
kubectl apply -f ./postgres-deploy.yml
kubectl apply -f ./postgres-svc.yml

echo "Applying the flask deployment and service..."
kubectl apply -f ./flask-deploy.yml
kubectl apply -f ./flask-svc.yml

echo "Enabling the ingress, add metaphotor.info to /etc/hosts on your host..."
minikube addons enable ingress
kubectl apply -f ./kube-ing.yml

echo "Applying the nginx deployment and service..."
kubectl apply -f ./nginx-cm.yml
kubectl apply -f ./nginx-deploy.yml
kubectl apply -f ./nginx-svc.yml
