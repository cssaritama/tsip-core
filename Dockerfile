# Course project of tsip-core: the whole flow in a container.
# Build:  docker build -t tsip-capstone .
# Run:    docker run --rm -v "$HOME/tsip_capstone_data:/data" tsip-capstone                 # stored copy
#         docker run --rm -v "$HOME/tsip_capstone_data:/data" tsip-capstone --mode download # fresh data
# Data stay outside the image, in the mounted folder (never in Git or in the image).
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TSIP_CAPSTONE_DATA=/data
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
COPY registry ./registry
# Editable install: the evaluation and broker example read registry/ next to the source.
RUN pip install --no-cache-dir -e ".[calendar,capstone]"
VOLUME ["/data"]
ENTRYPOINT ["python", "-m", "tsip.capstone.run_all"]
CMD ["--mode", "file"]
