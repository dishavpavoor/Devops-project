FROM python:3.12-slim-trixie AS python
FROM docker:29.1.3-cli AS dockercli
FROM jenkins/jenkins:lts-jdk21
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libbz2-1.0 libffi8 libsqlite3-0 libssl3t64 zlib1g liblzma5 \
    libncursesw6 libreadline8t64 libexpat1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=python /usr/local /usr/local
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins
RUN ldconfig && python3.12 --version && docker --version && docker compose version
RUN jenkins-plugin-cli --plugins workflow-aggregator git credentials-binding junit plain-credentials ssh-credentials timestamper
COPY deploy/jenkins/init.groovy /usr/share/jenkins/ref/init.groovy.d/10-project.groovy
# The local Compose controller explicitly runs as root to access Docker Desktop.
# Keep it localhost-only; it is intended for this trusted classroom project.
USER jenkins
