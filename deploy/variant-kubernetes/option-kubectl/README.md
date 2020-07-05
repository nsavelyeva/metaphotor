## Deploy MetaPhotor on Kubernetes cluster (Minikube)

### Step 1 - Docker Image
To get a docker image ready to be used in Kubernetes cluster, follow the steps:
- Navigate to the repository root, e.g. into _github/metaphotor_.
- Run:
    ```
    docker build -t metaphotor_src -f deploy/variant-kubernetes/dockerize/Dockerfile .
    ```
- Tag the image: `docker tag metaphotor_src nsavelyeva/metaphotor`
- Login to docker registry: `docker login docker.io`
- Push the image: `docker push nsavelyeva/metaphotor`

### Step 2 - NFS Share
To get the folders _/media/nfs/media_ and _/media/nfs/watch_ shared via NFS
on an Ubuntu-based host, you can do the following:
- Change ownership recursively on all the files and give full access:
    ```
    sudo chown -R nobody:nogroup /media/nfs
    sudo chmod a+rwx -R /media/nfs
    ```
- Instal NFS server:
    ```
    sudo apt update
    sudo apt install nfs-kernel-server
    ```
- Add below lines to the main NFS config file _/etc/exports_: 
    ```
    /media/nfs/media *(rw,sync,no_subtree_check,no_root_squash)
    /media/nfs/watch *(rw,sync,no_subtree_check,no_root_squash)
    ```
- Apply changes:
    ```
    sudo exportfs -a
    sudo systemctl restart nfs-kernel-server
    ```
- Create a Firewall rule to allow access to NFS share:
    ```
    sudo ufw allow from any to any port nfs
    ```

### Step 3 - Kubernetes cluster
- Start Kubernetes cluster - in our case, `minikube`
(if needed, stop it first and remove via `minikube stop` and `minikube delete`):
    ```
    minikube start --cpus 4 --memory 8192
    ```
- On all cluster nodes
(in our case, the only `minikube` itself - enter it via `minikube ssh`),
install NFS client package:
    ```
    sudo apt update
    sudo apt install -y nfs-common
    exit
    ```

### Step 4 - MetaPhotor
Start MetaPhotor:
- Navigate to _deploy/variant-kubernetes/option-kubectl_ folder inside repository root.
- Run the start script:
    ```
    sh deploy.sh
    ```
- Add _metaphotor.info_ to _/etc/hosts_ on the host:
    ```
    sudo echo "$(minikube ip) metaphotor.info" | sudo tee -a /etc/hosts
    ````
- In browser, open http://metaphotor.info/

_Notes:_ 
- Run `minikube dashboard` and select namespace `metaphotor`
to observe MetaPhotor objects in `minikube` and troubleshoot issues.
- In case of this error:
    ```
    pod has unbound immediate PersistentVolumeClaims kubernetes nfs volume
    ```
re-run `sh deploy.sh` (TODO: fix this).
- Page http://metaphotor.info/statistics will display `502 Bad Gateway` error
if there are no video files and/or no photo files -
as a workaround, have media files of both types ingested.