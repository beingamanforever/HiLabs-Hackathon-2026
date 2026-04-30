FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including the AWS CLI v2 + jq, both required by
# entrypoint.sh to assume the judge-provided IAM role at container startup.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        unzip \
        ca-certificates \
        jq \
    && curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/awscliv2.zip /tmp/aws \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir -e ".[api,ml,demo]"

# Container reads/writes go through these paths. AWS_ROLE_ARN is unset by
# default — the entrypoint detects its absence and starts in local-dev mode.
ENV OUTPUT_DIR=/app/outputs \
    CACHE_DIR=/app/outputs/cache \
    BASE_DATA_FILE=/app/Base\ data_hackathon.xlsx \
    CLAIMS_DATA_FILE=/app/Claims\ data_Hackathon.xlsx \
    NPPES_DATA_FILE=/app/data/npidata_pfile.csv \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

# entrypoint.sh assumes the IAM role (if AWS_ROLE_ARN is set) before launching
# uvicorn. Override the default command by passing args to `docker run`, e.g.
#     docker run -e AWS_ROLE_ARN=... r3hackathon python scripts/predict_holdout.py ...
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD []
