# Deploy Spectre Healer on EC2

This deployment runs the read-only Healer HTTP API in Docker on an Amazon Linux 2023 EC2 instance. Provider and Neatlogs credentials are injected at runtime; they are not present in the image.

## 1. Build and push to ECR

Create an ECR repository once, then authenticate Docker, build, tag, and push:

```bash
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
REPOSITORY=spectre-healer
IMAGE="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPOSITORY"

aws ecr create-repository --repository-name "$REPOSITORY"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin \
    "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker build --platform linux/amd64 -t "$REPOSITORY:latest" .
docker tag "$REPOSITORY:latest" "$IMAGE:latest"
docker push "$IMAGE:latest"
```

Use `linux/arm64` instead when deploying to a Graviton EC2 instance. For repeatable production deployments, replace `:latest` in the compose environment with the pushed image digest.

## 2. Prepare the instance

Launch an Amazon Linux 2023 instance with an instance profile that can pull this ECR repository. Its security group should allow SSH only from an administrative CIDR. For direct access, allow TCP 8080 only from trusted clients. When using an Application Load Balancer, allow TCP 8080 on the instance only from the load balancer security group and configure `/healthz` as the target-group health check.

For an internet-facing deployment, terminate TLS on the load balancer and do not expose instance port 8080 directly to the internet.

Install and start Docker (the current Amazon Linux 2023 Docker package is available through `dnf`):

```bash
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
```

Reconnect so the Docker group membership takes effect. The standard Amazon Linux 2023 AMI includes AWS CLI v2; verify it with `aws --version` because ECR login uses it.

## 3. Configure and run

Copy `deploy/ec2/compose.yaml` and `deploy/ec2/.env.example` to `/opt/spectre-healer`, rename the environment file to `.env`, and fill it using values from your secret manager. Do not commit it.

```bash
cd /opt/spectre-healer
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin \
    "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

HEALER_IMAGE=123456789012.dkr.ecr.us-east-1.amazonaws.com/spectre-healer@sha256:REPLACE_ME
docker pull "$HEALER_IMAGE"
docker volume create healer-data
docker run -d --name spectre-healer \
  --restart unless-stopped \
  --env-file .env \
  -p 8080:8080 \
  -v healer-data:/data \
  --read-only \
  --tmpfs /tmp:size=64m,mode=1777 \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  "$HEALER_IMAGE"

docker ps --filter name=spectre-healer
curl http://127.0.0.1:8080/healthz
```

The ECR authorization token is temporary, so repeat the login before later pulls or automate it through your deployment process. `compose.yaml` provides the same hardened settings when Docker Compose is installed.

## API

Health endpoints do not expose configuration and need no token:

```text
GET /healthz
GET /readyz
```

API endpoints require `Authorization: Bearer $HEALER_SERVER_TOKEN`:

```text
GET  /v1/status
GET  /v1/scan?since=24h&tag=production&limit=100
POST /v1/scan  {"since":"24h","tag":"production","limit":100}
```

Example:

```bash
curl -H "Authorization: Bearer $HEALER_SERVER_TOKEN" \
  "http://127.0.0.1:8080/v1/scan?since=24h"
```

The container runs as UID/GID `10001`, drops Linux capabilities in Compose, has a read-only root filesystem, and persists the local trace fallback in the `healer-data` volume.
