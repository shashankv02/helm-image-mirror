FROM python:3 as builder
RUN wget https://download.docker.com/linux/static/stable/x86_64/docker-19.03.8.tgz \
    && tar -xvf docker-19.03.8.tgz \
    && wget https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 -O get_helm.sh \
    && chmod 700 ./get_helm.sh \
    && ./get_helm.sh

FROM python:3
ENV HELM_EXPERIMENTAL_OCI=1
WORKDIR /workdir
COPY --from=builder /docker/docker /usr/local/bin/docker
COPY --from=builder /usr/local/bin/helm /usr/local/bin/helm
RUN python3 -m pip install pyyaml \
    && helm plugin install https://github.com/chartmuseum/helm-push.git

ADD src/ /usr/local/bin/
ENTRYPOINT ["helm_image_mirror.py"]