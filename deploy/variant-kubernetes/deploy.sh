#!/bin/bash
# kubectl apply -f ./feature-gates.yml  # error: unable to recognize "./feature-gates.yml": no matches for kind "Cluster" in version "cluster.x-k8s.io/v1alpha2"
echo "Creating namespace 'metaphotor'..."
kubectl create namespace metaphotor
kubectl config set-context --current --namespace=metaphotor

echo "Removing previous deployments, services and pods..."
kubectl delete service/postgresql deployment/postgresql service/flask deployment/flask  service/nginx deployment/nginx
kubectl delete pod --all
#kubectl delete pv --all
#kubectl delete pvc --all

echo "Applying volumes for postgres data and uwsgi socket..."
kubectl apply -f ./postgres-pv.yml
kubectl apply -f ./postgres-pvc.yml
kubectl apply -f ./flask-cm.yml
kubectl apply -f ./flask-pv-uwsgi-socket.yml
kubectl apply -f ./flask-pv-settings.yml
kubectl apply -f ./flask-pvc-uwsgi-socket.yml
kubectl apply -f ./flask-pvc-settings.yml

echo "Applying postgres deployment and service..."
kubectl apply -f ./postgres-secrets.yml
kubectl apply -f ./postgres-deploy.yml
kubectl apply -f ./postgres-svc.yml
#POD_NAME=$(kubectl get pod -l service=postgresql -o jsonpath="{.items[0].metadata.name}")
#kubectl exec $POD_NAME --stdin --tty -- createdb -U postgres metaphotor


echo "Applying the flask deployment and service..."
kubectl apply -f ./flask-deploy.yml
kubectl apply -f ./flask-svc.yml
#FLASK_POD_NAME=$(kubectl get pod -l app=flask -o jsonpath="{.items[0].metadata.name}")
#kubectl exec $FLASK_POD_NAME --stdin --tty -- python run.py recreate_db
#kubectl exec $FLASK_POD_NAME --stdin --tty -- python run.py seed_db


echo "Enabling the ingress, add metaphotor.info to /etc/hosts on your host..."
minikube addons enable ingress
kubectl apply -f ./kube-ing.yml

echo "Applying the nginx deployment and service..."
kubectl apply -f ./nginx-cm.yml
kubectl apply -f ./nginx-deploy.yml
kubectl apply -f ./nginx-svc.yml